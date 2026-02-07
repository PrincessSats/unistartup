from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.security.rate_limit import RateLimit, enforce_rate_limit

router = APIRouter(prefix="/feedback", tags=["Обратная связь"])


class FeedbackRequest(BaseModel):
    topic: str
    message: str


class FeedbackResponse(BaseModel):
    message: str


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: Request,
    data: FeedbackRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    enforce_rate_limit(
        request,
        scope="feedback_submit",
        subject=str(user.id),
        rule=RateLimit(max_requests=10, window_seconds=60),
    )

    topic = (data.topic or "").strip()
    message = (data.message or "").strip()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тема обязательна",
        )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сообщение обязательно",
        )

    if len(message) > 123:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сообщение слишком длинное",
        )

    await db.execute(
        text(
            """
            INSERT INTO feedback (user_id, topic, message)
            VALUES (:user_id, :topic, :message)
            """
        ),
        {"user_id": user.id, "topic": topic, "message": message},
    )
    await db.commit()

    return FeedbackResponse(message="ok")
