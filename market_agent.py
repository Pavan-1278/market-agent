"""Production runner for the Personal US Stock Market AI Agent.

Run manually:
    python market_agent.py

Force fresh Alpha Vantage data instead of using a valid local cache:
    python market_agent.py --refresh-data

This runner:
- executes the existing live market-agent pipeline (never development fixtures),
- writes a timestamped log under ./logs,
- relies on the core pipeline to send important-story Telegram alerts,
- sends a short completion Telegram message when no important stories are found,
- sends a Telegram failure alert if the run crashes.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from market_agent_test import main as run_pipeline
from telegram_notifier import send_telegram_message


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"


class Tee(io.TextIOBase):
    """Write text to both the terminal and a log file while retaining a copy."""

    def __init__(self, *streams):
        self.streams = streams
        self.buffer = io.StringIO()

    def write(self, text: str) -> int:
        self.buffer.write(text)
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def captured_text(self) -> str:
        return self.buffer.getvalue()


def safe_telegram(message: str) -> None:
    """Attempt a Telegram status message without hiding the original run result."""
    try:
        send_telegram_message(message)
    except Exception as exc:  # Notification failure must not mask pipeline status.
        print(f"Telegram status notification failed: {type(exc).__name__}: {exc}")


def extract_important_count(output: str) -> int | None:
    match = re.search(r"Finished:\s*(\d+)\s+important stor(?:y|ies)", output)
    if not match:
        return None
    return int(match.group(1))


def run_production(*, refresh_data: bool = False) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y-%m-%d_%H%M%S_UTC")
    log_path = LOG_DIR / f"market_agent_{stamp}.log"

    with log_path.open("w", encoding="utf-8") as log_file:
        tee = Tee(sys.__stdout__, log_file)

        with redirect_stdout(tee), redirect_stderr(tee):
            print("=" * 70)
            print("MARKET AGENT — PRODUCTION RUN")
            print("Started (UTC):", started.isoformat(timespec="seconds"))
            print("Log:", log_path)
            print("Mode: LIVE provider/cache data; development fixtures disabled.")
            print("=" * 70)

            try:
                run_pipeline(refresh_data=refresh_data, dev=False)
            except Exception as exc:
                print("\n" + "=" * 70)
                print("PRODUCTION RUN FAILED")
                print(f"Error: {type(exc).__name__}: {exc}")
                print("Traceback:")
                traceback.print_exc()

                finished = datetime.now(timezone.utc)
                print("Finished (UTC):", finished.isoformat(timespec="seconds"))

                # Keep the Telegram alert concise. Do not include secrets or traceback.
                safe_telegram(
                    "🚨 MARKET AGENT — RUN FAILED\n\n"
                    f"Time (UTC): {finished.isoformat(timespec='seconds')}\n"
                    f"Error: {type(exc).__name__}: {str(exc)[:500]}\n\n"
                    "Check the local logs folder for details."
                )
                return 1

            finished = datetime.now(timezone.utc)
            print("\n" + "=" * 70)
            print("PRODUCTION RUN COMPLETE")
            print("Finished (UTC):", finished.isoformat(timespec="seconds"))
            print("Log:", log_path)

            output = tee.captured_text()
            important_count = extract_important_count(output)

            # The core pipeline already sends detailed Telegram messages for
            # important stories. Only send a completion ping when there were none.
            if important_count == 0:
                safe_telegram(
                    "✅ MARKET AGENT — DAILY SCAN COMPLETE\n\n"
                    "No stories met the importance threshold in this run.\n"
                    f"Completed (UTC): {finished.isoformat(timespec='seconds')}"
                )
            elif important_count is None:
                # Unexpected output shape: report completion without asserting a count.
                safe_telegram(
                    "✅ MARKET AGENT — DAILY SCAN COMPLETE\n\n"
                    "The run completed, but the final important-story count could not "
                    "be read from the log.\n"
                    f"Completed (UTC): {finished.isoformat(timespec='seconds')}"
                )

            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Bypass valid Alpha Vantage cache entries for this run.",
    )
    args = parser.parse_args()
    return run_production(refresh_data=args.refresh_data)


if __name__ == "__main__":
    raise SystemExit(main())
