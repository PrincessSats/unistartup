# Profile Provider Display Design

**Date:** 2026-03-31  
**Status:** Design  

---

## Context

The Profile page currently displays a hardcoded "Способы входа" (Login Methods) section with 5 provider rows (GitHub, Apple, Google, Яндекс, Телеграм), but they are non-functional — every button is inert and there is no indication of which providers the user has actually connected.

The database already tracks connected OAuth providers in the `user_auth_identities` table (one record per connected provider per user), and the initial registration method is stored in `user_registration_data.registration_source` (values: `'email_magic_link'`, `'yandex'`, `'github'`, `'telegram'`).

The goal is to reflect the user's actual login methods in the UI: connected providers display normally, unconnected ones are grayed out.

---

## Requirements

1. **Show connected providers correctly**: If a user registered via email, only the email row is active; GitHub/Telegram/Yandex rows are grayed out.
2. **Support all 4 current providers**: email (registration source), GitHub, Telegram, Yandex.
3. **Remove unsupported providers**: Apple and Google have no backend support; remove these rows entirely.
4. **Email is always connected**: Since all users have an email address, the email row is always shown as active.
5. **Gray out = disabled state**: Unconnected providers show a grayed-out button with the text "Добавить" (Add), but the button is disabled/non-interactive.
6. **One API call**: Extend the existing `GET /profile` endpoint to include the provider list; no additional round-trip.

---

## Architecture

### Backend

**File:** `backend/app/schemas/profile.py`

Update the `ProfileResponse` Pydantic model:
```python
class ProfileResponse(BaseModel):
    id: int
    email: str
    username: str
    role: str
    bio: Optional[str]
    avatar_url: Optional[str]
    onboarding_status: Optional[str]
    contest_rating: int
    practice_rating: int
    first_blood: int
    connected_providers: List[str]  # NEW: e.g., ['email', 'yandex']
```

**File:** `backend/app/routes/profile.py`

In the `GET /profile` route handler:
1. Query `user_auth_identities` for the current user → extract provider names (`'github'`, `'telegram'`, `'yandex'`).
2. Query `user_registration_data` for the current user:
   - If `registration_source == 'email_magic_link'` OR the user has a real (non-random) password hash → add `'email'` to the list.
3. Return the combined list in `ProfileResponse.connected_providers`.

**Logic:** A user can have at most one identity per provider (unique constraint), so `list(map(...provider))` from the identity rows directly gives the list.

---

### Frontend

**File:** `frontend/src/pages/Profile.jsx`

In the "Способы входа" section (currently around line 363–430):

1. **Remove Apple and Google rows** — they have no backend support.

2. **Restructure the provider list** to be data-driven instead of hardcoded:
   ```javascript
   const providers = [
     { name: 'email', label: 'Email' },
     { name: 'github', label: 'GitHub' },
     { name: 'telegram', label: 'Telegram' },
     { name: 'yandex', label: 'Яндекс' },
   ];
   ```

3. **For each provider, check if it's in `userData.connected_providers`:**
   ```javascript
   const isConnected = userData.connected_providers?.includes(provider.name);
   ```

4. **Conditional styling:**
   - If `isConnected` → normal appearance, button clickable (for future "disconnect" or "manage" functionality).
   - If not connected → gray out the entire row (text and button), disable the button, keep "Добавить" label.

5. **Email special case:** Always show as connected (no query logic needed).

**Visual changes:**
- Unconnected provider rows have reduced opacity (`opacity-50` or similar) and disabled cursor.
- Connected provider rows are at full opacity with normal cursor.

---

## Data Flow

```
User loads Profile page
    ↓
Frontend: GET /profile
    ↓
Backend: 
  - Fetch user.auth_identities (providers 'github', 'yandex', etc.)
  - Fetch user.registration_data.source (is 'email_magic_link'?)
  - Merge into ['email', 'github', ...]
    ↓
Response includes { connected_providers: [...] }
    ↓
Frontend: Read userData.connected_providers
    ↓
Render provider rows:
  - If in list → active
  - Else → grayed out
```

---

## Implementation Scope

**Backend (2 files):**
- `backend/app/schemas/profile.py` — add field to `ProfileResponse`
- `backend/app/routes/profile.py` — extend `GET /profile` handler with provider query logic

**Frontend (1 file):**
- `frontend/src/pages/Profile.jsx` — restructure provider rows, add connected_providers check, apply conditional styling

**No database migrations needed** — the `user_auth_identities` and `user_registration_data` tables already exist.

---

## Testing

1. **Manual:** Create test users via email, GitHub, Telegram, Yandex. Log in as each and verify the Profile page shows only the correct provider as connected.
2. **Backend unit test:** Mock `get_current_user()`, stub the identity + registration queries, verify the route returns the correct `connected_providers` list.
3. **Frontend component test:** Render the provider section with a mock `userData` object and verify connected providers are active and unconnected are grayed out.

---

## Success Criteria

- ✅ User can see which login methods they have connected.
- ✅ Unconnected providers are visually distinguished (grayed out, disabled button).
- ✅ Apple and Google are removed from the UI.
- ✅ No extra API calls — data is in the existing profile response.
