import unittest

from app.services.landing_hunt import (
    LANDING_HUNT_BUG_KEYS,
    apply_found_bug,
    create_promo_code,
    is_promo_code_format,
    ordered_found_bug_keys,
)


class LandingHuntServiceTests(unittest.TestCase):
    def test_ordered_found_bug_keys_filters_unknown_items(self) -> None:
        ordered = ordered_found_bug_keys(["unknown", LANDING_HUNT_BUG_KEYS[2], LANDING_HUNT_BUG_KEYS[0]])
        self.assertEqual(ordered, [LANDING_HUNT_BUG_KEYS[0], LANDING_HUNT_BUG_KEYS[2]])

    def test_apply_found_bug_is_idempotent_for_duplicates(self) -> None:
        initial = [LANDING_HUNT_BUG_KEYS[0], LANDING_HUNT_BUG_KEYS[1]]
        updated, added, just_completed = apply_found_bug(initial, LANDING_HUNT_BUG_KEYS[1])
        self.assertEqual(updated, initial)
        self.assertFalse(added)
        self.assertFalse(just_completed)

    def test_apply_found_bug_marks_completion_only_once(self) -> None:
        current = list(LANDING_HUNT_BUG_KEYS[:-1])
        updated, added, just_completed = apply_found_bug(current, LANDING_HUNT_BUG_KEYS[-1])
        self.assertEqual(updated, list(LANDING_HUNT_BUG_KEYS))
        self.assertTrue(added)
        self.assertTrue(just_completed)

        updated_again, added_again, just_completed_again = apply_found_bug(updated, LANDING_HUNT_BUG_KEYS[-1])
        self.assertEqual(updated_again, list(LANDING_HUNT_BUG_KEYS))
        self.assertFalse(added_again)
        self.assertFalse(just_completed_again)

    def test_create_promo_code_uses_expected_format(self) -> None:
        code = create_promo_code()
        self.assertEqual(len(code), 5)
        self.assertTrue(is_promo_code_format(code))


if __name__ == "__main__":
    unittest.main()
