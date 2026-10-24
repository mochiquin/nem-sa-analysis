from pathlib import Path

import pandas as pd

from nemsa.nemweb.clean import clean_price, clean_region, find_gaps
from nemsa.nemweb.parse import read_report

FIXTURE = Path(__file__).parent / "fixtures" / "PUBLIC_DISPATCHIS_SAMPLE.CSV"


def _tables():
    return read_report(FIXTURE)


def test_price_filters_region_and_types_values():
    df = clean_price(_tables()["DISPATCH_PRICE"], region="SA1", source="nemweb")
    assert set(df["regionid"]) == {"SA1"}
    assert df["settlementdate"].iloc[0] == pd.Timestamp("2026-10-24 14:10:00")
    assert df["rrp"].dtype.kind == "f"


def test_negative_prices_are_kept():
    df = clean_price(_tables()["DISPATCH_PRICE"], region="SA1", source="nemweb")
    assert (df["rrp"] < 0).all()


def test_both_intervention_runs_are_kept():
    df = clean_price(_tables()["DISPATCH_PRICE"], region="SA1", source="nemweb")
    assert sorted(df["intervention"].tolist()) == [0, 1]


def test_duplicate_rows_keep_latest_revision():
    raw = _tables()["DISPATCH_PRICE"]
    newer = raw[raw["REGIONID"] == "NSW1"].copy()
    newer["RRP"] = "99.99"
    newer["LASTCHANGED"] = '"2026/10/24 14:06:00"'
    df = clean_price(pd.concat([raw, newer]), region="NSW1", source="nemweb")
    assert len(df) == 1
    assert df["rrp"].iloc[0] == 99.99


def test_region_summary():
    df = clean_region(_tables()["DISPATCH_REGIONSUM"], region="SA1", source="nemweb")
    row = df[df["intervention"] == 0].iloc[0]
    assert row["totaldemand"] == 1188.6
    assert row["netinterchange"] == 513.7


def test_find_gaps_reports_missing_run():
    ts = pd.date_range("2026-10-24 00:05", periods=12, freq="5min").delete([4, 5, 6])
    df = pd.DataFrame({"settlementdate": ts, "regionid": "SA1", "intervention": 0})
    gaps = find_gaps(df)
    assert len(gaps) == 1
    assert gaps.iloc[0]["missing"] == 3
    assert gaps.iloc[0]["gap_start"] == pd.Timestamp("2026-10-24 00:25")
