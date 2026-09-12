# Skill: News Analysis

## Goal

Identify whether a market story contains new, material information worth reading.

## Importance

Rate 1–10:

- 9–10: Major market-moving information
- 7–8: Material new information
- 5–6: Relevant but not urgent
- 3–4: Low-value commentary
- 1–2: Noise or recycled information

Before giving 7+, ask:

**What materially changed?**

If there is no clear answer, score below 7.

## Evidence Wording

Do not strengthen the source language.

If the evidence says "may", "could", "expected", "reportedly", or uses cautious wording,
preserve that level of uncertainty.

Do not turn indirect relationships into confirmed causal claims.

## Prioritize

Pay attention to developments affecting:

AMD, NVDA, SPY, QQQ, AVGO, TSM, ARM, MU, INTC, MSFT, META, GOOGL, AMZN.

Also prioritize:

Fed, rates, CPI, PCE, jobs, GDP, Treasury yields, VIX, oil, geopolitics, and semiconductor restrictions.

Watchlist membership alone must not increase the importance score.

## Reduce Importance

Lower scores for:

- Opinion pieces
- Stock comparisons
- Price-target articles
- Minor institutional holdings
- Clickbait
- Recycled news

## Output

Return:

- `importance`: integer 1–10
- `sentiment`: bullish, bearish, mixed, or neutral
- `affected`: relevant ticker symbols only
- `why_read`: one sentence maximum

`why_read` should explain **why the new information matters**, not repeat the headline.