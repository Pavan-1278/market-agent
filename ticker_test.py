import os
import json
import requests

from dotenv import load_dotenv
from anthropic import Anthropic
from pydantic import BaseModel


# -----------------------------
# Load API keys and prompts
# -----------------------------

load_dotenv()

with open("AGENT_RULES.md", "r", encoding="utf-8") as file:
    system_rules = file.read()

with open("skills/TICKER_DISCOVERY.md", "r", encoding="utf-8") as file:
    ticker_skill = file.read()

alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")


# -----------------------------
# Pydantic models
# -----------------------------

class TickerCandidate(BaseModel):
    ticker: str
    priority: int
    reason_to_investigate: str


class TickerDiscoveryResult(BaseModel):
    candidates: list[TickerCandidate]


# -----------------------------
# Fetch market movers
# -----------------------------

url = "https://www.alphavantage.co/query"

params = {
    "function": "TOP_GAINERS_LOSERS",
    "apikey": alpha_vantage_key
}

response = requests.get(
    url,
    params=params,
    timeout=30
)

data = response.json()


# -----------------------------
# Python noise filter
# -----------------------------

def is_valid_candidate(stock):
    ticker = stock.get("ticker", "")
    price = float(stock.get("price", 0))
    volume = int(stock.get("volume", 0))

    if ticker.endswith(("W", "R")):
        return False

    if "^" in ticker:
        return False

    if price < 5:
        return False

    if volume < 1_000_000:
        return False

    return True


# -----------------------------
# Combine market lists
# -----------------------------

raw_candidates = (
    data.get("top_gainers", [])
    + data.get("top_losers", [])
    + data.get("most_actively_traded", [])
)

filtered_candidates = [
    stock
    for stock in raw_candidates
    if is_valid_candidate(stock)
]


# -----------------------------
# Remove duplicate tickers
# -----------------------------

unique_candidates = {}

for stock in filtered_candidates:
    ticker = stock["ticker"]

    if ticker not in unique_candidates:
        unique_candidates[ticker] = stock

market_candidates = list(unique_candidates.values())


print("\nFILTERED MARKET CANDIDATES:\n")

for stock in market_candidates:
    print(
        stock["ticker"],
        "| Price:", stock["price"],
        "| Change:", stock["change_percentage"],
        "| Volume:", stock["volume"]
    )


# -----------------------------
# Prepare data for Claude
# -----------------------------

candidate_data = []

for stock in market_candidates:
    candidate_data.append({
        "ticker": stock["ticker"],
        "price": stock["price"],
        "change_percentage": stock["change_percentage"],
        "volume": stock["volume"]
    })


# -----------------------------
# Claude ticker discovery
# -----------------------------

client = Anthropic(
    api_key=anthropic_key
)

system_prompt = system_rules + "\n\n" + ticker_skill

prompt = f"""
These are market candidates supplied by Python:

{json.dumps(candidate_data, indent=2)}

Select up to 5 tickers that deserve further investigation.

You may ONLY select tickers that appear in the supplied data.

Do not explain why the stock moved.
Only identify which tickers deserve investigation.

Return ONLY valid JSON:

{{
    "candidates": [
        {{
            "ticker": "NVDA",
            "priority": 8,
            "reason_to_investigate": "Large price move combined with heavy trading volume."
        }}
    ]
}}
"""

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=500,
    system=system_prompt,
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)


# -----------------------------
# Parse Claude response
# -----------------------------

raw_result = message.content[0].text

clean_result = raw_result.strip()

if clean_result.startswith("```json"):
    clean_result = clean_result[7:]

if clean_result.endswith("```"):
    clean_result = clean_result[:-3]

clean_result = clean_result.strip()

parsed_json = json.loads(clean_result)

result = TickerDiscoveryResult(**parsed_json)


# -----------------------------
# Validate Claude selections
# -----------------------------

valid_tickers = {
    stock["ticker"]
    for stock in market_candidates
}

validated_candidates = []

for candidate in result.candidates:

    if candidate.ticker in valid_tickers:
        validated_candidates.append(candidate)

    else:
        print(
            f"\nREJECTED UNKNOWN TICKER: {candidate.ticker}"
        )


# -----------------------------
# Show AI selections
# -----------------------------

print("\n" + "=" * 70)
print("TICKERS SELECTED FOR INVESTIGATION:\n")

for candidate in validated_candidates:

    print(
        f"{candidate.ticker} | Priority: "
        f"{candidate.priority}/10"
    )

    print(
        "Reason:",
        candidate.reason_to_investigate
    )

    print("-" * 70)


# -----------------------------
# Build ticker query for news
# -----------------------------

selected_tickers = [
    candidate.ticker
    for candidate in validated_candidates
]

ticker_query = ",".join(selected_tickers)

print("\nTICKERS FOR NEWS SEARCH:")
print(ticker_query)