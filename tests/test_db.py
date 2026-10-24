"""Integration tests against a real Postgres. Skipped when no database is reachable.

Locally: ``docker compose up -d`` first. In CI a Postgres service is provided.
"""

import os
from pathlib import Path

import psycopg
import pytest

from nemsa import db
from nemsa.nemweb.clean import clean_price, clean_region
from nemsa.nemweb.parse import read_report

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "PUBLIC_DISPATCHIS_SAMPLE.CSV"
URL = os.getenv("DATABASE_URL", "postgresql://nemsa:nemsa@localhost:5432/nemsa")


@pytest.fixture()
def conn():
    try:
        c = psycopg.connect(URL, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("no Postgres available")
    with c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS dispatch_price, dispatch_region, ingest_log CASCADE")
        cur.execute((ROOT / "db" / "schema.sql").read_text())
    c.commit()
    yield c
    c.close()


def _count(conn, table):
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def test_upsert_is_idempotent(conn):
    tables = read_report(FIXTURE)
    price = clean_price(tables["DISPATCH_PRICE"], region="SA1", source="nemweb")
    db.upsert(conn, "dispatch_price", price)
    db.upsert(conn, "dispatch_price", price)
    conn.commit()
    assert _count(conn, "dispatch_price") == 2  # SA1 x two intervention runs


def test_upsert_overwrites_revised_values(conn):
    price = clean_price(read_report(FIXTURE)["DISPATCH_PRICE"], region="SA1", source="nemweb")
    db.upsert(conn, "dispatch_price", price)
    db.upsert(conn, "dispatch_price", price.assign(rrp=123.45))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT rrp FROM dispatch_price")
        assert [float(r[0]) for r in cur.fetchall()] == [123.45]


def test_view_and_generated_interval_start(conn):
    tables = read_report(FIXTURE)
    db.upsert(conn, "dispatch_price", clean_price(tables["DISPATCH_PRICE"], "SA1", "nemweb"))
    db.upsert(conn, "dispatch_region", clean_region(tables["DISPATCH_REGIONSUM"], "SA1", "nemweb"))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT interval_start::text, rrp FROM v_price")
        rows = cur.fetchall()
    assert rows == [("2026-10-24 14:05:00", pytest.approx(-41.5))]
    assert _count(conn, "dispatch_region") == 2


def test_ingest_log(conn):
    assert not db.already_loaded(conn, "f.zip")
    db.mark_loaded(conn, "f.zip", ["DISPATCH_PRICE"], 2)
    db.mark_loaded(conn, "f.zip", ["DISPATCH_PRICE"], 2)
    conn.commit()
    assert db.already_loaded(conn, "f.zip")
