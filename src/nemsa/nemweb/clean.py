"""Turn raw AEMO tables into typed, de-duplicated frames ready for the database.

Works on frames from our own parser (all strings) and from NEMOSIS
(already partly typed), so both ingest paths share the same rules.
"""

from __future__ import annotations

import pandas as pd

AEMO_TS_FORMAT = "%Y/%m/%d %H:%M:%S"
KEY = ["settlementdate", "regionid", "intervention"]

PRICE_COLS = {"SETTLEMENTDATE", "REGIONID", "INTERVENTION", "RRP"}
REGION_COLS = {
    "SETTLEMENTDATE",
    "REGIONID",
    "INTERVENTION",
    "TOTALDEMAND",
    "AVAILABLEGENERATION",
    "NETINTERCHANGE",
}


def _require(df: pd.DataFrame, cols: set[str], table: str) -> None:
    missing = cols - set(df.columns)
    if missing:
        raise KeyError(f"{table}: missing columns {sorted(missing)}")


def _to_timestamp(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.tz_localize(None) if s.dt.tz is not None else s
    return pd.to_datetime(s.str.strip().str.strip('"'), format=AEMO_TS_FORMAT)


def _dedupe(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Keep one row per key. If LASTCHANGED is present, the latest revision wins."""
    if "LASTCHANGED" in raw.columns:
        df = df.assign(_lc=_to_timestamp(raw["LASTCHANGED"]).values)
        df = df.sort_values("_lc").drop(columns="_lc")
    return df.drop_duplicates(subset=KEY, keep="last").sort_values(KEY).reset_index(drop=True)


def clean_price(raw: pd.DataFrame, region: str | None, source: str) -> pd.DataFrame:
    """DISPATCH_PRICE / NEMOSIS DISPATCHPRICE -> dispatch_price rows."""
    _require(raw, PRICE_COLS, "DISPATCH_PRICE")
    if region:
        raw = raw[raw["REGIONID"].astype(str).str.strip() == region]
    df = pd.DataFrame(
        {
            "settlementdate": _to_timestamp(raw["SETTLEMENTDATE"]),
            "regionid": raw["REGIONID"].astype(str).str.strip(),
            "intervention": pd.to_numeric(raw["INTERVENTION"]).astype("int16"),
            # Negative prices and the market price cap are REAL market outcomes,
            # not errors. Do not clip or drop them.
            "rrp": pd.to_numeric(raw["RRP"]),
            "source": source,
        }
    )
    return _dedupe(df, raw)


def clean_region(raw: pd.DataFrame, region: str | None, source: str) -> pd.DataFrame:
    """DISPATCH_REGIONSUM / NEMOSIS DISPATCHREGIONSUM -> dispatch_region rows."""
    _require(raw, REGION_COLS, "DISPATCH_REGIONSUM")
    if region:
        raw = raw[raw["REGIONID"].astype(str).str.strip() == region]
    df = pd.DataFrame(
        {
            "settlementdate": _to_timestamp(raw["SETTLEMENTDATE"]),
            "regionid": raw["REGIONID"].astype(str).str.strip(),
            "intervention": pd.to_numeric(raw["INTERVENTION"]).astype("int16"),
            "totaldemand": pd.to_numeric(raw["TOTALDEMAND"], errors="coerce"),
            "availablegeneration": pd.to_numeric(raw["AVAILABLEGENERATION"], errors="coerce"),
            "netinterchange": pd.to_numeric(raw["NETINTERCHANGE"], errors="coerce"),
            "source": source,
        }
    )
    return _dedupe(df, raw)


def find_gaps(df: pd.DataFrame, freq: str = "5min") -> pd.DataFrame:
    """Report missing intervals per region, as (regionid, gap_start, gap_end, missing).

    Gaps are reported, not filled: whether to interpolate depends on the analysis.
    """
    out = []
    for region, g in df[df["intervention"] == 0].groupby("regionid"):
        ts = g["settlementdate"].sort_values()
        expected = pd.date_range(ts.iloc[0], ts.iloc[-1], freq=freq)
        missing = expected.difference(ts)
        if missing.empty:
            continue
        # Collapse consecutive missing timestamps into ranges.
        step = pd.Timedelta(freq)
        run_id = (missing.to_series().diff() != step).cumsum()
        for _, run in missing.to_series().groupby(run_id):
            out.append((region, run.iloc[0], run.iloc[-1], len(run)))
    return pd.DataFrame(out, columns=["regionid", "gap_start", "gap_end", "missing"])
