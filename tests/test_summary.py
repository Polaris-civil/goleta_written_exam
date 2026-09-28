"""单元测试。

运行方式（在项目根目录）：
    python -m unittest discover -v

测试用 tempfile 造临时 CSV，不依赖 examples/ 里的文件，
这样以后改示例数据也不会把测试搞挂。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from expense_tool import (
    CsvFormatError,
    ExpenseToolError,
    format_amount,
    load_expenses,
    render,
    summarize,
)

#: 题目给出的验收用例
ACCEPTANCE_CSV = """date,category,amount
2025-01-02,Food,12.50
2025-01-03,Transit,3.00
2025-02-01,Food,8.50
2025-02-02,Food,-2.00
"""


class TempCsvMixin:
    """把一段 CSV 文本写成临时文件，交给 load_expenses 读取。"""

    def load(self, text, encoding="utf-8-sig"):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding=encoding, newline=""
        ) as handle:
            handle.write(text)
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return load_expenses(path, encoding=encoding)


class AcceptanceTests(TempCsvMixin, unittest.TestCase):
    """验收用例：必须逐字对得上题目给的输出。"""

    def setUp(self):
        self.summary = summarize(self.load(ACCEPTANCE_CSV))

    def test_total(self):
        self.assertEqual(self.summary.total, Decimal("22.00"))

    def test_by_month_sorted_ascending(self):
        self.assertEqual(
            self.summary.by_month,
            {"2025-01": Decimal("15.50"), "2025-02": Decimal("6.50")},
        )

    def test_by_category_sorted_alphabetically(self):
        self.assertEqual(
            self.summary.by_category,
            {"Food": Decimal("19.00"), "Transit": Decimal("3.00")},
        )

    def test_rendered_text_contains_expected_lines(self):
        text = render(self.summary)
        for line in ("总额：22.00", "2025-01：15.50", "2025-02：6.50",
                     "Food：19.00", "Transit：3.00"):
            self.assertIn(line, text)


class AmountFormattingTests(unittest.TestCase):
    def test_two_decimal_places(self):
        self.assertEqual(format_amount(Decimal("15.5")), "15.50")
        self.assertEqual(format_amount(Decimal("22")), "22.00")

    def test_negative_zero_is_not_shown_as_negative(self):
        self.assertEqual(format_amount(Decimal("-0.00")), "0.00")

    def test_rounds_half_up(self):
        self.assertEqual(format_amount(Decimal("0.005")), "0.01")


class LoaderTests(TempCsvMixin, unittest.TestCase):
    def test_header_order_does_not_matter(self):
        expenses = self.load("amount,category,date\n1.00,Food,2025-03-05\n")
        self.assertEqual(expenses[0].category, "Food")
        self.assertEqual(expenses[0].amount, Decimal("1.00"))

    def test_header_is_trimmed_and_case_insensitive(self):
        expenses = self.load(" Date , CATEGORY , Amount \n2025-03-05,Food,1.00\n")
        self.assertEqual(expenses[0].amount, Decimal("1.00"))

    def test_utf8_bom_is_handled(self):
        expenses = self.load("﻿date,category,amount\n2025-03-05,Food,1.00\n")
        self.assertEqual(len(expenses), 1)

    def test_blank_lines_are_skipped(self):
        expenses = self.load(
            "date,category,amount\n\n2025-01-01,Food,1.00\n   ,,\n"
        )
        self.assertEqual(len(expenses), 1)

    def test_currency_symbol_and_thousands_separator(self):
        expenses = self.load("date,category,amount\n2025-01-01,Rent,\"¥1,200.50\"\n")
        self.assertEqual(expenses[0].amount, Decimal("1200.50"))

    def test_alternate_date_formats(self):
        expenses = self.load(
            "date,category,amount\n2025/1/2,A,1\n2025.01.03,B,1\n20250104,C,1\n"
        )
        self.assertEqual([e.month for e in expenses], ["2025-01"] * 3)

    def test_missing_column_raises(self):
        with self.assertRaises(CsvFormatError) as ctx:
            self.load("date,category\n2025-01-01,Food\n")
        self.assertIn("amount", str(ctx.exception))

    def test_bad_amount_reports_line_number(self):
        with self.assertRaises(CsvFormatError) as ctx:
            self.load("date,category,amount\n2025-01-01,Food,abc\n")
        self.assertIn("第 2 行", str(ctx.exception))

    def test_bad_date_reports_line_number(self):
        with self.assertRaises(CsvFormatError) as ctx:
            self.load("date,category,amount\n01/02/2025,Food,1.00\n")
        self.assertIn("第 2 行", str(ctx.exception))

    def test_empty_amount_is_rejected(self):
        with self.assertRaises(CsvFormatError):
            self.load("date,category,amount\n2025-01-01,Food,\n")

    def test_nan_is_rejected(self):
        with self.assertRaises(CsvFormatError):
            self.load("date,category,amount\n2025-01-01,Food,NaN\n")

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            self.load("")

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            load_expenses(os.path.join(tempfile.gettempdir(), "不存在的文件.csv"))


class SummaryEdgeCaseTests(TempCsvMixin, unittest.TestCase):
    def test_header_only_file_gives_zero_total(self):
        summary = summarize(self.load("date,category,amount\n"))
        self.assertEqual(summary.count, 0)
        self.assertEqual(summary.total, Decimal("0"))
        self.assertEqual(summary.by_month, {})
        self.assertIn("总额：0.00", render(summary))
        self.assertIn("（无数据）", render(summary))

    def test_only_refunds_give_negative_total(self):
        summary = summarize(self.load("date,category,amount\n2025-01-01,Food,-5.00\n"))
        self.assertEqual(summary.total, Decimal("-5.00"))
        self.assertIn("总额：-5.00", render(summary))

    def test_same_category_across_months_is_merged(self):
        summary = summarize(
            self.load(
                "date,category,amount\n"
                "2025-01-01,Food,1.00\n"
                "2025-02-01,Food,2.00\n"
            )
        )
        self.assertEqual(summary.by_category, {"Food": Decimal("3.00")})
        self.assertEqual(len(summary.by_month), 2)

    def test_decimals_do_not_drift(self):
        """0.1 + 0.2 用 float 会变成 0.30000000000000004，Decimal 不会。"""
        summary = summarize(
            self.load("date,category,amount\n2025-01-01,A,0.10\n2025-01-02,A,0.20\n")
        )
        self.assertEqual(summary.total, Decimal("0.30"))
        self.assertIn("总额：0.30", render(summary))


if __name__ == "__main__":
    unittest.main(verbosity=2)
