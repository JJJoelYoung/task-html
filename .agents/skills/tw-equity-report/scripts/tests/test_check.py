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


if __name__ == "__main__":
    unittest.main()
