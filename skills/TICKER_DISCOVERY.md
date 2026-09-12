Skill: Ticker Discovery

Goal

Choose which supplied securities deserve investigation of the supplied market snapshot; do not explain their moves.

Selection

Rank candidates using the supplied percentage moves and other available, comparable measurements. Prefer clear research leads over filling the requested quota. Use core watchlist relevance as a tie-breaker, not proof of a catalyst.

Use only:

Supplied tickers and snapshot values.

Relative volume when Python supplies a comparable historical baseline/result.

Gap, sector divergence, or index contribution when the necessary aligned measurements are supplied.

Without those inputs, omit those claims. A raw share count is not evidence of unusual volume. Do not infer market capitalization, normal volatility, company activity, ETF exposure, warrant status, or a corporate action from a symbol or share price. Security type remains unverified unless supplied.

Priority

9–10: Strongest measured investigation leads in the supplied set.

7–8: Substantial observed move or supported anomaly.

4–6: Moderate measured move or relevant contextual lead.

1–3: Weak reason to investigate.

These are research priorities, not likelihoods of a news event. Do not infer a gap or split-adjusted return from a generic change field. Describe values as belonging to the supplied snapshot, not necessarily current trading.

Output

Use the application's candidates array. Each entry contains:

ticker: exact supplied symbol.

priority: integer 1–10.

reason_to_investigate: one sentence citing observed evidence, without an invented cause or unsupported baseline comparison.

Return unique candidates in descending priority, up to the requested maximum. An empty array is valid.