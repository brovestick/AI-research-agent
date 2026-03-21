#!/usr/bin/env python3
"""券商研报智能预处理 —— PDF → 结构化 JSON

用法：
    python3 broker_rpt_extract.py <pdf_path> [--out output.json]

流程：
    1. pdfplumber 全文提取文本 + 表格（复用 pdf_extract.py）
    2. Qwen3.5 Plus 识别研报类型（首次覆盖 / 深度 / 业绩点评 / 事件点评）
    3. 按类型选择对应 Schema，Qwen3.5 Plus 定向提取结构化字段
    4. 输出标准化 JSON → 供 Claude Code 下游分析

依赖：
    pip install pdfplumber openai
    同目录下需有 pdf_extract.py

环境变量：
    DASHSCOPE_API_KEY   阿里云 DashScope API Key
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path

import pdfplumber

# 从同目录导入 pdf_extract 的表格函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_extract import extract_tables_with_merge, table_to_markdown

# ── Qwen 客户端初始化（DashScope OpenAI 兼容接口）──────────────

try:
    from openai import OpenAI
    _client = OpenAI(
        api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
except ImportError:
    _client = None
    print("[WARNING] openai 未安装，LLM 功能不可用", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════
# 第一阶段：PDF 文本 + 表格提取
# ══════════════════════════════════════════════════════════════════

def extract_pdf(pdf_path: str):
    """全文提取，返回结构化原始数据。

    Returns
    -------
    dict:
        pages      : list[dict{page_num, text}]
        tables     : list[list[list]]   （合并后的表格，二维列表）
        total_pages: int
        front_text : str   前5页文本拼接（用于分类）
    """
    pages_data = []
    all_pages_obj = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_data.append({"page_num": i + 1, "text": text})
            all_pages_obj.append(page)

        tables = extract_tables_with_merge(all_pages_obj)

    front_text = "\n".join(
        p["text"] for p in pages_data[:5] if p["text"]
    )

    return {
        "pages": pages_data,
        "tables": tables,
        "total_pages": total,
        "front_text": front_text,
    }


# ══════════════════════════════════════════════════════════════════
# 第二阶段：报告类型识别
# ══════════════════════════════════════════════════════════════════

REPORT_TYPES = {
    "首次覆盖": "first_coverage",
    "公司深度": "deep_dive",
    "业绩点评": "earnings_review",
    "事件点评": "event_review",
    "未知": "unknown",
}

_CLASSIFY_PROMPT = """你是金融研报分类专家。请根据以下研报前几页内容，判断报告类型。

报告类型定义：
- 首次覆盖（first_coverage）：首次对该公司发布研究报告，通常包含完整的公司介绍、商业模式分析、行业分析、估值模型。
- 公司深度（deep_dive）：对某一主题/业务线做专项深入研究，篇幅较长，通常不是首次覆盖。
- 业绩点评（earnings_review）：针对公司季度/年度财务数据发布的简短点评，通常含业绩数据对比和预测更新。
- 事件点评（event_review）：针对特定事件（政策、并购、产品发布等）的简短点评。
- 未知（unknown）：无法判断。

仅输出 JSON，格式如下（不要输出其他内容）：
{{
  "report_type": "<first_coverage|deep_dive|earnings_review|event_review|unknown>",
  "confidence": "<high|medium|low>",
  "reason": "<一句话说明判断依据>"
}}

---
研报内容：
{front_text}
"""


def classify_report(front_text: str) -> dict:
    """调用 Qwen 识别报告类型。"""
    if _client is None:
        return {"report_type": "unknown", "confidence": "low", "reason": "Qwen 不可用"}

    prompt = _CLASSIFY_PROMPT.format(front_text=front_text[:3000])

    resp = _client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    return _safe_json(raw, default={"report_type": "unknown"})


# ══════════════════════════════════════════════════════════════════
# 第三阶段：按类型定向提取
# ══════════════════════════════════════════════════════════════════

# ── Schema 定义 ──────────────────────────────────────────────────

_SCHEMA_FIRST_COVERAGE = """
请从研报中提取以下字段，仅输出 JSON，不要输出其他内容。

提取原则：
- 重点提炼"为什么看好这家公司"的定性逻辑，而非具体财务数值
- growth_estimates 是列表：把该逻辑下研报明确给出的所有定量数据点都填入，
  每个数据点包含指标名和数值（如里程、增速、市场规模等），找不到填空列表 []
- 不要从盈利预测表中摘取数字；只提取论述性文字中附带的数据
- 字段找不到时填 null，不要猜测或推断

{
  "company_name": "公司名称",
  "ticker": "股票代码（如 600519.SH）",
  "rating": "投资评级",
  "target_price": "目标价（数字，单位元），找不到填 null",
  "current_price": "当前价（数字，单位元）",
  "industry": "所属行业",
  "business_desc": "公司主营业务简述（2-3句，说清楚公司靠什么赚钱）",

  "investment_thesis": "研报看好该公司的一句话核心判断",

  "business_segments": [
    {
      "name": "业务线名称（如：高强高导铜合金材料及制品）",
      "revenue_share": "该业务营收占比（如：62%），找不到填 null",
      "gross_margin": "该业务毛利率，找不到填 null",
      "key_products": ["代表性产品1", "代表性产品2"],
      "downstream": ["下游应用领域1", "下游应用领域2"],
      "segment_status": "业务现阶段描述（1-2句：规模、增速、供需状态）",
      "industry_outlook": "研报对该业务所在行业发展态势的论述（2-4句，包含行业规模、增速、政策驱动等）"
    }
  ],

  "capacity_by_product": [
    {
      "product": "产品或业务名称",
      "current_capacity": "现有产能或规模（数字+单位，如：800吨/年、5000万件/年、100MW；非制造业可填服务规模），找不到填 null",
      "utilization_rate": "产能利用率或满载率（如：80%以上），找不到填 null",
      "output_trend": "产量/产出变化趋势（1句，如：2018-2021年产量从X增至Y；或：逐年增长但绝对规模仍小）"
    }
  ],

  "growth_drivers": [
    {
      "driver": "增长驱动因素名称（尽量具体，如：铁路网扩张带动牵引电机端环需求）",
      "logic": "研报对该驱动因素的完整论述（尽量保留原文逻辑链，2-5句）",
      "growth_estimates": [
        {
          "metric": "指标名称（如：全国铁路营业里程、电化率、市场规模CAGR）",
          "value": "具体数值或区间（如：从12.4万公里增至14.63万公里）"
        }
      ]
    }
  ],

  "competitive_advantages": [
    {
      "advantage": "竞争优势/壁垒名称",
      "description": "研报对该壁垒的具体论述（2-3句）"
    }
  ],

  "competitive_landscape": "行业竞争格局：公司所处位置、主要竞争对手、格局集中度（3-5句）",

  "comparable_companies": [
    {
      "name": "可比公司名称",
      "ticker": "股票代码，找不到填 null",
      "pe_current_year": "当年预测PE（数字），找不到填 null",
      "pe_next_year": "次年预测PE（数字），找不到填 null",
      "note": "与目标公司的异同点（1句），找不到填 null"
    }
  ],

  "primary_growth_curve": {
    "name": "主增长曲线名称",
    "description": "该曲线的增长逻辑和现阶段特征（2-4句）",
    "growth_estimates": [
      {"metric": "指标名称", "value": "数值"}
    ]
  },

  "second_growth_curve": {
    "exists": true,
    "name": "第二增长曲线名称，不存在填 null",
    "description": "第二曲线的业务描述和研报对其前景的判断（2-4句），不存在填 null",
    "maturity": "early_stage / scaling / mature，不确定填 null",
    "growth_estimates": []
  },

  "capital_allocation": {
    "type": "资本用途类型（IPO募投/定增扩产/研发投入/收购并购/其他），找不到填 null",
    "total_amount": "资金规模（数字+单位，如：3.62亿元/36208.76万元），找不到填 null",
    "project_name": "项目名称，找不到填 null",
    "capacity_or_output_added": "新增产能/产出描述（数字+单位，如：新增产能2万吨；或：新增2座工厂；无产能概念则填对应描述），找不到填 null",
    "breakdown": [
      {
        "category": "类别名称（如：铬锆铜合金材料/研发中心/新业务线扩张）",
        "amount_or_capacity": "该类别投入金额或产能（数字+单位）",
        "details": "细项描述（1-2句），找不到填 null"
      }
    ],
    "ramp_up_schedule": "投产/达产/落地时间计划（如：建设周期24个月；第1年达产26%），找不到填 null",
    "strategic_rationale": "研报对该资本配置战略意义的判断（2-3句）"
  },

  "earnings_forecast": {
    "pricing_assumptions": [
      {
        "segment": "业务线名称",
        "pricing_mechanism": "定价机制描述（如：原材料+加工费定价；历史价格趋势外推；市场定价等）",
        "margin_sensitivity": "毛利率对原材料/价格波动的敏感性描述（1句），找不到填 null"
      }
    ],
    "segment_margins": [
      {
        "segment": "业务线名称",
        "gross_margin_actual": "最近实际年度毛利率（如：17.5%，标注年份）",
        "gross_margin_forecast": "研报预测的未来毛利率趋势或区间（1句），找不到填 null"
      }
    ],
    "segment_revenues": [
      {
        "segment": "业务线名称（需与 segment_margins 保持一致）",
        "revenue_actual": "最近实际年度营收规模（数字+单位+年份，如：5.34亿元（2023年）），找不到填 null",
        "revenue_forecast": "研报预测的未来各年营收规模（按年列出，如：2024E/2025E/2026E分别为5.58/6.46/7.86亿元），找不到填 null"
      }
    ],
    "segment_revenue_growth": [
      {
        "segment": "业务线名称（需与 segment_margins 保持一致）",
        "yoy_actual": "最近实际年度营收同比增速（如：20.83%（2023年）），找不到填 null",
        "yoy_forecast": "研报预测的未来各年营收同比增速YOY（按年列出，如：2024E/2025E/2026E分别为4.41%/15.87%/21.69%），找不到填 null"
      }
    ],
    "revenue_growth_assumption": "研报对整体营收增速的核心假设（1-2句，如：募投产能释放带动增速，原材料价格企稳后毛利率改善）"
  },

  "valuation_methodology": {
    "method": "估值方法（如：PE估值/DCF/PB/PS/EV-EBITDA/分部估值），找不到填 null",
    "target_multiple": "目标估值倍数或参数（如：25倍PE；1.5倍PB），找不到填 null",
    "benchmark": "估值基准年份或参数（如：基于2025E EPS），找不到填 null",
    "rationale": "估值依据（1-2句，为什么用这个方法和倍数），找不到填 null"
  },

  "key_risks": [
    {
      "risk": "风险名称",
      "description": "风险的具体描述（1-2句）"
    }
  ],

  "analyst": "分析师姓名",
  "publish_date": "发布日期 YYYY-MM-DD",
  "broker": "券商名称"
}
"""

_SCHEMA_DEEP_DIVE = """
请从研报中提取以下字段，仅输出 JSON，不要输出其他内容。

提取原则：
- 深度报告通常聚焦某一核心主题，先识别该主题，再围绕主题提炼逻辑
- growth_estimates 是列表，把该逻辑下所有明确给出的定量数据点都填入
- 字段找不到时填 null，不要猜测；列表找不到时填空列表 []

{
  "company_name": "公司名称",
  "ticker": "股票代码",
  "rating": "投资评级",
  "target_price": "目标价（数字，单位元），找不到填 null",
  "current_price": "当前价（数字，单位元），找不到填 null",
  "industry": "所属行业",
  "report_theme": "本次深度报告的核心研究主题（一句话，如：深度拆解公司海外业务扩张逻辑）",

  "investment_thesis": "研报对该公司/主题的一句话核心判断",

  "business_segments": [
    {
      "name": "业务线名称",
      "revenue_share": "营收占比，找不到填 null",
      "gross_margin": "毛利率，找不到填 null",
      "key_products": ["代表性产品1", "代表性产品2"],
      "downstream": ["下游应用领域1"],
      "segment_status": "业务现阶段描述（1-2句）",
      "industry_outlook": "行业发展态势论述（2-4句），找不到填 null"
    }
  ],

  "growth_drivers": [
    {
      "driver": "增长驱动因素名称",
      "logic": "研报对该驱动因素的完整论述（尽量保留原文逻辑链，2-5句）",
      "growth_estimates": [
        {"metric": "指标名称", "value": "具体数值或区间"}
      ]
    }
  ],

  "competitive_advantages": [
    {
      "advantage": "竞争优势/壁垒名称",
      "description": "研报对该壁垒的具体论述（2-3句）"
    }
  ],

  "competitive_landscape": "行业竞争格局判断：公司处于什么位置，与竞争对手的差异化在哪里（3-5句）",

  "comparable_companies": [
    {
      "name": "可比公司名称",
      "ticker": "股票代码，找不到填 null",
      "pe_current_year": "当年预测PE（数字），找不到填 null",
      "pe_next_year": "次年预测PE（数字），找不到填 null",
      "note": "与目标公司的异同点（1句），找不到填 null"
    }
  ],

  "primary_growth_curve": {
    "name": "主增长曲线名称",
    "description": "该曲线的增长逻辑和现阶段特征（2-4句）",
    "growth_estimates": [{"metric": "指标名称", "value": "数值"}]
  },

  "second_growth_curve": {
    "exists": true,
    "name": "第二增长曲线名称，不存在填 null",
    "description": "第二曲线的业务描述和前景判断（2-4句），不存在填 null",
    "maturity": "early_stage / scaling / mature，不确定填 null",
    "growth_estimates": []
  },

  "key_findings": [
    {
      "finding": "重要发现/结论（一句话）",
      "evidence": "研报给出的支撑证据或数据（1-3句）"
    }
  ],

  "earnings_forecast": {
    "pricing_assumptions": [
      {
        "segment": "业务线名称",
        "pricing_mechanism": "定价机制描述，找不到填 null",
        "margin_sensitivity": "毛利率对价格/成本波动的敏感性描述（1句），找不到填 null"
      }
    ],
    "segment_margins": [
      {
        "segment": "业务线名称",
        "gross_margin_actual": "最近实际年度毛利率（标注年份），找不到填 null",
        "gross_margin_forecast": "预测毛利率趋势（1句），找不到填 null"
      }
    ],
    "segment_revenues": [
      {
        "segment": "业务线名称（需与 segment_margins 保持一致）",
        "revenue_actual": "最近实际年度营收规模（数字+单位+年份，如：5.34亿元（2023年）），找不到填 null",
        "revenue_forecast": "研报预测的未来各年营收规模（按年列出，如：2024E/2025E/2026E分别为5.58/6.46/7.86亿元），找不到填 null"
      }
    ],
    "segment_revenue_growth": [
      {
        "segment": "业务线名称（需与 segment_margins 保持一致）",
        "yoy_actual": "最近实际年度营收同比增速（如：20.83%（2023年）），找不到填 null",
        "yoy_forecast": "研报预测的未来各年营收同比增速YOY（按年列出，如：2024E/2025E/2026E分别为4.41%/15.87%/21.69%），找不到填 null"
      }
    ],
    "revenue_growth_assumption": "整体营收增速核心假设（1-2句），找不到填 null"
  },

  "valuation_methodology": {
    "method": "估值方法（如：PE/DCF/PB/PS/EV-EBITDA/分部估值），找不到填 null",
    "target_multiple": "目标估值倍数或参数，找不到填 null",
    "benchmark": "估值基准年份或参数，找不到填 null",
    "rationale": "估值依据（1-2句），找不到填 null"
  },

  "key_risks": [
    {
      "risk": "风险名称",
      "description": "风险的具体描述（1-2句）"
    }
  ],

  "analyst": "分析师姓名（多人用顿号分隔）",
  "publish_date": "发布日期 YYYY-MM-DD",
  "broker": "券商名称"
}
"""

_SCHEMA_EARNINGS_REVIEW = """
请从研报中提取以下字段，仅输出 JSON，不要输出其他内容。

提取原则：
- 所有数字字段找不到时填 null，不要猜测
- 定性描述（yoy_qualitative 等）与定量字段（yoy_pct）并行，二选一或均填
- publish_date 是时效性判断基准，必须准确提取
- performance_drivers 要区分经常性/一次性因素，这是判断业绩质量的关键
- product_progress 针对科技/成长型公司填写，无产品进展内容则填空列表

{
  "company_name": "公司名称",
  "ticker": "股票代码",
  "publish_date": "发布日期 YYYY-MM-DD（时效性判断基准，必填）",
  "broker": "券商名称",
  "analyst": "分析师姓名（多人用顿号分隔）",

  "rating": "投资评级",
  "rating_change": "评级变化（维持/上调/下调/首次给予）",
  "target_price": "目标价（数字，单位元），找不到填 null",
  "target_price_change": "目标价变化（上调/下调/维持/首次给予），找不到填 null",
  "current_price": "当前价（数字，为 publish_date 时的价格）",

  "reporting_period": "主报告期（如 2025H1 / 2024Q3 / 2024年报）",

  "financials": {
    "revenue_bn": "主报告期收入（数字，亿元）",
    "revenue_yoy": "收入同比增速（数字，百分比，如 2.49）",
    "gross_margin_pct": "综合毛利率（数字，百分比，如 56.80）",
    "gross_margin_yoy_pct": "毛利率同比变化（百分点，如 +0.31 或 -1.20），找不到填 null",
    "operating_profit_bn": "营业利润（数字，亿元），找不到填 null",
    "net_profit_bn": "归母净利润（数字，亿元）",
    "net_profit_yoy": "归母净利润同比增速（数字，百分比）",
    "net_profit_excl_nonrecurring_bn": "扣非归母净利润（数字，亿元），找不到填 null",
    "net_profit_excl_nonrecurring_yoy": "扣非净利润同比（数字，百分比），找不到填 null",
    "operating_cash_flow_bn": "经营活动现金流（数字，亿元），研报未提及填 null"
  },

  "sub_period_financials": {
    "period": "子区间名称（如 2Q25；若研报未单独披露单季度数据则整个字段填 null）",
    "revenue_bn": "子区间收入（数字，亿元）",
    "revenue_yoy": "收入同比（数字，百分比）",
    "revenue_qoq": "收入环比（数字，百分比），找不到填 null",
    "net_profit_bn": "归母净利润（数字，亿元）",
    "net_profit_yoy": "净利润同比（数字，百分比）",
    "net_profit_qoq": "净利润环比（数字，百分比），找不到填 null",
    "gross_margin_pct": "子区间毛利率（数字，百分比），找不到填 null"
  },

  "vs_expectation": "业绩与市场预期对比（超预期/符合预期/低于预期）",

  "performance_drivers": [
    {
      "factor": "因素名称（如：存货跌价损失增加 / FPGA收入高增 / 政府补贴减少）",
      "direction": "正面/负面",
      "nature": "recurring（经常性，反映业务基本面）/ one_time（一次性，不反映持续经营）",
      "description": "具体描述（1-2句，说清楚为什么发生）",
      "quantified_impact": "量化影响（如有，如：计提存货跌价损失1.43亿元），找不到填 null"
    }
  ],

  "segment_breakdown": [
    {
      "segment": "业务线名称",
      "revenue_bn": "收入（数字，亿元），找不到填 null",
      "yoy_pct": "同比增速（数字，百分比），有具体数字时填",
      "yoy_qualitative": "同比方向定性描述（如：同比有所下滑），无具体数字时填，有数字则填 null",
      "gross_margin_pct": "该业务线毛利率，找不到填 null",
      "key_observation": "核心观察（1句，说清楚这条业务线最值得关注的点）"
    }
  ],

  "balance_sheet_highlights": {
    "inventory_bn": "存货规模（数字，亿元），找不到填 null",
    "inventory_yoy_pct": "存货同比变化，找不到填 null",
    "impairment_total_bn": "本期计提各项减值损失合计（数字，亿元），找不到填 null",
    "impairment_breakdown": [
      {"item": "减值项目名称（如：存货跌价损失）", "amount_bn": "金额（数字，亿元）"}
    ],
    "accounts_receivable_bn": "应收账款（数字，亿元），找不到填 null",
    "cash_bn": "货币资金（数字，亿元），找不到填 null",
    "other_notes": "其他值得关注的资产负债表变化（1-2句），无则填 null"
  },

  "product_progress": [
    {
      "product_name": "产品或技术名称（如：FPAI 32TOPS芯片 / 1xnm FinFET FPGA）",
      "status": "研发中/客户导入/量产/推广中/已量产",
      "key_milestone": "关键进展描述（1-2句，说清楚当前到了哪个阶段）",
      "strategic_significance": "对公司的战略意义（1句）"
    }
  ],

  "updated_earnings_forecast": {
    "timeliness_note": "以下预测基于 publish_date 时点，使用前请确认时效性",
    "forecasts": [
      {
        "year": "年份（数字）",
        "revenue_bn": "预测营收（数字，亿元），找不到填 null",
        "net_profit_bn": "预测归母净利润（数字，亿元）",
        "growth_rate_pct": "净利润增速（数字，百分比）",
        "pe": "对应PE倍数（数字），找不到填 null"
      }
    ]
  },

  "key_takeaway": "核心观点一句话（研报最想传达的判断，结合业绩质量+前景判断）",

  "forward_catalysts": [
    {
      "catalyst": "催化剂名称（如：FPAI新品量产放量 / 存货结构改善）",
      "timeline": "预期发生时间（如：2025H2 / 2026年），不确定填 null",
      "significance": "重要性说明（1句，为什么这个催化剂重要）"
    }
  ],

  "key_risks": [
    {"risk": "风险名称", "description": "风险描述（1-2句）"}
  ]
}
"""

_SCHEMA_EVENT_REVIEW = """
请从研报中提取以下字段，仅输出 JSON，不要输出其他内容。

提取原则：
- 事件点评的核心价值在于研报的分析逻辑，而非目标价/评级数字
- impact_on_thesis 是关键字段：研报是否因该事件修正了对公司的判断
- 所有字段找不到时填 null，不要猜测

{
  "company_name": "公司名称",
  "ticker": "股票代码",
  "publish_date": "发布日期 YYYY-MM-DD（时效性判断基准，必填）",
  "broker": "券商名称",
  "analyst": "分析师姓名（多人用顿号分隔）",

  "rating": "投资评级",
  "rating_change": "评级变化（维持/上调/下调/首次给予）",
  "target_price": "目标价（数字，单位元，为 publish_date 时的判断），找不到填 null",
  "target_price_change": "目标价变化（上调/下调/维持/首次给予），找不到填 null",
  "current_price": "当前价（数字，为 publish_date 时的价格），找不到填 null",

  "event_date": "事件发生/披露日期 YYYY-MM-DD，找不到填 null",
  "event_summary": "事件一句话描述（what happened，尽量具体）",
  "event_nature": "事件性质（利好/利空/中性/混合）",

  "impact_on_thesis": {
    "thesis_changed": "研报是否因此事件修正了对公司的核心判断（是/否）",
    "change_description": "如有修正，说明修正了哪个判断（1-2句）；无修正填 null"
  },

  "impact_analysis": [
    {
      "dimension": "影响维度（如：收入端 / 成本端 / 竞争格局 / 政策监管 / 融资能力）",
      "timeframe": "影响时效（short_term短期<1年 / mid_term中期1-3年 / long_term长期>3年）",
      "direction": "正面/负面/中性",
      "analysis": "研报对该维度影响的具体分析（2-3句，保留原始逻辑链）"
    }
  ],

  "market_expectation_gap": "市场预期差判断：研报认为市场是否已充分定价此事件，以及为什么（2-3句），找不到填 null",

  "investment_suggestion": "研报的投资建议及核心逻辑（2-3句）",

  "forward_catalysts": [
    {
      "catalyst": "催化剂名称",
      "timeline": "预期时间（如：未来3-6个月），不确定填 null",
      "significance": "重要性说明（1句）"
    }
  ],

  "key_risks": [
    {"risk": "风险名称", "description": "风险描述（1-2句）"}
  ]
}
"""

_SCHEMAS = {
    "first_coverage": _SCHEMA_FIRST_COVERAGE,
    "deep_dive": _SCHEMA_DEEP_DIVE,
    "earnings_review": _SCHEMA_EARNINGS_REVIEW,
    "event_review": _SCHEMA_EVENT_REVIEW,
}

# ── 首页摘要提取 Prompt ──────────────────────────────────────────

_FIRST_PAGE_PROMPT = """你是专业金融研报信息提取助手。

研报第一页通常是全文的"核心摘要"，集中呈现了分析师最想传达的关键判断。
请完整提取第一页的所有实质性内容，识别并列出其中涉及的**每一个核心论点**。

输出格式要求（仅输出 JSON，不要加 markdown 代码块）：
{{
  "publish_date": "发布日期 YYYY-MM-DD，找不到填 null",
  "company_name": "公司名称",
  "ticker": "股票代码",
  "broker": "券商名称",
  "analyst": "分析师姓名",
  "rating": "投资评级",
  "target_price": "目标价（数字），找不到填 null",
  "current_price": "当前价（数字），找不到填 null",
  "key_points": [
    {{
      "point": "核心论点标题（5-10字概括）",
      "content": "该论点的完整表述，尽量保留原文关键措辞（2-4句）",
      "has_growth_estimate": true,
      "growth_estimate": "该论点中明确提到的增长率或规模估计，没有填 null"
    }}
  ],
  "investment_advice_summary": "投资建议核心一句话",
  "risk_highlights": ["风险要点1", "风险要点2"]
}}

---
研报第一页内容：
{first_page_text}
"""

# ── 正文补充提取 Prompt ──────────────────────────────────────────

_BODY_EXTRACT_PROMPT_TPL = """你是专业金融研报信息提取助手。

【任务说明】
研报第一页摘要已提取完毕（见下方"已提取摘要"）。
现在请阅读研报正文，对摘要中每个核心论点进行**扩展补充**，并提取摘要中未覆盖的深度内容。

【提取原则】
- 以摘要论点为锚点，在正文中寻找对应的详细论述、数据支撑、案例佐证
- 增长率等定量估计：仅当正文在论述某条具体逻辑时明确给出，才填入对应字段
- 盈利预测表中的数字【不要提取】，只提取论述性文字中附带的增长率判断
- 时效性敏感字段（投资建议、目标价、盈利预测）务必记录研报发布日期，Claude Code 分析时需结合时效性判断参考价值
- 字段找不到时填 null，不要猜测

【已提取摘要】
{first_page_summary}

【Schema】
{schema}

---
研报正文（第2页起）：
{body_text}

---
表格内容（Markdown 格式）：
{tables_md}
"""


def extract_first_page_summary(first_page_text: str) -> dict:
    """提取研报第一页的核心摘要内容。"""
    if _client is None:
        return {"error": "Qwen 不可用"}

    prompt = _FIRST_PAGE_PROMPT.format(first_page_text=first_page_text[:4000])

    resp = _client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    return _safe_json(raw, default={"raw_response": raw})


def extract_structured(first_page_summary: dict, body_text: str,
                       tables: list, report_type: str) -> dict:
    """两阶段提取：以首页摘要为锚，从正文补充深度内容。"""
    if _client is None:
        return {"error": "Qwen 不可用"}

    schema = _SCHEMAS.get(report_type, _SCHEMA_EVENT_REVIEW)
    tables_md = "\n\n".join(table_to_markdown(t) for t in tables) if tables else "（无表格）"
    summary_text = json.dumps(first_page_summary, ensure_ascii=False, indent=2)

    # ── 动态截断：按实际可用空间分配，而非硬编码 ──────────────────
    # Qwen-Plus 上下文窗口 131072 token；中文约 1.5 字符/token，保守取 1.8
    # 留出 schema + prompt 模板 + 摘要 + 输出的固定开销（约 8K token ≈ 14400 字符）
    MODEL_CTX_CHARS  = int(131_072 / 1.8)  # ≈ 72817 字符（可用上限）
    FIXED_OVERHEAD   = 14_400               # schema + 模板 + 摘要 + 预留输出
    SUMMARY_BUDGET   = min(2000, len(summary_text))
    available        = MODEL_CTX_CHARS - FIXED_OVERHEAD - SUMMARY_BUDGET

    # body_text 优先级高于 tables_md（表格信息多已在正文中有文字描述）
    # 分配比例：body 75% / tables 25%，但各自不超过实际长度
    body_budget   = min(int(available * 0.75), len(body_text))
    tables_budget = min(int(available * 0.25), len(tables_md))

    # 若 body 未用满，将剩余空间让给 tables（反之亦然）
    body_spare   = int(available * 0.75) - body_budget
    tables_spare = int(available * 0.25) - tables_budget
    body_budget  += tables_spare
    tables_budget += body_spare

    _info(f"  正文长度: {len(body_text):,} 字符 → 实际送入: {body_budget:,}")
    _info(f"  表格长度: {len(tables_md):,} 字符 → 实际送入: {tables_budget:,}")
    if len(body_text) > body_budget:
        _info("  [警告] 正文被截断，盈利预测章节可能在报告后半段，建议检查输出完整性")

    prompt = _BODY_EXTRACT_PROMPT_TPL.format(
        first_page_summary=summary_text[:SUMMARY_BUDGET],
        schema=schema,
        body_text=body_text[:body_budget],
        tables_md=tables_md[:tables_budget],
    )

    resp = _client.chat.completions.create(
        model="qwen3.5-plus",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    return _safe_json(raw, default={"raw_response": raw})


# ══════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════

def _safe_json(text: str, default=None):
    """安全解析 JSON，容忍 markdown 代码块包裹。"""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { ... } 块
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return default if default is not None else {}


def _build_full_text(pages_data: list) -> str:
    """将所有页文本拼接为单一字符串。"""
    return "\n".join(
        f"[Page {p['page_num']}]\n{p['text']}"
        for p in pages_data if p["text"]
    )


def _find_summary_end(pages_data: list, max_pages: int = 3) -> int:
    """找到摘要部分的最后一页索引（0-based）。

    策略：从第1页开始逐页检查是否包含"风险提示"关键词，
    找到后即认为摘要结束于该页。上限 max_pages 页，防止极端情况。
    若未找到则默认仅取第1页（索引0）。
    """
    keywords = ("风险提示",)
    limit = min(max_pages, len(pages_data))
    for i in range(limit):
        text = pages_data[i].get("text", "")
        if any(kw in text for kw in keywords):
            return i  # 找到风险提示，摘要结束于第 i 页
    return 0  # 未找到，保守取第1页


def _build_summary_text(pages_data: list, end_idx: int) -> str:
    """拼接摘要页（第1页到 end_idx 页，含）。"""
    return "\n".join(
        f"[Page {p['page_num']}]\n{p['text']}"
        for p in pages_data[:end_idx + 1] if p["text"]
    )


def _build_body_text(pages_data: list, start_idx: int = 1) -> str:
    """从 start_idx 页起拼接正文（跳过摘要部分，避免重复）。"""
    return "\n".join(
        f"[Page {p['page_num']}]\n{p['text']}"
        for p in pages_data[start_idx:] if p["text"]
    )


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════

def process(pdf_path: str, out_path: str | None = None) -> dict:
    """完整预处理流水线，返回结构化 JSON dict。

    流程：
        1. PDF 文本/表格提取
        2. 报告类型识别（GLM，仅读前5页）
        3. 首页摘要提取（GLM，精读第1页）
        4. 正文深度提取（GLM，以首页摘要为锚，补充正文内容）
        5. 组装输出 JSON
    """
    _info(f"处理文件: {pdf_path}")

    # 1. PDF 提取
    _info("第一阶段：PDF 文本/表格提取...")
    raw = extract_pdf(pdf_path)
    _info(f"  共 {raw['total_pages']} 页，提取表格 {len(raw['tables'])} 个")

    summary_end = _find_summary_end(raw["pages"])
    first_page_text = _build_summary_text(raw["pages"], summary_end)
    body_text = _build_body_text(raw["pages"], start_idx=summary_end + 1)
    _info(f"  摘要范围：第1页～第{summary_end + 1}页，正文从第{summary_end + 2}页起")

    # 2. 类型识别（基于前5页）
    _info("第二阶段：报告类型识别...")
    classify_result = classify_report(raw["front_text"])
    report_type = classify_result.get("report_type", "unknown")
    _info(f"  识别结果: {report_type} (confidence={classify_result.get('confidence')})")
    _info(f"  原因: {classify_result.get('reason')}")

    # 3. 首页摘要提取
    _info("第三阶段：首页核心摘要提取...")
    first_page_summary = extract_first_page_summary(first_page_text)
    publish_date = first_page_summary.get("publish_date", "unknown")
    _info(f"  研报发布日期: {publish_date}")
    _info(f"  提取到 {len(first_page_summary.get('key_points', []))} 个首页核心论点")

    # 4. 正文深度提取（以首页摘要为锚）
    _info(f"第四阶段：按 [{report_type}] schema 从正文补充深度内容...")
    structured = extract_structured(
        first_page_summary, body_text, raw["tables"], report_type
    )

    # 5. 组装最终输出
    output = {
        "meta": {
            "source_file": str(Path(pdf_path).name),
            "total_pages": raw["total_pages"],
            "report_type": report_type,
            "publish_date": publish_date,
            "classify_confidence": classify_result.get("confidence"),
            "classify_reason": classify_result.get("reason"),
            # 时效性提示：供 Claude Code 判断数据参考价值
            "timeliness_note": (
                f"本报告发布于 {publish_date}，其中投资评级、目标价、"
                "盈利预测等字段具有时效性，分析时请结合当前时间判断参考价值。"
                "投资逻辑、竞争格局、增长驱动等定性内容时效性相对较强。"
            ),
        },
        # 首页摘要（独立保留，供 Claude Code 快速概览）
        "first_page_summary": first_page_summary,
        # 正文深度提取结果
        "structured": structured,
    }

    # 6. 输出
    json_str = json.dumps(output, ensure_ascii=False, indent=2)
    if out_path:
        Path(out_path).write_text(json_str, encoding="utf-8")
        _info(f"已保存至: {out_path}")
    else:
        print(json_str)

    _info("完成")
    return output


def _info(msg):
    print(f"[INFO] {msg}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="券商研报预处理 PDF → JSON")
    parser.add_argument("pdf_path", help="研报 PDF 路径")
    parser.add_argument("--out", "-o", help="输出 JSON 路径（省略则打印到 stdout）")
    args = parser.parse_args()

    process(args.pdf_path, args.out)


if __name__ == "__main__":
    main()
