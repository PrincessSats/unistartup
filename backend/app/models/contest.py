from sqlalchemy import Column, BigInteger, Integer, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP, ARRAY, JSONB
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


class KBEntry(Base):
    __tablename__ = "kb_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False, default=100)
    tags = Column(ARRAY(Text), default=list)
    task_kind = Column(Text, nullable=False, default="contest")
    language = Column(Text, nullable=False, default="ru")
    story = Column(Text)
    participant_description = Column(Text)
    state = Column(Text, nullable=False, default="draft")
    kb_entry_id = Column(BigInteger, ForeignKey("kb_entries.id"))
    llm_raw_response = Column(JSONB)
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    contests = relationship("ContestTask", back_populates="task", cascade="all, delete-orphan")
    flags = relationship("TaskFlag", back_populates="task", cascade="all, delete-orphan")
    author_solution = relationship("TaskAuthorSolution", back_populates="task", uselist=False, cascade="all, delete-orphan")


class ContestTask(Base):
    __tablename__ = "contest_tasks"

    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id"), primary_key=True)
    order_index = Column(Integer, nullable=False, default=0)
    points_override = Column(Integer)
    override_title = Column(Text)
    override_participant_description = Column(Text)
    override_tags = Column(ARRAY(Text))
    override_category = Column(Text)
    override_difficulty = Column(Integer)

    contest = relationship("Contest", back_populates="tasks")
    task = relationship("Task", back_populates="contests")


class ContestParticipant(Base):
    __tablename__ = "contest_participants"

    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_active_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))


class TaskFlag(Base):
    __tablename__ = "task_flags"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    flag_id = Column(Text, nullable=False)
    format = Column(Text, nullable=False)
    expected_value = Column(Text)
    description = Column(Text)

    task = relationship("Task", back_populates="flags")


class TaskAuthorSolution(Base):
    __tablename__ = "task_author_solutions"

    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    summary = Column(Text)
    creation_solution = Column(Text)
    steps = Column(JSONB)
    difficulty_rationale = Column(Text)
    implementation_notes = Column(Text)

    task = relationship("Task", back_populates="author_solution")


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


class LlmGeneration(Base):
    __tablename__ = "llm_generations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    input_payload = Column(JSONB, nullable=False)
    output_payload = Column(JSONB)
    kb_entry_id = Column(BigInteger, ForeignKey("kb_entries.id"))
    task_id = Column(BigInteger, ForeignKey("tasks.id"))
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    code = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)
    updated_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
