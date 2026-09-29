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
from .filters import (
    DATE_ARGUMENT_FORMAT,
    FilterSet,
    build_category_filter,
    build_date_range,
)
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
            "  python run.py 账单.csv --start 2025-01-01 --end 2025-01-31\n"
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

    # 日期筛选。开始和结束日期都计入结果（闭区间）。
    # 用 --start/--end 而不是 --from/--to：from 是 Python 关键字，
    # 会让 args.from 直接成为语法错误，将来维护容易踩坑。
    parser.add_argument(
        "--start",
        metavar=DATE_ARGUMENT_FORMAT,
        default=None,
        help="只统计这一天及之后的记录（含当天），格式 {}".format(
            DATE_ARGUMENT_FORMAT
        ),
    )
    parser.add_argument(
        "--end",
        metavar=DATE_ARGUMENT_FORMAT,
        default=None,
        help="只统计这一天及之前的记录（含当天），格式 {}".format(
            DATE_ARGUMENT_FORMAT
        ),
    )

    # 类别筛选。用 append 支持多次传，不用逗号分隔：
    # CSV 里的类别名本身可能含逗号（比如 "Food, Dining"），
    # 按逗号切会把一个类别名劈成两个，静默筛错。
    parser.add_argument(
        "--category",
        metavar="NAME",
        action="append",
        default=None,
        help="只统计指定类别的记录；可重复传多个，如 --category Food --category Transit",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """程序主流程。返回进程退出码。"""
    # 必须在 parse_args 之前调用：--help 和参数报错都是 argparse 在
    # parse_args 内部直接打印并退出的，那时这个函数还没机会跑。
    configure_output_encoding()

    args = build_parser().parse_args(argv)

    # 所有"用户能自己修好"的问题都在这里被挡住，一律打印一行中文说明并返回 1，
    # 不会有 traceback 漏给用户：
    #   - 日期参数格式不对 / 开始日期晚于结束日期 / 日期参数传了空值
    #   - --category 传了空值 / 指定的类别在文件里不存在
    #   - 文件不存在、编码不对、表头缺列等结构性错误
    # 单个数据行的格式问题已在 loader 里被跳过，不会抛到这里。
    try:
        filters = FilterSet(
            date_range=build_date_range(args.start, args.end),
            categories=build_category_filter(args.category),
        )
        result = load_expenses(args.csv_file, encoding=args.encoding)
        # 拿筛选前的全部有效记录来校验类别名，避免"日期把某类别筛没了"
        # 被误判成用户把类别名拼错了
        filters.validate_against(result.expenses)
        # 总额、按月汇总、按类别汇总都基于这一批记录，三者天然一致
        summary = summarize(filters.filter(result.expenses))
    except ExpenseToolError as exc:
        print("错误：{}".format(exc), file=sys.stderr)
        return 1

    print(
        render(
            summary,
            source=args.csv_file,
            skipped=result.skipped,
            filters=filters,
        )
    )
    # 有跳过的行也返回 0：用户要的是"别崩、照常出汇总"，
    # 跳过的行已经在输出里如实汇报了。
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
