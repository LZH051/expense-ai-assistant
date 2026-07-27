import argparse
import json
import os

from paths import AI_ANALYSIS_FILE, STATISTICS_JSON_FILE


def build_prompt(statistics: dict) -> str:
    return f"""你是一名理性的个人消费分析助手。

下面是经过清洗和聚合的消费统计数据：
{json.dumps(statistics, ensure_ascii=False, indent=2)}

请概括消费结构和趋势，找出金额最高的类别，指出可能的超支，并给出三条
具体可执行的节省建议。使用中文，控制在300字以内，不要虚构数据。
"""


def generate_ai_analysis() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("AI_API_KEY", "").strip()
    base_url = os.getenv("AI_BASE_URL", "").strip()
    model = os.getenv("AI_MODEL", "").strip()
    missing = [
        name for name, value in {
            "AI_API_KEY": api_key,
            "AI_BASE_URL": base_url,
            "AI_MODEL": model,
        }.items() if not value
    ]
    if missing:
        raise RuntimeError("AI 配置不完整：" + ", ".join(missing))
    if not STATISTICS_JSON_FILE.exists():
        raise FileNotFoundError(f"未找到统计数据：{STATISTICS_JSON_FILE}")

    from openai import OpenAI

    statistics = json.loads(STATISTICS_JSON_FILE.read_text(encoding="utf-8"))
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你只根据用户提供的数据进行分析。"},
            {"role": "user", "content": build_prompt(statistics)},
        ],
        temperature=0.3,
    )
    analysis = (response.choices[0].message.content or "").strip()
    AI_ANALYSIS_FILE.write_text(analysis, encoding="utf-8")
    print(f"AI 分析已保存：{AI_ANALYSIS_FILE}")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="生成消费 AI 分析")
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")
    generate_ai_analysis()


if __name__ == "__main__":
    main()
