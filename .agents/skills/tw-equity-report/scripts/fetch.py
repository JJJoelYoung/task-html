#!/usr/bin/env python3
"""Fetch FinMind data for one Taiwan stock and write data_{code}.json.

Usage:
  python fetch.py <code> --out <work-folder> [--peers 2327,3026,2478] [--asof YYYY-MM-DD]

--asof pins the as-of date (default: the latest trading day in TaiwanStockPrice).
Exit code 2: the FinMind hourly quota is exhausted.
Exit code 3: a chip dataset has no row for asof yet (FinMind publishes it later).
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import metrics as mt
from finmind_client import QuotaError, fetch

HERE = Path(__file__).resolve().parent


class NotPublishedError(RuntimeError):
    """A W20 dataset has no row for asof yet."""


def chip_rows(dataset, code, w20_dates, gaps):
    """Fetch a W20 chip dataset; stop if asof is absent, record a gap for earlier absent days."""
    rows = fetch(dataset, code, w20_dates[0], w20_dates[-1])
    absent = mt.missing_dates(rows, w20_dates)
    if w20_dates[-1] in absent:
        raise NotPublishedError(
            f"{dataset} has no row for {w20_dates[-1]} yet. FinMind usually adds it in the evening; "
            "rerun later, or pin an earlier --asof."
        )
    if absent:
        gaps.append(f"{dataset} has no rows for {', '.join(absent)}; those days are null and excluded.")
    return rows


def tool_version():
    """Short git hash of this scripts folder, with -dirty when it has local edits."""
    try:
        h = subprocess.run(
            ["git", "-C", str(HERE), "log", "-1", "--format=%h", "--", "."],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(HERE), "status", "--porcelain", "--", "."],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return (h or "uncommitted") + ("-dirty" if dirty else "")


def build(code, peers, asof_pin=None):
    gaps, sources = [], {}
    today = date.today()
    anchor = date.fromisoformat(asof_pin) if asof_pin else today
    probe = fetch("TaiwanStockPrice", code, (anchor - timedelta(days=300)).isoformat(), asof_pin)
    traded = [r for r in probe if r["Trading_Volume"] > 0]
    if not traded:
        raise RuntimeError(f"TaiwanStockPrice returned no traded days for {code}.")
    asof = max(r["date"] for r in traded)
    asof_d = date.fromisoformat(asof)
    price_rows = sorted((r for r in probe if r["date"] <= asof), key=lambda r: r["date"])[-120:]
    series, pm = mt.price_metrics(price_rows)
    sources["price"] = {"dataset": "TaiwanStockPrice", "range": [series[0]["date"], asof]}
    w20_dates = [d["date"] for d in series[-20:]]
    by_date = {d["date"]: d for d in series}
    w_start = w20_dates[0]

    inst_rows = chip_rows("TaiwanStockInstitutionalInvestorsBuySell", code, w20_dates, gaps)
    inst_daily, inst_cum, zone = mt.institutional(inst_rows, w20_dates, by_date)
    sources["institutional"] = {"dataset": "TaiwanStockInstitutionalInvestorsBuySell", "range": [w_start, asof]}
    if zone is None:
        gaps.append("Neither foreign nor investment trust had 3+ net-buy days in W20; institutional cost zone is null.")

    sh = mt.shareholding(chip_rows("TaiwanStockShareholding", code, w20_dates, gaps), w20_dates)
    sources["foreign_holding"] = {"dataset": "TaiwanStockShareholding", "range": [w_start, asof]}
    if sh is None:
        gaps.append("TaiwanStockShareholding returned no rows in W20.")

    mg = mt.margin(chip_rows("TaiwanStockMarginPurchaseShortSale", code, w20_dates, gaps), w20_dates)
    sources["margin"] = {"dataset": "TaiwanStockMarginPurchaseShortSale", "range": [w_start, asof]}
    if mg is None:
        gaps.append("TaiwanStockMarginPurchaseShortSale returned no rows in W20.")
    pm["float_settling"] = mt.float_settling(pm, mg)

    rev = mt.revenue(fetch("TaiwanStockMonthRevenue", code, f"{asof_d.year - 2}-01-01", asof), gaps)
    sources["revenue"] = {"dataset": "TaiwanStockMonthRevenue", "range": [rev["series24"][0]["period"], rev["latest_period"]]}

    fin_start = f"{asof_d.year - 2}-07-01"
    inc = fetch("TaiwanStockFinancialStatements", code, fin_start, asof)
    bal = fetch("TaiwanStockBalanceSheet", code, fin_start, asof)
    cf = fetch("TaiwanStockCashFlowsStatement", code, f"{asof_d.year - 3}-01-01", asof)
    fin = mt.financials(inc, bal, cf, asof, gaps)
    fin["quarters"] = fin["quarters"][-8:]
    sources["financials"] = {
        "dataset": "TaiwanStockFinancialStatements / TaiwanStockBalanceSheet / TaiwanStockCashFlowsStatement",
        "range": [fin["quarters"][0]["quarter"], fin["latest_quarter"]],
        "types_used": mt.STATEMENT_TYPES + [fin["ocf_type"]],
    }
    q_gap = mt.missing_quarter_gap(fin["latest_quarter"], asof)
    if q_gap:
        gaps.append(q_gap)

    per = fetch("TaiwanStockPER", code, f"{asof_d.year - 5}-{asof[5:]}", asof)
    val = mt.bands(per)
    sources["valuation"] = {"dataset": "TaiwanStockPER", "range": [val["start"], val["date"]]}

    peer_rows = [{"code": code, "PER": val["PER"]["current"], "PBR": val["PBR"]["current"],
                  "dividend_yield": val["dividend_yield"], "date": val["date"]}]
    for p in peers:
        rows = fetch("TaiwanStockPER", p, (asof_d - timedelta(days=14)).isoformat(), asof)
        if not rows:
            gaps.append(f"No TaiwanStockPER rows for peer {p}.")
            continue
        lr = sorted(rows, key=lambda r: r["date"])[-1]
        peer_rows.append({"code": p, "PER": lr["PER"], "PBR": lr["PBR"],
                          "dividend_yield": lr["dividend_yield"], "date": lr["date"]})
    if peers:
        sources["peers"] = {"dataset": "TaiwanStockPER", "range": ["latest", asof], "codes": peers}

    return {
        "code": code,
        "asof": asof,
        "generated": today.isoformat(),
        "tool_version": tool_version(),
        "sources": sources,
        "gaps": gaps,
        "price": {"series": series, "metrics": pm},
        "institutional": {"daily": inst_daily, "cum": inst_cum, "cost_zone": zone},
        "foreign_holding": sh,
        "margin": mg,
        "revenue": rev,
        "financials": fin,
        "valuation": val,
        "peers": mt.peer_matrix(peer_rows),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code")
    ap.add_argument("--out", required=True, type=Path, help="work folder for data_{code}.json")
    ap.add_argument("--peers", default="", help="comma-separated peer codes")
    ap.add_argument("--asof", default=None, help="pin the as-of date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    peers = [p for p in args.peers.split(",") if p]
    try:
        data = build(args.code, peers, args.asof)
    except QuotaError as e:
        print(e, file=sys.stderr)
        return 2
    except NotPublishedError as e:
        print(e, file=sys.stderr)
        return 3
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"data_{args.code}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}: asof={data['asof']}, gaps={len(data['gaps'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
