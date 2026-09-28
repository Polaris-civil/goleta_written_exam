"""汇总计算层。

这一层是纯函数：输入一堆 Expense，输出一个 Summary 对象，
不读文件、不打印、不关心命令行参数。这样它既好测试，也好复用
（比如以后要做个 Web 界面，直接调用 summarize 就行）。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, Tuple

from .models import Expense

ZERO = Decimal("0")


@dataclass(frozen=True)
class Summary:
    """汇总结果。

    by_month / by_category 都是"有序字典"：按 key 的字典序排好序了，
    这样同样的输入永远得到同样的输出，方便对比和写测试。
    """

    total: Decimal
    count: int
    by_month: Dict[str, Decimal]
    by_category: Dict[str, Decimal]


def summarize(expenses: Iterable[Expense]) -> Summary:
    """计算总额、按月汇总、按类别汇总。

    负数（退款）按字面值相加，因此会自动从总额里扣掉。
    """
    total = ZERO
    count = 0
    months: Dict[str, Decimal] = {}
    categories: Dict[str, Decimal] = {}

    for expense in expenses:
        count += 1
        total += expense.amount
        months[expense.month] = months.get(expense.month, ZERO) + expense.amount
        categories[expense.category] = (
            categories.get(expense.category, ZERO) + expense.amount
        )

    return Summary(
        total=total,
        count=count,
        by_month=_sorted_items(months),
        by_category=_sorted_items(categories),
    )


def _sorted_items(values: Dict[str, Decimal]) -> Dict[str, Decimal]:
    """按 key 排序，返回一个新的普通 dict（保持插入顺序即有序）。"""
    return dict(sorted(values.items(), key=lambda item: item[0]))


def month_range(summary: Summary) -> Tuple[str, str]:
    """辅助函数：返回 (最早月份, 最晚月份)，没有数据时返回 ('', '')。

    现在没被用上，但保留它作为"这一层可以长出新功能"的示例。
    """
    if not summary.by_month:
        return "", ""
    keys = list(summary.by_month)
    return keys[0], keys[-1]
