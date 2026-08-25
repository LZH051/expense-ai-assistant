import logging
import csv
import json

from db import connect_to_database
from paths import (
    CATEGORY_SUMMARY_FILE,
    MONTHLY_SUMMARY_FILE,
    STATISTICS_JSON_FILE,
    ensure_directories,
)

logger = logging.getLogger(__name__)


CATEGORY_SQL = """
SELECT category, ROUND(SUM(amount), 2) AS total_amount,
       COUNT(*) AS expense_count
FROM expenses
GROUP BY category
ORDER BY total_amount DESC
"""

MONTHLY_SQL = """
SELECT strftime('%Y-%m', expense_date) AS expense_month,
       ROUND(SUM(amount), 2) AS total_amount,
       COUNT(*) AS expense_count
FROM expenses
GROUP BY strftime('%Y-%m', expense_date)
ORDER BY expense_month
"""

BUDGET_COMPARISON_SQL = """
SELECT b.budget_month AS month, b.category,
       ROUND(b.budget_amount, 2) AS budget_amount,
       ROUND(COALESCE(SUM(e.amount), 0), 2) AS actual_amount,
       ROUND(COALESCE(SUM(e.amount), 0) - b.budget_amount, 2) AS difference
FROM budgets AS b
LEFT JOIN expenses AS e
    ON e.user_id = b.user_id
   AND strftime('%Y-%m', e.expense_date) = b.budget_month
   AND e.category = b.category
GROUP BY b.budget_id, b.budget_month, b.category, b.budget_amount
ORDER BY b.budget_month, b.category
"""


def write_csv(path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fetch_rows(cursor, sql: str) -> list[dict]:
    cursor.execute(sql)
    return [dict(row) for row in cursor.fetchall()]


def generate_statistics() -> dict:
    ensure_directories()
    connection = connect_to_database()
    try:
        cursor = connection.cursor()
        category_rows = fetch_rows(cursor, CATEGORY_SQL)
        monthly_rows = fetch_rows(cursor, MONTHLY_SQL)
        budget_rows = fetch_rows(cursor, BUDGET_COMPARISON_SQL)
        cursor.close()
    finally:
        connection.close()

    write_csv(
        CATEGORY_SUMMARY_FILE,
        ["category", "total_amount", "expense_count"],
        category_rows,
    )
    write_csv(
        MONTHLY_SUMMARY_FILE,
        ["expense_month", "total_amount", "expense_count"],
        monthly_rows,
    )
    statistics = {
        "category_summary": category_rows,
        "monthly_summary": monthly_rows,
        "budget_comparison": budget_rows,
    }
    STATISTICS_JSON_FILE.write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("\n按类别统计：")
    for row in category_rows:
        logger.info(
            f"- {row['category']}：{row['total_amount']:.2f} 元，"
            f"{row['expense_count']} 笔"
        )
    logger.info("\n按月统计：")
    for row in monthly_rows:
        logger.info(
            f"- {row['expense_month']}：{row['total_amount']:.2f} 元，"
            f"{row['expense_count']} 笔"
        )
    logger.info(f"\n统计结果已保存：{STATISTICS_JSON_FILE}")
    return statistics


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    generate_statistics()
