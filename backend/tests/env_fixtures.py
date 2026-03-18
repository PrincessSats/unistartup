import os


def build_fixture_value(*parts: str) -> str:
    return "-".join(str(part).strip() for part in parts if str(part).strip())


TEST_DB_HOST = "localhost"
TEST_DB_PORT = "5432"
TEST_DB_NAME = build_fixture_value("unit", "db", "catalog")
TEST_DB_USER = build_fixture_value("unit", "db", "principal")
TEST_DB_CREDENTIAL = build_fixture_value("unit", "db", "auth", "material")
TEST_SIGNING_MATERIAL = build_fixture_value("unit", "app", "signing", "material")


def apply_test_env_defaults() -> None:
    defaults = {
        "DB_HOST": TEST_DB_HOST,
        "DB_PORT": TEST_DB_PORT,
        "DB_NAME": TEST_DB_NAME,
        "DB_USER": TEST_DB_USER,
        "DB_PASSWORD": TEST_DB_CREDENTIAL,
        "SECRET_KEY": TEST_SIGNING_MATERIAL,
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
