"""Unit tests for universe.py on trimmed ISIN fixtures (no network)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from universe import events, load_master, parse_isin, reconcile  # noqa: E402
from helpers import fixture, sec  # noqa: E402


def isin_html(market):
    return ("<table><tr><td>2330　台積電</td><td>TW0002330008</td><td>1994/09/05</td>"
            f"<td>{market}</td><td>半導體業</td><td>ESVUFR</td><td></td></tr></table>")


class ParseIsin(unittest.TestCase):
    def test_parse_isin_equities_and_traps(self):
        s = {x.code: x for x in parse_isin(fixture("isin_2.html", "cp950"))}
        self.assertEqual((s["2330"].key, s["2330"].industry), ("2330@1994-09-05", "半導體業"))
        self.assertNotIn("0050", s)                                                    # ETF: CFI not ES*
        self.assertTrue(s["3673"].cfi.startswith("ES") and not s["3673"].isin.startswith("TW"))  # KY issuer
        self.assertTrue(any(x.board == "tib" for x in s.values()))                     # 創新板 section kept

    def test_unknown_market_raises(self):
        with self.assertRaises(ValueError) as cm:
            parse_isin(isin_html("上市X"))
        self.assertIn("上市X", str(cm.exception))

    def test_load_master_reads_three_boards(self):
        calls = []

        class FakeFetcher:
            def get(self, source, key, url, *, encoding, validate, **kw):
                calls.append((source, key, encoding))
                text = fixture(f"isin_{source[-1]}.html", "cp950")
                assert validate(text)
                return text

        master = load_master(FakeFetcher(), "2026-11-23")
        self.assertEqual(calls, [("isin2", "2026-11-23", "cp950"), ("isin4", "2026-11-23", "cp950"),
                                 ("isin5", "2026-11-23", "cp950")])
        self.assertEqual({(x.code, x.market, x.board) for x in master if x.code in ("2237", "6488", "1260")},
                         {("2237", "twse", "tib"), ("6488", "tpex", "main"), ("1260", "emerging", "main")})


class Events(unittest.TestCase):
    def test_transfer_is_one_event(self):           # Review Focus 1
        ev = events([sec("8908", "1997-03-01", "tpex")], [sec("8908", "2026-10-16", "twse")])
        self.assertEqual(ev["transfers"], [{"code": "8908", "from": "tpex", "to": "twse"}])
        self.assertEqual((ev["new"], ev["exits"]), ([], []))

    def test_rename_and_code_reuse(self):
        prev = [sec("1101", "1962-02-09", "twse", name="台泥")]
        cur = [sec("1101", "1962-02-09", "twse", name="台泥新"), sec("2432", "2026-11-02", "tpex"),
               sec("6666", "2026-11-02", "tpex")]
        ev = events(prev, cur, delisted={"2432": "2010-05-01", "6666": "2026-12-01"})
        self.assertEqual(ev["renames"], [{"key": "1101@1962-02-09", "from": "台泥", "to": "台泥新"}])
        self.assertEqual(ev["code_reuse"], ["2432@2026-11-02"])
        self.assertEqual(ev["new"], ["2432@2026-11-02", "6666@2026-11-02"])

    def test_first_week_has_no_events(self):
        ev = events(None, [sec("1101", "1962-02-09", "twse")])
        self.assertEqual(ev, {"new": [], "exits": [], "transfers": [], "renames": [], "code_reuse": []})


class Reconcile(unittest.TestCase):
    def test_reconcile_lists(self):
        master = [sec("1101", "1962-02-09", "twse"), sec("2330", "1994-09-05", "twse"),
                  sec("6488", "2015-09-25", "tpex"), sec("1260", "2012-11-26", "emerging")]
        info = [
            {"industry_category": "水泥工業", "stock_id": "1101", "stock_name": "台泥", "type": "twse", "date": "2026-11-19"},
            {"industry_category": "水泥工業", "stock_id": "1101", "stock_name": "台泥", "type": "twse", "date": "2026-11-20"},
            {"industry_category": "半導體業", "stock_id": "6488", "stock_name": "環球晶", "type": "tpex", "date": "2026-11-20"},
            {"industry_category": "食品工業", "stock_id": "1260", "stock_name": "富味鄉", "type": "emerging", "date": "2026-10-01"},
        ]
        self.assertEqual(reconcile(master, {"1101", "2330"}, info),
                         {"not_in_finmind": ["2330"], "not_quoted": ["6488"], "finmind_stale": ["1260"]})


if __name__ == "__main__":
    unittest.main()
