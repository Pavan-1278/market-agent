"""Display recent development analyses without changing SQLite or calling APIs.

Save beside market_agent_test.py and run: python view_history.py
This viewer deliberately reads only market_agent_dev.db (synthetic test history).
"""

from contextlib import closing
from pathlib import Path
import sqlite3


LATEST_ROWS = 10


def main() -> None:
    database = Path(__file__).resolve().parent / "market_agent_dev.db"
    if not database.is_file():
        raise SystemExit(
            f"Database not found: {database}\n"
            "Place this script beside your existing development database. "
            "No database was created."
        )

    try:
        # mode=ro disallows writes and does not create a missing database.
        with closing(
            sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        ) as connection:
            connection.row_factory = sqlite3.Row
            total = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            rows = connection.execute(
                """
                SELECT id, headline, importance, sentiment, why_read, analyzed_at_utc
                FROM articles
                ORDER BY id DESC
                LIMIT ?
                """,
                (LATEST_ROWS,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SystemExit(f"HISTORY READ FAILED: {exc}") from None

    print("DEVELOPMENT HISTORY: synthetic test data, not live research.")
    print(f"Database: {database.name}")
    print(f"Saved analyses: {total}")
    print(f"Showing {len(rows)} most recent rows (newest first).")

    for row in rows:
        print("\n" + "=" * 70)
        print(f"Row {row['id']} | {row['importance']}/10 | {row['sentiment']}")
        print("Headline:", row["headline"])
        print("Why Read:", row["why_read"])
        print("Analyzed at (UTC):", row["analyzed_at_utc"])

    print("\nRead-only check complete. No API calls or database writes.")


if __name__ == "__main__":
    main()
