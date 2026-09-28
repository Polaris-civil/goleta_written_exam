"""命令行入口层。

负责三件事，且只负责这三件事：
1. 解析命令行参数；
2. 依次调用 loader -> summary -> report；
3. 把异常变成人话，并返回退出码。

退出码约定：
    0  成功
    1  数据/文件问题（文件不存在、CSV 格式错误……）
    2  命令行参数用法错误（argparse 自动处理）
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .console import configure_output_encoding
from .errors import ExpenseToolError
from .loader import DEFAULT_ENCODING, load_expenses
from .report import render
from .summary import summarize

PROGRAM_NAME = "expense-summary"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="家庭支出汇总工具：读取本地 CSV 文件，汇总总额、每月金额和每类金额。",
        epilog=(
            "示例：\n"
            "  python run.py examples/sample_expenses.csv\n"
            "  python run.py D:/账单/2025.csv --encoding gbk\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "csv_file",
        help="要读取的 CSV 文件路径，必须包含 date、category、amount 三列",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        default=DEFAULT_ENCODING,
        help="CSV 文件编码（默认 {}；Excel 导出的中文文件通常需要 gbk）".format(
            DEFAULT_ENCODING
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """程序主流程。返回进程退出码。"""
    # 必须在 parse_args 之前调用：--help 和参数报错都是 argparse 在
    # parse_args 内部直接打印并退出的，那时这个函数还没机会跑。
    configure_output_encoding()

    args = build_parser().parse_args(argv)

    try:
        expenses = load_expenses(args.csv_file, encoding=args.encoding)
    except ExpenseToolError as exc:
        print("错误：{}".format(exc), file=sys.stderr)
        return 1

    summary = summarize(expenses)
    print(render(summary, source=args.csv_file))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
