import argparse

from ai_analysis import generate_ai_analysis
from etl import clean_expense_data
from generate_data import generate_data
from interactive import run_interactive
from load_database import load_database
from expense_statistics import generate_statistics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 SQLite 版个人消费记账与 AI 分析助手"
    )
    parser.add_argument("--with-ai", action="store_true")
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument(
        "--interactive", action="store_true", help="进入用户手动记账模式"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interactive:
        run_interactive()
        return
    if args.with_ai and not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")

    print("步骤 1/4：生成模拟消费数据")
    generate_data()
    print("\n步骤 2/4：清洗消费数据")
    clean_expense_data()
    print("\n步骤 3/4：创建 SQLite 表并写入数据")
    load_database()
    print("\n步骤 4/4：从 SQLite 生成消费统计")
    statistics = generate_statistics()

    if args.with_ai:
        print("\n调用大模型生成分析建议")
        print(generate_ai_analysis())
    else:
        print("\nSQLite 数据流程已完成，未调用付费 AI 接口。")
    print(
        f"\n流程完成：共生成 {len(statistics['category_summary'])} "
        "个类别的统计结果。"
    )


if __name__ == "__main__":
    main()
