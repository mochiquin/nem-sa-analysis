"""Thin PostgreSQL helpers: idempotent upserts and an ingest log."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import psycopg

KEY = ("settlementdate", "regionid", "intervention")


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def upsert(conn: psycopg.Connection, table: str, df: pd.DataFrame, key: Sequence[str] = KEY) -> int:
    """Insert rows; on key conflict, overwrite with the newer values."""
    if df.empty:
        return 0
    cols = list(df.columns)
    updates = [c for c in cols if c not in key]
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) "
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET "
        + ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
        + ", loaded_at = now()"
    )
    records = [
        tuple(
            None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v)
            for v in row
        )
        for row in df.itertuples(index=False, name=None)
    ]
    with conn.cursor() as cur:
        cur.executemany(sql, records)
    return len(records)


def already_loaded(conn: psycopg.Connection, filename: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM ingest_log WHERE filename = %s", (filename,))
        return cur.fetchone() is not None


def mark_loaded(conn: psycopg.Connection, filename: str, tables: list[str], rows: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingest_log (filename, tables, row_count) VALUES (%s, %s, %s) "
            "ON CONFLICT (filename) DO NOTHING",
            (filename, tables, rows),
        )
