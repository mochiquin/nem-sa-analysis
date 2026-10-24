"""Daily incremental load from NEMweb 'Current' DispatchIS reports.

Each DispatchIS file covers one 5-minute interval and contains several tables;
we take DISPATCH_PRICE and DISPATCH_REGIONSUM. Files already recorded in
``ingest_log`` are skipped, so the job can be re-run safely.
"""

from __future__ import annotations

import logging

from nemsa import db
from nemsa.config import Settings
from nemsa.nemweb import fetch
from nemsa.nemweb.clean import clean_price, clean_region
from nemsa.nemweb.parse import read_report

log = logging.getLogger(__name__)

TABLE_MAP = {
    "DISPATCH_PRICE": ("dispatch_price", clean_price),
    "DISPATCH_REGIONSUM": ("dispatch_region", clean_region),
}


def ingest_current(settings: Settings, limit: int | None = None) -> int:
    """Fetch and load any DispatchIS files not yet in the database."""
    dest = settings.cache_dir / "dispatchis"
    names = fetch.list_files()
    if limit:
        names = names[-limit:]

    total = 0
    with db.connect(settings.database_url) as conn:
        for name in names:
            if db.already_loaded(conn, name):
                continue
            path = fetch.download(name, dest)
            tables = read_report(path)

            rows = 0
            used = []
            for aemo_name, (pg_table, cleaner) in TABLE_MAP.items():
                if aemo_name not in tables:
                    log.warning("%s: no %s table", name, aemo_name)
                    continue
                df = cleaner(tables[aemo_name], region=settings.region, source="nemweb")
                rows += db.upsert(conn, pg_table, df)
                used.append(aemo_name)

            db.mark_loaded(conn, name, used, rows)
            conn.commit()  # one transaction per file
            total += rows
    log.info("loaded %s rows from NEMweb", total)
    return total
