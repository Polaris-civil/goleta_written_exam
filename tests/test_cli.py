"""端到端测试：直接调用 cli.main，检查完整输出和退出码。

这一层是唯一验证"参数解析 + loader + summary + report 串起来能跑"的地方。
"""

from __future__ import annotations

import unittest

from .helpers import run_cli, write_temp_csv

ACCEPTANCE_CSV = """date,category,amount
2025-01-02,Food,12.50
2025-01-03,Transit,3.00
2025-02-01,Food,8.50
2025-02-02,Food,-2.00
"""

DIRTY_CSV = """date,category,amount
2025-01-02,Food,12.50
2025-13-45,Food,9.90
2025-01-03,Transit,3.00
2025-01-04,,5.00
2025-01-05,Food,abc
2025-02-01,Food,8.50
2025-02-02,Food,-2.00
"""


class CliSuccessTests(unittest.TestCase):
    def test_acceptance_case(self):
        path = write_temp_csv(self, ACCEPTANCE_CSV)
        code, out, err = run_cli(path)

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("总额：22.00", out)
        self.assertIn("2025-01：15.50", out)
        self.assertIn("2025-02：6.50", out)
        self.assertIn("Food：19.00", out)
        self.assertIn("Transit：3.00", out)

    def test_clean_file_has_no_skipped_section(self):
        path = write_temp_csv(self, ACCEPTANCE_CSV)
        _, out, _ = run_cli(path)
        self.assertNotIn("跳过", out)


class CliSkippedRowTests(unittest.TestCase):
    """核心验收：脏数据不崩溃、被跳过、行号和原因都显示出来，其余行照常汇总。"""

    def setUp(self):
        self.path = write_temp_csv(self, DIRTY_CSV)
        self.code, self.out, self.err = run_cli(self.path)

    def test_exit_code_is_zero_despite_bad_rows(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.err, "")

    def test_valid_rows_are_still_summarized(self):
        # 有效的 4 行：12.50 + 3.00 + 8.50 - 2.00 = 22.00
        self.assertIn("总额：22.00", self.out)
        self.assertIn("2025-01：15.50", self.out)
        self.assertIn("2025-02：6.50", self.out)
        self.assertIn("Food：19.00", self.out)
        self.assertIn("Transit：3.00", self.out)

    def test_record_count_excludes_skipped_rows(self):
        self.assertIn("记录条数：4", self.out)

    def test_skipped_count_is_shown(self):
        self.assertIn("已跳过：3 行", self.out)

    def test_each_skipped_line_is_listed_with_number_and_reason(self):
        self.assertIn("第 3 行：date 无法识别：'2025-13-45'", self.out)
        self.assertIn("第 5 行：category 为空。", self.out)
        self.assertIn("第 6 行：amount 不是有效数字：'abc'", self.out)

    def test_skipped_section_header(self):
        self.assertIn("跳过的行（共 3 行，未计入上面的汇总）", self.out)

    def test_no_traceback_leaked(self):
        self.assertNotIn("Traceback", self.out + self.err)


class CliAllRowsBadTests(unittest.TestCase):
    def test_all_rows_bad_still_prints_report(self):
        path = write_temp_csv(self, "date,category,amount\nx,,\n2025-99-99,,\n")
        code, out, err = run_cli(path)

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("总额：0.00", out)
        self.assertIn("已跳过：2 行", out)
        self.assertIn("（无数据）", out)


class CliStructuralErrorTests(unittest.TestCase):
    """结构性错误仍然要报错退出，不能被"跳过"掩盖。"""

    def test_missing_file(self):
        code, out, err = run_cli("这个文件不存在.csv")
        self.assertEqual(code, 1)
        self.assertIn("找不到文件", err)
        self.assertEqual(out, "")

    def test_missing_column_in_header(self):
        path = write_temp_csv(self, "date,category\n2025-01-01,Food\n")
        code, _, err = run_cli(path)
        self.assertEqual(code, 1)
        self.assertIn("amount", err)

    def test_no_arguments_is_usage_error(self):
        code, _, err = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("usage", err)


class CliDateFilterTests(unittest.TestCase):
    """日期筛选的端到端行为。"""

    #: 首尾各一条正好落在边界上的记录，用来验证闭区间
    SPAN_CSV = """date,category,amount
2025-01-01,Food,100.00
2025-01-10,Food,10.00
2025-01-31,Transit,1.00
2025-02-01,Food,200.00
"""

    def setUp(self):
        self.path = write_temp_csv(self, self.SPAN_CSV)

    def test_no_filter_keeps_everything(self):
        code, out, _ = run_cli(self.path)
        self.assertEqual(code, 0)
        self.assertIn("总额：311.00", out)
        self.assertNotIn("日期范围", out)

    def test_both_ends_are_inclusive(self):
        """--start 和 --end 指定的那一天本身要算进去。"""
        code, out, _ = run_cli(self.path, "--start", "2025-01-01",
                               "--end", "2025-01-31")
        self.assertEqual(code, 0)
        self.assertIn("总额：111.00", out)  # 100 + 10 + 1
        self.assertIn("记录条数：3", out)

    def test_start_only(self):
        code, out, _ = run_cli(self.path, "--start", "2025-01-31")
        self.assertEqual(code, 0)
        self.assertIn("总额：201.00", out)  # 1 + 200

    def test_end_only(self):
        code, out, _ = run_cli(self.path, "--end", "2025-01-01")
        self.assertEqual(code, 0)
        self.assertIn("总额：100.00", out)

    def test_single_day_range(self):
        code, out, _ = run_cli(self.path, "--start", "2025-01-10",
                               "--end", "2025-01-10")
        self.assertEqual(code, 0)
        self.assertIn("总额：10.00", out)
        self.assertIn("日期范围：2025-01-10", out)

    def test_range_is_shown_in_output(self):
        _, out, _ = run_cli(self.path, "--start", "2025-01-01",
                            "--end", "2025-01-31")
        self.assertIn("日期范围：2025-01-01 ~ 2025-01-31（含首尾）", out)

    def test_monthly_breakdown_respects_filter(self):
        _, out, _ = run_cli(self.path, "--start", "2025-01-01",
                            "--end", "2025-01-31")
        self.assertIn("2025-01：111.00", out)
        self.assertNotIn("2025-02", out)

    def test_empty_result_is_not_an_error(self):
        """筛出来一条都没有时，仍然出报表，不是错误。"""
        code, out, err = run_cli(self.path, "--start", "2030-01-01")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("记录条数：0", out)
        self.assertIn("总额：0.00", out)
        self.assertIn("（无数据）", out)


class CliCategoryFilterTests(unittest.TestCase):
    """类别筛选的端到端行为。

    核心断言：总额、按月汇总、按类别汇总三处都只反映筛选后的记录。
    如果只筛了某一部分（比如忘了筛 monthly），这里会立刻暴露。
    """

    CSV = """date,category,amount
2025-01-02,Food,12.50
2025-01-03,Transit,3.00
2025-01-04,Rent,1000.00
2025-02-01,Food,8.50
2025-02-02,Transit,7.00
"""

    def setUp(self):
        self.path = write_temp_csv(self, self.CSV)

    def test_no_category_keeps_everything(self):
        code, out, _ = run_cli(self.path)
        self.assertEqual(code, 0)
        self.assertIn("总额：1031.00", out)
        self.assertNotIn("类别：", out)

    def test_single_category_filters_every_section(self):
        code, out, _ = run_cli(self.path, "--category", "Food")
        self.assertEqual(code, 0)

        # 顶部
        self.assertIn("类别：Food", out)
        self.assertIn("记录条数：2", out)
        # 总额
        self.assertIn("总额：21.00", out)
        # 按月汇总（两处月份都只剩 Food 的金额）
        self.assertIn("2025-01：12.50", out)
        self.assertIn("2025-02：8.50", out)
        # 按类别汇总（只剩被选中的类别）
        self.assertIn("Food：21.00", out)
        self.assertNotIn("Transit", out)
        self.assertNotIn("Rent", out)

    def test_multiple_categories_via_repeated_flag(self):
        code, out, _ = run_cli(self.path, "--category", "Food",
                               "--category", "Transit")
        self.assertEqual(code, 0)
        self.assertIn("类别：Food、Transit", out)
        self.assertIn("总额：31.00", out)  # 12.50+3.00+8.50+7.00
        self.assertIn("2025-01：15.50", out)
        self.assertIn("2025-02：15.50", out)
        self.assertNotIn("Rent", out)

    def test_category_is_not_split_on_commas(self):
        """类别名里可能有逗号，所以不按逗号切分——那样会静默筛错。"""
        path = write_temp_csv(
            self, 'date,category,amount\n2025-01-01,"Food, Dining",5.00\n'
        )
        code, out, _ = run_cli(path, "--category", "Food, Dining")
        self.assertEqual(code, 0)
        self.assertIn("总额：5.00", out)

    def test_combined_with_date_range(self):
        code, out, _ = run_cli(self.path, "--category", "Food",
                               "--start", "2025-02-01")
        self.assertEqual(code, 0)
        self.assertIn("类别：Food", out)
        self.assertIn("日期范围：2025-02-01 起（含当天）", out)
        self.assertIn("总额：8.50", out)
        self.assertIn("2025-02：8.50", out)
        self.assertNotIn("2025-01", out)

    def test_unknown_category_fails_cleanly(self):
        code, out, err = run_cli(self.path, "--category", "Fod")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Fod", err)
        # 列出可用类别，用户才知道正确的拼写
        self.assertIn("Food", err)
        self.assertIn("Transit", err)
        self.assertIn("Rent", err)
        self.assertNotIn("Traceback", err)

    def test_category_case_mismatch_fails_cleanly(self):
        code, _, err = run_cli(self.path, "--category", "food")
        self.assertEqual(code, 1)
        self.assertIn("区分大小写", err)
        self.assertNotIn("Traceback", err)

    def test_empty_category_value_fails_cleanly(self):
        """`--category ""` 是传了空值，不是没传。"""
        code, out, err = run_cli(self.path, "--category", "")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("--category", err)
        self.assertIn("空", err)
        self.assertNotIn("Traceback", err)

    def test_unknown_category_is_checked_against_unfiltered_rows(self):
        """日期把某类别筛没了，不算类别名写错。

        这里 Transit 只在 3 月出现，而日期只留 1 月：
        结果确实是空的，但那是筛选的正常结果，不该报错。
        """
        path = write_temp_csv(
            self,
            "date,category,amount\n"
            "2025-01-02,Food,1.00\n"
            "2025-03-02,Transit,2.00\n",
        )
        code, out, err = run_cli(path, "--category", "Transit",
                                 "--start", "2025-01-01", "--end", "2025-01-31")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("总额：0.00", out)
        self.assertIn("记录条数：0", out)

    def test_category_filter_does_not_affect_skipped_rows(self):
        path = write_temp_csv(
            self,
            "date,category,amount\n"
            "2025-01-02,Food,1.00\n"
            "bad-a,Food,9.90\n",
        )
        code, out, _ = run_cli(path, "--category", "Food")
        self.assertEqual(code, 0)
        # 坏行的类别虽然也是 Food，但它读不出来，不能因此被"筛进来"
        self.assertIn("已跳过：1 行", out)
        self.assertIn("第 3 行：date 无法识别：'bad-a'", out)
        self.assertIn("总额：1.00", out)


class CliBadDateArgumentsTests(unittest.TestCase):
    """参数错误必须报得清楚、以失败状态退出、不留堆栈。"""

    def setUp(self):
        self.path = write_temp_csv(
            self, "date,category,amount\n2025-01-15,Food,1.00\n"
        )

    def test_start_after_end_fails_cleanly(self):
        code, out, err = run_cli(self.path, "--start", "2025-03-01",
                                 "--end", "2025-01-31")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("开始日期不能晚于结束日期", err)
        self.assertIn("2025-03-01", err)
        self.assertIn("2025-01-31", err)

    def test_start_after_end_leaks_no_traceback(self):
        _, _, err = run_cli(self.path, "--start", "2025-03-01",
                            "--end", "2025-01-31")
        for leak in ("Traceback", "File \"", "ExpenseToolError", "raise "):
            self.assertNotIn(leak, err)

    def test_wrong_format_fails_cleanly(self):
        code, _, err = run_cli(self.path, "--start", "2025/01/01")
        self.assertEqual(code, 1)
        self.assertIn("YYYY-MM-DD", err)
        self.assertNotIn("Traceback", err)

    def test_nonexistent_date_fails_cleanly(self):
        code, _, err = run_cli(self.path, "--end", "2025-02-30")
        self.assertEqual(code, 1)
        self.assertIn("2025-02-30", err)
        self.assertNotIn("Traceback", err)

    def test_empty_start_value_fails_instead_of_being_ignored(self):
        """`--start ""` 是传了空值，不是没传——必须报错，不能静默地不筛选。"""
        code, out, err = run_cli(self.path, "--start", "")
        self.assertEqual(code, 1)
        # 关键：没有汇总输出。旧实现会当成"没传"，照常打印一份没筛选的报表
        self.assertEqual(out, "")
        self.assertIn("YYYY-MM-DD", err)
        self.assertIn("--start", err)

    def test_empty_end_value_fails_instead_of_being_ignored(self):
        code, out, err = run_cli(self.path, "--end", "")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("YYYY-MM-DD", err)
        self.assertIn("--end", err)

    def test_both_empty_values_fail(self):
        code, out, _ = run_cli(self.path, "--start", "", "--end", "")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")

    def test_empty_value_leaks_no_traceback(self):
        _, _, err = run_cli(self.path, "--start", "")
        for leak in ("Traceback", "File \"", "ExpenseToolError", "raise "):
            self.assertNotIn(leak, err)

    def test_whitespace_value_fails(self):
        code, out, _ = run_cli(self.path, "--start", "   ")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")

    def test_nothing_passed_still_means_no_filtering(self):
        """回归防护：确实没传时才不筛选，输出里不该有日期范围那一行。"""
        code, out, _ = run_cli(self.path)
        self.assertEqual(code, 0)
        self.assertIn("总额", out)
        self.assertNotIn("日期范围", out)

    def test_filter_error_takes_precedence_over_missing_file(self):
        """参数自身有错时，先报参数错，不要跑去报文件不存在。"""
        code, _, err = run_cli("不存在的文件.csv", "--start", "2025-03-01",
                               "--end", "2025-01-31")
        self.assertEqual(code, 1)
        self.assertIn("开始日期不能晚于结束日期", err)


class CliFilterWithSkippedRowsTests(unittest.TestCase):
    """筛选和跳过坏行同时存在时的行为。"""

    DIRTY_CSV = """date,category,amount
2025-01-02,Food,12.50
bad-a,Food,9.90
2025-03-01,Transit,50.00
"""

    def setUp(self):
        self.path = write_temp_csv(self, self.DIRTY_CSV)

    def test_skipped_rows_are_listed_regardless_of_range(self):
        """坏行的日期读不出来，没法判断是否在范围内，所以一律照列。"""
        code, out, _ = run_cli(self.path, "--start", "2025-01-01",
                               "--end", "2025-01-31")
        self.assertEqual(code, 0)
        # bad-a 在文件第 3 行（表头 1、第一条数据 2）
        self.assertIn("第 3 行：date 无法识别：'bad-a'", out)

    def test_skipped_header_says_it_is_unaffected_by_filter(self):
        """措辞用"筛选条件"而不是"日期筛选"——类别筛选同样不作用于坏行。"""
        _, out, _ = run_cli(self.path, "--start", "2025-01-01",
                            "--end", "2025-01-31")
        self.assertIn("不受筛选条件影响", out)

    def test_skipped_header_mentions_filter_for_category_too(self):
        _, out, _ = run_cli(self.path, "--category", "Food")
        self.assertIn("不受筛选条件影响", out)

    def test_out_of_range_valid_rows_are_dropped(self):
        """3 月那条在范围外，要被筛掉——它和"坏行"是两回事，不该出现在跳过清单里。"""
        _, out, _ = run_cli(self.path, "--start", "2025-01-01",
                            "--end", "2025-01-31")
        self.assertIn("总额：12.50", out)
        self.assertIn("记录条数：1", out)
        self.assertIn("已跳过：1 行", out)

    def test_no_filter_keeps_out_of_range_rows(self):
        _, out, _ = run_cli(self.path)
        self.assertIn("总额：62.50", out)  # 12.50 + 50.00


class CliEncodingOptionTests(unittest.TestCase):
    def test_gbk_file_via_flag(self):
        path = write_temp_csv(
            self, "date,category,amount\n2025-03-01,餐饮,88.80\n", encoding="gbk"
        )
        code, out, _ = run_cli(path, "--encoding", "gbk")
        self.assertEqual(code, 0)
        self.assertIn("餐饮：88.80", out)

    def test_short_flag_also_works(self):
        path = write_temp_csv(
            self, "date,category,amount\n2025-03-01,餐饮,88.80\n", encoding="gbk"
        )
        code, _, _ = run_cli(path, "-e", "gbk")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
