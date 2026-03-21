# iFinD 财务数据抓取与可视化脚本设计

> 目标文件: `tools/ifind_fetcher.py`（单文件，约 450 行）
> 状态: 设计完成，待创建

## 定位

独立于主工作流的数据准备工具。输出的数据既可直接供模块03/04使用，也可独立做分析和作图。

## 依赖

- `iFinDPy` — 需用户从 iFinD 终端安装或 `pip install iFinDPy`
- `pandas`（已有）
- `matplotlib`（需添加）
- `openpyxl`（已有）

## CLI 接口

```bash
# 抓取目标公司数据 + 作图
python tools/ifind_fetcher.py --code 688102.SH --years 5

# 抓取目标公司 + 可比公司对比
python tools/ifind_fetcher.py --code 688102.SH --comps "688128.SH,002842.SZ" --years 5

# 仅导出数据不作图
python tools/ifind_fetcher.py --code 688102.SH --no-chart

# 全部参数
--code        目标公司股票代码（必填）
--comps       可比公司代码，逗号分隔
--years       最近 N 年年报数据（默认5）
--no-chart    仅导出数据，不生成图表
--user        iFinD 账号（默认读 IFIND_USER 环境变量）
--password    iFinD 密码（默认读 IFIND_PASS 环境变量）
--output-dir  XLSX 输出目录（默认 input/financial_data/）
--chart-dir   图表输出目录（默认 output/charts/）
```

## 模块结构（8 个区块）

### 1. 指标映射 `INDICATOR_MAP`

集中定义在文件顶部，用户可在 iFinD 超级命令中验证后一处修改。

```python
INDICATOR_MAP: dict[str, dict[str, str]] = {
    # key 与模块03 history dict 字段名一致
    "revenue":               {"id": "ths_or_stock",                        "label": "营业收入(万元)"},
    "net_profit":            {"id": "ths_np_atsopc_stock",                 "label": "归母净利润(万元)"},
    "gross_margin":          {"id": "ths_gross_selling_rate_stock",        "label": "毛利率(%)"},
    "net_margin":            {"id": "ths_net_selling_rate_stock",          "label": "净利率(%)"},
    "revenue_yoy":           {"id": "ths_or_yoy_stock",                   "label": "营收同比增速(%)"},
    "eps":                   {"id": "ths_eps_stock",                       "label": "EPS(元)"},
    "roe":                   {"id": "ths_roe_stock",                       "label": "ROE(%)"},
    "asset_liability_ratio": {"id": "ths_asset_liability_ratio_stock",     "label": "资产负债率(%)"},
    "inventory_days":        {"id": "ths_inventory_turnover_days_stock",   "label": "存货周转天数"},
    "ar_days":               {"id": "ths_ar_turnover_days_stock",          "label": "应收账款周转天数"},
    "ap_days":               {"id": "ths_ap_turnover_days_stock",          "label": "应付账款周转天数"},
    "operating_cashflow":    {"id": "ths_operating_cf_stock",              "label": "经营活动现金流净额(万元)"},
    "price":                 {"id": "ths_close_price_stock",               "label": "年末收盘价(元)"},
    "pe":                    {"id": "ths_pe_ttm_stock",                    "label": "PE(TTM)"},
    "pb":                    {"id": "ths_pb_stock",                        "label": "PB"},
    "market_cap":            {"id": "ths_market_value_stock",              "label": "总市值(万元)"},
    "total_shares":          {"id": "ths_total_shares_stock",              "label": "总股本(万股)"},
}
```

### 2. iFinD 连接管理

- `_check_ifindpy()` — iFinDPy 未安装时给出明确安装指引，不抛 ImportError
- `ifind_login(user, password)` — `THS_iFinDLogin`，返回值 0 或 -201 均为成功
- `ifind_logout()` — `THS_iFinDLogout`，放在 `finally` 中确保退出

### 3. 数据抓取

- `_build_report_dates(years)` — 生成 `['20201231', '20211231', ...]` 报告期列表
- `_parse_ths_result(result)` — 统一解析 iFinDPy 返回对象为 DataFrame
- `fetch_basic_data(codes, indicator_ids, report_dates)` — 调用 `THS_BasicData`，一次传入多代码多指标
- `fetch_market_data(codes, indicator_ids, report_dates)` — 调用 `THS_HistoryQuotes` 获取年末市场数据
- `fetch_all_indicators(codes, years)` — 将指标分为基本面类/市场类，分别调用后按 `thscode + report_date` 合并

**API 限额友好**: 合并请求，一次调用传入多个代码，减少调用次数。

### 4. 数据整合 `raw_to_history()`

将 API 返回的宽表转为模块03兼容的 history 字典:

```python
{
    2022: {"revenue": 100000.0, "net_profit": 20000.0, "gross_margin": 21.0, ...},
    2023: {...},
    2024: {...},
}
```

key 为 `int` 年份，value 为 `dict[str, float | None]`，与 `modules/03_financial.py` 的 `_extract_structured_from_tables` 输出格式完全一致。

### 5. XLSX 导出 `export_xlsx()`

宽格式表：行=中文指标名，列=`{年份}年报`。与 iFinD Excel 插件导出格式一致，模块03的 `_extract_year_columns` 可匹配列头中的年份，`_pick_metric_row` 可匹配行首中文名。

指标行顺序与中文名（`_METRIC_ORDER`）:

| key | 中文名 |
|-----|--------|
| revenue | 营业收入 |
| net_profit | 归属于母公司股东的净利润 |
| gross_margin | 毛利率 |
| net_margin | 净利率 |
| revenue_yoy | 营业收入同比增长率 |
| eps | 每股收益-基本 |
| roe | 净资产收益率 |
| asset_liability_ratio | 资产负债率 |
| inventory_days | 存货周转天数 |
| ar_days | 应收账款周转天数 |
| ap_days | 应付账款周转天数 |
| operating_cashflow | 经营活动产生的现金流量净额 |
| price | 收盘价 |
| pe | PE(TTM) |
| pb | PB |
| market_cap | 总市值 |
| total_shares | 总股本 |

输出路径: `input/financial_data/{label}({code})-财务摘要-iFinD.xlsx`

### 6. 可比公司数据 `build_comparison_df()`

将多家公司的 history 整合为对比 DataFrame（指定年份或取最近一年），额外导出 `可比公司对比.xlsx`。

### 7. 图表生成（matplotlib, Agg 后端）

中文字体自动检测: PingFang SC → Heiti SC → STHeiti → Arial Unicode MS → SimHei

**目标公司分析图（2×2 四象限，16×12）：**

| 位置 | 内容 |
|------|------|
| 左上 | 营收 & 归母净利润柱状图（双Y轴，含营收同比增速折线） |
| 右上 | 毛利率 / 净利率 / ROE 趋势折线图 |
| 左下 | 存货/应收周转天数柱状图 + CCC折线 + 资产负债率折线 |
| 右下 | 经营现金流 vs 归母净利润柱状图（标注净现比 x 倍） |

保存: `output/charts/{code}_财务分析.png`（150dpi）

**可比公司对比图（1×3，18×6）：**

| 位置 | 内容 |
|------|------|
| 左 | 营收规模对比柱状图（目标公司高亮） |
| 中 | 毛利率 / ROE 分组柱状图 |
| 右 | PE / PB 估值散点图（目标公司用菱形标记） |

保存: `output/charts/可比公司对比.png`（150dpi）

### 8. CLI 入口 `main()` + `_run()`

`main()` 处理参数解析、登录/登出；`_run()` 在登录态下执行核心逻辑：
1. 批量抓取所有公司 → `fetch_all_indicators`
2. 转换为 history → `raw_to_history`
3. 打印数据概览
4. 导出 XLSX → `export_xlsx`
5. 导出可比对比表（如有）
6. 生成图表（除非 `--no-chart`）

## 关键设计决策

1. **指标 ID 可配置** — 全部集中在 `INDICATOR_MAP`，验证后一处修改
2. **优雅降级** — iFinDPy 未安装时打印指引而非 ImportError
3. **API 限额友好** — 合并请求，一次传入多代码多指标
4. **输出兼容** — XLSX 格式可被模块03 `_extract_year_columns` + `_pick_metric_row` 直接读取
5. **分产品数据** — iFinD 无标准化接口，保留手动 XLSX 导入兼容

## 验证清单

- [ ] `python3 -m py_compile tools/ifind_fetcher.py`
- [ ] 安装 iFinDPy 后执行 `--code 688102.SH` 验证登录和抓取
- [ ] 检查 `output/charts/` 下图片
- [ ] 检查导出的 XLSX 能被模块03正确读取
