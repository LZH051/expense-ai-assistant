"""P0-1 复现测试：ETL 去重键必须以 record_id 为准。

场景一：两笔 record_id 不同、其余字段完全相同的合法消费
       （同一天在同一家店买两次同样的东西）——必须全部保留。
场景二：同一条记录被重复导入（record_id 相同）——必须只保留一条。
"""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import etl


def write_raw_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=etl.FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def base_row(record_id: str) -> dict[str, str]:
    return {
        "record_id": record_id,
        "user_id": "1",
        "expense_date": "2026-03-01",
        "category": "餐饮",
        "amount": "15.00",
        "merchant": "便利店",
        "description": "日常消费",
    }


def run_clean(rows: list[dict[str, str]], workdir: Path) -> tuple[list[dict[str, str]], dict]:
    raw_file = workdir / "raw.csv"
    write_raw_csv(raw_file, rows)
    etl.RAW_DATA_FILE = raw_file
    etl.CLEAN_DATA_FILE = workdir / "cleaned.csv"
    etl.CLEANING_REPORT_FILE = workdir / "report.json"
    cleaned = etl.clean_expense_data()
    import json

    report = json.loads(etl.CLEANING_REPORT_FILE.read_text(encoding="utf-8"))
    return cleaned, report


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)

        # 场景一：record_id 不同的两笔合法消费，不允许被误删
        cleaned, report = run_clean(
            [base_row("EXP-9001"), base_row("EXP-9002")], workdir
        )
        kept_ids = [row["record_id"] for row in cleaned]
        assert kept_ids == ["EXP-9001", "EXP-9002"], (
            f"合法消费被静默删除：清洗后只剩 {kept_ids}"
        )
        assert report["removed_duplicate"] == 0, report

        # 场景二：同一条记录重复导入，必须去重
        cleaned, report = run_clean(
            [base_row("EXP-9001"), base_row("EXP-9001")], workdir
        )
        kept_ids = [row["record_id"] for row in cleaned]
        assert kept_ids == ["EXP-9001"], f"重复导入未被去重：{kept_ids}"
        assert report["removed_duplicate"] == 1, report

    print("ETL_DEDUP_TEST=PASS")


if __name__ == "__main__":
    main()
