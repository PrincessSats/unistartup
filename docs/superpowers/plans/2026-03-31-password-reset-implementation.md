# Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement complete password reset flow: forgot password → email link → reset password, across backend and frontend with rate limiting and session invalidation.

**Architecture:** 
- Backend: Two endpoints (`/auth/forgot-password`, `/auth/reset-password`) with hashed token storage, rate limiting, and email sending
- Frontend: Two new pages (`ForgotPassword`, `ResetPassword`) + button integration in Login and Profile
- Database: New `auth_password_reset_tokens` table for token lifecycle management
- Email: Reuse existing Yandex SMTP infrastructure with new password reset template

**Tech Stack:** FastAPI, SQLAlchemy, bcrypt, secrets, SMTP (Yandex), Pydantic, React, React Router, Axios

---

## File Structure

**Backend (Database):**
- `schema.sql` — add `auth_password_reset_tokens` table

**Backend (Config):**
- `backend/app/config.py` — add PASSWORD_RESET_* settings

**Backend (Models):**
- `backend/app/models/auth.py` — new `PasswordResetToken` SQLAlchemy model

**Backend (Security):**
- `backend/app/security/rate_limit.py` — add password reset rate limiters

**Backend (Services):**
- `backend/app/services/registration.py` — add `password_reset_email_template()` and `send_password_reset_email()` functions

**Backend (Routes):**
- `backend/app/routes/auth.py` — add `/auth/forgot-password` and `/auth/reset-password` endpoints

**Frontend (Services):**
- `frontend/src/services/api.js` — add `authAPI.requestPasswordReset()` and `authAPI.confirmPasswordReset()`

**Frontend (Router):**
- `frontend/src/index.js` or `App.jsx` — register `/forgot-password` and `/reset-password` routes

**Frontend (Pages):**
- `frontend/src/pages/ForgotPassword.jsx` — new page (email input → success state)
- `frontend/src/pages/ResetPassword.jsx` — new page (token validation → new password form → success)
- `frontend/src/pages/Login.jsx` — modify: replace stub button with functional link
- `frontend/src/pages/Profile.jsx` — modify: add "send reset link" button in password modal

---

## Implementation Tasks

### Task 1: Add `auth_password_reset_tokens` Table to Schema

**Files:**
- Modify: `schema.sql`

- [ ] **Step 1: Add table definition to schema.sql**

Open `schema.sql` and find the `auth_refresh_tokens` table (around line 54). After it, add:

```sql
CREATE TABLE auth_password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    CONSTRAINT no_reuse CHECK (used_at IS NULL OR used_at <= expires_at)
);

CREATE INDEX idx_password_reset_tokens_user_id ON auth_password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON auth_password_reset_tokens(expires_at);
```

- [ ] **Step 2: Commit**

```bash
git add schema.sql
git commit -m "schema: add auth_password_reset_tokens table"
```

---

### Task 2: Add Password Reset Configuration Settings

**Files:**
- Modify: `backend/app/config.py:1-150`

- [ ] **Step 1: Find the Settings class**

Open `backend/app/config.py`. Find the line with `MAGIC_LINK_TTL_HOURS` (around line 147). After the last SMTP setting, add:

```python
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 60
    PASSWORD_RESET_REQUEST_RATE_LIMIT_COUNT: int = 3
    PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW: int = 3600
    PASSWORD_RESET_CONFIRM_RATE_LIMIT_COUNT: int = 5
    PASSWORD_RESET_CONFIRM_RATE_LIMIT_WINDOW: int = 60
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "config: add password reset settings"
```

---

### Task 3: Create PasswordResetToken SQLAlchemy Model

**Files:**
- Modify: `backend/app/models/auth.py` (create if doesn't exist, or add to existing auth models file)

- [ ] **Step 1: Create or open the auth models file**

Check if `backend/app/models/auth.py` exists. If not, create it with:

```python
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.database import Base

class PasswordResetToken(Base):
    __tablename__ = "auth_password_reset_tokens"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to User (assumes User model exists in same or different file)
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_password_reset_tokens_user_id", user_id),
        Index("idx_password_reset_tokens_expires_at", expires_at),
    )
```

If `auth.py` already exists, add this class at the end of the file after other models.

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/auth.py
git commit -m "models: add PasswordResetToken ORM model"
```

---

### Task 4: Add Password Reset Rate Limiters

**Files:**
- Modify: `backend/app/security/rate_limit.py`

- [ ] **Step 1: Open rate_limit.py and add two new rate limiter functions**

Find the end of the existing rate limiter definitions (after `auth_login_account` limiter, around line 40). Add:

```python
# Password reset rate limiters
auth_forgot_password_email = RateLimiter(
    key_func=lambda email: f"auth:forgot_password:email:{email}",
    max_requests=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_COUNT,
    window_seconds=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW,
)

auth_reset_password_ip = RateLimiter(
    key_func=lambda ip: f"auth:reset_password:ip:{ip}",
    max_requests=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_COUNT,
    window_seconds=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_WINDOW,
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/security/rate_limit.py
git commit -m "security: add password reset rate limiters"
```

---

### Task 5: Add Password Reset Email Template and Send Function

**Files:**
- Modify: `backend/app/services/registration.py`

- [ ] **Step 1: Add password reset email template function**

Open `backend/app/services/registration.py`. Find the `_send_magic_link_email_sync()` function (around line 490). After that function, add:

```python
def password_reset_email_template(reset_token: str, user_email: str, reset_link_url: str) -> tuple[str, str]:
    """
    Generate password reset email subject and HTML body.
    
    Args:
        reset_token: The plaintext reset token (for audit/logging, not sent)
        user_email: User's email address
        reset_link_url: Full URL to reset page with token (e.g., https://hacknet.tech/reset-password?token=xyz)
    
    Returns:
        (subject, html_body)
    """
    subject = "Восстановление пароля на HackNet"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e27; color: #e0e0e0; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1a1f3a; border-radius: 8px; padding: 40px; border: 1px solid #2a3050; }}
            .logo {{ text-align: center; margin-bottom: 30px; font-size: 24px; font-weight: bold; color: #00d4ff; }}
            .greeting {{ margin-bottom: 20px; font-size: 16px; }}
            .message {{ margin-bottom: 30px; line-height: 1.6; font-size: 14px; }}
            .button {{ display: inline-block; background: #00d4ff; color: #0a0e27; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
            .expiry {{ margin-top: 20px; font-size: 12px; color: #999; }}
            .footer {{ margin-top: 40px; border-top: 1px solid #2a3050; padding-top: 20px; font-size: 12px; color: #666; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">HackNet</div>
            
            <div class="greeting">Привет,</div>
            
            <div class="message">
                Вы запросили восстановление пароля. Нажмите на кнопку ниже, чтобы установить новый пароль:
            </div>
            
            <a href="{reset_link_url}" class="button">Сбросить пароль</a>
            
            <div class="expiry">
                ⏱️ Ссылка действительна 1 час. Если вы не запрашивали восстановление, проигнорируйте это письмо.
            </div>
            
            <div class="footer">
                <p>© 2026 HackNet. Все права защищены.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html_body
```

- [ ] **Step 2: Add send function**

After the `password_reset_email_template()` function, add:

```python
def _send_password_reset_email_sync(user_email: str, reset_token: str, frontend_base_url: str = "https://hacknet.tech") -> bool:
    """
    Synchronously send password reset email via Yandex SMTP.
    
    Args:
        user_email: Recipient email
        reset_token: Plaintext reset token to include in link
        frontend_base_url: Base URL for reset link (e.g., https://hacknet.tech)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        reset_link_url = f"{frontend_base_url}/reset-password?token={reset_token}"
        subject, html_body = password_reset_email_template(reset_token, user_email, reset_link_url)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = settings.smtp_from_address
        msg["To"] = user_email
        
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        with ssl.create_default_context() as context:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
                server.login(settings.YANDEX_MAIL_LOGIN, settings.YANDEX_MAIL_PASSWORD)
                server.sendmail(settings.smtp_from_address, user_email, msg.as_string())
        
        logger.info(f"Password reset email sent to {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user_email}: {e}")
        return False


async def send_password_reset_email(user_email: str, reset_token: str, frontend_base_url: str = "https://hacknet.tech") -> bool:
    """
    Async wrapper for password reset email sending.
    """
    return await anyio.to_thread.run_sync(
        _send_password_reset_email_sync,
        user_email,
        reset_token,
        frontend_base_url,
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/registration.py
git commit -m "services: add password reset email template and sender"
```

---

### Task 6: Implement `/auth/forgot-password` and `/auth/reset-password` Endpoints

**Files:**
- Modify: `backend/app/routes/auth.py`

- [ ] **Step 1: Add imports at top of auth.py**

Open `backend/app/routes/auth.py` and find the imports section. Add these imports if not already present:

```python
from datetime import datetime, timezone, timedelta
import secrets
import hashlib
from sqlalchemy import select, and_
from backend.app.models.auth import PasswordResetToken
from backend.app.security.rate_limit import auth_forgot_password_email, auth_reset_password_ip
from backend.app.services.registration import send_password_reset_email
```

- [ ] **Step 2: Add forgot-password endpoint**

Find the `@router.post("/login")` endpoint in auth.py (around line 50). After the login endpoint, add:

```python
@router.post("/forgot-password")
async def forgot_password(
    request: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    request_obj: Request = Depends(),
):
    """
    Request a password reset link. Returns 200 even if email not found (prevents email enumeration).
    Rate limited to 3 requests per email per hour.
    """
    try:
        # Apply rate limit (check first, to fail fast)
        await auth_forgot_password_email.check_limit(request.email)
    except HTTPException as e:
        # Still return 200 to prevent email enumeration
        return {"message": "Email sent"}
    
    # Look up user
    stmt = select(User).where(User.email == request.email.lower())
    user = await db.scalar(stmt)
    
    if not user:
        # Return success even if user not found (email enumeration prevention)
        return {"message": "Email sent"}
    
    # Generate reset token
    plaintext_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()
    
    # Create token record
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    await db.commit()
    
    # Send email
    frontend_url = settings.FRONTEND_BASE_URL or "https://hacknet.tech"
    await send_password_reset_email(user.email, plaintext_token, frontend_base_url=frontend_url)
    
    logger.info(f"Password reset requested for {user.email}")
    return {"message": "Email sent"}


@router.post("/reset-password")
async def reset_password(
    request: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    request_obj: Request = Depends(),
):
    """
    Reset password using a valid reset token. Token is single-use. 
    Revokes all refresh tokens for the user (logs them out everywhere).
    Rate limited to 5 requests per IP per minute.
    """
    # Get client IP for rate limiting
    client_ip = request_obj.client.host if request_obj.client else "unknown"
    
    try:
        await auth_reset_password_ip.check_limit(client_ip)
    except HTTPException:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    
    # Validate new password
    try:
        validate_registration_password(request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Hash the plaintext token to look up in DB
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    
    # Find token
    stmt = select(PasswordResetToken).where(
        and_(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),  # Not yet used
            PasswordResetToken.expires_at > datetime.now(timezone.utc),  # Not expired
        )
    )
    reset_token = await db.scalar(stmt)
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    
    # Mark token as used
    reset_token.used_at = datetime.now(timezone.utc)
    
    # Get user and update password
    user = await db.get(User, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")
    
    user.password_hash = bcrypt.hashpw(request.new_password.encode(), bcrypt.gensalt()).decode()
    
    # Revoke all refresh tokens for this user (log out all sessions)
    stmt_revoke = select(AuthRefreshToken).where(
        AuthRefreshToken.user_id == user.id,
        AuthRefreshToken.revoked_at.is_(None),
    )
    tokens_to_revoke = await db.scalars(stmt_revoke)
    for token in tokens_to_revoke:
        token.revoked_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    logger.info(f"Password reset for {user.email}")
    return {"message": "Password reset successfully"}
```

- [ ] **Step 3: Add Pydantic schemas for requests**

Open `backend/app/schemas/` or find the schemas file that contains auth request/response models. Add these schemas:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
```

If schemas are in `backend/app/schemas/auth.py`, add there. If they're in a combined file, add to the appropriate location.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/auth.py backend/app/schemas/auth.py
git commit -m "routes: add forgot-password and reset-password endpoints"
```

---

### Task 7: Add API Methods to Frontend Service

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Find the authAPI object in api.js**

Open `frontend/src/services/api.js`. Find the `authAPI` object (around line 20-50). Add these two methods to it:

```javascript
const authAPI = {
  // ... existing methods ...
  
  requestPasswordReset: (email) => {
    return api.post('/auth/forgot-password', { email });
  },
  
  confirmPasswordReset: (token, newPassword) => {
    return api.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
  },
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "services: add password reset API methods"
```

---

### Task 8: Register Frontend Routes

**Files:**
- Modify: `frontend/src/index.js` or router file (likely `frontend/src/App.jsx`)

- [ ] **Step 1: Find the router configuration**

Open the main router file (likely `frontend/src/App.jsx` or `frontend/src/index.js`). Find the route definitions (should be JSX with `<Route>` elements or a route config array).

Add these two routes after the `/login` route:

```jsx
<Route path="/forgot-password" element={<ForgotPassword />} />
<Route path="/reset-password" element={<ResetPassword />} />
```

Import both page components at the top of the file:

```javascript
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "router: register forgot-password and reset-password routes"
```

---

### Task 9: Create ForgotPassword Page Component

**Files:**
- Create: `frontend/src/pages/ForgotPassword.jsx`

- [ ] **Step 1: Create ForgotPassword.jsx**

Create the file at `frontend/src/pages/ForgotPassword.jsx`:

```jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authAPI.requestPasswordReset(email);
      setSuccess(true);
      setEmail('');
      
      // Auto-redirect after 5 seconds
      setTimeout(() => {
        navigate('/login');
      }, 5000);
    } catch (err) {
      if (err.response?.status === 429) {
        setError('Too many requests. Please try again in a few minutes.');
      } else {
        setError(err.response?.data?.detail || 'Failed to send reset link. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black flex items-center justify-center px-4">
        <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Ссылка отправлена</h2>
          <p className="text-gray-300 mb-6">
            Проверьте ваш email <strong>{email}</strong>. Ссылка для восстановления пароля действительна 1 час.
          </p>
          <p className="text-gray-400 text-sm mb-6">
            Вы будете перенаправлены на страницу входа через несколько секунд...
          </p>
          <button
            onClick={() => navigate('/login')}
            className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded w-full transition"
          >
            Вернуться на вход
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black flex items-center justify-center px-4">
      <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-white mb-2">Восстановление пароля</h1>
        <p className="text-gray-400 mb-6">Введите адрес электронной почты, и мы отправим ссылку для восстановления</p>

        {error && (
          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <label className="block text-gray-300 font-semibold mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="you@example.com"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded transition"
          >
            {loading ? 'Отправка...' : 'Отправить ссылку'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-gray-400">
            Вспомнили пароль?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-blue-400 hover:text-blue-300 font-semibold transition"
            >
              Вернуться на вход
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ForgotPassword.jsx
git commit -m "pages: add ForgotPassword page"
```

---

### Task 10: Create ResetPassword Page Component

**Files:**
- Create: `frontend/src/pages/ResetPassword.jsx`

- [ ] **Step 1: Create ResetPassword.jsx**

Create the file at `frontend/src/pages/ResetPassword.jsx`:

```jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI } from '../services/api';

export default function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [tokenValid, setTokenValid] = useState(null);

  useEffect(() => {
    if (!token) {
      setError('Reset token is missing. Please use the link from your email.');
      setTokenValid(false);
      return;
    }
    setTokenValid(true);
  }, [token]);

  const validatePasswords = () => {
    if (newPassword.length < 6) {
      setError('Пароль должен быть не менее 6 символов');
      return false;
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validatePasswords()) {
      return;
    }

    setLoading(true);

    try {
      await authAPI.confirmPasswordReset(token, newPassword);
      setSuccess(true);
      setNewPassword('');
      setConfirmPassword('');

      // Auto-redirect after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err) {
      if (err.response?.status === 400) {
        setError('Ссылка истекла или недействительна. Запросите новую ссылку для восстановления.');
      } else if (err.response?.status === 429) {
        setError('Слишком много попыток. Попробуйте позже.');
      } else {
        setError(err.response?.data?.detail || 'Ошибка при сбросе пароля. Попробуйте снова.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (tokenValid === false) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black flex items-center justify-center px-4">
        <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Ошибка</h2>
          <p className="text-gray-300 mb-6">{error}</p>
          <button
            onClick={() => navigate('/forgot-password')}
            className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded w-full transition"
          >
            Запросить новую ссылку
          </button>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black flex items-center justify-center px-4">
        <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Пароль изменён</h2>
          <p className="text-gray-300 mb-6">Пароль успешно сброшен. Вы можете войти с новым паролем.</p>
          <p className="text-gray-400 text-sm mb-6">Перенаправление на страницу входа...</p>
          <button
            onClick={() => navigate('/login')}
            className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded w-full transition"
          >
            Перейти на вход
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-black flex items-center justify-center px-4">
      <div className="bg-gray-800 rounded-lg p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-white mb-2">Новый пароль</h1>
        <p className="text-gray-400 mb-6">Введите новый пароль для вашего аккаунта</p>

        {error && (
          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-300 font-semibold mb-2">Новый пароль</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="Минимум 6 символов"
              disabled={loading}
            />
            <p className="text-gray-400 text-xs mt-1">Минимум 6 символов</p>
          </div>

          <div className="mb-6">
            <label className="block text-gray-300 font-semibold mb-2">Подтверждение пароля</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="Введите пароль ещё раз"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded transition"
          >
            {loading ? 'Изменение пароля...' : 'Изменить пароль'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-gray-400">
            <button
              onClick={() => navigate('/forgot-password')}
              className="text-blue-400 hover:text-blue-300 font-semibold transition"
            >
              Запросить новую ссылку
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ResetPassword.jsx
git commit -m "pages: add ResetPassword page"
```

---

### Task 11: Modify Login Page — Replace Stub Button

**Files:**
- Modify: `frontend/src/pages/Login.jsx:171-174`

- [ ] **Step 1: Find and replace the forgot password section**

Open `frontend/src/pages/Login.jsx`. Find lines 171-174 (the stub button with "Если забыл пароль..."). Replace:

```jsx
// BEFORE (stub):
<span className="text-white/38">Если забыл пароль, восстановление добавим позже.</span>
<button type="button" className="text-white/60 transition hover:text-white">
  Не помнишь пароль?
</button>
```

With:

```jsx
// AFTER (functional):
<button
  type="button"
  onClick={() => navigate('/forgot-password')}
  className="text-white/60 transition hover:text-white"
>
  Не помнишь пароль?
</button>
```

Also add `useNavigate` import at the top of the file if not already present:

```javascript
import { useNavigate } from 'react-router-dom';
```

And inside the component, add:

```javascript
const navigate = useNavigate();
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Login.jsx
git commit -m "pages: make forgot-password button functional in Login"
```

---

### Task 12: Modify Profile Page — Add "Send Reset Link" Button

**Files:**
- Modify: `frontend/src/pages/Profile.jsx`

- [ ] **Step 1: Find the password modal in Profile.jsx**

Open `frontend/src/pages/Profile.jsx`. Find the password change modal (around lines 140-200, look for `showPasswordModal` state). Inside the modal, after the password form inputs but before the submit button, add:

```jsx
<div className="flex gap-2 mt-4 mb-4">
  <button
    type="submit"
    disabled={loading}
    className="flex-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 text-white font-semibold py-2 rounded transition"
  >
    {loading ? 'Изменение...' : 'Изменить пароль'}
  </button>
  <button
    type="button"
    onClick={handleSendResetLink}
    disabled={loading}
    className="flex-1 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-600 text-white font-semibold py-2 rounded transition text-sm"
    title="Send reset link if you forgot current password"
  >
    Отправить ссылку
  </button>
</div>
```

- [ ] **Step 2: Add the handler function**

In the Profile component, find where `handleSavePassword` is defined (around line 172). Before it, add:

```javascript
const handleSendResetLink = async () => {
  try {
    setLoading(true);
    await authAPI.requestPasswordReset(currentUser.email);
    
    // Show success toast
    setError('');
    setSuccess('Ссылка для восстановления отправлена на ваш email');
    
    // Clear message after 3 seconds
    setTimeout(() => {
      setSuccess('');
    }, 3000);
  } catch (err) {
    setError(err.response?.data?.detail || 'Ошибка при отправке ссылки');
  } finally {
    setLoading(false);
  }
};
```

Also ensure `authAPI` is imported at the top:

```javascript
import { authAPI, profileAPI } from '../services/api';
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Profile.jsx
git commit -m "pages: add send-reset-link button to Profile password modal"
```

---

## Verification Checklist

After all tasks are complete:

1. **Database migration applied:**
   ```bash
   # If using migrations, run migration. If using schema.sql directly:
   psql -U postgres -h localhost -p 6432 hacknet < schema.sql
   ```
   Verify: `\dt auth_password_reset_tokens` shows the table in psql

2. **Backend tests pass:**
   ```bash
   cd backend
   pytest tests/test_auth.py -v -k password_reset
   ```

3. **Frontend routes registered:**
   Navigate to `http://localhost:3000/forgot-password` and `http://localhost:3000/reset-password?token=test` — should load pages without crashes

4. **E2E flow test (manual):**
   - Go to login page
   - Click "Не помнишь пароль?"
   - Should navigate to `/forgot-password`
   - Enter email, submit
   - Should see success message
   - Check mailbox (or mock SMTP logs) for reset email
   - Click link in email
   - Should navigate to `/reset-password?token=xxx`
   - Enter new password, submit
   - Should see success and redirect to login
   - Try logging in with new password — should work

5. **Session revocation test (manual):**
   - User is logged in (has refresh token)
   - User requests password reset
   - While reset page is open, make an API call with old refresh token
   - Should return 401 (token revoked)

6. **Rate limiting test (manual):**
   - Request 4 reset emails for same email within 1 hour — 4th should be rate limited
   - Request 6 password resets from same IP within 1 minute — 6th should be rate limited

---

**Next Step:** Execute this plan using superpowers:subagent-driven-development or superpowers:executing-plans.
