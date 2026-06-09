#!/usr/bin/env python3
"""
Figma -> компактный JSON-снимок для генерации кода (удобен для Codex).

Зачем это нужно:
- Сырой payload Figma API огромный и шумный.
- Codex лучше работает с минимальной схемой: геометрия + layout + стили + дерево.
- Снимок можно версионировать, диффить и использовать для генерации React/Tailwind компонентов.

Безопасность:
- Никогда не хардкодить токены.
- Используй переменную окружения FIGMA_TOKEN.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import urllib.request


FIGMA_API = "https://api.figma.com/v1"


def http_get_json(url: str, token: str) -> dict:
    """Авторизованный GET-запрос к Figma API с парсингом JSON."""
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def rgb01_to_hex(color: dict) -> str:
    """
    Конвертирует Figma-цвет {r,g,b} из диапазона 0..1 в #RRGGBB.
    """
    r = int(round(color.get("r", 0) * 255))
    g = int(round(color.get("g", 0) * 255))
    b = int(round(color.get("b", 0) * 255))
    return f"#{r:02X}{g:02X}{b:02X}"


def pick_fills(node: dict) -> List[dict]:
    fills = node.get("fills") or []
    out = []
    for f in fills:
        if not f.get("visible", True):
            continue
        t = f.get("type")
        if t == "SOLID":
            out.append({
                "type": "SOLID",
                "color": rgb01_to_hex(f.get("color", {})),
                "opacity": f.get("opacity", 1)
            })
        # Можно расширить до GRADIENT_* и IMAGE при необходимости.
    return out


def pick_strokes(node: dict) -> List[dict]:
    strokes = node.get("strokes") or []
    out = []
    for s in strokes:
        if not s.get("visible", True):
            continue
        if s.get("type") == "SOLID":
            out.append({
                "type": "SOLID",
                "color": rgb01_to_hex(s.get("color", {})),
                "opacity": s.get("opacity", 1)
            })
    return out


def pick_text_style(node: dict) -> Optional[dict]:
    style = node.get("style")
    if not style:
        return None
    # Нормализуем lineHeight и letterSpacing, если присутствуют.
    return {
        "fontFamily": style.get("fontFamily"),
        "fontPostScriptName": style.get("fontPostScriptName"),
        "fontWeight": style.get("fontWeight"),
        "fontSize": style.get("fontSize"),
        "lineHeightPx": style.get("lineHeightPx"),
        "letterSpacing": style.get("letterSpacing"),
        "textAlignHorizontal": style.get("textAlignHorizontal"),
        "textAlignVertical": style.get("textAlignVertical"),
    }


def pick_effects(node: dict) -> List[dict]:
    effects = node.get("effects") or []
    out = []
    for e in effects:
        if not e.get("visible", True):
            continue
        t = e.get("type")
        if t in ("DROP_SHADOW", "INNER_SHADOW", "LAYER_BLUR", "BACKGROUND_BLUR"):
            eff = {"type": t}
            if "radius" in e:
                eff["radius"] = e["radius"]
            if "offset" in e:
                eff["offset"] = e["offset"]
            if "color" in e:
                eff["color"] = rgb01_to_hex(e["color"])
                eff["opacity"] = e.get("color", {}).get("a", 1)
            out.append(eff)
    return out


def pick_layout(node: dict) -> Optional[dict]:
    # Auto-layout есть в основном у FRAME/COMPONENT/INSTANCE с layoutMode
    if "layoutMode" not in node:
        return None
    mode = node.get("layoutMode")
    if mode == "NONE":
        return None
    return {
        "mode": mode,  # HORIZONTAL / VERTICAL
        "padding": {
            "t": node.get("paddingTop", 0),
            "r": node.get("paddingRight", 0),
            "b": node.get("paddingBottom", 0),
            "l": node.get("paddingLeft", 0),
        },
        "gap": node.get("itemSpacing", 0),
        "align_primary": node.get("primaryAxisAlignItems"),
        "align_counter": node.get("counterAxisAlignItems"),
        "sizing_primary": node.get("primaryAxisSizingMode"),
        "sizing_counter": node.get("counterAxisSizingMode"),
    }


def pick_radii(node: dict) -> Optional[Any]:
    if "cornerRadius" in node and node["cornerRadius"] is not None:
        return node["cornerRadius"]
    if "rectangleCornerRadii" in node and node["rectangleCornerRadii"]:
        return node["rectangleCornerRadii"]
    return None


def compact_node(node: dict) -> dict:
    """
    Преобразует сырой Figma-узел в компактное представление.
    """
    box = node.get("absoluteBoundingBox") or {}
    out: Dict[str, Any] = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "box": {
            "x": box.get("x"),
            "y": box.get("y"),
            "w": box.get("width"),
            "h": box.get("height"),
        }
    }

    layout = pick_layout(node)
    if layout:
        out["layout"] = layout

    style: Dict[str, Any] = {}
    fills = pick_fills(node)
    if fills:
        style["fills"] = fills
    strokes = pick_strokes(node)
    if strokes:
        style["strokes"] = strokes
        if "strokeWeight" in node:
            style["strokeWeight"] = node.get("strokeWeight")
    radii = pick_radii(node)
    if radii is not None:
        style["radii"] = radii
    effects = pick_effects(node)
    if effects:
        style["effects"] = effects

    text_style = pick_text_style(node)
    if text_style:
        out["text"] = {"characters": node.get("characters", ""), "style": text_style}

    if style:
        out["style"] = style

    children = node.get("children") or []
    if children:
        out["children"] = [compact_node(ch) for ch in children]

    return out


def build_snapshot(file_key: str, root_node_id: str, raw: dict) -> dict:
    """
    Строит Codex-совместимый снимок JSON из ответа `/nodes`.
    """
    # Figma возвращает: {"nodes": {"<id>": {"document": {...}, "components": {...}}}}
    node_payload = (raw.get("nodes") or {}).get(root_node_id) or {}
    doc = node_payload.get("document")
    if not doc:
        raise RuntimeError("No document for requested node. Check node-id and permissions.")

    snapshot = {
        "meta": {
            "source": "figma",
            "file_key": file_key,
            "captured_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "root_node_id": root_node_id,
        },
        # Токены опциональны; можно заполнить позже, анализируя стили по узлам.
        "tokens": {
            "colors": {},
            "radii": {},
            "typography": {},
        },
        "tree": compact_node(doc),
    }
    return snapshot


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: figma_snapshot.py <FILE_KEY> <NODE_ID> [out.json]")
        print("Example: figma_snapshot.py J8iTUVFUOPGR6EGNoCay4f 715-28201 snapshot.json")
        return 2

    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        print("ERROR: FIGMA_TOKEN env var is required.")
        return 2

    file_key = sys.argv[1]
    node_id = sys.argv[2].replace("-", ":")
    out_path = sys.argv[3] if len(sys.argv) >= 4 else "snapshot.json"

    qs = urlencode({"ids": node_id})
    url = f"{FIGMA_API}/files/{file_key}/nodes?{qs}"
    raw = http_get_json(url, token)

    snapshot = build_snapshot(file_key, node_id, raw)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())