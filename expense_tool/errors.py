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
    """CSV 内容不符合预期（缺列、日期/金额解析失败等）。

    line_number 是文件里的真实行号（表头是第 1 行，所以数据从第 2 行开始），
    方便用户直接跳过去修改。
    """

    def __init__(self, message: str, line_number: Optional[int] = None) -> None:
        if line_number is not None:
            message = "第 {} 行：{}".format(line_number, message)
            # 用 setattr 记录原始行号，便于调用方或测试单独取用
            self.line_number = line_number
        else:
            self.line_number = None
        super().__init__(message)
