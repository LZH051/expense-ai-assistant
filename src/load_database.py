import csv

from db import connect_to_database
from init_database import initialize_database
from paths import CLEAN_DATA_FILE


BUDGETS = [
    ("2026-01", "餐饮", "900.00"),
    ("2026-01", "交通", "300.00"),
    ("2026-02", "餐饮", "900.00"),
    ("2026-02", "购物", "800.00"),
    ("2026-03", "餐饮", "950.00"),
    ("2026-03", "娱乐", "400.00"),
    ("2026-04", "餐饮", "950.00"),
    ("2026-05", "餐饮", "1000.00"),
    ("2026-06", "餐饮", "1000.00"),
    ("2026-06", "学习", "1500.00"),
]


def load_database() -> tuple[int, int]:
    if not CLEAN_DATA_FILE.exists():
        raise FileNotFoundError(f"未找到清洗数据：{CLEAN_DATA_FILE}")

    initialize_database()
    with CLEAN_DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (user_id, username, email)
            VALUES (?, ?, ?)
            """,
            (1, "示例用户", "student@example.com"),
        )
        cursor.execute("SELECT COUNT(*) FROM expenses")
        before_count = cursor.fetchone()[0]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO expenses (
                source_record_id, user_id, expense_date, category,
                amount, merchant, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["record_id"],
                    int(row["user_id"]),
                    row["expense_date"],
                    row["category"],
                    float(row["amount"]),
                    row["merchant"] or None,
                    row["description"] or None,
                )
                for row in rows
            ],
        )
        cursor.executemany(
            """
            INSERT OR IGNORE INTO budgets (
                user_id, budget_month, category, budget_amount
            )
            VALUES (?, ?, ?, ?)
            """,
            [(1, month, category, float(amount)) for month, category, amount in BUDGETS],
        )
        connection.commit()
        cursor.execute("SELECT COUNT(*) FROM expenses")
        after_count = cursor.fetchone()[0]
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    inserted_count = after_count - before_count
    skipped_count = len(rows) - inserted_count
    print(f"新增消费记录：{inserted_count}")
    print(f"跳过已存在记录：{skipped_count}")
    return inserted_count, skipped_count


if __name__ == "__main__":
    load_database()
