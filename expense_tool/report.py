"""结果渲染层。

接收一个 Summary（外加可选的"被跳过的行"清单），产出要打印的字符串。
这一层不做任何计算，也不 print——返回字符串是为了好测试，
cli 拿到后再决定打到 stdout 还是别的地方。

想改输出样式（加颜色、改成 Markdown、导成表格）都只动这个文件。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Iterable, List, Optional

from .filters import FilterSet
from .models import SkippedRow
from .summary import Summary

#: 金额统一保留两位小数
MONEY_QUANTUM = Decimal("0.01")

#: 缩进，让分组的明细和标题有层级感
INDENT = "  "

EMPTY_PLACEHOLDER = "（无数据）"

#: 按列给出的格式提示。只对"格式不直观"的列给提示；
#: category 为空这种原因本身已经说清楚了，不需要再补一句。
COLUMN_HINTS = {
    "date": "date 支持的写法：2025-01-02、2025/1/2、2025.01.02、20250102",
    "amount": "amount 需要是数字（如 12.50），负数表示退款（如 -2.00）",
}


def format_amount(value: Decimal) -> str:
    """格式化成两位小数的字符串，例如 15.5 -> '15.50'。"""
    if not value:
        # 避免把 -0.00 这种"负零"打出来
        value = abs(value)
    return str(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def render(
    summary: Summary,
    source: Optional[str] = None,
    skipped: Iterable[SkippedRow] = (),
    filters: Optional[FilterSet] = None,
) -> str:
    """把 Summary 渲染成多行文本。

    参数:
        summary: 汇总结果。注意它应当是对**筛选后**的记录算出来的，
            渲染层不会再去碰筛选，只是把生效的条件显示出来。
        source: 数据来源（文件路径），只用于显示
        skipped: 被跳过的行。为空时不会在输出里出现任何相关字样，
            保证干净文件的输出格式和以前完全一致。
        filters: 生效的筛选条件。None 或没有任何条件生效时，
            不产生任何额外输出行。
    """
    skipped_list = list(skipped)
    filtering = filters is not None and filters.is_active

    lines: List[str] = []

    if source:
        lines.append("数据来源：{}".format(source))
    if filtering:
        # 措辞（含"闭区间"之类的说明）由 FilterSet.describe 负责，这里不重复
        lines.extend(filters.describe())
    lines.append("记录条数：{}".format(summary.count))
    # 在顶部就给一个显眼的提示，避免用户只看总额就以为数据是全的
    if skipped_list:
        lines.append("已跳过：{} 行".format(len(skipped_list)))
    lines.append("")
    lines.append("总额：{}".format(format_amount(summary.total)))

    lines.append("")
    lines.append("按月汇总")
    lines.extend(_render_group(summary.by_month))

    lines.append("")
    lines.append("按类别汇总")
    lines.extend(_render_group(summary.by_category))

    if skipped_list:
        lines.append("")
        lines.append(_skipped_header(len(skipped_list), filtering))
        lines.extend(_render_skipped(skipped_list))
        lines.extend(_render_hints(skipped_list))

    return "\n".join(lines)


def _skipped_header(count: int, filtering: bool) -> str:
    """跳过行的区块标题。

    筛选生效时要额外说明一句：坏行的日期和类别都可能读不出来，
    没法判断它是否满足筛选条件，所以一律照列不误。
    不说清楚的话，用户会奇怪"我明明筛了 1 月，怎么列出一行 3 月的"。
    """
    header = "跳过的行（共 {} 行，未计入上面的汇总".format(count)
    if filtering:
        header += "；不受筛选条件影响"
    return header + "）"


def _render_skipped(skipped: List[SkippedRow]) -> List[str]:
    return [
        "{}第 {} 行：{}".format(INDENT, item.line_number, item.reason)
        for item in skipped
    ]


def _render_hints(skipped: List[SkippedRow]) -> List[str]:
    """按出现过的列给一次格式提示，避免每行都重复一遍。

    COLUMN_HINTS 里没有的列（比如 category）不会有提示。
    """
    # 用 dict 保序去重：同一个列只提示一次
    columns = {item.column: None for item in skipped if item.column}
    hints = [COLUMN_HINTS[col] for col in columns if col in COLUMN_HINTS]
    if not hints:
        return []

    lines = ["", "提示："]
    lines.extend("{}{}".format(INDENT, hint) for hint in hints)
    return lines


def _render_group(values: Dict[str, Decimal]) -> List[str]:
    if not values:
        return [INDENT + EMPTY_PLACEHOLDER]
    return [
        "{}{}：{}".format(INDENT, key, format_amount(amount))
        for key, amount in values.items()
    ]
