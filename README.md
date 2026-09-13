# Personal US Stock Market AI Agent

A local Python-based AI agent for discovering unusual US stock-market activity, finding relevant news, filtering noise, ranking importance, storing analysis history, and sending important updates to Telegram.

The project follows one core design principle:

> **Use Python for deterministic work. Use AI for reasoning.**

Python handles calculations, filtering, ranking, validation, deduplication, caching, persistence, and thresholds. Claude is used for interpretation: deciding which tickers deserve investigation, which articles are plausible catalysts, and whether a story is materially important.

---

## Current MVP

The current system supports:

- US market-mover discovery using Alpha Vantage
- Python filtering of low-quality candidates
- Python-calculated price-move and volume rankings
- Claude-based ticker discovery
- Per-ticker news retrieval
- Python news-noise filtering and duplicate removal
- Claude catalyst triage
- Batched Claude news analysis
- Importance, sentiment, affected tickers, and **Why Read**
- Native Claude structured JSON output
- Strict Pydantic validation
- Anti-hallucination rules and task-specific skills
- SQLite analysis history
- Reuse of unchanged analyses before another Claude call
- Alpha Vantage response caching
- Development mode using local fixtures
- Telegram notifications
- Production logging
- Windows Task Scheduler support
- Git/GitHub version control

---

## High-Level Architecture

```text
                Market Agent
                     │
                     ▼
            Alpha Vantage Market Data
                     │
                     ▼
            Python Candidate Filtering
                     │
                     ▼
          Python Price / Volume Rankings
                     │
                     ▼
             Ticker Discovery AI
                     │
                     ▼
          Python Priority Threshold
                     │
                     ▼
          News Retrieval Per Ticker
                     │
                     ▼
       Python Noise + Duplicate Filtering
                     │
                     ▼
             Catalyst Triage AI
                     │
                     ▼
        Python Catalyst-Relevance Threshold
                     │
                     ▼
              SQLite Reuse Check
               │             │
          Match found      New evidence
               │             │
               ▼             ▼
        Reuse analysis   Batch News Analysis AI
                              │
                              ▼
                         Save to SQLite
                              │
                              ▼
                    Python Importance Threshold
                              │
                              ▼
                       Telegram Notification
```

---

## Longer-Term Goal

```text
                    Market Agent
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        News           Prices        SEC EDGAR
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                    Deduplication
                         ▼
                    Rule Filtering
                         ▼
                       Claude
                         ▼
                 Importance Ranking
                         ▼
                  SQLite / History
                         ▼
              Telegram / Dashboard
```

A future interactive investigation flow is planned for questions such as:

```text
Why is AMD falling?
```

Intended investigation path:

```text
AMD price
   ↓
Related semiconductor stocks
   ↓
Sector / ETF performance
   ↓
QQQ / SPY
   ↓
Company news
   ↓
SEC filings
   ↓
Macro events
   ↓
Claude reasoning
   ↓
Evidence-based explanation
```

---

## Project Structure

```text
market-agent/
│
├── .env
├── .gitignore
├── README.md
│
├── market_agent.py
├── market_agent_test.py
├── run_market_agent.bat
│
├── alpha_vantage_cache.py
├── database.py
├── dev_data_source.py
├── telegram_notifier.py
├── telegram_test.py
├── view_history.py
│
├── AGENT_RULES.md
│
├── skills/
│   ├── CATALYST_TRIAGE.md
│   ├── EARNINGS_ANALYSIS.md
│   ├── MACRO_ANALYSIS.md
│   ├── NEWS_ANALYSIS.md
│   ├── PRICE_INVESTIGATION.md
│   ├── SEC_ANALYSIS.md
│   └── TICKER_DISCOVERY.md
│
├── test_data/
│   ├── market_movers.json
│   ├── FEIM_news.json
│   ├── TNON_news.json
│   ├── ...
│   └── validate_fixtures.py
│
├── logs/
│
├── market_agent.db
├── market_agent_dev.db
│
└── .cache/
    └── alpha_vantage/
```

Generated databases, logs, cache files, API keys, and the virtual environment should remain local and should not be committed to Git.

---

## Requirements

Current development environment:

- Windows 11
- Python 3.12+
- VS Code
- Python virtual environment
- Anthropic API access
- Alpha Vantage API access
- Telegram bot

Python packages:

```text
anthropic
requests
python-dotenv
pydantic
```

SQLite is accessed through Python's built-in `sqlite3` module and does not require a separate Python package.

---

## Environment Variables

Create a local `.env` file in the project root:

```dotenv
ANTHROPIC_API_KEY=your_anthropic_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Never commit `.env`.

Recommended `.gitignore` coverage:

```gitignore
.env
.env.*
!.env.example

.venv/
venv/
env/

__pycache__/
*.py[cod]

.cache/
logs/

*.db
*.db-*
*.sqlite
*.sqlite-*
*.sqlite3
*.sqlite3-*

.vscode/
.idea/

Thumbs.db
Desktop.ini
.DS_Store
```

---

## AI Design

The project separates permanent agent rules from task-specific skills.

### Core Rules

`AGENT_RULES.md` applies to every AI stage.

Key principles:

- Use only supplied evidence for current factual claims
- Do not invent facts, numbers, dates, relationships, guidance, or market data
- Do not fill missing information gaps
- Separate reported facts from implications and speculation
- Preserve uncertainty in source wording
- Do not claim a stock will definitely rise or fall
- Do not treat correlation as causation
- Do not claim independent verification unless verification actually occurred
- Prefer primary evidence when available
- Let Python perform deterministic calculations and comparisons

### Skills

#### `TICKER_DISCOVERY.md`

Purpose:

```text
Which supplied tickers deserve investigation?
```

The AI can only select tickers supplied by Python.

Python calculates:

- `volume_rank_in_candidates`
- `absolute_change_rank_in_candidates`

Claude interprets those ranks rather than recalculating them.

#### `CATALYST_TRIAGE.md`

Purpose:

```text
Which supplied articles are worth investigating as possible catalysts?
```

Catalyst triage identifies leads. It does **not** prove that an article caused a stock-price move.

#### `NEWS_ANALYSIS.md`

Purpose:

```text
Is this story important enough for an investor to read?
```

Current output:

```json
{
  "importance": 8,
  "sentiment": "bullish",
  "affected": ["AMD", "NVDA"],
  "why_read": "One sentence explaining why the new information matters."
}
```

Current display threshold:

```text
Importance >= 6
```

#### Future Skills

Draft skills already exist for:

- Earnings analysis
- SEC filing analysis
- Macro analysis
- Price-move investigation

These are not all connected to the active production pipeline yet.

---

## Structured AI Output

Claude responses use:

- native JSON-schema structured output
- strict local Pydantic validation

Unexpected fields, invalid values, missing fields, duplicate IDs, or unknown IDs are rejected rather than silently accepted.

Structured output improves response-format reliability. It does not prove that a financial conclusion is correct, so grounding rules and deterministic validation remain necessary.

---

## Market Candidate Filtering

Python screens market candidates before Claude sees them.

Current deterministic checks include:

- minimum price
- minimum trading volume
- valid ticker-symbol format

Security type is not assumed unless verified.

Python also calculates deterministic ranks such as:

```text
volume_rank_in_candidates
absolute_change_rank_in_candidates
```

Claude is instructed to use these supplied ranks rather than inventing numerical comparisons.

---

## News Retrieval

News is currently retrieved separately for each selected ticker.

Workflow:

```text
Selected ticker
    ↓
NEWS_SENTIMENT request
    ↓
Python removes obvious noise
    ↓
Python removes duplicate URLs/titles
    ↓
Claude catalyst triage
```

Examples of obvious noise removed in Python include routine small institutional ownership changes.

---

## Thresholds

Current pipeline thresholds:

```text
MIN_TICKER_PRIORITY = 6
MIN_CATALYST_RELEVANCE = 5
MIN_IMPORTANCE = 6
```

These answer different questions:

```text
Ticker priority
= Is this market move worth investigating?

Catalyst relevance
= Is this article worth investigating as a possible catalyst?

News importance
= Is this information materially important enough to surface?
```

A high catalyst score does not force a high final importance score.

---

## SQLite History

Completed article analyses are stored in SQLite.

Development database:

```text
market_agent_dev.db
```

Live database:

```text
market_agent.db
```

Stored information includes:

- headline
- article URL
- source
- publication time
- searched ticker context
- supplied summary
- importance score
- sentiment
- affected tickers
- Why Read
- analysis timestamp
- reference time
- Claude model
- prompt fingerprint
- supplied evidence

Both high-scoring and low-scoring completed analyses are stored.

---

## SQLite Reuse

Before final Claude news analysis, the agent checks SQLite for a reusable previous analysis.

Reuse requires matching evidence and context, including:

- article URL
- headline
- source
- publication timestamp
- summary
- searched ticker context
- Claude model
- prompt/rules fingerprint

If a reusable analysis exists:

```text
DATABASE REUSED
```

Claude is not called again for that article.

If evidence or prompts change, the article can be analyzed again.

Development fixtures can reuse saved analyses indefinitely. Live analysis reuse is time-limited.

---

## View Saved History

Run:

```powershell
python view_history.py
```

This reads the development SQLite database without contacting Alpha Vantage or Claude.

---

## Development Mode

Use development mode to test the AI pipeline without consuming Alpha Vantage requests:

```powershell
python market_agent_test.py --dev
```

Development mode:

- uses `test_data/`
- makes zero Alpha Vantage requests
- uses synthetic news scenarios
- still uses the real Claude API
- stores analysis in `market_agent_dev.db`
- can send clearly labeled development Telegram notifications

Development data must never be treated as real market research.

Validate fixture files with:

```powershell
python test_data/validate_fixtures.py
```

---

## Live Test Mode

Run:

```powershell
python market_agent_test.py
```

This uses live Alpha Vantage data or valid cached Alpha Vantage responses.

To bypass the cache:

```powershell
python market_agent_test.py --refresh-data
```

Use refresh carefully because it consumes additional API requests.

---

## Alpha Vantage Cache

Successful Alpha Vantage responses are cached locally under:

```text
.cache/alpha_vantage/
```

The current development cache lifetime is approximately 15 minutes.

API error responses are not treated as valid empty market/news results.

---

## API Usage and Cost Optimization

The pipeline reduces unnecessary provider and Claude usage through:

```text
Python filtering
    ↓
Ticker priority threshold
    ↓
Catalyst threshold
    ↓
SQLite reuse
    ↓
Batch final analysis
```

Final shortlisted articles are analyzed in one Claude batch rather than one request per article.

Alpha Vantage's standard free tier is restrictive for frequent polling, so the current local production workflow is best suited to limited daily scans. Higher-frequency monitoring will likely require another or higher-capacity data provider.

---

## Telegram Notifications

Telegram delivers important stories automatically.

Required `.env` values:

```dotenv
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Test Telegram with:

```powershell
python telegram_test.py
```

Only stories meeting the final importance threshold are included in normal market alerts.

Development-mode messages are explicitly labeled as synthetic test output.

Example:

```text
📈 MARKET AGENT

1 important story found.

FEIM — 6/10 | Bullish

Headline:
...

Why Read:
...

Affected:
FEIM

Source:
...
```

---

## Production Runner

Production execution uses:

```powershell
python market_agent.py
```

The production runner:

- runs the live market pipeline
- creates a local log
- uses the live SQLite database
- sends Telegram market alerts
- sends a completion message if no stories meet the threshold
- sends a Telegram failure alert if the production run crashes

Production logs are stored under:

```text
logs/
```

Example:

```text
logs/market_agent_2026-09-13_013318_UTC.log
```

---

## Windows Launcher

The project uses:

```text
run_market_agent.bat
```

Example:

```bat
@echo off

cd /d C:\Users\Pavan\market-agent

C:\Users\Pavan\market-agent\.venv\Scripts\python.exe market_agent.py

exit /b %ERRORLEVEL%
```

This lets Windows execute the project without manually activating the virtual environment.

---

## Windows Task Scheduler

The production runner can be scheduled automatically with Windows Task Scheduler.

Suggested task:

```text
Name:
Market Agent Daily Scan

Schedule:
Monday-Friday

Time:
2:30 PM Edmonton local time

Program:
C:\Users\Pavan\market-agent\run_market_agent.bat

Start in:
C:\Users\Pavan\market-agent
```

Recommended settings:

- Run whether user is logged on or not
- Run with highest privileges
- Wake the computer to run the task
- Run as soon as possible after a missed scheduled start
- Do not start a second instance if one is already running
- Restart after failure if desired

The computer must be powered on or able to wake from sleep. A fully powered-off computer cannot run the local agent.

---

## Git and GitHub

Typical workflow:

```powershell
git status
git add .
git commit -m "Describe the change"
git push
```

View history:

```powershell
git log --oneline
```

Sensitive/local files such as `.env`, databases, logs, cache files, and `.venv` should remain excluded from Git.

---

## Current Processing Flow

```text
TOP_GAINERS_LOSERS
        ↓
Python candidate screen
        ↓
Python numerical rankings
        ↓
Claude Ticker Discovery
        ↓
MIN_TICKER_PRIORITY
        ↓
NEWS_SENTIMENT per ticker
        ↓
Python news noise filtering
        ↓
Python deduplication
        ↓
Claude Catalyst Triage
        ↓
MIN_CATALYST_RELEVANCE
        ↓
SQLite reuse check
        ↓
Batch Claude News Analysis
        ↓
SQLite persistence
        ↓
MIN_IMPORTANCE
        ↓
Telegram
```

---

## Current Limitations

The current MVP is not a complete investment-research system.

Important limitations:

- News summaries come from a third-party provider and are not automatically independently verified.
- A related article is not proof that it caused a stock-price move.
- Raw trading volume alone does not establish unusual volume relative to historical norms.
- The current market-mover endpoint does not provide a complete verified security classification.
- Alpha Vantage free-tier limits constrain frequent monitoring.
- Claude can still make reasoning mistakes despite grounding rules and structured output.
- The agent does not place trades or orders.
- The production workflow is currently designed primarily as a daily scan rather than continuous intraday monitoring.
- SEC, macro, earnings, and interactive price-investigation skills are not yet fully integrated into the active live workflow.

---

## Planned Development

Planned enhancements include:

1. Always-monitor / watchlist logic
2. Improved market-data provider strategy
3. Live stock-price context
4. Historical volume and volatility baselines
5. Better market/sector comparison
6. SEC EDGAR integration
7. Earnings-specific workflow
8. Macro-event monitoring
9. Interactive "Why is this stock moving?" investigations
10. Additional duplicate-event detection
11. More advanced source-quality scoring
12. Dashboard / UI
13. Higher-frequency monitoring
14. Cloud deployment so the agent can run when the local PC is off

---

## Security

Never commit or share:

- Anthropic API keys
- Alpha Vantage API keys
- Telegram bot tokens
- other credentials

Store secrets only in `.env`.

If a token is accidentally exposed, revoke and regenerate it.

---

## Disclaimer

This project is for personal market research and software experimentation.

It does not provide financial advice, does not guarantee the accuracy or completeness of market information, and does not execute trades.

AI-generated conclusions should be treated as research leads that require appropriate verification before investment decisions are made.
