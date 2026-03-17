import os
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "app")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "pass")
os.environ.setdefault("SECRET_KEY", "secret")

from fastapi import HTTPException, Response  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app.routes import auth_registration  # noqa: E402
from app.schemas.user import RegistrationCompleteRequest  # noqa: E402
from app.services.registration import utcnow  # noqa: E402


def build_request(host: str = "127.0.0.1:3000") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/yandex/start",
        "headers": [(b"host", host.encode("utf-8"))],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


class AuthRegistrationRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_yandex_callback_existing_user_uses_explicit_profile_query(self) -> None:
        request = build_request()
        now = utcnow()

        flow = SimpleNamespace(
            id=11,
            expires_at=now + timedelta(minutes=5),
            consumed_at=None,
            intent="login",
            oauth_code_verifier="verifier",
            email=None,
            email_verified_at=None,
            provider=None,
            provider_user_id=None,
            provider_email=None,
            provider_login=None,
            provider_avatar_url=None,
            provider_raw_profile_json=None,
            oauth_state_hash="hashed",
            completed_user_id=None,
        )

        class ExistingUser:
            id = 7
            email = "user@example.com"
            is_active = True
            email_verified_at = None

            @property
            def profile(self):  # pragma: no cover - must never be touched
                raise AssertionError("lazy profile access is forbidden in async callback")

        user = ExistingUser()
        profile = SimpleNamespace(user_id=7, avatar_url=None)

        def result(value):
            return SimpleNamespace(scalar_one_or_none=lambda: value)

        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    result(flow),      # flow by state hash
                    result(None),      # identity by provider subject
                    result(user),      # user by email
                    result(profile),   # explicit profile lookup
                ]
            ),
            get=AsyncMock(return_value=None),
            add=MagicMock(),
        )

        with patch(
            "app.routes.auth_registration.exchange_yandex_code_for_token",
            AsyncMock(return_value={"access_token": "oauth-token"}),
        ), patch(
            "app.routes.auth_registration.fetch_yandex_profile",
            AsyncMock(
                return_value=SimpleNamespace(
                    provider_user_id="yandex-42",
                    email="user@example.com",
                    login="yanuser",
                    avatar_url="https://avatars.yandex.net/avatar.png",
                    raw_profile={"id": "yandex-42"},
                )
            ),
        ), patch(
            "app.routes.auth_registration.issue_login_session",
            AsyncMock(return_value=("refresh-token", "access-token", now, now + timedelta(hours=1))),
        ), patch(
            "app.routes.auth_registration.set_refresh_cookie"
        ) as set_cookie:
            response = await auth_registration.yandex_oauth_callback(
                request=request,
                code="oauth-code",
                state="opaque-state",
                error=None,
                db=db,
            )

        self.assertEqual(response.status_code, 303)
        self.assertIn("/auth/bridge", response.headers["location"])
        self.assertEqual(profile.avatar_url, "https://avatars.yandex.net/avatar.png")
        set_cookie.assert_called_once()

    async def test_start_yandex_oauth_requires_terms_for_register(self) -> None:
        request = build_request()
        db = AsyncMock()

        with patch.object(auth_registration.settings, "YANDEX_CLIENT_ID", "client"), patch.object(
            auth_registration.settings,
            "YANDEX_CLIENT_SECRET",
            "secret",
        ):
            with self.assertRaises(HTTPException) as ctx:
                await auth_registration.start_yandex_oauth(
                    request=request,
                    intent="register",
                    terms_accepted=False,
                    marketing_opt_in=False,
                    db=db,
                )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_get_registration_flow_returns_email_sent_state(self) -> None:
        flow = SimpleNamespace(
            source="email_magic_link",
            intent="register",
            email="user@example.com",
            email_verified_at=None,
            provider=None,
            provider_login=None,
            terms_accepted_at=utcnow(),
            marketing_opt_in=False,
        )

        with patch("app.routes.auth_registration._get_flow_or_raise", AsyncMock(return_value=flow)):
            response = await auth_registration.get_registration_flow(
                flow_token="flow-token",
                db=AsyncMock(),
            )

        self.assertEqual(response.step, "email_sent")
        self.assertEqual(response.email, "user@example.com")
        self.assertFalse(response.email_verified)

    async def test_complete_registration_rejects_unverified_email(self) -> None:
        flow = SimpleNamespace(
            email="user@example.com",
            email_verified_at=None,
        )
        payload = RegistrationCompleteRequest(
            flow_token="flow-token",
            username="cyberhero",
            password="Strong!92",
            profession_tags=["Студент"],
            grade="Junior",
            interest_tags=["Веб"],
        )

        with patch("app.routes.auth_registration._get_flow_or_raise", AsyncMock(return_value=flow)):
            with self.assertRaises(HTTPException) as ctx:
                await auth_registration.complete_registration(
                    payload=payload,
                    request=build_request(),
                    response=Response(),
                    db=AsyncMock(),
                )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_complete_registration_allows_yandex_without_password(self) -> None:
        now = utcnow()
        flow = SimpleNamespace(
            email="oauth@example.com",
            email_verified_at=now,
            source="yandex",
            provider_avatar_url="https://avatars.yandex.net/avatar.png",
            provider_user_id="ya-1",
            provider_email="oauth@example.com",
            provider_login="yanhero",
            provider_raw_profile_json={"id": "ya-1"},
            terms_accepted_at=now,
            marketing_opt_in=True,
            marketing_opt_in_at=now,
        )
        response = Response()
        created_objects = []

        def add_side_effect(obj):
            created_objects.append(obj)

        async def flush_side_effect():
            for obj in created_objects:
                if getattr(obj, "email", None) == "oauth@example.com" and getattr(obj, "id", None) is None:
                    obj.id = 77

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: None),  # existing user by email
                SimpleNamespace(scalar_one_or_none=lambda: None),  # existing username
            ]),
            add=MagicMock(side_effect=add_side_effect),
            flush=AsyncMock(side_effect=flush_side_effect),
        )

        payload = RegistrationCompleteRequest(
            flow_token="flow-token",
            username="cyberhero",
            password=None,
            profession_tags=["Разработчик"],
            grade="Middle",
            interest_tags=["OSINT"],
        )

        with patch("app.routes.auth_registration._get_flow_or_raise", AsyncMock(return_value=flow)), patch(
            "app.routes.auth_registration.hash_password",
            return_value="hashed-oauth-secret",
        ), patch(
            "app.routes.auth_registration.generate_opaque_token",
            return_value="opaque-secret",
        ), patch(
            "app.routes.auth_registration.ensure_questionnaire_payload",
            return_value=(["Разработчик"], "Middle", ["OSINT"]),
        ), patch(
            "app.routes.auth_registration.issue_login_session",
            AsyncMock(return_value=("refresh", "access", now, now + timedelta(hours=1))),
        ), patch("app.routes.auth_registration.set_refresh_cookie"):
            result = await auth_registration.complete_registration(
                payload=payload,
                request=build_request(),
                response=response,
                db=db,
            )

        self.assertEqual(result.access_token, "access")

    async def test_start_yandex_oauth_redirects_to_provider(self) -> None:
        request = build_request()
        db = SimpleNamespace(add=MagicMock(), commit=AsyncMock())
        fake_response = "https://oauth.yandex.ru/authorize?client_id=client"

        with patch.object(auth_registration.settings, "YANDEX_CLIENT_ID", "client"), patch.object(
            auth_registration.settings,
            "YANDEX_CLIENT_SECRET",
            "secret",
        ), patch("app.routes.auth_registration.generate_opaque_token", return_value="opaque-state"), patch(
            "app.routes.auth_registration.generate_pkce_pair",
            return_value=("verifier", "challenge"),
        ), patch(
            "app.routes.auth_registration.build_yandex_authorize_url",
            return_value=fake_response,
        ):
            response = await auth_registration.start_yandex_oauth(
                request=request,
                intent="register",
                terms_accepted=True,
                marketing_opt_in=True,
                db=db,
            )

        self.assertEqual(response.headers["location"], fake_response)
        db.add.assert_called_once()
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
