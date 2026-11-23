"""Unit tests for exchange.py on trimmed exchange fixtures and scripted fetchers (no network)."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import Fetcher, NoDataError  # noqa: E402
from exchange import (fetch_day, fetch_valuation, num, parse_qfiis, parse_t86, parse_taiex,  # noqa: E402
                      parse_tpex_insti, parse_tpex_quotes, parse_twse_quotes, parse_valuation, resolve_asof)
from helpers import fixture, fx  # noqa: E402

FIXTURE_BY_SOURCE = {
    "twse_quotes": "twse_mi_index_20261120.json",
    "tpex_quotes": "tpex_quotes_20261120.json",
    "twse_t86": "twse_t86_20261120.json",
    "tpex_insti": "tpex_insti_20261119.json",
    "twse_qfiis": "twse_qfiis_20261120.json",
}
TWSE_PER_FIELDS = ["證券代號", "證券名稱", "收盤價", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"]
TPEX_PER_FIELDS = ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"]


def twse_per(date):
    return {"stat": "OK", "date": date, "fields": TWSE_PER_FIELDS,
            "data": [["1101", "台泥", "22.00", "4.55", 114, "-", "0.78", "115/3"]]}


def tpex_per(date):
    return {"stat": "ok", "date": date, "tables": [{
        "fields": TPEX_PER_FIELDS, "data": [["6488", "環球晶          ", "24.86", "7.70000000", 114, "1.74", "1.60", "115Q3"]]}]}


class FixtureFetcher:
    """Serves each source's fixture through the caller's own validator."""

    def __init__(self):
        self.calls = []

    def get(self, source, key, url, *, encoding, validate, **kw):
        self.calls.append((source, key, url))
        text = fixture(FIXTURE_BY_SOURCE[source], "utf-8")
        if not validate(text):
            raise NoDataError(source)
        return text


class AsofFetcher:
    """Answers TWSE quotes with "no data" for the unpublished dates and a bare OK otherwise."""

    def __init__(self, unpublished):
        self.unpublished = set(unpublished)
        self.calls = []

    def get(self, source, key, url, *, encoding, validate, **kw):
        self.calls.append((source, key))
        published = '{"stat": "OK", "tables": [{"title": "每日收盤行情", "data": [["2330"]]}]}'
        text = '{"stat": "很抱歉，沒有符合條件的資料!"}' if key in self.unpublished else published
        if not validate(text):
            raise NoDataError(key)
        return text


class Parsers(unittest.TestCase):
    def test_num_placeholders_and_numbers(self):
        self.assertEqual([num(s) for s in ("", "-", "--", "---", "N/A", " 1,234.5 ", "-48.50 ", 0.54, 114)],
                         [None, None, None, None, None, 1234.5, -48.5, 0.54, 114.0])

    def test_twse_quotes(self):
        q = parse_twse_quotes(fx("twse_mi_index_20261120.json"))
        self.assertEqual((q["00400A"]["close"], q["00400A"]["value"]), (9.80, 640498037))
        self.assertIsNone(q["00625K"]["close"])                                   # no trade: "--"

    def test_missing_quotes_table_raises(self):
        j = fx("twse_mi_index_20261120.json")
        j["tables"] = [t for t in j["tables"] if "每日收盤行情" not in (t.get("title") or "")]
        with self.assertRaises(ValueError) as cm:
            parse_twse_quotes(j)
        self.assertIn("每日收盤行情", str(cm.exception))

    def test_taiex(self):
        self.assertEqual(parse_taiex(fx("twse_mi_index_20261120.json")), 36033.29)

    def test_t86_foreign_includes_dealer_self(self):
        f = parse_t86(fx("twse_t86_20261120.json"))["3481"]
        self.assertEqual((f["foreign"], f["trust"], f["dealer"]), (46944616, -450532, 2854959))

    def test_t86_foreign_adds_foreign_dealer(self):    # every live row had 0 here, so set one
        j = fx("twse_t86_20261120.json")
        next(r for r in j["data"] if r[0] == "3481")[j["fields"].index("外資自營商買賣超股數")] = "1,000"
        self.assertEqual(parse_t86(j)["3481"]["foreign"], 46945616)

    def test_tpex_insti_foreign_is_cell_10_with_dealer(self):
        j = fx("tpex_insti_20261119.json")
        row = next(r for r in j["tables"][0]["data"] if r[0] == "00411A")
        row[7], row[10], row[23] = "500", "1,155,500", "5,459,039"
        self.assertEqual(parse_tpex_insti(j)["00411A"]["foreign"], 1155500)

    def test_tpex_managed_codes_parsed(self):           # the live table was empty on 2026-11-20
        j = fx("tpex_quotes_20261120.json")
        next(t for t in j["tables"] if t.get("title") == "管理股票")["data"].append(["9999", "測試"] + [""] * 17)
        self.assertEqual(parse_tpex_quotes(j)[1], {"9999"})

    def test_tpex_insti_positional(self):
        f = parse_tpex_insti(fx("tpex_insti_20261119.json"))["00411A"]
        self.assertEqual((f["foreign"], f["trust"], f["dealer"]), (1155000, 0, 4303539))

    def test_tpex_insti_layout_guard(self):
        j = fx("tpex_insti_20261119.json")
        next(r for r in j["tables"][0]["data"] if r[0] == "00411A")[23] = "1"
        with self.assertRaises(ValueError) as cm:
            parse_tpex_insti(j)
        self.assertIn("00411A", str(cm.exception))

    def test_tpex_quotes_shares_and_managed(self):
        q, managed = parse_tpex_quotes(fx("tpex_quotes_20261120.json"))
        self.assertEqual((q["00411A"]["close"], q["00411A"]["shares"], managed), (8.19, 481076000, set()))

    def test_qfiis(self):
        h = parse_qfiis(fx("twse_qfiis_20261120.json"))["00400A"]
        self.assertEqual((h["shares"], h["foreign_pct"]), (2458640000, 0.54))

    def test_valuation_both_boards(self):
        self.assertEqual(parse_valuation(twse_per("20261120"), tpex_per("20261120")),
                         {"1101": {"per": None, "pbr": 0.78, "yield": 4.55},
                          "6488": {"per": 24.86, "pbr": 1.60, "yield": 1.74}})


class FetchDay(unittest.TestCase):
    def test_fetch_day_merges_boards_and_flows(self):
        f = FixtureFetcher()
        day = fetch_day(f, "2026-11-20", with_flows=True)
        self.assertEqual((day["quotes"]["2330"]["market"], day["quotes"]["6488"]["market"]), ("twse", "tpex"))
        self.assertEqual((day["taiex"], day["managed"]), (36033.29, set()))
        self.assertEqual((day["flows"]["3481"]["trust"], day["flows"]["6488"]["dealer"]), (-450532, 129511))
        self.assertEqual(day["holdings"]["0050"]["foreign_pct"], 2.3)
        self.assertEqual(sorted(f.calls), [
            ("tpex_insti", "2026-11-20",
             "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=2026/11/20&response=json"),
            ("tpex_quotes", "2026-11-20",
             "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date=2026/11/20&id=&response=json"),
            ("twse_qfiis", "2026-11-20",
             "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20261120&selectType=ALLBUT0999&response=json"),
            ("twse_quotes", "2026-11-20",
             "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20261120&type=ALLBUT0999&response=json"),
            ("twse_t86", "2026-11-20",
             "https://www.twse.com.tw/rwd/zh/fund/T86?date=20261120&selectType=ALLBUT0999&response=json"),
        ])

    def test_twse_ok_without_rows_not_cached(self):  # Review Focus 2: MI_QFIIS answered this way on 2026-11-22
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        empty = {"stat": "OK", "date": "20261120", "title": "115年11月20日 外資及陸資投資持股統計",
                 "fields": ["證券代號", "發行股數", "全體外資及陸資持股比率"], "data": [], "total": 0}

        def opener(request, timeout):
            if "MI_QFIIS" in request.full_url:
                return io.BytesIO(json.dumps(empty).encode("utf-8"))
            source = next(s for s, marker in (("twse_quotes", "MI_INDEX"), ("tpex_quotes", "dailyQuotes"),
                                              ("twse_t86", "T86"), ("tpex_insti", "dailyTrade"))
                          if marker in request.full_url)
            return io.BytesIO(fixture(FIXTURE_BY_SOURCE[source], "utf-8").encode("utf-8"))

        f = Fetcher(root=tmp.name, pause_s=0, opener=opener, sleep=lambda s: None)
        with self.assertRaises(NoDataError):
            fetch_day(f, "2026-11-20", with_flows=True)
        self.assertFalse(f.has("twse_qfiis", "2026-11-20"))

    def test_fetch_day_without_flows_costs_two_requests(self):
        f = FixtureFetcher()
        day = fetch_day(f, "2026-11-20", with_flows=False)
        self.assertEqual((day["flows"], day["holdings"]), (None, None))
        self.assertEqual(sorted(source for source, _, _ in f.calls), ["tpex_quotes", "twse_quotes"])


class Valuation(unittest.TestCase):
    def fetcher(self, twse_date, tpex_date):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bodies = {"BWIBBU_d": twse_per(twse_date), "pera_result": tpex_per(tpex_date)}
        self.requested = []

        def opener(request, timeout):
            self.requested.append(request.full_url)
            body = next(b for marker, b in bodies.items() if marker in request.full_url)
            return io.BytesIO(json.dumps(body).encode("utf-8"))

        return Fetcher(root=tmp.name, pause_s=0, opener=opener, sleep=lambda s: None)

    def test_valuation_other_date_rejected(self):   # Review Focus 2
        f = self.fetcher("20261120", "20261119")
        with self.assertRaises(NoDataError):
            fetch_valuation(f, "2026-11-20")
        self.assertFalse(f.has("tpex_per", "2026-11-20"))
        self.assertEqual(self.requested, [
            "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date=20261120&selectType=ALL&response=json",
            "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json&d=115/11/20",
        ])

    def test_valuation_same_date_cached(self):
        f = self.fetcher("20261120", "20261120")
        self.assertEqual(fetch_valuation(f, "2026-11-20")["6488"]["per"], 24.86)
        self.assertTrue(f.has("twse_per", "2026-11-20") and f.has("tpex_per", "2026-11-20"))


class ResolveAsof(unittest.TestCase):
    DATES = ["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24"]

    def test_resolve_asof_steps_back_when_unpublished(self):   # Review Focus 2
        f = AsofFetcher({"2026-11-23"})
        self.assertEqual(resolve_asof(f, "2026-11-23", ["2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24"]),
                         "2026-11-20")
        self.assertEqual(f.calls, [("twse_quotes", "2026-11-23"), ("twse_quotes", "2026-11-20")])

    def test_resolve_asof_gives_up_after_three_steps(self):
        f = AsofFetcher(self.DATES)
        with self.assertRaises(NoDataError):
            resolve_asof(f, "2026-11-23", self.DATES)
        self.assertEqual([key for _, key in f.calls], ["2026-11-23", "2026-11-20", "2026-11-19", "2026-11-18"])


if __name__ == "__main__":
    unittest.main()
