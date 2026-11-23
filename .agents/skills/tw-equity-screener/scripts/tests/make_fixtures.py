"""Write trimmed test fixtures from the live sources. Run by hand, never by the tests.

Usage, from the repo root:
    python -I -X utf8 .agents/skills/tw-equity-screener/scripts/tests/make_fixtures.py

Responses go through the screener's raw cache, so a rerun fetches only what
is missing. Each fixture keeps its payload's structure (HTML section rows,
JSON keys, table headers) and only the rows of FIXTURE_CODES, plus the first
data row after each ISIN section header.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cache import Fetcher  # noqa: E402
from exchange import (TAIEX_NAME, TPEX_INSTI, TPEX_QUOTES, TWSE_QFIIS, TWSE_QUOTES, TWSE_T86,  # noqa: E402
                      tpex_ok, twse_ok, url_for)
from mops import INCOME_URL, has_code_header, income_form, revenue_url  # noqa: E402

FIXTURES = HERE / "fixtures"
FIXTURE_CODES = ["1101", "1303", "1409", "2330", "2801", "3481", "3673", "0050", "00400A", "00625K", "00411A",
                 "6488", "1260"]
ISIN_PAGE = "https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"

# (fixture file, cache source, ISO date, URL template, validator): the same cache entries exchange.py reads.
EXCHANGE = [
    ("twse_mi_index_20261120.json", "twse_quotes", "2026-11-20", TWSE_QUOTES, twse_ok),
    ("twse_t86_20261120.json", "twse_t86", "2026-11-20", TWSE_T86, twse_ok),
    ("twse_qfiis_20261120.json", "twse_qfiis", "2026-11-20", TWSE_QFIIS, twse_ok),
    ("tpex_quotes_20261120.json", "tpex_quotes", "2026-11-20", TPEX_QUOTES, tpex_ok),
    ("tpex_insti_20261119.json", "tpex_insti", "2026-11-19", TPEX_INSTI, tpex_ok),
]


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


def keep_row(row):
    first = str(row[0]).strip() if row else ""
    return first in FIXTURE_CODES or first == TAIEX_NAME


def trim_json(j):
    """Keep every key and table header; keep only the data rows of FIXTURE_CODES and the TAIEX row."""
    out = dict(j)
    if isinstance(out.get("tables"), list):
        out["tables"] = [dict(t, data=[r for r in t["data"] if keep_row(r)])
                         if isinstance(t, dict) and isinstance(t.get("data"), list) else t for t in out["tables"]]
    if isinstance(out.get("data"), list):
        out["data"] = [r for r in out["data"] if keep_row(r)]
    return out


def exchange_fixtures(fetcher):
    for name, source, day, template, validate in EXCHANGE:
        j = trim_json(json.loads(fetcher.get(source, day, url_for(template, day), encoding="utf-8", validate=validate)))
        (FIXTURES / name).write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rows = sum(len(t.get("data", [])) for t in j.get("tables", []) if isinstance(t, dict)) + len(j.get("data", []))
        print(f"{name}: {rows} rows kept")


REVENUE_INDUSTRIES = ("水泥工業", "塑膠工業")
INCOME_CODES = ("1101", "2801", "1409")
TAGS = re.compile(r"<[^>]+>")


def trim_revenue(html):
    """Keep the page shell, the grand-total table, and the REVENUE_INDUSTRIES blocks."""
    starts = [m.start() for m in re.finditer(r"<table border=0 width=100%><tr><th class=tt align=left >產業別：", html)]
    total = html.rfind("<table", 0, html.rfind("合計"))
    blocks = [html[s:e] for s, e in zip(starts, starts[1:] + [total])]
    keep = [b for b in blocks if any(f"產業別：{name}</th>" in b[:300] for name in REVENUE_INDUSTRIES)]
    return html[:starts[0]] + "".join(keep) + html[total:]


def trim_income(html):
    """Keep every table and header row; keep only the data rows of INCOME_CODES."""
    def keep(m):
        first = re.search(r"(?is)<td[^>]*>(.*?)</td>", m.group(0))
        return m.group(0) if first and TAGS.sub("", first.group(1)).strip() in INCOME_CODES else ""

    return re.sub(r"(?is)<tr class='(?:even|odd)'>.*?</tr>", keep, html)


def mops_fixtures(fetcher):
    rev = fetcher.get("rev_sii_0", "2026-10", revenue_url("sii", 0, 2026, 10), encoding="cp950",
                      validate=has_code_header)
    (FIXTURES / "mops_sii_115_10_0.html").write_bytes(trim_revenue(rev).encode("cp950"))
    inc = fetcher.get("inc_sii", "2026-Q3", INCOME_URL, encoding="utf-8", validate=has_code_header,
                      form=income_form("sii", 2026, 3))
    (FIXTURES / "mops_t163sb04_sii_115_03.html").write_text(trim_income(inc), encoding="utf-8")
    for name in ("mops_sii_115_10_0.html", "mops_t163sb04_sii_115_03.html"):
        print(f"{name}: {(FIXTURES / name).stat().st_size:,} bytes")


def main():
    FIXTURES.mkdir(exist_ok=True)
    fetcher = Fetcher()
    isin_fixtures(fetcher, date.today().isoformat())
    exchange_fixtures(fetcher)
    mops_fixtures(fetcher)
    print(f"network calls: {fetcher.network_calls}")


if __name__ == "__main__":
    main()
