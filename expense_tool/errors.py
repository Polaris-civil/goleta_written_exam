"""本工具所有"可预期的用户级错误"。

设计原则：
- 凡是"用户能自己修好"的问题（文件不存在、表头少列、金额不是数字），
  都抛 ExpenseToolError 的子类；
- 这些异常会被 cli.main 捕获，打印成人话并返回非 0 退出码，
  而不是给用户看一堆 Python traceback。
- 真正的编程错误（TypeError 之类）不要包装，让它照常抛出，方便排查。
"""

from __future__ import annotations

from typing import Optional


class ExpenseToolError(Exception):
    """本工具所有可预期错误的基类。"""


class CsvFormatError(ExpenseToolError):
    """CSV 内容不符合预期。

    line_number 是文件里的真实行号（表头是第 1 行，所以数据从第 2 行开始），
    方便用户直接跳过去修改。

    这类错误分两种处理方式：
    - 表头问题（缺列）：无法汇总任何数据，直接抛给 cli 报错退出；
    - 数据行问题（日期/金额解析失败）：由 loader 捕获，记成 SkippedRow 后跳过，
      程序继续处理其余有效行。

    为了后者能拿到不带行号前缀的原始原因，这里把 message 存在 self.reason。
    """

    def __init__(
        self,
        message: str,
        line_number: Optional[int] = None,
        column: Optional[str] = None,
    ) -> None:
        #: 不含"第 N 行："前缀的原始原因
        self.reason = message
        self.line_number = line_number
        #: 出问题的是哪一列（"date" / "category" / "amount"），
        #: 用于在报告末尾按列给出一次性的格式提示，而不是每行重复一遍
        self.column = column
        if line_number is not None:
            message = "第 {} 行：{}".format(line_number, message)
        super().__init__(message)
