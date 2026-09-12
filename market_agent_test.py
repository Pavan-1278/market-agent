import os
import json
import requests

from dotenv import load_dotenv
from anthropic import Anthropic
from pydantic import BaseModel


# ============================================================
# Load API keys and prompt files
# ============================================================

load_dotenv()

alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

with open("AGENT_RULES.md", "r", encoding="utf-8") as file:
    system_rules = file.read()

with open("skills/TICKER_DISCOVERY.md", "r", encoding="utf-8") as file:
    ticker_skill = file.read()

with open("skills/NEWS_ANALYSIS.md", "r", encoding="utf-8") as file:
    news_skill = file.read()


# ============================================================
# Settings
# ============================================================

MAX_SELECTED_TICKERS = 5

# Alpha Vantage may return up to 50 articles per ticker.
# We only send the most relevant few to Claude.
MAX_ARTICLES_PER_TICKER = 5

# Only display stories that Claude rates at least this high.
MIN_IMPORTANCE = 6


# ============================================================
# Pydantic models
# ============================================================

class TickerCandidate(BaseModel):
    ticker: str
    priority: int
    reason_to_investigate: str


class TickerDiscoveryResult(BaseModel):
    candidates: list[TickerCandidate]


class NewsAnalysis(BaseModel):
    importance: int
    sentiment: str
    affected: list[str]
    why_read: str


# ============================================================
# Claude client
# ============================================================

client = Anthropic(
    api_key=anthropic_key
)


# ============================================================
# Helper: clean Claude JSON
# ============================================================

def clean_claude_json(raw_result):
    clean_result = raw_result.strip()

    if clean_result.startswith("```json"):
        clean_result = clean_result[7:]

    if clean_result.endswith("```"):
        clean_result = clean_result[:-3]

    return clean_result.strip()


# ============================================================
# Helper: get Alpha Vantage relevance for searched ticker
# ============================================================

def get_ticker_relevance(article, searched_ticker):
    ticker_sentiment = article.get("ticker_sentiment", [])

    for item in ticker_sentiment:
        if item.get("ticker") == searched_ticker:
            try:
                return float(item.get("relevance_score", 0))
            except (TypeError, ValueError):
                return 0.0

    return 0.0


# ============================================================
# Step 1: Fetch market movers
# ============================================================

market_url = "https://www.alphavantage.co/query"

market_params = {
    "function": "TOP_GAINERS_LOSERS",
    "apikey": alpha_vantage_key
}

market_response = requests.get(
    market_url,
    params=market_params,
    timeout=30
)

market_data = market_response.json()


# ============================================================
# Step 2: Python market noise filter
# ============================================================

def is_valid_market_candidate(stock):
    ticker = stock.get("ticker", "")
    price = float(stock.get("price", 0))
    volume = int(stock.get("volume", 0))

    # Remove obvious warrants and rights
    if ticker.endswith(("W", "R")):
        return False

    if "^" in ticker:
        return False

    # Remove very low-priced securities
    if price < 5:
        return False

    # Require meaningful trading volume
    if volume < 1_000_000:
        return False

    return True


raw_candidates = (
    market_data.get("top_gainers", [])
    + market_data.get("top_losers", [])
    + market_data.get("most_actively_traded", [])
)

filtered_candidates = [
    stock
    for stock in raw_candidates
    if is_valid_market_candidate(stock)
]


# ============================================================
# Step 3: Remove duplicate tickers
# ============================================================

unique_candidates = {}

for stock in filtered_candidates:
    ticker = stock["ticker"]

    if ticker not in unique_candidates:
        unique_candidates[ticker] = stock

market_candidates = list(unique_candidates.values())


print("\n" + "=" * 70)
print("MARKET CANDIDATES")
print("=" * 70)

for stock in market_candidates:
    print(
        stock["ticker"],
        "| Price:", stock["price"],
        "| Change:", stock["change_percentage"],
        "| Volume:", stock["volume"]
    )


# ============================================================
# Step 4: Prepare candidates for Ticker Discovery AI
# ============================================================

candidate_data = []

for stock in market_candidates:
    candidate_data.append({
        "ticker": stock["ticker"],
        "price": stock["price"],
        "change_percentage": stock["change_percentage"],
        "volume": stock["volume"]
    })


# ============================================================
# Step 5: Ticker Discovery AI
# ============================================================

ticker_system_prompt = system_rules + "\n\n" + ticker_skill

ticker_prompt = f"""
These are market candidates supplied by Python:

{json.dumps(candidate_data, indent=2)}

Select up to {MAX_SELECTED_TICKERS} tickers that deserve further investigation.

You may ONLY select ticker symbols that appear in the supplied data.

Do not explain why the stock moved.
Only identify which tickers deserve further investigation.

Return ONLY valid JSON using this structure:

{{
    "candidates": [
        {{
            "ticker": "NVDA",
            "priority": 8,
            "reason_to_investigate": "Large price move combined with unusually high trading volume."
        }}
    ]
}}
"""

ticker_message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=500,
    system=ticker_system_prompt,
    messages=[
        {
            "role": "user",
            "content": ticker_prompt
        }
    ]
)

ticker_raw = ticker_message.content[0].text
ticker_clean = clean_claude_json(ticker_raw)

ticker_parsed = json.loads(ticker_clean)

ticker_result = TickerDiscoveryResult(**ticker_parsed)


# ============================================================
# Step 6: Validate Claude's ticker selections
# ============================================================

valid_tickers = {
    stock["ticker"]
    for stock in market_candidates
}

validated_candidates = []

for candidate in ticker_result.candidates:

    if candidate.ticker in valid_tickers:
        validated_candidates.append(candidate)

    else:
        print(
            f"\nREJECTED UNKNOWN TICKER: {candidate.ticker}"
        )


print("\n" + "=" * 70)
print("TICKERS SELECTED FOR INVESTIGATION")
print("=" * 70)

for candidate in validated_candidates:

    print(
        f"\n{candidate.ticker} | Priority: "
        f"{candidate.priority}/10"
    )

    print(
        "Reason:",
        candidate.reason_to_investigate
    )


# ============================================================
# Step 7: Create ticker list
# ============================================================

selected_tickers = [
    candidate.ticker
    for candidate in validated_candidates
]

print("\nTICKERS FOR NEWS SEARCH:")
print(",".join(selected_tickers))


if not selected_tickers:
    print("\nNo tickers selected. Stopping.")
    raise SystemExit


# ============================================================
# Step 8: News noise filter
# ============================================================

def is_noise_article(article):
    title = article.get("title", "").lower()

    noise_phrases = [
        "buys shares of",
        "purchases shares of",
        "acquires shares of",
        "shares sold by",
        "increases stake in",
        "decreases stake in",
        "has holdings in",
        "has $",
        "largest position",
    ]

    return any(
        phrase in title
        for phrase in noise_phrases
    )


# ============================================================
# Step 9: Fetch news separately for each selected ticker
# ============================================================

candidate_articles = []


for ticker in selected_tickers:

    print("\n" + "-" * 70)
    print(f"Fetching news for {ticker}...")

    news_params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "sort": "LATEST",
        "apikey": alpha_vantage_key
    }

    news_response = requests.get(
        market_url,
        params=news_params,
        timeout=30
    )

    news_data = news_response.json()

    ticker_articles = news_data.get("feed", [])

    print(
        f"Alpha Vantage returned "
        f"{len(ticker_articles)} articles for {ticker}"
    )


    # --------------------------------------------------------
    # Remove obvious news noise BEFORE Claude
    # --------------------------------------------------------

    ticker_articles = [
        article
        for article in ticker_articles
        if not is_noise_article(article)
    ]


    # --------------------------------------------------------
    # Calculate relevance to the ticker
    # --------------------------------------------------------

    for article in ticker_articles:

        article["_searched_ticker"] = ticker

        article["_ticker_relevance"] = (
            get_ticker_relevance(
                article,
                ticker
            )
        )


    # --------------------------------------------------------
    # Rank by Alpha Vantage relevance
    # --------------------------------------------------------

    ticker_articles = sorted(
        ticker_articles,
        key=lambda article: article["_ticker_relevance"],
        reverse=True
    )


    # --------------------------------------------------------
    # Keep only top few articles for Claude
    # --------------------------------------------------------

    ticker_articles = ticker_articles[
        :MAX_ARTICLES_PER_TICKER
    ]


    print(
        f"Keeping {len(ticker_articles)} "
        f"articles for Claude analysis."
    )


    for article in ticker_articles:

        print(
            f"  {article.get('title', '')}"
            f" | Relevance: "
            f"{article.get('_ticker_relevance', 0):.3f}"
        )


    candidate_articles.extend(
        ticker_articles
    )


# ============================================================
# Step 10: Remove duplicate articles across tickers
# ============================================================

unique_articles = {}


for article in candidate_articles:

    article_url = article.get("url")

    if not article_url:
        continue

    # If same article appeared for multiple tickers,
    # keep the version with higher relevance.
    if article_url not in unique_articles:

        unique_articles[article_url] = article

    else:

        existing_relevance = unique_articles[
            article_url
        ].get("_ticker_relevance", 0)

        new_relevance = article.get(
            "_ticker_relevance",
            0
        )

        if new_relevance > existing_relevance:
            unique_articles[article_url] = article


candidate_articles = list(
    unique_articles.values()
)


print("\n" + "=" * 70)
print(
    f"{len(candidate_articles)} UNIQUE ARTICLES "
    f"SELECTED FOR CLAUDE"
)
print("=" * 70)


# ============================================================
# Step 11: News Analysis AI
# ============================================================

news_system_prompt = (
    system_rules
    + "\n\n"
    + news_skill
)

important_count = 0


for article in candidate_articles:

    searched_ticker = article.get(
        "_searched_ticker",
        ""
    )

    relevance = article.get(
        "_ticker_relevance",
        0
    )

    headline = article.get(
        "title",
        ""
    )

    source = article.get(
        "source",
        ""
    )

    article_url = article.get(
        "url",
        ""
    )

    summary = article.get(
        "summary",
        ""
    )

    time_published = article.get(
        "time_published",
        ""
    )


    news_prompt = f"""
Analyze this market news item using only the evidence below.

Ticker being investigated:
{searched_ticker}

Headline:
{headline}

Source:
{source}

Published:
{time_published}

Summary:
{summary}

Return ONLY valid JSON using exactly this structure:

{{
    "importance": 8,
    "sentiment": "bullish",
    "affected": ["AMD", "NVDA"],
    "why_read": "One sentence explaining why this matters."
}}
"""


    news_message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=news_system_prompt,
        messages=[
            {
                "role": "user",
                "content": news_prompt
            }
        ]
    )


    news_raw = (
        news_message
        .content[0]
        .text
    )

    news_clean = clean_claude_json(
        news_raw
    )

    news_parsed = json.loads(
        news_clean
    )

    analysis = NewsAnalysis(
        **news_parsed
    )


    # ========================================================
    # Step 12: Python importance threshold
    # ========================================================

    if analysis.importance >= MIN_IMPORTANCE:

        important_count += 1

        print("\n" + "=" * 70)

        print(
            f"{searched_ticker} "
            f"| Importance: "
            f"{analysis.importance}/10"
        )

        print("\nHEADLINE:")
        print(headline)

        print("\nWHY READ:")
        print(
            analysis.why_read
        )

        print("\nSENTIMENT:")
        print(
            analysis.sentiment
        )

        print("\nAFFECTED:")
        print(
            ", ".join(
                analysis.affected
            )
        )

        print("\nSOURCE:")
        print(source)

        print(
            "\nALPHA VANTAGE RELEVANCE:"
        )

        print(
            f"{relevance:.3f}"
        )

        print("\nURL:")
        print(article_url)


# ============================================================
# Final summary
# ============================================================

print("\n" + "=" * 70)

print(
    f"Finished. Claude found "
    f"{important_count} important stories "
    f"from {len(candidate_articles)} "
    f"pre-filtered articles."
)