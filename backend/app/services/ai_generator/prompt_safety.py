"""
Обнаружение инъекции промпта в запросах вариантов задач пользователя.

Обнаруживает и фильтрует вредоносные попытки манипулировать конвейером генерации LLM.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SafetyCheckResult:
    """Result of prompt safety check."""
    is_safe: bool
    rejection_reason: Optional[str] = None
    sanitized_request: str = ""


class PromptSafetyChecker:
    """
    Обнаруживает попытки инъекции промпта в запросах пользователей.

    Проверяет:
    - Попытки переопределения инструкций ("ignore previous instructions")
    - Паттерны jailbreak ("developer mode", "bypass rules")
    - Инъекция формата флага (CTF{...})
    - Паттерны SQL injection
    - Попытки выполнения кода
    - Извлечение системного промпта
    """

    # Английские паттерны инъекции
    INJECTION_PATTERNS_EN = [
        r"ignore\s+(\w+\s+){0,3}(instructions|rules|constraints|guidelines)",
        r"disregard\s+(\w+\s+){0,2}(instructions|rules|guidelines|constraints)",
        r"bypass\s+(\w+\s+)?(security|rules|filters|restrictions|safety)",
        r"you\s+are\s+now\s+(free|unrestricted|liberated|in\s+developer\s+mode)",
        r"forget\s+(\w+\s+){0,2}(rules|instructions|constraints|programming)",
        r"system\s+prompt|system\s+message|initial\s+instructions",
        r"developer\s+mode|debug\s+mode|debugging\s+mode",
        r"sudo\s+make\s+me\s+a\s+sandwich",  # Classic xkcd reference
        r"activate\s+god\s+mode",
        r"enable\s+unsafe\s+mode",
        r"turn\s+off\s+content\s+filters",
        r"pretend\s+you\s+are\s+(unrestricted|a\s+different\s+AI)",
        r"roleplay\s+as\s+(an?\s+unrestricted|a\s+hacked)\s+AI",
    ]

    # Русские паттерны инъекции
    INJECTION_PATTERNS_RU = [
        r"игнорируй\s+(предыдущие|все)\s+(инструкции|правила|ограничения)",
        r"забудь\s+(все|свои)\s+(правила|инструкции|ограничения|программу)",
        r"пожалуйста\s+игнорируй",
        r"преодолей\s+(защиту|фильтры|ограничения|безопасность)",
        r"ты\s+теперь\s+(свободен|без\s+ограничений|в\s+режиме\s+разработчика)",
        r"системный\s+промпт|системное\s+сообщение|начальные\s+инструкции",
        r"режим\s+разработчика|режим\s+отладки",
        r"активируй\s+режим\s+бога",
        r"отключи\s+фильтры\s+контента",
        r"притворись\s+(что\s+ты\s+без\s+ограничений|другим\s+ИИ)",
    ]

    # Паттерны формата флага (не должны появляться в запросах пользователя)
    FLAG_PATTERNS = [
        r"CTF\{[^}]+\}",  # Standard flag format
        r"flag\s*[=:]\s*[A-Za-z0-9_]+",
        r"флаг\s*[=:]\s*\S+",
    ]

    # Паттерны SQL injection
    SQL_INJECTION_PATTERNS = [
        r"'\s*OR\s+'1'\s*=\s*'1",
        r";\s*DROP\s+TABLE",
        r"'\s*;\s*--",
        r"UNION\s+SELECT",
        r"OR\s+1\s*=\s*1",
    ]

    # Паттерны выполнения кода
    CODE_EXEC_PATTERNS = [
        r"```[a-z]*\n.*```",  # Markdown code blocks
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"os\.system\s*\(",
        r"subprocess\.",
    ]
    
    def __init__(self):
        # Компилировать паттерны для эффективности
        self.injection_regex_en = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS_EN
        ]
        self.injection_regex_ru = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS_RU
        ]
        self.flag_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.FLAG_PATTERNS
        ]
        self.sql_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SQL_INJECTION_PATTERNS
        ]
        self.code_exec_regex = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.CODE_EXEC_PATTERNS
        ]
    
    async def check_user_request(self, user_request: str) -> SafetyCheckResult:
        """
        Проверить запрос пользователя на попытки инъекции.

        Args:
            user_request: Сырые данные пользователя

        Returns:
            SafetyCheckResult с флагом is_safe, дополнительным причина отклонения,
            и очищенный запрос
        """
        if not user_request or not user_request.strip():
            return SafetyCheckResult(
                is_safe=False,
                rejection_reason="Пустой запрос",
                sanitized_request="",
            )

        # Проверить длину на RAW входе (до санитизации)
        if len(user_request) > 200:
            return SafetyCheckResult(
                is_safe=False,
                rejection_reason="Запрос слишком длинный (максимум 200 символов)",
                sanitized_request="",
            )

        # Санитизировать ПЕРВЫМ (удалить zero-width chars перед проверкой паттернов)
        sanitized = self._sanitize_request(user_request)

        # Проверить паттерны инъекции (английский) на санитизированном
        for regex in self.injection_regex_en:
            if regex.search(sanitized):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка обхода инструкций (EN)",
                    sanitized_request="",
                )

        # Проверить паттерны инъекции (русский) на санитизированном
        for regex in self.injection_regex_ru:
            if regex.search(sanitized):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка обхода инструкций (RU)",
                    sanitized_request="",
                )

        # Проверить инъекцию формата флага на санитизированном
        for regex in self.flag_regex:
            if regex.search(sanitized):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Формат флага в запросе запрещён",
                    sanitized_request="",
                )

        # Проверить SQL injection на санитизированном
        for regex in self.sql_regex:
            if regex.search(sanitized):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружен SQL injection паттерн",
                    sanitized_request="",
                )

        # Проверить попытки выполнения кода на санитизированном
        for regex in self.code_exec_regex:
            if regex.search(sanitized):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка выполнения кода",
                    sanitized_request="",
                )

        return SafetyCheckResult(
            is_safe=True,
            rejection_reason=None,
            sanitized_request=sanitized,
        )
    
    def _sanitize_request(self, request: str) -> str:
        """
        \u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f, \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u044f \u043d\u0430\u043c\u0435\u0440\u0435\u043d\u0438\u0435.

        - \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043b\u0438\u0448\u043d\u0438\u0439 \u043f\u0440\u043e\u0431\u0435\u043b
        - \u041d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u043e\u0432\u0430\u0442\u044c \u043a\u0430\u0432\u044b\u0447\u043a\u0438
        - \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0438\u043c\u0432\u043e\u043b\u044b \u043d\u0443\u043b\u0435\u0432\u043e\u0439 \u0448\u0438\u0440\u0438\u043d\u044b
        - \u041e\u0431\u0440\u0435\u0437\u0430\u0442\u044c \u0434\u043e \u043f\u0440\u0438\u0435\u043c\u043b\u0435\u043c\u043e\u0439 \u0434\u043b\u0438\u043d\u044b
        """
        # \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0438\u043c\u0432\u043e\u043b\u044b \u043d\u0443\u043b\u0435\u0432\u043e\u0439 \u0448\u0438\u0440\u0438\u043d\u044b
        sanitized = re.sub(r"[\u200b-\u200f\u2028-\u202f]", "", request)

        # \u041d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u043e\u0432\u0430\u0442\u044c \u043a\u0430\u0432\u044b\u0447\u043a\u0438
        sanitized = sanitized.replace('"', "'").replace('"', "'")

        # \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0438\u043c\u0432\u043e\u043b\u044b \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f (\u043a\u0440\u043e\u043c\u0435 \u043d\u043e\u0432\u044b\u0445 \u0441\u0442\u0440\u043e\u043a \u0438 \u0442\u0430\u0431\u0443\u043b\u044f\u0446\u0438\u0438)
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)

        # \u041d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u043e\u0432\u0430\u0442\u044c \u043f\u0440\u043e\u0431\u0435\u043b\u044b
        sanitized = " ".join(sanitized.split())

        # \u041e\u0431\u0440\u0435\u0437\u0430\u0442\u044c \u0434\u043e 200 \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432 (\u0436\u0451\u0441\u0442\u043a\u0438\u0439 \u043f\u0440\u0435\u0434\u0435\u043b)
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rsplit(" ", 1)[0]

        return sanitized.strip()


# Экземпляр-синглтон
_safety_checker: Optional[PromptSafetyChecker] = None


def get_safety_checker() -> PromptSafetyChecker:
    """Получить или создать экземпляр-синглтон проверки безопасности."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = PromptSafetyChecker()
    return _safety_checker


async def check_prompt_safety(user_request: str) -> SafetyCheckResult:
    """Удобная функция для проверки безопасности промпта."""
    return await get_safety_checker().check_user_request(user_request)
