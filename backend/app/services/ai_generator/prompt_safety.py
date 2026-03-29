"""
Prompt injection detection for user task variant requests.

Detects and filters malicious attempts to manipulate the LLM generation pipeline.
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
    Detects prompt injection attempts in user requests.
    
    Checks for:
    - Instruction override attempts ("ignore previous instructions")
    - Jailbreak patterns ("developer mode", "bypass rules")
    - Flag format injection (CTF{...})
    - SQL injection patterns
    - Code execution attempts
    - System prompt extraction
    """
    
    # English injection patterns
    INJECTION_PATTERNS_EN = [
        r"ignore\s+(previous|all|the)\s+(instructions|rules|constraints|guidelines)",
        r"disregard\s+(previous|all|the)\s+(instructions|rules)",
        r"bypass\s+(security|rules|filters|restrictions|safety)",
        r"you\s+are\s+now\s+(free|unrestricted|liberated|in\s+developer\s+mode)",
        r"forget\s+(all|your)\s+(rules|instructions|constraints|programming)",
        r"system\s+prompt|system\s+message|initial\s+instructions",
        r"developer\s+mode|debug\s+mode|debugging\s+mode",
        r"sudo\s+make\s+me\s+a\s+sandwich",  # Classic xkcd reference
        r"activate\s+god\s+mode",
        r"enable\s+unsafe\s+mode",
        r"turn\s+off\s+content\s+filters",
        r"pretend\s+you\s+are\s+(unrestricted|a\s+different\s+AI)",
        r"roleplay\s+as\s+(an?\s+unrestricted|a\s+hacked)\s+AI",
    ]
    
    # Russian injection patterns
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
    
    # Flag format patterns (should not appear in user requests)
    FLAG_PATTERNS = [
        r"CTF\{[^}]+\}",  # Standard flag format
        r"flag\s*[=:]\s*[A-Za-z0-9_]+",
        r"флаг\s*[=:]\s*[A-Za-z0-9_]+",
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"'\s*OR\s+'1'\s*=\s*'1",
        r";\s*DROP\s+TABLE",
        r"'\s*;\s*--",
        r"UNION\s+SELECT",
        r"OR\s+1\s*=\s*1",
    ]
    
    # Code execution patterns
    CODE_EXEC_PATTERNS = [
        r"```[a-z]*\n.*```",  # Markdown code blocks
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"os\.system\s*\(",
        r"subprocess\.",
    ]
    
    def __init__(self):
        # Compile patterns for efficiency
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
        Check user request for injection attempts.
        
        Args:
            user_request: Raw user input
            
        Returns:
            SafetyCheckResult with is_safe flag, optional rejection reason,
            and sanitized request
        """
        if not user_request or not user_request.strip():
            return SafetyCheckResult(
                is_safe=False,
                rejection_reason="Пустой запрос",
                sanitized_request="",
            )
        
        # Check for injection patterns (English)
        for regex in self.injection_regex_en:
            if regex.search(user_request):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка обхода инструкций (EN)",
                    sanitized_request="",
                )
        
        # Check for injection patterns (Russian)
        for regex in self.injection_regex_ru:
            if regex.search(user_request):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка обхода инструкций (RU)",
                    sanitized_request="",
                )
        
        # Check for flag format injection
        for regex in self.flag_regex:
            if regex.search(user_request):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Формат флага в запросе запрещён",
                    sanitized_request="",
                )
        
        # Check for SQL injection
        for regex in self.sql_regex:
            if regex.search(user_request):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружен SQL injection паттерн",
                    sanitized_request="",
                )
        
        # Check for code execution attempts
        for regex in self.code_exec_regex:
            if regex.search(user_request):
                return SafetyCheckResult(
                    is_safe=False,
                    rejection_reason="Обнаружена попытка выполнения кода",
                    sanitized_request="",
                )
        
        # Sanitize: remove potentially dangerous characters but preserve meaning
        sanitized = self._sanitize_request(user_request)
        
        # Length check (reasonable limit)
        if len(sanitized) > 200:
            return SafetyCheckResult(
                is_safe=False,
                rejection_reason="Запрос слишком длинный (максимум 200 символов)",
                sanitized_request="",
            )
        
        return SafetyCheckResult(
            is_safe=True,
            rejection_reason=None,
            sanitized_request=sanitized,
        )
    
    def _sanitize_request(self, request: str) -> str:
        """
        Sanitize user request while preserving intent.
        
        - Remove extra whitespace
        - Normalize quotes
        - Remove zero-width characters
        - Trim to reasonable length
        """
        # Remove zero-width characters
        sanitized = re.sub(r"[\u200b-\u200f\u2028-\u202f]", "", request)
        
        # Normalize quotes
        sanitized = sanitized.replace('"', "'").replace('"', "'")
        
        # Remove control characters (except newlines and tabs)
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
        
        # Normalize whitespace
        sanitized = " ".join(sanitized.split())
        
        # Trim to 200 characters (hard limit)
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rsplit(" ", 1)[0]
        
        return sanitized.strip()


# Singleton instance
_safety_checker: Optional[PromptSafetyChecker] = None


def get_safety_checker() -> PromptSafetyChecker:
    """Get or create the singleton safety checker instance."""
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = PromptSafetyChecker()
    return _safety_checker


async def check_prompt_safety(user_request: str) -> SafetyCheckResult:
    """Convenience function to check prompt safety."""
    return await get_safety_checker().check_user_request(user_request)
