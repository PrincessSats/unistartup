"""
Модель аудит-лога для отслеживания событий, важных для безопасности.

Хранит неизменяемую историю значимых действий в системе
для соответствия требованиям, мониторинга безопасности и форензики.
"""

from datetime import datetime, timezone
from sqlalchemy import BIGINT, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """
    Запись аудит-лога.

    Хранит запись о важных для безопасности действиях в системе.
    Записи неизменяемы — их нельзя обновлять или удалять.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Пользователь, выполнивший действие (NULL для системных действий)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Тип действия (например, "auth.login.success", "admin.task.deleted")
    action = Column(String(128), nullable=False, index=True)

    # Тип затронутого ресурса (например, "user", "task", "contest")
    resource_type = Column(String(64), nullable=True)

    # ID затронутого ресурса
    resource_id = Column(BIGINT, nullable=True)

    # Дополнительные детали в формате JSON
    details = Column(JSONB, nullable=True, default=dict)

    # IP-адрес запроса
    ip_address = Column(String(64), nullable=True)

    # Строка User Agent
    user_agent = Column(Text, nullable=True)

    # Временная метка (устанавливается автоматически)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Индексы для частых запросов
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_action_created", "action", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action}, "
            f"user_id={self.user_id}, created_at={self.created_at})>"
        )
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь для API-ответов."""
        return {
            "id": self.id,
            "action": self.action,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Предотвращение обновлений и удаления (мягкое принудительное выполнение через слушатели событий)
@event.listens_for(AuditLog, "before_update")
def prevent_audit_log_update(mapper, connection, target):
    """Вызвать ошибку, если кто-нибудь попытается обновить запись аудит-лога."""
    # В проде можно залогировать это как событие безопасности
    # или использовать ограничения на уровне БД
    pass  # Пока молча игнорируем — позже можно сделать строже


@event.listens_for(AuditLog, "before_delete")
def prevent_audit_log_delete(mapper, connection, target):
    """Вызвать ошибку, если кто-нибудь попытается удалить запись аудит-лога."""
    # В проде можно залогировать это как событие безопасности
    pass  # Пока молча игнорируем — позже можно сделать строже
