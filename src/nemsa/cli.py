"""Command line entry point: ``nemsa backfill | ingest | gaps``."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

import pandas as pd

from nemsa import db
from nemsa.config import get_settings


def _date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nemsa")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_back = sub.add_parser("backfill", help="load history with NEMOSIS")
    p_back.add_argument("--start", type=_date, required=True, help="YYYY-MM-DD")
    p_back.add_argument("--end", type=_date, required=True, help="YYYY-MM-DD (exclusive)")

    p_ing = sub.add_parser("ingest", help="load new NEMweb DispatchIS files")
    p_ing.add_argument("--limit", type=int, default=None, help="only the newest N files")

    sub.add_parser("gaps", help="report missing 5-minute intervals in dispatch_price")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()

    if args.cmd == "backfill":
        from nemsa.backfill import backfill

        print(backfill(settings, args.start, args.end))
    elif args.cmd == "ingest":
        from nemsa.ingest import ingest_current

        print(f"{ingest_current(settings, args.limit)} rows loaded")
    elif args.cmd == "gaps":
        from nemsa.nemweb.clean import find_gaps

        with db.connect(settings.database_url) as conn:
            df = pd.read_sql(
                "SELECT settlementdate, regionid, intervention FROM dispatch_price", conn
            )
        gaps = find_gaps(df)
        print("no gaps" if gaps.empty else gaps.to_string(index=False))


if __name__ == "__main__":
    main()
