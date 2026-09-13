"""Short-lived, local cache for this project's two Alpha Vantage endpoints.

Caches successful provider responses, NOT Claude outputs. A rolling news query
reuses a saved 72-hour snapshot only while its original request is within the
TTL; the original UTC query window is retained and exposed to the caller.
Errors never become empty feeds and expired data is never a fallback.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Any

import requests

API_URL = "https://www.alphavantage.co/query"
CACHE_VERSION = 1
SUPPORTED = {"TOP_GAINERS_LOSERS", "NEWS_SENTIMENT"}


class AlphaVantageError(RuntimeError):
    """Request or response failure; not evidence that no news exists."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def encode_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def parse_utc(text: str) -> datetime:
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        raise ValueError("Timestamp has no timezone.")
    return result.astimezone(timezone.utc)


def validate_payload(data: Any, function: str, api_key: str) -> None:
    if not isinstance(data, dict):
        raise AlphaVantageError(f"{function}: unexpected response format.")
    for field in ("Error Message", "Information", "Note"):
        if data.get(field):
            detail = str(data[field]).replace(api_key, "[REDACTED]")
            raise AlphaVantageError(f"{function}: {field}: {detail[:1000]}")
    fields = ("feed",) if function == "NEWS_SENTIMENT" else (
        "top_gainers", "top_losers", "most_actively_traded"
    )
    if any(not isinstance(data.get(field), list) for field in fields):
        raise AlphaVantageError(f"{function}: response is missing expected data lists.")
    try:
        serialized = encode_json(data)
    except (TypeError, ValueError) as exc:
        raise AlphaVantageError(f"{function}: response contains invalid JSON values.") from exc
    # Do not save or pass along a response that unexpectedly echoes our key.
    if api_key in serialized:
        raise AlphaVantageError(f"{function}: response unexpectedly contained a credential.")


@dataclass(frozen=True)
class AlphaSnapshot:
    data: dict[str, Any]
    request_parameters: dict[str, Any]  # Never contains apikey.
    request_started_utc: str
    received_utc: str
    from_cache: bool
    age_seconds: float

    @property
    def news_window_utc(self) -> dict[str, str]:
        return {
            "from": self.request_parameters["time_from"],
            "to": self.request_parameters["time_to"],
        }

    def evidence_metadata(self) -> dict[str, Any]:
        return {
            "api_request_started_utc": self.request_started_utc,
            "api_response_received_utc": self.received_utc,
            "reused_from_local_cache": self.from_cache,
            "request_age_seconds_at_read": round(self.age_seconds, 1),
            "note": "Retrieval time is not the market snapshot or event time.",
        }


class AlphaVantageCache:
    def __init__(self, api_key: str, cache_dir: Path, *, ttl_seconds: float = 900,
                 delay_seconds: float = 1.2, refresh: bool = False) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("An Alpha Vantage key is required.")
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("Cache lifetime must be positive and finite.")
        if not math.isfinite(delay_seconds) or delay_seconds < 1.2:
            raise ValueError("Request delay must be at least 1.2 seconds.")
        self._api_key = api_key.strip()
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.delay_seconds = delay_seconds
        self.refresh = refresh
        self.request_attempts = 0
        self.cache_hits = 0

    def _path(self, identity: dict) -> Path:
        digest = hashlib.sha256(encode_json(identity).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read(self, path: Path, identity: dict, now: datetime) -> AlphaSnapshot | None:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("identity") != identity:
                return None
            started = parse_utc(record["request_started_utc"])
            received = parse_utc(record["received_utc"])
            age = (now - started).total_seconds()
            if not 0 <= age < self.ttl_seconds or not started <= received <= now:
                return None
            saved_params = record["request_parameters"]
            if not isinstance(saved_params, dict):
                return None
            comparable = dict(saved_params)
            lookback = identity["lookback_hours"]
            if lookback is not None:
                end = datetime.strptime(comparable.pop("time_to"), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
                begin = datetime.strptime(comparable.pop("time_from"), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
                if end - begin != timedelta(hours=lookback):
                    return None
                if end != started.replace(second=0, microsecond=0):
                    return None
            if comparable != identity["parameters"]:
                return None
            validate_payload(record["data"], identity["function"], self._api_key)
            return AlphaSnapshot(record["data"], saved_params,
                                 record["request_started_utc"], record["received_utc"],
                                 True, age)
        except (OSError, ValueError, TypeError, KeyError, OverflowError,
                AlphaVantageError):
            # Missing, expired, corrupt, or incompatible cache: fetch normally.
            return None

    def _save(self, path: Path, record: dict) -> None:
        temp_path = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # A second safety net; also add .cache/ to the root .gitignore.
            ignore = self.cache_dir / ".gitignore"
            if not ignore.exists():
                ignore.write_text("*\n", encoding="utf-8")
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.cache_dir, suffix=".tmp",
                                             delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(encode_json(record))
            # Close before replacing, including on Windows.
            temp_path.replace(path)
        except (OSError, ValueError, TypeError):
            print("[CACHE WARNING] Could not save this response; using fetched data only.")
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def get(self, function: str, *, lookback_hours: int | None = None,
            **parameters: Any) -> AlphaSnapshot:
        if function not in SUPPORTED:
            raise ValueError("This cache currently supports movers and news only.")
        allowed = {"entitlement"} if function == "TOP_GAINERS_LOSERS" else {
            "tickers", "topics", "sort", "limit", "time_from", "time_to"
        }
        if set(parameters) - allowed:
            raise ValueError("Unsupported parameters; never pass credentials as query metadata.")
        if lookback_hours is not None:
            if (function != "NEWS_SENTIMENT" or type(lookback_hours) is not int
                    or lookback_hours <= 0):
                raise ValueError("A positive integer lookback is supported for news only.")
            if "time_from" in parameters or "time_to" in parameters:
                raise ValueError("Use either a rolling lookback or explicit times, not both.")
        # Semantic identity for rolling news: ticker, sort, limit, window length.
        # Exact old time bounds are kept in the snapshot, not relabelled as now.
        identity = {
            "version": CACHE_VERSION, "endpoint": API_URL, "function": function,
            "parameters": dict(parameters), "lookback_hours": lookback_hours,
        }
        if self._api_key in encode_json(identity):
            raise ValueError("Query metadata must not contain credentials.")
        path = self._path(identity)
        label = function + (f" [{parameters['tickers']}]" if parameters.get("tickers") else "")
        if not self.refresh:
            cached = self._read(path, identity, utc_now())
            if cached is not None:
                self.cache_hits += 1
                print(f"[CACHE HIT] {label} | request age: {cached.age_seconds:.0f}s | "
                      f"received: {cached.received_utc}")
                return cached

        print(f"[API FETCH] {label} | "
              + ("forced refresh" if self.refresh else "no unexpired matching cache"))
        # Sequential requests only. Other scripts/processes have separate limits.
        time.sleep(self.delay_seconds)
        started = utc_now()
        request_params = dict(parameters)
        if lookback_hours is not None:
            end = started.replace(second=0, microsecond=0)
            request_params["time_from"] = (end - timedelta(hours=lookback_hours)).strftime("%Y%m%dT%H%M")
            request_params["time_to"] = end.strftime("%Y%m%dT%H%M")
        self.request_attempts += 1
        try:
            response = requests.get(
                API_URL, params={"function": function, "apikey": self._api_key,
                                 **request_params}, timeout=30,
            )
        except requests.RequestException as exc:
            # Exception strings can contain the URL/key. Never print them.
            raise AlphaVantageError(f"{function}: network request failed ({type(exc).__name__}).") from exc
        if not response.ok:
            raise AlphaVantageError(f"{function}: Alpha Vantage returned HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise AlphaVantageError(f"{function}: response was not valid JSON.") from exc
        validate_payload(data, function, self._api_key)
        received = utc_now()
        record = {
            "identity": identity, "request_parameters": request_params,
            "request_started_utc": started.isoformat(), "received_utc": received.isoformat(),
            "data": data,
        }
        # Successful empty feeds ARE snapshots; API errors are never stored.
        self._save(path, record)
        return AlphaSnapshot(data, request_params, record["request_started_utc"],
                             record["received_utc"], False,
                             max(0.0, (received - started).total_seconds()))

