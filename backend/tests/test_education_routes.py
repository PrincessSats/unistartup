import os
import unittest

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "app")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "pass")
os.environ.setdefault("SECRET_KEY", "secret")

from app.routes.education import (  # noqa: E402
    _compute_passed_users_count,
    _parse_vpn_info,
    difficulty_label,
    extract_hints,
    task_status,
)


class EducationRouteHelpersTests(unittest.TestCase):
    def test_difficulty_label_boundaries(self) -> None:
        self.assertEqual(difficulty_label(1), "Легко")
        self.assertEqual(difficulty_label(3), "Легко")
        self.assertEqual(difficulty_label(4), "Средне")
        self.assertEqual(difficulty_label(7), "Средне")
        self.assertEqual(difficulty_label(8), "Сложно")
        self.assertEqual(difficulty_label(10), "Сложно")
        self.assertEqual(difficulty_label(99), "Средне")

    def test_task_status_transitions(self) -> None:
        self.assertEqual(task_status(False, {"main"}, set(), False), "not_started")
        self.assertEqual(task_status(True, {"main"}, set(), False), "in_progress")
        self.assertEqual(task_status(True, {"main"}, {"main"}, True), "solved")
        self.assertEqual(task_status(True, set(), set(), True), "solved")

    def test_extract_hints_supports_flat_and_nested_payloads(self) -> None:
        payload = {
            "hints": ["Первая подсказка", "Вторая подсказка"],
            "task": {
                "hint": "Третья подсказка",
                "hints": ["Четвертая подсказка", "Вторая подсказка"],
            },
        }
        self.assertEqual(
            extract_hints(payload),
            ["Первая подсказка", "Вторая подсказка", "Четвертая подсказка", "Третья подсказка"],
        )

    def test_compute_passed_users_count_uses_required_flags(self) -> None:
        required = {"main", "bonus"}
        flags_by_user = {
            1: {"main", "bonus"},
            2: {"main"},
            3: {"main", "bonus", "extra"},
        }
        self.assertEqual(_compute_passed_users_count(required, flags_by_user), 2)
        self.assertEqual(_compute_passed_users_count(set(), flags_by_user), 3)

    def test_parse_vpn_info_uses_task_materials_fields(self) -> None:
        materials = [
            {
                "type": "credentials",
                "name": "How to connect",
                "description": "Подключение к VPN. IP-адрес: 10.10.10.2",
                "url": "https://example.com/how-to-connect",
                "storage_key": None,
            },
            {
                "type": "file",
                "name": "WireGuard config",
                "description": "Разрешенные IP: 10.10.10.0/24; создана 01.11.2025 11:59",
                "url": "https://example.com/download.conf",
                "storage_key": None,
            },
        ]

        vpn = _parse_vpn_info(materials)
        self.assertEqual(vpn.config_ip, "10.10.10.2")
        self.assertEqual(vpn.allowed_ips, "10.10.10.0/24")
        self.assertEqual(vpn.created_at, "01.11.2025 11:59")
        self.assertEqual(vpn.how_to_connect_url, "https://example.com/how-to-connect")
        self.assertEqual(vpn.download_url, "https://example.com/download.conf")


if __name__ == "__main__":
    unittest.main()
