Skill: Catalyst Triage

Goal

Select supplied articles worth investigating as potential drivers of the supplied market move; do not establish causation.

Selection

Select only supplied article IDs, up to the application's maximum; prefer one representative per event. Empty candidates is valid.

Favor concrete company/sector developments: earnings, outlook, contracts, financing, regulation, leadership, and operations. Do not require a favored event type or reject small issuers automatically.

Prefer event detail over dramatic headlines, provider scores, generic forecasts, ownership recaps, and repetitive price summaries. Use supplied evidence of source quality, not publisher reputation alone.

Check event time against the market window. A later article may describe an earlier event; keep that distinction. Exclude an explicitly later event as a cause of the earlier move. When event timing is missing, state that uncertainty rather than inventing it.

Treat truncated summaries as partial evidence. Do not declare the full article irrelevant solely because omitted details are unavailable.

Relevance

8–10: Concrete material event with strong supplied relevance and timing support.
5–7: Plausible research lead with incomplete timing or context.
1–4: Weak connection; usually omit.

This score is investigative usefulness, not probability of causation or final news importance. Magnitude/sign agreement alone is not causal evidence.

Output

Use the application's candidates array, with unique entries containing:

article_id: exact supplied ID.

catalyst_relevance: integer 1–10.

reason: one sentence identifying the reported development and why it is a potential catalyst to investigate; include timing uncertainty when material.

Do not say "directly explains," "directly matches," or "confirmed catalyst." Do not infer reduced dilution or improved liquidity from debt repayment without supporting terms/context. A shorter factual reason is better than an invented financial benefit.