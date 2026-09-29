"""按日期范围筛选。

单独成一个模块，是为了让职责边界保持清楚：
    cli     —— 只管把命令行参数取出来
    filters —— 校验日期参数、判断某条记录在不在范围内（本文件）
    summary —— 只管对已经筛好的记录做汇总

注意这里校验的日期格式是**命令行参数**的格式，比 CSV 里 date 列的格式严格得多：
命令行只接受 YYYY-MM-DD。CSV 文件里的日期宽容一些（见 loader.DATE_FORMATS），
因为那是别人导出的数据；而命令行是我们自己定的接口，严格一点更好排查。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, List, Optional, Tuple

from .errors import ExpenseToolError
from .models import Expense

#: 命令行日期参数的格式，用于**显示**给用户看
DATE_ARGUMENT_FORMAT = "YYYY-MM-DD"

#: 给 datetime.strptime 用的**解析**格式。
#: 注意它必须和上面那个分开：strptime 只认 %Y 这样的指令，
#: 把 "YYYY-MM-DD" 传进去会被当成字面量，连 "2025-01-02" 都解析不了。
_DATE_STRPTIME_FORMAT = "%Y-%m-%d"

#: 严格匹配 4 位年 - 2 位月 - 2 位日。
#: 不能只靠 strptime，因为它会欣然接受 "2025-1-2" 这种少写前导零的写法。
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date_argument(text: str, option_name: str) -> date:
    """把命令行里的 "YYYY-MM-DD" 转成 date。

    参数:
        text: 用户输入的原始字符串
        option_name: 出错的选项名（如 "--start"），用来让提示信息指得更准

    异常:
        ExpenseToolError: 值为空、格式不对，或者不是一个真实存在的日期（比如 2025-02-30）
    """
    # 空值单独说，因为 "--start 的值是空的" 比 "格式不对：''" 好懂得多。
    # 注意这里必须显式判空：用户传了 --start "" 和压根没传 --start 是两回事，
    # 前者要给报错，后者才是不筛选（由 build_date_range 负责区分）。
    if not text.strip():
        raise ExpenseToolError(
            "{} 的值是空的。请提供一个 {} 格式的日期，例如 2025-01-02".format(
                option_name, DATE_ARGUMENT_FORMAT
            )
        )

    if not _DATE_PATTERN.match(text):
        raise ExpenseToolError(
            "{} 的日期格式不对：{!r}。请用 {} 格式，例如 2025-01-02".format(
                option_name, text, DATE_ARGUMENT_FORMAT
            )
        )

    try:
        return datetime.strptime(text, _DATE_STRPTIME_FORMAT).date()
    except ValueError:
        # 格式对但日期不存在，比如 2025-02-30、2025-13-01
        raise ExpenseToolError(
            "{} 不是一个真实存在的日期：{!r}".format(option_name, text)
        ) from None


@dataclass(frozen=True)
class DateRange:
    """闭区间 [start, end]，**首尾两天都算在内**。

    start / end 都可以为 None，表示那一侧不设限：
        DateRange()                      -> 不筛选
        DateRange(start=d)               -> d 及以后
        DateRange(end=d)                 -> d 及以前
        DateRange(start=a, end=b)        -> [a, b]

    构造时会校验 start <= end，所以只要拿到了一个 DateRange 实例，
    就一定是合法的——校验不会漏。
    """

    start: Optional[date] = None
    end: Optional[date] = None

    def __post_init__(self) -> None:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ExpenseToolError(
                "开始日期不能晚于结束日期：{} > {}。"
                "请检查 --start 和 --end，或把它们去掉以统计全部记录。".format(
                    self.start.isoformat(), self.end.isoformat()
                )
            )

    @property
    def is_active(self) -> bool:
        """两侧都没设限时为 False（此时输出里不会出现日期范围这一行）。"""
        return self.start is not None or self.end is not None

    def contains(self, day: date) -> bool:
        """day 是否落在范围内（闭区间）。"""
        if self.start is not None and day < self.start:
            return False
        if self.end is not None and day > self.end:
            return False
        return True

    def filter(self, expenses: Iterable[Expense]) -> List[Expense]:
        """挑出范围内的记录，保持原有顺序。不设限时原样返回。"""
        if not self.is_active:
            return list(expenses)
        return [item for item in expenses if self.contains(item.date)]

    def describe(self) -> str:
        """给报告用的一句话描述，含"闭区间"的措辞。

        按边界情况分别措辞，避免出现 "2025-01-31（首尾都计入）" 这种别扭的说法：
            2025-01-01 ~ 2025-01-31（含首尾）
            2025-01-31（仅这一天）
            2025-01-01 起（含当天）
            截至 2025-01-31（含当天）
        """
        if self.start is not None and self.end is not None:
            if self.start == self.end:
                return "{}（仅这一天）".format(self.start.isoformat())
            return "{} ~ {}（含首尾）".format(
                self.start.isoformat(), self.end.isoformat()
            )
        if self.start is not None:
            return "{} 起（含当天）".format(self.start.isoformat())
        if self.end is not None:
            return "截至 {}（含当天）".format(self.end.isoformat())
        return ""


def build_date_range(
    start_text: Optional[str], end_text: Optional[str]
) -> DateRange:
    """从两个命令行参数拼出 DateRange。

    参数为 None 表示用户没传这个选项 -> 那一侧不筛选。
    任何**非 None** 的值（包括空字符串）都会被当成用户的输入送去校验，
    不合法就抛 ExpenseToolError。

    这里必须用 `is not None` 而不是 `if start_text`：
    后者是真值判断，会把 `--start ""` 这种"传了但传空了"的情况
    误当成"没传"，导致跳过校验继续汇总——用户明明是敲错了参数，
    却拿到一份没有任何筛选的报表，还看不出哪里不对。

    起止倒置的校验在 DateRange.__post_init__ 里。
    """
    start = parse_date_argument(start_text, "--start") if start_text is not None else None
    end = parse_date_argument(end_text, "--end") if end_text is not None else None
    return DateRange(start=start, end=end)


@dataclass(frozen=True)
class CategoryFilter:
    """按类别筛选，保留出现在 categories 里的记录。

    categories 为空元组表示不筛选（全部保留）。
    匹配是**精确匹配**（去掉首尾空格后），区分大小写：
    CSV 里 "Food" 和 "food" 是两个不同的类别，筛选时也应当区别对待。
    写错了不会静默变成空报表——FilterSet.validate_against 会报错并列出可用类别。
    """

    categories: Tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        return bool(self.categories)

    def contains(self, category: str) -> bool:
        if not self.is_active:
            return True
        return category in self.categories

    def filter(self, expenses: Iterable[Expense]) -> List[Expense]:
        """挑出类别匹配的记录，保持原有顺序。不筛选时原样返回。"""
        if not self.is_active:
            return list(expenses)
        return [item for item in expenses if self.contains(item.category)]

    def describe(self) -> str:
        """给报告用的一句话描述，例如 "Food、Transit"。"""
        return "、".join(self.categories)

    def unmatched(self, expenses: Iterable[Expense]) -> List[str]:
        """请求了、但在这批记录里一个都没出现的类别。"""
        present = {item.category for item in expenses}
        return [name for name in self.categories if name not in present]


def build_category_filter(values: Optional[List[str]]) -> CategoryFilter:
    """从 --category 收集到的值拼出 CategoryFilter。

    参数为 None 表示用户没传这个选项 -> 不筛选。
    传了但某个值是空的（`--category ""`）属于用户敲错，报错而不是忽略——
    和 --start/--end 的处理保持一致，理由见 build_date_range 的说明。

    重复的类别会被去重，重复传 --category Food 不会让任何记录被算两次。
    """
    if values is None:
        return CategoryFilter()

    cleaned: List[str] = []
    for raw in values:
        name = raw.strip()
        if not name:
            raise ExpenseToolError(
                "--category 的值不能为空。请提供一个类别名，例如 --category Food"
            )
        if name not in cleaned:
            cleaned.append(name)

    return CategoryFilter(categories=tuple(cleaned))


@dataclass(frozen=True)
class FilterSet:
    """一次运行里生效的全部筛选条件。

    存在的意义有两个：
    1. 把"先按日期筛、再按类别筛"的顺序固定在一个地方，cli 不用自己串；
    2. 让 report 只依赖这一个对象，以后再加筛选维度不用改 render 的签名。
    """

    date_range: DateRange = field(default_factory=DateRange)
    categories: CategoryFilter = field(default_factory=CategoryFilter)

    @property
    def is_active(self) -> bool:
        """任何一项筛选生效就为 True。都不生效时报告里不会出现筛选相关的行。"""
        return self.date_range.is_active or self.categories.is_active

    def filter(self, expenses: Iterable[Expense]) -> List[Expense]:
        """依次施加所有筛选条件，返回筛选后的记录。

        总额、按月汇总、按类别汇总都基于这里返回的结果，
        所以三者天然是一致的：它们看的是同一批记录。
        """
        return self.categories.filter(self.date_range.filter(expenses))

    def describe(self) -> List[str]:
        """给报告用的描述行，每个生效的条件一行。"""
        lines: List[str] = []
        if self.date_range.is_active:
            lines.append("日期范围：{}".format(self.date_range.describe()))
        if self.categories.is_active:
            lines.append("类别：{}".format(self.categories.describe()))
        return lines

    def validate_against(self, expenses: Iterable[Expense]) -> None:
        """确认用户指定的类别确实存在，不存在就报错。

        传进来的应当是**筛选前**的全部有效记录：
        否则"--start 把某个类别筛没了"会被误判成用户把类别名拼错了。

        exception:
            ExpenseToolError: 有类别一个都没匹配上
        """
        missing = self.categories.unmatched(expenses)
        if not missing:
            return

        available = sorted({item.category for item in expenses})
        if not available:
            raise ExpenseToolError(
                "--category 指定了 {}，但这个文件里没有任何有效记录，无法按类别筛选。".format(
                    "、".join(missing)
                )
            )

        raise ExpenseToolError(
            "--category 指定的类别在文件里不存在：{}\n"
            "文件里实际出现的类别：{}\n"
            "提示：类别名要和 CSV 里写的完全一致（区分大小写）。".format(
                "、".join(missing), "、".join(available)
            )
        )
