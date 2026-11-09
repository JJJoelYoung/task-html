#!/usr/bin/env python3
"""
Empirical Adversarial Frontend & DOM Integrity Stress Harness
Challenger 2: Adversarial Frontend & DOM Integrity Verifier
Project: 2501 Cathay Real Estate Equity Research Report

Verifies:
1. DOM Structural Rigor & XML/SVG Bounding Box Integrity
2. Script-Disabled Standalone Rendering & Co-located Tables
3. Responsive Grid, Viewport & Media Query Breakpoints (375px/480px/768px/1024px)
4. Print Fidelity (@media print, page breaks, A4 pagination, print color adjustment)
5. Exhaustive Placeholder Scan (undefined, NaN, null, TODO, template tags)
6. Color Contrast & Accessibility (OKLCH, WCAG AAA, ARIA)
"""

import sys
import os
import re
import math
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set

HTML_PATH = Path("2501_Cathay_Real_Estate_Equity_Report.html")

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check(self, condition: bool, message: str):
        if condition:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(message)

    def warn(self, message: str):
        self.warnings.append(message)


# ----------------------------------------------------------------------
# 1. DOM Structural Rigor: Tag Balancing, Stack Verification & SVG Box
# ----------------------------------------------------------------------

HTML5_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

class StrictTagStackParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: List[Tuple[str, int, int]] = []
        self.mismatches: List[str] = []
        self.duplicate_ids: Dict[str, int] = {}
        self.ids_seen: Set[str] = set()
        self.elements_count = 0
        self.current_tags: Set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.elements_count += 1
        tag_lower = tag.lower()
        self.current_tags.add(tag_lower)

        for k, v in attrs:
            if k.lower() == "id" and v:
                if v in self.ids_seen:
                    self.duplicate_ids[v] = self.duplicate_ids.get(v, 1) + 1
                else:
                    self.ids_seen.add(v)

        if tag_lower in HTML5_VOID_ELEMENTS:
            return

        self.stack.append((tag_lower, self.getpos()[0], self.getpos()[1]))

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in HTML5_VOID_ELEMENTS:
            return

        if not self.stack:
            pos = self.getpos()
            self.mismatches.append(f"Unexpected closing tag </{tag_lower}> at line {pos[0]}:{pos[1]} with empty stack")
            return

        top_tag, line, col = self.stack[-1]
        if top_tag == tag_lower:
            self.stack.pop()
        else:
            stack_tags = [t[0] for t in self.stack]
            if tag_lower in stack_tags:
                idx = len(stack_tags) - 1 - stack_tags[::-1].index(tag_lower)
                unclosed = [t[0] for t in self.stack[idx+1:]]
                pos = self.getpos()
                self.mismatches.append(f"Mismatched closing tag </{tag_lower}> at line {pos[0]}:{pos[1]}. Unclosed: {unclosed}")
                self.stack = self.stack[:idx]
            else:
                pos = self.getpos()
                self.mismatches.append(f"Stray closing tag </{tag_lower}> at line {pos[0]}:{pos[1]} (expected </{top_tag}>)")


def test_dom_structural_rigor(html_content: str) -> TestResult:
    res = TestResult("1. DOM Structural Rigor & SVG Box-Model Integrity")
    
    # 1.1 DOCTYPE
    res.check(html_content.strip().startswith("<!DOCTYPE html>"), "Document must start with <!DOCTYPE html>")
    
    # 1.2 Tag balance & hierarchy
    parser = StrictTagStackParser()
    try:
        parser.feed(html_content)
        res.check(len(parser.mismatches) == 0, f"No mismatched or stray closing tags (found {len(parser.mismatches)})")
        res.check(len(parser.stack) == 0, f"All non-void tags properly closed. Remaining: {parser.stack}")
        res.check(len(parser.duplicate_ids) == 0, f"DOM element IDs must be unique. Duplicates: {parser.duplicate_ids}")
        res.check(parser.elements_count > 100, f"Rich DOM structure ({parser.elements_count} elements)")
        res.check("html" in parser.current_tags, "Contains <html>")
        res.check("head" in parser.current_tags, "Contains <head>")
        res.check("body" in parser.current_tags, "Contains <body>")
        res.check("header" in parser.current_tags, "Contains <header>")
        res.check("footer" in parser.current_tags, "Contains <footer>")
        res.check("main" in parser.current_tags or "section" in parser.current_tags, "Contains <main> or <section>")
    except Exception as e:
        res.check(False, f"DOM parsing exception: {str(e)}")

    # 1.3 SVG XML Well-Formedness & Bounding Box Coordinates Check
    svg_blocks = re.findall(r"(<svg[\s\S]*?</svg>)", html_content, re.IGNORECASE)
    res.check(len(svg_blocks) >= 4, f"Document must contain at least 4 inline SVG charts (found {len(svg_blocks)})")
    
    for i, svg in enumerate(svg_blocks, 1):
        try:
            cleaned_svg = svg
            if "xmlns" not in cleaned_svg:
                cleaned_svg = cleaned_svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            cleaned_svg = re.sub(r"&nbsp;", " ", cleaned_svg)
            root = ET.fromstring(cleaned_svg)
            res.check(root.tag.endswith("svg"), f"SVG #{i} root element is valid svg")
            vb_str = root.attrib.get("viewBox", "")
            res.check(bool(vb_str), f"SVG #{i} must have a viewBox attribute for responsiveness")
            
            if vb_str:
                vx, vy, vw, vh = [float(x) for x in vb_str.split()]
                out_of_bounds = []
                
                def inspect_svg_elem(elem, in_trans=False):
                    has_trans = in_trans or bool(elem.attrib.get("transform"))
                    tag = elem.tag.split("}")[-1]
                    if not has_trans and "y" in elem.attrib:
                        try:
                            y = float(elem.attrib["y"])
                            if y < vy or y > vy + vh:
                                out_of_bounds.append(f"<{tag} y='{y}'> (text='{elem.text}')")
                        except ValueError:
                            pass
                    for ch in elem:
                        inspect_svg_elem(ch, has_trans)

                inspect_svg_elem(root)
                res.check(len(out_of_bounds) == 0, 
                          f"SVG #{i} visual elements must stay within viewBox [0, {vh}]. Found {len(out_of_bounds)} clipped out-of-bounds elements: {out_of_bounds[:3]}")

        except ET.ParseError as err:
            res.check(False, f"SVG #{i} is not well-formed XML: {str(err)}")

    return res


# ----------------------------------------------------------------------
# 2. Script-Disabled Durability & Standalone Capability
# ----------------------------------------------------------------------

def test_script_disabled_durability(html_content: str) -> TestResult:
    res = TestResult("2. Script-Disabled Durability")
    
    # Check for script tags
    scripts = re.findall(r"<script[\s\S]*?</script>", html_content, re.IGNORECASE)
    res.check(len(scripts) == 0, f"Standalone durable report must have 0 client-side <script> tags for 100% JS-disabled rendering (found {len(scripts)})")
    
    # Check for inline event handlers
    inline_events = re.findall(r'\son[a-z]+=["\'][^"\']*["\']', html_content, re.IGNORECASE)
    res.check(len(inline_events) == 0, f"No inline JS event handlers found (found {len(inline_events)})")

    # Verify inline SVGs are directly in markup
    svg_matches = re.findall(r"<svg[\s\S]*?</svg>", html_content, re.IGNORECASE)
    res.check(len(svg_matches) >= 4, f"Charts are pre-rendered inline vector SVGs (found {len(svg_matches)})")

    # Verify co-located tables with accessible semantic elements
    tables = re.findall(r"<table[\s\S]*?</table>", html_content, re.IGNORECASE)
    res.check(len(tables) >= 4, f"Data is co-located in accessible HTML tables (found {len(tables)})")
    
    for idx, table in enumerate(tables, 1):
        has_th = "<th" in table
        has_td = "<td" in table
        has_thead = "<thead" in table
        res.check(has_th and has_td, f"Table #{idx} contains both <th> header cells and <td> data cells")
        res.check(has_thead, f"Table #{idx} contains <thead> structural container")

    # Font fallbacks in CSS variables or font-family
    has_font_fallbacks = bool(re.search(r"(?:font-family|--font-[a-z]+):[^;]+(?:sans-serif|serif|monospace)", html_content))
    res.check(has_font_fallbacks, "Font system declares offline system fallback fonts (sans-serif, serif, monospace)")

    return res


# ----------------------------------------------------------------------
# 3. Responsive & Media Query Stress
# ----------------------------------------------------------------------

def test_responsive_layout(html_content: str) -> TestResult:
    res = TestResult("3. Responsive Layout & Media Queries")

    # Viewport meta tag
    viewport = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*>', html_content, re.IGNORECASE)
    res.check(bool(viewport), "HTML has a <meta name='viewport'> tag")
    if viewport:
        vp_content = viewport.group(0)
        res.check("width=device-width" in vp_content, "Viewport meta includes 'width=device-width'")
        res.check("initial-scale=1" in vp_content, "Viewport meta includes 'initial-scale=1'")

    # Extract CSS
    styles = re.findall(r"<style[\s\S]*?</style>", html_content, re.IGNORECASE)
    combined_css = "\n".join(styles)

    # Max-width container
    has_max_width = bool(re.search(r"max-width:\s*(?:var\(--container\)|1[0-4]\d\dpx|min\(|100%)", combined_css))
    res.check(has_max_width, "Container specifies bounded max-width (e.g. 1360px)")

    # Media queries
    media_queries = re.findall(r"@media[^{]+\{", combined_css)
    res.check(len(media_queries) >= 3, f"CSS defines responsive media queries (found {len(media_queries)})")

    # Breakpoints (1024px, 768px, 480px)
    has_1024 = bool(re.search(r"@media[^{]*max-width:\s*1024px", combined_css))
    res.check(has_1024, "CSS defines 1024px desktop/tablet breakpoint")

    has_768 = bool(re.search(r"@media[^{]*max-width:\s*768px", combined_css))
    res.check(has_768, "CSS defines 768px tablet breakpoint")

    has_480 = bool(re.search(r"@media[^{]*max-width:\s*480px", combined_css))
    res.check(has_480, "CSS defines 480px mobile breakpoint")

    # Table overflow-x: auto
    has_table_scroll = bool(re.search(r"\.table-wrap\s*\{[^}]*overflow-x:\s*auto", combined_css))
    res.check(has_table_scroll, ".table-wrap specifies 'overflow-x: auto' for horizontal scrolling on mobile")

    # SVG fluid scaling
    has_svg_fluid = bool(re.search(r"\.chart-svg\s*\{[^}]*width:\s*100%", combined_css))
    res.check(has_svg_fluid, ".chart-svg specifies 'width: 100%' for fluid responsive vector rendering")

    # Column count consistency across all tables
    tables = re.findall(r"<table[\s\S]*?</table>", html_content, re.IGNORECASE)
    for idx, t in enumerate(tables, 1):
        th_count = len(re.findall(r"<th[\s>]", t))
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", t)
        for r_i, r in enumerate(rows):
            td_count = len(re.findall(r"<td[\s>]", r))
            if td_count > 0:
                res.check(td_count == th_count, f"Table #{idx} row #{r_i} column count matches header ({td_count} == {th_count})")

    return res


# ----------------------------------------------------------------------
# 4. Print Fidelity & Print Rules (@media print)
# ----------------------------------------------------------------------

def test_print_fidelity(html_content: str) -> TestResult:
    res = TestResult("4. Print Fidelity & Print Rules")

    # Check presence of @media print
    print_match = re.search(r"@media\s+print\s*\{([\s\S]*?)\}(?:\s*@media|\s*</style>|\s*\Z)", html_content)
    res.check(bool(print_match), "CSS contains explicit '@media print' rules")
    
    if print_match:
        print_css = print_match.group(1)
        
        # Check break-inside: avoid
        has_break_inside = bool(re.search(r"(?:break-inside|page-break-inside)\s*:\s*avoid", print_css))
        res.check(has_break_inside, "Print CSS specifies 'break-inside: avoid' on cards and tables")

        # Check @page size A4 rule
        has_page_rule = bool(re.search(r"@page\s*\{[^}]*size:\s*A4", print_css))
        res.check(has_page_rule, "Print CSS defines '@page { size: A4; margin: 12mm; }'")

        # High contrast overrides
        has_bg_override = "background: #ffffff" in print_css or "background-color: #ffffff" in print_css
        res.check(has_bg_override, "Print CSS overrides body background to clean white (#ffffff)")

        has_color_override = "color: #000000" in print_css
        res.check(has_color_override, "Print CSS overrides body text to high-contrast black (#000000)")

        # print-color-adjust
        has_color_adjust = bool(re.search(r"(?:print-color-adjust|-webkit-print-color-adjust)\s*:\s*exact", print_css))
        if not has_color_adjust:
            res.warn("Recommended: add 'print-color-adjust: exact' to preserve chart background fills when printing")

    return res


# ----------------------------------------------------------------------
# 5. Exhaustive Placeholder Scan
# ----------------------------------------------------------------------

def test_placeholder_scan(html_content: str) -> TestResult:
    res = TestResult("5. Exhaustive Placeholder Scan")

    clean_text = re.sub(r"<style[\s\S]*?</style>", " ", html_content)
    clean_text = re.sub(r"d=['\"][^'\"]+['\"]", " ", clean_text)

    patterns = [
        (r"\bundefined\b", "undefined"),
        (r"\bNaN\b", "NaN"),
        (r"\bnull\b", "null"),
        (r"\bTODO\b", "TODO"),
        (r"\bFIXME\b", "FIXME"),
        (r"\bTBD\b", "TBD"),
        (r"\[placeholder\]", "[placeholder]"),
        (r"\[TBD\]", "[TBD]"),
        (r"lorem\s+ipsum", "lorem ipsum"),
        (r"\{\{.*?\}\}", "{{ template }}"),
        (r"\$\{[^}]+\}", "${ template }"),
        (r"\[insert\s+", "[insert ...]"),
        (r"\bN/A%\b", "N/A%"),
    ]

    for pat, label in patterns:
        matches = re.findall(pat, clean_text, re.IGNORECASE)
        res.check(len(matches) == 0, f"Exhaustive placeholder scan: zero occurrences of '{label}' (found {len(matches)})")

    return res


# ----------------------------------------------------------------------
# 6. Color Contrast & Accessibility (WCAG AAA & OKLCH)
# ----------------------------------------------------------------------

def oklch_to_srgb(l: float, c: float, h: float) -> Tuple[float, float, float]:
    if l > 1.0:
        l = l / 100.0
    h_rad = math.radians(h)
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)

    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b

    L = l_ ** 3
    M = m_ ** 3
    S = s_ ** 3

    r_lin = +4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S
    g_lin = -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S
    b_lin = -0.0041960863 * L - 0.7034186147 * M + 1.7076147010 * S

    def gamma(v: float) -> float:
        v = max(0.0, min(1.0, v))
        if v <= 0.0031308:
            return 12.92 * v
        else:
            return 1.055 * (v ** (1.0 / 2.4)) - 0.055

    return (gamma(r_lin), gamma(g_lin), gamma(b_lin))


def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    def to_linear(c: float) -> float:
        if c <= 0.04045:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    r = to_linear(rgb[0])
    g = to_linear(rgb[1])
    b = to_linear(rgb[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(lum1: float, lum2: float) -> float:
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return (l_max + 0.05) / (l_min + 0.05)


def test_color_contrast_accessibility(html_content: str) -> TestResult:
    res = TestResult("6. Color Contrast & Accessibility")

    # Verify OKLCH declarations
    oklch_tokens = re.findall(r"oklch\(\s*([\d\.]+%?)\s+([\d\.]+)\s+([\d\.]+)\s*\)", html_content)
    res.check(len(oklch_tokens) >= 3, f"Design system declares OKLCH tokens (found {len(oklch_tokens)})")

    # Cathay Emerald Hue ~155
    emerald_hues = [float(t[2]) for t in oklch_tokens if 140 <= float(t[2]) <= 170]
    res.check(len(emerald_hues) > 0, f"Cathay Emerald primary accent matches hue ~155 (found {emerald_hues})")

    # Contrast evaluation
    parsed_colors = {}
    for l_s, c_s, h_s in oklch_tokens:
        l = float(l_s.rstrip("%")) / (100.0 if "%" in l_s else 1.0)
        c = float(c_s)
        h = float(h_s)
        rgb = oklch_to_srgb(l, c, h)
        lum = relative_luminance(rgb)
        parsed_colors[f"oklch({l_s} {c_s} {h_s})"] = (rgb, lum, l)

    bg_tokens = [c for c in parsed_colors.values() if c[2] > 0.85]
    text_tokens = [c for c in parsed_colors.values() if c[2] < 0.35]

    if bg_tokens and text_tokens:
        highest_contrast = 1.0
        for bg in bg_tokens:
            for fg in text_tokens:
                cr = contrast_ratio(bg[1], fg[1])
                if cr > highest_contrast:
                    highest_contrast = cr
        res.check(highest_contrast >= 7.0, f"Primary text/bg contrast satisfies WCAG AAA (>= 7.0:1, calculated: {highest_contrast:.2f}:1)")

    # Taiwan stock directionals
    res.check("tw-rise" in html_content or "▲" in html_content, "Taiwan equity rise semantic token present")
    res.check("tw-fall" in html_content or "▼" in html_content, "Taiwan equity fall semantic token present")

    # Accessibility attributes on SVGs
    svg_accessible = re.findall(r'<svg[^>]*(?:role=["\']img["\']|aria-label|aria-hidden)', html_content, re.IGNORECASE)
    res.check(len(svg_accessible) >= 4, f"SVG charts include accessibility roles/labels (found {len(svg_accessible)})")

    return res


# ----------------------------------------------------------------------
# Main Runner & Aggregate Summary
# ----------------------------------------------------------------------

def run_all_tests():
    if not HTML_PATH.exists():
        print(f"FATAL: HTML deliverable not found at {HTML_PATH.resolve()}")
        sys.exit(1)

    html_content = HTML_PATH.read_text(encoding="utf-8")
    print(f"Loaded {HTML_PATH.name} ({len(html_content)} characters, {len(html_content.splitlines())} lines)")
    print("=" * 80)

    suites = [
        test_dom_structural_rigor(html_content),
        test_script_disabled_durability(html_content),
        test_responsive_layout(html_content),
        test_print_fidelity(html_content),
        test_placeholder_scan(html_content),
        test_color_contrast_accessibility(html_content),
    ]

    total_passed = 0
    total_failed = 0
    all_errors = []

    for suite in suites:
        print(f"\n--- {suite.name} ---")
        print(f"Passed: {suite.passed} | Failed: {suite.failed} | Warnings: {len(suite.warnings)}")
        for err in suite.errors:
            print(f"  [FAIL] {err}")
            all_errors.append(f"{suite.name}: {err}")
        for warn in suite.warnings:
            print(f"  [WARN] {warn}")
        total_passed += suite.passed
        total_failed += suite.failed

    print("\n" + "=" * 80)
    print(f"TOTAL EMPIRICAL VERIFICATION SUMMARY: {total_passed} Passed | {total_failed} Failed")
    print("=" * 80)

    if total_failed == 0:
        print("VERDICT: APPROVE (Zero DOM/layout/integrity defects detected)")
        return 0
    else:
        print(f"VERDICT: REQUEST_CHANGES ({total_failed} defect(s) detected)")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
