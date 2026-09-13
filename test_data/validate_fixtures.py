"""Check development fixture files locally, with no imports of the agent or APIs."""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(name):
    path = (ROOT / name).resolve()
    require(path.parent == ROOT, "Fixture path must remain inside test_data.")
    def reject_constant(value):
        raise ValueError("Non-finite JSON constant: " + value)
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)


def check_secrets(value):
    # A sanity check for credential fields, not a general-purpose secret scanner.
    forbidden = {"apikey", "api_key", "anthropic_api_key", "alpha_vantage_api_key",
                 "authorization", "password", "access_token"}
    if isinstance(value, dict):
        for key, item in value.items():
            require(key.lower() not in forbidden, "Unexpected credential field: " + key)
            check_secrets(item)
    elif isinstance(value, list):
        for item in value:
            check_secrets(item)


def prepare_like_current_script(feed):
    phrases = (
        "buys shares of", "purchases shares of", "acquires shares of",
        "shares sold by", "increases stake in", "decreases stake in",
        "largest position", "acquires new position in", "has holdings in",
    )
    seen_urls, seen_titles, prepared = set(), set(), []
    for row in sorted(feed, key=lambda r: r["time_published"], reverse=True):
        title, url = row["title"].strip(), row["url"].strip()
        title_key = " ".join(title.lower().split())
        if any(p in title.lower() for p in phrases):
            continue
        if url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        prepared.append(row)
    return prepared


def main():
    manifest = load_json("manifest.json")
    market = load_json(manifest["market_file"])
    expected = manifest["expected_data_checks"]
    require(manifest["mode"] == "DEVELOPMENT_ONLY", "Development marker is missing.")
    require(manifest["alpha_vantage_network_requests_allowed"] is False,
            "Live Alpha Vantage calls must not be allowed for this dataset.")
    require(manifest["write_into_live_cache"] is False, "Do not mix fixtures and live cache.")
    replay = datetime.fromisoformat(manifest["replay_time_utc"])
    require(replay.utcoffset() == timedelta(0), "Replay time must be UTC.")
    begin, end = [datetime.strptime(manifest["news_window_utc"][k], "%Y%m%dT%H%M")
                  .replace(tzinfo=timezone.utc) for k in ("from", "to")]
    require(end - begin == timedelta(hours=manifest["lookback_hours"]),
            "Replay window has the wrong duration.")
    require(end == replay.replace(second=0, microsecond=0), "Window and replay time disagree.")
    require(market["last_updated"] == manifest["market_snapshot_time_as_supplied"],
            "Market timestamp mismatch.")
    require(market["_fixture"]["independently_verified"] is False,
            "Reconstructed market data must not be marked as verified.")
    tickers = set()
    for group in ("top_gainers", "top_losers", "most_actively_traded"):
        require(isinstance(market[group], list), "Missing mover list: " + group)
        for row in market[group]:
            ticker = row["ticker"]
            require(bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", ticker)), "Invalid ticker.")
            price = float(row["price"])
            change = float(row["change_percentage"].rstrip("%"))
            require(math.isfinite(price) and math.isfinite(change), "Invalid number.")
            require(price >= 5 and int(row["volume"]) >= 1_000_000,
                    "Unexpected row outside the saved candidate subset.")
            tickers.add(ticker)
    require(len(tickers) == expected["unique_market_candidates"], "Candidate count mismatch.")
    require(set(manifest["news_files"]) == tickers, "Each market ticker needs an explicit feed.")
    require(len(manifest["news_files"]) == expected["news_files"], "News-file count mismatch.")
    total_raw = total_prepared = 0
    nonempty = []
    for ticker, name in manifest["news_files"].items():
        data = load_json(name)
        check_secrets(data)
        require(data["_fixture"]["ticker"] == ticker, "Wrong ticker in " + name)
        require(data["_fixture"]["mode"] == "DEVELOPMENT_ONLY", "Unlabeled news fixture.")
        require(data["_fixture"]["independently_verified"] is False, "Mock news is not verified.")
        feed = data["feed"]
        require(isinstance(feed, list), "Invalid feed: " + name)
        require(int(data["items"]) == len(feed), "Item count mismatch: " + name)
        for article in feed:
            for key in ("title", "url", "time_published", "source", "summary"):
                require(isinstance(article[key], str) and bool(article[key]),
                        "Missing article field: " + key)
            require(article["title"].startswith("[MOCK TEST DATA]"), "Missing title marker.")
            require(article["source"].startswith("MOCK DEVELOPMENT DATA"), "Missing source marker.")
            require(article["summary"].startswith("Synthetic scenario"), "Missing summary marker.")
            require(urlparse(article["url"]).hostname == "example.invalid", "Unexpected real article URL.")
            published = datetime.strptime(article["time_published"], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            require(begin <= published <= end, "Article outside fixed replay window.")
            require("ticker_sentiment" not in article and "overall_sentiment_score" not in article,
                    "This dataset should not fabricate provider model scores.")
        prepared = prepare_like_current_script(feed)
        total_raw += len(feed)
        total_prepared += len(prepared)
        if feed:
            nonempty.append(ticker)
            require(len(feed) == expected[ticker+"_rows_before"], "Unexpected raw count.")
            require(len(prepared) == expected[ticker+"_rows_after_existing_filters"],
                    "Unexpected filtered count.")
    check_secrets(market)
    check_secrets(manifest)
    require(total_raw == expected["news_rows_before_filters"], "Total row count mismatch.")
    require(total_prepared == expected["news_rows_after_existing_filters"], "Prepared count mismatch.")
    print("PASS: 19 JSON files validated.")
    print(f"Market candidates: {len(tickers)} (reconstructed historical test snapshot).")
    print("Mock news feeds with articles: " + ", ".join(nonempty) + ".")
    print(f"News rows: {total_raw} before filters; {total_prepared} after duplicate/noise checks.")
    print("Replay time: " + manifest["replay_time_utc"])
    print("Alpha Vantage calls: 0. Claude calls: 0.")
    print("Data checks passed; Claude behavior has NOT been tested.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("FIXTURE CHECK FAILED:", exc)
        raise SystemExit(1)
