"""调用大模型生成消费分析，带超时、重试、降级与 token 用量记录。

健壮性设计：
- 客户端级超时 30 秒，避免请求无限挂起；
- 仅对瞬时故障（网络中断/超时/限流/服务端 5xx）做最多 3 次
  指数退避重试；认证失败等确定性错误不做无意义重试；
- 最终失败不抛异常：优先返回上一次成功的分析结果（不覆盖旧文件），
  没有旧结果时返回明确的不可用提示，保证主流程不被 AI 步骤拖垮；
- 每次成功调用把 response.usage 追加到 output/ai_usage.jsonl，
  作为成本监控的原始数据。
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable

from paths import AI_ANALYSIS_FILE, AI_USAGE_FILE, STATISTICS_JSON_FILE

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30.0
FALLBACK_MESSAGE = "AI 分析暂不可用（接口调用失败），本次流程未生成新的分析。"


def build_prompt(statistics: dict) -> str:
    return f"""你是一名理性的个人消费分析助手。

下面是经过清洗和聚合的消费统计数据：
{json.dumps(statistics, ensure_ascii=False, indent=2)}

请概括消费结构和趋势，找出金额最高的类别，指出可能的超支，并给出三条
具体可执行的节省建议。使用中文，控制在300字以内，不要虚构数据。
"""


def load_ai_config() -> dict[str, str]:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    config = {
        "AI_API_KEY": os.getenv("AI_API_KEY", "").strip(),
        "AI_BASE_URL": os.getenv("AI_BASE_URL", "").strip(),
        "AI_MODEL": os.getenv("AI_MODEL", "").strip(),
    }
    missing = [name for name, value in config.items() if not value]
    if missing:
        raise RuntimeError("AI 配置不完整：" + ", ".join(missing))
    return config


def is_transient_error(error: Exception) -> bool:
    """网络/超时/限流/服务端 5xx 才值得重试，4xx 配置类错误重试无意义。"""
    import openai

    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(error, openai.RateLimitError):
        return True
    if isinstance(error, openai.APIStatusError):
        return error.status_code >= 500
    return False


def call_with_retry(
    request: Callable[[], object], retry_base_delay: float = 2.0
) -> object:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return request()
        except Exception as error:
            if not is_transient_error(error) or attempt == MAX_ATTEMPTS:
                raise
            delay = retry_base_delay * (2 ** (attempt - 1))
            logger.warning(
                "AI 调用第 %d/%d 次失败（%s），%.1f 秒后重试",
                attempt, MAX_ATTEMPTS, type(error).__name__, delay,
            )
            time.sleep(delay)
    raise RuntimeError("unreachable")


def record_usage(model: str, usage: object) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
    AI_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AI_USAGE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(
        "本次 AI 调用消耗 token：输入 %s / 输出 %s / 合计 %s",
        entry["prompt_tokens"], entry["completion_tokens"], entry["total_tokens"],
    )


def degraded_result() -> str:
    if AI_ANALYSIS_FILE.exists():
        cached = AI_ANALYSIS_FILE.read_text(encoding="utf-8")
        logger.warning("AI 调用失败，返回上一次成功的分析结果作为降级。")
        return f"[降级：以下为上一次成功生成的分析]\n{cached}"
    logger.warning("AI 调用失败且无历史结果可降级。")
    return FALLBACK_MESSAGE


def generate_ai_analysis(
    client_factory: Callable[[], object] | None = None,
    retry_base_delay: float = 2.0,
) -> str:
    config = load_ai_config()
    if not STATISTICS_JSON_FILE.exists():
        raise FileNotFoundError(f"未找到统计数据：{STATISTICS_JSON_FILE}")
    statistics = json.loads(STATISTICS_JSON_FILE.read_text(encoding="utf-8"))

    if client_factory is None:
        from openai import OpenAI

        def client_factory() -> object:
            # max_retries=0：重试策略由 call_with_retry 统一控制，避免叠加
            return OpenAI(
                api_key=config["AI_API_KEY"],
                base_url=config["AI_BASE_URL"],
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )

    client = client_factory()
    try:
        response = call_with_retry(
            lambda: client.chat.completions.create(
                model=config["AI_MODEL"],
                messages=[
                    {"role": "system", "content": "你只根据用户提供的数据进行分析。"},
                    {"role": "user", "content": build_prompt(statistics)},
                ],
                temperature=0.3,
            ),
            retry_base_delay=retry_base_delay,
        )
    except Exception:
        logger.exception("AI 调用最终失败，进入降级路径")
        return degraded_result()

    analysis = (response.choices[0].message.content or "").strip()
    if not analysis:
        logger.error("模型返回了空内容，进入降级路径")
        return degraded_result()

    if getattr(response, "usage", None) is not None:
        record_usage(config["AI_MODEL"], response.usage)
    AI_ANALYSIS_FILE.write_text(analysis, encoding="utf-8")
    logger.info(f"AI 分析已保存：{AI_ANALYSIS_FILE}")
    return analysis


def main() -> None:
    from logging_setup import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(description="生成消费 AI 分析")
    parser.add_argument("--confirm-paid-run", action="store_true")
    args = parser.parse_args()
    if not args.confirm_paid_run:
        raise SystemExit("AI 调用可能产生费用，请添加 --confirm-paid-run。")
    print(generate_ai_analysis())


if __name__ == "__main__":
    main()
