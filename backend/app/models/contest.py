from sqlalchemy import Column, BigInteger, Integer, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class Contest(Base):
    __tablename__ = "contests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    start_at = Column(TIMESTAMP(timezone=True), nullable=False)
    end_at = Column(TIMESTAMP(timezone=True), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)
    leaderboard_visible = Column(Boolean, nullable=False, default=True)

    tasks = relationship("ContestTask", back_populates="contest", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False, default=100)
    tags = Column(ARRAY(Text), default=list)
    language = Column(Text, nullable=False, default="ru")
    story = Column(Text)
    participant_description = Column(Text)
    state = Column(Text, nullable=False, default="draft")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    contests = relationship("ContestTask", back_populates="task", cascade="all, delete-orphan")


class ContestTask(Base):
    __tablename__ = "contest_tasks"

    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), primary_key=True)
    order_index = Column(Integer, nullable=False, default=0)
    points_override = Column(Integer)

    contest = relationship("Contest", back_populates="tasks")
    task = relationship("Task", back_populates="contests")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"))
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flag_id = Column(Text, nullable=False)
    submitted_value = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    awarded_points = Column(Integer, nullable=False, default=0)
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
