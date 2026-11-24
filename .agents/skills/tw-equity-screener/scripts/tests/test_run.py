"""End-to-end tests for run.py on a synthetic market served by in-memory fakes (no network)."""

import io
import json
import math
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run  # noqa: E402
import shared  # noqa: E402
from cache import NoDataError  # noqa: E402
from check_screen import main as check_screen  # noqa: E402
from exchange import T86_FIELDS  # noqa: E402
from history import read_csv, screens_dir, write_week  # noqa: E402
from render import render  # noqa: E402
from run import latest_month, main  # noqa: E402
from snapshots import OPENAPI  # noqa: E402
from test_exchange import TPEX_PER_FIELDS, TWSE_PER_FIELDS  # noqa: E402
from test_render import INDEX, README  # noqa: E402

ORIGIN = date(2025, 1, 1)
LAST_DATE = "2026-12-31"            # TaiwanStockTradingDate also lists future dates
FIELDS = ("code", "name", "market", "industry", "close", "drift", "volume", "growth", "margin")
# close at ORIGIN, daily drift, shares traded a day, monthly revenue growth, operating margin
STOCKS = [
    ("2330", "甲電", "上市", "半導體業", 100.0, 0.0012, 4e6, 0.030, 0.30),
    ("2303", "乙電", "上市", "半導體業", 50.0, 0.0010, 6e6, 0.020, 0.20),       # on the attention list
    ("2454", "丙電", "上市", "半導體業", 200.0, 0.0008, 2e6, 0.025, 0.25),
    ("3711", "丁電", "上市", "半導體業", 80.0, 0.0007, 4e6, 0.010, 0.15),
    ("2408", "戊電", "上市", "半導體業", 60.0, -0.0010, 6e6, -0.010, 0.05),     # falling
    ("2344", "巳電", "上市", "半導體業", 30.0, 0.0002, 9e6, 0.000, -0.05),      # operating loss
    ("6488", "己電", "上櫃", "半導體業", 150.0, 0.0009, 2e6, 0.015, 0.20),
    ("1301", "庚塑", "上市", "塑膠工業", 70.0, 0.0004, 4e6, 0.005, 0.10),
    ("2881", "辛金", "上市", "金融保險業", 60.0, 0.0005, 8e6, 0.010, 0.30),
    ("1409", "壬纖", "上市", "紡織纖維", 30.0, 0.0003, 9e6, 0.010, 0.10),       # other income template
    ("1312", "癸塑", "上市", "塑膠工業", 8.0, 0.0002, 9e6, 0.010, 0.10),        # close below 10
    ("1316", "子塑", "上市", "塑膠工業", 40.0, 0.0002, 1e4, 0.010, 0.10),       # thin trading
    ("8044", "丑網", "上櫃", "電子商務業", 40.0, 0.0002, 2e6, 0.010, 0.10),     # managed (TPEx 管理股票)
    ("6901", "寅新", "上市臺灣創新板", "生技醫療業", 90.0, 0.0010, 1e6, 0.020, 0.20),
    ("6999", "卯新", "上市", "電子零組件業", 50.0, 0.0010, 2e6, 0.020, 0.20),   # listed 2026-09-01
    ("6998", "未新", "上市", "電子零組件業", 60.0, 0.0010, 2e6, 0.020, 0.20),   # listed between the weeks
    ("3008", "午光", "上市", "半導體業", 300.0, 0.0012, 2e6, 0.030, 0.30),     # strong, then falling
    ("7777", "辰興", "興櫃", "生技醫療業", 30.0, 0.0, 0.0, 0.030, 0.20),
]
LISTED = {"6999": "2026/09/01", "6998": "2026/11/17"}
BREAK = {"3008": "2026-10-21"}            # falls 1% a day after this date
LATE = {("3711", 2026, 10)}               # this month's revenue is not filed yet
ONE_OFF = {("1312", 2026, 10)}            # this month's revenue is tripled by a one-off, with a note
NOTES = {("2330", 2026, 10): "新廠量產"}    # a note on an ordinary month (YoY 42.6%), so not a one-off
LATE_INCOME = {("1409", 2026, 3)}         # this season's income is not filed yet
OTHER_UNTIL = {"1301": 2024}              # files on the other income template up to this year
GAPS = {("1312", "2026-11-06")}          # no trade that day
NON_GENERAL = {"2881", "1409"}
MANAGED = {"8044"}
BOARD = {"上市": "sii", "上市臺灣創新板": "sii", "上櫃": "otc", "興櫃": "rotc"}
ISIN_MODE = {"上市": 2, "上市臺灣創新板": 2, "上櫃": 4, "興櫃": 5}
SNAPSHOTS = {"notice": [{"Code": "2303", "Name": "乙電"}, {"Code": "030001", "Name": "權證"}],   # a warrant too
             "esb_quotes": [{"SecuritiesCompanyCode": "7777", "CompanyName": "辰興", "Average": "30.5",
                             "LatestPrice": "31.00", "TransactionVolume": "5,000", "ApplyingStatus": ""}]}
TPEX_FIELDS = ["代號", "名稱", "收盤", "開盤", "最高", "最低", "成交股數", "成交金額(元)", "發行股數"]
GENERAL_HEAD = ["公司代號", "公司名稱", "營業收入", "營業利益（損失）", "稅前淨利（淨損）", "本期淨利（淨損）",
                "淨利（淨損）歸屬於母公司業主", "基本每股盈餘（元）"]
OTHER_HEAD = ["公司代號", "公司名稱", "收益", "營業利益", "本期淨利（淨損）", "基本每股盈餘（元）"]


def weekdays(start, end):
    d, out = date.fromisoformat(start), []
    while d.isoformat() <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def html_table(head, rows):
    return ("<table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>")


class World:
    """Every source a run reads, generated from STOCKS. The switches break one source each."""

    def __init__(self, duplicate_isin=False, tpex_per_lag=False, closed=(), twse_missing=()):
        self.duplicate_isin, self.tpex_per_lag = duplicate_isin, tpex_per_lag
        self.closed, self.twse_missing = set(closed), set(twse_missing)     # no quotes on both boards / on TWSE
        self.stocks = [dict(zip(FIELDS, s)) for s in STOCKS]

    def respond(self, source, key):
        if source.startswith("isin"):
            return self.isin(int(source[4:]), key)
        if source.startswith("rev_"):
            _, board, kind = source.split("_")
            return self.revenue(board, int(kind), *(int(x) for x in key.split("-")))
        if source.startswith("inc_"):
            year, season = key.split("-Q")
            return self.income(source[4:], int(year), int(season))
        if source in OPENAPI:
            return json.dumps(SNAPSHOTS.get(source, []), ensure_ascii=False)
        return json.dumps(getattr(self, source)(key), ensure_ascii=False)

    @staticmethod
    def listed(s):
        return LISTED.get(s["code"], "2000/01/03").replace("/", "-")

    def close(self, s, d):
        t = (date.fromisoformat(d) - ORIGIN).days
        c = s["close"] * math.exp(s["drift"] * t) * (1 + 0.004 * math.sin(t / 9 + int(s["code"]) % 7))
        if s["code"] in BREAK and d > BREAK[s["code"]]:
            c *= math.exp(-0.01 * (date.fromisoformat(d) - date.fromisoformat(BREAK[s["code"]])).days)
        return round(c, 2)

    def taiex(self, d):
        return round(20000 * math.exp(0.0005 * (date.fromisoformat(d) - ORIGIN).days), 2)

    def on(self, d, board):
        return [s for s in self.stocks if BOARD[s["market"]] == board and self.listed(s) <= d
                and (s["code"], d) not in GAPS]

    def twse_quotes(self, d):
        if d in self.closed | self.twse_missing:
            return {"stat": "很抱歉，沒有符合條件的資料!"}
        rows = [[s["code"], s["name"], f"{s['volume']:,.0f}", "1", f"{self.close(s, d) * s['volume']:,.0f}",
                 *[f"{self.close(s, d):.2f}"] * 4] for s in self.on(d, "sii")]
        return {"stat": "OK", "date": d.replace("-", ""), "tables": [
            {"title": "價格指數(臺灣證券交易所)", "fields": ["指數", "收盤指數"],
             "data": [["發行量加權股價指數", f"{self.taiex(d):,.2f}"]]},
            {"title": "每日收盤行情(全部)", "fields": ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額",
                                                 "開盤價", "最高價", "最低價", "收盤價"], "data": rows}]}

    def tpex_quotes(self, d):
        def row(s):
            c = f"{self.close(s, d):.2f}"
            return [s["code"], s["name"], c, c, c, c, f"{s['volume']:,.0f}", f"{self.close(s, d) * s['volume']:,.0f}",
                    "1,000,000,000"]
        otc = [] if d in self.closed else self.on(d, "otc")
        return {"stat": "ok", "date": d.replace("-", ""), "tables": [
            {"title": "上櫃股票行情", "fields": TPEX_FIELDS, "data": [row(s) for s in otc if s["code"] not in MANAGED]},
            {"title": "管理股票", "fields": TPEX_FIELDS, "data": [row(s) for s in otc if s["code"] in MANAGED]}]}

    @staticmethod
    def flows(s):
        return 1000 * (1 + int(s["code"]) % 5), 500 if s["drift"] > 0 else -500, 100

    def twse_t86(self, d):
        rows = [[s["code"], s["name"], f"{f:,}", "0", f"{t:,}", f"{dl:,}"]
                for s in self.on(d, "sii") for f, t, dl in [self.flows(s)]]
        return {"stat": "OK", "date": d.replace("-", ""), "fields": ["證券代號", "證券名稱", *T86_FIELDS], "data": rows}

    def tpex_insti(self, d):
        rows = []
        for s in self.on(d, "otc"):
            cells = [s["code"], s["name"]] + ["0"] * 22
            f, t, dl = self.flows(s)
            cells[10], cells[13], cells[22], cells[23] = (f"{v:,}" for v in (f, t, dl, f + t + dl))
            rows.append(cells)
        return {"stat": "ok", "date": d.replace("-", ""), "tables": [{"title": "三大法人買賣明細資訊", "data": rows}]}

    def twse_qfiis(self, d):
        rows = [[s["code"], s["name"], "TW0", "1,000,000,000", "30.00"] for s in self.on(d, "sii")]
        return {"stat": "OK", "date": d.replace("-", ""),
                "fields": ["證券代號", "證券名稱", "國際證券編碼", "發行股數", "全體外資及陸資持股比率"], "data": rows}

    @staticmethod
    def valuation(s):
        return f"{10 + int(s['code']) % 20:.2f}", f"{1 + int(s['code']) % 5 / 2:.2f}"

    def twse_per(self, d):
        rows = [[s["code"], s["name"], "0", "3.00", 114, per, pbr, "115/3"]
                for s in self.on(d, "sii") for per, pbr in [self.valuation(s)]]
        return {"stat": "OK", "date": d.replace("-", ""), "fields": TWSE_PER_FIELDS, "data": rows}

    def tpex_per(self, d):
        rows = [[s["code"], s["name"], per, "1.0", 114, "3.00", pbr, "115Q3"]
                for s in self.on(d, "otc") for per, pbr in [self.valuation(s)]]
        return {"stat": "ok", "date": "19000101" if self.tpex_per_lag else d.replace("-", ""),
                "tables": [{"fields": TPEX_PER_FIELDS, "data": rows}]}

    def isin(self, mode, asof):
        rows = [s for s in self.stocks if ISIN_MODE[s["market"]] == mode and self.listed(s) <= asof]
        if self.duplicate_isin and mode == 2:
            rows.append(rows[0])
        cells = "".join(f"<tr><td>{s['code']}　{s['name']}</td><td>TW{s['code']:0>9}0</td>"
                        f"<td>{LISTED.get(s['code'], '2000/01/03')}</td><td>{s['market']}</td><td>{s['industry']}</td>"
                        f"<td>ESVUFR</td><td></td></tr>" for s in rows)
        return f"<table><tr><td>有價證券代號及名稱</td></tr>{cells}</table>"

    @staticmethod
    def monthly(s, y, m):
        return 1e6 * (1 + s["growth"]) ** ((y - 2023) * 12 + m - 1)        # thousand NT$

    def revenue(self, board, kind, y, m):
        rows = []
        for s in self.stocks if kind == 0 else []:
            if BOARD[s["market"]] != board or (s["code"], y, m) in LATE:
                continue
            one_off = (s["code"], y, m) in ONE_OFF
            r, ly = self.monthly(s, y, m) * (3 if one_off else 1), self.monthly(s, y - 1, m)
            rows.append([s["code"], s["name"], f"{r:,.0f}", "0", f"{ly:,.0f}", "0", f"{(r / ly - 1) * 100:.2f}", "0",
                         "0", "0", "處分利益" if one_off else NOTES.get((s["code"], y, m), "-")])
        return ("<table><tr><th>公司<br>代號</th><th>公司名稱</th></tr><tr><th>產業別：其他</th></tr>"
                + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>")

    def income(self, board, y, season):
        general, other = [], []
        for s in self.stocks:
            if BOARD[s["market"]] != board or (s["code"], y, season) in LATE_INCOME:
                continue
            revenue = sum(self.monthly(s, y, m) for m in range(1, 3 * season + 1))
            op = revenue * s["margin"]
            net, eps = op * 0.8, op * 0.8 * 1000 / 1e9
            if s["code"] in NON_GENERAL or y <= OTHER_UNTIL.get(s["code"], 0):
                other.append([s["code"], s["name"], f"{revenue:,.0f}", f"{op:,.0f}", f"{net:,.0f}", f"{eps:.2f}"])
            else:
                general.append([s["code"], s["name"], f"{revenue:,.0f}", f"{op:,.0f}", f"{op:,.0f}", f"{net:,.0f}",
                                f"{net:,.0f}", f"{eps:.2f}"])
        return html_table(GENERAL_HEAD, general) + html_table(OTHER_HEAD, other)


class MemoryFetcher:
    """cache.Fetcher's interface over an in-memory cache; a miss asks the World and validates like the real one."""

    def __init__(self, world, root):
        self.world, self.root, self.cache, self.network_calls = world, Path(root), {}, 0

    def has(self, source, key):
        return (source, key) in self.cache

    def get(self, source, key, url, *, encoding, validate, form=None, refresh=False):
        if not refresh and (source, key) in self.cache:
            return self.cache[(source, key)]
        self.network_calls += 1
        text = self.world.respond(source, key)
        if not validate(text):
            raise NoDataError(f"{source}/{key}")
        self.cache[(source, key)] = text
        return text


def finmind(dataset, data_id, start, end=None):
    if dataset == "TaiwanStockTradingDate":
        return [{"date": d} for d in weekdays(start, LAST_DATE)]
    if dataset == "TaiwanStockInfo":
        return [{"stock_id": s[0], "stock_name": s[1], "date": "2026-11-20"} for s in STOCKS]
    raise AssertionError(dataset)


def deep(code, peers, asof):
    """A fetch.build result that gives every name a BUY proxy of +25%."""
    return {"price": {"metrics": {"close": 100.0}},
            "valuation": {"PER": {"p50": 25.0, "current_percentile": 40.0}, "PBR": {"current_percentile": 55.0}},
            "financials": {"core_baseline": {"ntm_eps": 5.0, "applicable": True, "high_volatility": False},
                           "cash_conversion": 1.1},
            "institutional": {"cost_zone": None}, "gaps": []}


def run_main(args, fetcher, today, build=deep):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(args, fetcher=fetcher, finmind=finmind, build=build, today=today)
    return code, out.getvalue()


def make_portal(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "reports" / "equity").mkdir(parents=True, exist_ok=True)
    for code in ("2330", "2308"):
        (root / "reports" / "equity" / f"{code}.html").write_text("x", encoding="utf-8")


def snapshot_files(root, week):
    folder = screens_dir(root) / week
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.iterdir())}
    texts["forward.csv"] = (screens_dir(root) / "forward.csv").read_text(encoding="utf-8")
    return texts


class LatestMonth(unittest.TestCase):
    def test_latest_month(self):
        self.assertEqual([latest_month(d) for d in ("2026-11-11", "2026-11-10", "2026-01-05")],
                         [(2026, 10), (2026, 9), (2025, 11)])


class Guards(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.cache = Path(tmp.name) / "cache"

    def test_backfill_guard_exits_5_with_estimate(self):
        f = MemoryFetcher(World(), self.cache)
        code, out = run_main(["--root", str(self.root)], f, "2026-11-21")
        self.assertEqual(code, 5, out)
        # 269 TWSE and 270 TPEx quote tables, 30 × 3 flow tables, 25 × 5 revenue files, 9 × 2 income pages
        self.assertIn("270 of 270 trading dates are not cached; about 772 requests, 39 minutes at 3 s each", out)
        self.assertEqual(f.network_calls, 1)                # only the asof probe ran
        self.assertFalse(screens_dir(self.root).exists())

    def test_past_asof_anchors_the_calendar(self):  # 450 days before asof, not before today
        code, out = run_main(["--asof", "2025-12-31", "--root", str(self.root)], MemoryFetcher(World(), self.cache),
                             "2026-11-21")
        self.assertEqual(code, 5, out)
        self.assertIn("asof 2025-12-31, week 2026-w01, archived snapshots", out)
        self.assertIn("270 of 270 trading dates", out)

    def test_past_asof_without_archived_lists_exits_4(self):
        f = MemoryFetcher(World(), self.cache)
        code, out = run_main(["--asof", "2026-11-13", "--backfill", "--root", str(self.root)], f, "2026-11-21")
        self.assertEqual(code, 4, out)
        self.assertIn("no ISIN lists cached for 2026-11-13", out)
        self.assertFalse(any(source.startswith("isin") for source, _ in f.cache))   # today's lists never land there

    def test_unpublished_valuation_exits_3(self):    # Review Focus 2
        code, out = run_main(["--backfill", "--root", str(self.root)],
                             MemoryFetcher(World(tpex_per_lag=True), self.cache), "2026-11-21")
        self.assertEqual(code, 3, out)
        self.assertIn("tpex_per/2026-11-20", out)

    def test_calendar_closure_is_skipped(self):      # final review I1: a typhoon day the calendar still lists
        f = MemoryFetcher(World(closed={"2026-11-10"}), self.cache)
        code, out = run_main(["--backfill", "--root", str(self.root)], f, "2026-11-21")
        self.assertEqual(code, 0, out)
        self.assertIn("skipped 1 calendar date that neither board traded: 2026-11-10", out)
        funnel = json.loads((screens_dir(self.root) / "2026-w47" / "funnel.json").read_text(encoding="utf-8"))
        self.assertEqual(funnel["closed_dates"], ["2026-11-10"])
        self.assertEqual((funnel["regime"]["transition"], funnel["regime"]["reasons"]), (False, []))   # 270 closes
        self.assertFalse([key for key in f.cache if key[1] == "2026-11-10"])                         # never cached
        self.assertEqual(len([key for key in f.cache if key[0] == "twse_t86"]), 30)                  # 30 traded dates
        self.assertEqual(len({key[1] for key in f.cache if key[0] == "twse_quotes"}), 270)

    def test_past_date_missing_on_twse_only_exits_3(self):     # the other board traded, so it is not a closure
        code, out = run_main(["--backfill", "--root", str(self.root)],
                             MemoryFetcher(World(twse_missing={"2026-11-10"}), self.cache), "2026-11-21")
        self.assertEqual(code, 3, out)
        self.assertIn("twse_quotes/2026-11-10", out)
        self.assertFalse(screens_dir(self.root).exists())


class Pipeline(unittest.TestCase):
    """Week 46 with a backfill, then week 47 from the cache; one shared repo and cache."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "repo"
        make_portal(cls.root)
        cls.fetcher = MemoryFetcher(World(), Path(cls.tmp.name) / "cache")
        cls.w46 = run_main(["--backfill", "--root", str(cls.root)], cls.fetcher, "2026-11-14")
        cls.w47 = run_main(["--root", str(cls.root)], cls.fetcher, "2026-11-21")
        cls.folder = screens_dir(cls.root) / "2026-w47"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def week(self, name):
        return json.loads((self.folder / name).read_text(encoding="utf-8"))

    def statuses(self):
        return {r["code"]: (r["status"], r["reason"], r["flags"]) for r in read_csv(self.folder / "universe.csv")}

    def copy_fetcher(self, world, keep=lambda key: True):
        f = MemoryFetcher(world, Path(tempfile.mkdtemp(dir=self.tmp.name)))
        f.cache = {k: v for k, v in self.fetcher.cache.items() if keep(k)}
        return f

    def test_both_weeks_written(self):
        for code, out in (self.w46, self.w47):
            self.assertEqual(code, 0, out)
        self.assertIn("funnel: L0 17, L0_full 15, L0_watch 2, L1 12, L2 9, L3 9, L4 5, L5 5, L6 3", self.w46[1])
        self.assertIn("week folder: ", self.w47[1])
        self.assertIn("funnel: L0 18, L0_full 15, L0_watch 3, L1 12, L2 9, L3 9, L4 5, L5 5, L6 3", self.w47[1])
        funnel, regime = self.week("funnel.json"), self.week("funnel.json")["regime"]
        self.assertEqual((funnel["asof"], regime["close"]), ("2026-11-20", World().taiex("2026-11-20")))
        self.assertEqual((regime["above_ma60"], regime["transition"], regime["reasons"]), (True, False, []))
        # 250 trading dates back; every weekday trades in this market
        self.assertAlmostEqual(regime["ret12m"], (World().taiex("2026-11-20") / World().taiex("2025-12-05") - 1) * 100)
        self.assertEqual(funnel["params"]["shortlist"],
                         {"enter": 20, "stay": 40, "cap": 30, "left_n": 10, "tier_a_proxy": 15.0})

    def test_gate_statuses(self):
        s = self.statuses()
        self.assertEqual({c: s[c][:2] for c in ("2881", "1409", "1312", "1316", "8044", "2344", "6999", "6998",
                                                "7777", "3008")},
                         {"2881": ("excluded_financial", None), "1409": ("insufficient_data", "non_general_template"),
                          "1312": ("excluded_price", None), "1316": ("excluded_liquidity", None),
                          "8044": ("excluded_status", "managed"), "2344": ("excluded_loss", None),
                          "6999": ("watch_track", None), "6998": ("watch_track", None),
                          "7777": ("watch_track", None), "3008": ("shortlist_left_watch", None)})
        self.assertEqual((s["6901"][2], s["2303"][2], s["1312"][2]), (["tib"], ["attention"], ["one_off_revenue"]))

    def test_scores_rows(self):
        rows = {r["code"]: r for r in read_csv(self.folder / "scores.csv")}
        scored = {c for c, (status, _, _) in self.statuses().items()
                  if status in ("ranked", "excluded_floor", "shortlist_actionable", "shortlist_left_watch")}
        self.assertEqual(set(rows), scored)
        self.assertIsNone(rows["3711"]["z_rev_yoy_med6"])        # a late filer keeps its row, without revenue inputs
        self.assertIsNotNone(rows["2330"]["z_rev_yoy_med6"])
        self.assertEqual({c: r["trend_ok"] for c, r in rows.items() if not r["trend_ok"]}, {"2408": False, "3008": False})
        self.assertEqual((rows["3008"]["list"], rows["2330"]["list"], rows["2454"]["list"]),
                         ("left_watch", "actionable", None))

    def test_shortlist_ties_out(self):
        sl, counts = self.week("shortlist.json"), self.week("funnel.json")["counts"]
        listed = sl["actionable"] + sl["left_watch"]
        self.assertEqual(([r["code"] for r in sl["actionable"]], [r["code"] for r in sl["left_watch"]], sl["tier_a"]),
                         (["2303", "2330", "6901", "6488"], ["3008"], ["2330", "6901", "6488"]))
        self.assertEqual(counts["L5"], len(listed))
        self.assertEqual(counts["L6"], len(sl["tier_a"]))
        self.assertLessEqual(set(sl["tier_a"]), {r["code"] for r in sl["actionable"]})
        self.assertNotIn("2303", sl["tier_a"])                  # attention is a red flag
        self.assertTrue(all(r["command"] == f"/tw-equity-report {r['code']}" and r["buy_proxy"] == 25.0
                            for r in listed))
        notes = {r["code"]: r["revenue_note"] for r in listed}      # read by the Step 2 review
        self.assertEqual(notes["2330"], {"month": "2026-10", "note": "新廠量產"})
        self.assertEqual({c for c, n in notes.items() if n}, {"2330"})
        marked = [c for c, (status, _, _) in self.statuses().items() if status.startswith("shortlist_")]
        self.assertEqual(sorted(marked), sorted(r["code"] for r in listed))

    def test_week_over_week(self):
        events, diff = self.week("events.json"), self.week("diff.json")
        self.assertEqual((events["new"], events["exits"], events["status_changes"]), (["6998@2026-11-17"], [], []))
        self.assertEqual(events["reconciliation"], {"not_in_finmind": [], "not_quoted": [], "finmind_stale": []})
        sl46 = json.loads((screens_dir(self.root) / "2026-w46" / "shortlist.json").read_text(encoding="utf-8"))
        was = {r["code"] for name in ("actionable", "left_watch") for r in sl46[name]}
        self.assertEqual(diff["streak"], {c: 2 if c in was else 1 for c in diff["streak"]})
        self.assertIn(2, diff["streak"].values())
        forward = read_csv(screens_dir(self.root) / "forward.csv")
        self.assertEqual(sorted({r["week"] for r in forward}), ["2026-w46", "2026-w47"])
        sl = self.week("shortlist.json")
        stock = next(s for s in World().stocks if s["code"] == "2330")
        self.assertEqual({r["close"] for r in forward if r["week"] == "2026-w47" and r["code"] == "2330"},
                         {World().close(stock, "2026-11-20")})
        self.assertEqual(sorted((r["list"], r["code"]) for r in forward if r["week"] == "2026-w47"),
                         sorted([("tier_a", c) for c in sl["tier_a"]] + [("actionable", r["code"]) for r in sl["actionable"]]))
        self.assertEqual([r["code"] for r in self.week("watch.json")["recent"]], ["6999", "6998"])
        self.assertEqual([e["code"] for e in self.week("watch.json")["emerging"]], ["7777"])

    def test_rendered_week_passes_check_screen(self):
        review = {"generation": {"model": "claude-opus-5-5", "effort": "high"}, "notes": {}, "events_zh": "本週無異動。"}
        (self.folder / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
        render(self.folder, self.root)
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_screen([str(self.folder), "--root", str(self.root)])
        self.assertEqual(code, 0, out.getvalue())

    def test_same_week_rerun_is_identical(self):       # Review Focus 4
        before = snapshot_files(self.root, "2026-w47")
        before.pop("review.json", None)
        code, out = run_main(["--root", str(self.root)], self.fetcher, "2026-11-21")
        self.assertEqual(code, 0, out)
        self.assertEqual(snapshot_files(self.root, "2026-w47"), before)
        forward = [(r["week"], r["list"], r["code"]) for r in read_csv(screens_dir(self.root) / "forward.csv")]
        self.assertEqual(len(forward), len(set(forward)))

    def test_invariant_failure_writes_nothing(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        f = self.copy_fetcher(World(duplicate_isin=True), keep=lambda key: not key[0].startswith("isin"))
        code, out = run_main(["--root", str(root)], f, "2026-11-21")
        self.assertEqual(code, 1, out)
        self.assertIn("invariant failed: statuses sum to 18, master has 19", out)
        self.assertFalse(screens_dir(root).exists())

    def test_quota_exits_2_then_resumes(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        f = self.copy_fetcher(World())
        built, rebuilt = [], []

        def flaky(code, peers, asof):              # the quota runs out on the second name
            if built:
                raise shared.QuotaError("quota")
            built.append(code)
            return deep(code, peers, asof)

        def counting(code, peers, asof):
            rebuilt.append(code)
            return deep(code, peers, asof)

        code, out = run_main(["--root", str(root)], f, "2026-11-21", build=flaky)
        self.assertEqual(code, 2, out)
        self.assertFalse(screens_dir(root).exists())
        code, out = run_main(["--root", str(root)], f, "2026-11-21", build=counting)
        self.assertEqual(code, 0, out)
        listed = json.loads((screens_dir(root) / "2026-w47" / "funnel.json").read_text(encoding="utf-8"))["counts"]["L5"]
        self.assertNotIn(built[0], rebuilt)                   # the first name came from the deep-metrics cache
        self.assertTrue((f.root / "finmind" / "2026-11-20" / f"{built[0]}.json").exists())
        self.assertFalse((root / "finmind").exists())             # the cache never lands in the repo
        self.assertEqual(len(rebuilt), listed - 1)

    def test_forward_stats_price_an_older_cohort(self):
        """A week-41 cohort of 1312 reaches its 4-week horizon on 2026-11-06, a day 1312 did not trade, so the end
        close steps back a day. 1316 failed L1 that week, so the equal-weight universe is 1312 alone. Rows of later
        weeks (a rerun of an old week) never price a horizon past asof."""
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        world, start = World(), "2026-10-09"
        stock = next(s for s in world.stocks if s["code"] == "1312")
        c0, c1 = world.close(stock, start), world.close(stock, "2026-11-05")
        common = {"name": "n", "market": "twse", "board": "main", "industry": "塑膠工業", "listing_date": "2000-01-03",
                  "track": "full", "history_days": 270, "reason": None, "flags": [], "tags": []}
        write_week(root, "2026-w41", {
            "universe.csv": [dict(common, key=f"{c}@2000-01-03", code=c, status=st)
                             for c, st in (("1312", "shortlist_actionable"), ("1316", "excluded_liquidity"))],
            "scores.csv": [{"key": "1312@2000-01-03", "code": "1312", "rank": 1, "trend_ok": True, "composite": 0.5}],
            "shortlist.json": {"actionable": [{"code": "1312"}], "left_watch": [], "tier_a": ["1312"]},
            "diff.json": {"streak": {"1312": 1}}}, start)
        rows = [("2026-w41", start, "tier_a", c0), ("2026-w41", start, "actionable", c0),
                ("2026-w44", "2026-10-30", "actionable", c0), ("2026-w48", "2026-11-27", "actionable", c0)]
        (screens_dir(root) / "forward.csv").write_text(
            "week,asof,list,code,close\n" + "".join(f"{w},{a},{n},1312,{c}\n" for w, a, n, c in rows), encoding="utf-8")
        code, out = run_main(["--root", str(root)], self.copy_fetcher(World()), "2026-11-21")
        self.assertEqual(code, 0, out)
        ret = (c1 / c0 - 1) * 100
        excess = ret - (world.taiex("2026-11-06") / world.taiex(start) - 1) * 100
        folder = screens_dir(root) / "2026-w47"
        stats = json.loads((folder / "funnel.json").read_text(encoding="utf-8"))["forward"]["stats"]
        self.assertEqual([(s["list"], s["horizon"], s["weeks"], s["names"], s["hit_rate"]) for s in stats],
                         [(name, 4, 1, 1, 100.0 if excess > 0 else 0.0) for name in ("tier_a", "actionable")])
        for s in stats:
            self.assertAlmostEqual(s["median_excess_taiex"], excess)
            self.assertAlmostEqual(s["median_excess_ew"], 0.0)
        self.assertEqual(json.loads((folder / "diff.json").read_text(encoding="utf-8"))["exited"],
                         [{"code": "1312", "list": "actionable", "reason": "excluded_price"}])
        self.assertIn("2026-w48", {r["week"] for r in read_csv(screens_dir(root) / "forward.csv")})

    def test_hysteresis_keeps_last_weeks_names(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(screens_dir(self.root) / "2026-w46", screens_dir(root) / "2026-w46")
        before = [r["code"] for r in json.loads((screens_dir(root) / "2026-w46" / "shortlist.json")
                                                .read_text(encoding="utf-8"))["actionable"]]
        with mock.patch.dict(run.SHORTLIST, enter=1):
            code, out = run_main(["--root", str(root)], self.copy_fetcher(World()), "2026-11-21")
        self.assertEqual(code, 0, out)
        after = [r["code"] for r in json.loads((screens_dir(root) / "2026-w47" / "shortlist.json")
                                               .read_text(encoding="utf-8"))["actionable"]]
        self.assertGreater(len(after), 1)                       # enter=1 alone admits one name
        self.assertLessEqual(set(after[1:]), set(before))

    def test_corrupt_previous_week_fails_the_invariant(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(screens_dir(self.root) / "2026-w46", screens_dir(root) / "2026-w46")
        universe = screens_dir(root) / "2026-w46" / "universe.csv"
        lines = universe.read_text(encoding="utf-8").splitlines(keepends=True)
        universe.write_text("".join(lines + lines[-1:]), encoding="utf-8")      # one row twice
        code, out = run_main(["--root", str(root)], self.copy_fetcher(World()), "2026-11-21")
        self.assertEqual(code, 1, out)
        self.assertIn("invariant failed: master moved 0 but events net 1", out)
        self.assertFalse((screens_dir(root) / "2026-w47").exists())


if __name__ == "__main__":
    unittest.main()
