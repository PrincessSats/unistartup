# Password Reset Feature Design

**Date:** 2026-03-31  
**Status:** Approved

## Context

The HackNet platform currently has no password reset flow. Users who forget their password cannot recover access without admin intervention. The platform has working Yandex SMTP infrastructure (used for magic-link registration emails), so password reset can reuse this to send secure reset links to user emails.

The feature enables three user flows:
1. **Login page:** "Forgot password?" button → password reset flow
2. **Profile page:** "Send reset link" in password change modal (for users who forgot current password)
3. Both flows use the same backend reset endpoint

## Architecture

### Database Schema

New table: `auth_password_reset_tokens`

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

**Behavior:**
- Token expires in 1 hour (configurable via `PASSWORD_RESET_TOKEN_TTL_MINUTES`)
- Token becomes single-use: cannot be reused after `used_at` is set
- Tokens are hashed in DB (opaque format), matching refresh token pattern
- Cleanup: old expired tokens should be purged periodically via maintenance script

### Backend Routes

#### `POST /auth/forgot-password`
Request:
```json
{ "email": "user@example.com" }
```

Response (200):
```json
{ "message": "Email sent" }
```

Behavior:
- Looks up user by email (returns 200 even if email not found — prevents email enumeration)
- Generates cryptographically secure opaque token: `secrets.token_urlsafe(48)`
- Stores `SHA-256(token)` in DB with 1-hour expiration
- Sends HTML email with reset link: `<domain>/reset-password?token=<plaintext_token>`
- Rate limiting: max 3 requests per email per hour (in-memory, like existing login rate limit)

#### `POST /auth/reset-password`
Request:
```json
{ "token": "...", "new_password": "..." }
```

Response (200):
```json
{ "message": "Password reset successfully" }
```

Behavior:
- Accepts plaintext token, computes `SHA-256(token)`, looks up in DB
- Validates: token exists, not expired, not already used
- Validates new password strength (reuse `validate_registration_password()`)
- Updates `users.password_hash` with bcrypt of new password
- Marks token as used: sets `used_at = NOW()`
- **Security:** Revokes all refresh tokens for this user (force logout all sessions)
- Rate limiting: max 5 requests per IP per minute (prevent brute force)

### Email Template

Reuse existing `_send_magic_link_email_sync()` infrastructure (SMTP config, SSL/TLS).

Create new template: `password_reset_email_template()` function in `services/registration.py`
- Dark theme, matching magic-link style
- CTA button: "Сбросить пароль" (Reset password)
- Link: `https://hacknet.tech/reset-password?token=<token>`
- Expiration message: "Действительна 1 час" (Valid for 1 hour)
- Note: If user has a refresh token, password reset logs them out (force re-authenticate)

### Configuration

Add to `config.py`:
```python
PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 60
PASSWORD_RESET_REQUEST_RATE_LIMIT: tuple = (3, 3600)  # 3 requests per hour per email
PASSWORD_RESET_CONFIRM_RATE_LIMIT: tuple = (5, 60)    # 5 requests per minute per IP
```

### Frontend Routes & Pages

#### New Route: `/forgot-password`
`ForgotPassword.jsx` page component

1. **Email submission:**
   - Text input for email
   - Submit button: "Отправить ссылку восстановления"
   - Client-side validation: email format
   
2. **Success state:**
   - Message: "Check your email for reset link (valid 1 hour)"
   - Auto-redirect to `/login` after 5 seconds (or manual link)
   - Display email: "We sent a link to user@example.com"

3. **Error handling:**
   - Network error → display error banner
   - Rate limit (429) → "Too many requests, try again in X minutes"

#### New Route: `/reset-password?token=<token>`
`ResetPassword.jsx` page component

1. **Token validation:**
   - Extract token from query param
   - On mount: validate token with `/auth/reset-password/validate` (optional read-only endpoint, returns 200 if valid)

2. **Form:**
   - New password input
   - Confirm password input
   - Password strength indicator (match profile.jsx pattern)
   - Submit button: "Изменить пароль"
   - Client-side: password === confirmPassword, length >= 6

3. **Success state:**
   - Message: "Password reset successfully"
   - Auto-redirect to `/login` after 3 seconds
   - Display: "You can now log in with your new password"

4. **Error handling:**
   - Invalid/expired token → "Reset link has expired, request a new one" with link to `/forgot-password`
   - Network error → error banner
   - Weak password → inline validation error

#### Modify `Login.jsx`
- Replace stub button (lines 172-174) with functional "Forgot password?" button
- Add `onClick={() => navigate('/forgot-password')}`
- Remove placeholder text "Если забыл пароль, восстановление добавим позже."

#### Modify `Profile.jsx`
- Add "Send reset link" button inside password modal (right-aligned, secondary style)
- Behavior: Opens a small dialog or tooltip: "Send a reset link to your email. Useful if you forgot your current password."
- On click: calls `requestPasswordReset(currentUser.email)` → shows toast "Link sent"
- Same success/error handling as `ForgotPassword.jsx`

### Frontend API Service

Add to `frontend/src/services/api.js`:
```javascript
const authAPI = {
  requestPasswordReset: (email) => POST /auth/forgot-password { email }
  confirmPasswordReset: (token, newPassword) => POST /auth/reset-password { token, new_password: newPassword }
}
```

## Security Considerations

1. **Email enumeration:** `/auth/forgot-password` returns 200 even if email not found (standard practice)
2. **Token reuse:** Marked as `used_at` after first successful reset, cannot be reused
3. **Token expiration:** 1 hour TTL, older tokens cleaned up by maintenance script
4. **Session invalidation:** Password change revokes all refresh tokens (user logged out everywhere)
5. **Rate limiting:** Prevents brute force (both request stage and confirm stage)
6. **HTTPS only:** Reset link works only over HTTPS in production (token in query param)
7. **Hashed storage:** Tokens hashed in DB, plaintext only in email/URL

## Testing Strategy

1. **Backend unit tests:**
   - Token generation and validation
   - Token expiration
   - Token single-use enforcement
   - Password strength validation
   - Rate limiting per email and per IP
   - Email sending (mock SMTP)

2. **Backend integration tests:**
   - Full flow: request → email sent → reset with valid token → user can login
   - Expired token rejection
   - Reused token rejection
   - Rate limit enforcement (3 per hour per email, 5 per minute per IP)
   - Session revocation (old refresh token invalid after reset)

3. **Frontend tests:**
   - Navigation to `/forgot-password` and `/reset-password?token=xxx`
   - Email submission and success state
   - Form validation (password match, length)
   - Error states (network, rate limit, expired token)
   - Profile modal "send reset link" button

4. **E2E smoke test:**
   - Complete user journey: Login → Forgot Password → Check Email → Reset → Login with new password

## Files to Create/Modify

**Backend:**
- `backend/app/database.py` - migration: create `auth_password_reset_tokens` table
- `backend/app/models/` - new SQLAlchemy model (or add to existing `auth.py`)
- `backend/app/routes/auth.py` - add `/auth/forgot-password` and `/auth/reset-password` endpoints
- `backend/app/services/registration.py` - new `password_reset_email_template()` and send function
- `backend/app/security/rate_limit.py` - add password reset rate limits
- `backend/app/config.py` - add PASSWORD_RESET_TOKEN_TTL_MINUTES and rate limit settings

**Frontend:**
- `frontend/src/pages/ForgotPassword.jsx` - new page
- `frontend/src/pages/ResetPassword.jsx` - new page
- `frontend/src/pages/Login.jsx` - replace stub button
- `frontend/src/pages/Profile.jsx` - add "send reset link" button
- `frontend/src/services/api.js` - add authAPI.requestPasswordReset and confirmPasswordReset
- `frontend/src/index.js` or router file - register new routes

**Database:**
- `schema.sql` - add `auth_password_reset_tokens` table definition

## Verification

1. **Manual testing:**
   - Forgot password flow from login screen: email → link → reset → login ✓
   - Forgot password flow from profile: button → email → reset ✓
   - Expired token handling ✓
   - Rate limit enforcement ✓

2. **Session cleanup verification:**
   - After password reset, old refresh token is invalid ✓
   - User redirected to login ✓

3. **Email delivery:**
   - Yandex SMTP integration works (reusing existing setup) ✓
   - Email contains valid reset link ✓
