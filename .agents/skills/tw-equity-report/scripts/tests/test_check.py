"""Unit tests for check_report.check_research on a temporary work folder."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_report as cr  # noqa: E402

URL = "https://example.com/news/1"


class Research(unittest.TestCase):
    def run_check(self, md, a, page=None):
        with tempfile.TemporaryDirectory() as t:
            work = Path(t)
            if md is not None:
                (work / "research_1234.md").write_text(md, encoding="utf-8")
            c = cr.Check()
            cr.check_research(c, work, "1234", a, page)
            return c.failures

    def fact(self, **kw):
        return {"external_facts": [{"text": "Q3 EPS 4.73", "source": "News", "date": "2026-11-05", "url": URL, **kw}]}

    def test_pass(self):
        self.assertEqual(self.run_check(f"- Q3 EPS 4.73. News, 2026-11-05. <{URL}>", self.fact(),
                                        f'<a href="{URL}">News</a>'), [])

    def test_missing_file(self):
        self.assertIn("research_1234.md missing", self.run_check(None, {})[0])

    def test_fact_without_url(self):
        fails = self.run_check("no links", self.fact(url=""))
        self.assertTrue(any("without url" in f for f in fails))

    def test_url_not_in_research(self):
        a = {"scenarios": [{"basis": f"EPS from {URL}"}]}
        fails = self.run_check("nothing listed", a)
        self.assertTrue(any("not listed" in f for f in fails))

    def test_url_ends_at_cjk_punctuation(self):
        self.assertEqual(cr.urls_in(f"（報導，{URL}）×4；見 {URL}."), {URL})

    def test_fact_not_linked_in_html(self):
        fails = self.run_check(URL, self.fact(), "<p>no link</p>")
        self.assertTrue(any("not linked" in f for f in fails))



class Review(unittest.TestCase):
    def failures(self, text):
        with tempfile.TemporaryDirectory() as t:
            work = Path(t)
            if text is not None:
                (work / "judgment_review_1234.md").write_text(text, encoding="utf-8")
            c = cr.Check()
            cr.check_review(c, work, "1234")
            return c.failures

    def test_present(self):
        self.assertEqual(self.failures("- check 2: Base EPS growth unsupported; fixed.\nfindings: 1"), [])

    def test_missing_or_empty(self):
        self.assertEqual(self.failures(None), ["review: judgment_review_1234.md missing"])
        self.assertEqual(self.failures("  \n"), ["review: judgment_review_1234.md is empty"])


class GenerationMeta(unittest.TestCase):
    @staticmethod
    def minimal_inputs(**gen_overrides):
        band = {"p10": 10.0, "p25": 12.0, "p50": 15.0, "p75": 18.0, "p90": 22.0}
        d = {"valuation": {"PER": band, "PBR": band}}
        a = {
            "valuation_method": "PER",
            "peers": [{"code": f"{i}", "basis": "b"} for i in range(3)],
            "catalysts": [{"title": f"c{i}", "basis": "b"} for i in range(3)],
            "risks": [{"title": f"r{i}", "basis": "b"} for i in range(3)],
            "thesis_breakers": [
                {"title": "tb1", "dataset": "TaiwanStockMonthRevenue", "threshold": "YoY < 0%"},
                {"title": "tb2", "dataset": "TaiwanStockFinancialStatements", "threshold": "OPM < 10%"},
            ],
            "dilution": {"has_cb": False, "has_spo": False, "summary": "None", "basis": "MOPS 2026-11"},
            "scenarios": [
                {"name": "Bull", "multiple": 20.0, "probability": 25, "basis": "b"},
                {"name": "Base", "multiple": 15.0, "probability": 50, "basis": "b"},
                {"name": "Bear", "multiple": 11.0, "probability": 25, "basis": "b"},
            ],
            "generation": {"model": "Gemini 3.8 Pro", "effort": "high", **gen_overrides},
        }
        x = {"scenarios": []}
        return d, a, x

    def test_analysis_requires_generation_model_and_effort(self):
        d, a, x = self.minimal_inputs()
        c = cr.Check()
        cr.check_analysis(c, d, a, x)
        self.assertEqual(c.failures, [])

        a_missing = dict(a)
        a_missing.pop("generation")
        c_missing = cr.Check()
        cr.check_analysis(c_missing, d, a_missing, x)
        self.assertIn("analysis: generation {model, effort} missing", c_missing.failures)

        _, a_blank, _ = self.minimal_inputs(model=" ", effort="")
        c_blank = cr.Check()
        cr.check_analysis(c_blank, d, a_blank, x)
        self.assertIn("analysis: generation.model is empty", c_blank.failures)
        self.assertIn("analysis: generation.effort is empty", c_blank.failures)

    def test_footer_generation_hooks(self):
        a = {"generation": {"model": "Gemini 3.8 Pro", "effort": "high"}}
        good_html = (
            '<html><body><footer class="footer">'
            '模型 <span class="mono" data-meta="model">Gemini 3.8 Pro</span>'
            '（<span class="mono" data-meta="effort">high</span>）'
            "</footer></body></html>"
        )
        c_ok = cr.Check()
        cr.check_generation_meta(c_ok, good_html, a)
        self.assertEqual(c_ok.failures, [])

        outside_footer = '<div data-meta="model">Gemini 3.8 Pro</div><div data-meta="effort">high</div>'
        c_no_footer = cr.Check()
        cr.check_generation_meta(c_no_footer, outside_footer, a)
        self.assertEqual(c_no_footer.failures, ["html: <footer> element missing for generation metadata"])

        mismatched = '<footer class="footer"><span data-meta="model">Other</span></footer>'
        c_mismatch = cr.Check()
        cr.check_generation_meta(c_mismatch, mismatched, a)
        self.assertEqual(len(c_mismatch.failures), 2)


class UpgradeChecks(unittest.TestCase):
    @staticmethod
    def minimal_data(series_len=65):
        band = {"p10": 10.0, "p25": 12.0, "p50": 15.0, "p75": 18.0, "p90": 22.0, "current_percentile": 50.0}
        return {
            "asof": "2026-11-13",
            "gaps": [],
            "sources": {k: {} for k in ("price", "institutional", "foreign_holding",
                                         "margin", "revenue", "financials", "valuation")},
            "price": {
                "series": [{"close": 100.0} for _ in range(series_len)],
                "metrics": {
                    "close": 100.0, "ma5": 100.0, "ma10": 100.0, "ma20": 100.0,
                    "ma60": 98.0, "ma20_slope_5d": 1.0,
                    "ma60_slope_5d": 0.5 if series_len >= 65 else None,
                    "bias_ma20_pct": 0.0, "w20_high": 102.0, "w20_low": 98.0,
                    "squeeze": True, "alignment": "bullish", "vol_avg20_lots": 1000,
                    "spike_days": [], "dryup_days": [], "float_settling": {"signal": False},
                    "high60": 105.0, "low60": 95.0,
                },
            },
            "institutional": {"daily": [{} for _ in range(20)], "cost_zone": {"low": 98, "high": 102}},
            "foreign_holding": {"first": 10, "last": 11, "high": 12, "low": 9, "change_pp": 1},
            "margin": {"margin_last": 100, "short_last": 10, "short_margin_ratio_pct": 10, "short_margin_level": "medium"},
            "revenue": {"last12": [{} for _ in range(12)], "ytd_yoy_pct": 12.0},
            "financials": {
                "last4": ["2025Q4", "2026Q1", "2026Q2", "2026Q3"],
                "quarters": [{"eps": 2.0, "dsi_days": 50.0} for _ in range(4)],
                "ttm_eps": 8.0,
                "cash_conversion": {"ratio": 1.0},
                "core_baseline": {"applicable": True, "cy_eps": 7.5, "ntm_eps": 9.25},
            },
            "valuation": {"PER": band, "PBR": band},
            "peers": {"rows": [{} for _ in range(4)], "median": {"PER": 15.0}},
        }

    @staticmethod
    def minimal_html(dil_html='<div data-dilution="none">無未轉換 CB 或已公告現增。</div>',
                     cy="7.50", ntm="9.25"):
        secs = "\n".join([
            '<section id="dim1"></section>',
            '<section id="dim2"></section>',
            f'<section id="dim3">{dil_html}</section>',
            f'<section id="dim4"><span data-baseline="cy">{cy}</span><span data-baseline="ntm">{ntm}</span></section>',
            '<section id="dim5"></section>',
            ('<section id="dim6">'
             '<line data-line="entry" data-value="100"></line>'
             '<line data-line="t1" data-value="105"></line>'
             '<line data-line="t2" data-value="115"></line>'
             '<line data-line="sl" data-value="94"></line>'
             '</section>'),
        ])
        return (
            '<html><head><meta name="viewport" content="width=device-width">'
            '<style>body{overflow-x: clip}@media (prefers-color-scheme: dark){}</style></head>'
            '<body><button id="mode-toggle"></button>'
            '<span data-kpi="action">可分批布局</span><span data-kpi="close">100.0</span>'
            '<span data-kpi="rating">買進</span><span data-kpi="target">120.0</span>'
            '<span data-kpi="upside">+20.0%</span><span data-kpi="rr">2.50</span>'
            '<span data-kpi="asof">2026-11-13</span>'
            '<p>進場區</p><p>分析師判斷</p><p>2026-11-13</p>'
            '<div data-tip="100"></div>'
            f'{secs}'
            f'<footer>{cr.DISCLAIMER}</footer></body></html>'
        )

    def test_check_data_new_fields(self):
        d = self.minimal_data(65)
        c = cr.Check()
        cr.check_data(c, d)
        self.assertEqual(c.failures, [])

        d60 = self.minimal_data(60)
        c60 = cr.Check()
        cr.check_data(c60, d60)
        self.assertEqual(c60.failures, [])

        d["price"]["metrics"]["ma60_slope_5d"] = None
        d["price"]["metrics"]["ma20_slope_5d"] = None
        d["financials"].pop("core_baseline")
        c_bad = cr.Check()
        cr.check_data(c_bad, d)
        self.assertTrue(any("ma60_slope_5d" in f for f in c_bad.failures))
        self.assertTrue(any("ma20_slope_5d" in f for f in c_bad.failures))
        self.assertTrue(any("core_baseline" in f for f in c_bad.failures))

    def test_check_analysis_dilution_and_revenue_breaker(self):
        d, a, x = GenerationMeta.minimal_inputs()
        a.pop("dilution")
        a["thesis_breakers"] = [{"title": "tb1", "dataset": "Custom", "threshold": "weak"},
                                {"title": "tb2", "dataset": "TaiwanStockMonthRevenue", "threshold": "weak"}]
        c = cr.Check()
        cr.check_analysis(c, d, a, x)
        self.assertTrue(any("dilution" in f for f in c.failures))
        self.assertTrue(any("TaiwanStockMonthRevenue" in f for f in c.failures))

    def test_check_structure_dilution_and_baseline(self):
        d = self.minimal_data(65)
        x = {
            "close": 100.0, "rating_zh": "買進", "base": {"target": 120.0, "upside_pct": 20.0},
            "rr_pullback": 2.5, "action_zh": "可分批布局", "action_note": "進場區",
            "entry": 100.0, "t1": 105.0, "t2": 115.0, "hard_stop": 94.0,
        }
        a = {"valuation_method": "PER"}
        c_ok = cr.Check()
        cr.check_structure(c_ok, self.minimal_html(), d, x, a)
        self.assertEqual(c_ok.failures, [])

        c_pbr = cr.Check()
        cr.check_structure(c_pbr, self.minimal_html(cy="不適用", ntm="不適用"), d, x, {"valuation_method": "PBR"})
        self.assertEqual(c_pbr.failures, [])

        c_bad = cr.Check()
        cr.check_structure(c_bad, self.minimal_html(dil_html="", cy="8.00", ntm="9.00"), d, x, a)
        self.assertTrue(any("data-dilution" in f for f in c_bad.failures))
        self.assertTrue(any("data-baseline=cy" in f for f in c_bad.failures))
        self.assertTrue(any("data-baseline=ntm" in f for f in c_bad.failures))


if __name__ == "__main__":
    unittest.main()
