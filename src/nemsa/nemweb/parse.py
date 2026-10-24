"""Parse AEMO's multi-table CSV format (the MMS "C/I/D" file layout).

A single NEMweb CSV holds several tables. The first field of each row says
what the row is:

    C  comment / file header / end-of-report marker
    I  table header:  I, <report>, <subtype>, <version>, <col1>, <col2>, ...
    D  data row:      D, <report>, <subtype>, <version>, <val1>, <val2>, ...

Each I row starts a new table; the D rows that follow belong to it until the
next I row. A table is identified by (report, subtype, version), e.g.
("DISPATCH", "PRICE", "5"), which we name "DISPATCH_PRICE".
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

TableKey = tuple[str, str, str]


def _rows_from_text(text: str) -> Iterable[list[str]]:
    return csv.reader(io.StringIO(text))


def parse_mms_csv(text: str) -> dict[str, pd.DataFrame]:
    """Split one MMS-format CSV into a DataFrame per table.

    Returns a dict keyed by "<REPORT>_<SUBTYPE>" (for example "DISPATCH_PRICE").
    All values are kept as strings here; typing happens in ``clean``.
    """
    headers: dict[TableKey, list[str]] = {}
    rows: dict[TableKey, list[list[str]]] = {}
    current: TableKey | None = None

    for line_no, row in enumerate(_rows_from_text(text), start=1):
        if not row:
            continue
        kind = row[0].strip().upper()

        if kind == "C":
            continue

        if kind == "I":
            if len(row) < 5:
                raise ValueError(f"line {line_no}: header row has no columns")
            current = (row[1].upper(), row[2].upper(), row[3])
            cols = [c.strip().upper() for c in row[4:]]
            if current in headers and headers[current] != cols:
                raise ValueError(f"line {line_no}: table {current} redeclared with new columns")
            headers[current] = cols
            rows.setdefault(current, [])
            continue

        if kind == "D":
            key = (row[1].upper(), row[2].upper(), row[3])
            if key not in headers:
                raise ValueError(f"line {line_no}: data row for {key} before its header")
            values = row[4:]
            expected = len(headers[key])
            # AEMO sometimes omits trailing empty fields; pad rather than fail.
            if len(values) < expected:
                values = values + [""] * (expected - len(values))
            elif len(values) > expected:
                raise ValueError(
                    f"line {line_no}: {key} has {len(values)} values, expected {expected}"
                )
            rows[key].append(values)
            continue

        raise ValueError(f"line {line_no}: unknown row type {row[0]!r}")

    tables: dict[str, pd.DataFrame] = {}
    for key, cols in headers.items():
        name = f"{key[0]}_{key[1]}"
        df = pd.DataFrame(rows[key], columns=cols)
        df.attrs["version"] = key[2]
        tables[name] = df
    return tables


def read_report(path: str | Path) -> dict[str, pd.DataFrame]:
    """Parse a NEMweb file on disk. Accepts a .zip (one CSV inside) or a .csv."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if len(csv_names) != 1:
                raise ValueError(f"{path.name}: expected one CSV inside, found {csv_names}")
            text = zf.read(csv_names[0]).decode("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    return parse_mms_csv(text)
