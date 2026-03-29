"""
User Task Variants API routes.

Endpoints:
  POST /user-variants/tasks/{task_id}/generate  — start variant generation
  GET  /user-variants/requests/{request_id}/status — poll generation status
  GET  /user-variants/tasks/{task_id}/variants — list variants for a task
  POST /user-variants/variants/{variant_id}/vote — vote on a variant
"""
import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user_task_variant import UserTaskVariantRequest, UserTaskVariantVote
from app.models.ai_generation import AIGenerationVariant
from app.services.ai_generator.prompt_safety import check_prompt_safety
from app.services.ai_generator.user_pipeline import run_user_variant_pipeline
from app.security.rate_limit import RateLimit, enforce_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user-variants", tags=["User Task Variants"])


# ── Rate Limits ──────────────────────────────────────────────────────────────
# (Defined inline in the route)


# ── Schemas ──────────────────────────────────────────────────────────────────

class UserVariantRequestSchema(BaseModel):
    """Request to generate a task variant."""
    user_request: str = Field(..., min_length=1, max_length=500, description="User's wishes for the variant")


class UserVariantRequestResponse(BaseModel):
    """Response after starting variant generation."""
    request_id: str
    status: str  # pending, generating
    message: str


class VariantStatusResponse(BaseModel):
    """Status of a variant generation request."""
    request_id: str
    status: str  # pending, generating, completed, failed
    progress_message: Optional[str] = None
    generated_variant_id: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None


class VariantVoteSchema(BaseModel):
    """Vote on a variant."""
    vote_type: str = Field(..., description="upvote or downvote")
    
    @classmethod
    def validate_vote_type(cls, v):
        if v not in ("upvote", "downvote"):
            raise ValueError("vote_type must be 'upvote' or 'downvote'")
        return v


class VariantInfoSchema(BaseModel):
    """Public information about a generated variant."""
    variant_id: str
    spec_title: Optional[str]
    spec_description: Optional[str]
    upvotes: int = 0
    downvotes: int = 0
    net_rating: int = 0
    user_vote: Optional[str] = None  # current user's vote (if any)
    created_at: Optional[str] = None
    published_task_id: Optional[int] = None  # ID of the auto-published task
    # Parent task info (for display in UGC task page)
    parent_task_id: Optional[int] = None
    parent_task_title: Optional[str] = None
    parent_task_category: Optional[str] = None
    parent_task_difficulty: Optional[str] = None


class ListVariantsResponse(BaseModel):
    """List of variants for a task."""
    task_id: int
    variants: List[VariantInfoSchema] = []


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_vote_counts(db: AsyncSession, variant_id: uuid.UUID) -> tuple[int, int]:
    """Get upvote and downvote counts for a variant."""
    result = await db.execute(
        select(
            func.sum(case((UserTaskVariantVote.vote_type == "upvote", 1), else_=0)),
            func.sum(case((UserTaskVariantVote.vote_type == "downvote", 1), else_=0)),
        )
        .where(UserTaskVariantVote.variant_id == variant_id)
    )
    row = result.first()
    return row[0] or 0, row[1] or 0


async def _get_user_vote(db: AsyncSession, variant_id: uuid.UUID, user_id: int) -> Optional[str]:
    """Get current user's vote for a variant."""
    result = await db.execute(
        select(UserTaskVariantVote.vote_type)
        .where(
            and_(
                UserTaskVariantVote.variant_id == variant_id,
                UserTaskVariantVote.user_id == user_id,
            )
        )
    )
    row = result.scalar_one_or_none()
    return row


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/tasks/{task_id}/generate", response_model=UserVariantRequestResponse)
async def create_variant_request(
    request: Request,
    task_id: int,
    request_data: UserVariantRequestSchema,
    background_tasks: BackgroundTasks,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start variant generation for a task.
    
    - Validates parent task (crypto/forensics/web only)
    - Checks prompt injection
    - Creates request record
    - Launches background pipeline
    - Returns request_id for polling
    """
    from app.models.contest import Task
    
    user, _profile = current_user_data
    
    # Rate limiting
    enforce_rate_limit(
        request,
        scope="user_variant_generation",
        subject=str(user.id),
        rule=RateLimit(max_requests=5, window_seconds=60 * 60),  # 5 per hour
    )
    
    # Load task
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    # Resolve effective parent ID for generation
    effective_parent_id = task.parent_id if task.parent_id else task.id
    
    # Reload parent task if we're on a daughter
    if task.parent_id:
        parent_result = await db.execute(select(Task).where(Task.id == effective_parent_id))
        parent_task = parent_result.scalar_one_or_none()
    else:
        parent_task = task
    
    if not parent_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent task not found",
        )
    
    # Check category (crypto/forensics/web only, NOT chat)
    ALLOWED_CATEGORIES = {"Crypto", "Forensics", "Web"}
    if parent_task.category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task category '{parent_task.category}' not supported for user variants. Allowed: {', '.join(ALLOWED_CATEGORIES)}",
        )
    
    # Check prompt safety
    safety_result = await check_prompt_safety(request_data.user_request)
    if not safety_result.is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request rejected: {safety_result.rejection_reason}",
        )
    
    # Create request record
    request_id = uuid.uuid4()
    variant_request = UserTaskVariantRequest(
        id=request_id,
        parent_task_id=effective_parent_id,
        user_id=user.id,
        user_request=request_data.user_request,
        sanitized_request=safety_result.sanitized_request,
        status="pending",
    )
    db.add(variant_request)
    await db.commit()
    
    # Launch background pipeline
    background_tasks.add_task(
        run_user_variant_pipeline,
        parent_task_id=effective_parent_id,
        user_request=request_data.user_request,
        sanitized_request=safety_result.sanitized_request,
        user_id=user.id,
        request_id=request_id,
    )
    
    return UserVariantRequestResponse(
        request_id=str(request_id),
        status="pending",
        message="Генерация варианта запущена",
    )


@router.get("/requests/{request_id}/status", response_model=VariantStatusResponse)
async def get_variant_status(
    request_id: uuid.UUID,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Poll generation status.
    
    Returns:
    - pending: waiting to start
    - generating: pipeline running (show tic-tac-toe)
    - completed: variant ready
    - failed: error occurred
    """
    user, _profile = current_user_data
    result = await db.execute(
        select(UserTaskVariantRequest).where(UserTaskVariantRequest.id == request_id)
    )
    variant_request = result.scalar_one_or_none()
    
    if not variant_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )
    
    # Check ownership
    if variant_request.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this request",
        )
    
    # Build progress message
    progress_message = None
    if variant_request.status == "pending":
        progress_message = "Ожидание начала генерации..."
    elif variant_request.status == "generating":
        progress_message = "Генерация варианта... (играйте в крестики-нолики)"
    elif variant_request.status == "completed":
        progress_message = "Вариант успешно создан!"
    elif variant_request.status == "failed":
        progress_message = f"Ошибка: {variant_request.failure_reason or variant_request.rejection_reason or 'Неизвестная ошибка'}"
    
    return VariantStatusResponse(
        request_id=str(variant_request.id),
        status=variant_request.status,
        progress_message=progress_message,
        generated_variant_id=str(variant_request.generated_variant_id) if variant_request.generated_variant_id else None,
        failure_reason=variant_request.failure_reason,
        rejection_reason=variant_request.rejection_reason,
    )


@router.get("/tasks/{task_id}/variants", response_model=ListVariantsResponse)
async def list_task_variants(
    task_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all user-generated variants for a task.

    Returns variants sorted by net rating (upvotes - downvotes).
    Includes current user's vote for each variant.
    """
    user, _profile = current_user_data
    from app.models.contest import Task

    # Verify task exists and find effective parent
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Resolve parent ID if this is a daughter task
    effective_parent_id = task.parent_id if task.parent_id else task.id

    # Find completed requests for the effective parent
    requests_result = await db.execute(
        select(UserTaskVariantRequest)
        .where(
            and_(
                UserTaskVariantRequest.parent_task_id == effective_parent_id,
                UserTaskVariantRequest.status == "completed",
                UserTaskVariantRequest.generated_variant_id.isnot(None),
            )
        )
        .order_by(UserTaskVariantRequest.created_at.desc())
    )
    requests = requests_result.scalars().all()

    variants = []
    for request in requests:
        # Load variant
        variant_result = await db.execute(
            select(AIGenerationVariant).where(AIGenerationVariant.id == request.generated_variant_id)
        )
        variant = variant_result.scalar_one_or_none()
        if not variant or not variant.generated_spec:
            continue

        spec = variant.generated_spec
        spec_title = spec.get("title") if spec else None
        spec_description = spec.get("description") if spec else None

        # Get vote counts
        upvotes, downvotes = await _get_vote_counts(db, variant.id)

        # Get user's vote
        user_vote = await _get_user_vote(db, variant.id, user.id)

        # Get parent task info (explicit async query to avoid lazy-loading)
        parent_task_title = None
        parent_task_category = None
        parent_task_difficulty = None
        
        if request.parent_task_id:
            parent_task_result = await db.execute(
                select(Task).where(Task.id == request.parent_task_id)
            )
            parent_task = parent_task_result.scalar_one_or_none()
            if parent_task:
                parent_task_title = parent_task.title
                parent_task_category = parent_task.category
                from app.routes.education import difficulty_label
                parent_task_difficulty = difficulty_label(parent_task.difficulty)

        variants.append(VariantInfoSchema(
            variant_id=str(variant.id),
            spec_title=spec_title,
            spec_description=spec_description,
            upvotes=upvotes,
            downvotes=downvotes,
            net_rating=upvotes - downvotes,
            user_vote=user_vote,
            created_at=variant.created_at.isoformat() if variant.created_at else None,
            published_task_id=variant.published_task_id,
            # Parent task info
            parent_task_id=request.parent_task_id,
            parent_task_title=parent_task_title,
            parent_task_category=parent_task_category,
            parent_task_difficulty=parent_task_difficulty,
        ))

    # Sort by net rating descending
    variants.sort(key=lambda v: v.net_rating, reverse=True)

    return ListVariantsResponse(
        task_id=task_id,
        variants=variants,
    )


@router.post("/variants/{variant_id}/vote")
async def vote_variant(
    variant_id: uuid.UUID,
    vote: VariantVoteSchema,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upvote or downvote a variant.
    
    One vote per user per variant. Changing vote type updates existing vote.
    """
    user, _profile = current_user_data
    # Verify variant exists
    variant_result = await db.execute(
        select(AIGenerationVariant).where(AIGenerationVariant.id == variant_id)
    )
    if not variant_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found",
        )
    
    # Check if user already voted
    existing_vote = await db.execute(
        select(UserTaskVariantVote)
        .where(
            and_(
                UserTaskVariantVote.variant_id == variant_id,
                UserTaskVariantVote.user_id == user.id,
            )
        )
    )
    existing = existing_vote.scalar_one_or_none()
    
    try:
        if existing:
            if existing.vote_type == vote.vote_type:
                # Same vote - remove it (toggle off)
                await db.delete(existing)
            else:
                # Different vote - update
                existing.vote_type = vote.vote_type
        else:
            # New vote
            new_vote = UserTaskVariantVote(
                variant_id=variant_id,
                user_id=user.id,
                vote_type=vote.vote_type,
            )
            db.add(new_vote)
        
        await db.commit()
    except Exception as exc:
        # Handle race condition - vote was already modified/deleted
        logger.warning("Vote race condition for user=%d variant=%s: %s", user.id, variant_id, exc)
        await db.rollback()
        # Return success anyway - frontend will refresh
    
    return {"status": "ok", "message": "Vote recorded"}
