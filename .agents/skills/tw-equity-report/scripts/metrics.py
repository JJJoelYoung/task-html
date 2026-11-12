"""Metrics from methodology.md sections 2 to 5.

Pure functions: FinMind rows in, metric dicts out. No network access.
"""

LOT = 1000
Q_DEADLINE = {"03-31": "05-15", "06-30": "08-14", "09-30": "11-14", "12-31": "03-31"}
STATEMENT_TYPES = [
    "Revenue", "GrossProfit", "OperatingIncome", "CostOfGoodsSold", "EPS",
    "IncomeAfterTaxes", "EquityAttributableToOwnersOfParent", "TotalNonoperatingIncomeAndExpense",
    "Inventories", "OrdinaryShare",
]


def r2(x):
    return None if x is None else round(x, 2)


def r1(x):
    return None if x is None else round(x, 1)


def pct(a, b):
    return None if not b else (a / b - 1) * 100


def percentile(sorted_vals, p):
    """Linear-interpolation percentile of an ascending list, p in [0, 100]."""
    n = len(sorted_vals)
    if n == 0:
        return None
    k = (n - 1) * p / 100
    f = int(k)
    c = min(f + 1, n - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------- 2. price

def price_metrics(rows):
    """Return (series, metrics) from TaiwanStockPrice rows ending at asof."""
    rows = sorted(rows, key=lambda r: r["date"])
    rows = [r for r in rows if r["Trading_Volume"] > 0]
    closes = [r["close"] for r in rows]

    def ma(n, i):
        return mean(closes[i - n + 1 : i + 1]) if i >= n - 1 else None

    series = []
    for i, r in enumerate(rows):
        series.append(
            {
                "date": r["date"],
                "open": r["open"],
                "high": r["max"],
                "low": r["min"],
                "close": r["close"],
                "volume_lots": round(r["Trading_Volume"] / LOT),
                "avg_price": r["Trading_money"] / r["Trading_Volume"],
                "ma5": r2(ma(5, i)),
                "ma10": r2(ma(10, i)),
                "ma20": r2(ma(20, i)),
            }
        )
    w20 = series[-20:]
    last = series[-1]
    ma5, ma10, ma20 = last["ma5"], last["ma10"], last["ma20"]
    vol_avg20 = mean([d["volume_lots"] for d in w20])
    hi = max(w20, key=lambda d: d["high"])
    lo = min(w20, key=lambda d: d["low"])
    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / last["close"]
    if ma5 > ma10 > ma20:
        align = "bullish"
    elif ma5 < ma10 < ma20:
        align = "bearish"
    else:
        align = "mixed"
    spikes = [d["date"] for d in w20 if d["volume_lots"] > 1.5 * vol_avg20]
    dryups = [d["date"] for d in w20 if d["volume_lots"] < 0.6 * vol_avg20]
    s60 = series[-60:]
    maxvol = max(w20, key=lambda d: d["volume_lots"])
    return series, {
        "close": last["close"],
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "bias_ma20_pct": r1((last["close"] - ma20) / ma20 * 100),
        "w20_start": w20[0]["date"],
        "w20_high": hi["high"],
        "w20_high_date": hi["date"],
        "w20_low": lo["low"],
        "w20_low_date": lo["date"],
        "ma_spread_pct": r2(spread * 100),
        "squeeze": spread < 0.02,
        "alignment": align,
        "vol_avg20_lots": round(vol_avg20),
        "spike_days": spikes,
        "dryup_days": dryups,
        "high60": max(d["high"] for d in s60),
        "high60_date": max(s60, key=lambda d: d["high"])["date"],
        "low60": min(d["low"] for d in s60),
        "low60_date": min(s60, key=lambda d: d["low"])["date"],
        "w20_maxvol_date": maxvol["date"],
        "w20_maxvol_low": maxvol["low"],
        "w20_maxvol_lots": maxvol["volume_lots"],
    }


def float_settling(price_m, margin_m):
    dryups = len(price_m["dryup_days"])
    return {
        "margin_change": margin_m["margin_change"] if margin_m else None,
        "dryup_count": dryups,
        "signal": bool(margin_m and margin_m["margin_change"] < 0 and dryups >= 5),
    }


# ---------------------------------------------------------------- 3. chips

def institutional(rows, w20_dates, price_by_date):
    """Return (daily, cumulative, cost_zone) for the 3 institutional groups."""
    groups = {
        "foreign": {"Foreign_Investor", "Foreign_Dealer_Self"},
        "trust": {"Investment_Trust"},
        "dealer": {"Dealer_self", "Dealer_Hedging"},
    }
    daily = {d: {g: 0 for g in groups} for d in w20_dates}
    for r in rows:
        if r["date"] not in daily:
            continue
        for g, names in groups.items():
            if r["name"] in names:
                daily[r["date"]][g] += (r["buy"] - r["sell"]) / LOT
    out, cum = [], {g: 0 for g in groups}
    for d in w20_dates:
        row = {"date": d}
        for g in groups:
            v = round(daily[d][g])
            cum[g] += v
            row[g] = v
            row[g + "_cum"] = cum[g]
        out.append(row)

    def cost_zone(g):
        buys = [(d, daily[d][g]) for d in w20_dates if daily[d][g] > 0]
        if len(buys) < 3:
            return None
        w = sum(v for _, v in buys)
        vwap = sum(price_by_date[d]["avg_price"] * v for d, v in buys) / w
        return {"group": g, "days": len(buys), "price": r2(vwap), "low": r2(vwap * 0.98), "high": r2(vwap * 1.02)}

    zone = cost_zone("foreign") or cost_zone("trust")
    return out, {g: cum[g] for g in groups}, zone


def shareholding(rows, w20_dates):
    rows = [r for r in sorted(rows, key=lambda r: r["date"]) if r["date"] in set(w20_dates)]
    if not rows:
        return None
    vals = [r["ForeignInvestmentSharesRatio"] for r in rows]
    return {
        "series": [{"date": r["date"], "ratio": r["ForeignInvestmentSharesRatio"]} for r in rows],
        "first": vals[0],
        "last": vals[-1],
        "high": max(vals),
        "low": min(vals),
        "change_pp": r2(vals[-1] - vals[0]),
    }


def margin(rows, w20_dates):
    rows = [r for r in sorted(rows, key=lambda r: r["date"]) if r["date"] in set(w20_dates)]
    if not rows:
        return None
    m = [r["MarginPurchaseTodayBalance"] for r in rows]
    s = [r["ShortSaleTodayBalance"] for r in rows]
    ratio = s[-1] / m[-1] * 100 if m[-1] else None
    level = None if ratio is None else ("low" if ratio < 5 else "medium" if ratio <= 20 else "high")
    return {
        "series": [
            {"date": r["date"], "margin": r["MarginPurchaseTodayBalance"], "short": r["ShortSaleTodayBalance"]}
            for r in rows
        ],
        "margin_first": m[0],
        "margin_last": m[-1],
        "margin_change": m[-1] - m[0],
        "margin_change_pct": r1(pct(m[-1], m[0])),
        "short_first": s[0],
        "short_last": s[-1],
        "short_change": s[-1] - s[0],
        "short_change_pct": r1(pct(s[-1], s[0])),
        "short_margin_ratio_pct": r2(ratio),
        "short_margin_level": level,
    }


# ---------------------------------------------------------------- 4. operations

def revenue(rows):
    by = {(r["revenue_year"], r["revenue_month"]): r["revenue"] for r in rows}
    keys = sorted(by)
    ly, lm = keys[-1]
    last12 = []
    for y, m in keys[-12:]:
        pm = (y, m - 1) if m > 1 else (y - 1, 12)
        v = by[(y, m)]
        last12.append(
            {
                "period": f"{y}-{m:02d}",
                "revenue": v,
                "mom_pct": r1(pct(v, by.get(pm))) if by.get(pm) else None,
                "yoy_pct": r1(pct(v, by.get((y - 1, m)))) if by.get((y - 1, m)) else None,
            }
        )
    ytd = sum(by[(ly, m)] for m in range(1, lm + 1))
    ytd_prev = sum(by.get((ly - 1, m), 0) for m in range(1, lm + 1))
    series24 = [{"period": f"{y}-{m:02d}", "revenue": by[(y, m)]} for y, m in keys[-24:]]
    return {
        "latest_period": f"{ly}-{lm:02d}",
        "ytd": ytd,
        "ytd_prev": ytd_prev,
        "ytd_yoy_pct": r1(pct(ytd, ytd_prev)),
        "last12": last12,
        "series24": series24,
    }


def pivot(rows):
    out = {}
    for r in rows:
        out.setdefault(r["date"], {})[r["type"]] = r["value"]
    return out


def usable(qdate, asof):
    """True once the quarter's statutory filing deadline has passed at asof."""
    y, md = qdate[:4], qdate[5:]
    dl_year = int(y) + 1 if md == "12-31" else int(y)
    return asof >= f"{dl_year}-{Q_DEADLINE[md]}"


def financials(inc, bal, cf, asof, gaps):
    inc, bal, cf = pivot(inc), pivot(bal), pivot(cf)
    # Rows present in the dataset are usable even before the deadline (methodology 0).
    qs = sorted(q for q in inc if "Revenue" in inc[q])
    quarters = []
    for q in qs:
        d = inc[q]
        rev = d.get("Revenue")
        gp = d.get("GrossProfit")
        oi = d.get("OperatingIncome")
        cogs = d.get("CostOfGoodsSold")
        quarters.append(
            {
                "quarter": q,
                "revenue": rev,
                "gross_profit": gp,
                "operating_income": oi,
                "cogs": cogs,
                "eps": d.get("EPS"),
                "net_income_parent": d.get("EquityAttributableToOwnersOfParent"),
                "net_income": d.get("IncomeAfterTaxes"),
                "non_operating": d.get("TotalNonoperatingIncomeAndExpense"),
                "gross_margin_pct": r2(gp / rev * 100) if gp is not None and rev else None,
                "operating_margin_pct": r2(oi / rev * 100) if oi is not None and rev else None,
                "inventory": bal.get(q, {}).get("Inventories"),
                "pre_deadline": not usable(q, asof),
            }
        )
    for i, qq in enumerate(quarters):
        if i > 0 and qq["inventory"] is not None and quarters[i - 1]["inventory"] is not None and qq["cogs"]:
            avg_inv = (qq["inventory"] + quarters[i - 1]["inventory"]) / 2
            qq["dsi_days"] = r1(avg_inv / qq["cogs"] * 91)
        else:
            qq["dsi_days"] = None
    last4 = quarters[-4:]
    ttm_eps = r2(sum(q["eps"] for q in last4)) if len(last4) == 4 else None

    # The cash flow statement is cumulative within a fiscal year: de-cumulate.
    ocf_key = "CashFlowsFromOperatingActivities"
    if not any(ocf_key in v for v in cf.values()):
        ocf_key = "NetCashInflowFromOperatingActivities"
    ocf_q = {}
    for q in sorted(cf):
        if ocf_key not in cf[q]:
            continue
        v = cf[q][ocf_key]
        if q[5:] != "03-31":
            prev = {"06-30": "03-31", "09-30": "06-30", "12-31": "09-30"}[q[5:]]
            pq = f"{q[:4]}-{prev}"
            if pq not in cf or ocf_key not in cf[pq]:
                continue
            v -= cf[pq][ocf_key]
        ocf_q[q] = v
    cash_conv = None
    l4q = [q["quarter"] for q in last4]
    if all(q in ocf_q for q in l4q):
        ttm_ocf = sum(ocf_q[q] for q in l4q)
        ttm_ni = sum(q["net_income"] for q in last4)
        cash_conv = {"ttm_ocf": ttm_ocf, "ttm_net_income": ttm_ni, "ratio": r2(ttm_ocf / ttm_ni)}
    else:
        gaps.append("Operating cash flow missing for one of the last 4 quarters; cash conversion is null.")

    lb = bal.get(quarters[-1]["quarter"], {})
    equity_parent = lb.get("EquityAttributableToOwnersOfParent")
    share_cap = lb.get("OrdinaryShare")
    bvps = r2(equity_parent / (share_cap / 10)) if equity_parent and share_cap else None
    return {
        "quarters": quarters,
        "last4": [q["quarter"] for q in last4],
        "ttm_eps": ttm_eps,
        "cash_conversion": cash_conv,
        "ocf_quarterly": ocf_q,
        "bvps_latest": bvps,
        "shares_outstanding": share_cap / 10 if share_cap else None,
        "latest_quarter": quarters[-1]["quarter"],
        "ocf_type": ocf_key,
    }


def missing_quarter_gap(latest_quarter, asof):
    """Gap text when the most recent ended quarter is not in the dataset yet, else None."""
    year = asof[:4]
    for md in ("09-30", "06-30", "03-31"):
        cand = f"{year}-{md}"
        if cand < asof:
            if latest_quarter < cand:
                return (
                    f"Quarter {cand} statements are not yet in FinMind (statutory deadline not reached); "
                    f"quarterly metrics run through {latest_quarter}."
                )
            return None
    return None


# ---------------------------------------------------------------- 5. valuation

def bands(rows):
    rows = sorted(rows, key=lambda r: r["date"])
    out = {}
    for key, drop_nonpos in (("PER", True), ("PBR", False)):
        vals = [r[key] for r in rows if r[key] is not None and (r[key] > 0 if drop_nonpos else True)]
        cur = rows[-1][key]
        s = sorted(vals)
        out[key] = {
            "current": cur,
            "p10": r2(percentile(s, 10)),
            "p25": r2(percentile(s, 25)),
            "p50": r2(percentile(s, 50)),
            "p75": r2(percentile(s, 75)),
            "p90": r2(percentile(s, 90)),
            "current_percentile": r1(sum(1 for v in vals if v <= cur) / len(vals) * 100) if cur and cur > 0 else None,
            "n": len(vals),
            "series": [{"date": r["date"], "v": r[key]} for r in rows if r[key] is not None][::5],
        }
    out["dividend_yield"] = rows[-1]["dividend_yield"]
    out["date"] = rows[-1]["date"]
    out["start"] = rows[0]["date"]
    return out


def peer_matrix(peer_rows):
    """peer_rows[0] is the target; the median covers the peers only."""

    def med(xs):
        xs = sorted(x for x in xs if x is not None and x > 0)
        return r2(percentile(xs, 50)) if xs else None

    pr = peer_rows[1:]
    return {
        "rows": peer_rows,
        "median": {k: med([r[k] for r in pr]) for k in ("PER", "PBR", "dividend_yield")} if pr else None,
    }
