"""家庭支出汇总工具。

分层结构（从下往上）：
    models   —— 数据结构 Expense
    loader   —— 读 CSV 并校验，产出 List[Expense]
    summary  —— 纯计算，产出 Summary
    report   —— 把 Summary 渲染成文本
    cli      —— 命令行参数 + 串联以上各层

作为库使用的最小示例：
    from expense_tool import load_expenses, summarize, render
    print(render(summarize(load_expenses("examples/sample_expenses.csv"))))
"""

from __future__ import annotations

from .errors import CsvFormatError, ExpenseToolError
from .loader import DEFAULT_ENCODING, load_expenses
from .models import Expense
from .report import format_amount, render
from .summary import Summary, summarize

__version__ = "0.1.0"

__all__ = [
    "CsvFormatError",
    "DEFAULT_ENCODING",
    "Expense",
    "ExpenseToolError",
    "Summary",
    "format_amount",
    "load_expenses",
    "render",
    "summarize",
    "__version__",
]
