import os
import re
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "overall-budget-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import app  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def post_budget(client: TestClient, category: str, amount: str) -> None:
    page = client.get("/budgets")
    response = client.post(
        "/budgets",
        data={
            "budget_month": date.today().strftime("%Y-%m"),
            "category": category,
            "amount": amount,
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_overall_budget_precedence() -> None:
    with TestClient(app) as client:
        register_page = client.get("/register")
        response = client.post(
            "/register",
            data={
                "username": "Budget Tester",
                "email": "overall-budget@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "csrf_token": csrf_from(register_page.text),
            },
        )
        assert response.status_code == 200

        budget_page = client.get("/budgets")
        assert 'value="全部类别"' in budget_page.text

        post_budget(client, "餐饮", "300.00")
        post_budget(client, "全部类别", "1000.00")

        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200
        assert "¥ 1000.00" in dashboard.text
        assert "¥ 1300.00" not in dashboard.text

    print("OVERALL_BUDGET_OPTION=PASS")
    print("OVERALL_BUDGET_PRECEDENCE=PASS")


if __name__ == "__main__":
    test_overall_budget_precedence()
