"""Create the Market Agent's local SQLite history table.

SQLite history helper for the Market Agent.
Run python database.py --dev or --live to create/check the table only.
The market agent imports this module to save completed analyses.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# One row will represent one completed analysis, including its supplied evidence.
# A URL is intentionally NOT unique: later prompt/model versions may reanalyze it.
# *_json fields will be populated with json.dumps(...) by the later save function.
# published_time preserves the provider's timestamp; UTC fields are ISO strings.
CREATE_ARTICLES_SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id                     INTEGER PRIMARY KEY,
    article_url            TEXT NOT NULL,
    headline               TEXT NOT NULL,
    source                 TEXT NOT NULL,
    published_time         TEXT,
    summary                TEXT NOT NULL,
    searched_tickers_json  TEXT NOT NULL,
    importance             INTEGER NOT NULL
        CHECK (typeof(importance) = 'integer' AND importance BETWEEN 1 AND 10),
    sentiment              TEXT NOT NULL
        CHECK (sentiment IN ('bullish', 'bearish', 'mixed', 'neutral')),
    affected_tickers_json  TEXT NOT NULL,
    why_read               TEXT NOT NULL,
    analyzed_at_utc        TEXT NOT NULL,
    reference_time_utc     TEXT NOT NULL,
    model                  TEXT NOT NULL,
    prompt_hash            TEXT NOT NULL,
    evidence_json          TEXT NOT NULL
)
"""

EXPECTED_COLUMNS = (
    "id", "article_url", "headline", "source", "published_time", "summary",
    "searched_tickers_json", "importance", "sentiment", "affected_tickers_json",
    "why_read", "analyzed_at_utc", "reference_time_utc", "model", "prompt_hash",
    "evidence_json",
)


def database_path(*, dev: bool) -> Path:
    """Choose a file relative to this module, never to the terminal's directory."""
    if not isinstance(dev, bool):
        raise TypeError("dev must be True or False")
    return BASE_DIR / ("market_agent_dev.db" if dev else "market_agent.db")


def initialize_database(*, dev: bool) -> Path:
    """Create the table/index if missing; never clear or replace existing rows.

    This initial setup does not migrate an existing incompatible table. Fail
    explicitly instead of deleting a database or silently accepting other fields.
    """
    path = database_path(dev=dev)
    with closing(sqlite3.connect(path, timeout=10)) as connection:
        # Use an explicit transaction so a schema error rolls back the setup.
        with connection:
            connection.execute("BEGIN")
            connection.execute(CREATE_ARTICLES_SQL)
            actual_columns = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(articles)")
            )
            if actual_columns != EXPECTED_COLUMNS:
                raise RuntimeError(
                    f"Existing articles table has a different schema: {path}. "
                    "Leave that database in place; a migration is required."
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(article_url)"
            )
    return path


def count_articles(*, dev: bool) -> int:
    """Read the existing row count without creating a missing database."""
    path = database_path(dev=dev)
    # A read-only URI works with absolute Windows paths as well as POSIX paths.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT COUNT(*) FROM articles").fetchone()
        return int(row[0])



@dataclass(frozen=True)
class SaveResult:
    row_id: int
    inserted: bool


def _canonical_string_list(values: list[str] | tuple[str, ...]) -> str:
    if not isinstance(values, (list, tuple)):
        raise TypeError("ticker values must be a list or tuple")
    cleaned = sorted({str(value).strip().upper() for value in values if str(value).strip()})
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class ReusableAnalysis:
    row_id: int
    importance: int
    sentiment: str
    affected_tickers: list[str]
    why_read: str
    analyzed_at_utc: str


def find_reusable_analysis(
    *,
    dev: bool,
    article: dict,
    searched_tickers: list[str],
    model: str,
    prompt_hash: str,
    max_age_hours: float | None = None,
) -> ReusableAnalysis | None:
    """Return a prior analysis only when the relevant evidence is unchanged.

    Reuse requires the same article URL/title/source/published timestamp/summary,
    the same searched-ticker context, model, and prompt fingerprint. Development
    replay may reuse without an age limit. Live callers can provide max_age_hours
    so an old analysis is not reused indefinitely. No database rows are modified.
    """
    if not isinstance(dev, bool):
        raise TypeError("dev must be True or False")
    if not isinstance(article, dict):
        raise TypeError("article must be a dict")
    if max_age_hours is not None and (
        isinstance(max_age_hours, bool)
        or not isinstance(max_age_hours, (int, float))
        or max_age_hours <= 0
    ):
        raise ValueError("max_age_hours must be a positive number or None")

    try:
        article_url = str(article["url"]).strip()
        headline = str(article["title"]).strip()
    except KeyError as exc:
        raise ValueError(f"article is missing {exc.args[0]}") from exc
    source = str(article.get("source") or "unknown").strip()
    published_time = str(article.get("time_published") or "").strip() or None
    summary = str(article.get("summary") or "")
    model = str(model).strip()
    prompt_hash = str(prompt_hash).strip()
    searched_json = _canonical_string_list(searched_tickers)

    if not article_url or not headline or not source or not model or not prompt_hash:
        raise ValueError("article identity, model, and prompt_hash are required")

    path = database_path(dev=dev)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute(
            """
            SELECT id, importance, sentiment, affected_tickers_json, why_read,
                   analyzed_at_utc
            FROM articles
            WHERE article_url = ?
              AND headline = ?
              AND source = ?
              AND COALESCE(published_time, '') = ?
              AND summary = ?
              AND searched_tickers_json = ?
              AND model = ?
              AND prompt_hash = ?
            ORDER BY id DESC
            """,
            (article_url, headline, source, published_time or "", summary,
             searched_json, model, prompt_hash),
        ).fetchall()

    now = datetime.now(timezone.utc)
    for row in rows:
        analyzed_at = str(row[5])
        if max_age_hours is not None:
            try:
                analyzed_dt = datetime.fromisoformat(analyzed_at)
                if analyzed_dt.tzinfo is None:
                    analyzed_dt = analyzed_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - analyzed_dt.astimezone(timezone.utc)).total_seconds() / 3600
            except ValueError:
                continue
            if age_hours < 0 or age_hours > float(max_age_hours):
                continue
        try:
            affected = json.loads(row[3])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(affected, list) or not all(isinstance(x, str) for x in affected):
            continue
        return ReusableAnalysis(
            row_id=int(row[0]),
            importance=int(row[1]),
            sentiment=str(row[2]),
            affected_tickers=affected,
            why_read=str(row[4]),
            analyzed_at_utc=analyzed_at,
        )
    return None


def save_article_analysis(
    *,
    dev: bool,
    article: dict,
    searched_tickers: list[str],
    importance: int,
    sentiment: str,
    affected_tickers: list[str],
    why_read: str,
    reference_time_utc: str,
    model: str,
    prompt_hash: str,
    evidence: dict,
) -> SaveResult:
    """Persist one completed, locally validated analysis.

    Exact repeats are idempotent: the same evidence + prompt/model + output is
    not inserted twice. If Claude produces a materially different analysis on
    a later run, that is retained as a separate history row.
    """
    if not isinstance(dev, bool):
        raise TypeError("dev must be True or False")
    if not isinstance(article, dict):
        raise TypeError("article must be a dict")
    try:
        article_url = str(article["url"]).strip()
        headline = str(article["title"]).strip()
    except KeyError as exc:
        raise ValueError(f"article is missing {exc.args[0]}") from exc
    source = str(article.get("source") or "unknown").strip()
    published_time = str(article.get("time_published") or "").strip() or None
    summary = str(article.get("summary") or "")
    why_read = str(why_read).strip()
    sentiment = str(sentiment).strip().lower()
    reference_time_utc = str(reference_time_utc).strip()
    model = str(model).strip()
    prompt_hash = str(prompt_hash).strip()

    if not article_url or not headline or not source or not why_read:
        raise ValueError("article URL, headline, source, and why_read must be non-empty")
    if not isinstance(importance, int) or isinstance(importance, bool) or not 1 <= importance <= 10:
        raise ValueError("importance must be an integer from 1 to 10")
    if sentiment not in {"bullish", "bearish", "mixed", "neutral"}:
        raise ValueError("sentiment is invalid")
    if not reference_time_utc or not model or not prompt_hash:
        raise ValueError("reference_time_utc, model, and prompt_hash are required")

    searched_json = _canonical_string_list(searched_tickers)
    affected_json = _canonical_string_list(affected_tickers)
    evidence_json = _canonical_json(evidence)
    analyzed_at_utc = datetime.now(timezone.utc).isoformat()

    path = initialize_database(dev=dev)
    with closing(sqlite3.connect(path, timeout=10)) as connection:
        with connection:
            existing = connection.execute(
                """
                SELECT id FROM articles
                WHERE article_url = ?
                  AND model = ?
                  AND prompt_hash = ?
                  AND evidence_json = ?
                  AND importance = ?
                  AND sentiment = ?
                  AND affected_tickers_json = ?
                  AND why_read = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_url, model, prompt_hash, evidence_json, importance,
                 sentiment, affected_json, why_read),
            ).fetchone()
            if existing is not None:
                return SaveResult(row_id=int(existing[0]), inserted=False)

            cursor = connection.execute(
                """
                INSERT INTO articles (
                    article_url, headline, source, published_time, summary,
                    searched_tickers_json, importance, sentiment,
                    affected_tickers_json, why_read, analyzed_at_utc,
                    reference_time_utc, model, prompt_hash, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (article_url, headline, source, published_time, summary,
                 searched_json, importance, sentiment, affected_json, why_read,
                 analyzed_at_utc, reference_time_utc, model, prompt_hash,
                 evidence_json),
            )
            return SaveResult(row_id=int(cursor.lastrowid), inserted=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create/check local history storage without contacting any APIs."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dev", action="store_true", help="Set up the test-history database.")
    mode.add_argument("--live", action="store_true", help="Set up the separate live-history database.")
    args = parser.parse_args()

    try:
        path = initialize_database(dev=args.dev)
        count = count_articles(dev=args.dev)
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise SystemExit(f"DATABASE SETUP FAILED: {exc}") from None

    print("SQLITE SETUP COMPLETE")
    print("Mode:", "DEVELOPMENT - test history only" if args.dev else "LIVE - separate history")
    print("Database:", path)
    print("Table: articles")
    print("Saved analyses:", count)
    print("No API calls were made. No article rows were inserted or deleted.")
    print("This command only creates/checks the table; it does not run the agent.")


if __name__ == "__main__":
    main()

