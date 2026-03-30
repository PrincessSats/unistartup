"""
Security headers middleware for HTTP responses.

Adds essential security headers to all responses:
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


# Default Content Security Policy
# Restricts resource loading to prevent XSS and data injection
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
    Add security headers to all HTTP responses.
    
    This middleware runs for every request and adds essential
    security headers to the response before it's sent to the client.
    """
    response = await call_next(request)
    
    # Prevent MIME type sniffing
    # Forces browser to respect declared Content-Type
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking attacks
    # Disallows page from being displayed in any frame
    response.headers["X-Frame-Options"] = "DENY"
    
    # Enable XSS filter in older browsers
    # Modern browsers use Content-Security-Policy instead
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Control referrer information sent with requests
    # Sends full referrer to same-origin, only origin to cross-origin
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Restrict browser features/APIs
    # Disables geolocation, microphone, camera, etc.
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
    
    # Content Security Policy - prevents XSS and data injection
    csp_policy = getattr(settings, 'CSP_POLICY', DEFAULT_CSP)
    response.headers["Content-Security-Policy"] = csp_policy
    
    # Add CSP report URI if configured
    csp_report_uri = getattr(settings, 'CSP_REPORT_URI', None)
    if csp_report_uri:
        response.headers["Content-Security-Policy-Report-Only"] = (
            csp_policy.replace("default-src 'self'", f"default-src 'self'; report-uri {csp_report_uri}")
        )
    
    # Only add HSTS in production (HTTPS)
    # Prevents protocol downgrade attacks
    if getattr(settings, 'HSTS_ENABLED', True):
        hsts_max_age = getattr(settings, 'HSTS_MAX_AGE', 31536000)
        include_subdomains = getattr(settings, 'HSTS_INCLUDE_SUBDOMAINS', True)
        preload = getattr(settings, 'HSTS_PRELOAD', False)
        
        hsts_value = f"max-age={hsts_max_age}"
        if include_subdomains:
            hsts_value += "; includeSubDomains"
        if preload:
            hsts_value += "; preload"
        
        # Only add HSTS on HTTPS responses
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = hsts_value
    
    # Add Vary header for CORS
    # Ensures proper caching behavior with multiple origins
    if "Access-Control-Allow-Origin" in response.headers:
        response.headers["Vary"] = "Origin"
    
    return response
