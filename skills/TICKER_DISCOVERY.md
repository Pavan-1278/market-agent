# Skill: Ticker Discovery

## Goal

Identify which supplied US stocks deserve investigation based on current market data.

## Look For

- Unusual price moves
- Unusual volume
- Large gap up/down
- Major sector divergence
- Watchlist stocks behaving unusually
- Stocks strongly influencing SPY or QQQ

## Rules

Only select tickers supplied in the market data.

Never invent a ticker.

Do not explain the cause of a price move at this stage.

Ticker Discovery only decides which stocks deserve further investigation.

## Output

Return:

- ticker
- priority: 1–10
- reason_to_investigate: one short sentence