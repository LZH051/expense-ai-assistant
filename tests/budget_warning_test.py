import os
import re
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "budget-warning-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import app  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def main() -> None:
    with TestClient(app) as client:
        register_page = client.get("/register")
        response = client.post(
            "/register",
            data={
                "username": "Warning Tester",
                "email": "budget-warning@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "csrf_token": csrf_from(register_page.text),
            },
        )
        assert response.status_code == 200

        budget_page = client.get("/budgets")
        budget_response = client.post(
            "/budgets",
            data={
                "budget_month": date.today().strftime("%Y-%m"),
                "category": "全部类别",
                "amount": "100.00",
                "csrf_token": csrf_from(budget_page.text),
            },
            follow_redirects=False,
        )
        assert budget_response.status_code == 303

        expense_page = client.get("/expenses/new")
        expense_response = client.post(
            "/expenses/new",
            data={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "150.00",
                "merchant": "Test Merchant",
                "description": "Budget warning test",
                "csrf_token": csrf_from(expense_page.text),
            },
            follow_redirects=False,
        )
        assert expense_response.status_code == 303

        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200
        assert "本月预算已超出" in dashboard.text
        assert "已超出 ¥ 50.00" in dashboard.text

    print("BUDGET_WARNING=PASS")
    print("EXPECTED_OVERAGE=50.00")


if __name__ == "__main__":
    main()
