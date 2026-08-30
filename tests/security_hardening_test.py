"""安全加固测试。

1. 登录失败限流：同一邮箱 15 分钟内失败 5 次后拒绝（429）；
2. 日期范围校验：不再接受公元 1 年 / 遥远未来的消费日期；
3. 预算月份校验：非法月份给中文提示，而不是英文异常原文；
4. CSRF 失败：返回 303 + flash 提示，而不是裸 JSON；
5. 安全响应头：CSP 存在；登录态页面 Cache-Control: no-store；
6. 未登录提交表单：跳转登录页并有提示。
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "security-hardening-test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from web_app import app  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def register(client: TestClient, email: str) -> None:
    page = client.get("/register")
    response = client.post(
        "/register",
        data={
            "username": "Security Tester",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 200


def test_login_rate_limit() -> None:
    email = "rate-limit@example.com"
    with TestClient(app) as client:
        register(client, email)
    with TestClient(app) as client:
        for attempt in range(5):
            page = client.get("/login")
            response = client.post(
                "/login",
                data={
                    "email": email,
                    "password": "WrongPassword!",
                    "csrf_token": csrf_from(page.text),
                },
            )
            assert response.status_code == 401, (attempt, response.status_code)
        page = client.get("/login")
        blocked = client.post(
            "/login",
            data={
                "email": email,
                "password": "SecurePass123!",   # 即使密码正确也应被拦
                "csrf_token": csrf_from(page.text),
            },
        )
        assert blocked.status_code == 429, blocked.status_code
        assert "尝试次数过多" in blocked.text


def test_date_and_month_validation() -> None:
    with TestClient(app) as client:
        register(client, "validation@example.com")
        page = client.get("/expenses/new")
        for bad_date in ("0001-01-01", "3000-01-01"):
            response = client.post(
                "/expenses/new",
                data={
                    "expense_date": bad_date,
                    "category": "餐饮",
                    "amount": "10.00",
                    "merchant": "",
                    "description": "",
                    "csrf_token": csrf_from(page.text),
                },
            )
            assert response.status_code == 422, (bad_date, response.status_code)

        budgets_page = client.get("/budgets")
        response = client.post(
            "/budgets",
            data={
                "budget_month": "2026-13",
                "category": "餐饮",
                "amount": "100.00",
                "csrf_token": csrf_from(budgets_page.text),
            },
            follow_redirects=True,
        )
        assert "预算月份" in response.text, "应给出中文的月份格式提示"
        assert "month must be" not in response.text


def test_csrf_failure_is_friendly() -> None:
    with TestClient(app) as client:
        register(client, "csrf-friendly@example.com")
        response = client.post(
            "/expenses/new",
            data={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "10.00",
                "csrf_token": "wrong-token",
            },
            headers={"referer": "http://testserver/expenses/new"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.status_code
        follow = client.get(response.headers["location"])
        assert "请求已失效" in follow.text


def test_security_headers() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        assert "content-security-policy" in home.headers
        assert "default-src 'self'" in home.headers["content-security-policy"]
        register(client, "headers@example.com")
        dashboard = client.get("/dashboard")
        assert dashboard.headers.get("cache-control") == "no-store"


def test_anonymous_post_redirects_with_message() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/expenses/new",
            data={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "10.00",
                "csrf_token": "irrelevant",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        login_page = client.get("/login")
        assert "请先登录" in login_page.text


def main() -> None:
    test_login_rate_limit()
    test_date_and_month_validation()
    test_csrf_failure_is_friendly()
    test_security_headers()
    test_anonymous_post_redirects_with_message()
    print("SECURITY_HARDENING_TEST=PASS")


if __name__ == "__main__":
    main()
