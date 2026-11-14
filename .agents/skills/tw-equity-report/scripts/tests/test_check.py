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
            "thesis_breakers": [{"title": "tb1"}, {"title": "tb2"}],
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


if __name__ == "__main__":
    unittest.main()
