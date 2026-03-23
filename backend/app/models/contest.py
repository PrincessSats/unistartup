from sqlalchemy import Column, BigInteger, Integer, Float, SmallInteger, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP, ARRAY, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
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
    source = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    cve_id = Column(Text)
    raw_en_text = Column(Text)
    ru_title = Column(Text)
    ru_summary = Column(Text)
    ru_explainer = Column(Text)
    tags = Column(ARRAY(Text), default=list)
    difficulty = Column(Text)
    # Structured metadata extracted from NVD API
    cwe_ids = Column(ARRAY(Text), default=list)
    cvss_base_score = Column(Float)
    cvss_vector = Column(Text)
    attack_vector = Column(Text)
    attack_complexity = Column(Text)
    affected_products = Column(ARRAY(Text), default=list)
    cve_metadata = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    embedding = Column(Vector(256))


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False, default=100)
    tags = Column(ARRAY(Text), default=list)
    task_kind = Column(Text, nullable=False, default="contest")
    access_type = Column(Text, nullable=False, default="just_flag")
    language = Column(Text, nullable=False, default="ru")
    story = Column(Text)
    participant_description = Column(Text)
    chat_system_prompt_template = Column(Text)
    chat_user_message_max_chars = Column(Integer, nullable=False, default=150)
    chat_model_max_output_tokens = Column(Integer, nullable=False, default=256)
    chat_session_ttl_minutes = Column(Integer, nullable=False, default=180)
    state = Column(Text, nullable=False, default="draft")
    embedding = Column(Vector(256))
    kb_entry_id = Column(BigInteger, ForeignKey("kb_entries.id"))
    llm_raw_response = Column(JSONB)
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    contests = relationship("ContestTask", back_populates="task", cascade="all, delete-orphan")
    flags = relationship("TaskFlag", back_populates="task", cascade="all, delete-orphan")
    materials = relationship("TaskMaterial", back_populates="task", cascade="all, delete-orphan")
    author_solution = relationship("TaskAuthorSolution", back_populates="task", uselist=False, cascade="all, delete-orphan")
    chat_sessions = relationship("TaskChatSession", back_populates="task", cascade="all, delete-orphan")


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


class TaskChatSession(Base):
    __tablename__ = "task_chat_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"))
    status = Column(Text, nullable=False, default="active")
    flag_seed = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_activity_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    solved_at = Column(TIMESTAMP(timezone=True))

    task = relationship("Task", back_populates="chat_sessions")
    messages = relationship("TaskChatMessage", back_populates="session", cascade="all, delete-orphan")


class TaskChatMessage(Base):
    __tablename__ = "task_chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("task_chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    session = relationship("TaskChatSession", back_populates="messages")


class TaskFlag(Base):
    __tablename__ = "task_flags"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    flag_id = Column(Text, nullable=False)
    format = Column(Text, nullable=False)
    expected_value = Column(Text)
    description = Column(Text)

    task = relationship("Task", back_populates="flags")


class TaskMaterial(Base):
    __tablename__ = "task_materials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    url = Column(Text)
    storage_key = Column(Text)
    meta = Column(JSONB)

    task = relationship("Task", back_populates="materials")


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


class PracticeTaskStart(Base):
    __tablename__ = "practice_task_starts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_practice_task_starts_user_task"),)


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


class ContestTaskRating(Base):
    __tablename__ = "contest_task_ratings"
    __table_args__ = (UniqueConstraint("contest_id", "task_id", "user_id", name="uq_contest_task_rating"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(SmallInteger, nullable=False)
    rated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    code = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)
    updated_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
