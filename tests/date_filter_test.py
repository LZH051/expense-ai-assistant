import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
TEST_DB_PATH = Path("E:/tmp/expense-date-filter-test.db")
for suffix in ("", "-shm", "-wal"):
    Path(f"{TEST_DB_PATH}{suffix}").unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SESSION_SECRET"] = "date-filter-test-secret"

from fastapi.testclient import TestClient

from src.web_app import app


with TestClient(app) as client:
    register_page = client.get("/register")
    csrf_token = re.search(
        r'name="csrf_token" value="([^"]+)"', register_page.text
    ).group(1)
    client.post(
        "/register",
        data={
            "username": "Date Test",
            "email": "datefilter@example.com",
            "password": "Testpass123",
            "password_confirm": "Testpass123",
            "csrf_token": csrf_token,
        },
    )
    for expense_date, category, merchant in (
        ("2026-08-10", "餐饮", "August Restaurant"),
        ("2026-09-10", "交通", "September Station"),
    ):
        new_page = client.get("/expenses/new")
        expense_token = re.search(
            r'name="csrf_token" value="([^"]+)"', new_page.text
        ).group(1)
        response = client.post(
            "/expenses/new",
            data={
                "expense_date": expense_date,
                "category": category,
                "amount": "25.00",
                "merchant": merchant,
                "description": "Date filter test",
                "csrf_token": expense_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    page = client.get(
        "/expenses?start_date=2026-08-01&end_date=2026-08-31"
    ).text
    assert 'name="start_date"' in page
    assert 'name="end_date"' in page
    assert "2026-08-01" in page
    assert "2026-08-31" in page
    assert "August Restaurant" in page
    assert "September Station" not in page

    combined = client.get(
        "/expenses?category=餐饮&start_date=2026-08-01&end_date=2026-08-31"
    ).text
    assert "August Restaurant" in combined
    assert "September Station" not in combined

    invalid = client.get(
        "/expenses?start_date=2026-09-01&end_date=2026-08-01",
        follow_redirects=True,
    )
    assert "开始日期不能晚于结束日期" in invalid.text

print("DATE_FILTER=PASS")
