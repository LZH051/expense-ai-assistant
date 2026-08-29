"""网站内的 AI 消费分析。

上下文控制：prompt 只携带聚合统计（类别汇总、近 6 个月合计、
预算对账状态），绝不塞原始流水——输入大小与流水条数无关，
成本与上下文都有上界。

健壮性沿用 ai_analysis 的同一套实现：超时、指数退避重试、
usage 记录（Vercel 只读文件系统下自动放弃落盘，只记日志）。
"""

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

import web_services as services
from ai_analysis import call_with_retry, load_ai_config, record_usage
from web_models import WebAiAnalysis, WebUser

logger = logging.getLogger(__name__)


def build_stats(database: Session, user_id: int, today: date) -> dict:
    categories = services.category_summary(database, user_id)
    monthly = services.monthly_summary(database, user_id, months=6)
    status = services.budget_status(database, user_id, today)
    return {
        "month": status["month_key"],
        "month_total": services.money(status["month_total"]),
        "budget_total": services.money(status["budget_total"]),
        "budget_exceeded": status["budget_exceeded"],
        "category_overruns": [
            {
                "category": item["category"],
                "budget": services.money(item["budget"]),
                "spent": services.money(item["spent"]),
            }
            for item in status["category_overruns"]
        ],
        "category_summary": [
            {"category": row.category, "total": services.money(row.total)}
            for row in categories
        ],
        "recent_months": [
            {"month": row["month"], "total": services.money(row["total"])}
            for row in monthly
        ],
    }


def build_prompt(stats: dict) -> str:
    return f"""你是一名理性的个人消费分析助手。

下面是一位用户经过聚合的消费统计数据（金额单位：元）：
{json.dumps(stats, ensure_ascii=False, indent=1)}

请概括本月消费结构，指出超支或异常的类别，结合近几个月趋势
给出两到三条具体可执行的建议。使用中文，控制在200字以内，
只根据给出的数据分析，不要虚构数字。
"""


def generate_insight(
    database: Session,
    user: WebUser,
    today: date | None = None,
    client_factory=None,
    retry_base_delay: float = 2.0,
) -> WebAiAnalysis:
    """生成（或覆盖更新）用户当月的 AI 分析。

    配置缺失或调用失败会抛异常，由路由层转为页面提示。
    """
    today = today or date.today()
    if client_factory is None:
        config = load_ai_config()
        model = config["AI_MODEL"]
        from openai import OpenAI

        def client_factory():
            return OpenAI(
                api_key=config["AI_API_KEY"],
                base_url=config["AI_BASE_URL"],
                timeout=30.0,
                max_retries=0,
            )
    else:
        model = "stub-model"

    stats = build_stats(database, user.id, today)
    client = client_factory()
    response = call_with_retry(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你只根据用户提供的数据进行分析。"},
                {"role": "user", "content": build_prompt(stats)},
            ],
            temperature=0.3,
        ),
        retry_base_delay=retry_base_delay,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("模型返回了空内容。")
    if getattr(response, "usage", None) is not None:
        record_usage(model, response.usage)

    month = today.strftime("%Y-%m")
    analysis = database.scalar(
        select(WebAiAnalysis).where(
            WebAiAnalysis.user_id == user.id,
            WebAiAnalysis.month == month,
        )
    )
    if analysis is None:
        analysis = WebAiAnalysis(user_id=user.id, month=month)
        database.add(analysis)
    analysis.content = content
    analysis.model_name = model
    database.commit()
    database.refresh(analysis)
    logger.info("AI 分析已生成 user=%s month=%s", user.id, month)
    return analysis


def list_insights(
    database: Session, user_id: int, limit: int = 6
) -> list[WebAiAnalysis]:
    return database.scalars(
        select(WebAiAnalysis)
        .where(WebAiAnalysis.user_id == user_id)
        .order_by(WebAiAnalysis.month.desc())
        .limit(limit)
    ).all()


def ai_configured() -> bool:
    try:
        load_ai_config()
        return True
    except RuntimeError:
        return False
