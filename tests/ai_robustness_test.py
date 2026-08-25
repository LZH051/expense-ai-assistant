"""AI 调用健壮性测试：超时/重试/降级/token 用量记录。

要求：
1. 瞬时故障（连接错误）自动重试，第三次成功则正常返回，
   并把 response.usage 的 token 消耗追加到 ai_usage.jsonl；
2. 持续故障时不抛异常，降级返回已有的旧分析结果（不覆盖旧文件）；
3. 非瞬时故障（如认证失败）不做无意义重试，只调用一次。
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ai_analysis


def make_response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=120, completion_tokens=80, total_tokens=200
        ),
    )


class StubClient:
    def __init__(self, failures: list[Exception], reply: str = "分析结果"):
        self.failures = list(failures)
        self.reply = reply
        self.attempts = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **_kwargs):
        self.attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        return make_response(self.reply)


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://example.com")
    )


def auth_error() -> openai.AuthenticationError:
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(401, request=request, json={"error": "bad key"})
    return openai.AuthenticationError(
        "invalid key", response=response, body=None
    )


def setup_files(workdir: Path) -> None:
    stats = workdir / "statistics.json"
    stats.write_text('{"category_summary": []}', encoding="utf-8")
    ai_analysis.STATISTICS_JSON_FILE = stats
    ai_analysis.AI_ANALYSIS_FILE = workdir / "ai_analysis.txt"
    ai_analysis.AI_USAGE_FILE = workdir / "ai_usage.jsonl"


def main() -> None:
    os.environ.update(
        AI_API_KEY="test-key", AI_BASE_URL="https://example.com", AI_MODEL="m"
    )

    # 场景1：失败两次后成功 → 重试生效 + usage 落盘
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        setup_files(workdir)
        stub = StubClient([connection_error(), connection_error()])
        result = ai_analysis.generate_ai_analysis(
            client_factory=lambda: stub, retry_base_delay=0
        )
        assert result == "分析结果", result
        assert stub.attempts == 3, f"应重试到第3次成功，实际调用 {stub.attempts} 次"
        usage_lines = ai_analysis.AI_USAGE_FILE.read_text("utf-8").splitlines()
        assert len(usage_lines) == 1, usage_lines
        usage = json.loads(usage_lines[0])
        assert usage["total_tokens"] == 200 and usage["model"] == "m", usage
        assert ai_analysis.AI_ANALYSIS_FILE.read_text("utf-8") == "分析结果"

    # 场景2：持续故障 → 不抛异常，返回旧结果且不覆盖
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        setup_files(workdir)
        ai_analysis.AI_ANALYSIS_FILE.write_text("旧分析", encoding="utf-8")
        stub = StubClient([connection_error()] * 10)
        result = ai_analysis.generate_ai_analysis(
            client_factory=lambda: stub, retry_base_delay=0
        )
        assert "旧分析" in result, result
        assert ai_analysis.AI_ANALYSIS_FILE.read_text("utf-8") == "旧分析"
        assert stub.attempts == 3, f"重试上限应为3次，实际 {stub.attempts}"
        assert not ai_analysis.AI_USAGE_FILE.exists()

    # 场景3：认证失败属非瞬时故障 → 只调用一次，不重试
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        setup_files(workdir)
        stub = StubClient([auth_error()] * 10)
        result = ai_analysis.generate_ai_analysis(
            client_factory=lambda: stub, retry_base_delay=0
        )
        assert "暂不可用" in result, result
        assert stub.attempts == 1, f"认证失败不应重试，实际 {stub.attempts} 次"

    print("AI_ROBUSTNESS_TEST=PASS")


if __name__ == "__main__":
    main()
