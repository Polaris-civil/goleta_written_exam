# 家庭支出汇总工具

读取本地的 CSV 支出文件，在命令行显示**总支出**、**每月总额**和**每类总额**。
纯本地运行，不联网、不需要任何第三方依赖。

---

## 一、环境要求

- **Python 3.8 或更高版本**（本机实测：3.9.1 / 3.11.15 / 3.14.0 均可运行）
- **不需要安装任何第三方库**，只用标准库（`csv`、`decimal`、`argparse`、`pathlib`）
- 不需要虚拟环境；想用也可以

检查 Python 版本：

```bash
python --version
```

---

## 二、如何启动

所有命令都在**项目根目录**执行。

```bash
# 方式一（推荐，最短）
python run.py <csv文件路径>

# 方式二：把项目当成模块运行
python -m expense_tool <csv文件路径>
```

查看帮助：

```bash
python run.py --help
```

### 命令行参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `csv_file` | 是 | 要读取的 CSV 文件路径，必须包含 `date`、`category`、`amount` 三列 |
| `-e, --encoding` | 否 | CSV 文件编码，默认 `utf-8-sig`。Excel 导出的中文 CSV 通常是 `gbk` |

---

## 三、使用示例文件

项目自带示例文件 `examples/sample_expenses.csv`：

```csv
date,category,amount
2025-01-02,Food,12.50
2025-01-03,Transit,3.00
2025-02-01,Food,8.50
2025-02-02,Food,-2.00
```

运行命令：

```bash
python run.py examples/sample_expenses.csv
```

**真实运行输出**（已实测，退出码 0）：

```
数据来源：examples/sample_expenses.csv
记录条数：4

总额：22.00

按月汇总
  2025-01：15.50
  2025-02：6.50

按类别汇总
  Food：19.00
  Transit：3.00
```

对得上验收要求：总额 `22.00`、`2025-01：15.50`、`2025-02：6.50`、`Food：19.00`、`Transit：3.00`。
其中 `2025-02` 的 `6.50 = 8.50 + (-2.00)`，退款按负数正常抵扣。

### 用你自己的文件

CSV 第一行必须是表头，三列名字固定，**顺序随意、大小写和前后空格都会被容忍**：

```csv
date,category,amount
2025-01-02,Food,12.50
```

日期支持这几种写法：`2025-01-02`、`2025/1/2`、`2025.01.02`、`20250102`。

如果文件是 GBK 编码（Excel「另存为 CSV」的默认结果），加上 `--encoding gbk`：

```bash
python run.py 我的账单.csv --encoding gbk
```

---

## 四、目录结构与各文件职责

```
.
├── README.md                      # 本文件
├── run.py                         # 便捷启动脚本（把参数转交给 expense_tool.cli）
├── .gitignore
├── examples/
│   └── sample_expenses.csv        # 示例数据，对应上面的验收用例
├── expense_tool/                  # 主体代码包
│   ├── __init__.py                # 包入口：导出主要 API 和 __version__
│   ├── __main__.py                # 让 `python -m expense_tool` 可用
│   ├── console.py                 # 控制台输出编码适配（解决 Windows 中文乱码）
│   ├── errors.py                  # 自定义异常：ExpenseToolError / CsvFormatError
│   ├── models.py                  # 数据结构：Expense（一条支出记录）
│   ├── loader.py                  # 读取 + 校验 CSV → List[Expense]   （只管 IO）
│   ├── summary.py                 # 汇总计算 → Summary                （纯计算，无 IO）
│   ├── report.py                  # Summary → 命令行文本              （只管格式化）
│   └── cli.py                     # 解析参数、串联上面几步、处理退出码
└── tests/
    ├── __init__.py
    └── test_summary.py            # 单元测试（24 个用例）
```

### 为什么这样分

数据流是单向的一条线：

```
CSV 文件 → loader(读+校验) → List[Expense] → summary(算) → Summary → report(渲染) → 文本 → cli 打印
```

关键点是**计算和展示彻底分开**：

- `summary.summarize()` 是纯函数，输入 `Expense` 列表、输出 `Summary` 对象，**不打印任何东西**。
  所以它既好写测试（不用去抓 stdout），也能被将来的 Web 界面 / 导出脚本直接复用。
- `report.render()` 只负责把 `Summary` 变成字符串，也**不打印**。
  cli 拿到字符串后才决定往哪儿输出。

### 想加功能的话，改哪里

| 需求 | 改哪里 |
|---|---|
| 改输出样式（加颜色、改成 Markdown / 表格） | `report.py` |
| 加一种汇总维度（按周、按年、按账户） | `summary.py` 加一个函数，`report.py` 加一段渲染 |
| CSV 多了一列（备注、账户） | `models.py` 加字段 + `loader.py` 加解析，其余不用动 |
| 换数据源（Excel、数据库） | 新写一个函数，返回 `List[Expense]` 即可，`summary`/`report` 完全复用 |
| 加命令行选项（`--top N`、`--only-month`） | `cli.py` |

---

## 五、运行测试

```bash
python -m unittest discover -v
```

**真实运行输出**：`Ran 24 tests in 0.020s` → `OK`

测试覆盖了：验收用例的逐字比对、金额格式化与舍入、表头乱序/大小写/带 BOM、
空行跳过、货币符号与千分位、多种日期格式、以及各类错误场景（缺列、非法金额、
非法日期、空文件、文件不存在、`NaN`）。

---

## 六、行为约定

**金额显示**：一律保留两位小数，四舍五入（`ROUND_HALF_UP`）。内部用 `Decimal`
而不是 `float` 计算，避免 `0.1 + 0.2 = 0.30000000000000004` 这类浮点误差。

**负数**：金额为负表示退款，按字面值参与求和，会自动从总额里扣掉。
如果全部都是退款，总额就是负数（例如 `总额：-5.00`）。

**排序**：月份按字典序升序（等价于时间升序）；类别按字母升序。
两者都是确定性排序，同样的输入永远得到同样的输出。

**容错**：表头前后空格、大小写、UTF-8 BOM 都会被自动处理；
整行为空或 `,,` 的行会被跳过；金额里的货币符号（`¥ ￥ $ € £`）和千分位逗号会被去掉。

**退出码**：

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 数据/文件问题（文件不存在、编码不对、CSV 格式错误） |
| 2 | 命令行参数用法错误（由 argparse 产生） |

出错时**不会**抛 Python traceback，而是打印一行中文说明，例如：

```
$ python run.py nope.csv
错误：找不到文件：nope.csv

$ python run.py bad.csv
错误：第 2 行：amount 不是有效数字：'abc'

$ python run.py bad_header.csv
错误：第 1 行：表头缺少必需的列：amount。实际读到的列是：date、category
```

---

## 七、常见的坑

**中文输出变成乱码？**
代码里已经处理了：输出被重定向（管道、`> out.txt`、CI 日志）时会自动切到 UTF-8；
在真正的 cmd / PowerShell 窗口里走 Python 原生的 `WriteConsoleW`，中文正常显示。
如果你在其它环境遇到乱码，可以临时加环境变量：

```bash
PYTHONIOENCODING=utf-8 python run.py examples/sample_expenses.csv
```

**报「无法用编码 'utf-8-sig' 读取」？**
文件多半是 GBK 编码，加 `--encoding gbk`。

**路径里有中文或空格？**
用引号包起来：`python run.py "D:/我的 账单/2025.csv"`。

---

## 八、作为库调用

除了命令行，也可以直接在 Python 里用：

```python
from expense_tool import load_expenses, summarize, render

expenses = load_expenses("examples/sample_expenses.csv")
summary = summarize(expenses)

print(summary.total)                # 22.00
print(summary.by_month["2025-01"])  # 15.50
print(render(summary))              # 完整报告文本
```

实测输出（数值部分）：

```
22.00
15.50
```

注意：`render()` 返回的是字符串，自己 `print` 时不经过 cli 的编码适配。
在真正的终端里没问题；如果把输出重定向到文件/管道后发现中文乱码，
先调用一下适配函数，或者设置 `PYTHONIOENCODING=utf-8`：

```python
from expense_tool.console import configure_output_encoding

configure_output_encoding()
```

---

## 第一版的范围

已实现：三列 CSV、指定文件、总额 / 按月 / 按类汇总、两位小数、负数抵扣、纯本地。

暂未实现（留给后续版本）：多文件合并、日期区间过滤、导出结果、图形界面、
按金额排序输出、货币单位符号配置。
