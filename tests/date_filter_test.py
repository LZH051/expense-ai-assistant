"""日期区间筛选测试（pytest 版）。

原版硬编码了 Windows 的 E:/tmp 路径与固定日期，只能在特定机器、
特定时间跑通；现在依赖 conftest 的临时库，并用相对日期构造数据
（消费日期校验不允许晚于明天，固定的未来日期会被拒绝）。
"""

from datetime import date, timedelta

from conftest import csrf_from

TODAY = date.today()
LAST_MONTH_DAY = (TODAY.replace(day=1) - timedelta(days=15))
THIS_MONTH_START = TODAY.replace(day=1)
LAST_MONTH_START = LAST_MONTH_DAY.replace(day=1)
LAST_MONTH_END = THIS_MONTH_START - timedelta(days=1)


def add_expense(client, expense_date: date, category: str, merchant: str) -> None:
    page = client.get("/expenses/new")
    response = client.post(
        "/expenses/new",
        data={
            "expense_date": expense_date.isoformat(),
            "category": category,
            "amount": "25.00",
            "merchant": merchant,
            "description": "Date filter test",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def seed(client) -> None:
    add_expense(client, LAST_MONTH_DAY, "餐饮", "LastMonth Restaurant")
    add_expense(client, TODAY, "交通", "ThisMonth Station")


def test_date_range_filter(user_client) -> None:
    seed(user_client)
    page = user_client.get(
        f"/expenses?start_date={LAST_MONTH_START}&end_date={LAST_MONTH_END}"
    ).text
    assert 'name="start_date"' in page
    assert "LastMonth Restaurant" in page
    assert "ThisMonth Station" not in page


def test_category_and_date_combined_filter(user_client) -> None:
    seed(user_client)
    combined = user_client.get(
        f"/expenses?category=餐饮&start_date={LAST_MONTH_START}"
        f"&end_date={LAST_MONTH_END}"
    ).text
    assert "LastMonth Restaurant" in combined
    assert "ThisMonth Station" not in combined


def test_start_after_end_is_rejected(user_client) -> None:
    invalid = user_client.get(
        f"/expenses?start_date={TODAY}&end_date={LAST_MONTH_START}",
        follow_redirects=True,
    )
    assert "开始日期不能晚于结束日期" in invalid.text
