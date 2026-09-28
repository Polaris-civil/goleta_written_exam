"""数据结构定义。

把"一条支出记录"固化成 Expense，好处是 loader / summary / report 三层之间
传递的是明确的对象，而不是裸的 dict 或 tuple。
以后如果要给 CSV 加一列（比如 note、account），只要在这里加字段，
再改 loader 里的解析即可，summary 和 report 基本不用动。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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
