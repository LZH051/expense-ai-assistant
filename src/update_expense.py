"""Interactively update an existing expense record."""

from db import connect_to_database
from etl import normalize_amount, normalize_date


def show_recent_expenses(cursor) -> bool:
    cursor.execute(
        """
        SELECT expense_id, user_id, expense_date, category,
               amount, merchant, description
        FROM expenses
        ORDER BY expense_id DESC
        LIMIT 20
        """
    )
    rows = cursor.fetchall()

    if not rows:
        print("目前没有可以修改的消费记录。")
        return False

    print("\n最近的消费记录：")
    print("记录ID | 用户ID | 日期 | 类别 | 金额 | 商户 | 说明")
    print("-" * 90)
    for row in rows:
        print(
            f"{row['expense_id']} | {row['user_id']} | {row['expense_date']} | "
            f"{row['category']} | {row['amount']:.2f} | "
            f"{row['merchant'] or ''} | {row['description'] or ''}"
        )
    return True


def read_new_user_id(cursor, current_user_id: int) -> int | None:
    value = input(f"用户 ID [{current_user_id}]：").strip()
    if not value:
        return current_user_id
    try:
        user_id = int(value)
    except ValueError:
        print("用户 ID 必须是整数。")
        return None

    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        print("没有找到该用户。")
        return None
    return user_id


def read_new_date(current_date: str) -> str | None:
    value = input(f"消费日期 [{current_date}]：").strip()
    if not value:
        return current_date
    normalized = normalize_date(value)
    if normalized is None:
        print("日期格式无效。")
    return normalized


def read_new_amount(current_amount: float) -> float | None:
    value = input(f"消费金额 [{current_amount:.2f}]：").strip()
    if not value:
        return current_amount
    normalized = normalize_amount(value)
    if normalized is None:
        print("金额格式无效，金额不能为负数。")
        return None
    return float(normalized)


def read_optional_text(label: str, current_value: str | None) -> str | None:
    shown_value = current_value or "空"
    value = input(f"{label} [{shown_value}]（输入 - 可清空）：").strip()
    if not value:
        return current_value
    if value == "-":
        return None
    return value


def update_expense() -> None:
    connection = connect_to_database()

    try:
        cursor = connection.cursor()
        if not show_recent_expenses(cursor):
            return

        expense_id_text = input("\n请输入需要修改的消费记录 ID：").strip()
        try:
            expense_id = int(expense_id_text)
        except ValueError:
            print("记录 ID 必须是整数，本次没有修改数据。")
            return

        cursor.execute(
            """
            SELECT expense_id, user_id, expense_date, category,
                   amount, merchant, description
            FROM expenses
            WHERE expense_id = ?
            """,
            (expense_id,),
        )
        expense = cursor.fetchone()

        if expense is None:
            print(f"没有找到 ID 为 {expense_id} 的消费记录。")
            return

        print("\n请输入新内容；直接按 Enter 保留原值。")
        user_id = read_new_user_id(cursor, expense["user_id"])
        if user_id is None:
            return

        expense_date = read_new_date(expense["expense_date"])
        if expense_date is None:
            return

        category = input(f"消费类别 [{expense['category']}]：").strip()
        category = category or expense["category"]

        amount = read_new_amount(expense["amount"])
        if amount is None:
            return

        merchant = read_optional_text("商户", expense["merchant"])
        description = read_optional_text("说明", expense["description"])

        old_values = (
            expense["user_id"], expense["expense_date"], expense["category"],
            float(expense["amount"]), expense["merchant"], expense["description"],
        )
        new_values = (
            user_id, expense_date, category, amount, merchant, description,
        )

        if new_values == old_values:
            print("所有内容都保持原值，没有需要更新的数据。")
            return

        print("\n更新后的内容：")
        print(f"用户 ID：{user_id}")
        print(f"日期：{expense_date}")
        print(f"类别：{category}")
        print(f"金额：{amount:.2f}")
        print(f"商户：{merchant or '空'}")
        print(f"说明：{description or '空'}")

        confirmation = input("输入 y 确认更新：").strip().lower()
        if confirmation != "y":
            print("已取消，本次没有修改数据。")
            return

        cursor.execute(
            """
            UPDATE expenses
            SET user_id = ?, expense_date = ?, category = ?,
                amount = ?, merchant = ?, description = ?
            WHERE expense_id = ?
            """,
            (*new_values, expense_id),
        )
        connection.commit()

        if cursor.rowcount == 1:
            print(f"修改成功：消费记录 {expense_id} 已更新。")
        else:
            print("没有记录被修改。")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    update_expense()
