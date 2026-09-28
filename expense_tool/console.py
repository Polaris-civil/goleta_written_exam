"""控制台输出编码适配。

为什么需要这个文件：
中文 Windows 的默认代码页是 936(GBK)。
- 在真正的 cmd / PowerShell 窗口里，Python 3.6+ 会走 WriteConsoleW 直接写
  UTF-16，中文显示正常，不受代码页影响；
- 但一旦输出被重定向（管道、`> out.txt`、CI 日志），Python 就退回到按
  本地代码页(GBK)编码字节，而接收方通常按 UTF-8 解读，于是中文全变成乱码。

所以这里的策略是：只有当 stdout/stderr 不是终端时才强制 UTF-8。
真实终端保持原样，不做任何冒险的改动。
"""

from __future__ import annotations

import sys
from typing import Optional


def configure_output_encoding() -> None:
    """把被重定向的 stdout/stderr 切到 UTF-8。失败时静默跳过。"""
    _reconfigure_if_redirected(sys.stdout)
    _reconfigure_if_redirected(sys.stderr)


def _reconfigure_if_redirected(stream: Optional[object]) -> None:
    if stream is None:
        return
    # 是真正的终端 -> 交给 Python 的原生控制台支持，不干预
    if _isatty(stream):
        return

    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        # 例如被测试框架替换成了别的对象，直接放过
        return

    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError, AttributeError):
        # 极少见：流已经写过数据、或平台不支持。宁可乱码也不要崩。
        pass


def _isatty(stream: object) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False
