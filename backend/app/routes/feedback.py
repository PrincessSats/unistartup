from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db

router = APIRouter(prefix="/feedback", tags=["Обратная связь"])


class FeedbackRequest(BaseModel):
    topic: str
    message: str


class FeedbackResponse(BaseModel):
    message: str


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    data: FeedbackRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data

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
