import csv

from db import connect_to_database, get_database_path
from paths import CLEAN_DATA_FILE, RAW_DATA_FILE


def count_csv_rows(path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return sum(1 for _ in csv.DictReader(file))


def verify_project() -> None:
    required_tables = {"users", "expenses", "budgets"}
    raw_count = count_csv_rows(RAW_DATA_FILE)
    clean_count = count_csv_rows(CLEAN_DATA_FILE)

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        table_names = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM expenses")
        expense_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM budgets")
        budget_count = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM expenses AS e
            LEFT JOIN users AS u ON u.user_id = e.user_id
            WHERE u.user_id IS NULL
            """
        )
        orphan_expenses = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM budgets AS b
            LEFT JOIN users AS u ON u.user_id = b.user_id
            WHERE u.user_id IS NULL
            """
        )
        orphan_budgets = cursor.fetchone()[0]
        cursor.close()
    finally:
        connection.close()

    assert required_tables.issubset(table_names), "缺少 SQLite 数据表"
    assert 50 <= raw_count <= 100, "原始模拟数据应为50～100条"
    assert clean_count == expense_count, "清洗数据与 SQLite 入库数量不一致"
    assert orphan_expenses == 0 and orphan_budgets == 0, "存在无效外键数据"

    print(f"SQLite：{get_database_path()}")
    print(f"数据库表：{', '.join(sorted(required_tables))}")
    print(f"原始数据：{raw_count} 条")
    print(f"清洗数据：{clean_count} 条")
    print(f"用户：{user_count} 条")
    print(f"消费记录：{expense_count} 条")
    print(f"预算：{budget_count} 条")
    print("外键数据检查：通过")
    print("项目A SQLite 验收：通过")


if __name__ == "__main__":
    verify_project()
