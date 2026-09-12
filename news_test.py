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

with open("skills/NEWS_ANALYSIS.md", "r", encoding="utf-8") as file:
    news_skill = file.read()

alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

# -----------------------------
# Pydantic model for Claude output
# -----------------------------

class NewsAnalysis(BaseModel):
    importance: int
    sentiment: str
    affected: list[str]
    why_read: str

# -----------------------------
# Simple noise filter
# -----------------------------

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

    return any(phrase in title for phrase in noise_phrases)

# -----------------------------
# Fetch Alpha Vantage news
# -----------------------------

url = "https://www.alphavantage.co/query"

params = {
    "function": "NEWS_SENTIMENT",
    "tickers": "AMD,NVDA",
    "sort": "LATEST",
    "apikey": alpha_vantage_key
}

response = requests.get(
    url,
    params=params,
    timeout=30
)

data = response.json()

all_articles = data.get("feed", [])

if all_articles:
    print("\nFIRST ARTICLE FIELDS:")
    for key, value in all_articles[0].items():
        print(f"{key}: {value}")

articles = [
    article
    for article in all_articles
    if not is_noise_article(article)
][:5]

print(f"\nAnalyzing {len(articles)} candidate articles")

# -----------------------------
# Claude client
# -----------------------------

client = Anthropic(
    api_key=anthropic_key
)

# Combine global rules + news skill
system_prompt = system_rules + "\n\n" + news_skill

# -----------------------------
# Analyze articles
# -----------------------------

important_count = 0

for article in articles:

    headline = article.get("title")
    source = article.get("source")
    article_url = article.get("url")
    summary = article.get("summary", "")

    #print("\nDEBUG SUMMARY:")
    #print(summary+"\n")

    time_published = article.get("time_published", "")

    prompt = f"""
Analyze this market news item using only the evidence below.

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

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_result = message.content[0].text
    clean_result = raw_result.strip()

    if clean_result.startswith("```json"):
        clean_result = clean_result[7:]

    if clean_result.endswith("```"):
        clean_result = clean_result[:-3]

    clean_result = clean_result.strip()

    # Convert Claude JSON text into Python data
    parsed_json = json.loads(clean_result)

    # Validate the structure using Pydantic
    analysis = NewsAnalysis(**parsed_json)

    if analysis.importance >= 6:
        important_count += 1

        print("\n" + "=" * 70)

        print("HEADLINE:")
        print(headline)

        print("\nSTRUCTURED ANALYSIS:")
        print("Importance:", analysis.importance)
        print("Sentiment:", analysis.sentiment)
        print("Affected:", analysis.affected)
        print("Why Read:", analysis.why_read)

        print("\nURL:")
        print(article_url)

print("\n" + "=" * 70)
print(
    f"Finished. {important_count} important stories "
    f"found from {len(articles)} candidates."
)