"""MOPS monthly revenue and quarterly income, parsed from the public HTML tables.

Revenue comes from the per-board monthly files (thousand NT$), income from the
t163sb04 summary (year-to-date, thousand NT$). Both pages print the code column
as 公司<br>代號, so the "has data" check strips tags before it looks for 公司代號.
"""

import html
import re
from collections import defaultdict
from datetime import date, timedelta

from exchange import num

REVENUE_URL = "https://mopsov.twse.com.tw/nas/t21/{board}/t21sc03_{roc}_{month}_{kind}.html"
REVENUE_FILES = [("sii", 0), ("sii", 1), ("otc", 0), ("otc", 1), ("rotc", 0)]
INCOME_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"
INCOME_BOARDS = ("sii", "otc")
REVENUE_REFRESH_DAY = 25           # the latest month is re-fetched until this day of the following month
INCOME_REFRESH_DAYS = 30           # the latest due season is re-fetched until this many days after its deadline
DEADLINES = {1: "05-15", 2: "08-14", 3: "11-14"}
GENERAL_FIELDS = (("revenue", "營業收入"), ("op_income", "營業利益（損失）"), ("pretax", "稅前淨利（淨損）"),
                  ("net_income", "本期淨利（淨損）"), ("net_parent", "淨利（淨損）歸屬於母公司業主"),
                  ("eps", "基本每股盈餘（元）"))
INCOME_KEYS = tuple(key for key, _ in GENERAL_FIELDS)

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<td[^>]*>(.*?)</td>")
TH_RE = re.compile(r"(?is)<th[^>]*>(.*?)</th>")
TABLE_RE = re.compile(r"(?is)<table.*?</table>")
INDUSTRY_RE = re.compile(r"產業別：([^<]+)")
CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")


def _text(cell):
    return html.unescape(TAG_RE.sub("", cell)).strip()


def has_code_header(text):
    """The page carries the 公司代號 column, however its header is broken across tags."""
    return "公司代號" in TAG_RE.sub("", text)


def parse_revenue(page):
    """Company rows of one monthly revenue file; revenue is in thousand NT$."""
    out, industry = [], None
    for row in ROW_RE.findall(page):
        m = INDUSTRY_RE.search(row)
        if m:
            industry = m.group(1).strip()
            continue
        cells = [_text(c) for c in CELL_RE.findall(row)]
        if len(cells) != 11 or not CODE_RE.match(cells[0]):
            continue                    # header rows, 合計 rows, and layout cells
        out.append({"code": cells[0], "name": cells[1].rstrip("*").strip(), "industry": industry,
                    "revenue": num(cells[2]), "revenue_last_year": num(cells[4]), "yoy_pct": num(cells[6]),
                    "note": None if cells[10] in ("", "-") else cells[10]})
    return out


def revenue_rows(months):
    """Per code, FinMind-shaped rows {revenue_year, revenue_month, revenue}, oldest first."""
    out = defaultdict(list)
    for (year, month) in sorted(months):
        seen = set()
        for r in months[(year, month)]:
            if r["revenue"] is None or r["code"] in seen:
                continue
            seen.add(r["code"])
            out[r["code"]].append({"revenue_year": year, "revenue_month": month, "revenue": r["revenue"]})
    return dict(out)


def deadline(year, season):
    """The statutory filing deadline of a season's report, as an ISO date."""
    return f"{year + 1}-03-31" if season == 4 else f"{year}-{DEADLINES[season]}"


def due_seasons(asof, n=9):
    """The n latest seasons whose deadline is on or before `asof`, oldest first."""
    out, year, season = [], int(asof[:4]), 4
    while len(out) < n:
        if deadline(year, season) <= asof:
            out.append((year, season))
        year, season = (year, season - 1) if season > 1 else (year - 1, 4)
    return out[::-1]


def parse_income(page):
    """({code: general-template YTD fields}, codes on every other template)."""
    general, other = {}, set()
    for table in TABLE_RE.findall(page):
        head = [re.sub(r"\s+", "", _text(h)) for h in TH_RE.findall(table)]
        if "公司代號" not in head:
            continue
        code_col = head.index("公司代號")
        cols = ({key: head.index(name) for key, name in GENERAL_FIELDS}
                if "營業收入" in head and "營業利益（損失）" in head else None)
        for row in ROW_RE.findall(table):
            cells = [_text(c) for c in CELL_RE.findall(row)]
            if not cells:
                continue                # header rows hold th cells only
            if len(cells) != len(head):
                raise ValueError(f"income row {cells[:2]} has {len(cells)} cells under {len(head)} headers")
            if cols:
                general[cells[code_col]] = {key: num(cells[i]) for key, i in cols.items()}
            else:
                other.add(cells[code_col])
    return general, other


def _minus(a, b):
    return None if a is None or b is None else a - b


def standalone(ytd):
    """Standalone quarters from YTD figures: Q1 as filed, Qs = YTD(s) − YTD(s−1) of the same year."""
    out = defaultdict(list)
    for (year, season) in sorted(ytd):
        for code, row in ytd[(year, season)].items():
            if season == 1:
                q = {k: row.get(k) for k in INCOME_KEYS}
            else:
                prev = ytd.get((year, season - 1), {}).get(code)
                if prev is None:
                    continue
                q = {k: _minus(row.get(k), prev.get(k)) for k in INCOME_KEYS}
            out[code].append(dict(q, year=year, season=season))
    return dict(out)


def revenue_url(board, kind, year, month):
    """The monthly revenue file; the month is not zero-padded."""
    return REVENUE_URL.format(board=board, roc=year - 1911, month=month, kind=kind)


def income_form(board, year, season):
    return {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y", "TYPEK": board,
            "year": str(year - 1911), "season": f"{season:02d}"}


def fetch_revenue(fetcher, year, month, asof):
    """Every board's revenue rows for one month. A month is re-fetched until the 25th of the next month."""
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    refresh = asof <= f"{ny:04d}-{nm:02d}-{REVENUE_REFRESH_DAY}"
    rows = []
    for board, kind in REVENUE_FILES:
        rows.extend(parse_revenue(fetcher.get(f"rev_{board}_{kind}", f"{year:04d}-{month:02d}",
                                              revenue_url(board, kind, year, month), encoding="cp950",
                                              validate=has_code_header, refresh=refresh)))
    return rows


def fetch_income(fetcher, year, season, asof, boards=INCOME_BOARDS):
    """General-template YTD income by code and the codes on other templates, merged over `boards`.
    A season is re-fetched until 30 days after its deadline, to pick up late filers."""
    until = date.fromisoformat(deadline(year, season)) + timedelta(days=INCOME_REFRESH_DAYS)
    refresh = asof <= until.isoformat()
    general, other = {}, set()
    for board in boards:
        g, o = parse_income(fetcher.get(f"inc_{board}", f"{year:04d}-Q{season}", INCOME_URL, encoding="utf-8",
                                        validate=has_code_header, form=income_form(board, year, season),
                                        refresh=refresh))
        general.update(g)
        other |= o
    return general, other
