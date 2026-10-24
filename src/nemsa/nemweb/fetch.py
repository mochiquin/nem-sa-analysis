"""Download new files from a NEMweb 'Current' directory.

NEMweb serves plain HTML directory listings; each file is a zipped CSV whose
name contains its timestamp, e.g.
PUBLIC_DISPATCHIS_202610241405_0000000412345678.zip
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests

from nemsa.config import NEMWEB_BASE_URL

# Paths are case-sensitive since the April 2026 HTTPS migration.
DISPATCHIS_DIR = "Current/DispatchIS_Reports/"

_LINK_RE = re.compile(r'href="([^"]+\.zip)"', re.IGNORECASE)
_session = requests.Session()
_session.headers["User-Agent"] = "nemsa/0.1 (portfolio project; github.com/mochiquin)"


def list_files(directory: str = DISPATCHIS_DIR) -> list[str]:
    """Return the file names in a NEMweb directory, oldest first."""
    url = f"{NEMWEB_BASE_URL}/{directory}"
    resp = _session.get(url, timeout=30)
    resp.raise_for_status()
    names = {Path(href).name for href in _LINK_RE.findall(resp.text)}
    return sorted(names)  # names embed a timestamp, so lexical order = time order


def download(name: str, dest_dir: Path, directory: str = DISPATCHIS_DIR, retries: int = 3) -> Path:
    """Download one file into dest_dir, skipping it if already cached."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / name
    if target.exists() and target.stat().st_size > 0:
        return target

    url = f"{NEMWEB_BASE_URL}/{directory}{name}"
    for attempt in range(1, retries + 1):
        try:
            resp = _session.get(url, timeout=60)
            resp.raise_for_status()
            tmp = target.with_suffix(".part")
            tmp.write_bytes(resp.content)
            tmp.rename(target)
            return target
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")
