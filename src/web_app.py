import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from logging_setup import configure_logging
from web_database import Base, SessionLocal, engine
from web_models import WebBudget, WebExpense, WebUser
from web_security import (
    get_csrf_token,
    hash_password,
    is_valid_email,
    normalize_email,
    valid_csrf_token,
    verify_password,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
EXPENSE_CATEGORIES = (
    "餐饮", "交通", "购物", "居住", "娱乐",
    "医疗", "教育", "旅行", "其他",
)
BUDGET_CATEGORIES = ("全部类别", *EXPENSE_CATEGORIES)

if os.getenv("VERCEL") and not SESSION_SECRET:
    raise RuntimeError("线上部署必须配置 SESSION_SECRET 环境变量。")
if not SESSION_SECRET:
    SESSION_SECRET = "local-development-only-change-before-deployment"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if engine.dialect.name == "postgresql":
        # Vercel may start several functions at the same time. Serializing the
        # schema check prevents concurrent CREATE TABLE statements from racing.
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(2077468312)"))
            Base.metadata.create_all(bind=connection)
    else:
        Base.metadata.create_all(bind=engine)
    yield


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="安心账本", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=bool(os.getenv("VERCEL")),
    max_age=60 * 60 * 24 * 14,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("%s %s 未捕获异常", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s %s %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def add_message(request: Request, text: str, kind: str = "success") -> None:
    messages = request.session.setdefault("messages", [])
    messages.append({"text": text, "kind": kind})
    request.session["messages"] = messages[-5:]


def current_user(request: Request, database: Session) -> WebUser | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return database.get(WebUser, user_id)


def render(
    request: Request,
    template_name: str,
    *,
    user: WebUser | None = None,
    status_code: int = 200,
    **context,
) -> HTMLResponse:
    messages = request.session.pop("messages", [])
    values = {
        "request": request,
        "current_user": user,
        "csrf_token": get_csrf_token(request.session),
        "messages": messages,
        **context,
    }
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=values,
        status_code=status_code,
    )


def require_csrf(request: Request, submitted_token: str) -> None:
    if not valid_csrf_token(request.session, submitted_token):
        raise HTTPException(status_code=400, detail="请求已失效，请刷新页面后重试。")


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("请输入有效金额。") from None
    if amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("金额必须在 0 至 9999999999.99 之间。")
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user:
            return redirect("/dashboard")
        return render(request, "landing.html")


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    with SessionLocal() as database:
        if current_user(request, database):
            return redirect("/dashboard")
    return render(request, "register.html")


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    username = username.strip()
    email = normalize_email(email)
    errors: list[str] = []
    if len(username) < 2 or len(username) > 50:
        errors.append("用户名长度应为2至50个字符。")
    if not is_valid_email(email):
        errors.append("请输入有效邮箱地址。")
    if len(password) < 8 or len(password) > 128:
        errors.append("密码长度应为8至128个字符。")
    if password != password_confirm:
        errors.append("两次输入的密码不一致。")
    if errors:
        return render(
            request, "register.html", errors=errors,
            form={"username": username, "email": email}, status_code=422,
        )

    with SessionLocal() as database:
        user = WebUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        database.add(user)
        try:
            database.commit()
        except IntegrityError:
            database.rollback()
            return render(
                request, "register.html", errors=["该邮箱已经注册。"],
                form={"username": username, "email": email}, status_code=409,
            )
        database.refresh(user)
        request.session.clear()
        request.session["user_id"] = user.id
        get_csrf_token(request.session)
        add_message(request, "账户创建成功，欢迎使用安心账本。")
    return redirect("/dashboard")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    with SessionLocal() as database:
        if current_user(request, database):
            return redirect("/dashboard")
    return render(request, "login.html")


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    email = normalize_email(email)
    with SessionLocal() as database:
        user = database.scalar(select(WebUser).where(WebUser.email == email))
        if user is None or not verify_password(password, user.password_hash):
            return render(
                request, "login.html",
                errors=["邮箱或密码不正确。"],
                form={"email": email}, status_code=401,
            )
        request.session.clear()
        request.session["user_id"] = user.id
        get_csrf_token(request.session)
        add_message(request, f"欢迎回来，{user.username}。")
    return redirect("/dashboard")


@app.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    request.session.clear()
    return redirect("/")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")

        today = date.today()
        month_key = today.strftime("%Y-%m")
        total = database.scalar(
            select(func.coalesce(func.sum(WebExpense.amount), 0)).where(
                WebExpense.user_id == user.id
            )
        )
        month_total = database.scalar(
            select(func.coalesce(func.sum(WebExpense.amount), 0)).where(
                WebExpense.user_id == user.id,
                func.strftime("%Y-%m", WebExpense.expense_date) == month_key
                if engine.dialect.name == "sqlite"
                else func.to_char(WebExpense.expense_date, "YYYY-MM") == month_key,
            )
        )
        count = database.scalar(
            select(func.count(WebExpense.id)).where(WebExpense.user_id == user.id)
        )
        category_rows = database.execute(
            select(WebExpense.category, func.sum(WebExpense.amount).label("total"))
            .where(WebExpense.user_id == user.id)
            .group_by(WebExpense.category)
            .order_by(func.sum(WebExpense.amount).desc())
            .limit(6)
        ).all()
        recent = database.scalars(
            select(WebExpense)
            .where(WebExpense.user_id == user.id)
            .order_by(WebExpense.expense_date.desc(), WebExpense.id.desc())
            .limit(8)
        ).all()
        overall_budget = database.scalar(
            select(WebBudget.amount).where(
                WebBudget.user_id == user.id,
                WebBudget.budget_month == month_key,
                WebBudget.category == "全部类别",
            )
        )
        if overall_budget is not None:
            budget_total = overall_budget
        else:
            budget_total = database.scalar(
                select(func.coalesce(func.sum(WebBudget.amount), 0)).where(
                    WebBudget.user_id == user.id,
                    WebBudget.budget_month == month_key,
                )
            )
        budget_total = Decimal(str(budget_total or 0))
        month_total = Decimal(str(month_total or 0))
        budget_remaining = budget_total - month_total
        budget_exceeded = budget_total > 0 and budget_remaining < 0
        return render(
            request, "dashboard.html", user=user, total=total,
            month_total=month_total, expense_count=count, recent=recent,
            category_rows=category_rows, month_key=month_key,
            budget_total=budget_total, budget_remaining=budget_remaining,
            budget_exceeded=budget_exceeded,
        )


@app.get("/expenses", response_class=HTMLResponse)
def expenses_page(
    request: Request,
    category: str = "",
    start_date: str = "",
    end_date: str = "",
):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")

        selected_category = category.strip()
        selected_start_date = start_date.strip()
        selected_end_date = end_date.strip()
        parsed_start_date = None
        parsed_end_date = None

        try:
            if selected_start_date:
                parsed_start_date = parse_expense_date(selected_start_date)
            if selected_end_date:
                parsed_end_date = parse_expense_date(selected_end_date)
            if (
                parsed_start_date is not None
                and parsed_end_date is not None
                and parsed_start_date > parsed_end_date
            ):
                raise ValueError("开始日期不能晚于结束日期。")
        except ValueError as error:
            add_message(request, str(error), "error")
            return redirect("/expenses")

        query = select(WebExpense).where(WebExpense.user_id == user.id)
        if selected_category:
            query = query.where(WebExpense.category == selected_category)
        if parsed_start_date is not None:
            query = query.where(WebExpense.expense_date >= parsed_start_date)
        if parsed_end_date is not None:
            query = query.where(WebExpense.expense_date <= parsed_end_date)
        expenses = database.scalars(
            query.order_by(WebExpense.expense_date.desc(), WebExpense.id.desc())
        ).all()
        return render(
            request, "expenses.html", user=user, expenses=expenses,
            categories=EXPENSE_CATEGORIES,
            selected_category=selected_category,
            selected_start_date=selected_start_date,
            selected_end_date=selected_end_date,
        )


@app.get("/expenses/new", response_class=HTMLResponse)
def new_expense_page(request: Request):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        return render(
            request, "expense_form.html", user=user, expense=None,
            form={"expense_date": date.today().isoformat()},
        )


@app.post("/expenses/new")
def create_expense(
    request: Request,
    expense_date: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    merchant: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        form = {
            "expense_date": expense_date, "category": category,
            "amount": amount, "merchant": merchant,
            "description": description,
        }
        try:
            parsed_date = parse_expense_date(expense_date)
            parsed_amount = parse_amount(amount)
            validate_expense_fields(category, merchant, description)
        except ValueError as error:
            return render(
                request, "expense_form.html", user=user, expense=None,
                form=form, errors=[str(error)], status_code=422,
            )
        database.add(
            WebExpense(
                user_id=user.id, expense_date=parsed_date,
                category=category.strip(), amount=parsed_amount,
                merchant=merchant.strip() or None,
                description=description.strip() or None,
            )
        )
        database.commit()
        add_message(request, "消费记录已保存。")
    return redirect("/expenses")


@app.get("/expenses/{expense_id}/edit", response_class=HTMLResponse)
def edit_expense_page(request: Request, expense_id: int):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        expense = database.scalar(
            select(WebExpense).where(
                WebExpense.id == expense_id, WebExpense.user_id == user.id
            )
        )
        if expense is None:
            raise HTTPException(status_code=404, detail="消费记录不存在。")
        return render(
            request, "expense_form.html", user=user, expense=expense, form={},
        )


@app.post("/expenses/{expense_id}/edit")
def update_expense_route(
    request: Request,
    expense_id: int,
    expense_date: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    merchant: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        expense = database.scalar(
            select(WebExpense).where(
                WebExpense.id == expense_id, WebExpense.user_id == user.id
            )
        )
        if expense is None:
            raise HTTPException(status_code=404, detail="消费记录不存在。")
        form = {
            "expense_date": expense_date, "category": category,
            "amount": amount, "merchant": merchant,
            "description": description,
        }
        try:
            parsed_date = parse_expense_date(expense_date)
            parsed_amount = parse_amount(amount)
            validate_expense_fields(category, merchant, description)
        except ValueError as error:
            return render(
                request, "expense_form.html", user=user, expense=expense,
                form=form, errors=[str(error)], status_code=422,
            )
        expense.expense_date = parsed_date
        expense.category = category.strip()
        expense.amount = parsed_amount
        expense.merchant = merchant.strip() or None
        expense.description = description.strip() or None
        database.commit()
        add_message(request, "消费记录已更新。")
    return redirect("/expenses")


@app.post("/expenses/{expense_id}/delete")
def delete_expense(request: Request, expense_id: int, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        expense = database.scalar(
            select(WebExpense).where(
                WebExpense.id == expense_id, WebExpense.user_id == user.id
            )
        )
        if expense is None:
            raise HTTPException(status_code=404, detail="消费记录不存在。")
        database.delete(expense)
        database.commit()
        add_message(request, "消费记录已删除。")
    return redirect("/expenses")


@app.get("/budgets", response_class=HTMLResponse)
def budgets_page(request: Request):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        budgets = database.scalars(
            select(WebBudget).where(WebBudget.user_id == user.id)
            .order_by(WebBudget.budget_month.desc(), WebBudget.category)
        ).all()
        return render(
            request, "budgets.html", user=user, budgets=budgets,
            current_month=date.today().strftime("%Y-%m"),
            categories=BUDGET_CATEGORIES,
        )


@app.post("/budgets")
def save_budget(
    request: Request,
    budget_month: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        try:
            date.fromisoformat(f"{budget_month}-01")
            parsed_amount = parse_amount(amount)
            if category.strip() not in BUDGET_CATEGORIES:
                raise ValueError("请选择有效的预算类别。")
        except ValueError as error:
            add_message(request, str(error), "error")
            return redirect("/budgets")
        budget = database.scalar(
            select(WebBudget).where(
                WebBudget.user_id == user.id,
                WebBudget.budget_month == budget_month,
                WebBudget.category == category.strip(),
            )
        )
        if budget:
            budget.amount = parsed_amount
            message = "预算已更新。"
        else:
            database.add(
                WebBudget(
                    user_id=user.id, budget_month=budget_month,
                    category=category.strip(), amount=parsed_amount,
                )
            )
            message = "预算已创建。"
        database.commit()
        add_message(request, message)
    return redirect("/budgets")


@app.post("/budgets/{budget_id}/delete")
def delete_budget(request: Request, budget_id: int, csrf_token: str = Form(...)):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        budget = database.scalar(
            select(WebBudget).where(
                WebBudget.id == budget_id, WebBudget.user_id == user.id
            )
        )
        if budget is None:
            raise HTTPException(status_code=404, detail="预算不存在。")
        database.delete(budget)
        database.commit()
        add_message(request, "预算已删除。")
    return redirect("/budgets")


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        return render(request, "account.html", user=user)


@app.post("/account/profile")
def update_profile(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    username = username.strip()
    email = normalize_email(email)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        if len(username) < 2 or len(username) > 50 or not is_valid_email(email):
            add_message(request, "用户名或邮箱格式不正确。", "error")
            return redirect("/account")
        user.username = username
        user.email = email
        try:
            database.commit()
        except IntegrityError:
            database.rollback()
            add_message(request, "该邮箱已经被其他账户使用。", "error")
            return redirect("/account")
        add_message(request, "账户资料已更新。")
    return redirect("/account")


@app.post("/account/password")
def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        if not verify_password(current_password, user.password_hash):
            add_message(request, "当前密码不正确。", "error")
        elif len(new_password) < 8 or len(new_password) > 128:
            add_message(request, "新密码长度应为8至128个字符。", "error")
        elif new_password != new_password_confirm:
            add_message(request, "两次输入的新密码不一致。", "error")
        else:
            user.password_hash = hash_password(new_password)
            database.commit()
            add_message(request, "密码已更新。")
    return redirect("/account")


@app.post("/account/delete")
def delete_account(
    request: Request,
    password: str = Form(...),
    confirmation: str = Form(...),
    csrf_token: str = Form(...),
):
    require_csrf(request, csrf_token)
    with SessionLocal() as database:
        user = current_user(request, database)
        if user is None:
            return redirect("/login")
        if confirmation != "DELETE" or not verify_password(password, user.password_hash):
            add_message(request, "删除确认文字或密码不正确。", "error")
            return redirect("/account")
        database.delete(user)
        database.commit()
    request.session.clear()
    return redirect("/")


@app.exception_handler(404)
def not_found(request: Request, _error: HTTPException):
    with SessionLocal() as database:
        user = current_user(request, database)
        return render(request, "404.html", user=user, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
