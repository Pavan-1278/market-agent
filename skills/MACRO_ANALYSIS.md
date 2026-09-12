Skill: Macro Analysis

Goal

Assess a supplied macro development's possible implications for US equities and the core watchlist.

Focus

Fed policy, interest rates, CPI, PCE, jobs, GDP, Treasury yields, VIX, oil, geopolitics, and semiconductor restrictions.

Evidence Checks

Separate actual releases, consensus forecasts, prior values, and revisions. Claim a beat/miss or surprise only from supplied comparable expectations and results or explicitly attributed reporting.

Preserve period, release date, units, headline/core distinction, monthly/annual rates, annualization, and adjustment basis. Do not mix incompatible measures.

Distinguish an enacted decision from a proposal, speech, rumor, or analyst forecast; retain effective date, jurisdiction, and affected scope when supplied.

Use Python-provided basis-point changes, surprises, yield spreads, and market comparisons. Do not calculate or invent them.

Discuss conditional channels such as policy expectations, discount rates, demand, costs, or regulation. Do not mechanically label lower inflation bullish or higher growth bearish without the supplied context.

Keep observed price reactions separate from predicted effects. Missing consensus means surprise is unknown, not zero.

Output

Retain importance (integer 1–10), sentiment, affected, market_impact, and why_read.

7+ needs a concrete materially relevant development, not merely a macro keyword. Sentiment follows the evidenced context; use mixed/neutral when appropriate. affected is not the entire watchlist by default.

market_impact briefly states a supported, conditional transmission channel and crucial uncertainty. why_read is at most one sentence. Without sufficient evidence, explain the missing comparison instead of inventing market expectations.