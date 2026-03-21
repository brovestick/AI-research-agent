# Sub-Query Generation Rules

## Purpose

For each search plan (Plans 1-3), decompose the plan description into
focused sub-queries suitable for web_search.

## Rules

1. Generate **1-3 sub-queries per plan** (strictly no more than 3).

2. Quantity guidelines:
   - Plan that decomposes/explains a theme concept: **1-2 sub-queries**
   - Plan that searches for related listed companies: **2-3 sub-queries**
   - Plan that gathers market data/trends: **2-3 sub-queries**

3. Each sub-query must be:
   - A **complete sentence** with a clear subject (not a keyword fragment)
   - **15-20 Chinese characters** in length (or equivalent specificity in English)
   - Free of numbering prefixes (no "1.", "2.", etc.)

4. Sub-queries should be **complementary, not overlapping** within the same plan.

5. The `time_qualifier` field indicates the time range to **incorporate into the query string**
   (e.g., append "近半年" or "2024年至今" to the query) — it is not a tool parameter.

## Output Format

For each plan, output a JSON array of sub-queries:

```json
{
  "plan_no": 1,
  "todo_items": [
    {"query": "人形机器人产业链上游核心零部件供应分析近半年", "time_qualifier": "past_half_year"},
    {"query": "人形机器人中游整机制造企业竞争格局2024年至今", "time_qualifier": "past_half_year"}
  ]
}
```

## Time Qualifier Reference

Default to `"past_half_year"` for all sub-queries unless the user's question
specifies a different time range.

| time_qualifier | 查询中附加的时间修饰词 |
|---|---|
| `past_month` | 近一个月 |
| `past_quarter` | 近三个月 |
| `past_half_year` | 近半年 |
| `past_year` | 近一年 / 2024年至今 |
| `all` | 不附加时间限定 |
