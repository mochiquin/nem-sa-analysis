import zipfile
from pathlib import Path

import pytest

from nemsa.nemweb.parse import parse_mms_csv, read_report

FIXTURE = Path(__file__).parent / "fixtures" / "PUBLIC_DISPATCHIS_SAMPLE.CSV"


def test_splits_file_into_tables():
    tables = read_report(FIXTURE)
    assert set(tables) == {"DISPATCH_CASE_SOLUTION", "DISPATCH_PRICE", "DISPATCH_REGIONSUM"}
    assert len(tables["DISPATCH_PRICE"]) == 4
    assert len(tables["DISPATCH_REGIONSUM"]) == 3


def test_keeps_header_columns_and_version():
    price = read_report(FIXTURE)["DISPATCH_PRICE"]
    assert list(price.columns[:4]) == ["SETTLEMENTDATE", "RUNNO", "REGIONID", "DISPATCHINTERVAL"]
    assert price.attrs["version"] == "5"


def test_reads_zip(tmp_path):
    zpath = tmp_path / "PUBLIC_DISPATCHIS_SAMPLE.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.write(FIXTURE, FIXTURE.name)
    assert "DISPATCH_PRICE" in read_report(zpath)


def test_pads_missing_trailing_fields():
    text = "I,X,Y,1,A,B,C\nD,X,Y,1,1,2\n"
    df = parse_mms_csv(text)["X_Y"]
    assert df.iloc[0].tolist() == ["1", "2", ""]


def test_rejects_data_before_header():
    with pytest.raises(ValueError, match="before its header"):
        parse_mms_csv("D,X,Y,1,1,2\n")


def test_rejects_too_many_fields():
    with pytest.raises(ValueError, match="expected 2"):
        parse_mms_csv("I,X,Y,1,A,B\nD,X,Y,1,1,2,3\n")
