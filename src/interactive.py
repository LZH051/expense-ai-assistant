from uuid import uuid4

from db import connect_to_database
from etl import normalize_amount, normalize_date
from init_database import initialize_database
from update_expense import update_expense


def read_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("该项不能为空，请重新输入。")


def read_user_id() -> int:
    while True:
        try:
            user_id = int(input("用户 ID：").strip())
        except ValueError:
            print("用户 ID 必须是整数。")
            continue
        connection = connect_to_database()
        try:
            user = connection.execute(
                "SELECT username FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        finally:
            connection.close()
        if user:
            return user_id
        print("没有找到该用户，请先创建用户。")


def add_user() -> None:
    username = read_required("用户名：")
    email = read_required("邮箱：")
    connection = connect_to_database()
    try:
        cursor = connection.execute(
            "INSERT INTO users (username, email) VALUES (?, ?)", (username, email)
        )
        connection.commit()
        print(f"用户创建成功，用户 ID：{cursor.lastrowid}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_expense() -> None:
    user_id = read_user_id()
    while True:
        expense_date = normalize_date(input("消费日期（例如 2026-08-21）："))
        if expense_date:
            break
        print("日期格式无效，请重新输入。")
    category = read_required("消费类别：")
    while True:
        amount = normalize_amount(input("消费金额："))
        if amount is not None:
            break
        print("金额格式无效，金额不能为负数。")
    merchant = input("商户（可留空）：").strip() or None
    description = input("说明（可留空）：").strip() or None

    connection = connect_to_database()
    try:
        connection.execute(
            """
            INSERT INTO expenses (
                source_record_id, user_id, expense_date, category,
                amount, merchant, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"MANUAL-{uuid4().hex}", user_id, expense_date, category,
                float(amount), merchant, description,
            ),
        )
        connection.commit()
        print("消费记录保存成功。")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_budget() -> None:
    user_id = read_user_id()
    while True:
        budget_month = input("预算月份（YYYY-MM）：").strip()
        if len(budget_month) == 7 and normalize_date(f"{budget_month}-01"):
            break
        print("月份格式无效，请使用 YYYY-MM。")
    category = read_required("预算类别：")
    while True:
        amount = normalize_amount(input("预算金额："))
        if amount is not None:
            break
        print("金额格式无效，金额不能为负数。")

    connection = connect_to_database()
    try:
        connection.execute(
            """
            INSERT INTO budgets (user_id, budget_month, category, budget_amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, budget_month, category)
            DO UPDATE SET budget_amount = excluded.budget_amount
            """,
            (user_id, budget_month, category, float(amount)),
        )
        connection.commit()
        print("预算保存成功；同月份、同类别的原预算会被更新。")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def show_data() -> None:
    connection = connect_to_database()
    try:
        users = connection.execute(
            "SELECT user_id, username, email FROM users ORDER BY user_id"
        ).fetchall()
        expenses = connection.execute(
            """
            SELECT e.expense_date, u.username, e.category, e.amount,
                   e.merchant, e.description
            FROM expenses AS e JOIN users AS u ON u.user_id = e.user_id
            ORDER BY e.expense_date DESC, e.expense_id DESC LIMIT 10
            """
        ).fetchall()
        budgets = connection.execute(
            """
            SELECT b.budget_month, u.username, b.category, b.budget_amount
            FROM budgets AS b JOIN users AS u ON u.user_id = b.user_id
            ORDER BY b.budget_month DESC, b.category LIMIT 10
            """
        ).fetchall()
    finally:
        connection.close()

    print("\n用户：")
    for row in users:
        print(f"- ID {row['user_id']}：{row['username']}（{row['email']}）")
    print("\n最近10条消费：")
    for row in expenses:
        print(
            f"- {row['expense_date']} {row['username']} {row['category']} "
            f"{row['amount']:.2f} 元 {row['merchant'] or ''} "
            f"{row['description'] or ''}".rstrip()
        )
    print("\n最近10条预算：")
    for row in budgets:
        print(
            f"- {row['budget_month']} {row['username']} {row['category']} "
            f"{row['budget_amount']:.2f} 元"
        )


def run_interactive() -> None:
    initialize_database()
    actions = {
        "1": add_user,
        "2": add_expense,
        "3": set_budget,
        "4": show_data,
        "5": update_expense,
    }
    while True:
        print(
            "\n个人消费记账助手\n"
            "1. 创建用户\n2. 录入消费\n3. 设置或更新预算\n"
            "4. 查看数据\n5. 修改已有消费记录\n0. 退出"
        )
        choice = input("请选择操作：").strip()
        if choice == "0":
            print("已退出。")
            return
        action = actions.get(choice)
        if not action:
            print("无效选项，请重新选择。")
            continue
        try:
            action()
        except Exception as error:
            print(f"操作失败：{error}")
