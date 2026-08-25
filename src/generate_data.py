import logging
import csv
import random
from datetime import date, timedelta
from decimal import Decimal

from paths import RAW_DATA_FILE, ensure_directories

logger = logging.getLogger(__name__)


FIELDNAMES = [
    "record_id",
    "user_id",
    "expense_date",
    "category",
    "amount",
    "merchant",
    "description",
]

CATEGORY_CONFIG = {
    "餐饮": (Decimal("12"), Decimal("160"), ["美团外卖", "盒马", "便利店"]),
    "交通": (Decimal("2"), Decimal("90"), ["滴滴出行", "地铁", "共享单车"]),
    "购物": (Decimal("20"), Decimal("800"), ["京东", "淘宝", "商场"]),
    "娱乐": (Decimal("20"), Decimal("260"), ["电影院", "视频会员", "游乐场"]),
    "住房": (Decimal("80"), Decimal("1200"), ["物业", "水电燃气", "家居店"]),
    "医疗": (Decimal("10"), Decimal("500"), ["药店", "医院", "体检中心"]),
    "学习": (Decimal("10"), Decimal("400"), ["书店", "在线课程", "文具店"]),
}

DESCRIPTIONS = ["日常消费", "计划内支出", "临时支出", "周末消费", ""]


def random_amount(low: Decimal, high: Decimal) -> str:
    cents = random.randint(int(low * 100), int(high * 100))
    return str(Decimal(cents) / Decimal("100"))


def generate_normal_rows(count: int = 80) -> list[dict[str, str]]:
    random.seed(20260724)
    start_date = date(2026, 1, 1)
    rows: list[dict[str, str]] = []

    for index in range(1, count + 1):
        category = random.choice(list(CATEGORY_CONFIG))
        low, high, merchants = CATEGORY_CONFIG[category]
        expense_date = start_date + timedelta(days=random.randint(0, 180))

        rows.append(
            {
                "record_id": f"EXP-{index:04d}",
                "user_id": "1",
                "expense_date": expense_date.isoformat(),
                "category": category,
                "amount": random_amount(low, high),
                "merchant": random.choice(merchants),
                "description": random.choice(DESCRIPTIONS),
            }
        )

    return rows


def add_anomalies(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """加入可修复和不可修复的异常，供 ETL 展示清洗能力。"""
    result = [row.copy() for row in rows]

    # 完全重复记录
    result.append(rows[4].copy())

    # 可修复异常：空类别、人民币符号、千位逗号、不同日期格式
    result.append(
        {
            "record_id": "EXP-0081",
            "user_id": "1",
            "expense_date": "2026/06/18",
            "category": "",
            "amount": "￥188.50",
            "merchant": " 商场 ",
            "description": "类别缺失测试",
        }
    )
    result.append(
        {
            "record_id": "EXP-0082",
            "user_id": "1",
            "expense_date": "2026.06.20",
            "category": "学习",
            "amount": "1,299.00",
            "merchant": "在线课程",
            "description": "金额格式测试",
        }
    )

    # 不可修复异常：错误金额、错误日期、负数金额
    result.extend(
        [
            {
                "record_id": "EXP-0083",
                "user_id": "1",
                "expense_date": "2026-06-22",
                "category": "购物",
                "amount": "金额未知",
                "merchant": "商场",
                "description": "非法金额测试",
            },
            {
                "record_id": "EXP-0084",
                "user_id": "1",
                "expense_date": "2026-13-40",
                "category": "餐饮",
                "amount": "35.00",
                "merchant": "便利店",
                "description": "非法日期测试",
            },
            {
                "record_id": "EXP-0085",
                "user_id": "1",
                "expense_date": "2026-06-23",
                "category": "交通",
                "amount": "-20.00",
                "merchant": "滴滴出行",
                "description": "负数金额测试",
            },
        ]
    )

    return result


def generate_data() -> list[dict[str, str]]:
    ensure_directories()
    rows = add_anomalies(generate_normal_rows())

    with RAW_DATA_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"模拟数据生成成功：{RAW_DATA_FILE}")
    logger.info(f"共生成 {len(rows)} 条记录，其中包含重复、缺失和格式异常数据。")
    return rows


if __name__ == "__main__":
    from logging_setup import configure_logging

    configure_logging()
    generate_data()

