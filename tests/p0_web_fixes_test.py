"""Web 层 P0 复现测试。

1. amount=nan 不允许打出 500（Decimal('nan') 能通过 quantize，
   但比较运算会抛 InvalidOperation）；
2. 预算对账语义：没有"全部类别"预算时，分类预算之和不得被当作
   总预算触发误报；分类超支必须逐类别提示；"全部类别=0"是合法
   语义（一分不花），超支时必须告警；
3. 404 页面（如浏览器自动请求 /favicon.ico）不得吞掉排队中的
   flash 消息。
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
os.environ.setdefault("SESSION_SECRET", "p0-web-fixes-test-secret")

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
            "username": "P0 Tester",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 200


def add_expense(client: TestClient, category: str, amount: str) -> None:
    page = client.get("/expenses/new")
    response = client.post(
        "/expenses/new",
        data={
            "expense_date": date.today().isoformat(),
            "category": category,
            "amount": amount,
            "merchant": "",
            "description": "",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def set_budget(client: TestClient, category: str, amount: str) -> None:
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


def test_nan_amount_rejected(user_client) -> None:
    client = user_client
    page = client.get("/expenses/new")
    for bad in ("nan", "NaN", "-nan", "inf", "1e5", "1_0"):
        response = client.post(
            "/expenses/new",
            data={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": bad,
                "merchant": "",
                "description": "",
                "csrf_token": csrf_from(page.text),
            },
        )
        assert response.status_code == 422, (
            f"amount={bad!r} 应返回 422 校验失败，实际 {response.status_code}"
        )
        assert "有效金额" in response.text


def test_budget_semantics(user_client) -> None:
    client = user_client
    # 场景1：只有分类预算（餐饮300），其他类别消费300 → 不得误报总预算超支
    set_budget(client, "餐饮", "300.00")
    add_expense(client, "餐饮", "200.00")
    add_expense(client, "交通", "300.00")
    dashboard = client.get("/dashboard")
    assert "本月预算已超出" not in dashboard.text, (
        "分类预算之和不是总预算，不应触发总超支告警"
    )

    # 场景2：餐饮实际超支 → 必须有逐类别提示
    add_expense(client, "餐饮", "200.00")   # 餐饮共400 > 300
    dashboard = client.get("/dashboard")
    assert "餐饮" in dashboard.text and "超支" in dashboard.text, (
        "分类超支必须逐类别提示"
    )
    assert "本月预算已超出" not in dashboard.text

    # 场景3：全部类别=0 是合法语义，超支必须告警
    set_budget(client, "全部类别", "0.00")
    dashboard = client.get("/dashboard")
    assert "本月预算已超出" in dashboard.text, (
        "全部类别预算为0时，任何消费都应触发总超支告警"
    )


def test_flash_survives_404(user_client) -> None:
    client = user_client
    add_expense(client, "购物", "10.00")   # 设置 flash 后跳转
    missing = client.get("/favicon.ico")   # 浏览器自动请求，命中 404 页
    assert missing.status_code == 404
    expenses = client.get("/expenses")
    assert "消费记录已保存" in expenses.text, (
        "flash 消息被 404 页面吞掉了"
    )


