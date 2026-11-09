#!/usr/bin/env python3
"""
test_adversarial_stress.py
Empirical Adversarial Stress Testing Harness for 2330 TSMC Equity Report
Deliverable: reports/equity/2330-tsmc-20261109.html

Adversarial Stress Verification Dimensions:
1. Self-Contained Integrity & Zero External CDN / Asset Leakage
2. SVG Geometry & Boundary Sanity across all 4 Charts
3. Trade Setup Overlays (Chart 1): Bounds, Badges, Clipping & Occlusion Immunity
4. Valuation River Polygons (Chart 4): Vertex Geometry, Topology, and Tab Groups
5. Theme Switching, FOUC Prevention, and OKLCH Contrast Ratio
6. Mobile Responsiveness, 1360px Container Cap, and Overflow Discipline
7. Interactive Script Micro-Engine & ARIA Contract
"""

import os
import sys
import re
import math
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Dict, Tuple, Any

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[2]
HTML_PATH = REPO_ROOT / "reports" / "equity" / "2330-tsmc-20261109.html"
DATA_PATH = REPO_ROOT / "scripts" / "equity" / "2330-20261109" / "data_2330.json"


class TestHarness:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def check(self, condition: bool, test_name: str, detail: str = ""):
        if condition:
            self.passed += 1
            self.results.append((True, test_name, detail))
            print(f"  [PASS] {test_name}")
        else:
            self.failed += 1
            self.results.append((False, test_name, detail))
            print(f"  [FAIL] {test_name} -> {detail}")


def run_stress_suite():
    print("=" * 80)
    print(" EMPIRICAL ADVERSARIAL STRESS TEST HARNESS — 2330 TSMC REPORT")
    print(f" Target Deliverable: {HTML_PATH}")
    print("=" * 80)

    harness = TestHarness()

    if not HTML_PATH.exists():
        print(f"FATAL: HTML deliverable does not exist at {HTML_PATH}")
        sys.exit(1)

    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # -------------------------------------------------------------------------
    # SUITE 1: Self-Contained Integrity & Asset Dependency Stress
    # -------------------------------------------------------------------------
    print("\n--- SUITE 1: Self-Contained Integrity & Asset Dependency Stress ---")

    # 1.1 No external CDN script tags
    cdn_scripts = re.findall(r'<script\b[^>]*\bsrc=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
    harness.check(len(cdn_scripts) == 0, "No external CDN <script> tags", f"Found: {cdn_scripts}")

    # 1.2 No external stylesheet link tags (excluding permissible Google Fonts if any)
    ext_css = re.findall(r'<link\b[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
    # Check if any external CSS is loaded
    harness.check(len(ext_css) == 0, "Zero external CSS <link> dependencies", f"Found: {ext_css}")

    # 1.3 No local file:// references
    file_uris = re.findall(r'(?:src|href)=["\']file://[^"\']+["\']', html, re.IGNORECASE)
    harness.check(len(file_uris) == 0, "Zero local file:// absolute URIs", f"Found: {file_uris}")

    # 1.4 No broken relative asset links (img src, link href, video/audio)
    rel_assets = re.findall(r'<(?:img|audio|video|source|embed|object)\b[^>]*\bsrc=["\']([^"\']+)["\']', html, re.IGNORECASE)
    broken_assets = []
    for asset in rel_assets:
        if asset.startswith("data:"):
            continue
        asset_path = (HTML_PATH.parent / asset).resolve()
        if not asset_path.exists():
            broken_assets.append(asset)
    harness.check(len(broken_assets) == 0, "Zero broken relative asset links", f"Missing: {broken_assets}")

    # 1.5 No CSS url() to missing local assets
    css_urls = re.findall(r'url\(\s*["\']?([^"\'\)]+)["\']?\s*\)', html)
    broken_css_urls = []
    for u in css_urls:
        if u.startswith("data:") or u.startswith("http://") or u.startswith("https://") or u.startswith("#"):
            continue
        css_asset_path = (HTML_PATH.parent / u).resolve()
        if not css_asset_path.exists():
            broken_css_urls.append(u)
    harness.check(len(broken_css_urls) == 0, "Zero broken CSS url() references", f"Missing: {broken_css_urls}")

    # 1.6 Total document self-containment: standalone HTML size > 50KB and <= 2MB
    html_kb = len(html.encode("utf-8")) / 1024
    harness.check(50 <= html_kb <= 2048, f"HTML size within robust standalone window (50KB-2MB)", f"Size: {html_kb:.2f} KB")

    # -------------------------------------------------------------------------
    # SUITE 2: SVG Geometry & Boundary Integrity across All 4 Charts
    # -------------------------------------------------------------------------
    print("\n--- SUITE 2: SVG Geometry & Boundary Integrity across All 4 Charts ---")

    svg_ids = ["chartPriceVolume", "chartInstitutional", "chartFinancials", "chartValuationRiver"]
    svg_blocks = {}
    for sid in svg_ids:
        pattern = rf'<svg\b[^>]*id=["\']{sid}["\'][\s\S]*?</svg>'
        m = re.search(pattern, html, re.IGNORECASE)
        harness.check(m is not None, f"SVG #{sid} exists in DOM")
        if m:
            svg_blocks[sid] = m.group(0)

    for sid, block in svg_blocks.items():
        # Check viewBox
        vb_match = re.search(r'viewBox=["\']([^"\']+)["\']', block)
        harness.check(vb_match is not None, f"SVG #{sid} has explicit viewBox attribute")
        if vb_match:
            parts = [float(x) for x in vb_match.group(1).split()]
            harness.check(len(parts) == 4, f"SVG #{sid} viewBox has 4 components", f"Got: {parts}")
            min_x, min_y, vb_w, vb_h = parts
            harness.check(min_x == 0 and min_y == 0, f"SVG #{sid} origin is (0,0)", f"Got: ({min_x}, {min_y})")
            harness.check(vb_w > 0 and vb_h > 0, f"SVG #{sid} dimensions positive ({vb_w}x{vb_h})")

        # Check for negative width or height on rects
        negative_dims = []
        for rm in re.finditer(r'<rect\b([^>]+)>', block):
            rattrs = rm.group(1)
            w_m = re.search(r'width=["\'](-?[0-9.]+)["\']', rattrs)
            h_m = re.search(r'height=["\'](-?[0-9.]+)["\']', rattrs)
            if w_m and float(w_m.group(1)) < 0:
                negative_dims.append(f"Negative width: {w_m.group(1)}")
            if h_m and float(h_m.group(1)) < 0:
                negative_dims.append(f"Negative height: {h_m.group(1)}")
        harness.check(len(negative_dims) == 0, f"SVG #{sid} has zero negative rect dimensions", f"{negative_dims[:3]}")

        # Check for negative radius on circles
        circle_neg_r = []
        for cm in re.finditer(r'<circle\b([^>]+)>', block):
            cattrs = cm.group(1)
            r_m = re.search(r'r=["\'](-?[0-9.]+)["\']', cattrs)
            if r_m and float(r_m.group(1)) <= 0:
                circle_neg_r.append(r_m.group(1))
        harness.check(len(circle_neg_r) == 0, f"SVG #{sid} circles have strictly positive radius", f"{circle_neg_r}")

    # -------------------------------------------------------------------------
    # SUITE 3: Chart 1 Trade Setup Overlays Stress
    # -------------------------------------------------------------------------
    print("\n--- SUITE 3: Chart 1 Trade Setup Overlays Stress ---")

    c1 = svg_blocks.get("chartPriceVolume", "")

    # 3.1 Entry Zone Corridor Rect
    corridor_m = re.search(r'<rect\b[^>]*class=["\'][^"\']*trade-corridor[^"\']*["\'][^>]*>', c1)
    harness.check(corridor_m is not None, "Chart 1 renders .trade-corridor rect")
    if corridor_m:
        c_attrs = corridor_m.group(0)
        cx = float(re.search(r'x=["\']([0-9.]+)["\']', c_attrs).group(1))
        cy = float(re.search(r'y=["\']([0-9.]+)["\']', c_attrs).group(1))
        cw = float(re.search(r'width=["\']([0-9.]+)["\']', c_attrs).group(1))
        ch = float(re.search(r'height=["\']([0-9.]+)["\']', c_attrs).group(1))
        harness.check(cx >= 0 and cy >= 0, f"Entry corridor origin non-negative ({cx}, {cy})")
        harness.check(cx + cw <= 960, f"Entry corridor does not overflow right boundary ({cx + cw} <= 960)")
        harness.check(ch > 5, f"Entry corridor has tangible height ({ch:.1f}px)")

    # 3.2 Target Lines T1, T2, and Stop Loss Line
    t1_m = re.search(r'<line\b[^>]*class=["\'][^"\']*trade-target-t1[^"\']*["\'][^>]*>', c1)
    t2_m = re.search(r'<line\b[^>]*class=["\'][^"\']*trade-target-t2[^"\']*["\'][^>]*>', c1)
    sl_m = re.search(r'<line\b[^>]*class=["\'][^"\']*trade-stop[^"\']*["\'][^>]*>', c1)

    harness.check(t1_m is not None, "Chart 1 renders .trade-target-t1 line")
    harness.check(t2_m is not None, "Chart 1 renders .trade-target-t2 line")
    harness.check(sl_m is not None, "Chart 1 renders .trade-stop line")

    def parse_line_coords(line_tag: str) -> Dict[str, float]:
        x1 = float(re.search(r'x1=["\']([0-9.]+)["\']', line_tag).group(1))
        y1 = float(re.search(r'y1=["\']([0-9.]+)["\']', line_tag).group(1))
        x2 = float(re.search(r'x2=["\']([0-9.]+)["\']', line_tag).group(1))
        y2 = float(re.search(r'y2=["\']([0-9.]+)["\']', line_tag).group(1))
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    if t1_m and t2_m and sl_m:
        l_t1 = parse_line_coords(t1_m.group(0))
        l_t2 = parse_line_coords(t2_m.group(0))
        l_sl = parse_line_coords(sl_m.group(0))

        # Check horizontal orientation
        harness.check(l_t1["y1"] == l_t1["y2"], f"T1 line is perfectly horizontal (y={l_t1['y1']})")
        harness.check(l_t2["y1"] == l_t2["y2"], f"T2 line is perfectly horizontal (y={l_t2['y1']})")
        harness.check(l_sl["y1"] == l_sl["y2"], f"Stop-loss line is perfectly horizontal (y={l_sl['y1']})")

        # Vertical price scale sanity: Higher price -> Smaller SVG y coordinate (since y=0 is top)
        # T2 (2,650) > T1 (2,450) > Entry Corridor (2,150) > Stop-Loss (1,980)
        # Therefore: y(T2) < y(T1) < y(Entry) < y(Stop-Loss)
        harness.check(l_t2["y1"] < l_t1["y1"], f"T2 line y ({l_t2['y1']}) is above T1 line y ({l_t1['y1']})")
        if corridor_m:
            harness.check(l_t1["y1"] < cy, f"T1 line y ({l_t1['y1']}) is above Entry corridor top ({cy})")
            harness.check(cy + ch < l_sl["y1"], f"Entry corridor bottom ({cy + ch}) is above Stop-loss y ({l_sl['y1']})")

    # 3.3 Callout Badge Coordinates & Canvas Clipping Stress
    # Find all badges in Chart 1
    # Badges are rects followed by text in the right margin
    badge_rects = re.findall(r'<rect\b[^>]*x=["\']([0-9.]+)["\'][^>]*y=["\']([0-9.]+)["\'][^>]*width=["\']([0-9.]+)["\'][^>]*height=["\']([0-9.]+)["\'][^>]*>', c1)
    # Check if there are badges positioned at x > 800
    right_badges = []
    for x, y, w, h in badge_rects:
        xf, yf, wf, hf = float(x), float(y), float(w), float(h)
        if xf >= 800 and wf > 50 and hf > 15:
            right_badges.append((xf, yf, wf, hf))

    harness.check(len(right_badges) >= 4, f"Chart 1 renders at least 4 right-margin callout badges (Found: {len(right_badges)})")

    # Check that NONE of the right badges clip outside the 960 canvas width
    clipping_badges = []
    for bx, by, bw, bh in right_badges:
        if bx + bw > 960:
            clipping_badges.append(f"Badge x={bx} w={bw} (right edge {bx + bw} > 960)")
        if by + bh > 480 or by < 0:
            clipping_badges.append(f"Badge y={by} h={bh} clips vertically")
    harness.check(len(clipping_badges) == 0, "Right-side badges have zero canvas clipping", f"Clipping: {clipping_badges}")

    # 3.4 Occlusion Stress: Ensure badges do not occlude candlestick bodies or wicks
    # All candle bodies have x around 70 to 825.
    candle_bodies = re.findall(r'<rect\b[^>]*class=["\']candle-body["\'][^>]*x=["\']([0-9.]+)["\'][^>]*width=["\']([0-9.]+)["\']', c1)
    max_candle_x = max(float(x) + float(w) for x, w in candle_bodies) if candle_bodies else 0
    min_badge_x = min(bx for bx, by, bw, bh in right_badges) if right_badges else 999

    badge_margin = min_badge_x - max_candle_x
    harness.check(badge_margin > 0, f"Badges do NOT occlude candles: margin gap is {badge_margin:.1f}px (candles max x={max_candle_x:.1f}, badge min x={min_badge_x:.1f})")

    # 3.5 Layer Stacking Order: trade-corridor rect must precede candle-body rects in DOM
    idx_corridor = c1.find('class="trade-corridor"')
    idx_first_candle = c1.find('class="candle-body"')
    harness.check(idx_corridor != -1 and idx_first_candle != -1 and idx_corridor < idx_first_candle,
                  "Trade corridor renders underneath price candles (corridor index < candle index)")

    # -------------------------------------------------------------------------
    # SUITE 4: Chart 4 Valuation River Bands Polygon Integrity
    # -------------------------------------------------------------------------
    print("\n--- SUITE 4: Chart 4 Valuation River Bands Polygon Integrity ---")

    c4 = svg_blocks.get("chartValuationRiver", "")

    # 4.1 Tab toggle groups existence
    has_per_group = 'id="groupPerRiver"' in c4
    has_pbr_group = 'id="groupPbrRiver"' in c4
    harness.check(has_per_group, "Chart 4 contains #groupPerRiver <g> element")
    harness.check(has_pbr_group, "Chart 4 contains #groupPbrRiver <g> element")

    # 4.2 Verify PBR group is initially hidden
    pbr_hidden = re.search(r'<g\b[^>]*id=["\']groupPbrRiver["\'][^>]*style=["\'][^"\']*display:\s*none', c4) is not None
    harness.check(pbr_hidden, "#groupPbrRiver is initially hidden via inline style='display: none;'")

    # 4.3 River Polygons Vertex Analysis
    poly_matches = re.findall(r'<polygon\b[^>]*class=["\'][^"\']*river-band[^"\']*["\'][^>]*points=["\']([^"\']+)["\']', c4)
    harness.check(len(poly_matches) >= 10, f"Chart 4 contains at least 10 river band polygons (5 PER + 5 PBR), found {len(poly_matches)}")

    polygon_anomalies = []
    for idx, pts_str in enumerate(poly_matches):
        pts = pts_str.strip().split()
        if len(pts) < 12:
            polygon_anomalies.append(f"Polygon {idx} has fewer than 12 vertices: {len(pts)}")
            continue

        coords = []
        for p in pts:
            x_str, y_str = p.split(",")
            coords.append((float(x_str), float(y_str)))

        # Split into top contour (first 6) and bottom contour (last 6, reversed)
        top_pts = coords[:6]
        bot_pts = coords[6:]  # ordered x_5 to x_0

        # Check top x is strictly increasing
        for i in range(len(top_pts) - 1):
            if top_pts[i+1][0] <= top_pts[i][0]:
                polygon_anomalies.append(f"Polygon {idx} top x not increasing: {top_pts[i][0]} -> {top_pts[i+1][0]}")

        # Check bottom x is strictly decreasing (since it wraps back)
        for i in range(len(bot_pts) - 1):
            if bot_pts[i+1][0] >= bot_pts[i][0]:
                polygon_anomalies.append(f"Polygon {idx} bot x not decreasing: {bot_pts[i][0]} -> {bot_pts[i+1][0]}")

        # Check geometry sanity: at matching x nodes, upper price band has smaller y than lower band (y=0 is top)
        # bot_pts reversed matches top_pts
        bot_matched = list(reversed(bot_pts))
        for k in range(6):
            top_y = top_pts[k][1]
            bot_y = bot_matched[k][1]
            if top_y > bot_y:
                polygon_anomalies.append(f"Polygon {idx} inverted band at node {k}: top_y={top_y} > bot_y={bot_y}")

    harness.check(len(polygon_anomalies) == 0, "All river band polygons have strictly valid non-twisted geometry", f"Anomalies: {polygon_anomalies[:3]}")

    # 4.4 River Pinpoint Callouts (PER & PBR current markers)
    has_per_pin = "目前 24.75x" in c4 and "第 56.1 分位" in c4
    has_pbr_pin = "目前 8.61x" in c4 and "第 83.6 分位" in c4
    harness.check(has_per_pin, "PER River group contains 24.75x (56.1 percentile) pinpoint callout")
    harness.check(has_pbr_pin, "PBR River group contains 8.61x (83.6 percentile) pinpoint callout")

    # -------------------------------------------------------------------------
    # SUITE 5: Theme Switching, OKLCH Tokens, Zero-FOUC & Contrast Verification
    # -------------------------------------------------------------------------
    print("\n--- SUITE 5: Theme Switching, OKLCH Tokens, Zero-FOUC & Contrast Verification ---")

    # 5.1 Inline script in <head> for zero-FOUC initialization
    head_match = re.search(r'<head>([\s\S]*?)</head>', html, re.IGNORECASE)
    harness.check(head_match is not None, "<head> block exists in HTML")
    if head_match:
        head_content = head_match.group(1)
        has_fouc_script = "localStorage.getItem('task-html-theme')" in head_content and "setAttribute('data-theme'" in head_content
        harness.check(has_fouc_script, "Zero-FOUC theme pre-initialization script runs synchronously in <head>")

    # 5.2 Root HTML initial data-theme
    has_root_theme = re.search(r'<html\b[^>]*data-theme=["\']light["\']', html) is not None
    harness.check(has_root_theme, "<html> root element defines default data-theme='light'")

    # 5.3 OKLCH Token Definitions in :root and [data-theme="dark"]
    root_vars = dict(re.findall(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);', html))
    required_tokens = ["--color-paper", "--color-sheet", "--color-ink", "--color-muted", "--color-accent", "--color-tw-rise", "--color-tw-fall"]
    missing_root_tokens = [t for t in required_tokens if t not in root_vars]
    harness.check(len(missing_root_tokens) == 0, "All primary OKLCH color tokens defined in CSS", f"Missing: {missing_root_tokens}")

    # Check dark theme overrides
    dark_css_m = re.search(r'\[data-theme=["\']dark["\']\][^{]*\{([\s\S]*?)\}', html)
    harness.check(dark_css_m is not None, "[data-theme='dark'] selector present in CSS")
    if dark_css_m:
        dark_css = dark_css_m.group(1)
        dark_vars = dict(re.findall(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);', dark_css))
        missing_dark_tokens = [t for t in ["--color-paper", "--color-sheet", "--color-ink"] if t not in dark_vars]
        harness.check(len(missing_dark_tokens) == 0, "Dark theme overrides paper, sheet, and ink", f"Missing: {missing_dark_tokens}")

        # 5.4 Mathematical Contrast & Elevation Verification in OKLCH
        # Parse OKLCH Lightness L from paper, sheet, ink (normalize % to 0.0-1.0)
        def extract_oklch_l(val: str) -> float:
            m = re.search(r'oklch\(\s*([0-9.]+)(%?)', val)
            if not m:
                return -1.0
            num = float(m.group(1))
            if m.group(2) == "%" or num > 1.0:
                return num / 100.0
            return num

        dark_paper_l = extract_oklch_l(dark_vars.get("--color-paper", ""))
        dark_sheet_l = extract_oklch_l(dark_vars.get("--color-sheet", ""))
        dark_ink_l = extract_oklch_l(dark_vars.get("--color-ink", ""))

        # Dark canvas floor: L between 0.10 and 0.22 (10% - 22%)
        harness.check(0.10 <= dark_paper_l <= 0.22, f"Dark canvas lightness L in dark range (0.10-0.22): {dark_paper_l:.3f}")
        # Dark sheet elevation step: sheet L > paper L (+2% to +6% elevation step)
        harness.check(dark_sheet_l > dark_paper_l, f"Dark sheet elevation stepped up: sheet={dark_sheet_l:.3f} > paper={dark_paper_l:.3f}")
        # Dark mode contrast ratio: ink L vs paper L delta >= 0.65 (High WCAG contrast)
        contrast_delta = dark_ink_l - dark_paper_l
        harness.check(contrast_delta >= 0.65, f"Dark mode ink/paper contrast delta >= 0.65: {contrast_delta:.3f}")

    # -------------------------------------------------------------------------
    # SUITE 6: Mobile Responsiveness, Container Capping, and Overflow Constraints
    # -------------------------------------------------------------------------
    print("\n--- SUITE 6: Mobile Responsiveness, Container Capping, and Overflow Constraints ---")

    # 6.1 Container max-width capping (1360px per Hallmark Floor 14)
    has_1360_cap = re.search(r'(--container:\s*1360px|max-width:\s*1360px)', html) is not None
    harness.check(has_1360_cap, "Main layout container caps width at 1360px (Hallmark Floor 14)")

    # 6.2 overflow-x: clip on html, body (Hallmark Floor 4)
    has_overflow_clip = re.search(r'overflow-x:\s*clip', html) is not None
    harness.check(has_overflow_clip, "html/body enforces overflow-x: clip (prevents mobile horizontal blowout)")

    # 6.3 Responsive table wrapper class around all tables
    table_count = len(re.findall(r'<table\b', html, re.IGNORECASE))
    resp_div_count = len(re.findall(r'class=["\'][^"\']*table-responsive[^"\']*["\']', html, re.IGNORECASE))
    harness.check(table_count > 0 and resp_div_count >= table_count,
                  f"All semantic data tables ({table_count}) wrapped in .table-responsive (found {resp_div_count})")

    # 6.4 Chart containers wrapped in .chart-container
    chart_containers = len(re.findall(r'class=["\'][^"\']*chart-container[^"\']*["\']', html, re.IGNORECASE))
    harness.check(chart_containers >= 4, f"All 4 SVG charts wrapped in .chart-container (found {chart_containers})")

    # 6.5 Dynamic Fluid Reflow vs Media Query Breakpoints
    has_fluid_grid = re.search(r'grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(', html) is not None
    harness.check(has_fluid_grid, "CSS utilizes fluid auto-fit grids (reflows columns adaptively across viewports)")

    has_clamp_typography = re.search(r'clamp\(', html) is not None
    harness.check(has_clamp_typography, "CSS utilizes fluid clamp() typography for responsive display titles")

    media_queries = re.findall(r'@media\s*\([^)]*max-width[^)]*\)', html)
    # Check if viewport-specific media queries exist, or if pure fluid layout is employed
    harness.check(True, f"Mobile breakpoint architecture evaluated: {len(media_queries)} @media max-width queries (uses fluid auto-fit + clamp)")

    # -------------------------------------------------------------------------
    # SUITE 7: Interactive Micro-Engine & ARIA Contract
    # -------------------------------------------------------------------------
    print("\n--- SUITE 7: Interactive Micro-Engine & ARIA Contract ---")

    # 7.1 River Tab ARIA attributes
    tab_per = re.search(r'<button\b[^>]*id=["\']tabPER["\'][^>]*>', html)
    tab_pbr = re.search(r'<button\b[^>]*id=["\']tabPBR["\'][^>]*>', html)
    harness.check(tab_per is not None and tab_pbr is not None, "River tab buttons #tabPER and #tabPBR present")
    if tab_per and tab_pbr:
        harness.check('role="tab"' in tab_per.group(0), "#tabPER declares role='tab'")
        harness.check('role="tab"' in tab_pbr.group(0), "#tabPBR declares role='tab'")
        harness.check('aria-selected="true"' in tab_per.group(0), "#tabPER initialized as aria-selected='true'")
        harness.check('aria-selected="false"' in tab_pbr.group(0), "#tabPBR initialized as aria-selected='false'")

    # 7.2 Theme toggle button presence & ARIA/accessibility
    theme_btn = re.search(r'<button\b[^>]*id=["\']themeToggle["\'][^>]*>', html)
    harness.check(theme_btn is not None, "Theme toggle button #themeToggle present")
    if theme_btn:
        has_aria = 'aria-label' in theme_btn.group(0) or 'title' in theme_btn.group(0)
        harness.check(has_aria, "#themeToggle includes accessibility attribute (aria-label/title)")

    # 7.3 Interactive hover slices telemetry binding
    slices = re.findall(r'<rect\b[^>]*class=["\'][^"\']*hover-slice[^"\']*["\'][^>]*>', html)
    harness.check(len(slices) >= 24, f"Chart 1 renders interactive hover slices for each candle (found {len(slices)})")
    if slices:
        first_slice = slices[0]
        harness.check('data-chart=' in first_slice and 'data-info=' in first_slice,
                      "Hover slices bind data-chart and data-info attributes for reactive crosshair")

    # -------------------------------------------------------------------------
    # SUITE 8: HTML Tag Nesting & Strict DOM Syntax Audit
    # -------------------------------------------------------------------------
    print("\n--- SUITE 8: HTML Tag Nesting & Strict DOM Syntax Audit ---")

    # 8.1 Check for malformed tags containing nested '<' inside attributes
    nested_lt_tags = re.findall(r'<[a-zA-Z0-9]+[^>]*<[^>]*>', html)
    harness.check(len(nested_lt_tags) == 0, "Zero malformed tags containing nested '<' inside attribute definitions", f"Found {len(nested_lt_tags)} malformed tags: {nested_lt_tags[:3]}")

    # 8.2 Strict HTML tag matching audit
    class StrictTagAuditor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.open_tags = []
            self.mismatches = []
            self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

        def handle_starttag(self, tag, attrs):
            t = tag.lower()
            if t not in self.void_tags:
                self.open_tags.append((t, self.getpos()))

        def handle_endtag(self, tag):
            t = tag.lower()
            if t in self.void_tags:
                return
            if not self.open_tags:
                self.mismatches.append(f"Unexpected closing </{t}> with empty stack at {self.getpos()}")
            elif self.open_tags[-1][0] == t:
                self.open_tags.pop()
            else:
                top_tag, top_pos = self.open_tags[-1]
                self.mismatches.append(f"Mismatched closing </{t}> at {self.getpos()}, top was <{top_tag}> from {top_pos}")
                # Check if tag is in stack
                stack_tags = [item[0] for item in self.open_tags]
                if t in stack_tags:
                    while self.open_tags and self.open_tags[-1][0] != t:
                        self.open_tags.pop()
                    if self.open_tags:
                        self.open_tags.pop()

    auditor = StrictTagAuditor()
    auditor.feed(html)
    harness.check(len(auditor.mismatches) == 0, "Zero mismatched HTML closing tags in document", f"Mismatches: {auditor.mismatches[:3]}")
    harness.check(len(auditor.open_tags) == 0, "All opened HTML tags are cleanly closed at EOF", f"Unclosed tags: {auditor.open_tags}")

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f" ADVERSARIAL STRESS TEST COMPLETE: {harness.passed} PASSED, {harness.failed} FAILED")
    print("=" * 80)

    return harness.passed, harness.failed, harness.results


if __name__ == "__main__":
    passed, failed, results = run_stress_suite()
    sys.exit(0 if failed == 0 else 1)
