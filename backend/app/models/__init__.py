# Импортируем все модели для регистрации в реестре декларативного Base
# Порядок важен: импортируйте модели, на которые ссылаются отношения, ДО моделей, которые их ссылаются

from app.models.user import User, UserProfile, UserRating, AuthRefreshToken, UserAuthIdentity, AuthRegistrationFlow, UserRegistrationData
from app.models.user_task_variant import UserTaskVariantRequest, UserTaskVariantVote
from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant, AIGenerationAnalytics, AIBaseImage, AIXSSTemplate
from app.models.contest import (
    Contest,
    ContestTask,
    ContestParticipant,
    KBEntry,
    Task,
    TaskChatSession,
    TaskChatMessage,
    TaskFlag,
    TaskMaterial,
    TaskAuthorSolution,
    Submission,
    PracticeTaskStart,
    LlmGeneration,
    ContestTaskRating,
    PromptTemplate,
)
from app.models.audit_log import AuditLog
from app.models.activity import ActivityLog, EventType, EventSource

__all__ = [
    # модели пользователя
    'User',
    'UserProfile',
    'UserRating',
    'AuthRefreshToken',
    'UserAuthIdentity',
    'AuthRegistrationFlow',
    'UserRegistrationData',
    # модели варианта задачи пользователя
    'UserTaskVariantRequest',
    'UserTaskVariantVote',
    # модели генерации ИИ
    'AIGenerationBatch',
    'AIGenerationVariant',
    'AIGenerationAnalytics',
    'AIBaseImage',
    'AIXSSTemplate',
    # модели конкурса
    'Contest',
    'ContestTask',
    'ContestParticipant',
    'KBEntry',
    'Task',
    'TaskChatSession',
    'TaskChatMessage',
    'TaskFlag',
    'TaskMaterial',
    'TaskAuthorSolution',
    'Submission',
    'PracticeTaskStart',
    'LlmGeneration',
    'ContestTaskRating',
    'PromptTemplate',
    # журнал аудита
    'AuditLog',
    # журнал активности
    'ActivityLog',
    'EventType',
    'EventSource',
]
