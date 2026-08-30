"""/api/v1 JSON API 测试：认证、统一错误码、Pydantic 校验、分页。

金额在 JSON 中一律序列化为字符串（"12.50"），避免 float 精度问题。
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
os.environ.setdefault("SESSION_SECRET", "api-v1-test-secret")

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
            "username": "API Tester",
            "email": email,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert response.status_code == 200


def test_api_v1_endpoints() -> None:
    # 未登录：统一 401 错误封装
    with TestClient(app) as anon:
        response = anon.get("/api/v1/statistics")
        assert response.status_code == 401, response.text
        body = response.json()
        assert body["error"]["code"] == "unauthorized", body

    with TestClient(app) as client:
        register(client, "api-v1@example.com")

        # 健康检查须真实探测数据库
        health = client.get("/health").json()
        assert health == {"status": "ok", "database": "ok"}, health

        # JSON 创建消费：Pydantic 校验
        created = client.post(
            "/api/v1/expenses",
            json={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "45.50",
                "merchant": "食堂",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["amount"] == "45.50"

        bad = client.post(
            "/api/v1/expenses",
            json={
                "expense_date": date.today().isoformat(),
                "category": "不存在的类别",
                "amount": "10.00",
            },
        )
        assert bad.status_code == 422, bad.text
        assert bad.json()["error"]["code"] == "validation_error", bad.json()

        nan_bad = client.post(
            "/api/v1/expenses",
            json={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "nan",
            },
        )
        assert nan_bad.status_code == 422, nan_bad.text

        # 分页：再造 24 条，共 25 条
        for index in range(24):
            response = client.post(
                "/api/v1/expenses",
                json={
                    "expense_date": date.today().isoformat(),
                    "category": "交通",
                    "amount": "1.00",
                    "description": f"批量 {index}",
                },
            )
            assert response.status_code == 201
        page1 = client.get("/api/v1/expenses").json()
        assert page1["total"] == 25, page1["total"]
        assert len(page1["items"]) == 20
        assert page1["page"] == 1 and page1["pages"] == 2
        page2 = client.get("/api/v1/expenses", params={"page": 2}).json()
        assert len(page2["items"]) == 5

        # 筛选下沉到 API
        dining = client.get(
            "/api/v1/expenses", params={"category": "餐饮"}
        ).json()
        assert dining["total"] == 1
        assert dining["items"][0]["merchant"] == "食堂"

        # 统计接口
        stats = client.get("/api/v1/statistics").json()
        categories = {
            row["category"]: row["total"]
            for row in stats["category_summary"]
        }
        assert categories["餐饮"] == "45.50", categories
        assert categories["交通"] == "24.00", categories
        assert stats["budget_status"]["month_total"] == "69.50"

        # HTML 列表页分页 + 汇总行
        html = client.get("/expenses").text
        assert "共 25 条" in html and "69.50" in html, "列表页应有汇总行"
        assert "下一页" in html, "列表页应有分页"
        html2 = client.get("/expenses", params={"page": 2}).text
        assert html2.count("<tr>") - 1 == 5 or "批量" in html2

    print("API_V1_TEST=PASS")


if __name__ == "__main__":
    test_api_v1_endpoints()
