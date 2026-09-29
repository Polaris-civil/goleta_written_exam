"""summary 与 report 两层的测试：汇总计算、金额格式化、文本渲染。"""

from __future__ import annotations

import unittest
from decimal import Decimal

from expense_tool import SkippedRow, format_amount, render, summarize

from .helpers import TempCsvMixin

#: 题目给出的验收用例
ACCEPTANCE_CSV = """date,category,amount
2025-01-02,Food,12.50
2025-01-03,Transit,3.00
2025-02-01,Food,8.50
2025-02-02,Food,-2.00
"""


class AcceptanceTests(TempCsvMixin, unittest.TestCase):
    """验收用例：必须逐字对得上题目给的输出。"""

    def setUp(self):
        self.summary = summarize(self.rows(ACCEPTANCE_CSV))

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


class SummaryEdgeCaseTests(TempCsvMixin, unittest.TestCase):
    def test_header_only_file_gives_zero_total(self):
        summary = summarize(self.rows("date,category,amount\n"))
        self.assertEqual(summary.count, 0)
        self.assertEqual(summary.total, Decimal("0"))
        self.assertEqual(summary.by_month, {})
        self.assertIn("总额：0.00", render(summary))
        self.assertIn("（无数据）", render(summary))

    def test_only_refunds_give_negative_total(self):
        summary = summarize(self.rows("date,category,amount\n2025-01-01,Food,-5.00\n"))
        self.assertEqual(summary.total, Decimal("-5.00"))
        self.assertIn("总额：-5.00", render(summary))

    def test_same_category_across_months_is_merged(self):
        summary = summarize(
            self.rows(
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
            self.rows("date,category,amount\n2025-01-01,A,0.10\n2025-01-02,A,0.20\n")
        )
        self.assertEqual(summary.total, Decimal("0.30"))
        self.assertIn("总额：0.30", render(summary))


class RenderSkippedTests(unittest.TestCase):
    """report 层对被跳过行的展示。"""

    def setUp(self):
        self.summary = summarize([])
        self.skipped = [
            SkippedRow(
                line_number=3,
                reason="date 无法识别：'2025-13-45'",
                column="date",
            ),
            SkippedRow(line_number=5, reason="category 为空。", column="category"),
        ]

    def test_no_skipped_means_no_extra_section(self):
        text = render(self.summary)
        self.assertNotIn("跳过", text)

    def test_skipped_count_is_shown(self):
        self.assertIn("已跳过：2 行", render(self.summary, skipped=self.skipped))

    def test_each_skipped_row_shows_line_number_and_reason(self):
        text = render(self.summary, skipped=self.skipped)
        self.assertIn("第 3 行：date 无法识别：'2025-13-45'", text)
        self.assertIn("第 5 行：category 为空。", text)

    def test_section_states_rows_are_excluded_from_totals(self):
        text = render(self.summary, skipped=self.skipped)
        self.assertIn("跳过的行（共 2 行，未计入上面的汇总）", text)

    def test_accepts_any_iterable(self):
        text = render(self.summary, skipped=iter(self.skipped))
        self.assertIn("已跳过：2 行", text)

    def test_summary_numbers_are_still_rendered_when_skipped_present(self):
        text = render(self.summary, skipped=self.skipped)
        self.assertIn("总额：0.00", text)


class RenderHintTests(unittest.TestCase):
    """末尾的格式提示：按列给一次，不按行重复。"""

    def setUp(self):
        self.summary = summarize([])

    def test_hint_for_date_column(self):
        skipped = [SkippedRow(2, "date 无法识别：'x'", "date")]
        text = render(self.summary, skipped=skipped)
        self.assertIn("提示：", text)
        self.assertIn("2025-01-02", text)

    def test_hint_for_amount_column(self):
        skipped = [SkippedRow(2, "amount 不是有效数字：'x'", "amount")]
        text = render(self.summary, skipped=skipped)
        self.assertIn("负数表示退款", text)

    def test_hint_appears_once_per_column_not_per_row(self):
        skipped = [
            SkippedRow(2, "date 无法识别：'x'", "date"),
            SkippedRow(3, "date 无法识别：'y'", "date"),
            SkippedRow(4, "date 无法识别：'z'", "date"),
        ]
        text = render(self.summary, skipped=skipped)
        self.assertEqual(text.count("2025-01-02"), 1)

    def test_no_hint_for_category_only(self):
        """category 为空的原因本身已经说清楚了，不必再补提示。"""
        skipped = [SkippedRow(2, "category 为空。", "category")]
        text = render(self.summary, skipped=skipped)
        self.assertNotIn("提示：", text)

    def test_no_hint_when_column_is_unknown(self):
        skipped = [SkippedRow(2, "某种未知问题", "")]
        text = render(self.summary, skipped=skipped)
        self.assertNotIn("提示：", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
