"""JSON API v1。

- 认证：沿用登录会话 Cookie；未登录统一返回
  {"error": {"code": "unauthorized", ...}}，错误封装由
  web_app 注册的异常处理器完成。
- CSRF：写接口只接受 JSON 请求体。SameSite=Lax 的会话 Cookie
  不会随跨站表单/fetch 提交，跨站页面构造不出这类请求，
  因此无需表单 CSRF token。
- 金额在 JSON 中一律为字符串（"45.50"），避免 float 精度问题。
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

import web_services as services
from web_database import SessionLocal
from web_models import WebExpense
from web_schemas import ExpenseCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


def require_user(request: Request, database):
    user = services.load_user(database, request.session)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def parse_optional_date(value: str, label: str) -> date | None:
    if not value.strip():
        return None
    try:
        return services.parse_expense_date(value)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"{label}不是有效日期。"
        ) from None


def serialize_expense(expense: WebExpense) -> dict:
    return {
        "id": expense.id,
        "expense_date": expense.expense_date.isoformat(),
        "category": expense.category,
        "amount": services.money(expense.amount),
        "merchant": expense.merchant,
        "description": expense.description,
    }


@router.get("/categories")
def list_categories(request: Request):
    with SessionLocal() as database:
        require_user(request, database)
    return {
        "expense_categories": list(services.EXPENSE_CATEGORIES),
        "budget_categories": list(services.BUDGET_CATEGORIES),
    }


@router.get("/expenses")
def list_expenses(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(services.DEFAULT_PAGE_SIZE, ge=1, le=100),
    category: str = "",
    start_date: str = "",
    end_date: str = "",
):
    with SessionLocal() as database:
        user = require_user(request, database)
        start = parse_optional_date(start_date, "开始日期")
        end = parse_optional_date(end_date, "结束日期")
        if start and end and start > end:
            raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期。")
        result = services.query_expenses_page(
            database, user.id,
            category=category.strip(), start=start, end=end,
            page=page, page_size=page_size,
        )
        return {
            "items": [serialize_expense(item) for item in result["items"]],
            "total": result["total"],
            "total_amount": services.money(result["total_amount"]),
            "page": result["page"],
            "pages": result["pages"],
            "page_size": result["page_size"],
        }


@router.post("/expenses", status_code=201)
def create_expense(request: Request, payload: ExpenseCreate):
    with SessionLocal() as database:
        user = require_user(request, database)
        expense = WebExpense(
            user_id=user.id,
            expense_date=payload.expense_date,
            category=payload.category,
            amount=services.parse_amount(payload.amount),
            merchant=payload.merchant or None,
            description=payload.description or None,
        )
        database.add(expense)
        database.commit()
        database.refresh(expense)
        logger.info("API 新增消费 user=%s id=%s", user.id, expense.id)
        return serialize_expense(expense)


@router.get("/statistics")
def statistics(request: Request):
    with SessionLocal() as database:
        user = require_user(request, database)
        categories = services.category_summary(database, user.id)
        monthly = services.monthly_summary(database, user.id)
        status = services.budget_status(database, user.id, date.today())
        return {
            "category_summary": [
                {"category": row.category, "total": services.money(row.total)}
                for row in categories
            ],
            "monthly_summary": [
                {"month": row["month"], "total": services.money(row["total"])}
                for row in monthly
            ],
            "budget_status": {
                "month": status["month_key"],
                "month_total": services.money(status["month_total"]),
                "budget_total": services.money(status["budget_total"]),
                "budget_remaining": services.money(status["budget_remaining"]),
                "budget_exceeded": status["budget_exceeded"],
                "has_overall_budget": status["has_overall_budget"],
                "category_overruns": [
                    {
                        "category": item["category"],
                        "budget": services.money(item["budget"]),
                        "spent": services.money(item["spent"]),
                        "over": services.money(item["over"]),
                    }
                    for item in status["category_overruns"]
                ],
            },
        }
