"""测试包。

这里顺带把被重定向的 stdout/stderr 切成 UTF-8，
否则在中文 Windows 上跑 `python -m unittest -v`，
测试名里的中文在管道/CI 日志里会变成乱码。

注意：这跟被测代码无关，纯粹是为了让测试日志可读。
"""

from __future__ import annotations

try:
    from expense_tool.console import configure_output_encoding

    configure_output_encoding()
except ImportError:  # 从别的目录运行时找不到包，不影响测试本身
    pass
