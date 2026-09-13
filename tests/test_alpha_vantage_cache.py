"""Offline cache checks. No API keys, internet, or extra test packages required.
Run from the project root: python -m unittest discover -s tests -v
"""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alpha_vantage_cache as cache_module
from alpha_vantage_cache import AlphaVantageCache, AlphaVantageError

KEY = "LOCAL-TEST-CREDENTIAL-NOT-A-REAL-KEY"
START = datetime(2026, 9, 11, 12, 0, 20, tzinfo=timezone.utc)
MOVERS = {
    "last_updated": "synthetic snapshot",
    "top_gainers": [], "top_losers": [], "most_actively_traded": [],
}
NEWS = {"items": "1", "feed": [{
    "title": "Synthetic announcement", "summary": "Synthetic data for tests only.",
    "url": "https://example.invalid/story", "time_published": "20260911T110000",
}]}


class CacheTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / ".cache" / "alpha_vantage"
        self.client = AlphaVantageCache(KEY, self.path)
        self.clock = self.enterContext(patch.object(cache_module, "utc_now", return_value=START))
        self.sleep = self.enterContext(patch.object(cache_module.time, "sleep"))
        self.get = self.enterContext(patch.object(cache_module.requests, "get"))
        self.response = Mock(ok=True, status_code=200)
        self.response.json.return_value = MOVERS
        self.get.return_value = self.response
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))

    def news(self, **options):
        return self.client.get("NEWS_SENTIMENT", lookback_hours=72,
                               tickers="SYNTH", sort="LATEST", limit=50, **options)

    def json_paths(self):
        return list(self.path.glob("*.json"))

    def change_record(self, field, value):
        path = self.json_paths()[0]
        record = json.loads(path.read_text())
        record[field] = value
        path.write_text(json.dumps(record))

    def test_first_fetch_then_hit_skips_network_and_sleep(self):
        a = self.client.get("TOP_GAINERS_LOSERS")
        b = self.client.get("TOP_GAINERS_LOSERS")
        self.assertFalse(a.from_cache)
        self.assertTrue(b.from_cache)
        self.assertEqual(b.data, MOVERS)
        self.assertEqual(self.get.call_count, 1)
        self.assertEqual(self.sleep.call_count, 1)
        self.assertEqual(self.client.cache_hits, 1)
        self.assertEqual(self.client.request_attempts, 1)
        self.assertIn("[CACHE HIT]", self.output.getvalue())

    def test_news_window_survives_run_time_change(self):
        self.response.json.return_value = NEWS
        a = self.news()
        self.clock.return_value = START + timedelta(minutes=5)
        b = self.news()
        self.assertTrue(b.from_cache)
        self.assertEqual(a.news_window_utc, b.news_window_utc)
        self.assertEqual(b.news_window_utc["to"], "20260911T1200")
        self.assertEqual(b.age_seconds, 300)
        self.assertEqual(self.get.call_count, 1)

    def test_hit_does_not_extend_original_expiry(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.clock.return_value = START + timedelta(minutes=14)
        self.assertTrue(self.client.get("TOP_GAINERS_LOSERS").from_cache)
        self.clock.return_value = START + timedelta(minutes=15)
        self.assertFalse(self.client.get("TOP_GAINERS_LOSERS").from_cache)
        self.assertEqual(self.get.call_count, 2)

    def test_refresh_bypasses_valid_cache(self):
        self.client.get("TOP_GAINERS_LOSERS")
        forced = AlphaVantageCache(KEY, self.path, refresh=True)
        self.assertFalse(forced.get("TOP_GAINERS_LOSERS").from_cache)
        self.assertEqual(self.get.call_count, 2)

    def test_successful_empty_feed_is_cached(self):
        self.response.json.return_value = {"items": "0", "feed": []}
        self.news()
        b = self.news()
        self.assertTrue(b.from_cache)
        self.assertEqual(b.data["feed"], [])
        self.assertEqual(self.get.call_count, 1)

    def test_error_messages_not_cached_and_key_redacted(self):
        for name in ("Information", "Note", "Error Message"):
            with self.subTest(field=name):
                self.response.json.return_value = {name: f"Rate limited {KEY}"}
                with self.assertRaises(AlphaVantageError) as exc:
                    self.news()
                self.assertNotIn(KEY, str(exc.exception))
                self.assertIn("[REDACTED]", str(exc.exception))
                self.assertEqual(self.json_paths(), [])

    def test_network_failure_not_cached(self):
        self.get.side_effect = cache_module.requests.RequestException(f"URL included {KEY}")
        with self.assertRaises(AlphaVantageError) as exc:
            self.news()
        self.assertNotIn(KEY, str(exc.exception))
        self.assertEqual(self.json_paths(), [])

    def test_http_failure_not_cached(self):
        self.response.ok = False
        self.response.status_code = 429
        with self.assertRaisesRegex(AlphaVantageError, "HTTP 429"):
            self.news()
        self.assertEqual(self.json_paths(), [])

    def test_invalid_json_not_cached(self):
        self.response.json.side_effect = ValueError("Bad JSON")
        with self.assertRaises(AlphaVantageError):
            self.news()
        self.assertEqual(self.json_paths(), [])

    def test_missing_feed_not_treated_as_empty(self):
        self.response.json.return_value = {"items": "0"}
        with self.assertRaisesRegex(AlphaVantageError, "expected data lists"):
            self.news()
        self.assertEqual(self.json_paths(), [])

    def test_missing_mover_group_is_failure(self):
        self.response.json.return_value = {"top_gainers": [], "top_losers": []}
        with self.assertRaises(AlphaVantageError):
            self.client.get("TOP_GAINERS_LOSERS")
        self.assertEqual(self.json_paths(), [])

    def test_no_expired_fallback_when_api_fails(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.clock.return_value = START + timedelta(minutes=16)
        self.response.json.return_value = {"Information": "rate limited"}
        with self.assertRaises(AlphaVantageError):
            self.client.get("TOP_GAINERS_LOSERS")
        self.assertEqual(self.client.cache_hits, 0)

    def test_corrupt_file_refetched(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.json_paths()[0].write_text("invalid JSON")
        self.assertFalse(self.client.get("TOP_GAINERS_LOSERS").from_cache)
        self.assertEqual(self.get.call_count, 2)

    def test_future_timestamp_refetched(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.clock.return_value = START - timedelta(minutes=1)
        self.assertFalse(self.client.get("TOP_GAINERS_LOSERS").from_cache)

    def test_saved_error_refetched(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.change_record("data", {"Note": "An error is not a response."})
        self.assertFalse(self.client.get("TOP_GAINERS_LOSERS").from_cache)

    def test_changed_ticker_creates_separate_entry(self):
        self.response.json.return_value = NEWS
        self.news()
        self.client.get("NEWS_SENTIMENT", lookback_hours=72,
                        tickers="OTHER", sort="LATEST", limit=50)
        self.assertEqual(self.get.call_count, 2)
        self.assertEqual(len(self.json_paths()), 2)

    def test_changed_lookback_creates_separate_entry(self):
        self.response.json.return_value = NEWS
        self.news()
        self.client.get("NEWS_SENTIMENT", lookback_hours=24,
                        tickers="SYNTH", sort="LATEST", limit=50)
        self.assertEqual(self.get.call_count, 2)

    def test_explicit_time_bounds_have_distinct_cache_keys(self):
        self.response.json.return_value = NEWS
        first = dict(tickers="SYNTH", time_from="20260910T1200", time_to="20260911T1200")
        self.client.get("NEWS_SENTIMENT", **first)
        self.assertTrue(self.client.get("NEWS_SENTIMENT", **first).from_cache)
        first["time_to"] = "20260911T1201"
        self.assertFalse(self.client.get("NEWS_SENTIMENT", **first).from_cache)
        self.assertEqual(self.get.call_count, 2)

    def test_metadata_and_files_do_not_store_key(self):
        result = self.client.get("TOP_GAINERS_LOSERS")
        text = "".join(path.read_text() for path in self.path.iterdir())
        self.assertNotIn(KEY, text)
        self.assertNotIn('"apikey"', text)
        self.assertNotIn(KEY, str(result.evidence_metadata()))
        self.assertEqual((self.path / ".gitignore").read_text(), "*\n")
        self.assertFalse(list(self.path.glob("*.tmp")))

    def test_response_that_echoes_key_rejected(self):
        self.response.json.return_value = {**MOVERS, "detail": KEY}
        with self.assertRaises(AlphaVantageError):
            self.client.get("TOP_GAINERS_LOSERS")
        self.assertEqual(self.json_paths(), [])

    def test_credentials_cannot_be_passed_as_metadata(self):
        with self.assertRaises(ValueError):
            self.client.get("TOP_GAINERS_LOSERS", apikey=KEY)
        self.get.assert_not_called()

    def test_truncated_or_changed_request_metadata_refetched(self):
        self.response.json.return_value = NEWS
        self.news()
        path = self.json_paths()[0]
        record = json.loads(path.read_text())
        record["request_parameters"]["tickers"] = "NOT_SYNTH"
        path.write_text(json.dumps(record))
        self.assertFalse(self.news().from_cache)

    def test_write_failure_uses_response_without_cache(self):
        with patch.object(self.client.cache_dir.__class__, "mkdir", side_effect=OSError()):
            result = self.client.get("TOP_GAINERS_LOSERS")
        self.assertEqual(result.data, MOVERS)
        self.assertFalse(result.from_cache)
        self.assertIn("[CACHE WARNING]", self.output.getvalue())

    def test_no_nan_saved(self):
        self.response.json.return_value = {**MOVERS, "bad": float("nan")}
        with self.assertRaises(AlphaVantageError):
            self.client.get("TOP_GAINERS_LOSERS")
        self.assertEqual(self.json_paths(), [])

    def test_same_cache_can_be_reused_by_new_instance(self):
        self.client.get("TOP_GAINERS_LOSERS")
        another = AlphaVantageCache(KEY, self.path)
        self.assertTrue(another.get("TOP_GAINERS_LOSERS").from_cache)
        self.assertEqual(self.get.call_count, 1)

    def test_changed_entitlement_does_not_reuse_old_cache(self):
        self.client.get("TOP_GAINERS_LOSERS")
        self.client.get("TOP_GAINERS_LOSERS", entitlement="delayed")
        self.assertEqual(self.get.call_count, 2)

    def test_guardrails_on_config(self):
        for bad in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                AlphaVantageCache(KEY, self.path, ttl_seconds=bad)
        with self.assertRaises(ValueError):
            AlphaVantageCache(KEY, self.path, delay_seconds=0)
        with self.assertRaises(ValueError):
            self.client.get("NEWS_SENTIMENT", lookback_hours=72, time_to="20260911T1200")


if __name__ == "__main__":
    unittest.main()
