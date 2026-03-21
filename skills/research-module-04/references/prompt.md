你是一名专业的 A 股投资研究员。请对【{company}（{code}）】进行估值建模分析。

公司行业类型：{industry_type_cn}（{valuation_method} 法）

以下是前序分析得出的关键财务数据：
- 最新年营收：{revenue_latest} 亿元
- 最新年归母净利润：{net_profit_latest} 亿元
- 近三年营收复合增速：{revenue_cagr_3y}%
- 最新年毛利率：{gross_margin_latest}%
- 主要产品线：{main_products}
{price_shares_hint}
{consensus_hint}

请联网搜索该公司最新券商研报和盈利预测，完成以下分析：

## 一、市场核心看好逻辑
- 当前市场 / 券商最主流的 1-3 个增长驱动点是什么？
- 每个驱动点的核心逻辑（产品结构优化 / 新赛道 / 产能扩张 / 政策催化）

## 二、分产品三情景假设

按 [[three-scenario-assumption]] 框架，对每条主要产品线给出三情景分析。每个情景须绑定 [[observable-indicators]] 定义的可观测前瞻指标。每条增速假设须按 [[causal-chain-reasoning]] 展示完整因果链：原子假设分解（FACT / ASSUMPTION / PREDICTION）→ 传导机制与强度标注 → 偏误自检 → 关键变量敏感度标注。

## 三、未来三年财务预测（三情景）

按 [[three-scenario-assumption]] 框架汇总三情景预测表（{year+1}E / {year+2}E / {year+3}E）。

{price_shares_instruction}

{cyclical_section}

## 四、可比公司估值对标
{comps_hint}

请联网搜索 2-3 家可比公司的当前估值：

| 公司 | 股票代码 | 市值（亿元） | PE（TTM） | PB | 备注 |
|------|---------|------------|---------|-----|------|
| {company} | {code} | | | | 目标公司 |
| | | | | | 可比公司1 |
| | | | | | 可比公司2 |

基于以上对比，判断目标公司当前估值是否合理（偏贵 / 合理 / 偏便宜），并说明原因。
