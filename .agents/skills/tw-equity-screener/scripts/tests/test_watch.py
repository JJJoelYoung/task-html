"""Unit tests for watch.py: watch-track tables and the TAIEX regime flag (no network)."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import sec  # noqa: E402
from watch import regime, watch_tables  # noqa: E402

PIPELINE = {
    "upcoming": [{"code": "7003", "applied": "2026-08-01", "listing_date": None},
                 {"code": "7002", "applied": "2026-07-01", "listing_date": "2026-12-10"},
                 {"code": "7001", "applied": "2026-09-01", "listing_date": "2026-12-01"},
                 {"code": "7004", "applied": "2026-06-01", "listing_date": "2026-12-10"}],
    "first_five": {"6999": {"first": "2026-11-17", "fifth": "2026-11-21", "price": 50.0}},
    "emerging": {"7701": {"avg": 30.0, "last": 31.0, "volume": 5000.0, "applying_status": "申請上櫃"},
                 "7702": {"avg": 20.0, "last": 19.0, "volume": 100.0, "applying_status": ""}},
    "delisted": {},
}


def series(closes, start=date(2025, 1, 1)):
    return [((start + timedelta(days=i)).isoformat(), c) for i, c in enumerate(closes)]


def rev_with_yoy(last6):
    """2025 months at 100, then 2026-01..06 at 100 × (1 + yoy / 100)."""
    rows = [{"revenue_year": 2025, "revenue_month": m, "revenue": 100} for m in range(1, 13)]
    return rows + [{"revenue_year": 2026, "revenue_month": m, "revenue": 100 + y} for m, y in enumerate(last6, 1)]


def tables(master, tracks=None, history=None, emerging_rev=None):
    return watch_tables(master, tracks or {}, history or {}, PIPELINE, emerging_rev or {}, "2026-11-20")


class Regime(unittest.TestCase):
    def test_regime_transition_on_cross(self):
        r = regime(series([100.0] * 270 + [101.0 + i for i in range(10)]))
        self.assertTrue(r["transition"])
        self.assertIn("ma60_cross", r["reasons"])
        self.assertEqual((r["close"], r["above_ma60"]), (110.0, True))

    def test_regime_ret12m_sign_only(self):              # far below its MA60 throughout; the 12-month return turns
        closes = [50.0] * 30 + [200.0] * 230 + [40.0] * 15 + [60.0] * 5
        r = regime(series(closes))
        self.assertEqual((r["transition"], r["reasons"], r["above_ma60"]), (True, ["ret12m_sign"], False))
        self.assertAlmostEqual(r["ret12m"], 60.0 / 50.0 * 100 - 100)

    def test_regime_window_starts_20_dates_back(self):   # only the oldest window date sees a negative 12-month return
        r = regime(series([50.0] * 10 + [200.0] + [50.0] * 189 + [100.0] * 80))
        self.assertEqual((r["transition"], r["reasons"]), (True, ["ret12m_sign"]))

    def test_regime_quiet(self):
        r = regime(series([100.0 + i for i in range(280)]))
        self.assertEqual((r["transition"], r["reasons"]), (False, []))
        self.assertAlmostEqual(r["ma60"], mean_last := sum(100.0 + i for i in range(220, 280)) / 60)
        self.assertAlmostEqual(r["ma60_slope_5d"], 5.0)
        self.assertAlmostEqual(r["ret12m"], 379.0 / 129.0 * 100 - 100)
        self.assertTrue(r["close"] > mean_last)

    def test_regime_insufficient_history(self):
        r = regime(series([100.0] * 200))
        self.assertEqual((r["transition"], r["reasons"]), (None, ["insufficient_history"]))
        self.assertEqual(regime(series([100.0 + i for i in range(270)]))["transition"], False)  # 270 is enough


class Tables(unittest.TestCase):
    def test_upcoming_sorted_by_listing_then_application(self):
        self.assertEqual([u["code"] for u in tables([])["upcoming"]], ["7001", "7004", "7002", "7003"])

    def test_recent_days_to_full(self):
        new, old, emg = sec("6999", "2026-07-01", "tpex"), sec("2330", "1994-09-05", "twse"), sec("7701", "2020-01-02",
                                                                                                  "emerging")
        t = tables([new, old, emg], tracks={new.key: "watch", old.key: "full", emg.key: "watch"},
                   history={"6999": 80, "2330": 300})
        self.assertEqual(t["recent"], [{"code": "6999", "name": "n", "market": "tpex", "listing_date": "2026-07-01",
                                        "history_days": 80, "days_to_full": 40,
                                        "first_five": PIPELINE["first_five"]["6999"]}])

    def test_emerging_standout_rule(self):
        a, b, c = sec("7701", "2020-01-02", "emerging"), sec("7702", "2020-01-02", "emerging"), sec("7703", "2020-01-02",
                                                                                                    "emerging")
        t = tables([a, b, c], emerging_rev={"7701": rev_with_yoy([25, 30, 20, 22, 24, 26]),
                                            "7702": rev_with_yoy([25, 30, 20, 22, -1, 26]),
                                            "7703": []})
        self.assertEqual([e["code"] for e in t["emerging"]], ["7701"])
        e = t["emerging"][0]
        self.assertEqual((e["rev_yoy_med6"], e["avg"], e["last"], e["volume"], e["applying_status"]),
                         (24.5, 30.0, 31.0, 5000.0, "申請上櫃"))

    def test_emerging_median_bound(self):                # median exactly 20 is listed; just below is not
        a, b = sec("7701", "2020-01-02", "emerging"), sec("7702", "2020-01-02", "emerging")
        t = tables([a, b], emerging_rev={"7701": rev_with_yoy([20] * 6), "7702": rev_with_yoy([19.9] * 6)})
        self.assertEqual([e["code"] for e in t["emerging"]], ["7701"])


if __name__ == "__main__":
    unittest.main()
