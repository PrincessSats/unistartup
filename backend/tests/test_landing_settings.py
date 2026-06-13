import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from env_fixtures import apply_test_env_defaults

apply_test_env_defaults()

from app.routes import landing as landing_routes  # noqa: E402
from app.routes import pages as pages_routes  # noqa: E402


def make_settings(**overrides):
    base = dict(
        id=1,
        is_visible=True,
        hunt_enabled=True,
        reward_points=10,
        hero_eyebrow=None,
        hero_title=None,
        hero_subtitle=None,
        updated_at=None,
        updated_by_user_id=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class PublicLandingSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_settings_maps_fields(self) -> None:
        db = SimpleNamespace(commit=AsyncMock())
        settings = make_settings(hunt_enabled=False, hero_title="Custom", reward_points=42)

        with patch.object(landing_routes, "get_or_create_settings", AsyncMock(return_value=settings)):
            result = await landing_routes.get_landing_settings(db=db)

        self.assertTrue(result.is_visible)
        self.assertFalse(result.hunt_enabled)
        self.assertEqual(result.hero_title, "Custom")
        # reward_points must NOT leak to the public payload
        self.assertFalse(hasattr(result, "reward_points"))
        db.commit.assert_awaited_once()


class AdminLandingUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_applies_fields_and_attribution(self) -> None:
        settings = make_settings()
        db = SimpleNamespace(commit=AsyncMock())
        user = SimpleNamespace(id=7)
        current = (user, SimpleNamespace(role="admin"))

        payload = pages_routes.LandingSettingsUpdate(
            is_visible=False,
            hunt_enabled=False,
            reward_points=25,
            hero_title="  Hello  ",
            hero_eyebrow="",
        )

        with patch.object(pages_routes, "get_or_create_settings", AsyncMock(return_value=settings)), patch.object(
            pages_routes, "get_admin_landing", AsyncMock(return_value="ok")
        ):
            result = await pages_routes.update_admin_landing(
                payload=payload, current_user_data=current, db=db
            )

        self.assertEqual(result, "ok")
        self.assertFalse(settings.is_visible)
        self.assertFalse(settings.hunt_enabled)
        self.assertEqual(settings.reward_points, 25)
        self.assertEqual(settings.hero_title, "Hello")  # trimmed
        self.assertIsNone(settings.hero_eyebrow)  # empty string -> None
        self.assertEqual(settings.updated_by_user_id, 7)
        db.commit.assert_awaited_once()

    async def test_update_ignores_unset_fields(self) -> None:
        settings = make_settings(reward_points=10, is_visible=True)
        db = SimpleNamespace(commit=AsyncMock())
        current = (SimpleNamespace(id=1), SimpleNamespace(role="admin"))

        payload = pages_routes.LandingSettingsUpdate(reward_points=99)

        with patch.object(pages_routes, "get_or_create_settings", AsyncMock(return_value=settings)), patch.object(
            pages_routes, "get_admin_landing", AsyncMock(return_value="ok")
        ):
            await pages_routes.update_admin_landing(
                payload=payload, current_user_data=current, db=db
            )

        self.assertEqual(settings.reward_points, 99)
        self.assertTrue(settings.is_visible)  # untouched


if __name__ == "__main__":
    unittest.main()
