"""AI 消费分析（/insights）测试。

- 未配置 AI 环境变量时页面明确提示，生成请求不报 500；
- 注入桩客户端生成分析：入库、页面展示、按月覆盖更新；
- prompt 只携带聚合统计（类别汇总/月度合计/预算状态），
  不塞原始流水，长度有上界。
"""

import os
import re
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("测试必须通过 DATABASE_URL 指向临时数据库。")
os.environ.setdefault("SESSION_SECRET", "insights-test-secret")
for key in ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL"):
    os.environ.pop(key, None)

from fastapi.testclient import TestClient  # noqa: E402

import web_insights  # noqa: E402
from web_app import app  # noqa: E402
from web_database import SessionLocal  # noqa: E402
from web_models import WebUser  # noqa: E402
from sqlalchemy import select  # noqa: E402


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


class StubClient:
    def __init__(self):
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, *, messages, **_kwargs):
        self.prompts.append(messages[-1]["content"])
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="桩分析：本月餐饮偏高。")
            )],
            usage=SimpleNamespace(
                prompt_tokens=200, completion_tokens=100, total_tokens=300
            ),
        )


def main() -> None:
    with TestClient(app) as client:
        page = client.get("/register")
        client.post(
            "/register",
            data={
                "username": "Insight Tester",
                "email": "insights@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "csrf_token": csrf_from(page.text),
            },
        )
        form = client.get("/expenses/new")
        client.post(
            "/expenses/new",
            data={
                "expense_date": date.today().isoformat(),
                "category": "餐饮",
                "amount": "88.00",
                "merchant": "食堂",
                "description": "",
                "csrf_token": csrf_from(form.text),
            },
        )

        # 未配置 AI：页面提示，生成不 500
        insights = client.get("/insights")
        assert insights.status_code == 200
        assert "尚未配置 AI 接口" in insights.text
        generate = client.post(
            "/insights/generate",
            data={
                "confirm_paid": "on",
                "csrf_token": csrf_from(insights.text),
            },
            follow_redirects=True,
        )
        assert generate.status_code == 200
        assert "尚未配置 AI 接口" in generate.text

        # 桩客户端直接走服务层：入库并可在页面看到
        stub = StubClient()
        with SessionLocal() as database:
            user = database.scalar(
                select(WebUser).where(WebUser.email == "insights@example.com")
            )
            analysis = web_insights.generate_insight(
                database, user, client_factory=lambda: stub,
                retry_base_delay=0,
            )
            assert analysis.content == "桩分析：本月餐饮偏高。"

            # prompt 只带聚合统计：不含流水字段'食堂'，含类别与金额
            prompt = stub.prompts[0]
            assert "餐饮" in prompt and "88.00" in prompt, prompt
            assert "食堂" not in prompt, "prompt 不应包含原始流水明细"
            assert len(prompt) < 4000, f"prompt 应有长度上界，实际 {len(prompt)}"

            # 同月重复生成：覆盖更新而不是堆积
            web_insights.generate_insight(
                database, user, client_factory=lambda: stub,
                retry_base_delay=0,
            )
            from web_models import WebAiAnalysis
            rows = database.scalars(select(WebAiAnalysis).where(
                WebAiAnalysis.user_id == user.id
            )).all()
            assert len(rows) == 1, f"同月应覆盖更新，实际 {len(rows)} 行"

        shown = client.get("/insights")
        assert "桩分析：本月餐饮偏高。" in shown.text

    print("INSIGHTS_TEST=PASS")


if __name__ == "__main__":
    main()
