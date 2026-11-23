"""Write trimmed test fixtures from the live sources. Run by hand, never by the tests.

Usage, from the repo root:
    python -I -X utf8 .agents/skills/tw-equity-screener/scripts/tests/make_fixtures.py

Responses go through the screener's raw cache, so a rerun fetches only what
is missing. Each fixture keeps its payload's structure (HTML section rows,
JSON keys, table headers) and only the rows of FIXTURE_CODES, plus the first
data row after each ISIN section header.
"""

import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cache import Fetcher  # noqa: E402

FIXTURES = HERE / "fixtures"
FIXTURE_CODES = ["1101", "1303", "1409", "2330", "2801", "3481", "3673", "0050", "00400A", "00625K", "00411A",
                 "6488", "1260"]
ISIN_PAGE = "https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"


def isin_code(row):
    """The security code in an ISIN data row's first cell, or '' for other rows."""
    first = re.search(r"(?is)<td[^>]*>(.*?)</td>", row)
    text = re.sub(r"<[^>]+>", "", first.group(1)).replace("　", " ").strip() if first else ""
    return text.split(" ", 1)[0]


def trim_isin(html):
    """Keep the page shell, the column header, every section row with its first data row, and FIXTURE_CODES."""
    rows = list(re.finditer(r"(?is)<tr.*?</tr>", html))
    kept, take_next = [], False
    for m in rows:
        row = m.group(0)
        if "有價證券代號" in row:
            kept.append(row)
        elif "colspan" in row.lower():
            kept.append(row)
            take_next = True
        elif take_next or isin_code(row) in FIXTURE_CODES:
            kept.append(row)
            take_next = False
    return html[:rows[0].start()] + "".join(kept) + html[rows[-1].end():]


def isin_fixtures(fetcher, capture_day):
    for mode in (2, 4, 5):
        html = fetcher.get(f"isin{mode}", capture_day, ISIN_PAGE.format(mode=mode), encoding="cp950",
                           validate=lambda t: "<table" in t)
        trimmed = trim_isin(html)
        (FIXTURES / f"isin_{mode}.html").write_bytes(trimmed.encode("cp950"))
        print(f"isin_{mode}.html: {len(re.findall(r'(?is)<tr', trimmed))} rows from {len(html):,} chars")


def main():
    FIXTURES.mkdir(exist_ok=True)
    fetcher = Fetcher()
    isin_fixtures(fetcher, date.today().isoformat())
    print(f"network calls: {fetcher.network_calls}")


if __name__ == "__main__":
    main()
