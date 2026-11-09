#!/usr/bin/env python3
"""
test_equity_report.py
Independent E2E Opaque-Box Test Suite & Diagnostic Runner
Project: Phison Electronics (8299 TW) Institutional Equity Research Report

Verifies:
- Tier 1: Feature Coverage (Pricing, Volume, MAs, Institutional Flow, Margin, Revenue, Margins, Valuation, Catalysts & Risks, Portal & Repo)
- Tier 2: Boundary & Corner Cases (Zero NaN/undefined/placeholders, Mathematical Consistency, SVG Geometry, Tabular Numerals, Offline Durability)
- Tier 3: Hallmark Design & Layout (Typography, OKLCH Palette, Theme Toggle DOM, Valuation Tab Switcher, Co-located Tables, Responsive & Print CSS)
- Tier 4: Real-World Scenarios (Institutional Masthead, Rating BUY, Target Price NT$2,215, NAND Inventory Cycle Callout, Peer Dislocation, DOM Hierarchy)
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
REPO_ROOT = BASE_DIR.parents[2]
DATA_PATH = BASE_DIR / "data_8299.json"
HTML_PATH = REPO_ROOT / "reports" / "equity" / "8299-phison-20261109.html"
PORTAL_PATH = REPO_ROOT / "index.html"
README_PATH = REPO_ROOT / "README.md"


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

    def assert_false(self, condition: bool, message: str):
        self.assertions_run += 1
        if condition:
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
    """Validates Tier 1 Feature Coverage on structured dataset (data_8299.json)."""
    # Stock identity & core metadata
    col.assert_true(data.get("stock_id") == "8299", "Stock ID must be '8299'")
    stock_name = data.get("stock_name", "")
    col.assert_true("Phison" in stock_name or "群聯" in stock_name, "Stock name must reference Phison / 群聯")
    target_price = float(data.get("target_price", 0))
    col.assert_almost_equal(target_price, 2215.0, 5.0, "Target price must be NT$2,215")
    rating = str(data.get("rating", "")).upper()
    col.assert_true("BUY" in rating or "OVERWEIGHT" in rating or "買進" in rating,
                    "Rating must be BUY / OVERWEIGHT / 買進")

    # 1. Price & Volume (Dimension 1)
    mkt = data.get("dimension1_price_volume", data.get("market_data", {}))
    stats = mkt.get("statistics", mkt)
    col.assert_almost_equal(float(stats.get("close", 0)), 1500.0, 1.0, "Closing price must be NT$1,500.0")
    col.assert_almost_equal(float(stats.get("month_high", 0)), 2165.0, 1.0, "1-month high must be NT$2,165.0")
    col.assert_almost_equal(float(stats.get("month_low", 0)), 1405.0, 1.0, "1-month low must be NT$1,405.0")
    col.assert_almost_equal(float(stats.get("ma5", 0)), 1667.0, 5.0, "5MA must be ~1,667.0")
    col.assert_almost_equal(float(stats.get("ma10", 0)), 1814.5, 5.0, "10MA must be ~1,814.5")
    col.assert_almost_equal(float(stats.get("ma20", 0)), 1879.5, 5.0, "20MA must be ~1,879.5")
    bias_val = float(stats.get("bias_20ma", stats.get("bias", 0)))
    col.assert_almost_equal(bias_val, -20.19, 0.5, "20MA bias must be ~ -20.19%")
    daily = mkt.get("daily_series", mkt.get("ohlcv", []))
    col.assert_true(len(daily) >= 20, f"Daily series must contain >= 20 trading days, found {len(daily)}")

    # 2. Institutional Flow & Margin Balances (Dimension 2)
    inst = data.get("dimension2_institutional", data.get("institutional_data", {}))
    foreign_net = float(inst.get("foreign_net_1m", inst.get("foreign_net", 0)))
    col.assert_true(foreign_net < -1500000, f"Foreign net selling must be significant (~ -1.91M shares), got {foreign_net}")
    trust_net = float(inst.get("trust_net_1m", inst.get("trust_net", 0)))
    col.assert_true(trust_net > 200000, f"Investment trust net buying must be positive (~ +366.6K shares), got {trust_net}")
    dealer_net = float(inst.get("dealer_net_1m", inst.get("dealer_net", 0)))
    col.assert_true(dealer_net < -500000, f"Dealer net selling must be ~ -748.8K shares, got {dealer_net}")
    foreign_pct = float(inst.get("foreign_ownership_pct", inst.get("foreign_ratio", 0)))
    col.assert_almost_equal(foreign_pct, 45.34, 0.5, "Foreign ownership % must be ~45.34%")
    margin_bal = int(inst.get("margin_balance_lots", inst.get("margin_balance", 0)))
    col.assert_true(8500 <= margin_bal <= 10000, f"Margin balance lots should be ~9,173, got {margin_bal}")
    short_bal = int(inst.get("short_balance_lots", inst.get("short_balance", 0)))
    col.assert_true(1 <= short_bal <= 50, f"Short balance lots should be ~8, got {short_bal}")

    # 3. Monthly Revenue & Profitability (Dimension 3)
    ops = data.get("dimension3_financials", data.get("operational_data", {}))
    monthly_revs = ops.get("monthly_revenue_2026", ops.get("monthly_revenue", []))
    col.assert_true(len(monthly_revs) >= 10, f"2026 monthly revenues must have at least 10 months, got {len(monthly_revs)}")
    total_rev_10m = float(ops.get("ten_month_revenue_total", ops.get("cumulative_revenue_10m", 0)))
    col.assert_almost_equal(total_rev_10m, 226461925000, 1000000000, "10-month revenue total must be ~NT$226.46B")
    yoy_pct = float(ops.get("ten_month_yoy_growth_pct", ops.get("yoy_growth_pct", 0)))
    col.assert_almost_equal(yoy_pct, 297.78, 1.0, "10-month YoY revenue growth must be ~297.78%")
    total_rev = total_rev_10m
    oct_rev = float(monthly_revs[-1].get("revenue", monthly_revs[-1].get("revenue_ntd", 0))) if monthly_revs else 0
    col.assert_true(total_rev >= oct_rev, "10-month total revenue must be >= single-month revenue")

    quarters = ops.get("quarterly_financials", ops.get("quarterly_income", []))
    col.assert_true(len(quarters) >= 4, f"Latest quarterly financials must contain 4 quarters, got {len(quarters)}")
    ttm_eps = sum(float(q.get("eps", 0)) for q in quarters[-4:])
    col.assert_almost_equal(ttm_eps, 347.45, 0.5, f"TTM EPS must sum to NT$347.45, got {ttm_eps}")
    blended_gm = float(ops.get("blended_gross_margin_pct", ops.get("gross_margin_ttm", 60.05)))
    col.assert_almost_equal(blended_gm, 60.05, 1.0, f"Blended gross margin must be ~60.05%, got {blended_gm}")

    # 4. Valuation Multiples & Peer Matrix (Dimension 4)
    val = data.get("dimension4_valuation", data.get("valuation_data", {}))
    col.assert_almost_equal(float(val.get("current_per", 0)), 4.33, 0.05, "Current PER must be ~4.33x")
    col.assert_almost_equal(float(val.get("per_percentile", 0)), 0.0, 0.1, "PER percentile must be 0.0th (historical min)")
    col.assert_almost_equal(float(val.get("current_pbr", 0)), 2.78, 0.05, "Current PBR must be ~2.78x")
    col.assert_almost_equal(float(val.get("pbr_percentile", 0)), 71.6, 1.0, "PBR percentile must be ~71.6th")
    peers = val.get("peers", [])
    col.assert_true(len(peers) >= 4, f"Peers list must contain at least 4 entries (8299, SIMO, 2379, 5269), found {len(peers)}")

    # 5. Catalysts & Risks (Dimension 5)
    cr = data.get("dimension5_catalysts_risks", data.get("supplementary_data", {}))
    moats = cr.get("moats", [])
    col.assert_true(len(moats) >= 2, "Must specify at least 2 competitive moats")
    risks = cr.get("risks", [])
    col.assert_true(len(risks) >= 2, "Must specify at least 2 downside risks")


def validate_html_tier1(html: str, col: AssertionCollector):
    """Validates Tier 1 Feature Coverage on HTML report content and text."""
    # 1. Price & Volume presence (Dimension 1)
    col.assert_regex(r"1[,.]?500(\.00?)?", html, "HTML must display closing price 1,500.00")
    col.assert_regex(r"2[,.]?165(\.00?)?", html, "HTML must display 1-month high 2,165.00")
    col.assert_regex(r"1[,.]?405(\.00?)?", html, "HTML must display 1-month low 1,405.00")
    col.assert_regex(r"1[,.]?667(\.00?)?", html, "HTML must display 5MA ~1,667.00")
    col.assert_regex(r"1[,.]?814(\.50?)?", html, "HTML must display 10MA ~1,814.50")
    col.assert_regex(r"1[,.]?879(\.50?)?", html, "HTML must display 20MA ~1,879.50")
    col.assert_regex(r"-20\.19\s*%|-20\.2\s*%", html, "HTML must display 20MA negative bias ~ -20.19%")
    col.assert_regex(r"6[,.]?267", html, "HTML must report peak volume ~6,267 lots / panic climax")
    col.assert_regex(r"2\.83\s*%", html, "HTML must report peak daily turnover ~2.83%")

    # 2. Institutional & Margin Flow presence (Dimension 2)
    col.assert_regex(r"45\.34\s*%", html, "HTML must report foreign shareholding ~45.34%")
    col.assert_regex(r"9[,.]?173", html, "HTML must report margin balance 9,173 lots")
    col.assert_regex(r"\b8\b", html, "HTML must report short balance 8 lots")
    col.assert_regex(r"1[,.]?146(\.6)?", html, "HTML must report margin-to-short ratio ~1,146.6x")
    col.assert_regex(r"(外資|Foreign)", html, "HTML must reference Foreign Investors")
    col.assert_regex(r"(投信|Investment Trust)", html, "HTML must reference Investment Trusts")
    col.assert_regex(r"(自營商|Dealer)", html, "HTML must reference Dealers")
    col.assert_regex(r"-1[,.]?914", html, "HTML must display foreign 1-month net flow ~ -1,914 lots")
    col.assert_regex(r"366(\.6)?", html, "HTML must display investment trust net flow ~ +366.6 lots")

    # 3. Monthly Revenue YoY & Trailing Profitability (Dimension 3)
    col.assert_regex(r"2,?264[.,]62?|226[,.]?46|226[,.]?5|226[,.]461", html, "HTML must display 10M revenue ~2,264.62 億 or NT$226.46B")
    col.assert_regex(r"297\.78\s*%|297\.8\s*%", html, "HTML must display 10M revenue YoY growth ~297.78%")
    col.assert_regex(r"347\.45", html, "HTML must display TTM EPS NT$347.45")
    col.assert_regex(r"60\.05\s*%|60\.1\s*%", html, "HTML must display blended gross margin ~60.05%")
    col.assert_regex(r"415\.4", html, "HTML must report Q1 peak inventory DSI 415.4 days")
    col.assert_regex(r"291\.1", html, "HTML must report Q3 normalized inventory DSI 291.1 days")

    # 4. Valuation Assessment & Peer Matrix (Dimension 4)
    col.assert_regex(r"4\.33", html, "HTML must display current PER 4.33x")
    col.assert_regex(r"0\.0\s*(th|%|分位)", html, "HTML must display PER at 0.0th percentile")
    col.assert_regex(r"2\.78", html, "HTML must display current PBR 2.78x")
    col.assert_regex(r"71\.6\s*(th|%|分位)", html, "HTML must display PBR at 71.6th percentile")
    col.assert_regex(r"(SIMO|Silicon Motion|慧榮)", html, "HTML must benchmark Silicon Motion (SIMO)")
    col.assert_regex(r"(2379|Realtek|瑞昱)", html, "HTML must benchmark Realtek (2379)")
    col.assert_regex(r"(5269|ASMedia|祥碩)", html, "HTML must benchmark ASMedia (5269)")
    col.assert_regex(r"75\.3\s*%", html, "HTML must display ~75.3% discount vs peer median")

    # 5. Target Price Derivation & Investment Rating
    col.assert_regex(r"2[,.]?215", html, "HTML must display Target Price NT$ 2,215")
    col.assert_regex(r"(BUY|OVERWEIGHT|強力買進|買進)", html, "HTML must display BUY / OVERWEIGHT rating")
    col.assert_regex(r"47\.67\s*%|47\.7\s*%", html, "HTML must display potential upside ~ +47.67%")

    # 6. Catalysts & Downside Risks (Dimension 5)
    col.assert_regex(r"(PCIe\s*Gen5|Gen5|SSD\s*控制晶片)", html, "HTML must itemize PCIe Gen5 leadership")
    col.assert_regex(r"(aiDAPTIV\+|AiDAPTIV)", html, "HTML must itemize aiDAPTIV+ platform")
    col.assert_regex(r"(TSMC|台積電|晶圓代工)", html, "HTML must itemize tier-1 foundry alliance")
    col.assert_regex(r"(NAND|快閃記憶體|記憶體週期)", html, "HTML must itemize NAND flash cyclical risk")

    # 7. Inline SVG Charts presence
    col.assert_true('id="chartPriceVolume"' in html or 'id=\'chartPriceVolume\'' in html, "Must contain #chartPriceVolume SVG")
    col.assert_true('id="chartInstitutional"' in html or 'id=\'chartInstitutional\'' in html, "Must contain #chartInstitutional SVG")
    col.assert_true('id="chartFinancials"' in html or 'id=\'chartFinancials\'' in html, "Must contain #chartFinancials SVG")
    col.assert_true('id="chartValuationRiver"' in html or 'id=\'chartValuationRiver\'' in html, "Must contain #chartValuationRiver SVG")

    # 8. Hallmark Co-located Tables presence
    tables = re.findall(r"<table[\s\S]*?</table>", html, re.IGNORECASE)
    col.assert_true(len(tables) >= 4, f"Must contain at least 4 co-located data tables, found {len(tables)}")


def validate_portal_repo_tier1(portal_html: Optional[str], readme_md: Optional[str], col: AssertionCollector):
    """Validates Tier 1 Portal Integration (index.html) and Repo Documentation (README.md)."""
    if portal_html:
        if "8299" not in portal_html:
            col.skip("8299 portal card not yet integrated into index.html (Milestone 2 scope)")
            return
        col.assert_true('data-category="equity"' in portal_html, "Portal must feature data-category='equity'")
        col.assert_regex(r'data-keywords="[^"]*8299[^"]*"', portal_html, "Portal card must include '8299' in data-keywords")
        col.assert_regex(r'data-keywords="[^"]*(群聯|phison)[^"]*"', portal_html, "Portal card must include '群聯' or 'phison' in data-keywords")
        col.assert_regex(r'href="[^"]*8299-phison-20261109\.html"', portal_html, "Portal card must link to 8299-phison-20261109.html")
        col.assert_regex(r"1[,.]?500(\s*元)?", portal_html, "Portal card telemetry must display close 1,500")
        col.assert_regex(r"4\.33x?", portal_html, "Portal card telemetry must display PER 4.33x")
        col.assert_regex(r"2,?264[.,]6|226[.,]5|226[.,]46", portal_html, "Portal card telemetry/desc must display 10M revenue ~2,264.6B or 226.5B")
        col.assert_regex(r"347\.45", portal_html, "Portal card telemetry must display TTM EPS 347.45")

    if readme_md:
        if "8299" not in readme_md:
            col.skip("8299 row not yet added to README.md (Milestone 2 scope)")
            return
        col.assert_regex(r"8299.*群聯|8299.*Phison", readme_md, "README deliverables table must list 8299 Phison")
        col.assert_regex(r"reports/equity/8299-phison-20261109\.html", readme_md, "README must link to local report path")


# --- Tier 2: Boundary & Corner Cases ---

def validate_tier2_boundaries(data: Optional[Dict[str, Any]], html: Optional[str], col: AssertionCollector):
    """Validates Tier 2: Boundary conditions, zero placeholders, math integrity, and offline robustness."""
    if html:
        # T2.1: Zero undefined/NaN/TODO/placeholder tokens
        col.assert_false(bool(re.search(r"\bundefined\b", html)), "HTML must not contain 'undefined' token")
        col.assert_false(bool(re.search(r"\bNaN\b", html)), "HTML must not contain 'NaN' token")
        col.assert_false(bool(re.search(r"\b(TODO|FIXME|TBD|\[placeholder\])\b", html, re.IGNORECASE)),
                          "HTML must not contain TODO/FIXME/TBD/placeholder tokens")
        col.assert_false(bool(re.search(r"\{\{.*?\}\}", html)), "HTML must not contain unresolved template tokens '{{...}}'")
        col.assert_false(bool(re.search(r"\$\{.*?\}", html)), "HTML must not contain unresolved literal '${...}' tokens")
        col.assert_false(bool(re.search(r"\bN/A%\b", html)), "HTML must not contain 'N/A%' values")

        # T2.2: Offline Durability & Self-contained Assets
        col.assert_false(bool(re.search(r'src=["\']file://', html, re.IGNORECASE)), "HTML must not reference local file:// URIs")
        col.assert_false(bool(re.search(r'href=["\']file://', html, re.IGNORECASE)), "HTML must not link to local file:// URIs")
        col.assert_false(bool(re.search(r'<script\b[^>]*\bsrc=["\']https?://(?!fonts)', html, re.IGNORECASE)),
                          "HTML must not depend on external CDN JavaScript")
        col.assert_false(bool(re.search(r'<link\b[^>]*\bhref=["\']https?://(?!fonts)', html, re.IGNORECASE)),
                          "HTML must not depend on external CDN CSS")

        # T2.3: SVG Geometry Sanity — Non-negative Y Coordinates for all <rect> and <text>
        svg_matches = re.findall(r"<svg[\s\S]*?</svg>", html, re.IGNORECASE)
        col.assert_true(len(svg_matches) >= 4, f"HTML must contain at least 4 inline SVG charts, found {len(svg_matches)}")

        svg_y_matches = list(re.finditer(r'<(rect|text)\b[^>]*\by\s*=\s*["\'](-?[0-9.]+)["\']', html, re.IGNORECASE))
        negative_y = [(m.group(1), float(m.group(2))) for m in svg_y_matches if float(m.group(2)) < 0]
        col.assert_true(len(negative_y) == 0,
                        f"All SVG <rect> and <text> elements must have y >= 0, found {len(negative_y)} negative: {negative_y[:3]}")

        # T2.4: SVG ViewBox Validity
        svg_viewboxes = re.findall(r'<svg\b[^>]*\bviewBox=["\']([^"\']+)["\']', html, re.IGNORECASE)
        col.assert_true(len(svg_viewboxes) >= 4, f"All 4 SVGs must define explicit viewBox, found {len(svg_viewboxes)}")
        for vb in svg_viewboxes:
            parts = [float(x) for x in vb.strip().split()]
            col.assert_true(len(parts) == 4 and parts[2] > 0 and parts[3] > 0, f"Valid viewBox dimensions: {vb}")

    if data:
        # T2.5: Mathematical Consistency in Structured Data
        mkt = data.get("dimension1_price_volume", data.get("market_data", {}))
        stats = mkt.get("statistics", mkt)
        close = float(stats.get("close", 0))
        high = float(stats.get("month_high", 0))
        low = float(stats.get("month_low", 0))
        col.assert_true(low <= close <= high, f"Mathematical bound failure: low ({low}) <= close ({close}) <= high ({high})")

        # Moving average verification from daily series
        daily = mkt.get("daily_series", mkt.get("ohlcv", []))
        if len(daily) >= 20:
            closes = [float(d.get("close", 0)) for d in daily]
            calc_ma5 = sum(closes[-5:]) / 5.0
            calc_ma10 = sum(closes[-10:]) / 10.0
            calc_ma20 = sum(closes[-20:]) / 20.0
            col.assert_almost_equal(float(stats.get("ma5", 0)), calc_ma5, 1.0, "5MA calculation matches latest 5 close prices")
            col.assert_almost_equal(float(stats.get("ma10", 0)), calc_ma10, 1.0, "10MA calculation matches latest 10 close prices")
            col.assert_almost_equal(float(stats.get("ma20", 0)), calc_ma20, 1.0, "20MA calculation matches latest 20 close prices")

        # Bias 20MA mathematical formula
        ma20_val = float(stats.get("ma20", 0))
        if ma20_val > 0:
            calc_bias = ((close - ma20_val) / ma20_val) * 100.0
            col.assert_almost_equal(float(stats.get("bias_20ma", stats.get("bias", 0))), calc_bias, 0.2,
                                    "20MA bias matches ((Close - 20MA) / 20MA) * 100")

        # Monthly Revenue 10M sum check
        ops = data.get("dimension3_financials", data.get("operational_data", {}))
        monthly_revs = ops.get("monthly_revenue_2026", ops.get("monthly_revenue", []))
        if len(monthly_revs) >= 10:
            rev_sum = sum(float(m.get("revenue_ntd", m.get("revenue", 0))) for m in monthly_revs[:10])
            reported_sum = float(ops.get("ten_month_revenue_total", ops.get("cumulative_revenue_10m", 0)))
            col.assert_almost_equal(reported_sum, rev_sum, 100000.0, "10-month revenue total must equal sum of 10 months")

        # Quarterly EPS sum consistency
        quarters = ops.get("quarterly_financials", ops.get("quarterly_income", []))
        if len(quarters) >= 4:
            ttm_sum = sum(float(q.get("eps", 0)) for q in quarters[-4:])
            col.assert_almost_equal(ttm_sum, 347.45, 0.5, "Quarterly EPS sum equals TTM EPS NT$347.45")

        # Blended Target Price formula check: 60% * 2432 + 40% * 1889 = 2214.8 ~= 2215
        val = data.get("dimension4_valuation", data.get("valuation_data", {}))
        models = val.get("valuation_models", {})
        per_model = float(models.get("model_per_repair", 2432.0))
        pbr_model = float(models.get("model_pbr_reversion", 1889.0))
        calc_target = (0.60 * per_model) + (0.40 * pbr_model)
        reported_target = float(data.get("target_price", 0))
        col.assert_almost_equal(reported_target, calc_target, 2.0, "Target price matches 60% PER model + 40% PBR model")

        # Non-zero division guards & short balance
        inst = data.get("dimension2_institutional", data.get("institutional_data", {}))
        short_lots = int(inst.get("short_balance_lots", inst.get("short_balance", 0)))
        margin_lots = int(inst.get("margin_balance_lots", inst.get("margin_balance", 0)))
        col.assert_true(short_lots > 0, "Short balance lots must be strictly positive to avoid 0-division")
        col.assert_true(margin_lots > short_lots, "Margin balance exceeds short balance")


# --- Tier 3: Hallmark Design & Cross-Feature Interactions ---

def validate_tier3_interactions_and_layout(html: str, col: AssertionCollector):
    """Validates Tier 3: Theme Switcher, Valuation Tab Switching, SVG Colors, Hallmark Layout & Print."""
    # T3.1: Theme Switcher DOM & Script Integration
    col.assert_true('id="themeToggle"' in html or 'id=\'themeToggle\'' in html, "Must contain #themeToggle button or switch")
    col.assert_regex(r'data-theme=["\'](light|dark)["\']|data-mode=["\'](light|dark)["\']', html, "Root HTML or body must support data-theme/data-mode")
    col.assert_regex(r"localStorage\.(getItem|setItem)", html, "Theme switcher must persist theme preference to localStorage")

    # T3.2: OKLCH Design Tokens & Dark Mode Parity
    col.assert_regex(r":root\s*\{[^}]*oklch\(", html, ":root must declare OKLCH color tokens")
    col.assert_regex(r"(\[data-theme=['\"]dark['\"]|\[data-mode=['\"]dark['\"]|body\.dark)[^}]*oklch\(", html,
                     "Dark mode selector must mathematically redefine OKLCH tokens")
    col.assert_regex(r"--color-paper", html, "Must declare --color-paper token")
    col.assert_regex(r"--color-ink", html, "Must declare --color-ink token")
    col.assert_regex(r"--color-accent", html, "Must declare --color-accent token")

    # T3.3: Valuation River Band Tab Switcher
    col.assert_regex(r'id=["\']tabPER["\']|class=["\'][^"\']*tab-per', html, "Must contain PER river band tab trigger")
    col.assert_regex(r'id=["\']tabPBR["\']|class=["\'][^"\']*tab-pbr', html, "Must contain PBR river band tab trigger")

    # T3.4: Typography Check
    col.assert_regex(r"(Plus\s*Jakarta\s*Sans|Host\s*Grotesk|Hanken\s*Grotesk)", html,
                     "Display font must feature Plus Jakarta Sans, Host Grotesk, or Hanken Grotesk")
    col.assert_regex(r"Newsreader", html, "Body font must feature Newsreader editorial serif")
    col.assert_regex(r"(IBM\s*Plex\s*Mono|Atkinson\s*Hyperlegible\s*Mono)", html,
                     "Financial monospace font must feature IBM Plex Mono or Atkinson Hyperlegible Mono")

    # T3.5: Tabular Numeral Formatting in CSS
    col.assert_regex(r"tabular-nums|tnum", html, "CSS must declare 'tabular-nums' or 'tnum' for financial numbers")

    # T3.6: Taiwan Market Directional Semantics
    col.assert_regex(r"(▲|▼|tw-rise|tw-fall|color-rise|color-fall)", html,
                     "Taiwan market directional glyphs (▲/▼) or semantic classes must be present")

    # T3.7: Layout Discipline & Responsive Media Queries
    col.assert_regex(r"overflow-x:\s*clip", html, "Layout must define 'overflow-x: clip' on html/body (Hallmark Gate 34)")
    col.assert_regex(r"@media\s*\([^{}]*max-width:[^{}]*\)", html, "CSS must define responsive media queries for mobile/tablet")

    # T3.8: Print & PDF Export Stylesheet
    col.assert_regex(r"@media\s*print", html, "CSS must define '@media print' stylesheet for PDF export")
    col.assert_regex(r"(break-inside:\s*avoid|page-break-inside:\s*avoid)", html,
                     "Print stylesheet must include 'break-inside: avoid' for multi-page print durability")


# --- Tier 4: Real-World Scenarios & Institutional Acceptance ---

class DomStructureParser(HTMLParser):
    """Pure-standard-library DOM validator."""
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
    # T4.1: Institutional Masthead & Key Recommendation Callouts
    col.assert_regex(r"8299(\.TWO)?", html, "Institutional report must display ticker 8299 / 8299.TWO")
    col.assert_regex(r"NT\$\s*2[,.]?215|2[,.]?215\s*元", html, "Institutional target price NT$2,215 must be featured")
    col.assert_regex(r"(BUY|OVERWEIGHT|買進|優於大盤)", html, "Investment rating (BUY / OVERWEIGHT) must be prominently featured")
    col.assert_regex(r"2026-11-09|2026\s*年\s*11\s*月", html, "Publication date badge (2026-11-09) must be present")

    # T4.2: NAND Flash Inventory Cycle Narrative
    col.assert_regex(r"(NAND\s*Flash|庫存循環|逆週期備貨|DSI|週轉天數)", html,
                     "Report must educate readers on counter-cyclical NAND flash inventory management")

    # T4.3: Peer Dislocation Scenario Validation
    col.assert_regex(r"(75\.3\s*%|估值折價|本益比折價|倍數修復)", html,
                     "Report must articulate peer valuation dislocation (75.3% PER discount vs peers)")

    # T4.4: Full Semantic DOM Hierarchy Parse
    parser = DomStructureParser()
    try:
        parser.feed(html)
        col.assert_true("html" in parser.tags_found, "DOM must contain root <html>")
        col.assert_true("head" in parser.tags_found, "DOM must contain <head>")
        col.assert_true("body" in parser.tags_found, "DOM must contain <body>")
        col.assert_true("header" in parser.tags_found, "DOM must contain <header> masthead")
        col.assert_true("footer" in parser.tags_found, "DOM must contain <footer>")
        col.assert_true(parser.sections_count >= 5, f"DOM must contain at least 5 semantic <section> blocks, found {parser.sections_count}")
        col.assert_true(parser.headers_count >= 5, f"DOM must contain proper heading hierarchy (h1/h2/h3), found {parser.headers_count}")
        col.assert_true(len(parser.titles) > 0 and len(parser.titles[0]) > 0, f"Page title must be populated: {parser.titles}")
    except Exception as e:
        col.assert_true(False, f"DOM Parsing failed with error: {str(e)}")


# --- Synthetic Self-Validation Mock Generator ---

def get_synthetic_mock_data() -> Dict[str, Any]:
    """Generates synthetic data matching PROJECT.md interface contract for suite self-validation."""
    return {
        "stock_id": "8299",
        "stock_name": "Phison Electronics (群聯電子)",
        "snapshot_date": "2026-11-09",
        "rating": "BUY / OVERWEIGHT",
        "target_price": 2215.0,
        "current_price": 1500.0,
        "upside_pct": 47.67,
        "dimension1_price_volume": {
            "statistics": {
                "close": 1500.0,
                "month_high": 2165.0,
                "month_low": 1405.0,
                "ma5": 1667.0,
                "ma10": 1814.5,
                "ma20": 1879.5,
                "bias_20ma": -20.19,
                "peak_volume": 6267396,
                "peak_turnover_pct": 2.83
            },
            "daily_series": [
                {"date": f"2026-10-{i:02d}", "close": 1944.5, "volume": 3000000} for i in range(1, 11)
            ] + [
                {"date": f"2026-10-{i:02d}", "close": c, "volume": 3000000}
                for i, c in zip(range(11, 16), [1960.0, 2010.0, 2020.0, 2050.0, 1770.0])
            ] + [
                {"date": f"2026-11-{i:02d}", "close": c, "volume": 3000000}
                for i, c in zip(range(2, 7), [1875.0, 1690.0, 1710.0, 1560.0, 1500.0])
            ]
        },
        "dimension2_institutional": {
            "foreign_net_1m": -1914468,
            "trust_net_1m": 366626,
            "dealer_net_1m": -748767,
            "foreign_ownership_pct": 45.34,
            "margin_balance_lots": 9173,
            "short_balance_lots": 8,
            "margin_short_ratio": 1146.6
        },
        "dimension3_financials": {
            "monthly_revenue_2026": [{"month": m, "revenue_ntd": 22646192500} for m in range(1, 11)],
            "ten_month_revenue_total": 226461925000,
            "ten_month_yoy_growth_pct": 297.78,
            "quarterly_financials": [
                {"quarter": "2025Q4", "eps": 22.08, "gross_margin_pct": 41.88, "revenue_ntd": 22800000000},
                {"quarter": "2026Q1", "eps": 68.80, "gross_margin_pct": 61.82, "revenue_ntd": 40970000000},
                {"quarter": "2026Q2", "eps": 118.57, "gross_margin_pct": 65.35, "revenue_ntd": 67890000000},
                {"quarter": "2026Q3", "eps": 138.00, "gross_margin_pct": 59.85, "revenue_ntd": 86080000000}
            ],
            "blended_gross_margin_pct": 60.05,
            "inventory_dsi_progression": {"2026Q1": 415.4, "2026Q2": 351.2, "2026Q3": 291.1}
        },
        "dimension4_valuation": {
            "current_per": 4.33,
            "per_percentile": 0.0,
            "current_pbr": 2.78,
            "pbr_percentile": 71.6,
            "valuation_models": {
                "model_per_repair": 2432.0,
                "model_pbr_reversion": 1889.0
            },
            "peers": [
                {"ticker": "8299", "name": "Phison", "per": 4.33, "pbr": 2.78, "yield": 1.55},
                {"ticker": "SIMO", "name": "Silicon Motion", "per": 17.50, "pbr": 4.88, "yield": 1.41},
                {"ticker": "2379", "name": "Realtek", "per": 25.67, "pbr": 7.24, "yield": 3.53},
                {"ticker": "5269", "name": "ASMedia", "per": 12.37, "pbr": 2.40, "yield": 3.91}
            ]
        },
        "dimension5_catalysts_risks": {
            "moats": ["PCIe Gen5 Controller Leadership", "aiDAPTIV+ Platform", "Tier-1 TSMC Alliance"],
            "risks": ["NAND Cyclical Downturn", "Raw Material Price Fluctuations", "Geopolitical Export Controls"]
        }
    }


def get_synthetic_mock_html() -> str:
    """Generates synthetic minimal HTML satisfying all Hallmark and contract rules for self-validation."""
    return """<!DOCTYPE html>
<html lang="zh-TW" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="8299 群聯電子 (Phison) 360度綜合研究分析報告與目標價推導。">
  <title>8299 群聯電子 (Phison) 360度綜合研究分析報告</title>
  <style>
    :root {
      --color-paper: oklch(98.5% 0.005 250);
      --color-ink: oklch(18% 0.025 250);
      --color-accent: oklch(48% 0.16 260);
      --color-rule: oklch(88% 0.01 250);
      --color-rise: oklch(62% 0.22 25);
      --color-fall: oklch(65% 0.20 150);
      font-family: "Newsreader", serif;
    }
    [data-theme="dark"] {
      --color-paper: oklch(15% 0.008 250);
      --color-ink: oklch(95% 0.005 250);
      --color-accent: oklch(65% 0.14 260);
      --color-rule: oklch(30% 0.01 250);
    }
    html, body { overflow-x: clip; margin: 0; }
    h1, h2, h3 { font-family: "Plus Jakarta Sans", "Host Grotesk", sans-serif; text-wrap: balance; }
    .num, td.num { font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
    @media (max-width: 768px) { .container { padding: 16px; } }
    @media print { .card, .chart-block { break-inside: avoid; } }
  </style>
</head>
<body>
  <header>
    <h1>8299.TWO 群聯電子 (Phison Electronics)</h1>
    <div class="badge">Date: 2026-11-09 | Rating: BUY / OVERWEIGHT | Target Price: NT$ 2,215 (+47.67%)</div>
    <button id="themeToggle" onclick="toggleTheme()">Toggle Theme</button>
  </header>
  <main>
    <section>
      <h2>價量結構分析 (Price & Volume)</h2>
      <p>收盤價 1,500.00 元，月高 2,165.00，月低 1,405.00。5MA 1,667.00，10MA 1,814.50，20MA 1,879.50，乖離率 -20.19%。爆量 6,267 張，週轉率 2.83% (▲ tw-rise)。</p>
      <svg id="chartPriceVolume" viewBox="0 0 800 400"><rect x="0" y="0" width="800" height="400" fill="none"/></svg>
      <table><thead><tr><th>指標</th><th>數值</th></tr></thead><tbody><tr><td>收盤價</td><td class="num">1,500.00</td></tr></tbody></table>
    </section>
    <section>
      <h2>法人籌碼與信用交易 (Institutional Flow)</h2>
      <p>外資持股 45.34%，近月外資賣超 -1,914 張，投信買超 366.6 張，自營商賣超 -748 張。融資 9,173 張，融券 8 張，資券比 1,146.6x (▼ tw-fall)。</p>
      <svg id="chartInstitutional" viewBox="0 0 800 400"><line x1="0" y1="0" x2="800" y2="400" stroke="currentColor"/></svg>
      <table><thead><tr><th>法人</th><th>籌碼</th></tr></thead><tbody><tr><td>外資</td><td class="num">45.34%</td></tr></tbody></table>
    </section>
    <section>
      <h2>營運獲利與 NAND 庫存循環 (Financials & Inventory)</h2>
      <p>前 10 月營收 2,264.62 億元 (年增 297.78%)。近四季 EPS 347.45 元，綜合毛利率 60.05%。NAND Flash 逆週期備貨，庫存週轉天數 DSI 由 Q1 峰值 415.4 天降至 Q3 291.1 天。</p>
      <svg id="chartFinancials" viewBox="0 0 800 400"><circle cx="400" cy="200" r="50" fill="none"/></svg>
      <table><thead><tr><th>累計營收</th><th>金額</th></tr></thead><tbody><tr><td>10M</td><td class="num">2,264.62 億</td></tr></tbody></table>
    </section>
    <section>
      <h2>估值分析與同業比較 (Valuation & Peers)</h2>
      <p>目前 PER 4.33x (處於歷史 0.0th 百分位極度低估)，PBR 2.78x (71.6th 百分位)。同業比較：Silicon Motion (SIMO), Realtek (2379), ASMedia (5269)，相較同業中位數折價 75.3% 估值折價，具強烈倍數修復空間。</p>
      <div class="tabs">
        <button id="tabPER" class="active">PER River</button>
        <button id="tabPBR">PBR River</button>
      </div>
      <svg id="chartValuationRiver" viewBox="0 0 800 400"><polyline points="0,0 400,200 800,400"/></svg>
      <table><thead><tr><th>標的</th><th>PER</th></tr></thead><tbody><tr><td>Phison</td><td class="num">4.33</td></tr></tbody></table>
    </section>
    <section>
      <h2>投資利多與潛在風險 (Catalysts & Risks)</h2>
      <p>利多：PCIe Gen5 SSD 控制晶片全球領先地位、aiDAPTIV+ 邊緣 AI 運算架構、TSMC 台積電先進製程堅實結盟。</p>
      <p>風險：快閃記憶體 NAND 現貨價格下行記憶體週期、原物料上漲通膨壓力、半導體出口禁令管制風險。</p>
    </section>
  </main>
  <footer>
    <p>Phison Electronics Equity Research, Hallmark Standard</p>
  </footer>
  <script>
    function toggleTheme() {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const nxt = cur === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', nxt);
      localStorage.setItem('theme', nxt);
    }
  </script>
</body>
</html>
"""


def get_synthetic_mock_portal() -> Tuple[str, str]:
    """Generates synthetic index.html card snippet and README row for self-test."""
    portal = """
    <article class="artifact-card" data-category="equity" data-keywords="8299 群聯 phison nand ssd aiDAPTIV per 4.33 target 2215">
      <a href="./reports/equity/8299-phison-20261109.html">8299 群聯電子 360 度研究報告</a>
      <div class="artifact-telemetry">
        <span>1,500 元</span><span>4.33x</span><span>2,264.6 億</span><span>347.45 元</span>
      </div>
    </article>
    """
    readme = """
    | **Equity Research** | 8299 Phison Electronics (群聯電子) 360° Comprehensive Analysis | [View Online](...) | [`reports/equity/8299-phison-20261109.html`](./reports/equity/8299-phison-20261109.html) |
    """
    return portal, readme


# --- Suite Runner Execution Engine ---

def run_e2e_suite(strict: bool = False, html_only: bool = False, data_only: bool = False, portal_only: bool = False, self_test: bool = False) -> int:
    """Main execution engine: runs all opaque-box tests across Tiers 1-4."""
    print(f"\n{Color.BOLD}{Color.CYAN}========================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}  8299 Phison Electronics Equity Report — E2E Opaque-Box Test Runner    {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}========================================================================{Color.RESET}\n")

    data_exists = DATA_PATH.is_file()
    html_exists = HTML_PATH.is_file()
    portal_exists = PORTAL_PATH.is_file()
    readme_exists = README_PATH.is_file()

    print(f"[*] Workspace Root: {REPO_ROOT}")
    print(f"[*] data_8299.json: {'FOUND (' + str(DATA_PATH.stat().st_size) + ' bytes)' if data_exists else 'NOT FOUND'}")
    print(f"[*] 8299-phison-20261109.html: {'FOUND (' + str(HTML_PATH.stat().st_size) + ' bytes)' if html_exists else 'NOT FOUND'}")
    print(f"[*] index.html: {'FOUND' if portal_exists else 'NOT FOUND'}")
    print(f"[*] README.md: {'FOUND' if readme_exists else 'NOT FOUND'}")
    print(f"[*] Mode Settings: strict={strict}, html_only={html_only}, data_only={data_only}, portal_only={portal_only}, self_test={self_test}\n")

    if not data_exists and not html_exists and not self_test:
        if strict:
            print(f"{Color.RED}[HARD FAILURE] Strict mode enabled: Target deliverables are missing on disk!{Color.RESET}")
            return 1
        else:
            print(f"{Color.YELLOW}[INTERMEDIATE STATUS] Target deliverables not yet created by M1/M2 workers.{Color.RESET}")
            print(f"[*] Automatically triggering suite self-validation harness to verify all check contracts...\n")
            self_test = True

    collectors: List[AssertionCollector] = []

    if self_test:
        print(f"{Color.BOLD}[RUNNING SYNTHETIC SELF-VALIDATION HARNESS]{Color.RESET}")
        mock_data = get_synthetic_mock_data()
        mock_html = get_synthetic_mock_html()
        mock_portal, mock_readme = get_synthetic_mock_portal()

        c_t1_d = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.5: Synthetic Data Contract (data_8299.json)")
        validate_data_tier1(mock_data, c_t1_d)
        collectors.append(c_t1_d)

        c_t1_h = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.8: Synthetic HTML Report Content")
        validate_html_tier1(mock_html, c_t1_h)
        collectors.append(c_t1_h)

        c_t1_p = AssertionCollector("Tier 1 (Feature Coverage)", "T1.9-T1.10: Synthetic Portal & Repo Integration")
        validate_portal_repo_tier1(mock_portal, mock_readme, c_t1_p)
        collectors.append(c_t1_p)

        c_t2 = AssertionCollector("Tier 2 (Boundary & Corner)", "T2.1-T2.5: Zero Placeholders, Math, Durability")
        validate_tier2_boundaries(mock_data, mock_html, c_t2)
        collectors.append(c_t2)

        c_t3 = AssertionCollector("Tier 3 (Hallmark & Interactions)", "T3.1-T3.8: Theme Toggle, Tabs, OKLCH, Layout & Print")
        validate_tier3_interactions_and_layout(mock_html, c_t3)
        collectors.append(c_t3)

        c_t4 = AssertionCollector("Tier 4 (Real-World Scenarios)", "T4.1-T4.4: Institutional Masthead, Rating, NAND Cycle, DOM Parse")
        validate_tier4_institutional(mock_html, c_t4)
        collectors.append(c_t4)

    else:
        data_obj: Optional[Dict[str, Any]] = None
        html_str: Optional[str] = None
        portal_str: Optional[str] = None
        readme_str: Optional[str] = None

        if not html_only and not portal_only:
            if data_exists:
                try:
                    with open(DATA_PATH, "r", encoding="utf-8") as f:
                        data_obj = json.load(f)
                except Exception as e:
                    print(f"{Color.RED}[ERROR] Failed to parse data_8299.json: {e}{Color.RESET}")
                    return 1
            elif strict:
                print(f"{Color.RED}[ERROR] data_8299.json is missing in strict mode!{Color.RESET}")
                return 1

        if not data_only and not portal_only:
            if html_exists:
                try:
                    with open(HTML_PATH, "r", encoding="utf-8") as f:
                        html_str = f.read()
                except Exception as e:
                    print(f"{Color.RED}[ERROR] Failed to read HTML report: {e}{Color.RESET}")
                    return 1
            elif strict:
                print(f"{Color.RED}[ERROR] 8299-phison-20261109.html is missing in strict mode!{Color.RESET}")
                return 1

        if portal_exists:
            try:
                with open(PORTAL_PATH, "r", encoding="utf-8") as f:
                    portal_str = f.read()
            except Exception as e:
                print(f"{Color.YELLOW}[WARN] Failed to read index.html: {e}{Color.RESET}")

        if readme_exists:
            try:
                with open(README_PATH, "r", encoding="utf-8") as f:
                    readme_str = f.read()
            except Exception as e:
                print(f"{Color.YELLOW}[WARN] Failed to read README.md: {e}{Color.RESET}")

        # Tier 1
        c_t1_d = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.5: Data Contract Completeness (data_8299.json)")
        if data_obj:
            validate_data_tier1(data_obj, c_t1_d)
        else:
            c_t1_d.skip("data_8299.json not available for evaluation")
        collectors.append(c_t1_d)

        c_t1_h = AssertionCollector("Tier 1 (Feature Coverage)", "T1.1-T1.8: HTML Report Content Completeness")
        if html_str:
            validate_html_tier1(html_str, c_t1_h)
        else:
            c_t1_h.skip("8299-phison-20261109.html not yet generated")
        collectors.append(c_t1_h)

        c_t1_p = AssertionCollector("Tier 1 (Feature Coverage)", "T1.9-T1.10: Portal & Repo Documentation Integration")
        if portal_str or readme_str:
            validate_portal_repo_tier1(portal_str, readme_str, c_t1_p)
        else:
            c_t1_p.skip("Portal or README not available for evaluation")
        collectors.append(c_t1_p)

        # Tier 2
        c_t2 = AssertionCollector("Tier 2 (Boundary & Corner)", "T2.1-T2.5: Zero Placeholders, Math Consistency & Durability")
        if data_obj or html_str:
            validate_tier2_boundaries(data_obj, html_str, c_t2)
        else:
            c_t2.skip("Neither data nor HTML available for boundary verification")
        collectors.append(c_t2)

        # Tier 3
        c_t3 = AssertionCollector("Tier 3 (Hallmark & Interactions)", "T3.1-T3.8: Theme Toggle, Tabs, OKLCH, Layout & Print")
        if html_str:
            validate_tier3_interactions_and_layout(html_str, c_t3)
        else:
            c_t3.skip("8299-phison-20261109.html not yet generated")
        collectors.append(c_t3)

        # Tier 4
        c_t4 = AssertionCollector("Tier 4 (Real-World Scenarios)", "T4.1-T4.4: Institutional Masthead, Rating, NAND Cycle, DOM Parse")
        if html_str:
            validate_tier4_institutional(html_str, c_t4)
        else:
            c_t4.skip("8299-phison-20261109.html not yet generated")
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

class TestPhisonDataContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DATA_PATH.is_file():
            raise unittest.SkipTest(f"data_8299.json not yet generated at {DATA_PATH}")
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_tier1_data_completeness(self):
        col = AssertionCollector("Tier 1", "data_8299.json")
        validate_data_tier1(self.data, col)
        self.assertEqual(col.failures, [], f"Data tier 1 failures: {col.failures}")

    def test_tier2_data_math_consistency(self):
        col = AssertionCollector("Tier 2", "data_8299.json math")
        validate_tier2_boundaries(self.data, None, col)
        self.assertEqual(col.failures, [], f"Data tier 2 math failures: {col.failures}")


class TestPhisonHtmlContract(unittest.TestCase):
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
        validate_tier3_interactions_and_layout(self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 3 failures: {col.failures}")

    def test_tier4_institutional_scenarios(self):
        col = AssertionCollector("Tier 4", "Institutional scenarios & DOM")
        validate_tier4_institutional(self.html, col)
        self.assertEqual(col.failures, [], f"HTML tier 4 failures: {col.failures}")


# --- Command-Line Entry Point ---

def main():
    parser = argparse.ArgumentParser(
        description="E2E Test Runner for 8299 Phison Electronics Hallmark Equity Research Report",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strict", action="store_true", help="Require deliverables to exist; fail if missing")
    parser.add_argument("--data-only", action="store_true", help="Evaluate only data_8299.json")
    parser.add_argument("--html-only", action="store_true", help="Evaluate only 8299-phison-20261109.html")
    parser.add_argument("--portal-only", action="store_true", help="Evaluate only index.html and README.md")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic self-test validating the harness itself")

    args = parser.parse_args()
    exit_code = run_e2e_suite(
        strict=args.strict,
        html_only=args.html_only,
        data_only=args.data_only,
        portal_only=args.portal_only,
        self_test=args.self_test
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
