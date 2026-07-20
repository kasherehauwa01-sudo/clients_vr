from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_contains(path: str, needle: str) -> None:
    text = read(path)
    if needle not in text:
        raise AssertionError(f"{path}: не найдено {needle!r}")


def assert_not_contains(path: str, pattern: str) -> None:
    text = read(path)
    if re.search(pattern, text):
        raise AssertionError(f"{path}: найден запрещенный шаблон {pattern!r}")


assert_contains("frontend/vite.config.ts", "base: '/vr/clients/'")
assert_contains("frontend/src/main.tsx", "API_BASE_URL")
assert_not_contains("frontend/src/main.tsx", r"fetch\(['\"]/(api|assets)/")
assert_contains("backend/app/main.py", "PrefixStripMiddleware")
assert_contains("backend/app/main.py", "SpaStaticFiles")
assert_contains("docker-compose.yml", "127.0.0.1:8015:8000")
assert_contains("docker-compose.yml", "/vr/clients/api/health")
assert_not_contains("docker-compose.yml", r"\n\s*nginx:")
assert_contains("nginx/kvasmix-vr-clients.conf", "location /vr/clients/")
assert_contains("Dockerfile", "alembic upgrade head")
assert_contains("backend/app/api/routes.py", '@router.get("/health")')
assert_contains("backend/alembic/versions/20260709_0001_initial_schema.py", "create_type=False")
assert_contains("backend/alembic/versions/20260710_0002_add_out_of_stock_status.py", "ADD VALUE IF NOT EXISTS")
print("deployment smoke check passed")
