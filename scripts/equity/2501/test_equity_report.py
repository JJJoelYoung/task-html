#!/usr/bin/env python3
"""
Independent E2E Opaque-Box Test Suite & Diagnostic Runner
Project: 2501 Cathay Real Estate (國泰建設) Equity Research Report

Verifies:
- Tier 1: Feature Coverage (Pricing, Volume, MAs, Institutional Flow, Margin, Revenue, Margins, Valuation, Catalysts & Risks)
- Tier 2: Boundary & Corner Cases (Zero NaN/undefined/placeholders, Mathematical Consistency, Tabular Numerals, Offline Durability)
- Tier 3: Hallmark Design & Layout (Typography, OKLCH Emerald Hue ~155, SVG Chart-Table Co-location, Responsive CSS, Print Rules)
- Tier 4: Real-World Acceptance Scenarios (Institutional Masthead, Rating, Target Price NT$24.50, IFRS 15 Accounting Note, DOM Integrity)
"""

import sys
import os
import re
import json
import argparse
import unittest
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple, Optional

# --- Paths & Configuration ---
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data_2501.json"
HTML_PATH = BASE_DIR / "2501_Cathay_Real_Estate_Equity_Report.html"

# Terminal Formatting
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def strip(cls, text: str) -> str:
        return re.sub(r"\033\[[0-9;]*m", "", text)


class AssertionCollector:
    """Collects individual assertion results for granular tier reporting."""
    def __init__(self, tier: str, name: str):
        self.tier = tier
        self.name = name
        self.assertions_run = 0
        self.failures: List[str] = []
        self.skipped_reason: Optional[str] = None

    def assert_true(self, condition: bool, message: str):
        self.assertions_run += 1
        if not condition:
            self.failures.append(message)

    def assert_almost_equal(self, actual: float, expected: float, tolerance: float, message: str):
        self.assertions_run += 1
        diff = abs(actual - expected)
        if diff > tolerance:
            self.failures.append(f"{message} (Expected {expected} +/- {tolerance}, got {actual}, diff {diff:.4f})")

    def assert_in(self, needle: Any, haystack: Any, message: str):
        self.assertions_run += 1
        if needle not in haystack:
            self.failures.append(f"{message} (Target '{needle}' not found)")

    def assert_regex(self, pattern: str, text: str, message: str, flags=0):
        self.assertions_run += 1
        if not re.search(pattern, text, flags):
            self.failures.append(f"{message} (Pattern /{pattern}/ did not match)")

    def skip(self, reason: str):
        self.skipped_reason = reason


# --- Tier 1: Feature Coverage Validators ---

def validate_data_tier1(data: Dict[str, Any], col: AssertionCollector):
    """Validates Tier 1 Feature Coverage on structured dataset (data_2501.json)."""
    # Stock identity & core metadata
    col.assert_true(data.get("stock_id") == "2501", "Stock ID must be '2501'")
    stock_name = data.get("stock_name", "")
    col.assert_true("Cathay" in stock_name or "國泰" in stock_name, "Stock name must reference Cathay / 國泰")
    target_price = float(data.get("target_price", 0))
    col.assert_almost_equal(target_price, 24.50, 0.05, "Target price must be NT$24.50")
    rating = str(data.get("rating", "")).upper()
    col.assert_true("ACCUMULATE" in rating or "OUTPERFORM" in rating or "逢低布局" in rating, 
                    "Rating must be ACCUMULATE / OUTPERFORM / 逢低布局")

    # 1. Price & Volume
    mkt = data.get("market_data", {})
    col.assert_almost_equal(float(mkt.get("close", 0)), 20.50, 0.05, "Closing price must be NT$20.50")
    col.assert_almost_equal(float(mkt.get("month_high", 0)), 21.55, 0.05, "1-month high must be NT$21.55")
    col.assert_almost_equal(float(mkt.get("month_low", 0)), 19.80, 0.05, "1-month low must be NT$19.80")
    col.assert_almost_equal(float(mkt.get("ma5", 0)), 20.37, 0.15, "5MA must be ~20.37")
    col.assert_almost_equal(float(mkt.get("ma10", 0)), 20.30, 0.15, "10MA must be ~20.30")
    col.assert_almost_equal(float(mkt.get("ma20", 0)), 20.40, 0.15, "20MA must be ~20.40")

    daily = mkt.get("daily_series", [])
    col.assert_true(len(daily) >= 20, f"Daily series must contain >= 20 trading days, found {len(daily)}")

    # 2. Institutional Flow & Margin Balances
    inst = data.get("institutional_data", {})
    foreign_pct = float(inst.get("foreign_ownership_pct", 0))
    col.assert_almost_equal(foreign_pct, 10.84, 0.3, "Foreign ownership % must be ~10.84%")
    margin_bal = int(inst.get("margin_balance_lots", 0))
    col.assert_true(4000 <= margin_bal <= 4500, f"Margin balance lots should be ~4195, got {margin_bal}")
    short_bal = int(inst.get("short_balance_lots", 0))
    col.assert_true(10 <= short_bal <= 50, f"Short balance lots should be ~18, got {short_bal}")

    # 3. Monthly Revenue & Profitability
    ops = data.get("operational_data", {})
    monthly_revs = ops.get("monthly_revenue_2026", [])
    col.assert_true(len(monthly_revs) >= 9, f"2026 monthly revenues must have at least 9 months, got {len(monthly_revs)}")
    
    total_rev_9m = float(ops.get("nine_month_revenue_total", 0))
    col.assert_almost_equal(total_rev_9m, 19672560000, 100000000, "9-month revenue total must be ~NT$19.67B")
    yoy_pct = float(ops.get("nine_month_yoy_growth_pct", 0))
    col.assert_almost_equal(yoy_pct, 26.45, 0.5, "9-month YoY revenue growth must be ~26.45%")

    quarters = ops.get("quarterly_financials", [])
    col.assert_true(len(quarters) >= 4, f"Latest quarterly financials must contain 4 quarters, got {len(quarters)}")
    ttm_eps = sum(float(q.get("eps", 0)) for q in quarters[-4:])
    col.assert_almost_equal(ttm_eps, 2.88, 0.05, f"TTM EPS must sum to NT$2.88, got {ttm_eps}")

    # 4. Valuation Multiples & Ranges
    val = data.get("valuation_data", {})
    col.assert_almost_equal(float(val.get("current_per", 0)), 7.14, 0.1, "Current PER must be ~7.14x")
    col.assert_almost_equal(float(val.get("current_pbr", 0)), 0.74, 0.05, "Current PBR must be ~0.74x")
    col.assert_almost_equal(float(val.get("dividend_yield", 0)), 5.85, 0.3, "Dividend yield must be ~5.85%")

    hist_per = val.get("historical_per_range", {})
    col.assert_true(hist_per.get("min", 0) > 0 and hist_per.get("max", 0) > hist_per.get("min", 0), 
                    "Historical PER range must have valid min and max")
    hist_pbr = val.get("historical_pbr_range", {})
    col.assert_true(hist_pbr.get("min", 0) > 0 and hist_pbr.get("max", 0) > hist_pbr.get("min", 0), 
                    "Historical PBR range must have valid min and max")


def validate_html_tier1(html: str, col: AssertionCollector):
    """Validates Tier 1 Feature Coverage on HTML report content and text."""
    # 1. Price & Volume presence
    col.assert_regex(r"20\.50|20\.5", html, "HTML must display closing price 20.50")
    col.assert_regex(r"21\.55", html, "HTML must display 1-month high 21.55")
    col.assert_regex(r"19\.80|19\.8", html, "HTML must display 1-month low 19.80")
    col.assert_regex(r"(5\s*MA|MA\s*5|週線)", html, "HTML must reference 5MA")
    col.assert_regex(r"(10\s*MA|MA\s*10|雙週線)", html, "HTML must reference 10MA")
    col.assert_regex(r"(20\s*MA|MA\s*20|月線)", html, "HTML must reference 20MA")

    # 2. Institutional & Margin Flow presence
    col.assert_regex(r"10\.84\s*%", html, "HTML must report foreign shareholding ~10.84%")
    col.assert_regex(r"4[,.]?195", html, "HTML must report margin balance 4,195 lots")
    col.assert_regex(r"18", html, "HTML must report short balance ~18 lots")
    col.assert_regex(r"(-3[,.]?099|3[,.]?099\s*張|3[,.]?099\s*lots)", html, 
                     "HTML must display cumulative institutional net flow (-3,099 lots / 3,099 張)")
    col.assert_regex(r"(外資|Foreign)", html, "HTML must include Foreign Investors")
    col.assert_regex(r"(投信|Investment Trust)", html, "HTML must include Investment Trust")
    col.assert_regex(r"(自營商|Dealer)", html, "HTML must include Dealers")

    # 3. Monthly Revenue YoY & 4-Quarter Profitability
    col.assert_regex(r"19[.,]67|19[,.]672|196\.7", html, "HTML must display 9M revenue ~19.67B")
    col.assert_regex(r"26\.45\s*%|26\.5\s*%", html, "HTML must display 9M revenue YoY growth ~26.45%")
    col.assert_regex(r"11[.,]15|11[,.]151", html, "HTML must display Q1 handover peak ~11.15B")
    col.assert_regex(r"2\.88", html, "HTML must display TTM EPS 2.88")
    col.assert_regex(r"1\.21", html, "HTML must display 2026 Q1 peak EPS 1.21")

    # 4. Valuation Assessment
    col.assert_regex(r"7\.14", html, "HTML must display current PER 7.14x")
    col.assert_regex(r"0\.74", html, "HTML must display current PBR 0.74x")
    col.assert_regex(r"5\.85\s*%", html, "HTML must display dividend yield ~5.85%")

    # 5. Bullish Catalysts & Downside Risks
    col.assert_regex(r"(國泰|霖園|三井工程|品牌溢價|低借貸成本|預售|完工交屋)", html, 
                     "HTML must itemize bullish catalysts (brand, Lin-Yuan, San-Jing, financing)")
    col.assert_regex(r"(第七波|信用管制|平均地權條例|銀行法\s*72-2|通膨|營造成本)", html, 
                     "HTML must itemize downside risks (7th wave credit controls, Average Land Rights Act, inflation)")


# --- Tier 2: Boundary & Corner Cases ---

def validate_tier2_boundaries(data: Optional[Dict[str, Any]], html: Optional[str], col: AssertionCollector):
    """Validates Tier 2: Boundary conditions, zero placeholders, math integrity, and offline robustness."""
    if html:
        # T2.1: Zero undefined/NaN/TODO/placeholder tokens
        col.assert_true(not bool(re.search(r"\bundefined\b", html)), "HTML must not contain 'undefined' token")
        col.assert_true(not bool(re.search(r"\bNaN\b", html)), "HTML must not contain 'NaN' token")
        col.assert_true(not bool(re.search(r"\b(TODO|FIXME|TBD|\[placeholder\])\b", html, re.IGNORECASE)), 
                        "HTML must not contain TODO/FIXME/TBD/placeholder tokens")
        col.assert_true(not bool(re.search(r"\{\{.*?\}\}", html)), "HTML must not contain unresolved template tokens '{{...}}'")
        col.assert_true(not bool(re.search(r"\bN/A%\b", html)), "HTML must not contain 'N/A%' values")

        # T2.3: Offline Durability & Self-contained Assets
        col.assert_true(not bool(re.search(r'src=["\']file://', html, re.IGNORECASE)), "HTML must not reference local file:// URIs")
        col.assert_true(not bool(re.search(r'href=["\']file://', html, re.IGNORECASE)), "HTML must not link to local file:// URIs")
        
        # Verify SVGs are inline and robust
        svg_matches = re.findall(r"<svg[\s\S]*?</svg>", html, re.IGNORECASE)
        col.assert_true(len(svg_matches) >= 4, f"HTML must contain at least 4 inline SVG charts, found {len(svg_matches)}")

        # T2.6: SVG Geometry Sanity — Non-negative Y Coordinates for all <rect> and <text>
        svg_y_matches = list(re.finditer(r'<(rect|text)\b[^>]*\by\s*=\s*["\'](-?[0-9.]+)["\']', html, re.IGNORECASE))
        negative_y = [(m.group(1), float(m.group(2))) for m in svg_y_matches if float(m.group(2)) < 0]
        col.assert_true(len(negative_y) == 0, 
                        f"All SVG <rect> and <text> elements must have non-negative Y coordinates (y >= 0), found {len(negative_y)} negative occurrences: {negative_y[:5]}")

        # T2.4: Tabular Numeral Formatting in CSS
        col.assert_regex(r"tabular-nums|tnum", html, "CSS must declare 'tabular-nums' or 'tnum' for financial numbers")

    if data:
        # T2.2: Mathematical Consistency
        mkt = data.get("market_data", {})
        close = float(mkt.get("close", 0))
        high = float(mkt.get("month_high", 0))
        low = float(mkt.get("month_low", 0))
        col.assert_true(low <= close <= high, f"Mathematical bound failure: low ({low}) <= close ({close}) <= high ({high})")

        # Moving average validation from daily series
        daily = mkt.get("daily_series", [])
        if len(daily) >= 20:
            closes = [float(d.get("close", 0)) for d in daily]
            calc_ma5 = sum(closes[-5:]) / 5.0
            calc_ma10 = sum(closes[-10:]) / 10.0
            calc_ma20 = sum(closes[-20:]) / 20.0
            col.assert_almost_equal(float(mkt.get("ma5", 0)), calc_ma5, 0.1, "5MA calculation matches latest 5 close prices")
            col.assert_almost_equal(float(mkt.get("ma10", 0)), calc_ma10, 0.1, "10MA calculation matches latest 10 close prices")
            col.assert_almost_equal(float(mkt.get("ma20", 0)), calc_ma20, 0.1, "20MA calculation matches latest 20 close prices")

        # Monthly Revenue 9M sum check (handles both revenue_ntd and revenue keys)
        ops = data.get("operational_data", {})
        monthly_revs = ops.get("monthly_revenue_2026", [])
        if len(monthly_revs) >= 9:
            rev_sum = sum(float(m.get("revenue_ntd", m.get("revenue", 0))) for m in monthly_revs[:9])
            reported_sum = float(ops.get("nine_month_revenue_total", 0))
            col.assert_almost_equal(reported_sum, rev_sum, 1000.0, "9-month revenue total must equal sum of 9 months")

        # Quarterly Gross Margin and EPS consistency
        quarters = ops.get("quarterly_financials", [])
        if len(quarters) >= 4:
            ttm_sum = sum(float(q.get("eps", 0)) for q in quarters[-4:])
            col.assert_almost_equal(ttm_sum, 2.88, 0.05, "Quarterly EPS sum equals TTM EPS NT$2.88")
            for q in quarters[-4:]:
                rev = float(q.get("revenue_ntd", q.get("revenue", 0)))
                gp = float(q.get("gross_profit_ntd", q.get("gross_profit", 0)))
                gm_pct = float(q.get("gross_margin_pct", q.get("gross_margin", 0)))
                if rev > 0 and gp > 0:
                    calc_gm = (gp / rev) * 100.0
                    col.assert_almost_equal(gm_pct, calc_gm, 0.15, f"Gross margin % for {q.get('quarter')} matches GP/Rev")

        # T2.5: Zero division guards & range sanity
        val = data.get("valuation_data", {})
        per = float(val.get("current_per", 0))
        pbr = float(val.get("current_pbr", 0))
        col.assert_true(per > 0 and per < 100, f"PER ({per}) must be reasonable positive number")
        col.assert_true(pbr > 0 and pbr < 10, f"PBR ({pbr}) must be reasonable positive number")


# --- Tier 3: Hallmark Design & Layout ---

def validate_tier3_hallmark(html: str, col: AssertionCollector):
    """Validates Tier 3: Hallmark v2.0.0 design principles, typography, OKLCH palette, responsiveness, and print."""
    # T3.1: Typography Check
    col.assert_regex(r"(Plus\s*Jakarta\s*Sans|Host\s*Grotesk)", html, 
                     "Typography: display font must be Plus Jakarta Sans or approved editorial sans")
    col.assert_regex(r"Newsreader", html, 
                     "Typography: body font must feature Newsreader literary serif")
    col.assert_regex(r"(IBM\s*Plex\s*Mono|Atkinson\s*Hyperlegible\s*Mono)", html, 
                     "Typography: financial monospace font must feature IBM Plex Mono or Atkinson Hyperlegible Mono")

    # T3.1: OKLCH Emerald Green Color System (hue ~155)
    col.assert_regex(r"oklch\(", html, "Design system must declare OKLCH color-scheme tokens")
    col.assert_regex(r"oklch\([^)]*15[0-9](\.[0-9]+)?\s*\)|#0a4b37|#00824b", html, 
                     "Color system must declare Cathay Emerald signature accent around hue 155")

    # T3.2: Chart-Table Co-Location (All visual charts must have corresponding structured tables)
    tables = re.findall(r"<table[\s\S]*?</table>", html, re.IGNORECASE)
    col.assert_true(len(tables) >= 4, f"Hallmark co-location: must contain at least 4 data tables, found {len(tables)}")
    
    # Check that each table contains proper accessibility & data elements
    for idx, table in enumerate(tables[:4], 1):
        col.assert_true("<th" in table and "<td" in table, f"Table {idx} must contain proper <th> and <td> tags")

    # T3.3: Taiwan Market Equity Color Semantics
    # red for rise / up, green for fall / down, or explicit legend explaining directional glyphs
    col.assert_regex(r"(▲|▼|tw-rise|tw-fall|漲|跌|rise|fall)", html, 
                     "Taiwan market directional semantics (▲/▼ or rise/fall tokens) must be present")

    # T3.4: Responsive Media Queries
    col.assert_regex(r"@media\s*\([^{}]*max-width:[^{}]*\)", html, 
                     "Responsive layout: CSS must define @media (max-width: ...) queries for mobile/tablet")

    # T3.5: Print & PDF Export Stylesheet
    col.assert_regex(r"@media\s*print", html, "CSS must define '@media print' stylesheet for PDF export")
    col.assert_regex(r"(break-inside:\s*avoid|page-break-inside:\s*avoid)", html, 
                     "Print stylesheet must include 'break-inside: avoid' for multi-page print durability")


# --- Tier 4: Real-World Scenarios & Institutional Acceptance ---

class DomStructureParser(HTMLParser):
    """Lightweight pure-standard-library DOM validator."""
    def __init__(self):
        super().__init__()
        self.tags_found = set()
        self.headers_count = 0
        self.sections_count = 0
        self.titles = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        self.tags_found.add(tag.lower())
        if tag.lower() in ("h1", "h2", "h3"):
            self.headers_count += 1
        elif tag.lower() == "section":
            self.sections_count += 1
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.titles.append(data.strip())


def validate_tier4_institutional(html: str, col: AssertionCollector):
    """Validates Tier 4: Real-World Scenarios, Institutional Analyst Metadata, and DOM Hierarchy."""
    # T4.1: Institutional Masthead & Investment Thesis Callout
    col.assert_regex(r"NT\$\s*24\.50|24\.50\s*元|24\.5", html, "Institutional target price NT$24.50 must be featured")
    col.assert_regex(r"(ACCUMULATE|OUTPERFORM|逢低布局|優於大盤)", html, 
                     "Institutional investment rating (ACCUMULATE / OUTPERFORM) must be clearly featured")
    col.assert_regex(r"2026-11-(06|08|09)|2026\s*年\s*11\s*月", html, "Analyst report publication date badge must be present")

    # T4.2: Educational Callout on IFRS 15 Completion & Handover Accounting
    col.assert_regex(r"(IFRS\s*15|完工交屋認列法|完工認列|point-in-time)", html, 
                     "Report must educate readers on IFRS 15 completion/handover accounting explaining revenue lumpiness")

    # T4.2: Full DOM Hierarchy Parse
    parser = DomStructureParser()
    try:
        parser.feed(html)
        col.assert_true("html" in parser.tags_found, "DOM must contain root <html>")
        col.assert_true("head" in parser.tags_found, "DOM must contain <head>")
        col.assert_true("body" in parser.tags_found, "DOM must contain <body>")
        col.assert_true("header" in parser.tags_found, "DOM must contain <header> masthead")
        col.assert_true(parser.sections_count >= 4, f"DOM must contain at least 4 semantic <section> blocks, found {parser.sections_count}")
        col.assert_true(parser.headers_count >= 4, f"DOM must contain proper heading hierarchy (h1/h2/h3), found {parser.headers_count}")
        col.assert_true(len(parser.titles) > 0 and len(parser.titles[0]) > 0, f"Page title must be populated: {parser.titles}")
    except Exception as e:
        col.assert_true(False, f"DOM Parsing failed with error: {str(e)}")


# --- Synthetic Self-Validation Mock Generator ---

def get_synthetic_mock_data() -> Dict[str, Any]:
    """Generates synthetic data matching PROJECT.md interface contract for suite self-validation."""
    return {
        "stock_id": "2501",
        "stock_name": "Cathay Real Estate (國泰建設)",
        "snapshot_date": "2026-11-06",
        "rating": "ACCUMULATE / OUTPERFORM",
        "target_price": 24.50,
        "market_data": {
            "close": 20.50,
            "ma5": 20.37,
            "ma10": 20.30,
            "ma20": 20.40,
            "month_high": 21.55,
            "month_low": 19.80,
            "daily_series": [{"date": f"2026-10-{i:02d}", "close": 20.30 + (i % 3) * 0.1, "volume": 4000} for i in range(1, 25)]
        },
        "institutional_data": {
            "foreign_net_1m": -3099,
            "foreign_ownership_pct": 10.84,
            "margin_balance_lots": 4195,
            "short_balance_lots": 18,
            "daily_series": []
        },
        "operational_data": {
            "monthly_revenue_2026": [
                {"year": 2026, "month": 1, "revenue_ntd": 3195793000},
                {"year": 2026, "month": 2, "revenue_ntd": 3430775000},
                {"year": 2026, "month": 3, "revenue_ntd": 4524900000},
                {"year": 2026, "month": 4, "revenue_ntd": 1122755000},
                {"year": 2026, "month": 5, "revenue_ntd": 950553000},
                {"year": 2026, "month": 6, "revenue_ntd": 1211334000},
                {"year": 2026, "month": 7, "revenue_ntd": 2481445000},
                {"year": 2026, "month": 8, "revenue_ntd": 1630282000},
                {"year": 2026, "month": 9, "revenue_ntd": 1124723000}
            ],
            "nine_month_revenue_total": 19672560000,
            "nine_month_yoy_growth_pct": 26.45,
            "quarterly_financials": [
                {"quarter": "2025Q3", "eps": 0.53, "gross_margin_pct": 28.38, "revenue_ntd": 4183875000, "gross_profit_ntd": 1187287000},
                {"quarter": "2025Q4", "eps": 0.92, "gross_margin_pct": 26.51, "revenue_ntd": 8732098000, "gross_profit_ntd": 2314820000},
                {"quarter": "2026Q1", "eps": 1.21, "gross_margin_pct": 24.15, "revenue_ntd": 11151468000, "gross_profit_ntd": 2692800000},
                {"quarter": "2026Q2", "eps": 0.22, "gross_margin_pct": 28.06, "revenue_ntd": 3284642000, "gross_profit_ntd": 921600000}
            ]
        },
        "valuation_data": {
            "current_per": 7.14,
            "current_pbr": 0.74,
            "dividend_yield": 5.85,
            "historical_per_range": {"min": 5.58, "max": 22.22, "median": 11.58},
            "historical_pbr_range": {"min": 0.72, "max": 1.83, "median": 0.91}
        }
    }


def get_synthetic_mock_html() -> str:
    """Generates synthetic minimal HTML satisfying all Hallmark and contract rules for self-validation."""
    return """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>2501 國泰建設 (Cathay Real Estate) 360度綜合研究分析報告</title>
  <style>
    :root {
      --color-paper: oklch(98.5% 0.005 85);
      --color-ink: oklch(18% 0.025 240);
      --color-accent: oklch(38% 0.120 155);
      --color-tw-rise: oklch(62% 0.22 29);
      --color-tw-fall: oklch(65% 0.20 150);
      font-family: "Newsreader", serif;
    }
    h1, h2, h3 { font-family: "Plus Jakarta Sans", sans-serif; }
    .num, td.num { font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
    @media (max-width: 768px) { .container { padding: 16px; } }
    @media print { .card { break-inside: avoid; } }
  </style>
</head>
<body>
  <header>
    <h1>2501 國泰建設 (Cathay Real Estate)</h1>
    <div class="badge">Date: 2026-11-06 | Rating: ACCUMULATE / OUTPERFORM | Target Price: NT$ 24.50</div>
  </header>
  <main>
    <section>
      <h2>價量結構分析 (Price & Volume)</h2>
      <p>收盤價 NT$ 20.50，月最高 21.55，月最低 19.80。5MA 20.37，10MA 20.30，20MA 20.40。成交量 4,550 張 (▲ +1.5%)。</p>
      <svg width="400" height="200"><rect width="400" height="200" fill="#e0e0e0"/></svg>
      <table><thead><tr><th>指標</th><th>數值</th></tr></thead><tbody><tr><td>收盤價</td><td class="num">20.50</td></tr></tbody></table>
    </section>
    <section>
      <h2>法人籌碼與信用交易 (Institutional Flow)</h2>
      <p>外資持股比率 10.84%，三大法人近月累計淨買賣超 -3,099 張（外資、投信、自營商），融資餘額 4,195 張，融券餘額 18 張。</p>
      <svg width="400" height="200"><line x1="0" y1="0" x2="400" y2="200" stroke="#000"/></svg>
      <table><thead><tr><th>法人</th><th>籌碼</th></tr></thead><tbody><tr><td>外資</td><td class="num">10.84%</td></tr></tbody></table>
    </section>
    <section>
      <h2>營運獲利與 IFRS 15 完工認列 (Operations & IFRS 15)</h2>
      <p>2026 前 9 月營收 19.67B (19,672百萬元)，年增率 +26.45%，Q1 完工交屋認列高達 11.15B。TTM EPS 2.88 元，26Q1 EPS 1.21 元。</p>
      <p>說明：依據 IFRS 15 完工交屋認列法 (point-in-time)，營建業營收具週期性集中特性。</p>
      <svg width="400" height="200"><circle cx="200" cy="100" r="50" fill="green"/></svg>
      <table><thead><tr><th>月份</th><th>營收</th></tr></thead><tbody><tr><td>9M</td><td class="num">19.67B</td></tr></tbody></table>
    </section>
    <section>
      <h2>估值分析與歷史區間 (Valuation)</h2>
      <p>目前 PER 7.14x，PBR 0.74x，現金殖利率 5.85%。歷史本益比區間 5.58x - 22.22x。</p>
      <svg width="400" height="200"><polyline points="0,0 200,100 400,200"/></svg>
      <table><thead><tr><th>指標</th><th>倍數</th></tr></thead><tbody><tr><td>PER</td><td class="num">7.14</td></tr></tbody></table>
    </section>
    <section>
      <h2>投資利多與潛在風險 (Catalysts & Risks)</h2>
      <p>利多：國泰與霖園集團品牌溢價、三井工程整合營造、低借貸成本優勢、預售完工交屋能見度高。</p>
      <p>風險：中央銀行第七波信用管制、平均地權條例預售轉售限制、銀行法 72-2 房貸限貸水位與營造成本通膨壓力。</p>
    </section>
  </main>
  <footer>
    <p>Cathay Real Estate Equity Research · Hallmark Standard</p>
  </footer>
</body>
</html>
"""


# --- Suite Runner Execution Engine ---

def run_e2e_suite(strict: bool = False, html_only: bool = False, data_only: bool = False, self_test: bool = False) -> int:
    """Main execution engine: runs all opaque-box tests across Tiers 1-4."""
    print(f"\n{Color.BOLD}{Color.CYAN}========================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}  2501 Cathay Real Estate Equity Report — E2E Opaque-Box Test Runner   {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}========================================================================{Color.RESET}\n")

    # Mode detection
    data_exists = DATA_PATH.is_file()
    html_exists = HTML_PATH.is_file()

    print(f"[*] Workspace Root: {BASE_DIR}")
    print(f"[*] data_2501.json: {'FOUND (' + str(DATA_PATH.stat().st_size) + ' bytes)' if data_exists else 'NOT FOUND'}")
    print(f"[*] 2501_Cathay_Real_Estate_Equity_Report.html: {'FOUND (' + str(HTML_PATH.stat().st_size) + ' bytes)' if html_exists else 'NOT FOUND'}")
    print(f"[*] Mode Settings: strict={strict}, html_only={html_only}, data_only={data_only}, self_test={self_test}\n")

    # If neither file exists and self_test not explicitly disabled, run synthetic harness validation
    if not data_exists and not html_exists and not self_test:
        if strict:
            print(f"{Color.RED}[HARD FAILURE] Strict mode enabled: Both deliverables are missing on disk!{Color.RESET}")
            return 1
        else:
            print(f"{Color.YELLOW}[INTERMEDIATE STATUS] Target deliverables not yet created by M1/M2 workers.{Color.RESET}")
            print(f"[*] Automatically triggering suite self-validation harness to verify all check contracts...\n")
            self_test = True

    # Collectors for test suites
    collectors: List[AssertionCollector] = []

    if self_test:
        print(f"{Color.BOLD}[RUNNING SELF-VALIDATION HARNESS]{Color.RESET}")
        mock_data = get_synthetic_mock_data()
        mock_html = get_synthetic_mock_html()

        # Run Tier 1 on mock
        c_t1_d = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.5: Synthetic Data Contract")
        validate_data_tier1(mock_data, c_t1_d)
        collectors.append(c_t1_d)

        c_t1_h = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.6: Synthetic HTML Text Content")
        validate_html_tier1(mock_html, c_t1_h)
        collectors.append(c_t1_h)

        # Run Tier 2 on mock
        c_t2 = AssertionCollector("Tier 2 (Boundary & Corner)", "T2.1-T2.5: Zero Placeholders, Math, Durability")
        validate_tier2_boundaries(mock_data, mock_html, c_t2)
        collectors.append(c_t2)

        # Run Tier 3 on mock
        c_t3 = AssertionCollector("Tier 3 (Hallmark Design)", "T3.1-T3.5: Fonts, OKLCH Emerald, Tables, Media Rules")
        validate_tier3_hallmark(mock_html, c_t3)
        collectors.append(c_t3)

        # Run Tier 4 on mock
        c_t4 = AssertionCollector("Tier 4 (Real-World Scenarios)", "T4.1-T4.2: Institutional Masthead, IFRS 15, DOM Parse")
        validate_tier4_institutional(mock_html, c_t4)
        collectors.append(c_t4)

    else:
        # Load available deliverables
        data_obj: Optional[Dict[str, Any]] = None
        html_str: Optional[str] = None

        if not html_only:
            if data_exists:
                try:
                    with open(DATA_PATH, "r", encoding="utf-8") as f:
                        data_obj = json.load(f)
                except Exception as e:
                    print(f"{Color.RED}[ERROR] Failed to parse data_2501.json: {e}{Color.RESET}")
                    return 1
            elif strict:
                print(f"{Color.RED}[ERROR] data_2501.json is missing in strict mode!{Color.RESET}")
                return 1

        if not data_only:
            if html_exists:
                try:
                    with open(HTML_PATH, "r", encoding="utf-8") as f:
                        html_str = f.read()
                except Exception as e:
                    print(f"{Color.RED}[ERROR] Failed to read HTML report: {e}{Color.RESET}")
                    return 1
            elif strict:
                print(f"{Color.RED}[ERROR] 2501_Cathay_Real_Estate_Equity_Report.html is missing in strict mode!{Color.RESET}")
                return 1

        # Execute Tier 1: Feature Coverage
        c_t1_d = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.5: FinMind Data Completeness (data_2501.json)")
        if data_obj:
            validate_data_tier1(data_obj, c_t1_d)
        else:
            c_t1_d.skip("data_2501.json not available for evaluation")
        collectors.append(c_t1_d)

        c_t1_h = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.6: HTML Report Content Completeness")
        if html_str:
            validate_html_tier1(html_str, c_t1_h)
        else:
            c_t1_h.skip("2501_Cathay_Real_Estate_Equity_Report.html not yet generated (intermediate phase)")
        collectors.append(c_t1_h)

        # Execute Tier 2: Boundary & Corner Cases
        c_t2 = AssertionCollector("Tier 2 (Boundary & Corner)", "T2.1-T2.5: Zero Placeholders, Math Consistency & Durability")
        if data_obj or html_str:
            validate_tier2_boundaries(data_obj, html_str, c_t2)
        else:
            c_t2.skip("Neither data nor HTML available for boundary verification")
        collectors.append(c_t2)

        # Execute Tier 3: Hallmark Design & Layout
        c_t3 = AssertionCollector("Tier 3 (Hallmark Design)", "T3.1-T3.5: Hallmark Tokens, Emerald Palette, SVG & Print")
        if html_str:
            validate_tier3_hallmark(html_str, c_t3)
        else:
            c_t3.skip("2501_Cathay_Real_Estate_Equity_Report.html not yet generated (intermediate phase)")
        collectors.append(c_t3)

        # Execute Tier 4: Real-World Scenarios
        c_t4 = AssertionCollector("Tier 4 (Real-World Scenarios)", "T4.1-T4.2: Institutional Acceptance & DOM Integrity")
        if html_str:
            validate_tier4_institutional(html_str, c_t4)
        else:
            c_t4.skip("2501_Cathay_Real_Estate_Equity_Report.html not yet generated (intermediate phase)")
        collectors.append(c_t4)

    # --- Print Reporting Dashboard ---
    total_assertions = sum(c.assertions_run for c in collectors)
    total_failures = sum(len(c.failures) for c in collectors)
    skipped_count = sum(1 for c in collectors if c.skipped_reason)

    print(f"{Color.BOLD}Test Execution Results by Tier:{Color.RESET}")
    print("-" * 74)

    for c in collectors:
        if c.skipped_reason:
            status = f"{Color.YELLOW}[SKIPPED]{Color.RESET}"
            print(f"  {status} {c.tier:<26} :: {c.name}")
            print(f"           Reason: {c.skipped_reason}")
        elif len(c.failures) == 0:
            status = f"{Color.GREEN}[PASS]{Color.RESET}"
            print(f"  {status} {c.tier:<26} :: {c.name} ({c.assertions_run} assertions)")
        else:
            status = f"{Color.RED}[FAIL]{Color.RESET}"
            print(f"  {status} {c.tier:<26} :: {c.name} ({len(c.failures)} failures in {c.assertions_run} assertions)")
            for fail in c.failures:
                print(f"           {Color.RED}• {fail}{Color.RESET}")

    print("-" * 74)
    print(f"Total Assertions Run : {total_assertions}")
    print(f"Total Failures       : {total_failures}")
    print(f"Suites Skipped       : {skipped_count}")

    if total_failures > 0:
        print(f"\n{Color.RED}{Color.BOLD}RESULT: FAILED ({total_failures} violations detected){Color.RESET}\n")
        return 1
    else:
        print(f"\n{Color.GREEN}{Color.BOLD}RESULT: PASSED (100% of evaluated assertions satisfied){Color.RESET}\n")
        return 0


# --- Standard PyUnit TestCase Integration ---

class TestEquityReportDataContract(unittest.TestCase):
    """Standard unittest wrapper for CI / test discovery."""
    @classmethod
    def setUpClass(cls):
        if not DATA_PATH.is_file():
            raise unittest.SkipTest(f"data_2501.json not yet generated at {DATA_PATH}")
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_tier1_data_completeness(self):
        col = AssertionCollector("Tier 1", "data_2501.json")
        validate_data_tier1(self.data, col)
        self.assertEqual(col.failures, [], f"Data tier 1 failures: {col.failures}")

    def test_tier2_data_math_consistency(self):
        col = AssertionCollector("Tier 2", "data_2501.json math")
        validate_tier2_boundaries(self.data, None, col)
        self.assertEqual(col.failures, [], f"Data tier 2 math failures: {col.failures}")


class TestEquityReportHtmlContract(unittest.TestCase):
    """Standard unittest wrapper for HTML deliverable."""
    @classmethod
    def setUpClass(cls):
        if not HTML_PATH.is_file():
            raise unittest.SkipTest(f"HTML deliverable not yet generated at {HTML_PATH}")
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_tier1_html_content(self):
        col = AssertionCollector("Tier 1", "HTML content")
        validate_html_tier1(self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 1 failures: {col.failures}")

    def test_tier2_html_placeholders_and_durability(self):
        col = AssertionCollector("Tier 2", "HTML placeholders & durability")
        validate_tier2_boundaries(None, self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 2 failures: {col.failures}")

    def test_tier3_hallmark_styling(self):
        col = AssertionCollector("Tier 3", "Hallmark styling")
        validate_tier3_hallmark(self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 3 failures: {col.failures}")

    def test_tier4_institutional_scenarios(self):
        col = AssertionCollector("Tier 4", "Institutional scenarios & DOM")
        validate_tier4_institutional(self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 4 failures: {col.failures}")


# --- Command-Line Entry Point ---

def main():
    parser = argparse.ArgumentParser(
        description="E2E Test Runner for 2501 Cathay Real Estate Hallmark Equity Research Report",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strict", action="store_true", help="Require both data_2501.json and HTML to exist; fail if missing")
    parser.add_argument("--data-only", action="store_true", help="Evaluate only data_2501.json")
    parser.add_argument("--html-only", action="store_true", help="Evaluate only 2501_Cathay_Real_Estate_Equity_Report.html")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic self-test validating the harness itself")

    args = parser.parse_args()
    exit_code = run_e2e_suite(
        strict=args.strict,
        html_only=args.html_only,
        data_only=args.data_only,
        self_test=args.self_test
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
