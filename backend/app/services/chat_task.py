import asyncio
import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from openai import AsyncOpenAI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contest import Task, TaskChatMessage, TaskChatSession

logger = logging.getLogger(__name__)

FLAG_PLACEHOLDER = "{{FLAG}}"
FLAG_TOKEN_LENGTH = 8
DEFAULT_CHAT_USER_MESSAGE_MAX_CHARS = 150
DEFAULT_CHAT_MODEL_MAX_OUTPUT_TOKENS = 256
DEFAULT_CHAT_SESSION_TTL_MINUTES = 180
CHAT_USER_MESSAGE_MAX_CHARS_RANGE = (20, 500)
CHAT_MODEL_MAX_OUTPUT_TOKENS_RANGE = (32, 1024)
CHAT_SESSION_TTL_MINUTES_RANGE = (15, 720)
CHAT_CONTEXT_MESSAGE_LIMIT = 24
LLM_COMPLETION_MAX_ATTEMPTS = 3
LLM_COMPLETION_RETRY_DELAYS_SECONDS = (0.25, 0.6)
CHAT_ASSISTANT_REPLY_MAX_ROUNDS = 8
CHAT_ASSISTANT_REPLY_RETRY_DELAYS_SECONDS = (0.35, 0.8, 1.3)
YANDEX_CHAT_MODEL_ID = "deepseek-v32"
YANDEX_CHAT_MODEL_VERSION = "latest"

_CONTEST_FILTER_UNSET = object()
_FLAG_CONTENT_PATTERN = re.compile(r"\{([^{}]+)\}")
_async_client: Optional[AsyncOpenAI] = None


class ChatTaskError(RuntimeError):
    pass


class ChatTaskConfigError(ChatTaskError):
    pass


class ChatTaskSessionExpiredError(ChatTaskError):
    pass


class ChatTaskSessionReadOnlyError(ChatTaskError):
    pass


@dataclass(frozen=True)
class ChatLimits:
    user_message_max_chars: int
    model_max_output_tokens: int
    session_ttl_minutes: int


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _range_check(name: str, value: int, bounds: tuple[int, int]) -> None:
    min_value, max_value = bounds
    if not (min_value <= value <= max_value):
        raise ChatTaskConfigError(f"{name} must be in range {min_value}..{max_value}")


def validate_chat_task_config_values(
    *,
    access_type: str,
    chat_system_prompt_template: Optional[str],
    chat_user_message_max_chars: Any,
    chat_model_max_output_tokens: Any,
    chat_session_ttl_minutes: Any,
) -> tuple[Optional[str], ChatLimits]:
    normalized_access_type = str(access_type or "just_flag").strip().lower()
    prompt_text = (chat_system_prompt_template or "").strip() or None
    limits = ChatLimits(
        user_message_max_chars=_safe_int(
            chat_user_message_max_chars,
            DEFAULT_CHAT_USER_MESSAGE_MAX_CHARS,
        ),
        model_max_output_tokens=_safe_int(
            chat_model_max_output_tokens,
            DEFAULT_CHAT_MODEL_MAX_OUTPUT_TOKENS,
        ),
        session_ttl_minutes=_safe_int(
            chat_session_ttl_minutes,
            DEFAULT_CHAT_SESSION_TTL_MINUTES,
        ),
    )

    _range_check(
        "chat_user_message_max_chars",
        limits.user_message_max_chars,
        CHAT_USER_MESSAGE_MAX_CHARS_RANGE,
    )
    _range_check(
        "chat_model_max_output_tokens",
        limits.model_max_output_tokens,
        CHAT_MODEL_MAX_OUTPUT_TOKENS_RANGE,
    )
    _range_check(
        "chat_session_ttl_minutes",
        limits.session_ttl_minutes,
        CHAT_SESSION_TTL_MINUTES_RANGE,
    )

    if normalized_access_type == "chat":
        if not prompt_text:
            raise ChatTaskConfigError("chat_system_prompt_template is required for chat tasks")
        if FLAG_PLACEHOLDER not in prompt_text:
            raise ChatTaskConfigError(
                f"chat_system_prompt_template must contain {FLAG_PLACEHOLDER}"
            )

    return prompt_text, limits


def get_chat_limits_for_task(task: Task) -> ChatLimits:
    _, limits = validate_chat_task_config_values(
        access_type=str(task.access_type or "just_flag"),
        chat_system_prompt_template=task.chat_system_prompt_template,
        chat_user_message_max_chars=task.chat_user_message_max_chars,
        chat_model_max_output_tokens=task.chat_model_max_output_tokens,
        chat_session_ttl_minutes=task.chat_session_ttl_minutes,
    )
    return limits


def _build_async_client() -> AsyncOpenAI:
    global _async_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY (or YANDEX_API_KEY / YC_API_KEY)")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER (or YANDEX_CLOUD_FOLDER_ID / YANDEX_FOLDER_ID / YC_FOLDER_ID)")
    if missing:
        raise ChatTaskError(f"Missing Yandex LLM config: {', '.join(missing)}")
    if _async_client is None:
        _async_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder,
        )
    return _async_client


def derive_dynamic_flag(flag_seed: str) -> str:
    secret_key = (settings.SECRET_KEY or "").strip()
    if not secret_key:
        raise ChatTaskError("SECRET_KEY is required for dynamic chat flags")
    payload = str(flag_seed or "").strip().encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest().upper()
    return f"FLAG{{{digest[:FLAG_TOKEN_LENGTH]}}}"


def _derive_legacy_dynamic_flag(flag_seed: str) -> str:
    secret_key = (settings.SECRET_KEY or "").strip()
    if not secret_key:
        raise ChatTaskError("SECRET_KEY is required for dynamic chat flags")
    payload = str(flag_seed or "").strip().encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest().lower()
    return f"FLAG{{{digest[:32]}}}"


def extract_flag_token_content(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _FLAG_CONTENT_PATTERN.search(text)
    if match:
        return (match.group(1) or "").strip()
    return text


def normalize_flag_token_content(value: str) -> str:
    return str(value or "").strip().upper()


def derive_dynamic_flag_token_candidates(flag_seed: str) -> set[str]:
    current = normalize_flag_token_content(extract_flag_token_content(derive_dynamic_flag(flag_seed)))
    legacy = normalize_flag_token_content(extract_flag_token_content(_derive_legacy_dynamic_flag(flag_seed)))
    return {token for token in (current, legacy) if token}


def _build_session_system_prompt(task: Task, flag_seed: str) -> str:
    template = (task.chat_system_prompt_template or "").strip()
    if not template:
        raise ChatTaskConfigError("chat_system_prompt_template is empty")
    if FLAG_PLACEHOLDER not in template:
        raise ChatTaskConfigError(
            f"chat_system_prompt_template must contain {FLAG_PLACEHOLDER}"
        )
    return template.replace(FLAG_PLACEHOLDER, derive_dynamic_flag(flag_seed))


def _contest_scope_filter(contest_id: Optional[int]):
    if contest_id is None:
        return TaskChatSession.contest_id.is_(None)
    return TaskChatSession.contest_id == contest_id


async def cleanup_expired_unsolved_chat_sessions(
    db: AsyncSession,
    *,
    task_id: Optional[int] = None,
    user_id: Optional[int] = None,
    contest_id: Any = _CONTEST_FILTER_UNSET,
) -> None:
    now = datetime.now(timezone.utc)
    stmt = delete(TaskChatSession).where(
        TaskChatSession.status == "active",
        TaskChatSession.expires_at <= now,
    )
    if task_id is not None:
        stmt = stmt.where(TaskChatSession.task_id == task_id)
    if user_id is not None:
        stmt = stmt.where(TaskChatSession.user_id == user_id)
    if contest_id is not _CONTEST_FILTER_UNSET:
        stmt = stmt.where(_contest_scope_filter(contest_id))
    await db.execute(stmt)


async def _load_latest_session(
    db: AsyncSession,
    *,
    task_id: int,
    user_id: int,
    contest_id: Optional[int],
    statuses: Iterable[str],
) -> Optional[TaskChatSession]:
    status_list = [status for status in statuses if status]
    if not status_list:
        return None
    query = (
        select(TaskChatSession)
        .where(
            TaskChatSession.task_id == task_id,
            TaskChatSession.user_id == user_id,
            _contest_scope_filter(contest_id),
            TaskChatSession.status.in_(status_list),
        )
        .order_by(
            TaskChatSession.solved_at.desc().nullslast(),
            TaskChatSession.created_at.desc(),
            TaskChatSession.id.desc(),
        )
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_or_create_chat_session(
    db: AsyncSession,
    *,
    task: Task,
    user_id: int,
    contest_id: Optional[int],
) -> tuple[TaskChatSession, bool]:
    await cleanup_expired_unsolved_chat_sessions(
        db,
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
    )

    active_session = await _load_latest_session(
        db,
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
        statuses=("active",),
    )
    if active_session is not None:
        return active_session, False

    solved_session = await _load_latest_session(
        db,
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
        statuses=("solved",),
    )
    if solved_session is not None:
        return solved_session, True

    limits = get_chat_limits_for_task(task)
    now = datetime.now(timezone.utc)
    session = TaskChatSession(
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
        status="active",
        flag_seed=secrets.token_hex(32),
        expires_at=now + timedelta(minutes=limits.session_ttl_minutes),
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()
    return session, False


async def restart_chat_session(
    db: AsyncSession,
    *,
    task: Task,
    user_id: int,
    contest_id: Optional[int],
) -> TaskChatSession:
    await cleanup_expired_unsolved_chat_sessions(
        db,
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
    )

    await db.execute(
        delete(TaskChatSession).where(
            TaskChatSession.task_id == task.id,
            TaskChatSession.user_id == user_id,
            _contest_scope_filter(contest_id),
            TaskChatSession.status == "active",
        )
    )

    limits = get_chat_limits_for_task(task)
    now = datetime.now(timezone.utc)
    session = TaskChatSession(
        task_id=task.id,
        user_id=user_id,
        contest_id=contest_id,
        status="active",
        flag_seed=secrets.token_hex(32),
        expires_at=now + timedelta(minutes=limits.session_ttl_minutes),
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()
    return session


async def abort_active_chat_session(
    db: AsyncSession,
    *,
    task_id: int,
    user_id: int,
    contest_id: Optional[int],
) -> int:
    result = await db.execute(
        delete(TaskChatSession).where(
            TaskChatSession.task_id == task_id,
            TaskChatSession.user_id == user_id,
            _contest_scope_filter(contest_id),
            TaskChatSession.status == "active",
        )
    )
    return int(result.rowcount or 0)


async def get_session_for_chat_submit(
    db: AsyncSession,
    *,
    task_id: int,
    user_id: int,
    contest_id: Optional[int],
    include_solved: bool = True,
) -> Optional[TaskChatSession]:
    await cleanup_expired_unsolved_chat_sessions(
        db,
        task_id=task_id,
        user_id=user_id,
        contest_id=contest_id,
    )
    active_session = await _load_latest_session(
        db,
        task_id=task_id,
        user_id=user_id,
        contest_id=contest_id,
        statuses=("active",),
    )
    if active_session is not None:
        return active_session
    if not include_solved:
        return None
    return await _load_latest_session(
        db,
        task_id=task_id,
        user_id=user_id,
        contest_id=contest_id,
        statuses=("solved",),
    )


async def list_chat_messages(
    db: AsyncSession,
    *,
    session_id: int,
    limit: int = 200,
) -> list[TaskChatMessage]:
    if limit <= 0:
        return []
    result = await db.execute(
        select(TaskChatMessage)
        .where(TaskChatMessage.session_id == session_id)
        .order_by(TaskChatMessage.created_at.asc(), TaskChatMessage.id.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def _list_context_messages_for_llm(
    db: AsyncSession,
    *,
    session_id: int,
) -> list[TaskChatMessage]:
    result = await db.execute(
        select(TaskChatMessage)
        .where(TaskChatMessage.session_id == session_id)
        .order_by(TaskChatMessage.created_at.desc(), TaskChatMessage.id.desc())
        .limit(CHAT_CONTEXT_MESSAGE_LIMIT)
    )
    rows = result.scalars().all()
    rows.reverse()
    return rows


async def add_chat_message(
    db: AsyncSession,
    *,
    session_id: int,
    role: str,
    content: str,
) -> TaskChatMessage:
    message = TaskChatMessage(
        session_id=session_id,
        role=role,
        content=content,
    )
    db.add(message)
    await db.flush()
    return message


def _extract_text_from_llm_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _extract_text_from_llm_content(item)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()

    if isinstance(content, dict):
        for key in ("text", "content", "value"):
            next_value = content.get(key)
            if next_value is content:
                continue
            text = _extract_text_from_llm_content(next_value)
            if text:
                return text
        return ""

    for attr in ("text", "content", "value"):
        next_value = getattr(content, attr, None)
        if next_value is content:
            continue
        text = _extract_text_from_llm_content(next_value)
        if text:
            return text
    return ""


def _extract_text_from_llm_response(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return ""

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, dict):
        message = first_choice.get("message")
    if message is not None:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        text = _extract_text_from_llm_content(content)
        if text:
            return text

    fallback_text = getattr(first_choice, "text", None)
    if fallback_text is None and isinstance(first_choice, dict):
        fallback_text = first_choice.get("text")
    return _extract_text_from_llm_content(fallback_text)


def _extract_error_details(error: Exception) -> tuple[Optional[int], Optional[str], Optional[str], str]:
    status_code = _extract_error_status_code(error)
    error_type = getattr(error, "type", None)
    error_code = getattr(error, "code", None)
    message = str(error)

    body = getattr(error, "body", None)
    if isinstance(body, dict):
        payload = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(payload, dict):
            error_type = error_type or payload.get("type")
            error_code = error_code or payload.get("code")
            body_message = payload.get("message")
            if body_message:
                message = str(body_message)

    truncated_message = " ".join(str(message or "").split())
    if len(truncated_message) > 500:
        truncated_message = f"{truncated_message[:500]}..."
    return (
        status_code,
        str(error_type) if error_type else None,
        str(error_code) if error_code else None,
        truncated_message or "unknown",
    )


def _describe_llm_response_shape(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return "choices=0"
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, dict):
        message = first_choice.get("message")
    content = None
    if message is not None:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
    if content is None:
        content = getattr(first_choice, "text", None)
        if content is None and isinstance(first_choice, dict):
            content = first_choice.get("text")
    return f"choices={len(choices)} content_type={type(content).__name__}"


def _extract_error_status_code(error: Exception) -> Optional[int]:
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _is_retryable_llm_error(error: Exception) -> bool:
    status_code = _extract_error_status_code(error)
    if status_code is not None:
        return status_code >= 500 or status_code in {408, 429}
    lowered_text = str(error).lower()
    transient_markers = (
        "server_error",
        "internal server error",
        "timeout",
        "timed out",
        "connection",
    )
    return any(marker in lowered_text for marker in transient_markers)


def _retry_delay_for_attempt(attempt_index: int) -> float:
    if attempt_index < len(LLM_COMPLETION_RETRY_DELAYS_SECONDS):
        return LLM_COMPLETION_RETRY_DELAYS_SECONDS[attempt_index]
    return LLM_COMPLETION_RETRY_DELAYS_SECONDS[-1]


def _reply_retry_delay_for_round(round_index: int) -> float:
    if round_index < len(CHAT_ASSISTANT_REPLY_RETRY_DELAYS_SECONDS):
        return CHAT_ASSISTANT_REPLY_RETRY_DELAYS_SECONDS[round_index]
    return CHAT_ASSISTANT_REPLY_RETRY_DELAYS_SECONDS[-1]


async def _run_llm_chat_completion(
    *,
    messages: list[dict[str, str]],
    max_output_tokens: int,
    retry_round: int,
    log_context: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    client = _build_async_client()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    model_name = f"gpt://{folder}/{YANDEX_CHAT_MODEL_ID}/{YANDEX_CHAT_MODEL_VERSION}"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"
    last_error: Optional[Exception] = None
    for attempt in range(LLM_COMPLETION_MAX_ATTEMPTS):
        try:
            response = await client.chat.completions.create(
                model=model_name,
                reasoning_effort=reasoning_effort,
                max_tokens=max_output_tokens,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            retryable = _is_retryable_llm_error(exc)
            status_code, error_type, error_code, error_message = _extract_error_details(exc)
            logger.warning(
                "Chat LLM request failed (round=%s attempt=%s/%s retryable=%s status=%s type=%s code=%s message=%s context=%s)",
                retry_round,
                attempt + 1,
                LLM_COMPLETION_MAX_ATTEMPTS,
                retryable,
                status_code,
                error_type,
                error_code,
                error_message,
                log_context or {},
            )
            if not retryable:
                raise ChatTaskError("Yandex model request failed") from exc
            if attempt + 1 < LLM_COMPLETION_MAX_ATTEMPTS:
                await asyncio.sleep(_retry_delay_for_attempt(attempt))
                continue
            return None

        text = _extract_text_from_llm_response(response)
        if text:
            return text
        logger.warning(
            "Chat LLM returned empty content (round=%s attempt=%s/%s shape=%s context=%s)",
            retry_round,
            attempt + 1,
            LLM_COMPLETION_MAX_ATTEMPTS,
            _describe_llm_response_shape(response),
            log_context or {},
        )
        if attempt + 1 < LLM_COMPLETION_MAX_ATTEMPTS:
            await asyncio.sleep(_retry_delay_for_attempt(attempt))

    if last_error is not None:
        if _is_retryable_llm_error(last_error):
            return None
        raise ChatTaskError("Yandex model request failed") from last_error
    return None


async def generate_chat_reply(
    db: AsyncSession,
    *,
    task: Task,
    session: TaskChatSession,
    user_message: str,
) -> str:
    if session.status != "active":
        raise ChatTaskSessionReadOnlyError("Чат-сессия уже закрыта")

    now = datetime.now(timezone.utc)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise ChatTaskSessionExpiredError("Чат-сессия истекла")

    limits = get_chat_limits_for_task(task)
    message_text = (user_message or "").strip()
    if not message_text:
        raise ChatTaskError("Message is empty")
    if len(message_text) > limits.user_message_max_chars:
        raise ChatTaskError(
            f"Message length exceeds {limits.user_message_max_chars} characters"
        )

    await add_chat_message(
        db,
        session_id=session.id,
        role="user",
        content=message_text,
    )
    context_rows = await _list_context_messages_for_llm(
        db,
        session_id=session.id,
    )
    payload_messages = [
        {"role": "system", "content": _build_session_system_prompt(task, session.flag_seed)},
        *[
            {"role": message.role, "content": message.content}
            for message in context_rows
        ],
    ]
    log_context = {
        "task_id": task.id,
        "session_id": session.id,
        "contest_id": session.contest_id,
        "user_id": session.user_id,
    }
    assistant_text: Optional[str] = None
    for round_index in range(CHAT_ASSISTANT_REPLY_MAX_ROUNDS):
        assistant_text = await _run_llm_chat_completion(
            messages=payload_messages,
            max_output_tokens=limits.model_max_output_tokens,
            retry_round=round_index + 1,
            log_context=log_context,
        )
        if assistant_text:
            break
        if round_index + 1 < CHAT_ASSISTANT_REPLY_MAX_ROUNDS:
            retry_delay = _reply_retry_delay_for_round(round_index)
            logger.warning(
                "Chat LLM returned no text, retrying same user message (round=%s/%s delay=%.2fs context=%s)",
                round_index + 1,
                CHAT_ASSISTANT_REPLY_MAX_ROUNDS,
                retry_delay,
                log_context,
            )
            await asyncio.sleep(retry_delay)

    if not assistant_text:
        logger.error(
            "Chat LLM exhausted silent retries without text response (rounds=%s context=%s)",
            CHAT_ASSISTANT_REPLY_MAX_ROUNDS,
            log_context,
        )
        raise ChatTaskError("Не удалось получить ответ модели. Попробуйте ещё раз.")

    await add_chat_message(
        db,
        session_id=session.id,
        role="assistant",
        content=assistant_text,
    )
    session.last_activity_at = now
    return assistant_text


def mark_chat_session_solved(session: TaskChatSession) -> None:
    now = datetime.now(timezone.utc)
    session.status = "solved"
    session.solved_at = now
    session.last_activity_at = now
