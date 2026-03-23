"""
Artifact creator: converts a generated spec into a concrete CTF artifact.

Currently supports: crypto_text_web, forensics_image_metadata, web_static_xss, chat_llm
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.ai_generator.crypto_utils import apply_chain, CryptoError

logger = logging.getLogger(__name__)


@dataclass
class ArtifactResult:
    # For crypto: the ciphertext string
    # For forensics/xss: not used directly (file_url is the artifact)
    content: Optional[str] = None
    # S3 URL for file-based artifacts (forensics, xss)
    file_url: Optional[str] = None
    # Data needed for validation (e.g. the chain used, flag location)
    verification_data: dict[str, Any] = field(default_factory=dict)
    # Error message if artifact creation failed
    error: Optional[str] = None


class ArtifactCreationError(RuntimeError):
    pass


async def create_artifact(task_type: str, spec: dict[str, Any], **kwargs: Any) -> ArtifactResult:
    """Dispatch to the appropriate artifact creator based on task_type."""
    if task_type == "crypto_text_web":
        return _create_crypto_text(spec)
    if task_type == "forensics_image_metadata":
        return await _create_forensics_image(spec, **kwargs)
    if task_type == "web_static_xss":
        return await _create_xss_page(spec, **kwargs)
    if task_type == "chat_llm":
        return _create_chat_task(spec)
    return ArtifactResult(error=f"Unsupported task_type for artifact creation: {task_type!r}")


def _create_crypto_text(spec: dict[str, Any]) -> ArtifactResult:
    """
    Apply the crypto_chain to the flag to produce ciphertext.

    Expected spec keys: flag, crypto_chain (list of {cipher, params})
    """
    flag = (spec.get("flag") or "").strip()
    crypto_chain = spec.get("crypto_chain") or []

    if not flag:
        return ArtifactResult(error="spec missing 'flag'")
    if not crypto_chain or not isinstance(crypto_chain, list):
        return ArtifactResult(error="spec missing or invalid 'crypto_chain'")

    try:
        ciphertext = apply_chain(flag, crypto_chain)
    except CryptoError as exc:
        return ArtifactResult(error=f"apply_chain failed: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in apply_chain")
        return ArtifactResult(error=f"apply_chain unexpected error: {exc}")

    return ArtifactResult(
        content=ciphertext,
        verification_data={"chain": crypto_chain, "flag": flag},
    )


async def _create_forensics_image(
    spec: dict[str, Any],
    batch_id: Optional[str] = None,
    variant_id: Optional[str] = None,
) -> ArtifactResult:
    """
    Pick a random stock image, inject the flag into metadata, upload to S3.
    All S3/Pillow calls run in threads via asyncio.to_thread.
    """
    from app.services.ai_generator.forensics_utils import (
        ForensicsError, VALID_HIDE_IN,
        pick_random_stock_image, download_image, inject_metadata, upload_image,
    )

    flag = (spec.get("flag") or "").strip()
    hide_in = (spec.get("hide_in") or "").strip()
    decoy_metadata = spec.get("decoy_metadata") or {}

    if not flag:
        return ArtifactResult(error="spec missing 'flag'")
    if hide_in not in VALID_HIDE_IN:
        return ArtifactResult(error=f"invalid hide_in: {hide_in!r}")
    if not batch_id or not variant_id:
        return ArtifactResult(error="Forensics: missing batch_id or variant_id for upload path")

    # Pick and download stock image
    try:
        stock_key = await asyncio.to_thread(pick_random_stock_image)
    except ForensicsError as exc:
        return ArtifactResult(error=str(exc))

    try:
        image_bytes = await asyncio.to_thread(download_image, stock_key)
    except ForensicsError as exc:
        return ArtifactResult(error=str(exc))

    # Inject metadata
    try:
        modified_bytes = await asyncio.to_thread(inject_metadata, image_bytes, flag, hide_in, decoy_metadata)
    except ForensicsError as exc:
        return ArtifactResult(error=str(exc))

    # Upload to S3
    try:
        s3_key = await asyncio.to_thread(upload_image, modified_bytes, batch_id, variant_id)
    except ForensicsError as exc:
        return ArtifactResult(error=str(exc))

    return ArtifactResult(
        file_url=s3_key,
        verification_data={
            "flag": flag,
            "hide_in": hide_in,
            "stock_image_key": stock_key,
            "decoy_fields": list(decoy_metadata.keys()),
        },
    )


async def _create_xss_page(
    spec: dict[str, Any],
    batch_id: Optional[str] = None,
    variant_id: Optional[str] = None,
) -> ArtifactResult:
    """
    Generate a self-contained XSS challenge HTML page and upload to S3.
    """
    from app.services.ai_generator.xss_utils import render_xss_page, upload_xss_page, XSSError

    flag = (spec.get("flag") or "").strip()
    xss_type = (spec.get("xss_type") or "").strip()

    if not flag:
        return ArtifactResult(error="spec missing 'flag'")
    if xss_type not in ("reflected", "stored", "dom"):
        return ArtifactResult(error=f"invalid xss_type: {xss_type!r}")
    if not batch_id or not variant_id:
        return ArtifactResult(error="XSS: missing batch_id or variant_id for upload path")

    try:
        html_content = render_xss_page(spec)
    except Exception as exc:
        return ArtifactResult(error=f"render_xss_page failed: {exc}")

    try:
        s3_key = await asyncio.to_thread(upload_xss_page, html_content, batch_id, variant_id)
    except XSSError as exc:
        return ArtifactResult(error=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error uploading XSS page")
        return ArtifactResult(error=f"upload_xss_page unexpected error: {exc}")

    return ArtifactResult(
        file_url=s3_key,
        verification_data={
            "flag": flag,
            "xss_type": xss_type,
            "vulnerable_param": spec.get("vulnerable_param", ""),
            "payload_solution": spec.get("payload_solution", ""),
        },
    )


def _create_chat_task(spec: dict[str, Any]) -> ArtifactResult:
    """
    Validate the chat_llm spec and return the system prompt template as content.
    No S3 upload needed — the template is stored in task.chat_system_prompt_template.
    """
    flag = (spec.get("flag") or "").strip()
    system_prompt = (spec.get("system_prompt_template") or "").strip()

    if not flag:
        return ArtifactResult(error="spec missing 'flag'")
    if not system_prompt:
        return ArtifactResult(error="spec missing 'system_prompt_template'")
    if "{{FLAG}}" not in system_prompt:
        return ArtifactResult(error="system_prompt_template must contain {{FLAG}} placeholder")

    return ArtifactResult(
        content=system_prompt,
        verification_data={
            "flag": flag,
            "defense_type": spec.get("defense_type", ""),
            "attack_hint": spec.get("attack_hint", ""),
        },
    )
