"""Read this project's fixed development fixtures; never make network requests.

The caller supplies test_data/ alongside the script. Missing or inconsistent
fixtures fail explicitly. Nothing is read from or written to the live cache.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


class FixtureDataError(RuntimeError):
    """Invalid development data; never replace this with a live request."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureDataError(message)


@dataclass(frozen=True)
class FixtureSnapshot:
    data: dict[str, Any]
    fixture_name: str
    replay_time_utc: str
    news_window_utc: dict[str, str]

    def evidence_metadata(self) -> dict[str, Any]:
        # These are NOT API request/response times. Do not invent retrieval times.
        return {
            "data_mode": "DEVELOPMENT_ONLY",
            "data_source": "local_fixture_file",
            "fixture_file": self.fixture_name,
            "replay_time_utc": self.replay_time_utc,
            "provenance": deepcopy(self.data["_fixture"]),
            "note": (
                "Fixed software-test scenario, NOT live market data. Market data "
                "is reconstructed from prior console output; news is synthetic. "
                "No provider request was made and no company facts were verified."
            ),
        }


class DevelopmentData:
    """Provide the two data operations used by the existing agent.

    Validate all mapped files at startup, before any paid Claude calls. A valid
    empty feed is allowed; a missing or damaged file is an error, not no news.
    """
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.request_attempts = 0
        self.cache_hits = 0
        self.snapshots_used = 0
        self.manifest = self._read_json("manifest.json")
        manifest = self.manifest
        require(manifest.get("fixture_version") == 1, "Unsupported fixture version.")
        require(manifest.get("mode") == "DEVELOPMENT_ONLY", "Missing development marker.")
        for flag in ("alpha_vantage_network_requests_allowed", "write_into_live_cache",
                     "use_wall_clock_for_fixture_news_window"):
            require(manifest.get(flag) is False, f"Fixture manifest must set {flag} to false.")
        require(type(manifest.get("lookback_hours")) is int and manifest["lookback_hours"] > 0,
                "Fixture lookback must be a positive integer.")
        self.lookback_hours = manifest["lookback_hours"]
        try:
            self.replay_time = datetime.fromisoformat(manifest["replay_time_utc"])
            window = manifest["news_window_utc"]
            begin, end = [datetime.strptime(window[key], "%Y%m%dT%H%M").replace(
                tzinfo=timezone.utc) for key in ("from", "to")]
        except (KeyError, TypeError, ValueError) as exc:
            raise FixtureDataError("Invalid fixture replay time or news window.") from exc
        require(self.replay_time.utcoffset() == timedelta(0), "Fixture replay time must be UTC.")
        require(end - begin == timedelta(hours=self.lookback_hours),
                "Fixture news window and lookback disagree.")
        require(end == self.replay_time.replace(second=0, microsecond=0),
                "Fixture news window and replay time disagree.")
        self.news_window = {"from": window["from"], "to": window["to"]}
        self._market_name = manifest.get("market_file")
        self._market = self._read_json(self._market_name)
        self._check_provenance(self._market, self._market_name)
        require(self._market.get("last_updated") == manifest.get("market_snapshot_time_as_supplied")
                and bool(self._market.get("last_updated")), "Fixture market timestamp mismatch.")
        market_tickers = set()
        for group in ("top_gainers", "top_losers", "most_actively_traded"):
            require(isinstance(self._market.get(group), list), f"Missing market list: {group}.")
            for row in self._market[group]:
                require(isinstance(row, dict) and isinstance(row.get("ticker"), str),
                        f"Invalid market entry in {group}.")
                market_tickers.add(row["ticker"])
        mapping = manifest.get("news_files")
        require(isinstance(mapping, dict) and set(mapping) == market_tickers,
                "Each market ticker needs an explicitly mapped news fixture.")
        self._news_names = dict(mapping)
        self._news = {}
        for ticker, filename in mapping.items():
            data = self._read_json(filename)
            self._check_provenance(data, filename)
            require(data["_fixture"].get("ticker") == ticker, f"Wrong ticker in {filename}.")
            require(isinstance(data.get("feed"), list), f"Missing feed list in {filename}.")
            require(str(data.get("items")) == str(len(data["feed"])),
                    f"Incorrect item count in {filename}.")
            for article in data["feed"]:
                require(isinstance(article, dict), f"Invalid article in {filename}.")
                for key in ("title", "source", "summary", "time_published", "url"):
                    require(isinstance(article.get(key), str) and bool(article[key]),
                            f"Missing article {key} in {filename}.")
                require(article["title"].startswith("[MOCK TEST DATA]")
                        and article["source"].startswith("MOCK DEVELOPMENT DATA")
                        and article["summary"].startswith("Synthetic scenario"),
                        f"Unlabeled synthetic article in {filename}.")
                require(urlparse(article["url"]).hostname == "example.invalid",
                        f"Unexpected real article URL in {filename}.")
                try:
                    published = datetime.strptime(article["time_published"],
                                                  "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                except ValueError as exc:
                    raise FixtureDataError(f"Invalid publication time in {filename}.") from exc
                require(begin <= published <= end, f"Article outside replay window in {filename}.")
            self._news[ticker] = data

    def _read_json(self, filename: str) -> dict[str, Any]:
        require(isinstance(filename, str) and
                re.fullmatch(r"[A-Za-z0-9_.-]+\.json", filename) is not None,
                "Fixture paths must be simple JSON filenames inside test_data.")
        path = (self.root / filename).resolve()
        require(path.parent == self.root, "Fixture path escapes test_data.")
        def reject_constant(value: str) -> None:
            raise ValueError("Non-finite JSON value.")
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)
        except (OSError, ValueError) as exc:
            raise FixtureDataError(f"Cannot read valid test_data/{filename}. "
                                   "No live-data fallback is allowed.") from exc
        require(isinstance(data, dict), f"Expected a JSON object in {filename}.")
        for field in ("Information", "Note", "Error Message"):
            require(not data.get(field), f"{filename} contains an API error, not a fixture response.")
        return data

    @staticmethod
    def _check_provenance(data: dict, filename: str) -> None:
        meta = data.get("_fixture")
        require(isinstance(meta, dict) and meta.get("mode") == "DEVELOPMENT_ONLY"
                and meta.get("independently_verified") is False,
                f"Missing unverified development provenance in {filename}.")

    def get(self, function: str, *, lookback_hours: int | None = None,
            **parameters: Any) -> FixtureSnapshot:
        if function == "TOP_GAINERS_LOSERS":
            require(lookback_hours is None and not parameters,
                    "Unsupported development market-query parameters.")
            data, filename = self._market, self._market_name
        elif function == "NEWS_SENTIMENT":
            require(lookback_hours == self.lookback_hours,
                    "Requested lookback differs from the fixture's fixed replay window.")
            require(not (set(parameters) - {"tickers", "sort", "limit"}),
                    "Unsupported development news-query parameters.")
            ticker = parameters.get("tickers")
            require(isinstance(ticker, str) and ticker in self._news,
                    "Requested ticker has no mapped news fixture; no live fallback allowed.")
            require(parameters.get("sort", "LATEST") == "LATEST",
                    "Development news currently supports LATEST ordering only.")
            limit = parameters.get("limit", 50)
            require(type(limit) is int and limit > 0, "News limit must be a positive integer.")
            data, filename = deepcopy(self._news[ticker]), self._news_names[ticker]
            data["feed"] = sorted(data["feed"], key=lambda row: row["time_published"],
                                  reverse=True)[:limit]
            data["items"] = str(len(data["feed"]))
        else:
            raise FixtureDataError("Development mode supports movers and news only.")
        self.snapshots_used += 1
        print(f"[DEV DATA] {function} | test_data/{filename}")
        return FixtureSnapshot(deepcopy(data), filename, self.replay_time.isoformat(),
                               dict(self.news_window))
