Skill: News Analysis

Goal

Identify material reported developments worth reading. This is news evaluation, not proof of what moved a stock.

Method

Identify the reported event, subject, period, and material change supported by the supplied text. Distinguish results, outlook, proposals, completed actions, and opinion. If only a headline is supplied, do not infer missing terms or article contents.

Importance

9–10: Specific, exceptionally consequential development with strong supplied support for its scale and significance.

7–8: Concrete material information about earnings, outlook, financing, business operations, regulation, or macro conditions.

5–6: Relevant reported development with moderate significance or important unresolved context.

3–4: Limited reading value, mostly commentary, or weak evidence of material change.

1–2: Routine/repeated information, or insufficient supplied evidence to identify a substantive development.

For 7+, identify the concrete material development. A dramatic headline, large price move, round dollar figure, or shortlist score is not enough. Unknown freshness limits claims of novelty; it does not automatically make a material report worthless. These scores do not certify source accuracy.

Prioritize and Reduce Noise

Consider the core watchlist and Fed, rates, CPI, PCE, jobs, GDP, yields, VIX, oil, geopolitics, and semiconductor restrictions.

Usually deprioritize generic comparisons, unsupported price-target speculation, routine holdings changes, and price recaps. Do not discard material news merely because its headline is opinion-shaped or the issuer is small. Evaluate financing against supplied company context; repayment does not automatically establish reduced dilution or improved net liquidity.

Score independently of triage and provider scores. A material story need not explain today's move. Do not assert that the full article has "no new information" when only a summary is available.

Output

Return exactly the requested fields:

importance: integer 1–10.

sentiment: bullish, bearish, mixed, or neutral under the core rules.

affected: only evidence-grounded ticker symbols.

why_read: one sentence, preferably no more than 45 words, joining an attributed reported development to its supported significance or a clearly conditional implication.

When evidence is inadequate, say what is missing in why_read; do not manufacture an investment takeaway.