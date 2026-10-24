"""Bulk-load historical data with NEMOSIS (UNSW-CEEM).

NEMOSIS handles the monthly MMSDM archives, which would be slow to rebuild
by hand. Day-to-day updates use our own NEMweb parser (see ``ingest``).
"""

from __future__ import annotations

import logging
from datetime import datetime

from nemosis import dynamic_data_compiler

from nemsa import db
from nemsa.config import Settings
from nemsa.nemweb.clean import clean_price, clean_region

log = logging.getLogger(__name__)

NEMOSIS_TS = "%Y/%m/%d %H:%M:%S"

TABLES = {
    "DISPATCHPRICE": (
        "dispatch_price",
        clean_price,
        ["SETTLEMENTDATE", "REGIONID", "INTERVENTION", "RRP"],
    ),
    "DISPATCHREGIONSUM": (
        "dispatch_region",
        clean_region,
        [
            "SETTLEMENTDATE",
            "REGIONID",
            "INTERVENTION",
            "TOTALDEMAND",
            "AVAILABLEGENERATION",
            "NETINTERCHANGE",
        ],
    ),
}


def backfill(settings: Settings, start: datetime, end: datetime) -> dict[str, int]:
    """Download [start, end) for the configured region and upsert into Postgres."""
    cache = settings.cache_dir / "nemosis"
    cache.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, int] = {}

    with db.connect(settings.database_url) as conn:
        for aemo_table, (pg_table, cleaner, cols) in TABLES.items():
            log.info("NEMOSIS %s %s -> %s", aemo_table, start.date(), end.date())
            raw = dynamic_data_compiler(
                start.strftime(NEMOSIS_TS),
                end.strftime(NEMOSIS_TS),
                aemo_table,
                str(cache),
                select_columns=cols,
                filter_cols=["REGIONID"],
                filter_values=([settings.region],),
                fformat="parquet",
            )
            df = cleaner(raw, region=settings.region, source="nemosis")
            loaded[pg_table] = db.upsert(conn, pg_table, df)
            conn.commit()
            log.info("  %s rows into %s", loaded[pg_table], pg_table)
    return loaded
