"""测试公用的小工具。

用临时文件而不是往 examples/ 里塞测试数据，这样以后改示例文件
不会把测试搞挂，测试之间也不会互相污染。
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from typing import List, Tuple

from expense_tool import load_expenses
from expense_tool.cli import main as cli_main


def write_temp_csv(case, text: str, encoding: str = "utf-8-sig") -> str:
    """把一段 CSV 文本写成临时文件并返回路径，测试结束自动删除。

    参数 case 是 unittest.TestCase 实例，用来注册清理函数。
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, encoding=encoding, newline=""
    ) as handle:
        handle.write(text)
        path = handle.name

    def cleanup():
        if os.path.exists(path):
            os.unlink(path)

    case.addCleanup(cleanup)
    return path


class TempCsvMixin:
    """给测试用例提供 load() / rows() 两个便捷方法。"""

    def load(self, text: str, encoding: str = "utf-8-sig"):
        """返回完整的 LoadResult（含 expenses 和 skipped）。"""
        path = write_temp_csv(self, text, encoding=encoding)
        return load_expenses(path, encoding=encoding)

    def rows(self, text: str, encoding: str = "utf-8-sig"):
        """只返回解析成功的记录列表，用于不关心跳过行的测试。"""
        return self.load(text, encoding=encoding).expenses


def run_cli(*argv: str) -> Tuple[int, str, str]:
    """在进程内跑一次命令行，返回 (退出码, stdout, stderr)。

    比开子进程快得多，也能直接断言退出码。
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = cli_main(list(argv))
        except SystemExit as exc:  # argparse 在参数错误时会 sys.exit
            code = int(exc.code or 0)
    return code, stdout.getvalue(), stderr.getvalue()


def lines_of(text: str) -> List[str]:
    return text.splitlines()
