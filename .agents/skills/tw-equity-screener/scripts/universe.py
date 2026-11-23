"""Security master from the official ISIN lists, weekly universe events, and reconciliation.

The master holds every equity (CFI `ES*`) on TWSE (both sections), TPEx, and
the Emerging board. Securities are keyed `{code}@{listing_date}`, because
codes are reused after delistings (research U6).
"""

import re
from collections import Counter
from dataclasses import dataclass

ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
ISIN_MODES = (2, 4, 5)
MARKETS = {
    "上市": ("twse", "main"),
    "上市臺灣創新板": ("twse", "tib"),
    "上櫃": ("tpex", "main"),
    "興櫃": ("emerging", "main"),
}
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
ROW_RE = re.compile(r"(?is)<tr.*?</tr>")
CELL_RE = re.compile(r"(?is)<td[^>]*>(.*?)</td>")
TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Security:
    code: str
    name: str
    isin: str
    listing_date: str
    market: str
    board: str
    industry: str
    cfi: str

    @property
    def key(self):
        return f"{self.code}@{self.listing_date}"


def parse_isin(html):
    """Equity rows of one ISIN page. KY issuers (non-TW ISINs) and the 創新板 section are kept."""
    out = []
    for row in ROW_RE.findall(html):
        cells = [TAG_RE.sub("", c).replace("　", " ").strip() for c in CELL_RE.findall(row)]
        if len(cells) < 6 or not ISIN_RE.match(cells[1]) or not cells[5].startswith("ES"):
            continue
        if cells[3] not in MARKETS:
            raise ValueError(f"unknown ISIN market {cells[3]!r} for {cells[0]!r}")
        code, _, name = cells[0].partition(" ")
        market, board = MARKETS[cells[3]]
        out.append(Security(code=code, name=name.strip(), isin=cells[1], listing_date=cells[2].replace("/", "-"),
                            market=market, board=board, industry=cells[4], cfi=cells[5]))
    return out


def load_master(fetcher, asof):
    """All three ISIN lists for `asof`, fetched through the raw cache."""
    master = []
    for mode in ISIN_MODES:
        html = fetcher.get(f"isin{mode}", asof, ISIN_URL.format(mode=mode), encoding="cp950",
                           validate=lambda t: "<table" in t)
        master.extend(parse_isin(html))
    return master


def events(prev, cur, delisted=None):
    """Week-over-week universe events. A code that changed market is one transfer, not an exit plus a listing."""
    out = {"new": [], "exits": [], "transfers": [], "renames": [], "code_reuse": []}
    if prev is None:
        return out
    prev_by_key = {s.key: s for s in prev}
    cur_by_key = {s.key: s for s in cur}
    prev_market = {s.code: s.market for s in prev}
    cur_market = {s.code: s.market for s in cur}
    moved = sorted(c for c in prev_market.keys() & cur_market.keys() if prev_market[c] != cur_market[c])
    out["transfers"] = [{"code": c, "from": prev_market[c], "to": cur_market[c]} for c in moved]
    out["new"] = sorted(k for k, s in cur_by_key.items() if k not in prev_by_key and s.code not in moved)
    out["exits"] = sorted(k for k, s in prev_by_key.items() if k not in cur_by_key and s.code not in moved)
    out["renames"] = [{"key": k, "from": prev_by_key[k].name, "to": s.name}
                      for k, s in sorted(cur_by_key.items()) if k in prev_by_key and prev_by_key[k].name != s.name]
    delisted = delisted or {}
    out["code_reuse"] = [k for k in out["new"]
                         if delisted.get(cur_by_key[k].code, "9999-12-31") < cur_by_key[k].listing_date]
    return out


def reconcile(master, quoted, finmind_info):
    """Informational cross-checks of the master against the quote tables and FinMind TaiwanStockInfo."""
    codes = {s.code for s in master}
    latest = {}
    for r in finmind_info:
        if r["stock_id"] in codes:
            latest[r["stock_id"]] = max(latest.get(r["stock_id"], ""), r["date"])
    modal = Counter(latest.values()).most_common(1)[0][0] if latest else None
    return {
        "not_in_finmind": sorted(codes - latest.keys()),
        "not_quoted": sorted({s.code for s in master if s.market in ("twse", "tpex") and s.code not in quoted}),
        "finmind_stale": sorted(c for c, d in latest.items() if d != modal),
    }
