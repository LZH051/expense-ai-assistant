"""Web 层共享业务逻辑：校验、聚合查询、预算对账。

页面路由（web_app）与 JSON API（web_api）共用同一份实现，
保证两个入口算出来的数字永远一致。
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from web_models import WebBudget, WebExpense, WebUser

EXPENSE_CATEGORIES = (
    "餐饮", "交通", "购物", "居住", "娱乐",
    "医疗", "教育", "旅行", "其他",
)
OVERALL_BUDGET_CATEGORY = "全部类别"
BUDGET_CATEGORIES = (OVERALL_BUDGET_CATEGORY, *EXPENSE_CATEGORIES)

AMOUNT_PATTERN = re.compile(r"\d+(\.\d{1,2})?")
MAX_AMOUNT = Decimal("9999999999.99")
DEFAULT_PAGE_SIZE = 20


def parse_amount(value: str) -> Decimal:
    cleaned = value.strip()
    # 先做字面校验：Decimal() 还"认识" nan/inf/1e5/1_0 这类写法，
    # 其中 NaN 能通过 quantize，但一参与比较就抛 InvalidOperation
    if not AMOUNT_PATTERN.fullmatch(cleaned):
        raise ValueError("请输入有效金额：数字，最多两位小数。")
    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
        if amount > MAX_AMOUNT:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError(f"金额必须在 0 至 {MAX_AMOUNT} 之间。") from None
    return amount


def parse_expense_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("请输入有效日期。") from None
    return parsed


def validate_expense_fields(category: str, merchant: str, description: str) -> None:
    if category.strip() not in EXPENSE_CATEGORIES:
        raise ValueError("请选择有效的消费类别。")
    if len(merchant.strip()) > 120:
        raise ValueError("商户名称不能超过120个字符。")
    if len(description.strip()) > 1000:
        raise ValueError("说明不能超过1000个字符。")


def load_user(database: Session, session_data: dict) -> WebUser | None:
    user_id = session_data.get("user_id")
    if not isinstance(user_id, int):
        return None
    return database.get(WebUser, user_id)


def money(value) -> str:
    """金额统一以字符串进入 JSON，避免 float 精度问题。"""
    return f"{Decimal(str(value or 0)):.2f}"


def month_range(today: date) -> tuple[date, date]:
    month_start = today.replace(day=1)
    next_month_start = (
        date(today.year + 1, 1, 1)
        if today.month == 12
        else date(today.year, today.month + 1, 1)
    )
    return month_start, next_month_start


def expense_conditions(
    user_id: int,
    category: str = "",
    start: date | None = None,
    end: date | None = None,
) -> list:
    conditions = [WebExpense.user_id == user_id]
    if category:
        conditions.append(WebExpense.category == category)
    if start is not None:
        conditions.append(WebExpense.expense_date >= start)
    if end is not None:
        conditions.append(WebExpense.expense_date <= end)
    return conditions


def query_expenses_page(
    database: Session,
    user_id: int,
    *,
    category: str = "",
    start: date | None = None,
    end: date | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    conditions = expense_conditions(user_id, category, start, end)
    total = database.scalar(
        select(func.count(WebExpense.id)).where(*conditions)
    ) or 0
    total_amount = Decimal(str(database.scalar(
        select(func.coalesce(func.sum(WebExpense.amount), 0)).where(*conditions)
    ) or 0))
    pages = max(1, -(-total // page_size))
    page = min(max(1, page), pages)
    items = database.scalars(
        select(WebExpense)
        .where(*conditions)
        .order_by(WebExpense.expense_date.desc(), WebExpense.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": items,
        "total": total,
        "total_amount": total_amount,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


def get_owned_expense(
    database: Session, user_id: int, expense_id: int
) -> WebExpense | None:
    return database.scalar(
        select(WebExpense).where(
            WebExpense.id == expense_id, WebExpense.user_id == user_id
        )
    )


def category_summary(database: Session, user_id: int, limit: int | None = None):
    query = (
        select(WebExpense.category, func.sum(WebExpense.amount).label("total"))
        .where(WebExpense.user_id == user_id)
        .group_by(WebExpense.category)
        .order_by(func.sum(WebExpense.amount).desc())
    )
    if limit:
        query = query.limit(limit)
    return database.execute(query).all()


def monthly_summary(
    database: Session, user_id: int, months: int = 12
) -> list[dict]:
    """近 N 个月逐月合计，缺数据的月份补零，升序返回。

    按 年/月 两列 extract 分组，SQLite 与 PostgreSQL 通用，
    不再需要 strftime/to_char 的方言分支。
    """
    year_col = func.extract("year", WebExpense.expense_date)
    month_col = func.extract("month", WebExpense.expense_date)
    today = date.today()
    start_month = date(
        today.year - (months - 1 + today.month - 1) // 12,
        (today.month - 1 - (months - 1)) % 12 + 1,
        1,
    )
    rows = database.execute(
        select(year_col, month_col, func.sum(WebExpense.amount))
        .where(
            WebExpense.user_id == user_id,
            WebExpense.expense_date >= start_month,
        )
        .group_by(year_col, month_col)
    ).all()
    totals = {
        (int(row[0]), int(row[1])): Decimal(str(row[2])) for row in rows
    }
    result = []
    year, month = start_month.year, start_month.month
    for _ in range(months):
        result.append({
            "month": f"{year:04d}-{month:02d}",
            "total": totals.get((year, month), Decimal("0")),
        })
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def budget_status(database: Session, user_id: int, today: date) -> dict:
    """预算对账：总预算与分类预算是两种承诺，必须分开算。

    - "全部类别"预算存在时才有"总超支"这一说（0 也是合法承诺）；
    - 分类预算逐类别与该类别当月实际支出对账；
    - 没有总预算时，分类预算之和只作参考展示，不触发总告警。
    """
    month_key = today.strftime("%Y-%m")
    month_start, next_month_start = month_range(today)
    in_current_month = (
        WebExpense.expense_date >= month_start,
        WebExpense.expense_date < next_month_start,
    )

    month_total = Decimal(str(database.scalar(
        select(func.coalesce(func.sum(WebExpense.amount), 0)).where(
            WebExpense.user_id == user_id, *in_current_month
        )
    ) or 0))
    month_budgets = database.scalars(
        select(WebBudget).where(
            WebBudget.user_id == user_id,
            WebBudget.budget_month == month_key,
        )
    ).all()
    overall_budget = next(
        (
            budget.amount
            for budget in month_budgets
            if budget.category == OVERALL_BUDGET_CATEGORY
        ),
        None,
    )
    has_overall_budget = overall_budget is not None
    category_budgets = [
        budget
        for budget in month_budgets
        if budget.category != OVERALL_BUDGET_CATEGORY
    ]

    spent_rows = database.execute(
        select(WebExpense.category, func.sum(WebExpense.amount))
        .where(WebExpense.user_id == user_id, *in_current_month)
        .group_by(WebExpense.category)
    ).all()
    spent_by_category = {row[0]: Decimal(str(row[1])) for row in spent_rows}

    category_statuses = []
    category_overruns = []
    for budget in category_budgets:
        amount = Decimal(str(budget.amount))
        spent = spent_by_category.get(budget.category, Decimal("0"))
        status = {
            "category": budget.category,
            "budget": amount,
            "spent": spent,
            "over": max(spent - amount, Decimal("0")),
        }
        category_statuses.append(status)
        if spent > amount:
            category_overruns.append(status)

    if has_overall_budget:
        budget_total = Decimal(str(overall_budget))
    else:
        budget_total = sum(
            (Decimal(str(budget.amount)) for budget in category_budgets),
            Decimal("0"),
        )
    return {
        "month_key": month_key,
        "month_total": month_total,
        "budget_total": budget_total,
        "budget_remaining": budget_total - month_total,
        "budget_exceeded": has_overall_budget and month_total > budget_total,
        "has_overall_budget": has_overall_budget,
        "category_statuses": category_statuses,
        "category_overruns": category_overruns,
    }
