"""Unit tests for mops.py on trimmed MOPS fixtures and a scripted fetcher (no network)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import NoDataError  # noqa: E402
from mops import (deadline, due_seasons, fetch_income, fetch_revenue, has_code_header, parse_income,  # noqa: E402
                  parse_revenue, revenue_rows, standalone)
from helpers import fixture  # noqa: E402

HEADER_ONLY = "<table><tr><th>公司<br>代號</th><th>公司名稱</th></tr></table>"


def inc(revenue, op_income, eps):
    return {"revenue": revenue, "op_income": op_income, "pretax": None, "net_income": None, "net_parent": None,
            "eps": eps}


def revenue_html(code, name, note):
    cells = [code, name, "1,000", "900", "800", "11.11", "25.00", "9,000", "8,000", "12.50", note]
    return ("<table><tr><th>產業別：水泥工業</th><th>單位：千元</th></tr></table><table><tr align=right>"
            + "".join(f"<td>{c}</td>" for c in cells) + "</tr></table>")


class MopsFetcher:
    """Serves `pages[source]` (else a header-only page) through the caller's validator, recording each call."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, source, key, url, *, encoding, validate, form=None, refresh=False):
        self.calls.append({"source": source, "key": key, "url": url, "encoding": encoding, "form": form,
                           "refresh": refresh})
        text = self.pages.get(source, HEADER_ONLY)
        if not validate(text):
            raise NoDataError(source)
        return text


class Revenue(unittest.TestCase):
    def test_parse_revenue(self):
        rows = {r["code"]: r for r in parse_revenue(fixture("mops_sii_115_10_0.html", "cp950"))}
        r = rows["1101"]
        self.assertEqual((r["revenue"], r["revenue_last_year"], r["yoy_pct"], r["industry"], r["note"]),
                         (16357176, 13882248, 17.82, "水泥工業", None))
        self.assertIsNotNone(rows["1303"]["note"])
        self.assertNotIn("合計", rows)

    def test_parse_revenue_industry_per_block(self):
        rows = {r["code"]: r for r in parse_revenue(fixture("mops_sii_115_10_0.html", "cp950"))}
        self.assertEqual((len(rows), rows["1303"]["industry"], rows["1102"]["industry"]), (25, "塑膠工業", "水泥工業"))

    def test_name_star_stripped_and_blank_note_none(self):
        (r,) = parse_revenue(revenue_html("2330", "台積電*", "&nbsp;"))
        self.assertEqual((r["name"], r["note"], r["revenue"]), ("台積電", None, 1000))

    def test_revenue_rows_oldest_first(self):
        oct_, sep = parse_revenue(revenue_html("2330", "a", "-")), parse_revenue(revenue_html("2330", "a", "-"))
        sep[0]["revenue"] = 950.0
        self.assertEqual(revenue_rows({(2026, 10): oct_, (2026, 9): sep})["2330"],
                         [{"revenue_year": 2026, "revenue_month": 9, "revenue": 950.0},
                          {"revenue_year": 2026, "revenue_month": 10, "revenue": 1000.0}])

    def test_code_header_matches_across_br(self):    # both MOPS pages print the header as 公司<br>代號
        self.assertEqual((has_code_header("<th>公司<br>代號</th>"), has_code_header("<p>查詢無資料</p>")),
                         (True, False))

    def test_fetch_revenue_files_and_refresh(self):
        f = MopsFetcher({"rev_sii_0": fixture("mops_sii_115_10_0.html", "cp950")})
        rows = fetch_revenue(f, 2026, 10, "2026-11-23")
        self.assertEqual(len(rows), 25)
        self.assertEqual([(c["source"], c["key"], c["encoding"], c["refresh"]) for c in f.calls],
                         [(s, "2026-10", "cp950", True) for s in
                          ("rev_sii_0", "rev_sii_1", "rev_otc_0", "rev_otc_1", "rev_rotc_0")])
        self.assertEqual(f.calls[4]["url"], "https://mopsov.twse.com.tw/nas/t21/rotc/t21sc03_115_10_0.html")
        fetch_revenue(f, 2026, 9, "2026-11-23")             # refreshed only until the 25th of the next month
        self.assertEqual((f.calls[5]["url"], f.calls[5]["refresh"]),
                         ("https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_115_9_0.html", False))


class Income(unittest.TestCase):
    def test_parse_income_templates(self):
        gen, other = parse_income(fixture("mops_t163sb04_sii_115_03.html", "utf-8"))
        self.assertEqual((gen["1101"]["revenue"], gen["1101"]["op_income"], gen["1101"]["eps"]),
                         (112522875, 9571599, 0.63))
        self.assertTrue({"2801", "1409"} <= other)
        self.assertNotIn("1409", gen)

    def test_parse_income_all_fields(self):
        gen, _ = parse_income(fixture("mops_t163sb04_sii_115_03.html", "utf-8"))
        self.assertEqual(gen["1101"], {"revenue": 112522875, "op_income": 9571599, "pretax": 11467348,
                                       "net_income": 7921300, "net_parent": 5089876, "eps": 0.63})

    def test_standalone_differencing(self):
        ytd = {(2026, 1): {"X": inc(100, 10, 1.0)}, (2026, 2): {"X": inc(250, 30, 2.5)},
               (2026, 3): {"X": inc(400, 45, 4.0)}}
        out = standalone(ytd)["X"]
        self.assertEqual([q["revenue"] for q in out], [100, 150, 150])
        self.assertEqual([q["op_income"] for q in out], [10, 20, 15])

    def test_standalone_skips_undifferenceable(self):
        ytd = {(2026, 1): {"X": inc(100, 10, 1.0)}, (2026, 3): {"X": inc(400, 45, 4.0)}}
        self.assertEqual([(q["year"], q["season"]) for q in standalone(ytd)["X"]], [(2026, 1)])

    def test_standalone_none_field_stays_none(self):
        ytd = {(2025, 4): {"X": inc(900, 90, 9.0)}, (2025, 3): {"X": inc(600, None, 6.0)}}
        q4 = standalone(ytd)["X"][-1]
        self.assertEqual((q4["season"], q4["revenue"], q4["op_income"], q4["pretax"]), (4, 300, None, None))

    def test_deadlines(self):
        self.assertEqual([deadline(2026, s) for s in (1, 2, 3, 4)],
                         ["2026-05-15", "2026-08-14", "2026-11-14", "2027-03-31"])

    def test_due_seasons(self):
        s = due_seasons("2026-11-23")
        self.assertEqual((s[0], s[-1], len(s)), ((2024, 3), (2026, 3), 9))
        self.assertEqual(due_seasons("2026-11-13")[-1], (2026, 2))

    def test_fetch_income_form_and_refresh(self):
        f = MopsFetcher({"inc_sii": fixture("mops_t163sb04_sii_115_03.html", "utf-8")})
        gen, other = fetch_income(f, 2026, 3, "2026-11-23")
        self.assertEqual((gen["1101"]["eps"], {"2801", "1409"} <= other), (0.63, True))
        self.assertEqual(f.calls[0], {
            "source": "inc_sii", "key": "2026-Q3", "url": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",
            "encoding": "utf-8", "refresh": True,
            "form": {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y",
                     "TYPEK": "sii", "year": "115", "season": "03"}})
        self.assertEqual([c["source"] for c in f.calls], ["inc_sii", "inc_otc"])
        fetch_income(f, 2026, 2, "2026-11-23")              # refreshed only until 30 days after its deadline
        self.assertEqual((f.calls[2]["key"], f.calls[2]["refresh"]), ("2026-Q2", False))


if __name__ == "__main__":
    unittest.main()
