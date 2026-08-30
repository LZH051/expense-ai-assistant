import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "filter-test-secret-not-for-production")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import EXPENSE_CATEGORIES, app  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def test_filter_categories_render() -> None:
    with TestClient(app) as client:
        register_page = client.get("/register")
        response = client.post(
            "/register",
            data={
                "username": "Category Tester",
                "email": "category-test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "csrf_token": csrf_from(register_page.text),
            },
        )
        assert response.status_code == 200

        expenses_page = client.get("/expenses")
        assert expenses_page.status_code == 200
        for category in EXPENSE_CATEGORIES:
            assert f'value="{category}"' in expenses_page.text

    print("EMPTY_ACCOUNT_FILTER_CATEGORIES=PASS")
    print("CATEGORIES=" + ",".join(EXPENSE_CATEGORIES))


if __name__ == "__main__":
    test_filter_categories_render()
