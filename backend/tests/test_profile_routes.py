import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from env_fixtures import apply_test_env_defaults

apply_test_env_defaults()

from fastapi import HTTPException, Response  # noqa: E402

from app.routes import profile as profile_routes  # noqa: E402


def scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


class ProfileRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_account_rejects_when_username_does_not_match(self) -> None:
        db = SimpleNamespace(
            execute=AsyncMock(return_value=scalar_result(SimpleNamespace(username="cyberhero", avatar_url=None))),
            commit=AsyncMock(),
        )

        with self.assertRaises(HTTPException) as ctx:
            await profile_routes.delete_account(
                data=profile_routes.DeleteAccountRequest(username="wrong-user"),
                response=Response(),
                current_user_data=(SimpleNamespace(id=7), SimpleNamespace(username="cyberhero")),
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Никнейм не совпадает")
        db.commit.assert_not_awaited()

    async def test_delete_account_removes_user_and_clears_cookie(self) -> None:
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    scalar_result(
                        SimpleNamespace(username="cyberhero", avatar_url="https://cdn.example/avatar.jpg")
                    ),
                    SimpleNamespace(),
                    SimpleNamespace(),
                    SimpleNamespace(),
                    SimpleNamespace(),
                ]
            ),
            commit=AsyncMock(),
        )
        response = Response()

        with patch("app.routes.profile.clear_refresh_cookie") as clear_refresh_cookie, patch(
            "app.routes.profile.delete_avatar",
            AsyncMock(return_value=True),
        ) as delete_avatar:
            result = await profile_routes.delete_account(
                data=profile_routes.DeleteAccountRequest(username=" cyberhero "),
                response=response,
                current_user_data=(SimpleNamespace(id=7), SimpleNamespace(username="cyberhero")),
                db=db,
            )

        self.assertEqual(result.message, "Аккаунт удалён")
        self.assertEqual(db.execute.await_count, 5)
        db.commit.assert_awaited_once()
        clear_refresh_cookie.assert_called_once_with(response)
        delete_avatar.assert_awaited_once_with("https://cdn.example/avatar.jpg")


if __name__ == "__main__":
    unittest.main()
