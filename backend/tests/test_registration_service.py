import unittest
from datetime import timedelta
import hashlib
import hmac

from env_fixtures import apply_test_env_defaults

apply_test_env_defaults()

from app.services.registration import (  # noqa: E402
    INTEREST_OPTIONS,
    PROFESSION_OPTIONS,
    build_github_authorize_url,
    build_magic_link_callback_url,
    build_registration_flow_token,
    build_yandex_authorize_url,
    decode_registration_flow_token,
    ensure_questionnaire_payload,
    generate_pkce_pair,
    resolve_backend_yandex_callback_url,
    utcnow,
    validate_registration_password,
    verify_telegram_auth,
)


class RegistrationServiceTests(unittest.TestCase):
    def test_pkce_pair_has_expected_shape(self) -> None:
        verifier, challenge = generate_pkce_pair()
        self.assertGreaterEqual(len(verifier), 40)
        self.assertGreaterEqual(len(challenge), 40)
        self.assertNotIn("=", challenge)

    def test_registration_flow_token_round_trip(self) -> None:
        token = build_registration_flow_token(42, expires_at=utcnow() + timedelta(minutes=5))
        self.assertEqual(decode_registration_flow_token(token), 42)

    def test_build_yandex_authorize_url_includes_state_and_pkce(self) -> None:
        url = build_yandex_authorize_url(
            client_id="client-id",
            redirect_uri="http://127.0.0.1:8000/api/auth/yandex/callback",
            scope="login:email login:info",
            state="opaque-state",
            code_challenge="challenge",
        )
        self.assertIn("client_id=client-id", url)
        self.assertIn("state=opaque-state", url)
        self.assertIn("code_challenge=challenge", url)
        self.assertIn("code_challenge_method=S256", url)

    def test_build_github_authorize_url_includes_state_and_scope(self) -> None:
        url = build_github_authorize_url(
            client_id="gh-client-id",
            redirect_uri="https://api.example.com/api/auth/github/callback",
            scope="read:user user:email",
            state="opaque-state",
        )
        self.assertIn("client_id=gh-client-id", url)
        self.assertIn("state=opaque-state", url)
        self.assertIn("scope=read%3Auser+user%3Aemail", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fapi.example.com%2Fapi%2Fauth%2Fgithub%2Fcallback", url)

    def test_verify_telegram_auth_accepts_valid_signature(self) -> None:
        bot_token = "telegram-bot-token"
        auth_date = int(utcnow().timestamp())
        base_payload = {
            "id": "123456",
            "first_name": "Hack",
            "last_name": "Net",
            "username": "hacknet_user",
            "photo_url": "https://t.me/i/userpic/320/demo.jpg",
            "auth_date": auth_date,
        }
        data_check_string = "\n".join(
            f"{key}={base_payload[key]}"
            for key in sorted(base_payload.keys())
        )
        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        signed_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        profile = verify_telegram_auth(
            telegram_user={**base_payload, "hash": signed_hash},
            bot_token=bot_token,
            max_age_seconds=86400,
        )

        self.assertEqual(profile.provider_user_id, "123456")
        self.assertEqual(profile.login, "hacknet_user")
        self.assertEqual(profile.avatar_url, "https://t.me/i/userpic/320/demo.jpg")

    def test_verify_telegram_auth_rejects_invalid_signature(self) -> None:
        with self.assertRaises(ValueError):
            verify_telegram_auth(
                telegram_user={
                    "id": "123456",
                    "first_name": "Hack",
                    "auth_date": int(utcnow().timestamp()),
                    "hash": "deadbeef",
                },
                bot_token="telegram-bot-token",
                max_age_seconds=86400,
            )

    def test_magic_link_callback_uses_registration_path(self) -> None:
        callback_url = build_magic_link_callback_url(
            request_scheme="http",
            request_host="127.0.0.1:3000",
            token="magic-token",
        )
        self.assertIn("/api/auth/registration/email/callback", callback_url)
        self.assertIn("token=magic-token", callback_url)

    def test_prod_callback_uses_runtime_api_host(self) -> None:
        callback_url = resolve_backend_yandex_callback_url(
            request_scheme="https",
            request_host="api.example.com",
        )
        self.assertEqual(callback_url, "https://api.example.com/api/auth/yandex/callback")

    def test_local_callback_keeps_registered_loopback_host(self) -> None:
        callback_url = resolve_backend_yandex_callback_url(
            request_scheme="http",
            request_host="localhost:8000",
        )
        self.assertEqual(callback_url, "http://127.0.0.1:8000/api/auth/yandex/callback")

    def test_validate_registration_password_blocks_personal_info_and_sequences(self) -> None:
        weak_candidate = "".join(["User", "1234", "!"])
        issues = validate_registration_password(
            weak_candidate,
            username="User",
            email="user@example.com",
            provider_login="userlogin",
        )
        self.assertTrue(issues)
        self.assertTrue(any("личные данные" in issue.lower() or "последовательности" in issue.lower() for issue in issues))

        strong_candidate = "".join(["Mighty", "!", "9", "2"])
        strong_issues = validate_registration_password(
            strong_candidate,
            username="cyberhero",
            email="hero@example.com",
            provider_login="yanhero",
        )
        self.assertEqual(strong_issues, [])

    def test_questionnaire_payload_normalizes_known_values(self) -> None:
        profession_tags, grade, interest_tags = ensure_questionnaire_payload(
            profession_tags=[PROFESSION_OPTIONS[0], "Неизвестно", PROFESSION_OPTIONS[0]],
            grade="Middle",
            interest_tags=[INTEREST_OPTIONS[1], INTEREST_OPTIONS[1], "bad"],
        )
        self.assertEqual(profession_tags, [PROFESSION_OPTIONS[0]])
        self.assertEqual(grade, "Middle")
        self.assertEqual(interest_tags, [INTEREST_OPTIONS[1]])


if __name__ == "__main__":
    unittest.main()
