"""CSV 读取与校验层。

只做一件事：把磁盘上的 CSV 变成 List[Expense]（外加一份"被跳过的行"清单）。

错误分两个层级处理，这是本文件最重要的约定：

1. **结构性错误**（文件不存在、编码不对、没有表头、表头缺列）
   —— 抛 ExpenseToolError，交给 cli 报错退出。这类问题下一行数据都读不出来，
   没有什么可汇总的。

2. **行级错误**（日期格式不对、金额不是数字、类别为空……）
   —— 只影响这一行。捕获后记成 SkippedRow，跳过它继续读下一行。
   程序不会崩，其余有效行照常汇总，最后把跳过的行号、原因和总数汇报给用户。

这样设计的原因：真实的账单文件里常常混着几行脏数据，为了它们让整份报表
跑不出来，对用户没有帮助。但也不能默默丢掉——那样用户会以为总额是完整的。
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO, Dict, List, Optional

from .errors import CsvFormatError, ExpenseToolError
from .models import Expense, LoadResult, SkippedRow

#: CSV 必须包含的列（顺序不限，大小写和前后空格都会被容忍）
REQUIRED_COLUMNS = ("date", "category", "amount")

#: 默认编码。utf-8-sig 既能读带 BOM 的 UTF-8（Excel 另存为 CSV 常见），
#: 也能读普通 UTF-8。
DEFAULT_ENCODING = "utf-8-sig"

#: 支持的日期写法，按顺序尝试
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d")

#: 金额里允许出现、解析前会被去掉的货币符号
_CURRENCY_SYMBOLS = ("¥", "￥", "$", "€", "£")

#: 千分位分隔符（中英文逗号都去掉）
_THOUSAND_SEPARATORS = (",", "，")


def load_expenses(path: str, encoding: str = DEFAULT_ENCODING) -> LoadResult:
    """读取 CSV 文件，返回 LoadResult（有效记录 + 被跳过的行）。

    参数:
        path: CSV 文件路径
        encoding: 文件编码，默认 utf-8-sig；中文 Windows 上的 GBK 文件请传 "gbk"

    返回:
        LoadResult。其中 result.expenses 是解析成功的记录，
        result.skipped 是无法解析、已被跳过的行（含行号和原因）。

    异常:
        ExpenseToolError: 文件不存在、不是文件、编码不对、没有表头、表头缺列。
            注意：单个数据行的格式问题**不会**抛异常，而是记入 result.skipped。
    """
    file_path = Path(path)

    if not file_path.exists():
        raise ExpenseToolError("找不到文件：{}".format(file_path))
    if file_path.is_dir():
        raise ExpenseToolError(
            "{} 是一个目录，不是 CSV 文件。请指定具体的 .csv 文件。".format(file_path)
        )

    try:
        with file_path.open("r", encoding=encoding, newline="") as handle:
            return _parse(handle, file_path)
    except UnicodeDecodeError as exc:
        raise ExpenseToolError(
            "无法用编码 {!r} 读取 {}\n"
            "提示：Windows 上由 Excel 另存为的 CSV 常见编码是 GBK，"
            "可以试试  --encoding gbk".format(encoding, file_path)
        ) from exc
    except OSError as exc:
        raise ExpenseToolError("读取文件失败：{}".format(exc)) from exc


def _parse(handle: IO[str], file_path: Path) -> LoadResult:
    """逐条读 CSV，返回有效记录和被跳过的行。

    ## 行号是怎么算准的

    不能用 enumerate + 2 来数行号，因为那个数的是"第几条记录"而不是"文件第几行"，
    有两种情况会偏：

    1. 中间夹着空白行 —— csv.DictReader 会悄悄跳过它们，但它们在文件里占着行号；
    2. 字段里含换行符（带引号的多行字段）—— 一条记录横跨多个物理行。

    这里改用 csv.reader 的 line_num。它的语义是"到目前为止从文件里消费掉的物理行数"，
    而且实测确认它**不预读**（读取一条记录时只会消费刚好够用的那些行）。
    于是：本条记录消费的物理行区间是 [上一条结束行 + 1, reader.line_num]，
    区间起点就是这条记录在文件里的起始行号，两种情况都能算对。

    表头那一行也用同样的方法定位，所以文件开头有空白行时也能报对。
    """
    reader = csv.reader(handle)

    # --- 定位表头：跳过文件开头的空白行 ---
    header_row = _find_header_row(reader)
    if header_row is None:
        raise ExpenseToolError(
            "文件是空的，连表头都没有：{}\n"
            "第一行应该是表头，例如：date,category,amount".format(file_path)
        )
    header_line = reader.line_num

    # --- 结构性检查：过不了就没法继续，直接抛给 cli ---
    columns = _build_column_index(header_row)
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise CsvFormatError(
            "表头缺少必需的列：{}。实际读到的列是：{}".format(
                "、".join(missing), "、".join(header_row)
            ),
            line_number=header_line,
        )

    # --- 逐条读：单条有问题就跳过，不影响其它记录 ---
    expenses: List[Expense] = []
    skipped: List[SkippedRow] = []

    # 已经消费掉的物理行数；下一条记录的起始行号 = 它 + 1
    consumed = reader.line_num

    for row in reader:
        start_line = consumed + 1
        consumed = reader.line_num

        if not _has_any_value(row):
            # 整条都是空白（比如 ",," ），不是数据错误，静默忽略、不计入跳过数
            continue

        try:
            expenses.append(_build_expense(row, columns, start_line))
        except CsvFormatError as exc:
            # exc.reason 是不带"第 N 行："前缀的纯原因
            skipped.append(
                SkippedRow(
                    line_number=start_line,
                    reason=exc.reason,
                    column=exc.column or "",
                )
            )

    return LoadResult(expenses=expenses, skipped=skipped)


def _find_header_row(reader: "csv.reader") -> Optional[List[str]]:
    """找到第一行非空白的记录当表头。整份文件都空白时返回 None。"""
    for row in reader:
        if _has_any_value(row):
            return row
    return None


def _build_column_index(header_row: List[str]) -> Dict[str, int]:
    """把 '  Date ' / 'date' / '\\ufeffdate' 之类统一成 'date'。

    返回 {归一化列名: 它在行里的下标}。同名列只认第一次出现的位置。
    """
    index: Dict[str, int] = {}
    for position, original in enumerate(header_row):
        if original is None:
            continue
        normalized = original.replace("﻿", "").strip().lower()
        if normalized and normalized not in index:
            index[normalized] = position
    return index


def _has_any_value(row: List[str]) -> bool:
    """整条记录都是空白（比如空白行、",," ）时视为无内容，直接忽略。"""
    return any((cell or "").strip() for cell in row)


def _cell(row: List[str], columns: Dict[str, int], name: str) -> str:
    """取某一列的值。

    行比表头短时（例如只有 "2025-01-02,Food" 少了金额列），
    按空字符串处理，让后续的空值校验给出"amount 为空"这样准确的提示，
    而不是抛 IndexError。
    """
    position = columns[name]
    if position >= len(row):
        return ""
    return (row[position] or "").strip()


def _build_expense(
    row: List[str], columns: Dict[str, int], line_number: int
) -> Expense:
    """把一条原始记录变成 Expense；有任何问题就抛 CsvFormatError。

    按 date -> category -> amount 的列顺序校验，并且**只报第一个问题**。
    这样一条记录里有多处错误时，用户看到的是最左边那个，符合从左往右读的习惯；
    剩下的问题修完第一个再跑一次就会浮现出来。
    """
    raw_date = _cell(row, columns, "date")
    raw_category = _cell(row, columns, "category")
    raw_amount = _cell(row, columns, "amount")

    if not raw_date:
        raise CsvFormatError("date 为空。", line_number=line_number, column="date")
    parsed_date = _parse_date(raw_date, line_number)

    if not raw_category:
        raise CsvFormatError(
            "category 为空。", line_number=line_number, column="category"
        )

    parsed_amount = _parse_amount(raw_amount, line_number)

    return Expense(
        date=parsed_date,
        category=raw_category,
        amount=parsed_amount,
        line_number=line_number,
    )


def _parse_date(text: str, line_number: int) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # 这里只说"错在哪"，不重复列支持的格式——那属于提示，
    # 由 report 层在末尾统一给一次，否则坏行多的时候会刷屏
    raise CsvFormatError(
        "date 无法识别：{!r}".format(text),
        line_number=line_number,
        column="date",
    )


def _parse_amount(text: str, line_number: int) -> Decimal:
    """把金额字符串转成 Decimal。

    用 Decimal 而不是 float，是为了避免 0.1 + 0.2 = 0.30000000000000004
    这类浮点误差——算钱必须精确。
    """
    cleaned = text
    for symbol in _CURRENCY_SYMBOLS:
        if cleaned.startswith(symbol):
            cleaned = cleaned[len(symbol):]
    for separator in _THOUSAND_SEPARATORS:
        cleaned = cleaned.replace(separator, "")
    cleaned = cleaned.strip()

    if not cleaned:
        raise CsvFormatError("amount 为空。", line_number=line_number, column="amount")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise CsvFormatError(
            "amount 不是有效数字：{!r}".format(text),
            line_number=line_number,
            column="amount",
        ) from None

    # Decimal("NaN") / Decimal("Infinity") 是能解析成功的，必须挡掉
    if not amount.is_finite():
        raise CsvFormatError(
            "amount 不是有限数字：{!r}".format(text),
            line_number=line_number,
            column="amount",
        )

    return amount
