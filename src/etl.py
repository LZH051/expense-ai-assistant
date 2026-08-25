import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from paths import (
    CLEAN_DATA_FILE,
    CLEANING_REPORT_FILE,
    RAW_DATA_FILE,
    ensure_directories,
)


FIELDNAMES = [
    "record_id",
    "user_id",
    "expense_date",
    "category",
    "amount",
    "merchant",
    "description",
]

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d")


def normalize_date(value: str) -> str | None:
    value = value.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_amount(value: str) -> str | None:
    cleaned = value.strip().replace("￥", "").replace("¥", "").replace(",", "")
    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

    if amount < 0:
        return None
    return format(amount, ".2f")


def clean_expense_data() -> list[dict[str, str]]:
    ensure_directories()
    if not RAW_DATA_FILE.exists():
        raise FileNotFoundError(f"未找到原始数据：{RAW_DATA_FILE}")

    with RAW_DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        raw_rows = list(csv.DictReader(file))

    cleaned_rows: list[dict[str, str]] = []
    seen_keys: set[tuple[str, ...]] = set()
    report = {
        "raw_count": len(raw_rows),
        "fixed_empty_category": 0,
        "removed_invalid_amount": 0,
        "removed_invalid_date": 0,
        "removed_duplicate": 0,
        "clean_count": 0,
    }

    for raw_row in raw_rows:
        row = {
            key: (raw_row.get(key) or "").strip()
            for key in FIELDNAMES
        }

        if not row["category"]:
            row["category"] = "其他"
            report["fixed_empty_category"] += 1

        amount = normalize_amount(row["amount"])
        if amount is None:
            report["removed_invalid_amount"] += 1
            continue

        expense_date = normalize_date(row["expense_date"])
        if expense_date is None:
            report["removed_invalid_date"] += 1
            continue

        row["amount"] = amount
        row["expense_date"] = expense_date

        # 幂等去重：record_id 是业务主键（数据库层 source_record_id 也以它唯一），
        # 只有同一条记录被重复导入才算重复；字段全同但 record_id 不同是两笔真实消费
        duplicate_key = (row["record_id"],)
        if duplicate_key in seen_keys:
            report["removed_duplicate"] += 1
            continue

        seen_keys.add(duplicate_key)
        cleaned_rows.append(row)

    report["clean_count"] = len(cleaned_rows)

    with CLEAN_DATA_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    CLEANING_REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"清洗前记录数：{report['raw_count']}")
    print(f"修复空类别：{report['fixed_empty_category']}")
    print(f"删除非法金额：{report['removed_invalid_amount']}")
    print(f"删除非法日期：{report['removed_invalid_date']}")
    print(f"删除重复记录：{report['removed_duplicate']}")
    print(f"清洗后记录数：{report['clean_count']}")
    print(f"清洗结果：{CLEAN_DATA_FILE}")
    return cleaned_rows


if __name__ == "__main__":
    clean_expense_data()

