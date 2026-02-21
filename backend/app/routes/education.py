import re
import logging
from pathlib import PurePosixPath
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from botocore.exceptions import BotoCoreError, ClientError
from app.config import settings
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.contest import Submission, Task, TaskFlag
from app.models.user import UserRating
from app.services.storage import get_s3_client
from app.schemas.education import (
    PracticeTaskCard,
    PracticeTaskDetailResponse,
    PracticeTaskMaterialDownloadResponse,
    PracticeTaskMaterial,
    PracticeTaskListResponse,
    PracticeTaskSubmitRequest,
    PracticeTaskSubmitResponse,
    PracticeVpnInfo,
)

router = APIRouter(prefix="/education", tags=["Обучение"])
logger = logging.getLogger(__name__)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IP_CIDR_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\b")
_DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?\b")
_CONNECTION_RE = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3}(?:\s*\(VPN\))?)\b")
_PRESIGNED_TTL_SECONDS = 300


def difficulty_label(difficulty: int) -> str:
    if 1 <= difficulty <= 3:
        return "Легко"
    if 4 <= difficulty <= 7:
        return "Средне"
    if 8 <= difficulty <= 10:
        return "Сложно"
    return "Средне"


def difficulty_bounds(bucket: str) -> tuple[int, int]:
    if bucket == "easy":
        return (1, 3)
    if bucket == "medium":
        return (4, 7)
    return (8, 10)


def coerce_access_type(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"vpn", "vm", "link", "file", "just_flag"}:
        return normalized
    return "just_flag"


def infer_access_type_from_materials(material_rows: list[dict]) -> str:
    for row in material_rows:
        row_type = coerce_access_type(row.get("type"))
        if row_type != "just_flag":
            return row_type
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        meta_type = coerce_access_type(meta.get("access_type"))
        if meta_type != "just_flag":
            return meta_type
    return "just_flag"


def extract_hints(llm_raw_response: Optional[dict]) -> list[str]:
    if not isinstance(llm_raw_response, dict):
        return []

    candidates: list[str] = []
    for key in ("hints", "hint"):
        value = llm_raw_response.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
        if isinstance(value, list):
            candidates.extend([str(item).strip() for item in value if str(item).strip()])

    task_payload = llm_raw_response.get("task")
    if isinstance(task_payload, dict):
        for key in ("hints", "hint"):
            value = task_payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
            if isinstance(value, list):
                candidates.extend([str(item).strip() for item in value if str(item).strip()])

    # Preserve order while removing duplicates.
    seen: set[str] = set()
    unique_hints: list[str] = []
    for hint in candidates:
        if hint in seen:
            continue
        seen.add(hint)
        unique_hints.append(hint)

    return unique_hints


def is_task_solved(
    required_flag_ids: set[str],
    solved_flags: set[str],
    has_any_correct_submission: bool,
) -> bool:
    if required_flag_ids:
        return required_flag_ids.issubset(solved_flags)
    return has_any_correct_submission


def task_status(
    has_any_submission: bool,
    required_flag_ids: set[str],
    solved_flags: set[str],
    has_any_correct_submission: bool,
) -> str:
    if not has_any_submission:
        return "not_started"
    if is_task_solved(required_flag_ids, solved_flags, has_any_correct_submission):
        return "solved"
    return "in_progress"


def _first_http_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed.startswith("http://") or trimmed.startswith("https://"):
        return trimmed
    return None


def _storage_is_configured() -> bool:
    return bool(
        settings.s3_task_bucket_name
        and settings.s3_task_access_key
        and settings.s3_task_secret_key
    )


def _extract_storage_key_from_url(raw_value: Optional[str]) -> Optional[str]:
    url_value = _first_http_url(raw_value)
    if not url_value:
        return None

    bucket_name = settings.s3_task_bucket_name
    if not bucket_name:
        return None

    parsed = urlparse(url_value)
    path = unquote(parsed.path.lstrip("/"))
    if not path:
        return None

    if path.startswith(f"{bucket_name}/"):
        return path[len(bucket_name) + 1 :]

    host = (parsed.netloc or "").lower()
    if host.startswith(f"{bucket_name.lower()}."):
        return path

    return None


def _normalize_storage_key(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None

    parsed_from_url = _extract_storage_key_from_url(raw_value)
    if parsed_from_url:
        return parsed_from_url

    text_value = str(raw_value).strip()
    if not text_value:
        return None
    if text_value.startswith("http://") or text_value.startswith("https://"):
        return None

    return text_value.lstrip("/")


def _resolve_material_storage_key(material_row: dict) -> Optional[str]:
    meta = material_row.get("meta") if isinstance(material_row.get("meta"), dict) else {}
    candidates = [
        material_row.get("storage_key"),
        meta.get("download_storage_key"),
        meta.get("storage_key"),
        meta.get("download_url"),
    ]

    for candidate in candidates:
        resolved = _normalize_storage_key(candidate)
        if resolved:
            return resolved
    return None


def _resolve_material_external_url(material_row: dict) -> Optional[str]:
    meta = material_row.get("meta") if isinstance(material_row.get("meta"), dict) else {}
    material_type = str(material_row.get("type") or "").strip().lower()
    if material_type in {"file", "credentials"}:
        return (
            _first_http_url(meta.get("download_url"))
            or _first_http_url(material_row.get("url"))
            or _first_http_url(meta.get("url"))
        )
    return _first_http_url(meta.get("download_url")) or _first_http_url(meta.get("url"))


def _material_filename(material_row: dict, storage_key: Optional[str] = None) -> Optional[str]:
    name = str(material_row.get("name") or "").strip()
    if name:
        return name

    if storage_key:
        filename = PurePosixPath(storage_key).name.strip()
        if filename:
            return filename

    return None


def _build_presigned_download_url(storage_key: str, filename: Optional[str]) -> str:
    params: dict = {
        "Bucket": settings.s3_task_bucket_name,
        "Key": storage_key,
    }
    if filename:
        safe_name = filename.replace('"', "").replace("\n", " ").replace("\r", " ").strip()
        if safe_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{safe_name}"'

    client = get_s3_client(
        access_key=settings.s3_task_access_key,
        secret_key=settings.s3_task_secret_key,
    )
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=_PRESIGNED_TTL_SECONDS,
    )


def _parse_vpn_info(material_rows: list[dict]) -> PracticeVpnInfo:
    config_ip: Optional[str] = None
    allowed_ips: Optional[str] = None
    created_at: Optional[str] = None
    how_to_connect_url: Optional[str] = None
    download_url: Optional[str] = None

    for row in material_rows:
        material_type = str(row.get("type") or "").strip().lower()
        name = str(row.get("name") or "").strip()
        description = str(row.get("description") or "").strip()
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        source_url = (
            _first_http_url(row.get("url"))
            or _first_http_url(row.get("storage_key"))
            or _first_http_url(meta.get("url"))
        )
        text_blob = " ".join(part for part in [material_type, name, description] if part).lower()
        meta_blob = " ".join(str(value) for value in meta.values() if value is not None)
        description_blob = " ".join(part for part in [description, meta_blob] if part)

        config_ip_meta = str(meta.get("config_ip") or "").strip()
        if config_ip_meta and not config_ip:
            config_ip = config_ip_meta

        allowed_ips_meta = str(meta.get("allowed_ips") or "").strip()
        if allowed_ips_meta and not allowed_ips:
            allowed_ips = allowed_ips_meta

        created_at_meta = str(meta.get("created_at") or "").strip()
        if created_at_meta and not created_at:
            created_at = created_at_meta

        how_to_connect_meta = _first_http_url(meta.get("how_to_connect_url"))
        if how_to_connect_meta and not how_to_connect_url:
            how_to_connect_url = how_to_connect_meta

        download_meta = _first_http_url(meta.get("download_url"))
        if download_meta and not download_url:
            download_url = download_meta

        if source_url:
            if (
                not how_to_connect_url
                and any(token in text_blob for token in ("подключ", "connect", "guide", "инструкц"))
            ):
                how_to_connect_url = source_url
            elif (
                not download_url
                and any(token in text_blob for token in ("скач", "download", "config", "wireguard"))
            ):
                download_url = source_url
            elif material_type in {"file", "credentials"} and not download_url:
                download_url = source_url

        ip_cidr_matches = _IP_CIDR_RE.findall(description_blob)
        if ip_cidr_matches and not allowed_ips:
            allowed_ips = ip_cidr_matches[0]

        ip_matches = _IP_RE.findall(description_blob)
        if ip_matches and not config_ip:
            config_ip = ip_matches[0]

        if not created_at:
            date_match = _DATE_RE.search(description_blob)
            if date_match:
                created_at = date_match.group(0)

    return PracticeVpnInfo(
        config_ip=config_ip,
        allowed_ips=allowed_ips,
        created_at=created_at,
        how_to_connect_url=how_to_connect_url,
        download_url=download_url,
    )


def _extract_connection_ip(*text_values: Optional[str]) -> Optional[str]:
    for value in text_values:
        if not value:
            continue
        match = _CONNECTION_RE.search(value)
        if match:
            return match.group(1).strip()
    return None


async def _load_task_flags_map(
    db: AsyncSession,
    task_ids: Iterable[int],
) -> Dict[int, list[TaskFlag]]:
    task_id_list = list(task_ids)
    if not task_id_list:
        return {}

    result = await db.execute(
        select(TaskFlag)
        .where(TaskFlag.task_id.in_(task_id_list))
        .order_by(TaskFlag.task_id.asc(), TaskFlag.id.asc())
    )

    by_task: Dict[int, list[TaskFlag]] = {}
    for flag in result.scalars().all():
        by_task.setdefault(flag.task_id, []).append(flag)
    return by_task


async def _load_user_submission_state(
    db: AsyncSession,
    user_id: int,
    task_ids: Iterable[int],
) -> tuple[set[int], Dict[int, set[str]], set[int]]:
    task_id_list = list(task_ids)
    if not task_id_list:
        return set(), {}, set()

    result = await db.execute(
        select(Submission.task_id, Submission.flag_id, Submission.is_correct)
        .where(
            Submission.user_id == user_id,
            Submission.contest_id.is_(None),
            Submission.task_id.in_(task_id_list),
        )
    )

    has_any_submission: set[int] = set()
    solved_flags: Dict[int, set[str]] = {}
    has_any_correct: set[int] = set()

    for task_id, flag_id, is_correct in result.all():
        has_any_submission.add(task_id)
        if not is_correct:
            continue
        has_any_correct.add(task_id)
        if flag_id:
            solved_flags.setdefault(task_id, set()).add(flag_id)

    return has_any_submission, solved_flags, has_any_correct


async def _load_all_users_correct_flags(
    db: AsyncSession,
    task_ids: Iterable[int],
) -> Dict[int, Dict[int, set[str]]]:
    task_id_list = list(task_ids)
    if not task_id_list:
        return {}

    result = await db.execute(
        select(Submission.task_id, Submission.user_id, Submission.flag_id)
        .where(
            Submission.contest_id.is_(None),
            Submission.is_correct.is_(True),
            Submission.task_id.in_(task_id_list),
        )
    )

    output: Dict[int, Dict[int, set[str]]] = {}
    for task_id, user_id, flag_id in result.all():
        per_task = output.setdefault(task_id, {})
        per_user = per_task.setdefault(user_id, set())
        if flag_id:
            per_user.add(flag_id)
    return output


def _compute_passed_users_count(
    required_flag_ids: set[str],
    correct_flags_by_user: Dict[int, set[str]],
) -> int:
    if not correct_flags_by_user:
        return 0
    if not required_flag_ids:
        return len(correct_flags_by_user)
    return sum(1 for flags in correct_flags_by_user.values() if required_flag_ids.issubset(flags))


async def _load_task_materials(
    db: AsyncSession,
    task_id: int,
) -> list[dict]:
    try:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT id, type, name, description, url, storage_key, meta
                    FROM task_materials
                    WHERE task_id = :task_id
                    ORDER BY id ASC
                    """
                ),
                {"task_id": task_id},
            )
        ).mappings().all()
        return [dict(row) for row in rows]
    except ProgrammingError as exc:
        lowered = str(exc).lower()
        if "task_materials" in lowered and "meta" in lowered and "column" in lowered:
            await db.rollback()
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT id, type, name, description, url, storage_key
                        FROM task_materials
                        WHERE task_id = :task_id
                        ORDER BY id ASC
                        """
                    ),
                    {"task_id": task_id},
                )
            ).mappings().all()
            return [dict(row) for row in rows]
        if "task_materials" in lowered:
            await db.rollback()
            return []
        raise


def _find_material_by_id(materials: list[dict], material_id: int) -> Optional[dict]:
    for item in materials:
        try:
            if int(item.get("id")) == material_id:
                return item
        except (TypeError, ValueError):
            continue
    return None


@router.get("/practice/tasks", response_model=PracticeTaskListResponse)
async def list_practice_tasks(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    difficulty: Optional[str] = Query(None, pattern="^(easy|medium|hard)$"),
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(not_started|in_progress|solved)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user, _profile = current_user_data

    categories_rows = (
        await db.execute(
            select(Task.category)
            .where(Task.task_kind == "practice", Task.state == "ready")
            .distinct()
            .order_by(Task.category.asc())
        )
    ).scalars().all()
    categories = [row for row in categories_rows if row]

    query = (
        select(Task)
        .where(Task.task_kind == "practice", Task.state == "ready")
        .order_by(Task.created_at.desc())
    )

    if difficulty:
        min_diff, max_diff = difficulty_bounds(difficulty)
        query = query.where(Task.difficulty >= min_diff, Task.difficulty <= max_diff)

    if category and category.strip():
        query = query.where(func.lower(Task.category) == category.strip().lower())

    tasks = (await db.execute(query)).scalars().all()
    if not tasks:
        return PracticeTaskListResponse(items=[], total=0, categories=categories)

    task_ids = [task.id for task in tasks]
    flags_by_task = await _load_task_flags_map(db, task_ids)
    user_has_submission, user_solved_flags, user_has_correct = await _load_user_submission_state(
        db, user.id, task_ids
    )
    correct_flags_by_task_user = await _load_all_users_correct_flags(db, task_ids)

    cards: list[PracticeTaskCard] = []
    for task in tasks:
        required_flag_ids = {flag.flag_id for flag in flags_by_task.get(task.id, []) if flag.flag_id}
        solved_flags = user_solved_flags.get(task.id, set())
        has_any_submission = task.id in user_has_submission
        has_any_correct = task.id in user_has_correct

        my_status = task_status(
            has_any_submission=has_any_submission,
            required_flag_ids=required_flag_ids,
            solved_flags=solved_flags,
            has_any_correct_submission=has_any_correct,
        )

        if status_filter and my_status != status_filter:
            continue

        cards.append(
            PracticeTaskCard(
                id=task.id,
                title=task.title,
                summary=task.participant_description or task.story,
                category=task.category,
                difficulty=task.difficulty,
                difficulty_label=difficulty_label(task.difficulty),
                points=task.points,
                passed_users_count=_compute_passed_users_count(
                    required_flag_ids,
                    correct_flags_by_task_user.get(task.id, {}),
                ),
                my_status=my_status,
                tags=task.tags or [],
            )
        )

    total = len(cards)
    page_items = cards[offset : offset + limit]
    return PracticeTaskListResponse(items=page_items, total=total, categories=categories)


@router.get("/practice/tasks/{task_id}", response_model=PracticeTaskDetailResponse)
async def get_practice_task(
    task_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data

    task = (
        await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.task_kind == "practice",
                Task.state == "ready",
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    flags_by_task = await _load_task_flags_map(db, [task.id])
    user_has_submission, user_solved_flags, user_has_correct = await _load_user_submission_state(
        db, user.id, [task.id]
    )
    correct_flags_by_task_user = await _load_all_users_correct_flags(db, [task.id])

    required_flag_ids = {flag.flag_id for flag in flags_by_task.get(task.id, []) if flag.flag_id}
    solved_flags = user_solved_flags.get(task.id, set())
    has_any_submission = task.id in user_has_submission
    has_any_correct = task.id in user_has_correct

    my_status = task_status(
        has_any_submission=has_any_submission,
        required_flag_ids=required_flag_ids,
        solved_flags=solved_flags,
        has_any_correct_submission=has_any_correct,
    )

    materials = await _load_task_materials(db, task.id)
    access_type = coerce_access_type(getattr(task, "access_type", None))
    if access_type == "just_flag":
        access_type = infer_access_type_from_materials(materials)

    materials_payload = [
        PracticeTaskMaterial(
            id=int(item.get("id")),
            type=str(item.get("type") or ""),
            name=str(item.get("name") or ""),
            description=item.get("description"),
            url=item.get("url"),
            storage_key=None,
            meta=item.get("meta") if isinstance(item.get("meta"), dict) else None,
        )
        for item in materials
        if item.get("id") is not None
    ]

    vpn_info = _parse_vpn_info(materials)
    has_vpn_payload = any(
        [
            vpn_info.config_ip,
            vpn_info.allowed_ips,
            vpn_info.created_at,
            vpn_info.how_to_connect_url,
            vpn_info.download_url,
        ]
    )
    connection_ip = _extract_connection_ip(
        task.participant_description,
        task.story,
        *(str(item.get("description") or "") for item in materials),
        *(
            " ".join(str(value) for value in item.get("meta", {}).values() if value is not None)
            for item in materials
            if isinstance(item.get("meta"), dict)
        ),
    ) or vpn_info.config_ip

    hints = extract_hints(task.llm_raw_response)
    passed_users_count = _compute_passed_users_count(
        required_flag_ids,
        correct_flags_by_task_user.get(task.id, {}),
    )

    return PracticeTaskDetailResponse(
        id=task.id,
        title=task.title,
        category=task.category,
        difficulty=task.difficulty,
        difficulty_label=difficulty_label(task.difficulty),
        points=task.points,
        tags=task.tags or [],
        participant_description=task.participant_description,
        story=task.story,
        my_status=my_status,
        solved_flags_count=len(required_flag_ids.intersection(solved_flags)),
        required_flags_count=len(required_flag_ids),
        passed_users_count=passed_users_count,
        hints_count=len(hints),
        hints=hints,
        connection_ip=connection_ip,
        access_type=access_type,
        materials=materials_payload,
        vpn=vpn_info if has_vpn_payload else None,
    )


@router.post(
    "/practice/tasks/{task_id}/materials/{material_id}/download",
    response_model=PracticeTaskMaterialDownloadResponse,
)
async def get_practice_task_material_download(
    task_id: int,
    material_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data

    task = (
        await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.task_kind == "practice",
                Task.state == "ready",
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    materials = await _load_task_materials(db, task_id)
    material = _find_material_by_id(materials, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")

    storage_key = _resolve_material_storage_key(material)
    filename = _material_filename(material, storage_key)

    if storage_key:
        if not _storage_is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object Storage не настроен на сервере",
            )
        try:
            url = _build_presigned_download_url(storage_key, filename)
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to build presigned url for task_id=%s material_id=%s", task_id, material_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось подготовить ссылку на скачивание",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unexpected storage error while preparing download for task_id=%s material_id=%s",
                task_id,
                material_id,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось подготовить скачивание. Попробуйте позже.",
            ) from exc

        return PracticeTaskMaterialDownloadResponse(
            url=url,
            expires_in=_PRESIGNED_TTL_SECONDS,
            filename=filename,
        )

    external_url = _resolve_material_external_url(material)
    if external_url:
        return PracticeTaskMaterialDownloadResponse(
            url=external_url,
            expires_in=0,
            filename=filename,
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Для материала не настроен источник скачивания",
    )


@router.post("/practice/tasks/{task_id}/submit", response_model=PracticeTaskSubmitResponse)
async def submit_practice_flag(
    task_id: int,
    payload: PracticeTaskSubmitRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data

    task = (
        await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.task_kind == "practice",
                Task.state == "ready",
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    submitted_flag = (payload.flag or "").strip()
    if not submitted_flag:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Флаг пустой")

    task_flags = (
        await db.execute(
            select(TaskFlag).where(TaskFlag.task_id == task.id).order_by(TaskFlag.id.asc())
        )
    ).scalars().all()
    if not task_flags:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У задачи не настроены флаги")

    user_has_submission, user_solved_flags_map, user_has_correct = await _load_user_submission_state(
        db, user.id, [task.id]
    )
    required_flag_ids = {flag.flag_id for flag in task_flags if flag.flag_id}
    solved_flags_before = set(user_solved_flags_map.get(task.id, set()))
    has_correct_before = task.id in user_has_correct
    has_submission_before = task.id in user_has_submission

    was_solved_before = is_task_solved(
        required_flag_ids=required_flag_ids,
        solved_flags=solved_flags_before,
        has_any_correct_submission=has_correct_before,
    )

    matched_flag: Optional[TaskFlag] = None
    target_flag_id = (payload.flag_id or "").strip()
    if target_flag_id:
        for candidate in task_flags:
            if candidate.flag_id != target_flag_id:
                continue
            expected = (candidate.expected_value or "").strip()
            matched_flag = candidate if expected and expected == submitted_flag else None
            break
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный flag_id для задачи")
    else:
        for candidate in task_flags:
            expected = (candidate.expected_value or "").strip()
            if expected and expected == submitted_flag:
                matched_flag = candidate
                break

    is_correct = matched_flag is not None
    solved_flags_after = set(solved_flags_before)
    if is_correct and matched_flag.flag_id:
        solved_flags_after.add(matched_flag.flag_id)

    has_correct_after = has_correct_before or is_correct
    is_solved_after = is_task_solved(
        required_flag_ids=required_flag_ids,
        solved_flags=solved_flags_after,
        has_any_correct_submission=has_correct_after,
    )
    awarded_points = task.points if is_correct and not was_solved_before and is_solved_after else 0

    db.add(
        Submission(
            contest_id=None,
            task_id=task.id,
            user_id=user.id,
            flag_id=matched_flag.flag_id if matched_flag else (target_flag_id or "unknown"),
            submitted_value=submitted_flag,
            is_correct=is_correct,
            awarded_points=awarded_points,
        )
    )

    if awarded_points > 0:
        rating = (await db.execute(select(UserRating).where(UserRating.user_id == user.id))).scalar_one_or_none()
        if rating is None:
            rating = UserRating(
                user_id=user.id,
                contest_rating=0,
                practice_rating=0,
                first_blood=0,
            )
            db.add(rating)
        rating.practice_rating = int(rating.practice_rating or 0) + awarded_points
        rating.last_updated_at = datetime.now(timezone.utc)

    await db.commit()

    final_status = task_status(
        has_any_submission=True if submitted_flag else has_submission_before,
        required_flag_ids=required_flag_ids,
        solved_flags=solved_flags_after if is_correct else solved_flags_before,
        has_any_correct_submission=has_correct_after if is_correct else has_correct_before,
    )

    if is_correct and awarded_points > 0:
        message = "Флаг принят. Задача решена."
    elif is_correct:
        message = "Флаг принят."
    else:
        message = "Неверный флаг. Попробуйте ещё раз."

    return PracticeTaskSubmitResponse(
        is_correct=is_correct,
        awarded_points=awarded_points,
        status=final_status,
        solved_flags_count=len(required_flag_ids.intersection(solved_flags_after if is_correct else solved_flags_before)),
        required_flags_count=len(required_flag_ids),
        message=message,
    )
