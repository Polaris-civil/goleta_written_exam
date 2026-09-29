"""filters 层的测试：日期参数校验和范围筛选。"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from expense_tool import (
    CategoryFilter,
    DateRange,
    Expense,
    ExpenseToolError,
    FilterSet,
    build_category_filter,
    build_date_range,
)
from expense_tool.filters import parse_date_argument


def expense_on(year, month, day, amount="1.00", category="Food"):
    return Expense(
        date=date(year, month, day), category=category, amount=Decimal(amount)
    )


class ParseDateArgumentTests(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(
            parse_date_argument("2025-01-02", "--start"), date(2025, 1, 2)
        )

    def test_rejects_single_digit_month_or_day(self):
        """命令行接口比 CSV 里的日期严格：必须写足两位，避免 2025-1-2 / 2025-01-2 混用。"""
        for text in ("2025-1-2", "2025-01-2", "2025-1-02"):
            with self.assertRaises(ExpenseToolError):
                parse_date_argument(text, "--start")

    def test_rejects_other_separators(self):
        for text in ("2025/01/02", "2025.01.02", "20250102"):
            with self.assertRaises(ExpenseToolError):
                parse_date_argument(text, "--start")

    def test_rejects_nonexistent_date(self):
        for text in ("2025-02-30", "2025-13-01", "2025-00-10", "2025-01-32"):
            with self.assertRaises(ExpenseToolError):
                parse_date_argument(text, "--end")

    def test_rejects_garbage(self):
        for text in ("abc", "2025", "2025-01", " 2025-01-02 ", "-"):
            with self.assertRaises(ExpenseToolError):
                parse_date_argument(text, "--start")

    def test_error_message_names_the_option(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            parse_date_argument("02/01/2025", "--end")
        self.assertIn("--end", str(ctx.exception))
        self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_nonexistent_date_message_differs_from_format_message(self):
        """格式错和日期不存在要分开说，否则用户不知道该改什么。"""
        with self.assertRaises(ExpenseToolError) as fmt:
            parse_date_argument("2025/01/02", "--start")
        with self.assertRaises(ExpenseToolError) as real:
            parse_date_argument("2025-02-30", "--start")
        self.assertNotEqual(str(fmt.exception), str(real.exception))


class EmptyArgumentTests(unittest.TestCase):
    """空字符串 ≠ 没传。

    `--start ""` 是"用户传了个空值"，必须报错；
    只有选项压根没出现（None）才是不筛选。
    早先 build_date_range 用 `if start_text` 判断，把这两种情况混为一谈，
    结果是敲错了参数却拿到一份没筛选的报表，而且看不出哪里不对。
    """

    def test_empty_string_is_rejected(self):
        with self.assertRaises(ExpenseToolError):
            parse_date_argument("", "--start")

    def test_whitespace_only_is_rejected(self):
        for text in (" ", "   ", "\t", "\n"):
            with self.assertRaises(ExpenseToolError):
                parse_date_argument(text, "--end")

    def test_empty_string_message_is_clear(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            parse_date_argument("", "--start")
        message = str(ctx.exception)
        self.assertIn("--start", message)
        self.assertIn("YYYY-MM-DD", message)
        self.assertIn("空", message)

    def test_build_date_range_rejects_empty_start(self):
        with self.assertRaises(ExpenseToolError):
            build_date_range("", None)

    def test_build_date_range_rejects_empty_end(self):
        with self.assertRaises(ExpenseToolError):
            build_date_range(None, "")

    def test_build_date_range_rejects_both_empty(self):
        with self.assertRaises(ExpenseToolError):
            build_date_range("", "")

    def test_empty_start_names_the_right_option(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            build_date_range(None, "")
        self.assertIn("--end", str(ctx.exception))

    def test_none_still_means_no_filtering(self):
        """回归防护：只有 None 才是不筛选。"""
        date_range = build_date_range(None, None)
        self.assertFalse(date_range.is_active)

    def test_one_side_none_other_side_valid(self):
        date_range = build_date_range("2025-01-01", None)
        self.assertTrue(date_range.is_active)
        self.assertIsNone(date_range.end)


class BuildDateRangeTests(unittest.TestCase):
    def test_both_none_means_no_filtering(self):
        date_range = build_date_range(None, None)
        self.assertFalse(date_range.is_active)

    def test_start_only(self):
        date_range = build_date_range("2025-01-15", None)
        self.assertTrue(date_range.is_active)
        self.assertEqual(date_range.start, date(2025, 1, 15))
        self.assertIsNone(date_range.end)

    def test_end_only(self):
        date_range = build_date_range(None, "2025-02-15")
        self.assertTrue(date_range.is_active)
        self.assertIsNone(date_range.start)

    def test_start_after_end_is_rejected(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            build_date_range("2025-03-01", "2025-01-31")
        message = str(ctx.exception)
        self.assertIn("开始日期不能晚于结束日期", message)
        self.assertIn("2025-03-01", message)
        self.assertIn("2025-01-31", message)

    def test_start_equal_to_end_is_allowed(self):
        date_range = build_date_range("2025-01-31", "2025-01-31")
        self.assertEqual(date_range.start, date_range.end)


class DateRangeContainsTests(unittest.TestCase):
    def test_boundaries_are_inclusive(self):
        date_range = DateRange(start=date(2025, 1, 10), end=date(2025, 1, 20))
        self.assertTrue(date_range.contains(date(2025, 1, 10)))
        self.assertTrue(date_range.contains(date(2025, 1, 20)))
        self.assertTrue(date_range.contains(date(2025, 1, 15)))

    def test_outside_boundaries(self):
        date_range = DateRange(start=date(2025, 1, 10), end=date(2025, 1, 20))
        self.assertFalse(date_range.contains(date(2025, 1, 9)))
        self.assertFalse(date_range.contains(date(2025, 1, 21)))

    def test_open_ended_ranges(self):
        self.assertTrue(DateRange(start=date(2025, 1, 10)).contains(date(2099, 1, 1)))
        self.assertTrue(DateRange(end=date(2025, 1, 20)).contains(date(1999, 1, 1)))
        self.assertTrue(DateRange().contains(date(1999, 1, 1)))

    def test_filter_keeps_order_and_drops_outside(self):
        rows = [expense_on(2025, 1, 5), expense_on(2025, 1, 15), expense_on(2025, 1, 25)]
        kept = DateRange(start=date(2025, 1, 10), end=date(2025, 1, 20)).filter(rows)
        self.assertEqual([e.date.day for e in kept], [15])

    def test_filter_is_noop_when_inactive(self):
        rows = [expense_on(2025, 1, 5), expense_on(2025, 1, 15)]
        kept = DateRange().filter(rows)
        self.assertEqual(len(kept), 2)

    def test_filter_returns_a_new_list(self):
        """返回新列表，不要就地改动调用方传进来的那个。"""
        rows = [expense_on(2025, 1, 5)]
        result = DateRange().filter(rows)
        self.assertIsNot(result, rows)


class DescribeTests(unittest.TestCase):
    """措辞要随边界情况变化，别出现"只筛一天却说首尾都计入"这种别扭说法。"""

    def test_both_ends(self):
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 1, 31)).describe(),
            "2025-01-01 ~ 2025-01-31（含首尾）",
        )

    def test_single_day(self):
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 1, 1)).describe(),
            "2025-01-01（仅这一天）",
        )

    def test_start_only(self):
        self.assertEqual(
            DateRange(start=date(2025, 1, 1)).describe(), "2025-01-01 起（含当天）"
        )

    def test_end_only(self):
        self.assertEqual(
            DateRange(end=date(2025, 1, 31)).describe(), "截至 2025-01-31（含当天）"
        )

    def test_inactive(self):
        self.assertEqual(DateRange().describe(), "")


class BuildCategoryFilterTests(unittest.TestCase):
    def test_none_means_no_filtering(self):
        self.assertFalse(build_category_filter(None).is_active)

    def test_single_category(self):
        result = build_category_filter(["Food"])
        self.assertTrue(result.is_active)
        self.assertEqual(result.categories, ("Food",))

    def test_multiple_categories(self):
        result = build_category_filter(["Food", "Transit"])
        self.assertEqual(result.categories, ("Food", "Transit"))

    def test_duplicates_are_removed(self):
        """重复传同一个类别不会让记录被算两次。"""
        result = build_category_filter(["Food", "Food", "Transit"])
        self.assertEqual(result.categories, ("Food", "Transit"))

    def test_surrounding_whitespace_is_stripped(self):
        result = build_category_filter(["  Food  "])
        self.assertEqual(result.categories, ("Food",))

    def test_empty_value_is_rejected(self):
        """`--category ""` 是传了空值，和 --start "" 一样要报错。"""
        with self.assertRaises(ExpenseToolError) as ctx:
            build_category_filter([""])
        self.assertIn("--category", str(ctx.exception))
        self.assertIn("空", str(ctx.exception))

    def test_whitespace_only_value_is_rejected(self):
        for raw in (" ", "   ", "\t"):
            with self.assertRaises(ExpenseToolError):
                build_category_filter([raw])

    def test_one_empty_among_valid_is_still_rejected(self):
        with self.assertRaises(ExpenseToolError):
            build_category_filter(["Food", ""])

    def test_case_is_not_normalized(self):
        """CSV 里 "Food" 和 "food" 是两个类别，筛选也应当区别对待。"""
        result = build_category_filter(["food"])
        self.assertFalse(result.contains("Food"))
        self.assertTrue(result.contains("food"))


class CategoryFilterTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            expense_on(2025, 1, 1, category="Food"),
            expense_on(2025, 1, 2, category="Transit"),
            expense_on(2025, 2, 1, category="Food"),
        ]

    def test_inactive_keeps_everything(self):
        self.assertEqual(len(CategoryFilter().filter(self.rows)), 3)

    def test_filters_to_requested_category(self):
        kept = CategoryFilter(("Food",)).filter(self.rows)
        self.assertEqual(len(kept), 2)
        self.assertTrue(all(e.category == "Food" for e in kept))

    def test_multiple_categories_union(self):
        kept = CategoryFilter(("Food", "Transit")).filter(self.rows)
        self.assertEqual(len(kept), 3)

    def test_keeps_original_order(self):
        kept = CategoryFilter(("Food",)).filter(self.rows)
        self.assertEqual([e.date.day for e in kept], [1, 1])  # 1/1 和 2/1

    def test_describe(self):
        self.assertEqual(CategoryFilter(("Food", "Transit")).describe(), "Food、Transit")

    def test_unmatched(self):
        result = CategoryFilter(("Food", "Rent"))
        self.assertEqual(result.unmatched(self.rows), ["Rent"])

    def test_unmatched_is_empty_when_all_present(self):
        self.assertEqual(CategoryFilter(("Food",)).unmatched(self.rows), [])


class ValidateAgainstTests(unittest.TestCase):
    """类别名写错时要报错并列出可用类别，不能静默给一份空报表。"""

    def setUp(self):
        self.rows = [
            expense_on(2025, 1, 1, category="Food"),
            expense_on(2025, 1, 2, category="Transit"),
        ]

    def test_valid_categories_pass(self):
        FilterSet(categories=CategoryFilter(("Food",))).validate_against(self.rows)

    def test_unknown_category_raises(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            FilterSet(categories=CategoryFilter(("Fod",))).validate_against(self.rows)
        message = str(ctx.exception)
        self.assertIn("Fod", message)
        # 要列出可用类别，否则用户不知道正确的拼写
        self.assertIn("Food", message)
        self.assertIn("Transit", message)

    def test_unknown_category_mentions_case_sensitivity(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            FilterSet(categories=CategoryFilter(("food",))).validate_against(self.rows)
        self.assertIn("区分大小写", str(ctx.exception))

    def test_no_categories_never_raises(self):
        FilterSet().validate_against([])

    def test_empty_dataset_gives_its_own_message(self):
        with self.assertRaises(ExpenseToolError) as ctx:
            FilterSet(categories=CategoryFilter(("Food",))).validate_against([])
        self.assertIn("没有任何有效记录", str(ctx.exception))

    def test_validation_uses_the_unfiltered_set(self):
        """关键：校验要拿筛选前的全量记录。

        否则 1 月的数据里没有 Transit，"--category Transit --start 2025-01-01"
        就会被误判成类别名拼错了。
        """
        rows = [expense_on(2025, 1, 1, category="Food"),
                expense_on(2025, 6, 1, category="Transit")]
        filters = FilterSet(
            date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
            categories=CategoryFilter(("Transit",)),
        )
        filters.validate_against(rows)  # 不该抛异常
        self.assertEqual(filters.filter(rows), [])  # 筛完确实是空的，但那是正常的


class FilterSetTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            expense_on(2025, 1, 10, category="Food"),
            expense_on(2025, 1, 20, category="Transit"),
            expense_on(2025, 2, 10, category="Food"),
        ]

    def test_no_filters_is_inactive(self):
        self.assertFalse(FilterSet().is_active)

    def test_date_only(self):
        filters = FilterSet(date_range=DateRange(start=date(2025, 2, 1)))
        self.assertTrue(filters.is_active)
        self.assertEqual(len(filters.filter(self.rows)), 1)

    def test_category_only(self):
        filters = FilterSet(categories=CategoryFilter(("Food",)))
        self.assertTrue(filters.is_active)
        self.assertEqual(len(filters.filter(self.rows)), 2)

    def test_both_conditions_are_intersected(self):
        """同时给日期和类别时取交集，不是并集。"""
        filters = FilterSet(
            date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
            categories=CategoryFilter(("Food",)),
        )
        kept = filters.filter(self.rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].date, date(2025, 1, 10))

    def test_filter_order_does_not_matter(self):
        """先日期后类别、还是先类别后日期，结果应当一样。"""
        rows = self.rows
        a = FilterSet(
            date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
            categories=CategoryFilter(("Food",)),
        ).filter(rows)
        b = CategoryFilter(("Food",)).filter(
            DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)).filter(rows)
        )
        self.assertEqual([e.date for e in a], [e.date for e in b])

    def test_describe_lists_active_conditions(self):
        filters = FilterSet(
            date_range=DateRange(date(2025, 1, 1), date(2025, 1, 31)),
            categories=CategoryFilter(("Food", "Transit")),
        )
        self.assertEqual(
            filters.describe(),
            [
                "日期范围：2025-01-01 ~ 2025-01-31（含首尾）",
                "类别：Food、Transit",
            ],
        )

    def test_describe_only_shows_active_conditions(self):
        self.assertEqual(FilterSet().describe(), [])
        self.assertEqual(
            FilterSet(categories=CategoryFilter(("Food",))).describe(),
            ["类别：Food"],
        )

    def test_filter_returns_new_list(self):
        rows = [expense_on(2025, 1, 1)]
        self.assertIsNot(FilterSet().filter(rows), rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
