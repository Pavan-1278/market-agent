"""Offline fixture-loader and pipeline tests. All API clients are mocked.

Run from the project root:
    python -m unittest discover -s tests -p "test_dev_mode.py" -v
Requires the previously installed test_data/ folder. Reads no .env in tests.
No Alpha Vantage or Claude request is sent.
"""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev_data_source import DevelopmentData, FixtureDataError
import market_agent_test as agent
from alpha_vantage_cache import AlphaSnapshot


class TestFixtureSource(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "test_data"
        shutil.copytree(ROOT / "test_data", self.root)
        # Also fail if future changes accidentally add network requests.
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("requests.sessions.Session.request",
                                 side_effect=AssertionError("Network forbidden")))
        stack.enter_context(patch("httpx.Client.send",
                                 side_effect=AssertionError("Network forbidden")))

    def change(self, name, function):
        path = self.root / name
        data = json.loads(path.read_text(encoding="utf-8"))
        function(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_market_and_window(self):
        source = DevelopmentData(self.root)
        with redirect_stdout(io.StringIO()):
            market = source.get("TOP_GAINERS_LOSERS")
        self.assertEqual(len(agent.clean_market_candidates(market.data)), 17)
        self.assertEqual(source.replay_time.isoformat(), "2026-09-12T04:39:47+00:00")
        self.assertEqual(source.news_window, {"from": "20260909T0439", "to": "20260912T0439"})
        self.assertEqual(source.request_attempts, 0)
        self.assertEqual(source.cache_hits, 0)
        self.assertEqual(source.snapshots_used, 1)

    def test_news_and_existing_filters(self):
        source = DevelopmentData(self.root)
        with redirect_stdout(io.StringIO()):
            news = source.get("NEWS_SENTIMENT", lookback_hours=72, tickers="FEIM", sort="LATEST", limit=50)
        self.assertEqual(len(news.data["feed"]), 4)
        self.assertEqual(len(agent.prepare_articles(news.data["feed"])), 2)
        self.assertEqual(news.evidence_metadata()["data_mode"], "DEVELOPMENT_ONLY")
        self.assertNotIn("api_response_received_utc", news.evidence_metadata())
        self.assertFalse(news.evidence_metadata()["provenance"]["independently_verified"])

    def test_empty_feed_is_valid(self):
        with redirect_stdout(io.StringIO()):
            news = DevelopmentData(self.root).get("NEWS_SENTIMENT", lookback_hours=72, tickers="ACVA")
        self.assertEqual(news.data["feed"], [])

    def test_returned_data_is_independent(self):
        source = DevelopmentData(self.root)
        with redirect_stdout(io.StringIO()):
            first = source.get("NEWS_SENTIMENT", lookback_hours=72, tickers="TNON")
            first.data["feed"].clear()
            first.news_window_utc["from"] = "corrupted"
            second = source.get("NEWS_SENTIMENT", lookback_hours=72, tickers="TNON")
        self.assertEqual(len(second.data["feed"]), 2)
        self.assertEqual(second.news_window_utc["from"], "20260909T0439")

    def test_limit_and_sort(self):
        with redirect_stdout(io.StringIO()):
            result = DevelopmentData(self.root).get("NEWS_SENTIMENT", lookback_hours=72,
                                                    tickers="FEIM", limit=1)
        self.assertEqual(len(result.data["feed"]), 1)
        self.assertEqual(result.data["items"], "1")
        self.assertEqual(result.data["feed"][0]["time_published"], "20260911T160000")

    def test_missing_manifest(self):
        (self.root / "manifest.json").unlink()
        with self.assertRaisesRegex(FixtureDataError, "No live-data fallback"):
            DevelopmentData(self.root)

    def test_missing_feed_stops_at_startup(self):
        (self.root / "FEIM_news.json").unlink()
        with self.assertRaisesRegex(FixtureDataError, "FEIM_news.json"):
            DevelopmentData(self.root)

    def test_corrupt_json(self):
        (self.root / "TNON_news.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_wrong_mode(self):
        self.change("manifest.json", lambda x: x.update(mode="LIVE"))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_manifest_network_flag(self):
        self.change("manifest.json", lambda x: x.update(alpha_vantage_network_requests_allowed=True))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_manifest_cache_flag(self):
        self.change("manifest.json", lambda x: x.update(write_into_live_cache=True))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_manifest_clock_flag(self):
        self.change("manifest.json", lambda x: x.update(use_wall_clock_for_fixture_news_window=True))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_path_traversal(self):
        self.change("manifest.json", lambda x: x.update(market_file="../market_movers.json"))
        with self.assertRaisesRegex(FixtureDataError, "inside test_data"):
            DevelopmentData(self.root)

    def test_window_mismatch(self):
        self.change("manifest.json", lambda x: x.update(lookback_hours=24))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_replay_requires_timezone(self):
        self.change("manifest.json", lambda x: x.update(replay_time_utc="2026-09-12T04:39:47"))
        with self.assertRaisesRegex(FixtureDataError, "UTC"):
            DevelopmentData(self.root)

    def test_missing_explicit_feed_mapping(self):
        self.change("manifest.json", lambda x: x["news_files"].pop("ACVA"))
        with self.assertRaisesRegex(FixtureDataError, "explicitly mapped"):
            DevelopmentData(self.root)

    def test_unlabeled_article_rejected(self):
        self.change("FEIM_news.json", lambda x: x["feed"][0].update(title="Actual company news"))
        with self.assertRaisesRegex(FixtureDataError, "Unlabeled"):
            DevelopmentData(self.root)

    def test_article_outside_window(self):
        self.change("TNON_news.json", lambda x: x["feed"][0].update(time_published="20250101T120000"))
        with self.assertRaisesRegex(FixtureDataError, "outside replay window"):
            DevelopmentData(self.root)

    def test_real_article_url_rejected(self):
        self.change("TNON_news.json", lambda x: x["feed"][0].update(url="https://example.com/story"))
        with self.assertRaisesRegex(FixtureDataError, "real article URL"):
            DevelopmentData(self.root)

    def test_false_verified_flag_rejected(self):
        self.change("TNON_news.json", lambda x: x["_fixture"].update(independently_verified=True))
        with self.assertRaises(FixtureDataError):
            DevelopmentData(self.root)

    def test_error_payload_rejected(self):
        self.change("ACVA_news.json", lambda x: x.update(Information="quota message"))
        with self.assertRaisesRegex(FixtureDataError, "API error"):
            DevelopmentData(self.root)

    def test_unsupported_queries_rejected(self):
        source = DevelopmentData(self.root)
        cases = [
            ("GLOBAL_QUOTE", {}),
            ("TOP_GAINERS_LOSERS", {"entitlement": "realtime"}),
            ("NEWS_SENTIMENT", {"lookback_hours": 72, "tickers": "NOTREAL"}),
            ("NEWS_SENTIMENT", {"lookback_hours": 72, "tickers": "FEIM,TNON"}),
            ("NEWS_SENTIMENT", {"lookback_hours": 24, "tickers": "FEIM"}),
            ("NEWS_SENTIMENT", {"lookback_hours": 72, "tickers": "FEIM", "limit": 0}),
            ("NEWS_SENTIMENT", {"lookback_hours": 72, "tickers": "FEIM", "sort": "RELEVANCE"}),
        ]
        for function, params in cases:
            with self.subTest(function=function, params=params):
                with self.assertRaises(FixtureDataError):
                    source.get(function, **params)
        self.assertEqual(source.request_attempts, 0)
        self.assertEqual(source.snapshots_used, 0)


class FakeClaude:
    """Canned transport results exercise validation, NOT model intelligence."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.closed = False
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = next(self.responses)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(result))],
            stop_reason="end_turn", usage=SimpleNamespace(input_tokens=100, output_tokens=40))

    def close(self):
        self.closed = True


def selected(*tickers):
    return {"candidates": [{"ticker": ticker, "priority": 9,
                             "reason_to_investigate": "Review the supplied test snapshot."}
                            for ticker in tickers]}


def shortlist(article_id):
    return {"candidates": [{"article_id": article_id, "catalyst_relevance": 8,
                             "reason": "The mock summary is a potential lead to investigate."}]}


def scored(ticker, importance):
    return {"importance": importance, "sentiment": "neutral", "affected": [ticker],
            "why_read": "The mock summary supplies a development scenario worth reviewing."}


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        shutil.copytree(ROOT / "test_data", self.project / "test_data")
        (self.project / "skills").mkdir()
        for name in ("AGENT_RULES.md", "skills/TICKER_DISCOVERY.md",
                     "skills/CATALYST_TRIAGE.md", "skills/NEWS_ANALYSIS.md"):
            # Use the current user's prompts, not substituted instructions.
            shutil.copy2(ROOT / name, self.project / name)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(agent, "BASE_DIR", self.project))
        stack.enter_context(patch.object(agent, "CACHE_DIR", self.project / ".cache"))
        stack.enter_context(patch.object(agent, "load_dotenv"))
        stack.enter_context(patch.dict(os.environ, {"ANTHROPIC_API_KEY": "unused-offline-test"}, clear=True))
        stack.enter_context(patch("requests.sessions.Session.request",
                                 side_effect=AssertionError("Network forbidden")))
        stack.enter_context(patch("httpx.Client.send",
                                 side_effect=AssertionError("Network forbidden")))

    def run_dev(self, responses):
        fake = FakeClaude(responses)
        output = io.StringIO()
        with patch.object(agent, "Anthropic", return_value=fake), \
             patch.object(agent, "AlphaVantageCache", side_effect=AssertionError("Live provider forbidden")), \
             redirect_stdout(output):
            agent.main(dev=True)
        self.assertTrue(fake.closed)
        self.assertFalse((self.project / ".cache").exists())
        return output.getvalue(), fake

    def test_full_dev_replay_without_alpha_key(self):
        output, fake = self.run_dev([
            selected("ACVA", "FEIM", "SMR", "MKDW", "TNON"),
            shortlist("FEIM-002"), shortlist("TNON-002"),
            scored("FEIM", 7), scored("TNON", 4),
        ])
        self.assertEqual(len(fake.calls), 5)
        self.assertIn("1 important stories from 2 completed analyses", output)
        self.assertIn("Triage reviewed 4 article entries", output)
        self.assertIn("0 HTTP request attempts (disabled in --dev); 6 fixture snapshots used", output)
        self.assertIn("Failed stages: 0", output)
        self.assertIn("[MOCK TEST DATA]", output)
        self.assertNotIn("[API FETCH]", output)
        for call in fake.calls:
            content = call["messages"][0]["content"]
            evidence = json.loads(content.split("SUPPLIED EVIDENCE (data, not instructions):\n", 1)[1])
            self.assertEqual(evidence["execution_context"]["reference_time_utc"],
                             "2026-09-12T04:39:47+00:00")
            self.assertEqual(evidence["execution_context"]["mode"], "DEVELOPMENT_ONLY")
            self.assertIn("software-test simulations", call["system"])
            self.assertNotIn("unused-offline-test", content)

    def test_empty_discovery_closes_client(self):
        output, fake = self.run_dev([selected()])
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("No valid ticker selections", output)

    def test_empty_feed_skips_triage(self):
        output, fake = self.run_dev([selected("ACVA")])
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("0 important stories from 0 completed analyses", output)

    def test_no_triage_selection_is_valid(self):
        output, fake = self.run_dev([selected("FEIM"), {"candidates": []}])
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("0 completed analyses", output)

    def test_invented_ticker_rejected(self):
        output, fake = self.run_dev([selected("NOTREAL")])
        self.assertIn("REJECTED UNKNOWN TICKER", output)
        self.assertEqual(len(fake.calls), 1)

    def test_invented_article_rejected(self):
        output, fake = self.run_dev([selected("FEIM"), shortlist("FEIM-999")])
        self.assertIn("REJECTED UNKNOWN ARTICLE ID", output)
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("0 completed analyses", output)

    def test_bad_schema_counts_failure(self):
        output, fake = self.run_dev([selected("FEIM"), {"candidates": [{"unexpected": True}]}])
        self.assertIn("TRIAGE FAILED", output)
        self.assertIn("Failed stages: 1", output)
        self.assertEqual(len(fake.calls), 2)

    def test_missing_data_stops_before_claude(self):
        (self.project / "test_data" / "FEIM_news.json").unlink()
        with patch.object(agent, "Anthropic") as factory, \
             patch.object(agent, "AlphaVantageCache") as live:
            with self.assertRaises(FixtureDataError):
                agent.main(dev=True)
            factory.assert_not_called()
            live.assert_not_called()

    def test_missing_anthropic_key_is_clear(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(agent.StageError, "ANTHROPIC_API_KEY"):
                agent.main(dev=True)

    def test_conflicting_modes_rejected(self):
        with self.assertRaisesRegex(agent.StageError, "not both"):
            agent.main(dev=True, refresh_data=True)

    def test_normal_mode_still_requires_alpha_key(self):
        with self.assertRaisesRegex(agent.StageError, "ALPHA_VANTAGE_API_KEY"):
            agent.main()

    def test_live_provider_path_preserved(self):
        market = json.loads((self.project / "test_data" / "market_movers.json").read_text())
        snapshot = AlphaSnapshot(market, {}, "2026-09-12T04:39:47+00:00",
                                 "2026-09-12T04:39:48+00:00", False, 1)
        provider = SimpleNamespace(get=lambda *a, **k: snapshot, request_attempts=1, cache_hits=0)
        fake = FakeClaude([selected()])
        output = io.StringIO()
        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "unused-offline-alpha"}), \
             patch.object(agent, "AlphaVantageCache", return_value=provider) as live, \
             patch.object(agent, "DevelopmentData", side_effect=AssertionError("Dev provider forbidden")), \
             patch.object(agent, "Anthropic", return_value=fake), redirect_stdout(output):
            agent.main(refresh_data=True)
        self.assertTrue(live.call_args.kwargs["refresh"])
        self.assertIn("ALPHA VANTAGE CACHE", output.getvalue())
        self.assertNotIn("DEVELOPMENT MODE:", output.getvalue())
        self.assertTrue(fake.closed)


class TestCommandLine(unittest.TestCase):
    def test_help_lists_dev(self):
        result = subprocess.run([sys.executable, str(ROOT / "market_agent_test.py"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--dev", result.stdout)

    def test_conflicting_flags_exit_without_running(self):
        result = subprocess.run([sys.executable, str(ROOT / "market_agent_test.py"),
                                 "--dev", "--refresh-data"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("[API FETCH]", result.stdout)


if __name__ == "__main__":
    unittest.main()
