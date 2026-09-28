#!/usr/bin/env python
"""便捷启动脚本。

存在的意义：让用户不用记 `python -m expense_tool`，
直接 `python run.py examples/sample_expenses.csv` 就能跑。

它本身不含任何业务逻辑，只是把参数转交给 expense_tool.cli.main。
"""

from __future__ import annotations

import os
import sys

# 保证从任意工作目录运行都能找到 expense_tool 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expense_tool.cli import main

if __name__ == "__main__":
    sys.exit(main())
