"""P0-3 复现测试：src/ 下不允许存在遮蔽标准库的模块名。

main.py / api/index.py 都会把 src/ 插到 sys.path 最前面，
此时 `import statistics` 拿到的必须仍是 Python 标准库，
而项目自己的统计模块要换一个不冲突的名字（expense_statistics）。
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


def test_no_stdlib_shadowing() -> None:
    # 在"src/ 排在 sys.path 首位"的运行环境里检查 statistics 的来源
    code = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "import statistics\n"
        "assert hasattr(statistics, 'mean'), (\n"
        "    'statistics 被本地模块遮蔽：' + statistics.__file__)\n"
        "import expense_statistics\n"
        "assert hasattr(expense_statistics, 'generate_statistics')\n"
        "print('OK')\n" % SRC_DIR
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0 and "OK" in result.stdout, (
        result.stdout + result.stderr
    )
    print("STDLIB_SHADOW_TEST=PASS")


if __name__ == "__main__":
    test_no_stdlib_shadowing()
