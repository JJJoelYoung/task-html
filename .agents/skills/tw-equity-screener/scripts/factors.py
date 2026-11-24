"""Raw factor variables per stock from the daily panel, MOPS revenue and income, and valuation.

Units are percent or percentage points, except `rev_surge` (a z-score) and the
counts. Any missing input gives None. Revenue and income are in thousand NT$,
so only their ratios leave this module comparable across sources.
"""

import math
from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev

from shared import mt


@dataclass
class Panel:
    dates: list            # ascending ISO dates
    days: dict             # date -> exchange.fetch_day output

    def quote(self, code, i):
        """The code's quote row on date index i; None off the panel (no wrap-around for i < 0) or untraded."""
        if not 0 <= i < len(self.dates):
            return None
        return self.days[self.dates[i]]["quotes"].get(code)

    def close(self, code, i):
        q = self.quote(code, i)
        return q["close"] if q else None


def price_rows(panel, code, n=120):
    """FinMind-shaped price rows over the last n panel dates on which the code has a close, oldest first."""
    rows = []
    for i in range(len(panel.dates) - 1, -1, -1):
        q = panel.quote(code, i)
        if q and q["close"] is not None:
            rows.append({"date": panel.dates[i], "open": q["open"], "max": q["high"], "min": q["low"],
                         "close": q["close"], "Trading_Volume": q["volume"], "Trading_money": q["value"]})
            if len(rows) == n:
                break
    return rows[::-1]


def history_days(panel, code, max_gap=60):
    """Dates with a close in the trailing run, which breaks at the first gap longer than max_gap dates."""
    days = gap = 0
    for i in range(len(panel.dates) - 1, -1, -1):
        if panel.close(code, i) is None:
            gap += 1
            if gap > max_gap:
                break
        else:
            days, gap = days + 1, 0
    return days


def adv20(panel, code):
    """Median traded value over the last 20 panel dates; a date without a row or a trade counts as 0."""
    values = [((panel.quote(code, i) or {}).get("value") or 0.0)
              for i in range(max(0, len(panel.dates) - 20), len(panel.dates))]
    return mt.percentile(sorted(values), 50)


def week_ends(panel, n=13):
    """Index of the last panel date in each of the last n ISO weeks, the asof week included."""
    last = {}
    for i, d in enumerate(panel.dates):
        last[date.fromisoformat(d).isocalendar()[:2]] = i
    return sorted(last.values())[-n:]


def momentum_6_1(panel, code, i):
    """close(i − 21) / close(i − 126) − 1."""
    a, b = panel.close(code, i - 21), panel.close(code, i - 126)
    return a / b - 1 if a is not None and b else None


def persistence(panel, codes):
    """Per code, how many of the 13 week-ends put its momentum in the top third (rank ≤ ceil(n / 3) among the
    codes with momentum that week); None when it lacks momentum at any of them."""
    counts, lacking = dict.fromkeys(codes, 0), set()
    for i in week_ends(panel, 13):
        have = {}
        for c in codes:
            m = momentum_6_1(panel, c, i)
            if m is None:
                lacking.add(c)
            else:
                have[c] = m
        cutoff = math.ceil(len(have) / 3)
        if cutoff:
            bar = sorted(have.values(), reverse=True)[cutoff - 1]   # rank ≤ cutoff ⟺ momentum ≥ this
            for c, m in have.items():
                counts[c] += m >= bar
    return {c: None if c in lacking else counts[c] for c in codes}


def _month(latest, back):
    t = latest[0] * 12 + latest[1] - 1 - back
    return t // 12, t % 12 + 1


def _sum3(by, latest, back):
    vals = [by.get(_month(latest, back + k)) for k in range(3)]
    return None if None in vals else sum(vals)


def _surge(by, latest):
    R = [by.get(_month(latest, k)) for k in range(24, -1, -1)]          # 25 consecutive months, oldest first
    if None in R:
        return None
    d = [R[j] - R[j - 12] for j in range(12, 25)]
    sd = pstdev(d[:12])
    return (d[12] - mean(d[:12])) / sd if sd else None


def _consecutive(qs, n):
    last = qs[-n:]
    keys = [q["year"] * 4 + q["season"] for q in last]
    return last if len(last) == n and all(b - a == 1 for a, b in zip(keys, keys[1:])) else None


def _opm(qs):
    revenue, op = [q["revenue"] for q in qs], [q["op_income"] for q in qs]
    if None in revenue or None in op or sum(revenue) <= 0:
        return None
    return sum(op) / sum(revenue) * 100


def _revenue_factors(rev, market_month):
    by = {(r["revenue_year"], r["revenue_month"]): r["revenue"] for r in rev}
    latest = max(by) if by else None
    out = dict.fromkeys(("rev_yoy_med6", "rev_accel", "rev_surge", "rev_yoy3", "rev3", "rev3_ly"))
    out["latest_month"] = latest
    if latest is None or latest < tuple(market_month):        # no revenue, or a late filer
        return out
    view = mt.revenue(rev, [])
    yoys = [r["yoy_pct"] for r in view["last12"]]
    if not all(_month(latest, k) in by for k in range(12)):    # last12 holds the latest 12 *available* months
        yoys = []
    rev3, rev3_ly = _sum3(by, latest, 0), _sum3(by, latest, 12)
    out.update(rev_yoy_med6=mt.yoy6_median(view),
               rev_accel=mean(yoys[-3:]) - mean(yoys) if len(yoys) == 12 and None not in yoys else None,
               rev_surge=_surge(by, latest), rev3=rev3, rev3_ly=rev3_ly,
               rev_yoy3=rev3 / rev3_ly * 100 - 100 if rev3 is not None and rev3_ly else None)
    return out


def _quality(quarters, close, pbr):
    last4, last8 = _consecutive(quarters, 4), _consecutive(quarters, 8)
    out = dict.fromkeys(("opm_ttm", "opm_delta_4q", "opm_spread_4q", "roe_ttm", "ttm_op_income"))
    if last4:
        out["opm_ttm"] = _opm(last4)
        if all(q["op_income"] is not None for q in last4):
            out["ttm_op_income"] = sum(q["op_income"] for q in last4)
        margins = [_opm([q]) for q in last4]
        if None not in margins:
            out["opm_spread_4q"] = max(margins) - min(margins)
        eps = [q["eps"] for q in last4]
        if None not in eps and close and pbr and pbr > 0:
            out["roe_ttm"] = sum(eps) / (close / pbr) * 100
    if last8:
        new, old = _opm(last8[4:]), _opm(last8[:4])
        out["opm_delta_4q"] = new - old if new is not None and old is not None else None
    return out


def stock_factors(code, panel, rev, latest_row, quarters, val, shares, market_month):
    i = len(panel.dates) - 1
    close, back = panel.close(code, i), panel.close(code, i - 65)
    per, pbr = (val or {}).get("per"), (val or {}).get("pbr")
    flows = [((panel.days[panel.dates[j]].get("flows") or {}).get(code))
             for j in range(max(0, len(panel.dates) - 20), len(panel.dates))]
    net = sum((f["foreign"] or 0) + (f["trust"] or 0) for f in flows if f)
    out = {
        "close": close,
        "adv20": adv20(panel, code),
        "earnings_yield": 100 / per if per and per > 0 else None,
        "book_yield": 100 / pbr if pbr and pbr > 0 else None,
        "flow20_pct": net / shares * 100 if shares else None,
        "trust_days20": sum(1 for f in flows if f and (f["trust"] or 0) > 0),
        "ret13w": close / back * 100 - 100 if close is not None and back else None,
        "one_off": (bool(latest_row.get("note")) and (latest_row.get("yoy_pct") or 0) > 100
                    if latest_row is not None else None),
    }
    out.update(_revenue_factors(rev, market_month))
    out.update(_quality(quarters, close, pbr))
    return out
