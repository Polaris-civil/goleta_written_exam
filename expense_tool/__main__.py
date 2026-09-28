"""让包可以这样运行：python -m expense_tool <csv文件>"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
