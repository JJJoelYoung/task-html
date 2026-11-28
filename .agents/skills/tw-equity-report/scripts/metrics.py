"""Metrics from methodology.md sections 2 to 5.

Pure functions: FinMind rows in, metric dicts out. No network access.
"""

LOT = 1000
TAX_OUTLIER_PP = 10.0  # a quarter this far from the other three's pooled tax rate is left out of the baseline
Q_DEADLINE = {"03-31": "05-15", "06-30": "08-14", "09-30": "11-14", "12-31": "03-31"}
STATEMENT_TYPES = [
    "Revenue", "GrossProfit", "OperatingIncome", "CostOfGoodsSold", "EPS",
    "IncomeAfterTaxes", "EquityAttributableToOwnersOfParent", "TotalNonoperatingIncomeAndExpense",
    "TAX", "PreTaxIncome",
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
                "ma60": r2(ma(60, i)),
            }
        )
    w20 = series[-20:]
    last = series[-1]
    ma5, ma10, ma20 = last["ma5"], last["ma10"], last["ma20"]

    def slope5(key):
        if len(series) >= 6 and last[key] is not None and series[-6][key] is not None:
            return r2(last[key] - series[-6][key])
        return None

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
        "ma60": last["ma60"],
        "ma20_slope_5d": slope5("ma20"),
        "ma60_slope_5d": slope5("ma60"),
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

def missing_dates(rows, dates):
    """W20 dates for which a dataset returned no row at all."""
    present = {r["date"] for r in rows}
    return [d for d in dates if d not in present]


def institutional(rows, w20_dates, price_by_date):
    """Return (daily, cumulative, cost_zone) for the 3 institutional groups."""
    groups = {
        "foreign": {"Foreign_Investor", "Foreign_Dealer_Self"},
        "trust": {"Investment_Trust"},
        "dealer": {"Dealer_self", "Dealer_Hedging"},
    }
    absent = set(missing_dates(rows, w20_dates))
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
            v = None if d in absent else round(daily[d][g])
            cum[g] += v or 0
            row[g] = v
            row[g + "_cum"] = cum[g]
        out.append(row)

    def cost_zone(g):
        buys = [(d, daily[d][g]) for d in w20_dates if d not in absent and daily[d][g] > 0]
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

def revenue(rows, gaps):
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
    missing = [f"{ly}-{m:02d}" for m in range(1, lm + 1) if (ly, m) not in by]
    ytd = None if missing else sum(by[(ly, m)] for m in range(1, lm + 1))
    absent = [f"{ly - 1}-{m:02d}" for m in range(1, lm + 1) if (ly - 1, m) not in by]
    ytd_prev = None if absent else sum(by[(ly - 1, m)] for m in range(1, lm + 1))
    if absent or missing:
        gaps.append(f"Revenue for {', '.join(sorted(absent + missing))} is missing; YTD YoY is null.")
    series24 = [{"period": f"{y}-{m:02d}", "revenue": by[(y, m)]} for y, m in keys[-24:]]
    return {
        "latest_period": f"{ly}-{lm:02d}",
        "ytd": ytd,
        "ytd_prev": ytd_prev,
        "ytd_yoy_pct": r1(pct(ytd, ytd_prev)) if ytd is not None and ytd_prev is not None else None,
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


def next_quarter(q):
    md = {"03-31": "06-30", "06-30": "09-30", "09-30": "12-31"}.get(q[5:])
    return f"{q[:4]}-{md}" if md else f"{int(q[:4]) + 1}-03-31"


def _implied_shares(last4, consecutive, ttm_eps, share_cap):
    """Weighted average share count from latest normal quarter, falling back to TTM or OrdinaryShare / 10."""
    for q in reversed(last4):
        eps, nip = q.get("eps"), q.get("net_income_parent")
        if eps is not None and nip is not None and abs(eps) >= 0.2 and eps * nip > 0:
            return nip / eps, "implied_latest_q"
    if consecutive and ttm_eps is not None and abs(ttm_eps) >= 0.2:
        nips = [q.get("net_income_parent") for q in last4]
        if all(v is not None for v in nips) and sum(nips) * ttm_eps > 0:
            return sum(nips) / ttm_eps, "implied_ttm"
    if share_cap:
        return share_cap / 10, "ordinary_share_par10"
    return None, None


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
                "pretax_income": d.get("PreTaxIncome"),
                "tax": d.get("TAX"),
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
    consecutive = len(last4) == 4 and all(next_quarter(a["quarter"]) == b["quarter"] for a, b in zip(last4, last4[1:]))
    ttm_eps = r2(sum(q["eps"] for q in last4)) if consecutive else None
    if len(last4) == 4 and not consecutive:
        gaps.append(f"The last 4 quarters ({', '.join(q['quarter'] for q in last4)}) are not consecutive; "
                    "TTM EPS and cash conversion are null.")

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
    if consecutive:
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
    imp_shares, shares_src = _implied_shares(last4, consecutive, ttm_eps, share_cap)
    return {
        "quarters": quarters,
        "last4": [q["quarter"] for q in last4],
        "ttm_eps": ttm_eps,
        "cash_conversion": cash_conv,
        "ocf_quarterly": ocf_q,
        "bvps_latest": bvps,
        "shares_outstanding": share_cap / 10 if share_cap else None,
        "implied_shares": round(imp_shares) if imp_shares else None,
        "shares_source": shares_src,
        "latest_quarter": quarters[-1]["quarter"],
        "ocf_type": ocf_key,
    }


def yoy6_median(rev):
    """Median of the non-null revenue YoY over the last six months, or None (methodology section 4)."""
    last12 = (rev or {}).get("last12") or []
    return percentile(sorted(r["yoy_pct"] for r in last12[-6:] if r.get("yoy_pct") is not None), 50)


def core_baseline(rev, fin):
    """Dual CY and rolling NTM core operating run-rate baseline EPS (methodology section 4)."""

    def _na(reason):
        return {
            "applicable": False,
            "reason": reason,
            "yoy6_median_pct": None,
            "ttm_opm_pct": None,
            "effective_tax_rate_pct": None,
            "tax_source": None,
            "tax_excluded_quarter": None,
            "parent_ratio_pct": None,
            "parent_source": None,
            "core_net_margin_pct": None,
            "shares_used": None,
            "shares_source": None,
            "cy_revenue": None,
            "cy_eps": None,
            "cy_late_year": None,
            "ntm_revenue": None,
            "ntm_eps": None,
            "opm_spread_pp": None,
            "high_volatility": False,
            "volatility_reasons": [],
        }

    last4 = (fin or {}).get("quarters", [])[-4:]
    if len(last4) < 4 or not all(next_quarter(a["quarter"]) == b["quarter"] for a, b in zip(last4, last4[1:])):
        return _na("non_consecutive_quarters")
    if any(q.get("revenue") is None or q.get("operating_income") is None for q in last4):
        return _na("nonpositive_operating_income")
    ttm_rev = sum(q["revenue"] for q in last4)
    ttm_oi = sum(q["operating_income"] for q in last4)
    if ttm_rev <= 0 or ttm_oi <= 0:
        return _na("nonpositive_operating_income")

    shares = fin.get("implied_shares") or fin.get("shares_outstanding")
    shares_src = fin.get("shares_source") or ("ordinary_share_par10" if fin.get("shares_outstanding") else None)
    if not shares or shares <= 0:
        return _na("missing_shares")

    last12 = (rev or {}).get("last12") or []
    med_yoy = yoy6_median(rev)
    if med_yoy is None:
        return _na("missing_yoy")

    ttm_opm = ttm_oi / ttm_rev

    if all(q.get("tax") is not None and q.get("pretax_income") is not None for q in last4):
        sum_pt = sum(q["pretax_income"] for q in last4)
        sum_tax = sum(q["tax"] for q in last4)
        ratio_tax = sum_tax / sum_pt if sum_pt > 0 else None
        if ratio_tax is not None and 0.0 <= ratio_tax <= 0.40:
            eff_tax, tax_src = ratio_tax, "ttm_actual"
        else:
            eff_tax, tax_src = 0.20, "default_20pct"
    else:
        eff_tax, tax_src = 0.20, "default_20pct"

    tax_excluded = None
    if tax_src == "ttm_actual" and all(q["pretax_income"] > 0 for q in last4):
        # One-off quarters (a year-end true-up, a reversal) skew the pooled rate; drop at most one.
        gaps = []
        for i, q in enumerate(last4):
            rest = [o for j, o in enumerate(last4) if j != i]
            rest_rate = sum(o["tax"] for o in rest) / sum(o["pretax_income"] for o in rest)
            gaps.append((abs(q["tax"] / q["pretax_income"] - rest_rate), rest_rate, q["quarter"]))
        gap, rest_rate, quarter = max(gaps)
        if gap * 100 > TAX_OUTLIER_PP and 0.0 <= rest_rate <= 0.40:
            eff_tax, tax_src, tax_excluded = rest_rate, "ttm_ex_outlier", quarter

    if all(q.get("net_income_parent") is not None and q.get("net_income") is not None for q in last4):
        sum_ni = sum(q["net_income"] for q in last4)
        sum_nip = sum(q["net_income_parent"] for q in last4)
        ratio_par = sum_nip / sum_ni if sum_ni > 0 else None
        if ratio_par is not None and 0.0 < ratio_par <= 1.0:
            parent_ratio, parent_src = ratio_par, "ttm_actual"
        else:
            parent_ratio, parent_src = 1.0, "default_100pct"
    else:
        parent_ratio, parent_src = 1.0, "default_100pct"

    core_margin = ttm_opm * (1.0 - eff_tax) * parent_ratio

    cy_rev, cy_late_year = None, None
    latest_period = (rev or {}).get("latest_period")
    ytd = (rev or {}).get("ytd")
    if latest_period and ytd is not None:
        ly, lm = map(int, latest_period.split("-"))
        cy_late_year = lm >= 10
        by_p = {r["period"]: r["revenue"] for r in (rev or {}).get("series24", [])}
        if lm == 12:
            cy_rev = ytd
        else:
            rem_keys = [f"{ly - 1}-{m:02d}" for m in range(lm + 1, 13)]
            if all(by_p.get(k) is not None for k in rem_keys):
                rem_rev = sum(by_p[k] for k in rem_keys)
                cy_rev = ytd + rem_rev * (1.0 + med_yoy / 100.0)

    ntm_rev = (
        sum(r["revenue"] for r in last12) * (1.0 + med_yoy / 100.0)
        if len(last12) == 12 and all(r.get("revenue") is not None for r in last12)
        else None
    )

    opms = [q["operating_income"] / q["revenue"] * 100.0 for q in last4 if q["revenue"] > 0]
    opm_spread = (max(opms) - min(opms)) if len(opms) == 4 else None
    vol_reasons = []
    if opm_spread is not None and opm_spread > 5.0:
        vol_reasons.append("opm_spread_gt_5pp")
    if any(o <= 0 for o in opms):
        vol_reasons.append("negative_quarter_opm")
    if abs(med_yoy) > 50.0:
        vol_reasons.append("yoy_gt_50pct")

    return {
        "applicable": True,
        "reason": None,
        "yoy6_median_pct": r1(med_yoy),
        "ttm_opm_pct": r2(ttm_opm * 100),
        "effective_tax_rate_pct": r2(eff_tax * 100),
        "tax_source": tax_src,
        "tax_excluded_quarter": tax_excluded,
        "parent_ratio_pct": r2(parent_ratio * 100),
        "parent_source": parent_src,
        "core_net_margin_pct": r2(core_margin * 100),
        "shares_used": round(shares),
        "shares_source": shares_src,
        "cy_revenue": round(cy_rev) if cy_rev is not None else None,
        "cy_eps": r2(cy_rev * core_margin / shares) if cy_rev is not None else None,
        "cy_late_year": cy_late_year,
        "ntm_revenue": round(ntm_rev) if ntm_rev is not None else None,
        "ntm_eps": r2(ntm_rev * core_margin / shares) if ntm_rev is not None else None,
        "opm_spread_pp": r2(opm_spread),
        "high_volatility": bool(vol_reasons),
        "volatility_reasons": vol_reasons,
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
