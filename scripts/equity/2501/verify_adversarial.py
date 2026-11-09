#!/usr/bin/env python3
"""
verify_adversarial.py
Adversarial Financial & Mathematical Verification Suite for 2501 Cathay Real Estate.
Author: teamwork_challenger (Challenger 1)
"""

import sys
import os
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data_2501.json"
HTML_PATH = BASE_DIR / "2501_Cathay_Real_Estate_Equity_Report.html"

def half_up_round(val, decimals=2):
    if val is None:
        return None
    d = Decimal(str(val))
    target = Decimal("10") ** -decimals
    return float(d.quantize(target, rounding=ROUND_HALF_UP))

def main():
    print("=" * 70)
    print(" EMPIRICAL ADVERSARIAL FINANCIAL & MATHEMATICAL VERIFICATION SUITE")
    print("=" * 70)
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # ------------------------------------------------------------------
    # 1. MOVING AVERAGES (5MA, 10MA, 20MA)
    # ------------------------------------------------------------------
    print("\n[1] MOVING AVERAGES AUDIT:")
    daily = data["market_data"]["daily_series"]
    closes = [Decimal(str(d["close"])) for d in daily]
    
    c_last = closes[-1]
    print(f"  Latest Close: {c_last}")
    
    # Latest 5 closes:
    c5 = closes[-5:]
    s5 = sum(c5)
    ma5_exact = s5 / Decimal("5")
    ma5_halfup = float(ma5_exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_ma5 = data["market_data"]["ma5"]
    print(f"  5 Closes: {[float(x) for x in c5]}")
    print(f"  Sum5 = {s5}, Exact 5MA = {ma5_exact}, Half-Up Rounded = {ma5_halfup}, Reported = {reported_ma5}")
    
    # Latest 10 closes:
    c10 = closes[-10:]
    s10 = sum(c10)
    ma10_exact = s10 / Decimal("10")
    ma10_halfup = float(ma10_exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_ma10 = data["market_data"]["ma10"]
    print(f"  10 Closes: {[float(x) for x in c10]}")
    print(f"  Sum10 = {s10}, Exact 10MA = {ma10_exact}, Half-Up Rounded = {ma10_halfup}, Reported = {reported_ma10}")
    
    # Latest 20 closes:
    c20 = closes[-20:]
    s20 = sum(c20)
    ma20_exact = s20 / Decimal("20")
    ma20_halfup = float(ma20_exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_ma20 = data["market_data"]["ma20"]
    print(f"  20 Closes: {[float(x) for x in c20]}")
    print(f"  Sum20 = {s20}, Exact 20MA = {ma20_exact}, Half-Up Rounded = {ma20_halfup}, Reported = {reported_ma20}")
    
    # Check if displayed in HTML:
    ma5_in_html = ("20.37" in html)
    ma10_in_html = ("20.30" in html or "20.3" in html)
    ma20_in_html = ("20.40" in html or "20.4" in html)
    print(f"  HTML Display: 5MA(20.37)={ma5_in_html}, 10MA(20.30)={ma10_in_html}, 20MA(20.40)={ma20_in_html}")

    # ------------------------------------------------------------------
    # 2. INSTITUTIONAL FLOWS (24 DAYS)
    # ------------------------------------------------------------------
    print("\n[2] INSTITUTIONAL FLOWS AUDIT:")
    inst = data["institutional_data"]
    series = inst["daily_series"]
    print(f"  Daily series record count: {len(series)}")
    
    f_shares = [x["foreign_net_shares"] for x in series]
    t_shares = [x["investment_trust_net_shares"] for x in series]
    d_shares = [x["dealer_net_shares"] for x in series]
    tot_shares = [x["total_institutional_net_shares"] for x in series]

    f_lots = [x["foreign_net_lots"] for x in series]
    t_lots = [x["investment_trust_net_lots"] for x in series]
    d_lots = [x["dealer_net_lots"] for x in series]
    tot_lots = [x["total_institutional_net_lots"] for x in series]

    sum_f_shares = sum(f_shares)
    sum_t_shares = sum(t_shares)
    sum_d_shares = sum(d_shares)
    sum_tot_shares = sum(tot_shares)

    sum_f_lots = sum(f_lots)
    sum_t_lots = sum(t_lots)
    sum_d_lots = sum(d_lots)
    sum_tot_lots = sum(tot_lots)

    print(f"  Exact Shares: Foreign={sum_f_shares:,}, Trust={sum_t_shares:,}, Dealer={sum_d_shares:,}, Total={sum_tot_shares:,}")
    print(f"  Sum Shares in Lots (/1000): Foreign={sum_f_shares/1000.0:,.3f}, Trust={sum_t_shares/1000.0:,.3f}, Dealer={sum_d_shares/1000.0:,.3f}, Total={sum_tot_shares/1000.0:,.3f}")
    print(f"  Sum of Daily Lots: Foreign={sum_f_lots:,.2f}, Trust={sum_t_lots:,.2f}, Dealer={sum_d_lots:,.2f}, Total={sum_tot_lots:,.2f}")
    
    # Check component sum in lots:
    sum_components_shares = sum_f_shares + sum_t_shares + sum_d_shares
    print(f"  Component Shares Sum (F+T+D): {sum_components_shares:,} (equals Total Shares: {sum_components_shares == sum_tot_shares})")
    
    # Rounded lots reported in summary:
    rep_f = inst.get("foreign_investors_net_lots")
    rep_t = inst.get("investment_trust_net_lots")
    rep_d = inst.get("dealer_net_lots")
    rep_tot = inst.get("total_institutional_net_lots")
    rep_f1m = inst.get("foreign_net_1m")

    print(f"  Reported Summary in JSON:")
    print(f"    foreign_investors_net_lots: {rep_f}")
    print(f"    investment_trust_net_lots:  {rep_t}")
    print(f"    dealer_net_lots:            {rep_d}")
    print(f"    total_institutional_net_lots: {rep_tot}")
    print(f"    foreign_net_1m:             {rep_f1m}")

    print(f"  Mathematical check: {rep_f} + {rep_t} + {rep_d} = {rep_f + rep_t + rep_d} vs {rep_tot}")
    
    # Check if the cumulative values appear in HTML:
    f_in_html = str(rep_f) in html or f"{rep_f:,}" in html
    t_in_html = str(rep_t) in html or f"{rep_t:,}" in html
    d_in_html = str(rep_d) in html or f"{rep_d:,}" in html
    tot_in_html = str(rep_tot) in html or f"{rep_tot:,}" in html
    print(f"  Cumulative Values in HTML:")
    print(f"    Foreign ({rep_f}): {f_in_html}")
    print(f"    Trust ({rep_t}): {t_in_html}")
    print(f"    Dealer ({rep_d}): {d_in_html}")
    print(f"    Total ({rep_tot}): {tot_in_html}")

    # Check daily additivity across all 24 days:
    daily_additive_errors = 0
    for i, x in enumerate(series):
        fs = x["foreign_net_shares"]
        ts = x["investment_trust_net_shares"]
        ds = x["dealer_net_shares"]
        tots = x["total_institutional_net_shares"]
        if fs + ts + ds != tots:
            daily_additive_errors += 1
            print(f"    Daily share additivity mismatch on {x['date']}: {fs} + {ts} + {ds} != {tots}")
    print(f"  Daily Share Additivity Errors across 24 days: {daily_additive_errors}")

    # ------------------------------------------------------------------
    # 3. REVENUES & YOY (2026 9M vs 2025 9M)
    # ------------------------------------------------------------------
    print("\n[3] REVENUE & YOY AUDIT:")
    ops = data["operational_data"]
    revs_2026 = ops["monthly_revenue_2026"]
    m_revs = [m["revenue_ntd"] for m in revs_2026]
    tot_2026 = sum(m_revs)
    expected_2026 = 19672560000
    print(f"  2026 Jan-Sep Revenues: {[f'{x:,}' for x in m_revs]}")
    print(f"  2026 9M Total Sum = {tot_2026:,} (Expected: {expected_2026:,}, Match: {tot_2026 == expected_2026})")

    # 2025 Jan-Sep:
    tot_2025 = 15557136000
    # YoY %:
    diff = tot_2026 - tot_2025
    yoy_raw = (Decimal(str(diff)) / Decimal(str(tot_2025))) * Decimal("100")
    yoy_halfup = float(yoy_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    print(f"  2025 9M Total = {tot_2025:,}")
    print(f"  Difference = {diff:,}")
    print(f"  Raw YoY% = {yoy_raw}")
    print(f"  Half-Up Rounded YoY% = {yoy_halfup}% (Reported in JSON: {ops.get('nine_month_yoy_growth_pct')}%)")
    
    # Q1 Sum (Jan + Feb + Mar):
    q1_sum = sum(m_revs[:3])
    print(f"  Q1 2026 Sum = {q1_sum:,} (~{q1_sum/1e9:.2f}B)")

    # ------------------------------------------------------------------
    # 4. QUARTERLY EPS, TTM EPS, P/E, NAV DISCOUNT
    # ------------------------------------------------------------------
    print("\n[4] EPS, P/E, NAV & DISCOUNT AUDIT:")
    qtrs = ops["quarterly_financials"]
    for q in qtrs:
        print(f"  Quarter {q['quarter']}: EPS = {q['eps']}, GM% = {q['gross_margin_pct']}%")
    
    eps_vals = [Decimal(str(q["eps"])) for q in qtrs]
    ttm_eps_calc = sum(eps_vals)
    print(f"  TTM EPS Sum: {' + '.join(str(e) for e in eps_vals)} = {ttm_eps_calc} (Reported: {ops.get('ttm_eps')})")

    # P/E Ratio:
    price = Decimal("20.50")
    pe_raw = price / ttm_eps_calc
    pe_halfup = float(pe_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_per = data["valuation_data"]["current_per"]
    print(f"  Price = {price}, TTM EPS = {ttm_eps_calc}")
    print(f"  P/E Raw = {pe_raw:.6f}, Half-Up Rounded = {pe_halfup}x, Reported in JSON = {reported_per}x")

    # NAV & Discount:
    nav = Decimal(str(data["valuation_data"]["nav_per_share"]))
    discount_raw = ((nav - price) / nav) * Decimal("100")
    discount_halfup = float(discount_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_discount = data["valuation_data"]["discount_to_nav_pct"]
    print(f"  NAV per share = {nav}")
    print(f"  Discount Raw = {discount_raw:.6f}%, Half-Up Rounded = {discount_halfup}%, Reported in JSON = {reported_discount}%")

    # P/B Ratio:
    pb_raw = price / nav
    pb_halfup = float(pb_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    reported_pbr = data["valuation_data"]["current_pbr"]
    print(f"  P/B Raw = {pb_raw:.6f}, Half-Up Rounded = {pb_halfup}x, Reported in JSON = {reported_pbr}x")

    # ------------------------------------------------------------------
    # 5. HTML REPORT ANALYSIS
    # ------------------------------------------------------------------
    print("\n[5] HTML REPORT ADVERSARIAL INSPECTION:")
    checks = [
        ("Closing price NT$ 20.50", r"20\.50"),
        ("5MA 20.37", r"20\.37"),
        ("10MA 20.30", r"20\.30|20\.3"),
        ("20MA 20.40", r"20\.40|20\.4"),
        ("1M High 21.55", r"21\.55"),
        ("1M Low 19.80", r"19\.80|19\.8"),
        ("Foreign shareholding 10.84%", r"10\.84\s*%"),
        ("Margin balance 4,195", r"4[,.]?195"),
        ("Short balance 18", r"\b18\b"),
        ("9M Revenue 19.67B / 19,672,560,000", r"196\.7|19\.67|19,672,560"),
        ("9M YoY +26.45%", r"26\.45\s*%"),
        ("Q1 Handover 11.15B", r"11\.15"),
        ("TTM EPS NT$ 2.88", r"2\.88"),
        ("Q1 Peak EPS 1.21", r"1\.21"),
        ("PER 7.14x", r"7\.14"),
        ("PBR 0.74x", r"0\.74"),
        ("NAV NT$ 27.67", r"27\.67"),
        ("NAV Discount 26% / 25.91%", r"25\.91\s*%|26\s*%"),
        ("Target Price NT$ 24.50", r"24\.50"),
        ("Rating ACCUMULATE / OUTPERFORM", r"ACCUMULATE"),
        ("Dividend Yield 5.85%", r"5\.85\s*%"),
    ]
    for label, pattern in checks:
        matched = bool(re.search(pattern, html))
        print(f"  [{'PASS' if matched else 'FAIL'}] {label}: {'Found' if matched else 'NOT FOUND'}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
