"""
Утилиты для очистки пользовательского ввода — защита от XSS и инъекций.

Содержит функции санитизации данных перед сохранением или отображением.
Использует библиотеку bleach для очистки HTML.
"""

import re
import html
from typing import Optional

try:
    import bleach
except ImportError:
    # Запасной вариант, если bleach не установлен
    bleach = None


# Разрешённые HTML теги для форматированного текста (если понадобится в будущем)
ALLOWED_TAGS = []  # По умолчанию теги HTML не разрешены

# Разрешённые атрибуты для разрешённых тегов
ALLOWED_ATTRIBUTES = {}

# Распространённые паттерны XSS для обнаружения и блокировки
XSS_PATTERNS = [
    re.compile(r'<\s*script', re.IGNORECASE),
    re.compile(r'javascript\s*:', re.IGNORECASE),
    re.compile(r'vbscript\s*:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick=, onerror=, etc.
    re.compile(r'<\s*iframe', re.IGNORECASE),
    re.compile(r'<\s*object', re.IGNORECASE),
    re.compile(r'<\s*embed', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),
    re.compile(r'url\s*\(\s*["\']?\s*javascript:', re.IGNORECASE),
]


def sanitize_html(text: str, allowed_tags: Optional[list] = None) -> str:
    """
    Очищает HTML-ввод: убирает опасные теги и атрибуты.

    Args:
        text: Текст, который может содержать HTML
        allowed_tags: Список разрешённых тегов (по умолчанию: пусто)

    Returns:
        Очищенный текст, безопасный для отображения в HTML
    """
    if not text:
        return ""
    
    if bleach is not None:
        return bleach.clean(
            text,
            tags=allowed_tags or ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES or {},
            strip=True
        )
    else:
        # Резервный вариант: удалить все HTML теги и экранировать
        return strip_html_tags(text)


def strip_html_tags(text: str) -> str:
    """
    Удаляет все HTML-теги из текста.

    Args:
        text: Текст с возможными HTML-тегами

    Returns:
        Чистый текст без HTML-тегов
    """
    if not text:
        return ""
    
    # Удалить HTML теги с помощью регулярного выражения
    clean = re.sub(r'<[^>]+>', '', text)
    return clean


def escape_html(text: str) -> str:
    """
    Экранирует спецсимволы HTML для защиты от XSS.

    Args:
        text: Текст для экранирования

    Returns:
        Экранированный HTML-безопасный текст
    """
    if not text:
        return ""
    
    return html.escape(text, quote=True)


def detect_xss_attempt(text: str) -> bool:
    """
    Ищет признаки XSS-атаки во входных данных.

    Args:
        text: Текст для проверки

    Returns:
        True если найден XSS-паттерн, иначе False
    """
    if not text:
        return False
    
    for pattern in XSS_PATTERNS:
        if pattern.search(text):
            return True
    
    return False


def sanitize_username(username: str) -> str:
    """
    Очищает имя пользователя.

    Разрешено: буквы, цифры, подчёркивание, дефис.
    Максимум: 50 символов.

    Args:
        username: Сырое имя пользователя

    Returns:
        Очищенное имя пользователя
    """
    if not username:
        return ""
    
    # Удалить любой символ, который не является буквой, цифрой, подчёркиванием или дефисом
    clean = re.sub(r'[^\w\-]', '', username)

    # Ограничить длину
    return clean[:50]


def sanitize_email(email: str) -> str:
    """
    Очищает email.

    Args:
        email: Сырой email

    Returns:
        Очищенный email (в нижнем регистре, без пробелов)
    """
    if not email:
        return ""
    
    # Преобразовать в нижний регистр и обрезать
    return email.lower().strip()[:254]


def sanitize_comment(body: str, max_length: int = 2000) -> str:
    """
    Очищает текст комментария.

    - Удаляет весь HTML
    - Экранирует спецсимволы
    - Обрезает по лимиту длины

    Args:
        body: Текст комментария
        max_length: Максимальная длина

    Returns:
        Очищенный текст комментария
    """
    if not body:
        return ""
    
    # Удалить HTML теги
    clean = strip_html_tags(body)

    # Экранировать HTML сущности
    clean = escape_html(clean)

    # Применить ограничение длины
    return clean[:max_length]


def sanitize_feedback_message(message: str, max_length: int = 500) -> str:
    """
    Очищает сообщение обратной связи.

    Args:
        message: Текст фидбека
        max_length: Максимальная длина

    Returns:
        Очищенное сообщение
    """
    if not message:
        return ""
    
    # Удалить и экранировать
    clean = strip_html_tags(message)
    clean = escape_html(clean)

    return clean[:max_length]


def sanitize_topic(topic: str, max_length: int = 100) -> str:
    """
    Очищает тему/заголовок.

    Args:
        topic: Текст темы
        max_length: Максимальная длина

    Returns:
        Очищенная тема
    """
    if not topic:
        return ""
    
    # Удалить HTML теги и экранировать
    clean = strip_html_tags(topic)
    clean = escape_html(clean)

    return clean[:max_length]


def validate_sql_sort_order(order: str, allowed_values: tuple = ("asc", "desc")) -> str:
    """
    Проверяет параметр ORDER BY для защиты от SQL-инъекций.

    Args:
        order: Порядок сортировки от пользователя
        allowed_values: Допустимые значения

    Returns:
        Проверенный порядок сортировки или значение по умолчанию

    Raises:
        ValueError: Если значение не входит в допустимые
    """
    if not order:
        return allowed_values[0]
    
    order_lower = order.lower().strip()
    
    if order_lower not in allowed_values:
        raise ValueError(f"Invalid sort order: {order}. Must be one of {allowed_values}")
    
    return order_lower
