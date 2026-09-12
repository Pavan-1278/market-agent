# Personal US Stock Market AI Agent

A local Python-based AI agent for monitoring important US stock-market developments, filtering noise, and identifying stories worth investigating.

## Current MVP

The agent currently:

* Fetches US market movers using Alpha Vantage
* Filters obvious low-quality securities and market noise with Python
* Uses Claude to identify tickers that deserve investigation
* Validates AI-selected tickers against real market data
* Fetches relevant news for selected tickers
* Filters low-value news articles
* Uses Claude to evaluate:

  * Importance
  * Sentiment
  * Affected tickers
  * Why the story matters
* Uses Pydantic to validate structured AI output
* Uses separate rule and skill files to reduce hallucination risk

## Architecture

```text
Market Data
    ↓
Python Filtering
    ↓
Ticker Discovery AI
    ↓
Validated Tickers
    ↓
News API
    ↓
Python Filtering
    ↓
News Analysis AI
    ↓
Importance Ranking
```

## Project Structure

```text
market-agent/
├── AGENT_RULES.md
├── README.md
├── market_agent_test.py
├── news_test.py
├── ticker_test.py
├── test.py
├── skills/
│   ├── EARNINGS_ANALYSIS.md
│   ├── MACRO_ANALYSIS.md
│   ├── NEWS_ANALYSIS.md
│   ├── PRICE_INVESTIGATION.md
│   ├── SEC_ANALYSIS.md
│   └── TICKER_DISCOVERY.md
└── .gitignore
```

Local secrets are stored in `.env` and are excluded from Git.

## Priority Watchlist

Primary:

* AMD
* NVDA
* SPY
* QQQ

Secondary:

* AVGO
* TSM
* ARM
* MU
* INTC
* MSFT
* META
* GOOGL
* AMZN

## Planned Features

* SQLite history
* Duplicate detection
* Live stock-price context
* SEC EDGAR analysis
* Macro-event monitoring
* Scheduled monitoring
* Telegram alerts
* Interactive investigations such as:

  * Why is AMD falling?
  * Why is NVDA moving?
  * Is this move company-specific or market-wide?

## Design Principle

Python handles deterministic tasks such as filtering, calculations, validation, thresholds, and duplicate detection.

AI handles reasoning tasks such as importance assessment, market implications, sentiment, and evidence-based explanation.

## Security

API keys are stored locally in `.env`.

The `.env` file and Python virtual environment are excluded from Git using `.gitignore`.

Do not commit API keys or other secrets to the repository.
