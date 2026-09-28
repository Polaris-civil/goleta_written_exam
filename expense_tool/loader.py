"""CSV 读取与校验层。

只做一件事：把磁盘上的 CSV 变成 List[Expense]。
所有"这份数据不合法"的判断都集中在这里，抛 CsvFormatError；
调用方（cli）负责把它变成一句给用户看的话。
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO, Dict, List

from .errors import CsvFormatError, ExpenseToolError
from .models import Expense

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


def load_expenses(path: str, encoding: str = DEFAULT_ENCODING) -> List[Expense]:
    """读取 CSV 文件并返回支出记录列表。

    参数:
        path: CSV 文件路径
        encoding: 文件编码，默认 utf-8-sig；中文 Windows 上的 GBK 文件请传 "gbk"

    异常:
        ExpenseToolError: 文件不存在、不是文件、编码不对、格式不合法
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


def _parse(handle: IO[str], file_path: Path) -> List[Expense]:
    reader = csv.DictReader(handle)

    if not reader.fieldnames:
        raise ExpenseToolError(
            "文件是空的，连表头都没有：{}\n"
            "第一行应该是表头，例如：date,category,amount".format(file_path)
        )

    header_map = _build_header_map(reader.fieldnames)
    missing = [name for name in REQUIRED_COLUMNS if name not in header_map]
    if missing:
        raise CsvFormatError(
            "表头缺少必需的列：{}。实际读到的列是：{}".format(
                "、".join(missing), "、".join(reader.fieldnames)
            ),
            line_number=1,
        )

    row_reader = _rows(reader, header_map)

    # csv.DictReader 会自己跳过完全空白的行，所以这里拿到的都是有内容的数据行
    expenses = [
        _build_expense(row, line_number)
        for line_number, row in row_reader
        if _has_any_value(row)
    ]

    return expenses


def _rows(reader: csv.DictReader, header_map: Dict[str, str]):
    """按原始行号产出 (line_number, {列名: 原始值})。

    表头占第 1 行，所以数据从第 2 行开始计数。
    """
    for offset, raw_row in enumerate(reader):
        row = {
            name: (raw_row.get(original) or "")
            for name, original in header_map.items()
        }
        yield offset + 2, row


def _build_header_map(fieldnames: List[str]) -> Dict[str, str]:
    """把 '  Date ' / 'date' / '\\ufeffdate' 之类统一成 'date'。

    返回 {归一化列名: 文件里原始的列名}。
    """
    mapping: Dict[str, str] = {}
    for original in fieldnames:
        if original is None:
            continue
        normalized = original.replace("﻿", "").strip().lower()
        if normalized and normalized not in mapping:
            mapping[normalized] = original
    return mapping


def _has_any_value(row: Dict[str, str]) -> bool:
    """整行都是空白（比如 ",," ）时视为空行，直接忽略。"""
    return any(value.strip() for value in row.values())


def _build_expense(row: Dict[str, str], line_number: int) -> Expense:
    raw_date = row["date"].strip()
    raw_category = row["category"].strip()
    raw_amount = row["amount"].strip()

    if not raw_date:
        raise CsvFormatError("date 为空。", line_number=line_number)
    if not raw_category:
        raise CsvFormatError("category 为空。", line_number=line_number)

    return Expense(
        date=_parse_date(raw_date, line_number),
        category=raw_category,
        amount=_parse_amount(raw_amount, line_number),
        line_number=line_number,
    )


def _parse_date(text: str, line_number: int) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise CsvFormatError(
        "date 无法识别：{!r}。支持的写法：2025-01-02、2025/1/2、2025.01.02、20250102".format(
            text
        ),
        line_number=line_number,
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
        raise CsvFormatError("amount 为空。", line_number=line_number)

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise CsvFormatError(
            "amount 不是有效数字：{!r}".format(text), line_number=line_number
        ) from None

    # Decimal("NaN") / Decimal("Infinity") 是能解析成功的，必须挡掉
    if not amount.is_finite():
        raise CsvFormatError(
            "amount 不是有限数字：{!r}".format(text), line_number=line_number
        )

    return amount
