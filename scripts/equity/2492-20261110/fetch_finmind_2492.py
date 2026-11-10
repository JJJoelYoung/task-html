#!/usr/bin/env python3
"""Fetch FinMind data for 2492 Walsin Technology and compute report metrics.

Standard library only. Optional token via FINMIND_TOKEN env var.
Usage: python fetch_finmind_2492.py [--peers 2327,3026,2478]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

CODE = "2492"
BASE_URL = "https://api.finmindtrade.com/api/v4/data"
OUT = Path(__file__).resolve().parent / f"data_{CODE}.json"
LOT = 1000


class QuotaError(RuntimeError):
    pass


def fetch(dataset, data_id, start, end=None):
    params = {"dataset": dataset, "data_id": data_id, "start_date": start}
    if end:
        params["end_date"] = end
    req = urllib.request.Request(BASE_URL + "?" + urllib.parse.urlencode(params))
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (402, 429):
            raise QuotaError(
                f"FinMind quota exhausted (HTTP {exc.code}). Set FINMIND_TOKEN to raise the limit."
            ) from exc
        raise
    finally:
        time.sleep(0.5)
    if payload.get("status") not in (200, None):
        raise RuntimeError(f"{dataset}: {payload.get('msg')}")
    return payload.get("data", [])


def r2(x):
    return None if x is None else round(x, 2)


def r1(x):
    return None if x is None else round(x, 1)


def pct(a, b):
    return None if not b else (a / b - 1) * 100


def percentile(sorted_vals, p):
    """Linear interpolation percentile, p in [0, 100]."""
    n = len(sorted_vals)
    if n == 0:
        return None
    k = (n - 1) * p / 100
    f = int(k)
    c = min(f + 1, n - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------- price

def price_metrics(rows):
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


# ---------------------------------------------------------------- chips

def institutional(rows, w20_dates, price_by_date):
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


# ---------------------------------------------------------------- operations

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


Q_DEADLINE = {"03-31": "05-15", "06-30": "08-14", "09-30": "11-14", "12-31": "03-31"}


def usable(qdate, asof):
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

    # Cash flow statement is cumulative within a fiscal year: de-cumulate.
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


# ---------------------------------------------------------------- valuation

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


def main():
    peers = []
    if "--peers" in sys.argv:
        arg = sys.argv[sys.argv.index("--peers") + 1]
        peers = [p for p in arg.split(",") if p]

    gaps, sources = [], {}
    today = date.today()
    probe = fetch("TaiwanStockPrice", CODE, (today - timedelta(days=300)).isoformat())
    asof = max(r["date"] for r in probe if r["Trading_Volume"] > 0)
    asof_d = date.fromisoformat(asof)
    price_rows = [r for r in probe if r["date"] <= asof]
    price_rows = sorted(price_rows, key=lambda r: r["date"])[-120:]
    series, pm = price_metrics(price_rows)
    sources["price"] = {"dataset": "TaiwanStockPrice", "range": [series[0]["date"], asof]}
    w20_dates = [d["date"] for d in series[-20:]]
    by_date = {d["date"]: d for d in series}
    w_start = w20_dates[0]

    inst_rows = fetch("TaiwanStockInstitutionalInvestorsBuySell", CODE, w_start, asof)
    inst_daily, inst_cum, zone = institutional(inst_rows, w20_dates, by_date)
    sources["institutional"] = {"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "range": [w_start, asof]}
    if zone is None:
        gaps.append("Neither foreign nor investment trust had 3+ net-buy days in W20; institutional cost zone is null.")

    sh = shareholding(fetch("TaiwanStockShareholding", CODE, w_start, asof), w20_dates)
    sources["foreign_holding"] = {"dataset": "TaiwanStockShareholding", "range": [w_start, asof]}
    if sh is None:
        gaps.append("TaiwanStockShareholding returned no rows in W20.")

    mg = margin(fetch("TaiwanStockMarginPurchaseShortSale", CODE, w_start, asof), w20_dates)
    sources["margin"] = {"dataset": "TaiwanStockMarginPurchaseShortSale", "range": [w_start, asof]}
    if mg is None:
        gaps.append("TaiwanStockMarginPurchaseShortSale returned no rows in W20.")

    dryups = len(pm["dryup_days"])
    pm["float_settling"] = {
        "margin_change": mg["margin_change"] if mg else None,
        "dryup_count": dryups,
        "signal": bool(mg and mg["margin_change"] < 0 and dryups >= 5),
    }

    rev_start = f"{asof_d.year - 2}-01-01"
    rev = revenue(fetch("TaiwanStockMonthRevenue", CODE, rev_start, asof))
    sources["revenue"] = {"dataset": "TaiwanStockMonthRevenue", "range": [rev["series24"][0]["period"], rev["latest_period"]]}

    fin_start = f"{asof_d.year - 2}-07-01"
    inc = fetch("TaiwanStockFinancialStatements", CODE, fin_start, asof)
    bal = fetch("TaiwanStockBalanceSheet", CODE, fin_start, asof)
    cf = fetch("TaiwanStockCashFlowsStatement", CODE, f"{asof_d.year - 3}-01-01", asof)
    fin = financials(inc, bal, cf, asof, gaps)
    fin["quarters"] = fin["quarters"][-8:]
    sources["financials"] = {
        "dataset": "TaiwanStockFinancialStatements / TaiwanStockBalanceSheet / TaiwanStockCashFlowsStatement",
        "range": [fin["quarters"][0]["quarter"], fin["latest_quarter"]],
        "types_used": [
            "Revenue", "GrossProfit", "OperatingIncome", "CostOfGoodsSold", "EPS",
            "IncomeAfterTaxes", "EquityAttributableToOwnersOfParent", "TotalNonoperatingIncomeAndExpense",
            "Inventories", "OrdinaryShare", fin["ocf_type"],
        ],
    }
    q_end = {1: "03-31", 2: "06-30", 3: "09-30"}
    exp_q = None
    for qn in (3, 2, 1):
        cand = f"{asof_d.year}-{q_end[qn]}"
        if cand < asof:
            exp_q = cand
            break
    if exp_q and fin["latest_quarter"] < exp_q:
        gaps.append(
            f"Quarter {exp_q} statements are not yet in FinMind (statutory deadline not reached); "
            f"quarterly metrics run through {fin['latest_quarter']}."
        )

    per = fetch("TaiwanStockPER", CODE, f"{asof_d.year - 5}-{asof[5:]}", asof)
    val = bands(per)
    sources["valuation"] = {"dataset": "TaiwanStockPER", "range": [val["start"], val["date"]]}

    peer_rows = [{"code": CODE, "PER": val["PER"]["current"], "PBR": val["PBR"]["current"], "dividend_yield": val["dividend_yield"], "date": val["date"]}]
    for p in peers:
        rows = fetch("TaiwanStockPER", p, (asof_d - timedelta(days=14)).isoformat(), asof)
        if not rows:
            gaps.append(f"No TaiwanStockPER rows for peer {p}.")
            continue
        lr = sorted(rows, key=lambda r: r["date"])[-1]
        peer_rows.append({"code": p, "PER": lr["PER"], "PBR": lr["PBR"], "dividend_yield": lr["dividend_yield"], "date": lr["date"]})

    def med(xs):
        xs = sorted(x for x in xs if x is not None and x > 0)
        return r2(percentile(xs, 50)) if xs else None

    pr = peer_rows[1:]
    peer_matrix = {
        "rows": peer_rows,
        "median": {k: med([r[k] for r in pr]) for k in ("PER", "PBR", "dividend_yield")} if pr else None,
    }
    if peers:
        sources["peers"] = {"dataset": "TaiwanStockPER", "range": ["latest", asof], "codes": peers}

    data = {
        "code": CODE,
        "asof": asof,
        "generated": today.isoformat(),
        "sources": sources,
        "gaps": gaps,
        "price": {"series": series, "metrics": pm},
        "institutional": {"daily": inst_daily, "cum": inst_cum, "cost_zone": zone},
        "foreign_holding": sh,
        "margin": mg,
        "revenue": rev,
        "financials": fin,
        "valuation": val,
        "peers": peer_matrix,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.name}: asof={asof}, gaps={len(gaps)}")


if __name__ == "__main__":
    try:
        main()
    except QuotaError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
