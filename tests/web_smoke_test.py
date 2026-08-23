import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "web-smoke-test-secret-not-for-production")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from web_app import app  # noqa: E402
from web_database import SessionLocal  # noqa: E402
from web_models import WebBudget, WebExpense, WebUser  # noqa: E402


CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf_from(response) -> str:
    match = CSRF_PATTERN.search(response.text)
    assert match, "页面中没有CSRF令牌"
    return match.group(1)


def register(client: TestClient, username: str, email: str) -> None:
    page = client.get("/register")
    assert page.status_code == 200
    response = client.post(
        "/register",
        data={
            "username": username,
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf_token": csrf_from(page),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def main() -> None:
    with TestClient(app) as first_client, TestClient(app) as second_client:
        register(first_client, "Alice", "alice@example.com")

        dashboard = first_client.get("/dashboard")
        assert dashboard.status_code == 200
        assert "Alice" in dashboard.text

        new_page = first_client.get("/expenses/new")
        create_response = first_client.post(
            "/expenses/new",
            data={
                "expense_date": "2026-08-23",
                "category": "餐饮",
                "amount": "12.50",
                "merchant": "Old Merchant",
                "description": "Old description",
                "csrf_token": csrf_from(new_page),
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303

        with SessionLocal() as database:
            alice = database.scalar(
                select(WebUser).where(WebUser.email == "alice@example.com")
            )
            expense = database.scalar(
                select(WebExpense).where(WebExpense.user_id == alice.id)
            )
            expense_id = expense.id

        edit_page = first_client.get(f"/expenses/{expense_id}/edit")
        update_response = first_client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "expense_date": "2026-08-24",
                "category": "交通",
                "amount": "30.75",
                "merchant": "New Merchant",
                "description": "New description",
                "csrf_token": csrf_from(edit_page),
            },
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        budget_page = first_client.get("/budgets")
        budget_response = first_client.post(
            "/budgets",
            data={
                "budget_month": "2026-08",
                "category": "交通",
                "amount": "500.00",
                "csrf_token": csrf_from(budget_page),
            },
            follow_redirects=False,
        )
        assert budget_response.status_code == 303

        register(second_client, "Bob", "bob@example.com")
        forbidden_record = second_client.get(f"/expenses/{expense_id}/edit")
        assert forbidden_record.status_code == 404

        with SessionLocal() as database:
            expense = database.get(WebExpense, expense_id)
            assert expense.category == "交通"
            assert str(expense.amount) == "30.75"
            assert expense.merchant == "New Merchant"
            assert database.scalar(select(func.count(WebBudget.id))) == 1

        expenses_page = first_client.get("/expenses")
        delete_response = first_client.post(
            f"/expenses/{expense_id}/delete",
            data={"csrf_token": csrf_from(expenses_page)},
            follow_redirects=False,
        )
        assert delete_response.status_code == 303

        account_page = first_client.get("/account")
        delete_account_response = first_client.post(
            "/account/delete",
            data={
                "password": "SecurePass123!",
                "confirmation": "DELETE",
                "csrf_token": csrf_from(account_page),
            },
            follow_redirects=False,
        )
        assert delete_account_response.status_code == 303

        with SessionLocal() as database:
            assert database.scalar(
                select(WebUser).where(WebUser.email == "alice@example.com")
            ) is None
            assert database.scalar(select(func.count(WebBudget.id))) == 0
            assert database.scalar(select(func.count(WebUser.id))) == 1

    print("WEB_SMOKE_TEST=PASS")
    print("REGISTER_LOGIN=PASS")
    print("EXPENSE_CREATE_UPDATE_DELETE=PASS")
    print("BUDGET_CREATE_AND_CASCADE_DELETE=PASS")
    print("CROSS_USER_ISOLATION=PASS")


if __name__ == "__main__":
    main()
