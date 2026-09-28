"""结果渲染层。

接收一个 Summary，产出要打印的字符串。
这一层不做任何计算，也不 print——返回字符串是为了好测试，
cli 拿到后再决定打到 stdout 还是别的地方。

想改输出样式（加颜色、改成 Markdown、导成表格）都只动这个文件。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from .summary import Summary

#: 金额统一保留两位小数
MONEY_QUANTUM = Decimal("0.01")

#: 缩进，让分组的明细和标题有层级感
INDENT = "  "

EMPTY_PLACEHOLDER = "（无数据）"


def format_amount(value: Decimal) -> str:
    """格式化成两位小数的字符串，例如 15.5 -> '15.50'。"""
    if not value:
        # 避免把 -0.00 这种"负零"打出来
        value = abs(value)
    return str(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def render(summary: Summary, source: Optional[str] = None) -> str:
    """把 Summary 渲染成多行文本。"""
    lines: List[str] = []

    if source:
        lines.append("数据来源：{}".format(source))
    lines.append("记录条数：{}".format(summary.count))
    lines.append("")
    lines.append("总额：{}".format(format_amount(summary.total)))

    lines.append("")
    lines.append("按月汇总")
    lines.extend(_render_group(summary.by_month))

    lines.append("")
    lines.append("按类别汇总")
    lines.extend(_render_group(summary.by_category))

    return "\n".join(lines)


def _render_group(values: Dict[str, Decimal]) -> List[str]:
    if not values:
        return [INDENT + EMPTY_PLACEHOLDER]
    return [
        "{}{}：{}".format(INDENT, key, format_amount(amount))
        for key, amount in values.items()
    ]
