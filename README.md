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
| `--start` | 否 | 只统计这一天**及之后**的记录（含当天），格式 `YYYY-MM-DD` |
| `--end` | 否 | 只统计这一天**及之前**的记录（含当天），格式 `YYYY-MM-DD` |
| `--category` | 否 | 只统计指定类别的记录。**可重复传多个**，见下 |
| `-e, --encoding` | 否 | CSV 文件编码，默认 `utf-8-sig`。Excel 导出的中文 CSV 通常是 `gbk` |

`--start` 和 `--end` 可以只用其中一个，表示只限一侧。**不传**才是不筛选；
传了空值（`--start ""`）会报错，不会当成没传——见下面的「空值 ≠ 没传」。

多个筛选条件之间是**取交集**（日期和类别都要满足）。

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

### 按日期范围筛选

用 `--start` / `--end` 只看某一段时间的账。**首尾两天都计入结果**（闭区间）：

```bash
# 只看 2025 年 1 月
python run.py 我的账单.csv --start 2025-01-01 --end 2025-01-31

# 只看 2025-01-31 当天
python run.py 我的账单.csv --start 2025-01-31 --end 2025-01-31

# 只看 2025-01-31 及以后（不限结束）
python run.py 我的账单.csv --start 2025-01-31
```

**真实运行输出**（用 4 条记录分别落在 1/1、1/10、1/31、2/1 的文件实测）：

```
$ python run.py span.csv --start 2025-01-01 --end 2025-01-31
数据来源：span.csv
日期范围：2025-01-01 ~ 2025-01-31（含首尾）
记录条数：3

总额：111.00

按月汇总
  2025-01：111.00

按类别汇总
  Food：110.00
  Transit：1.00
```

边界验证：1/1 的 `100.00` 和 1/31 的 `1.00` 都被算进去了（`111.00 = 100 + 10 + 1`），
2/1 的 `200.00` 被排除。

筛选只影响**有效记录**。读不出日期的坏行无法判断是否在范围内，因此**一律照列**，
并在区块标题里注明——见下节。这种"3 月的数据被我筛掉了"和"这行根本读不出来"
是两回事，前者不叫跳过，不会出现在跳过清单里。

### 按类别筛选

用 `--category` 只看某几类。**重复传**即可指定多个（取并集）：

```bash
# 只看餐饮
python run.py 我的账单.csv --category Food

# 看餐饮和交通
python run.py 我的账单.csv --category Food --category Transit

# 和日期一起用：2025 年 1 月的餐饮
python run.py 我的账单.csv --category Food --start 2025-01-01 --end 2025-01-31
```

**真实运行输出**（文件里 5 条记录，含一笔 1000.00 的房租）：

```
$ python run.py cat.csv
数据来源：cat.csv
记录条数：5

总额：1031.00

按月汇总
  2025-01：1015.50
  2025-02：15.50

按类别汇总
  Food：21.00
  Rent：1000.00
  Transit：10.00

$ python run.py cat.csv --category Food
数据来源：cat.csv
类别：Food
记录条数：2

总额：21.00

按月汇总
  2025-01：12.50
  2025-02：8.50

按类别汇总
  Food：21.00
```

**总额、按月汇总、按类别汇总三处都只统计筛选后的记录**——它们看的是同一批
记录，不会出现"总额筛了、月份没筛"这种自相矛盾的结果。

多个类别（`--category Food --category Transit`）：

```
记录条数：4
总额：31.00

按月汇总
  2025-01：15.50
  2025-02：15.50

按类别汇总
  Food：21.00
  Transit：10.00
```

**为什么用重复传而不是逗号分隔**

`--category Food,Transit` 这种写法**不支持**，逗号会被当成类别名的一部分。
原因是 CSV 里的类别名本身可能含逗号（`"Food, Dining"`），按逗号切分
会把一个类别名劈成两个，**静默筛错**——比报错更糟。

类别名是**精确匹配**（去掉首尾空格后），**区分大小写**：CSV 里 `Food` 和
`food` 是两个不同的类别。类别名**写错时会报错并列出可用类别**，不会给你一份
空报表：

```
$ python run.py cat.csv --category Fod
错误：--category 指定的类别在文件里不存在：Fod
文件里实际出现的类别：Food、Rent、Transit
提示：类别名要和 CSV 里写的完全一致（区分大小写）。
$ echo $?
1
```

校验用的是**筛选前**的全部有效记录。所以"日期把某个类别筛没了"（比如查 1 月的
`Transit`，而 Transit 只在 3 月出现）会正常给出总额 `0.00` 的报表，不会被误判成
类别名拼错。

### 文件里有坏数据会怎样

如果某些行的日期格式不对、金额不是数字、或者类别为空，**程序不会崩，也不会拒绝出报表**。
它会把这几行跳过，用其余的有效行正常汇总，然后在最后如实列出：

- 每一行的**行号**和**跳过原因**
- 一共跳过了**多少行**
- 针对出错的列给一次格式提示

用 `examples/sample_with_bad_rows.csv` 演示（在验收用例的第 3、5、6 行各插入一处错误）：

```bash
python run.py examples/sample_with_bad_rows.csv
```

**真实运行输出**（已实测，退出码 0）：

```
数据来源：examples/sample_with_bad_rows.csv
记录条数：4
已跳过：3 行

总额：22.00

按月汇总
  2025-01：15.50
  2025-02：6.50

按类别汇总
  Food：19.00
  Transit：3.00

跳过的行（共 3 行，未计入上面的汇总）
  第 3 行：date 无法识别：'2025-13-45'
  第 5 行：category 为空。
  第 6 行：amount 不是有效数字：'abc'

提示：
  date 支持的写法：2025-01-02、2025/1/2、2025.01.02、20250102
  amount 需要是数字（如 12.50），负数表示退款（如 -2.00）
```

注意 `记录条数：4` 只统计**有效**行，坏行不计入；`已跳过：3 行` 在顶部就先提醒一次，
免得只看总额就以为数据是全的。跳过的行**不参与**任何汇总计算。

如果每一行都是坏的，程序仍然会正常输出一份总额 `0.00` 的报表，并列出所有坏行。

---

## 四、目录结构与各文件职责

```
.
├── README.md                      # 本文件
├── run.py                         # 便捷启动脚本（把参数转交给 expense_tool.cli）
├── .gitignore
├── examples/
│   ├── sample_expenses.csv        # 示例数据，对应上面的验收用例
│   └── sample_with_bad_rows.csv   # 示例数据，演示"跳过坏行"
├── expense_tool/                  # 主体代码包
│   ├── __init__.py                # 包入口：导出主要 API 和 __version__
│   ├── __main__.py                # 让 `python -m expense_tool` 可用
│   ├── console.py                 # 控制台输出编码适配（解决 Windows 中文乱码）
│   ├── errors.py                  # 自定义异常：ExpenseToolError / CsvFormatError
│   ├── models.py                  # 数据结构：Expense / SkippedRow / LoadResult
│   ├── loader.py                  # 读取 + 校验 CSV → LoadResult        （只管 IO）
│   ├── filters.py                 # 参数校验 + 筛选：DateRange / CategoryFilter / FilterSet
│   ├── summary.py                 # 汇总计算 → Summary                （纯计算，无 IO）
│   ├── report.py                  # Summary → 命令行文本              （只管格式化）
│   └── cli.py                     # 解析参数、串联上面几步、处理退出码
└── tests/
    ├── __init__.py
    ├── helpers.py                 # 测试公用工具（临时 CSV、进程内跑 CLI）
    ├── test_loader.py             # loader 层：表头校验、行级错误的跳过、行号准确性
    ├── test_filters.py            # filters 层：日期参数校验、闭区间边界
    ├── test_summary.py            # summary + report 层：汇总、格式化、渲染
    └── test_cli.py                # 端到端：退出码 + 完整输出（113 个用例）
```

### 为什么这样分

数据流是单向的一条线：

```
                              ┌─ filters(挑) ────────────────────────┐
                              ↓                                      │
CSV 文件 → loader(读+校验) → LoadResult ─┬─ expenses ────────────────→ summary(算) → Summary ─→ report(渲染) → 文本 → cli 打印
                                        └─ skipped  ────────────────────────────────────────────┘
```

`filters` 只碰 `expenses`，不碰 `skipped`——坏行连日期和类别都读不出来，
没法判断它满不满足筛选条件，所以一律照列给用户看。

所有筛选条件收在一个 `FilterSet` 里，`cli` 只调一次 `filters.filter(...)`，
拿到结果直接喂给 `summary`。这样**不可能出现"筛了总额忘了筛月份"**——
三处汇总用的是同一批记录。以后再加筛选维度也只是往 `FilterSet` 加一个字段，
`render` 的签名不用动。

关键点是**计算和展示彻底分开**：

- `summary.summarize()` 是纯函数，输入 `Expense` 列表、输出 `Summary` 对象，**不打印任何东西**。
  所以它既好写测试（不用去抓 stdout），也能被将来的 Web 界面 / 导出脚本直接复用。
- `report.render()` 只负责把 `Summary`（和被跳过的行）变成字符串，也**不打印**。
  cli 拿到字符串后才决定往哪儿输出。

数据结构分三层，都放在 `models.py`（最底层，避免 `report` 反向依赖 `loader`）：

| 类型 | 含义 |
|---|---|
| `Expense` | 一条解析成功的支出记录 |
| `SkippedRow` | 一行没解析成功的数据：`line_number` + `reason` + `column` |
| `LoadResult` | 上面两者的集合，就是读文件的完整结果 |

### 想加功能的话，改哪里

| 需求 | 改哪里 |
|---|---|
| 改输出样式（加颜色、改成 Markdown / 表格） | `report.py` |
| 加一种汇总维度（按周、按年、按账户） | `summary.py` 加一个函数，`report.py` 加一段渲染 |
| 加一种筛选条件（按金额区间、按账户） | 照着 `filters.py` 的 `DateRange`/`CategoryFilter` 再写一个，加进 `FilterSet`，`cli.py` 接上参数 |
| 改"跳过策略"（比如严格模式下直接报错、或限制最多跳几行） | `loader._parse` 里的 `except CsvFormatError` 分支 |
| CSV 多了一列（备注、账户） | `models.py` 加字段 + `loader.py` 加解析，其余不用动 |
| 换数据源（Excel、数据库） | 新写一个函数，返回 `LoadResult` 即可，`summary`/`report` 完全复用 |
| 加命令行选项（`--top N`、`--only-month`） | `cli.py` |

`cli.main` 里所有"用户能自己修好"的问题都被同一个 `try/except ExpenseToolError`
兜住，一律打印一行中文并返回 1。加新的校验只要抛 `ExpenseToolError`，
错误处理的格式就自动统一了。

---

## 五、运行测试

```bash
python -m unittest discover -v
```

**真实运行输出**：`Ran 169 tests in 0.107s` → `OK`

测试分四个文件，对应源码的分层：

- `test_loader.py` —— 表头乱序/大小写/带 BOM、空行跳过、货币符号与千分位、
  多种日期格式；**行级错误的跳过**（行号、原因、出错列、坏行不影响好行）；
  以及**行号准确性**（拿文件物理行交叉比对）
- `test_filters.py` —— 日期参数校验（格式错 / 日期不存在 / 少写前导零 / **空值**）、
  闭区间边界、单侧不设限、起止倒置报错；类别筛选的精确匹配与去重、
  类别名不存在的报错；`FilterSet` 的交集语义
- `test_summary.py` —— 验收用例逐字比对、金额格式化与舍入、汇总边界情况、跳过信息的渲染
- `test_cli.py` —— 端到端：退出码、完整 stdout/stderr、`--encoding`、
  `--start`/`--end`、`--category`

有几组用例是**回归防护**，值得单独说：

- 空值：断言 `--start ""` / `--category ""` 必须**不产生任何汇总输出**并以 1 退出。
  旧实现会当成"没传"而打印一份没筛选的报表，这些用例能立刻抓住。
- 类别筛选的一致性：`CliCategoryFilterTests.test_single_category_filters_every_section`
  同时断言总额、按月汇总、按类别汇总三处都只反映筛选后的记录。只筛了一部分的话
  （比如忘了筛 monthly），这里会立刻暴露。

注意 `python -m unittest discover` 需要**在项目根目录**执行（包才在 `sys.path` 上）。
想跑单个文件用 `python -m unittest tests.test_loader -v`。

---

## 六、行为约定

**金额显示**：一律保留两位小数，四舍五入（`ROUND_HALF_UP`）。内部用 `Decimal`
而不是 `float` 计算，避免 `0.1 + 0.2 = 0.30000000000000004` 这类浮点误差。

**负数**：金额为负表示退款，按字面值参与求和，会自动从总额里扣掉。
如果全部都是退款，总额就是负数（例如 `总额：-5.00`）。

**排序**：月份按字典序升序（等价于时间升序）；类别按字母升序。
两者都是确定性排序，同样的输入永远得到同样的输出。

**容错**：表头前后空格、大小写、UTF-8 BOM 都会被自动处理；
整行为空或 `,,` 的行会被静默忽略（这不算错误，也不计入"跳过行数"）；
金额里的货币符号（`¥ ￥ $ € £`）和千分位逗号会被去掉。

**错误分两个层级**，这是本工具最重要的行为约定：

| 层级 | 例子 | 处理方式 |
|---|---|---|
| **参数错误** | `--start`/`--end` 格式不对、日期不存在、开始晚于结束 | 报错退出（退出码 1）。还没读文件就先挡住 |
| **结构性错误** | 文件不存在、编码不对、没有表头、表头缺列 | 报错退出（退出码 1）。没有表头就没法汇总，没有折中方案 |
| **行级错误** | 日期格式错、金额不是数字、类别为空、日期/金额为空 | 跳过该行并汇报，其余行照常汇总（退出码 0） |

这样划分的原因：真实账单里常混着几行脏数据，为它们让整份报表跑不出来没有意义；
但也不能默默丢掉——那样用户会以为总额是完整的。

前两层都会打印一行中文说明，**不会**把 Python 堆栈甩给用户。

一行里有多个问题时，**只报最左边那列**（按 date → category → amount 的顺序）。
修完一个再跑一次，下一个问题会浮现出来。

**行号是文件里的物理行号**（表头是第 1 行），可以直接拿去用编辑器跳到那一行。
空白行和跨多行的带引号字段都不会让行号偏移——见下面「行号是怎么算准的」。

**退出码**：

| 码 | 含义 |
|---|---|
| 0 | 成功（**即使跳过了若干行，也是 0**） |
| 1 | 参数错误（`--start`/`--end`/`--category` 不合法、类别名不存在）、结构性错误（文件不存在、编码不对、表头缺列） |
| 2 | 命令行参数用法错误（缺 `csv_file`、未知选项，由 argparse 产生） |

关于"跳过行时仍返回 0"：用户要的语义是"别崩、照常出汇总"，跳过的行已经在输出里
如实汇报了。如果你希望脚本能自动感知到有跳行，可以改成非 0，或者去数输出里的
`已跳过：` 那一行。

结构性错误**不会**抛 Python traceback，而是打印一行中文说明：

```
$ python run.py nope.csv
错误：找不到文件：nope.csv

$ python run.py bad_header.csv
错误：第 1 行：表头缺少必需的列：amount。实际读到的列是：date、category
```

---

### 行号是怎么算准的

一个容易踩的坑是"用第几条记录来当行号"（`enumerate(records)` + 2）。
它数的是**记录序号**而不是**文件行号**，两种情况会偏：

1. 中间夹着空白行 —— CSV 解析器会悄悄跳过它们，但它们在文件里占着行号；
2. 字段里含换行符（带引号的多行字段）—— 一条记录横跨多个物理行。

改成用 `csv.reader` 的 `line_num`：它的语义是"到目前为止消费掉的物理行数"，
且**不会预读**（读一条记录时只消费刚好够用的那些行）。
于是本条记录占用的物理行区间是 `[上一条结束行 + 1, reader.line_num]`，
区间起点就是它在文件里的起始行号。

实测对比（文件里有 2 个空白行和 1 个跨行字段）：

| 记录首列 | 真实物理行 | 旧算法 | 新算法 |
|---|---|---|---|
| `2025-01-02` | 2 | 2 | 2 |
| `bad-a` | 4 | **3** | 4 |
| `2025-01-03` | 5 | **4** | 5 |
| `bad-b` | 9 | **5** | 9 |
| `2025-02-01` | 10 | **6** | 10 |

对应的回归测试见 `tests/test_loader.py` 里的 `PhysicalLineNumberTests`——
它不按"第几条记录"推算预期值，而是把文件读成物理行数组，
再用程序报出的行号去取那一行，检查内容确实是那条坏记录。

---

### 筛选条件本身有问题时

日期参数的格式**比 CSV 里的 date 列严格**：只接受足位的 `YYYY-MM-DD`，不接受
`2025/01/01`、`2025.01.01`、`20250101`，也不接受 `2025-1-1`。理由是命令行是
我们自己定的接口，严格一点更好排查；而 CSV 里是别人导出的数据，只好宽容。

出错时打印一行中文说明、以退出码 **1** 结束，**不会**给用户看 Python 堆栈：

```
$ python run.py 账单.csv --start 2025-03-01 --end 2025-01-31
错误：开始日期不能晚于结束日期：2025-03-01 > 2025-01-31。请检查 --start 和 --end，或把它们去掉以统计全部记录。

$ python run.py 账单.csv --start 2025/01/01
错误：--start 的日期格式不对：'2025/01/01'。请用 YYYY-MM-DD 格式，例如 2025-01-02

$ python run.py 账单.csv --end 2025-02-30
错误：--end 不是一个真实存在的日期：'2025-02-30'

$ python run.py 账单.csv --start 2025-1-1
错误：--start 的日期格式不对：'2025-1-1'。请用 YYYY-MM-DD 格式，例如 2025-01-02

$ python run.py 账单.csv --start ""
错误：--start 的值是空的。请提供一个 YYYY-MM-DD 格式的日期，例如 2025-01-02
```

注意"格式不对"和"日期不存在"是两条不同的提示——`2025-02-30` 格式没问题，
只是 2 月没有 30 号，用户要改的地方不一样。

参数自身有错时会**先报参数错**，不会跑去报"文件不存在"。

#### 空值 ≠ 没传

`--start ""`、`--start=`、`--start "   "` 都算**用户传了值，只是值是空的**，
一律报错退出。只有选项**压根没出现**（内部表示为 `None`）才是不筛选。

这两种情况必须分开：如果把空值当成"没传"而放行，用户敲错了参数，
却会拿到一份**没有任何筛选**的报表——而且输出里连"日期范围"那一行都没有
（因为确实没筛选），于是完全看不出哪里不对，只会觉得数字对不上。

实现上就是 `build_date_range` 里用 `if x is not None` 而不是 `if x`：

```python
start = parse_date_argument(start_text, "--start") if start_text is not None else None
```

```bash
$ python run.py 账单.csv --start ""
错误：--start 的值是空的。请提供一个 YYYY-MM-DD 格式的日期，例如 2025-01-02
$ echo $?
1
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
from datetime import date

from expense_tool import (
    CategoryFilter,
    DateRange,
    FilterSet,
    load_expenses,
    summarize,
    render,
)

result = load_expenses("examples/sample_with_bad_rows.csv")

print(len(result.expenses))         # 4   —— 有效行
print(result.skipped_count)         # 3   —— 被跳过的行
for row in result.skipped:
    print(row.line_number, row.column, row.reason)

# 可选：筛选。日期是闭区间（两侧都可以是 None），类别可传多个，条件之间取交集
filters = FilterSet(
    date_range=DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31)),
    categories=CategoryFilter(("Food", "Transit")),
)
expenses = filters.filter(result.expenses)

summary = summarize(expenses)
print(summary.total)                # 15.50（1 月且属于 Food/Transit 的记录）
print(summary.by_month["2025-01"])  # 15.50
print(render(summary, skipped=result.skipped, filters=filters))
```

也可以只用其中一个条件，另一个留空即可：

```python
filters = FilterSet(categories=CategoryFilter(("Food",)))   # 只看类别
filters = FilterSet(date_range=DateRange(start=date(2025, 1, 1)))  # 只看日期
```

实测输出（数值部分）：

```
4
3
3 date date 无法识别：'2025-13-45'
5 category category 为空。
6 amount amount 不是有效数字：'abc'
22.00
15.50
```

注意 `load_expenses()` 返回的是 `LoadResult`（不是裸列表），
要用 `result.expenses` 取有效记录。这样调用方**没法忽略**跳过的行——
只返回成功记录会让人误以为数据是全的。

注意：`render()` 返回的是字符串，自己 `print` 时不经过 cli 的编码适配。
在真正的终端里没问题；如果把输出重定向到文件/管道后发现中文乱码，
先调用一下适配函数，或者设置 `PYTHONIOENCODING=utf-8`：

```python
from expense_tool.console import configure_output_encoding

configure_output_encoding()
```

---

## 实现范围

已实现：

- 三列 CSV（`date`、`category`、`amount`），指定本地文件，纯本地不联网
- 总额 / 按月汇总 / 按类汇总，金额两位小数，负数（退款）抵扣
- `--start` / `--end` 日期范围筛选，闭区间，可只限一侧
- `--category` 类别筛选，可重复传多个，条件之间取交集
- 坏行跳过并汇报（物理行号 + 原因 + 总数），其余有效行照常汇总
- 表头顺序/大小写/空格/BOM 容错，多种日期写法，`--encoding` 指定编码

暂未实现（留给后续版本）：多文件合并、按金额区间筛选、导出结果、图形界面、
按金额排序输出、货币单位符号配置、严格模式（`--strict`，遇到坏行直接报错）、
`--exclude-category` 反向排除。
