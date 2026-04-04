# Import all models to register them with the Base declarative registry
# Order matters: import models that are referenced by relationships BEFORE the models that reference them

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
    # user models
    'User',
    'UserProfile',
    'UserRating',
    'AuthRefreshToken',
    'UserAuthIdentity',
    'AuthRegistrationFlow',
    'UserRegistrationData',
    # user task variant models
    'UserTaskVariantRequest',
    'UserTaskVariantVote',
    # ai generation models
    'AIGenerationBatch',
    'AIGenerationVariant',
    'AIGenerationAnalytics',
    'AIBaseImage',
    'AIXSSTemplate',
    # contest models
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
    # audit log
    'AuditLog',
    # activity log
    'ActivityLog',
    'EventType',
    'EventSource',
]
