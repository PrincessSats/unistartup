"""
Middleware безопасных заголовков для HTTP-ответов.

Добавляет нужные заголовки безопасности ко всем ответам:
- Content-Security-Policy (CSP)
- X-Content-Type-Options
- X-Frame-Options
- Strict-Transport-Security (HSTS)
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
"""

from fastapi import Request
from app.config import settings


# Политика безопасности содержимого по умолчанию
# Ограничивает загрузку ресурсов для предотвращения XSS и инъекции данных
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self' https://api.hacknet.tech https://storage.yandexcloud.net; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


async def security_headers_middleware(request: Request, call_next):
    """
    Добавляет заголовки безопасности ко всем HTTP-ответам.

    Запускается на каждый запрос, добавляет заголовки
    до отправки ответа клиенту.
    """
    response = await call_next(request)

    # Предотвращение сниффинга типов MIME
    # Заставляет браузер соблюдать объявленный Content-Type
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Предотвращение атак кликджекинга
    # Не позволяет странице отображаться в любом фрейме
    response.headers["X-Frame-Options"] = "DENY"

    # Включить фильтр XSS в старых браузерах
    # Современные браузеры используют Content-Security-Policy
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Контролировать информацию о реферере, отправляемую с запросами
    # Отправляет полный реферер для того же происхождения, только происхождение для кросс-происхождения
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Ограничить функции браузера/API
    # Отключает геолокацию, микрофон, камеру и т. д.
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    # Политика безопасности содержимого - предотвращает XSS и инъекцию данных
    csp_policy = getattr(settings, 'CSP_POLICY', DEFAULT_CSP)
    response.headers["Content-Security-Policy"] = csp_policy

    # Добавить URI отчёта CSP, если он настроен
    csp_report_uri = getattr(settings, 'CSP_REPORT_URI', None)
    if csp_report_uri:
        response.headers["Content-Security-Policy-Report-Only"] = (
            csp_policy.replace("default-src 'self'", f"default-src 'self'; report-uri {csp_report_uri}")
        )

    # Добавлять HSTS только в продакшене (HTTPS)
    # Предотвращает атаки понижения протокола
    if getattr(settings, 'HSTS_ENABLED', True):
        hsts_max_age = getattr(settings, 'HSTS_MAX_AGE', 31536000)
        include_subdomains = getattr(settings, 'HSTS_INCLUDE_SUBDOMAINS', True)
        preload = getattr(settings, 'HSTS_PRELOAD', False)

        hsts_value = f"max-age={hsts_max_age}"
        if include_subdomains:
            hsts_value += "; includeSubDomains"
        if preload:
            hsts_value += "; preload"

        # Добавлять HSTS только для HTTPS ответов
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = hsts_value

    # Добавить заголовок Vary для CORS
    # Обеспечивает надлежащее поведение кэширования с несколькими источниками
    if "Access-Control-Allow-Origin" in response.headers:
        response.headers["Vary"] = "Origin"

    return response
