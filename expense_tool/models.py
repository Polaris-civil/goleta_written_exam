"""数据结构定义。

把"一条支出记录"固化成 Expense，好处是 loader / summary / report 三层之间
传递的是明确的对象，而不是裸的 dict 或 tuple。
以后如果要给 CSV 加一列（比如 note、account），只要在这里加字段，
再改 loader 里的解析即可，summary 和 report 基本不用动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List


@dataclass(frozen=True)
class Expense:
    """一条支出记录。amount 为负数时表示退款。"""

    date: date
    category: str
    amount: Decimal
    # 记录它在源文件里的行号，出错时可以直接告诉用户去哪儿改
    line_number: int = 0

    @property
    def month(self) -> str:
        """按月汇总用的键，形如 "2025-01"。"""
        return "{:04d}-{:02d}".format(self.date.year, self.date.month)


@dataclass(frozen=True)
class SkippedRow:
    """一行没能解析成功的数据。

    行级错误（日期格式不对、金额不是数字、类别为空……）不会让程序退出，
    而是被记成这样一条，最后统一汇报给用户。
    """

    #: 文件里的真实行号（表头是第 1 行）
    line_number: int
    #: 跳过这一行的原因，不含"第 N 行："前缀
    reason: str
    #: 出问题的是哪一列（"date" / "category" / "amount"），可为空
    column: str = ""


@dataclass(frozen=True)
class LoadResult:
    """读文件的结果：成功的记录 + 被跳过的行。

    把两者一起返回，是为了让调用方既能汇总，也能如实告诉用户
    "有多少数据没算进去"——只返回成功的记录会让用户误以为数据是全的。
    """

    expenses: List[Expense] = field(default_factory=list)
    skipped: List[SkippedRow] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def has_skipped(self) -> bool:
        return bool(self.skipped)
