"""Watch-track tables (upcoming listings, young listings, Emerging standouts) and the TAIEX regime flag."""

from shared import mt

FULL_HISTORY = 120
EMERGING_MIN_YOY = 20.0
REGIME_MIN_CLOSES = 270
RET_LAG, MA_N, WINDOW, SLOPE_LAG = 250, 60, 20, 5


def watch_tables(master, tracks, history, pipeline, emerging_rev, asof):
    """`tracks` is keyed by Security.key; `history` and `emerging_rev` by code."""
    upcoming = sorted(pipeline["upcoming"],
                      key=lambda u: (u["listing_date"] is None, u["listing_date"] or "", u["applied"] or ""))
    recent, emerging = [], []
    for s in master:
        if s.market in ("twse", "tpex") and tracks.get(s.key) != "full":
            days = history.get(s.code, 0)
            recent.append({"code": s.code, "name": s.name, "market": s.market, "listing_date": s.listing_date,
                           "history_days": days, "days_to_full": FULL_HISTORY - days,
                           "first_five": pipeline["first_five"].get(s.code)})
        elif s.market == "emerging" and emerging_rev.get(s.code):
            view = mt.revenue(emerging_rev[s.code], [])
            med6, last3 = mt.yoy6_median(view), [r["yoy_pct"] for r in view["last12"][-3:]]
            if med6 is not None and med6 >= EMERGING_MIN_YOY and len(last3) == 3 and all(
                    y is not None and y > 0 for y in last3):
                quote = pipeline["emerging"].get(s.code) or {}
                emerging.append({"code": s.code, "name": s.name, "industry": s.industry,
                                 "latest_period": view["latest_period"], "rev_yoy_med6": med6, "last3_yoy": last3,
                                 **{k: quote.get(k) for k in ("avg", "last", "volume", "applying_status")}})
    recent.sort(key=lambda r: (r["days_to_full"], r["code"]))
    emerging.sort(key=lambda e: (-e["rev_yoy_med6"], e["code"]))
    return {"asof": asof, "upcoming": upcoming, "recent": recent, "emerging": emerging}


def _state(closes, k):
    """(close > MA60, 12-month return > 0) at index k."""
    ma = sum(closes[k - MA_N + 1:k + 1]) / MA_N
    return closes[k] > ma, closes[k] / closes[k - RET_LAG] - 1 > 0


def regime(taiex):
    """TAIEX regime from (date, close) pairs, oldest first."""
    closes = [c for _, c in taiex]
    n = len(closes)
    out = {"close": closes[-1] if closes else None, "ma60": None, "ma60_slope_5d": None, "ret12m": None,
           "above_ma60": None, "transition": None, "reasons": ["insufficient_history"]}
    if n >= MA_N + SLOPE_LAG:
        ma_now = sum(closes[-MA_N:]) / MA_N
        out.update(ma60=ma_now, above_ma60=closes[-1] > ma_now,
                   ma60_slope_5d=ma_now - sum(closes[-MA_N - SLOPE_LAG:-SLOPE_LAG]) / MA_N)
    if n > RET_LAG:
        out["ret12m"] = (closes[-1] / closes[-1 - RET_LAG] - 1) * 100
    if n >= REGIME_MIN_CLOSES:
        states = [_state(closes, k) for k in range(n - WINDOW, n)]     # the last 20 dates
        reasons = [name for i, name in enumerate(("ma60_cross", "ret12m_sign")) if len({s[i] for s in states}) > 1]
        out.update(transition=bool(reasons), reasons=reasons)
    return out
