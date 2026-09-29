"""loader 层的测试：CSV 读取、表头校验、行级错误的跳过。"""

from __future__ import annotations

import os
import tempfile
import unittest
from decimal import Decimal

from expense_tool import ExpenseToolError, CsvFormatError, load_expenses

from .helpers import TempCsvMixin, write_temp_csv


class HeaderTests(TempCsvMixin, unittest.TestCase):
    """表头相关：这些是结构性错误，必须直接报错，不能跳过。"""

    def test_header_order_does_not_matter(self):
        rows = self.rows("amount,category,date\n1.00,Food,2025-03-05\n")
        self.assertEqual(rows[0].category, "Food")
        self.assertEqual(rows[0].amount, Decimal("1.00"))

    def test_header_is_trimmed_and_case_insensitive(self):
        rows = self.rows(" Date , CATEGORY , Amount \n2025-03-05,Food,1.00\n")
        self.assertEqual(rows[0].amount, Decimal("1.00"))

    def test_utf8_bom_is_handled(self):
        rows = self.rows("﻿date,category,amount\n2025-03-05,Food,1.00\n")
        self.assertEqual(len(rows), 1)

    def test_missing_column_raises(self):
        with self.assertRaises(CsvFormatError) as ctx:
            self.load("date,category\n2025-01-01,Food\n")
        self.assertIn("amount", str(ctx.exception))

    def test_missing_column_is_not_swallowed_as_skipped(self):
        """表头缺列时不能"全跳过"了事——那样用户会拿到一份空报表。"""
        with self.assertRaises(CsvFormatError):
            self.load("date,category\n2025-01-01,Food\n")

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            self.load("")

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            load_expenses(os.path.join(tempfile.gettempdir(), "不存在的文件.csv"))

    def test_directory_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            load_expenses(tempfile.gettempdir())


class ValueParsingTests(TempCsvMixin, unittest.TestCase):
    """各类合法写法的解析。"""

    def test_blank_lines_are_silently_ignored(self):
        result = self.load("date,category,amount\n\n2025-01-01,Food,1.00\n   ,,\n")
        self.assertEqual(len(result.expenses), 1)
        # 空白行不算"错误行"，不该出现在跳过清单里
        self.assertEqual(result.skipped, [])

    def test_currency_symbol_and_thousands_separator(self):
        rows = self.rows('date,category,amount\n2025-01-01,Rent,"¥1,200.50"\n')
        self.assertEqual(rows[0].amount, Decimal("1200.50"))

    def test_alternate_date_formats(self):
        rows = self.rows(
            "date,category,amount\n2025/1/2,A,1\n2025.01.03,B,1\n20250104,C,1\n"
        )
        self.assertEqual([e.month for e in rows], ["2025-01"] * 3)


class SkippedRowTests(TempCsvMixin, unittest.TestCase):
    """行级错误：跳过 + 记录行号 + 记录原因，其余行照常汇总。"""

    def test_bad_date_is_skipped(self):
        result = self.load(
            "date,category,amount\n2025-13-45,Food,9.90\n2025-01-02,Food,1.00\n"
        )
        self.assertEqual(len(result.expenses), 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.skipped[0].line_number, 2)
        self.assertIn("date 无法识别", result.skipped[0].reason)

    def test_bad_amount_is_skipped(self):
        result = self.load("date,category,amount\n2025-01-02,Food,abc\n")
        self.assertEqual(result.expenses, [])
        self.assertEqual(result.skipped[0].line_number, 2)
        self.assertIn("amount 不是有效数字", result.skipped[0].reason)

    def test_empty_category_is_skipped(self):
        result = self.load("date,category,amount\n2025-01-02,,1.00\n")
        self.assertEqual(result.skipped[0].line_number, 2)
        self.assertIn("category 为空", result.skipped[0].reason)

    def test_empty_date_is_skipped(self):
        result = self.load("date,category,amount\n,Food,1.00\n")
        self.assertIn("date 为空", result.skipped[0].reason)

    def test_empty_amount_is_skipped(self):
        result = self.load("date,category,amount\n2025-01-02,Food,\n")
        self.assertIn("amount 为空", result.skipped[0].reason)

    def test_nan_is_skipped(self):
        result = self.load("date,category,amount\n2025-01-02,Food,NaN\n")
        self.assertIn("不是有限数字", result.skipped[0].reason)

    def test_infinity_is_skipped(self):
        result = self.load("date,category,amount\n2025-01-02,Food,Infinity\n")
        self.assertEqual(result.skipped_count, 1)

    def test_line_numbers_are_correct_with_multiple_bad_rows(self):
        result = self.load(
            "date,category,amount\n"      # 第 1 行（表头）
            "2025-01-02,Food,1.00\n"      # 第 2 行 正常
            "bad-date,Food,2.00\n"        # 第 3 行 坏
            "2025-01-04,Transit,3.00\n"   # 第 4 行 正常
            "2025-01-05,,4.00\n"          # 第 5 行 坏
            "2025-01-06,Food,xyz\n"       # 第 6 行 坏
        )
        self.assertEqual(len(result.expenses), 2)
        self.assertEqual([s.line_number for s in result.skipped], [3, 5, 6])

    def test_valid_rows_after_bad_rows_are_still_loaded(self):
        result = self.load(
            "date,category,amount\n"
            "2025-01-02,Food,bad\n"
            "2025-01-03,Transit,3.00\n"
        )
        self.assertEqual(len(result.expenses), 1)
        self.assertEqual(result.expenses[0].category, "Transit")

    def test_all_rows_bad_yields_empty_but_no_exception(self):
        result = self.load("date,category,amount\nx,,\ny,,\n")
        self.assertEqual(result.expenses, [])
        self.assertEqual(result.skipped_count, 2)

    def test_header_only_file_has_no_skipped(self):
        result = self.load("date,category,amount\n")
        self.assertEqual(result.expenses, [])
        self.assertEqual(result.skipped, [])

    def test_skipped_row_reason_has_no_line_prefix(self):
        """reason 存的是纯原因，行号单独放在 line_number 里，方便调用方自己排版。"""
        result = self.load("date,category,amount\n2025-01-02,Food,abc\n")
        self.assertNotIn("第 2 行", result.skipped[0].reason)

    def test_failing_column_is_recorded(self):
        """记下是哪一列出错，report 层才能按列给一次性的格式提示。"""
        result = self.load(
            "date,category,amount\n"
            "bad,Food,1.00\n"
            "2025-01-02,,1.00\n"
            "2025-01-03,Food,abc\n"
        )
        self.assertEqual([s.column for s in result.skipped],
                         ["date", "category", "amount"])

    def test_reason_does_not_repeat_the_format_hint(self):
        """原因只说错在哪；格式提示由 report 层统一给，避免坏行多时刷屏。"""
        result = self.load("date,category,amount\n2025-13-45,Food,1.00\n")
        self.assertNotIn("支持的写法", result.skipped[0].reason)

    def test_reports_leftmost_problem_first(self):
        """一行里多处出错时，报最左边那列——符合从左往右读的习惯。"""
        result = self.load("date,category,amount\nx,,abc\n")
        self.assertEqual(result.skipped[0].column, "date")
        self.assertIn("date 无法识别", result.skipped[0].reason)

        # 日期修好后，category 的问题才会浮现
        result = self.load("date,category,amount\n2025-01-02,,abc\n")
        self.assertEqual(result.skipped[0].column, "category")

    def test_only_first_problem_is_reported_per_row(self):
        """一行只产生一条跳过记录，不是每列都记一条。"""
        result = self.load("date,category,amount\nx,,abc\n")
        self.assertEqual(result.skipped_count, 1)

    def test_gbk_file_can_be_read(self):
        text = "date,category,amount\n2025-03-01,餐饮,88.80\n"
        result = self.load(text, encoding="gbk")
        self.assertEqual(result.expenses[0].category, "餐饮")


class PhysicalLineNumberTests(TempCsvMixin, unittest.TestCase):
    """报出的行号必须对得上文件里真实的物理行。

    这些用例不用"第几条记录"来算预期值，而是把文件读成物理行数组，
    再用报出的行号去取那一行，检查内容确实是那条坏记录。
    只有这样才能真正证明行号没偏。
    """

    def assert_line_numbers(self, csv_text, expected):
        """expected: [(行号, 该行应包含的标记), ...]"""
        path = write_temp_csv(self, csv_text)
        result = load_expenses(path)

        with open(path, encoding="utf-8-sig", newline="") as handle:
            physical = handle.read().splitlines()

        actual = [
            (item.line_number, physical[item.line_number - 1])
            for item in result.skipped
        ]
        self.assertEqual(len(actual), len(expected))
        for (got_number, got_text), (want_number, want_marker) in zip(
            actual, expected
        ):
            self.assertEqual(
                got_number,
                want_number,
                "行号不对：拿到第 {} 行（{!r}），应该是第 {} 行".format(
                    got_number, got_text, want_number
                ),
            )
            self.assertIn(want_marker, got_text)

    def test_blank_lines_do_not_shift_line_numbers(self):
        """中间夹着空白行时，行号要按物理行算，不能按记录序号算。"""
        self.assert_line_numbers(
            "date,category,amount\n"       # 1 表头
            "2025-01-02,Food,1.00\n"       # 2 正常
            "\n"                           # 3 空白行
            "bad-a,Food,2.00\n"            # 4 坏 -> 之前会误报成第 3 行
            "\n"                           # 5 空白行
            "\n"                           # 6 空白行
            "2025-01-04,Transit,3.00\n"    # 7 正常
            "bad-b,Food,4.00\n",           # 8 坏 -> 之前会误报成第 5 行
            [(4, "bad-a"), (8, "bad-b")],
        )

    def test_multiline_quoted_fields_do_not_shift_line_numbers(self):
        """字段里含换行（一条记录跨多个物理行）时，行号同样要算对。"""
        self.assert_line_numbers(
            "date,category,amount\n"            # 1 表头
            '2025-01-02,"Food\nnote",1.00\n'    # 2-3 正常，跨两行
            "bad-a,Food,2.00\n"                 # 4   坏
            '2025-01-04,"Transit\nx\ny",3.00\n' # 5-7 正常，跨三行
            "bad-b,Food,4.00\n",                # 8   坏
            [(4, "bad-a"), (8, "bad-b")],
        )

    def test_blank_lines_and_multiline_fields_together(self):
        self.assert_line_numbers(
            "date,category,amount\n"            # 1
            "\n"                                # 2 空白
            '2025-01-02,"Food\nnote",1.00\n'    # 3-4 正常
            "bad-a,Food,2.00\n"                 # 5   坏
            "\n"                                # 6 空白
            "bad-b,Food,3.00\n",                # 7   坏
            [(5, "bad-a"), (7, "bad-b")],
        )

    def test_leading_blank_lines_before_header(self):
        """文件开头有空白行时，数据行号也要对。"""
        self.assert_line_numbers(
            "\n"                                # 1 空白
            "\n"                                # 2 空白
            "date,category,amount\n"            # 3 表头
            "bad-a,Food,1.00\n",                # 4 坏
            [(4, "bad-a")],
        )

    def test_missing_column_error_reports_header_line(self):
        """表头缺列时，报的也应该是表头的真实行号，不是写死的 1。"""
        path = write_temp_csv(
            self, "\n\ndate,category\n2025-01-01,Food\n"
        )
        with self.assertRaises(CsvFormatError) as ctx:
            load_expenses(path)
        self.assertEqual(ctx.exception.line_number, 3)

    def test_trailing_short_row_reports_correct_line(self):
        """行比表头短（少了列）要按"该列为空"处理，行号同样要对。"""
        path = write_temp_csv(
            self,
            "date,category,amount\n"      # 1
            "2025-01-02,Food,1.00\n"      # 2 正常
            "\n"                          # 3 空白
            "2025-01-03,Transit\n",       # 4 少了 amount
        )
        result = load_expenses(path)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.skipped[0].line_number, 4)
        self.assertIn("amount 为空", result.skipped[0].reason)

    def test_valid_rows_after_all_that_still_summarize(self):
        """行号修准之后，汇总行为必须保持不变。"""
        path = write_temp_csv(
            self,
            "date,category,amount\n"
            "\n"
            "2025-01-02,Food,12.50\n"
            "bad,Food,9.90\n"
            '2025-01-03,"Transit\nx",3.00\n'
            "2025-02-01,Food,8.50\n"
            "2025-02-02,Food,-2.00\n",
        )
        result = load_expenses(path)

        self.assertEqual(len(result.expenses), 4)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(sum(e.amount for e in result.expenses), Decimal("22.00"))


class EncodingTests(TempCsvMixin, unittest.TestCase):
    def test_wrong_encoding_gives_helpful_error(self):
        """用 UTF-8 去读 GBK 文件时，报错信息里要提示可以试 --encoding gbk。"""
        from .helpers import write_temp_csv

        path = write_temp_csv(
            self, "date,category,amount\n2025-03-01,餐饮,1.00\n", encoding="gbk"
        )
        with self.assertRaises(ExpenseToolError) as ctx:
            load_expenses(path, encoding="utf-8")
        self.assertIn("gbk", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
