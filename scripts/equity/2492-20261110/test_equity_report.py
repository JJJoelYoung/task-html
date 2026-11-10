#!/usr/bin/env python3
"""Standard-library tests for the 2492 equity report (report-contract.md section 7)."""

import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_report as g  # noqa: E402

D, A = g.load()
X = g.derive(D, A)
ROOT = g.ROOT
REPORT = g.report_path(D, A)
REL = REPORT.relative_to(ROOT).as_posix()
HTML = REPORT.read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def gap_mentions(word):
    return any(word.lower() in gp.lower() for gp in D["gaps"])


class Data(unittest.TestCase):
    def test_top_level(self):
        self.assertRegex(D["asof"], r"^\d{4}-\d{2}-\d{2}$")
        for k in ("price", "institutional", "foreign_holding", "margin", "revenue", "financials", "valuation"):
            self.assertIn(k, D["sources"], k)

    def test_price_group(self):
        m = D["price"]["metrics"]
        for k in ("close", "ma5", "ma10", "ma20", "bias_ma20_pct", "w20_high", "w20_low", "squeeze", "alignment",
                  "vol_avg20_lots", "spike_days", "dryup_days", "float_settling", "high60", "low60"):
            self.assertIn(k, m, k)
            self.assertIsNotNone(m[k], k)
        self.assertGreaterEqual(len(D["price"]["series"]), 60)
        closes = [s["close"] for s in D["price"]["series"][-20:]]
        self.assertAlmostEqual(m["ma20"], round(sum(closes) / 20, 2), places=2)

    def test_chip_groups(self):
        self.assertEqual(len(D["institutional"]["daily"]), 20)
        if D["institutional"]["cost_zone"] is None:
            self.assertTrue(gap_mentions("cost zone"))
        for k in ("first", "last", "high", "low", "change_pp"):
            self.assertIsNotNone(D["foreign_holding"][k])
        for k in ("margin_last", "short_last", "short_margin_ratio_pct", "short_margin_level"):
            self.assertIsNotNone(D["margin"][k])

    def test_operations(self):
        r, f = D["revenue"], D["financials"]
        self.assertEqual(len(r["last12"]), 12)
        self.assertIsNotNone(r["ytd_yoy_pct"])
        self.assertEqual(len(f["last4"]), 4)
        self.assertAlmostEqual(f["ttm_eps"], round(sum(q["eps"] for q in f["quarters"][-4:]), 2))
        if f["cash_conversion"] is None:
            self.assertTrue(gap_mentions("cash"))
        self.assertIsNotNone(f["quarters"][-1]["dsi_days"])

    def test_valuation(self):
        for k in ("PER", "PBR"):
            b = D["valuation"][k]
            vals = [b[p] for p in ("p10", "p25", "p50", "p75", "p90")]
            self.assertEqual(vals, sorted(vals))
            self.assertIsNotNone(b["current_percentile"])
        self.assertEqual(len(D["peers"]["rows"]), 4)
        self.assertIsNotNone(D["peers"]["median"]["PER"])


class Analysis(unittest.TestCase):
    def test_probabilities(self):
        self.assertEqual(sum(s["probability"] for s in A["scenarios"]), 100)

    def test_basis(self):
        for group in ("scenarios", "peers", "catalysts", "risks"):
            for item in A[group]:
                self.assertTrue(item.get("basis", "").strip(), (group, item))
        self.assertEqual(len(A["peers"]), 3)
        self.assertTrue(3 <= len(A["catalysts"]) <= 5)
        self.assertTrue(3 <= len(A["risks"]) <= 5)
        self.assertTrue(2 <= len(A["thesis_breakers"]) <= 3)

    def test_anchoring(self):
        b = D["valuation"]["PER"]
        sc = {s["name"]: s for s in A["scenarios"]}
        checks = {
            "Bear": sc["Bear"]["multiple"] <= b["p25"],
            "Base": b["p25"] <= sc["Base"]["multiple"] <= b["p75"],
            "Bull": sc["Bull"]["multiple"] <= b["p90"],
        }
        for name, ok in checks.items():
            if not ok:
                self.assertIn("P", sc[name]["basis"], f"{name} multiple outside bounds needs justification")


def text_of(attr, value):
    m = re.search(rf'{attr}="{re.escape(value)}"[^>]*>([^<]*)<', HTML)
    return m.group(1) if m else None


class Calculations(unittest.TestCase):
    def test_targets(self):
        close = D["price"]["metrics"]["close"]
        for s in A["scenarios"]:
            t = g.rt(s["eps"] * s["multiple"])
            self.assertIn(g.fp(t), HTML)
            self.assertIn(g.fs(round((t / close - 1) * 100, 1)), HTML)
        w = g.rt(sum(s["probability"] * g.rt(s["eps"] * s["multiple"]) for s in A["scenarios"]) / 100)
        self.assertEqual(w, X["weighted_target"])
        self.assertIn(g.fp(w), HTML)

    def test_rating(self):
        up = X["base"]["upside_pct"]
        exp = "買進" if up > 15 else ("中立" if up >= -5 else "賣出")
        self.assertEqual(X["rating_zh"], exp)

    def test_trade_setup(self):
        m = D["price"]["metrics"]
        lo, hi = sorted((m["ma10"], m["ma20"]))
        z = D["institutional"]["cost_zone"]
        if z and max(lo, z["low"]) <= min(hi, z["high"]):
            lo, hi = max(lo, z["low"]), min(hi, z["high"])
        lo, hi = g.rt(lo), g.rt(hi)
        entry = g.rt((lo + hi) / 2)
        self.assertEqual(entry, X["entry"])
        cands = [c for c in (m["w20_maxvol_low"], g.rt(m["ma20"] * 0.97)) if c < lo]
        stop = g.rt(max(cands)) if cands else g.rt(lo * 0.95)
        self.assertEqual(stop, X["hard_stop"])
        self.assertEqual(g.rt(m["high60"] * 0.95), X["breakout_stop"])
        t2 = X["base"]["target"]
        self.assertEqual(round((t2 - entry) / (entry - stop), 2), X["rr_pullback"])
        self.assertEqual(round((t2 - m["high60"]) / (m["high60"] - X["breakout_stop"]), 2), X["rr_breakout"])
        self.assertEqual(text_of("data-rr", "pullback"), g.rr_txt(X["rr_pullback"]))
        self.assertEqual(text_of("data-rr", "breakout"), g.rr_txt(X["rr_breakout"]))
        for v in (X["entry"], X["hard_stop"], X["breakout_stop"], X["t1"], X["trigger"]):
            self.assertIn(g.fp(v), HTML)


class Structure(unittest.TestCase):
    def test_sections(self):
        for i in range(1, 7):
            self.assertRegex(HTML, rf'<section id="dim{i}"')

    def test_kpis(self):
        exp = {
            "close": g.fp(X["close"]),
            "rating": X["rating_zh"],
            "target": g.fp(X["base"]["target"]),
            "upside": g.fs(X["base"]["upside_pct"]),
            "rr": g.rr_txt(X["rr_pullback"]),
            "asof": D["asof"],
        }
        for k, v in exp.items():
            self.assertEqual(text_of("data-kpi", k), v, k)

    def test_dim6_lines(self):
        dim6 = HTML[HTML.index('<section id="dim6"'):]
        dim6 = dim6[: dim6.index("</section>")]
        for key, val in (("entry", X["entry"]), ("t1", X["t1"]), ("t2", X["t2"]), ("sl", X["hard_stop"])):
            m = re.search(rf'data-line="{key}" data-value="([\d.]+)"', dim6)
            self.assertIsNotNone(m, key)
            self.assertAlmostEqual(float(m.group(1)), val)

    def test_labels(self):
        self.assertIn("本報告僅供研究參考，不構成任何投資建議。", HTML)
        self.assertIn(D["asof"], HTML)
        self.assertIn("分析師判斷", HTML)
        for gp in D["gaps"]:
            self.assertIn(g.E(gp), HTML)
        for fig in re.findall(r'<figure class="fig">.*?</figure>', HTML, re.S):
            cap = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S).group(1)
            self.assertIn("FinMind", cap)
            self.assertRegex(cap, r"\d{4}-\d{2}")

    def test_themes_and_mobile(self):
        self.assertIn("prefers-color-scheme: dark", HTML)
        self.assertIn('id="mode-toggle"', HTML)
        self.assertIn('name="viewport"', HTML)
        self.assertIn("overflow-x: clip", HTML)
        self.assertIn("data-tip=", HTML)


class Portal(unittest.TestCase):
    def test_index_card(self):
        cards = re.findall(r'<article class="artifact-card".*?</article>', INDEX, re.S)
        mine = [c for c in cards if REL in c]
        self.assertEqual(len(mine), 1)
        c = mine[0]
        self.assertIn('data-category="equity"', c)
        self.assertIn(f'<span class="artifact-date">{D["asof"]}</span>', c)
        self.assertIn(f"NT$ {g.fp(X['base']['target'])}", c)
        self.assertIn(g.fs(X["base"]["upside_pct"]), c)
        self.assertIn(X["rating_zh"], c)
        self.assertIn(f"{g.rr_txt(X['rr_pullback'])} : 1", c)
        self.assertIn("aria-label=", c)

    def test_readme_row(self):
        rows = [ln for ln in README.splitlines() if ln.startswith("|") and REL in ln]
        self.assertEqual(len(rows), 1)
        self.assertIn("View Online", rows[0])


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.refs.append(v)


def relative_refs(text):
    p = Links()
    p.feed(text)
    out = []
    for r in p.refs:
        u = urlparse(r)
        if u.scheme or r.startswith("#") or r.startswith("//") or r.startswith("mailto:"):
            continue
        out.append(unquote(u.path))
    return out


class LinkCheck(unittest.TestCase):
    def test_report_links(self):
        for r in relative_refs(HTML):
            self.assertTrue((REPORT.parent / r).exists(), r)

    def test_card_links(self):
        card = [c for c in re.findall(r'<article class="artifact-card".*?</article>', INDEX, re.S) if REL in c][0]
        for r in relative_refs(card):
            self.assertTrue((ROOT / r).exists(), r)

    def test_readme_links(self):
        row = [ln for ln in README.splitlines() if REL in ln][0]
        for target in re.findall(r"\]\((\./[^)]+)\)", row):
            self.assertTrue((ROOT / target).exists(), target)


if __name__ == "__main__":
    unittest.main(verbosity=1)
