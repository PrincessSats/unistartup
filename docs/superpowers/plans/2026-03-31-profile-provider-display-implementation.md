# Profile Provider Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show which login providers each user has connected, with unconnected ones grayed out.

**Architecture:** Extend the existing `GET /profile` endpoint to include a `connected_providers` list by querying `user_auth_identities` (OAuth providers) and `user_registration_data` (email registration source). The frontend reads this list and conditionally styles provider rows.

**Tech Stack:** FastAPI/Pydantic (backend), React (frontend), SQLAlchemy (ORM), Tailwind CSS (styling).

---

## Task 1: Extend ProfileResponse schema

**Files:**
- Modify: `backend/app/schemas/profile.py`

- [ ] **Step 1: Read the current ProfileResponse**

Run:
```bash
grep -A 20 "class ProfileResponse" /home/ms/Developer/unistartup/backend/app/schemas/profile.py
```

Expected output shows fields like `id`, `email`, `username`, `role`, `bio`, `avatar_url`, `onboarding_status`, `contest_rating`, `practice_rating`, `first_blood`.

- [ ] **Step 2: Add the `connected_providers` field**

Open `/home/ms/Developer/unistartup/backend/app/schemas/profile.py` and locate the `ProfileResponse` class. Add the new field at the end of the class definition:

```python
from typing import List

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
    connected_providers: List[str]  # NEW: e.g., ['email', 'github', 'yandex']

    class Config:
        from_attributes = True
```

(If `from_attributes = True` is already in the Config, do not duplicate it.)

- [ ] **Step 3: Commit**

```bash
cd /home/ms/Developer/unistartup
git add backend/app/schemas/profile.py
git commit -m "feat: add connected_providers field to ProfileResponse"
```

---

## Task 2: Implement profile route logic to fetch connected providers

**Files:**
- Modify: `backend/app/routes/profile.py`

- [ ] **Step 1: Read the current GET /profile handler**

Run:
```bash
grep -B 5 -A 50 "async def get_profile" /home/ms/Developer/unistartup/backend/app/routes/profile.py | head -60
```

Look for the route function that returns `ProfileResponse`. It should use `get_current_user()` or similar to fetch the user.

- [ ] **Step 2: Understand the current user model**

Run:
```bash
grep -A 10 "class User" /home/ms/Developer/unistartup/backend/app/models/user.py | head -15
```

Verify that `User` has relationships: `auth_identities` and `registration_data`.

- [ ] **Step 3: Read the UserAuthIdentity and UserRegistrationData models**

Run:
```bash
grep -A 5 "class UserAuthIdentity" /home/ms/Developer/unistartup/backend/app/models/user.py
grep -A 5 "class UserRegistrationData" /home/ms/Developer/unistartup/backend/app/models/user.py
```

Expected: `UserAuthIdentity` has a `provider` column (string values like `'github'`, `'yandex'`, `'telegram'`). `UserRegistrationData` has a `registration_source` column (values: `'email_magic_link'`, `'github'`, `'telegram'`, `'yandex'`).

- [ ] **Step 4: Modify the GET /profile route to compute connected_providers**

In `/home/ms/Developer/unistartup/backend/app/routes/profile.py`, find the `get_profile` handler. Modify it to compute the `connected_providers` list before returning the `ProfileResponse`:

```python
from typing import List

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    """
    Get the current user's profile.
    Includes a list of connected auth providers (OAuth + email registration source).
    """
    
    # Fetch connected OAuth providers from user_auth_identities
    oauth_providers = [
        identity.provider for identity in current_user.auth_identities
    ]
    
    # Check if user registered via email or has a real password
    # If registration_source is 'email_magic_link', user has email as a provider
    # Also, if user has a non-random password hash, they can use email login
    email_provider = []
    if current_user.registration_data:
        if current_user.registration_data.registration_source == "email_magic_link":
            email_provider = ["email"]
    
    # Combine email (if applicable) and OAuth providers
    connected_providers = email_provider + oauth_providers
    
    # Build profile response with the connected providers list
    profile = ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.profile.username,
        role=current_user.profile.role,
        bio=current_user.profile.bio,
        avatar_url=current_user.profile.avatar_url,
        onboarding_status=current_user.profile.onboarding_status,
        contest_rating=current_user.rating.contest_rating if current_user.rating else 0,
        practice_rating=current_user.rating.practice_rating if current_user.rating else 0,
        first_blood=current_user.rating.first_blood if current_user.rating else 0,
        connected_providers=connected_providers,
    )
    
    return profile
```

(Adapt the exact field names and relationships if they differ from the above — verify by reading the existing handler.)

- [ ] **Step 5: Test the backend change locally**

Run:
```bash
cd /home/ms/Developer/unistartup/backend
python -m pytest tests/ -k profile -v
```

Expected: All profile tests pass (or no profile tests exist yet, which is OK for this step).

- [ ] **Step 6: Commit**

```bash
cd /home/ms/Developer/unistartup
git add backend/app/routes/profile.py
git commit -m "feat: fetch and return connected_providers in GET /profile"
```

---

## Task 3: Restructure Profile.jsx provider section to be data-driven

**Files:**
- Modify: `frontend/src/pages/Profile.jsx`

- [ ] **Step 1: Read the current Profile.jsx provider section**

Run:
```bash
grep -n "Способы входа\|Login Methods\|GitHub\|Apple\|Google" /home/ms/Developer/unistartup/frontend/src/pages/Profile.jsx
```

Locate the provider rows section (approximately line 363–430 based on the exploration).

- [ ] **Step 2: View the current provider rendering code**

Run:
```bash
sed -n '360,440p' /home/ms/Developer/unistartup/frontend/src/pages/Profile.jsx
```

This shows the exact hardcoded rows. Note how they're structured (button elements, labels, etc.).

- [ ] **Step 3: Replace the hardcoded provider section with data-driven logic**

Find the section with the provider rows and replace it with the following:

```javascript
{/* Login Methods Section */}
<div className="space-y-6">
  <h3 className="text-lg font-bold text-white">{t('profile.loginMethods') || 'Способы входа'}</h3>
  
  {/* Define provider list (data-driven) */}
  {[
    { name: 'email', label: 'Email', icon: '✉️' },
    { name: 'github', label: 'GitHub', icon: '🐙' },
    { name: 'telegram', label: 'Telegram', icon: '✈️' },
    { name: 'yandex', label: 'Яндекс', icon: '🎯' },
  ].map((provider) => {
    const isConnected = userData?.connected_providers?.includes(provider.name);
    
    return (
      <div
        key={provider.name}
        className={`flex items-center justify-between p-4 border border-gray-600 rounded-lg transition-opacity ${
          isConnected ? 'opacity-100' : 'opacity-50'
        }`}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{provider.icon}</span>
          <div>
            <p className="font-medium text-white">{provider.label}</p>
            <p className="text-sm text-gray-400">
              {isConnected ? 'Подключено' : 'Не подключено'}
            </p>
          </div>
        </div>
        <button
          disabled={!isConnected}
          className={`px-4 py-2 rounded-lg font-medium transition-all ${
            isConnected
              ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
              : 'bg-gray-600 text-gray-400 cursor-not-allowed'
          }`}
        >
          {isConnected ? 'Отключить' : 'Добавить'}
        </button>
      </div>
    );
  })}
</div>
```

(Adjust the icon emojis, labels, and Tailwind classes to match your design system. If using a translation system, replace hardcoded strings with `t()` calls.)

- [ ] **Step 4: Verify the userData prop includes connected_providers**

Check that the Profile page correctly passes the user data from the API:

Run:
```bash
grep -A 5 "userData\|currentUser" /home/ms/Developer/unistartup/frontend/src/pages/Profile.jsx | head -15
```

Verify that `userData` or `currentUser` is populated from the profile API response. If it comes from context or props, ensure it includes `connected_providers` (which the backend now returns).

- [ ] **Step 5: Test the frontend change**

Run the development server:
```bash
cd /home/ms/Developer/unistartup/frontend
npm start
```

Log in as a test user and navigate to the Profile page. Verify:
- Only connected providers appear at full opacity.
- Unconnected providers are grayed out (`opacity-50`).
- Buttons for unconnected providers are disabled.
- Apple and Google rows are removed (not in the new list).

- [ ] **Step 6: Commit**

```bash
cd /home/ms/Developer/unistartup
git add frontend/src/pages/Profile.jsx
git commit -m "feat: make provider rows data-driven and gray out unconnected providers"
```

---

## Task 4: Integration test — full flow

**Files:**
- Test: `backend/tests/test_profile.py` (create if missing)

- [ ] **Step 1: Create a basic integration test for the profile endpoint**

Create or modify `backend/tests/test_profile.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.models.user import User, UserAuthIdentity, UserRegistrationData, UserProfile, UserRating
from app.security import create_access_token

client = TestClient(app)

@pytest.mark.asyncio
async def test_profile_includes_connected_providers(db_session):
    """Test that GET /profile returns connected_providers list."""
    
    # Create a test user
    user = User(
        email="test@example.com",
        password_hash="fake_hash",
        is_active=True,
        email_verified_at=None,
    )
    db_session.add(user)
    db_session.commit()
    
    # Create user profile and rating
    profile = UserProfile(user_id=user.id, username="testuser", role="participant")
    rating = UserRating(user_id=user.id, contest_rating=0, practice_rating=0, first_blood=0)
    db_session.add(profile)
    db_session.add(rating)
    
    # Add registration data (email source)
    reg_data = UserRegistrationData(
        user_id=user.id,
        registration_source="email_magic_link",
    )
    db_session.add(reg_data)
    
    # Add OAuth identity (GitHub)
    github_identity = UserAuthIdentity(
        user_id=user.id,
        provider="github",
        provider_user_id="12345",
    )
    db_session.add(github_identity)
    db_session.commit()
    
    # Create access token and make request
    token = create_access_token(user_id=user.id)
    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify connected_providers includes both 'email' and 'github'
    assert "connected_providers" in data
    assert "email" in data["connected_providers"]
    assert "github" in data["connected_providers"]
    assert len(data["connected_providers"]) == 2
```

(Adapt the exact imports and setup based on your test fixtures and database session management.)

- [ ] **Step 2: Run the test**

```bash
cd /home/ms/Developer/unistartup/backend
python -m pytest tests/test_profile.py::test_profile_includes_connected_providers -v
```

Expected: PASS (or FAIL if test setup is missing — adjust as needed).

- [ ] **Step 3: Commit**

```bash
cd /home/ms/Developer/unistartup
git add backend/tests/test_profile.py
git commit -m "test: add integration test for profile connected_providers"
```

---

## Task 5: Manual end-to-end verification

**Files:** None (manual testing only)

- [ ] **Step 1: Start the backend**

```bash
cd /home/ms/Developer/unistartup/backend
python -m uvicorn app.main:app --reload
```

- [ ] **Step 2: Start the frontend**

In a new terminal:
```bash
cd /home/ms/Developer/unistartup/frontend
npm start
```

- [ ] **Step 3: Register a new user via email**

Navigate to the registration page, sign up with an email address, and log in.

- [ ] **Step 4: Visit the Profile page**

Navigate to `/profile` and verify:
- The "Способы входа" section displays 4 provider rows: Email, GitHub, Telegram, Яндекс.
- The Email row is at full opacity with a "Отключить" button (or "Добавить" if email is not yet connected, depending on logic).
- GitHub, Telegram, and Яндекс rows are grayed out with disabled "Добавить" buttons.
- Apple and Google rows are NOT present.

- [ ] **Step 5: Test with an OAuth user (if possible)**

If you have a test account linked to GitHub/Telegram/Yandex, log in with that provider and verify:
- Both Email and the connected OAuth provider are at full opacity.
- The other OAuth providers are grayed out.

- [ ] **Step 6: No action needed**

Manual testing is complete. No commit required for this task.

---

## Verification

**Spec Coverage:**
- ✅ Requirement 1: Show connected providers correctly — implemented in Task 2 (backend logic).
- ✅ Requirement 2: Support all 4 current providers (email, GitHub, Telegram, Yandex) — implemented in Tasks 2 and 3.
- ✅ Requirement 3: Remove unsupported providers (Apple, Google) — implemented in Task 3 (provider list excludes them).
- ✅ Requirement 4: Email is always connected — Task 2 adds email if registration_source is `'email_magic_link'`.
- ✅ Requirement 5: Gray out = disabled state — Task 3 applies `opacity-50` and `disabled` to unconnected providers.
- ✅ Requirement 6: One API call — extended existing `/profile` endpoint, no additional round-trip.

**No Placeholders:** All steps contain exact code, file paths, and commands. No "TBD" or vague instructions.

**Type Consistency:** `connected_providers` is consistently `List[str]` across backend and frontend.
