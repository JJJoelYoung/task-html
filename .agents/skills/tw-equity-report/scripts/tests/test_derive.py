"""Unit tests for derive.py (methodology sections 6 and 7) on synthetic inputs."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive as dv  # noqa: E402


def inputs(close, ma10, ma20, high60, low60, maxvol_low, zone=None, eps=(12, 10, 8), mult=(20, 18, 12)):
    d = {
        "price": {"metrics": {"close": close, "ma10": ma10, "ma20": ma20, "high60": high60, "low60": low60,
                              "w20_maxvol_low": maxvol_low, "vol_avg20_lots": 1000}},
        "institutional": {"cost_zone": zone},
    }
    a = {"scenarios": [
        {"name": "Bull", "eps": eps[0], "multiple": mult[0], "probability": 25},
        {"name": "Base", "eps": eps[1], "multiple": mult[1], "probability": 50},
        {"name": "Bear", "eps": eps[2], "multiple": mult[2], "probability": 25},
    ]}
    return d, a


class Ticks(unittest.TestCase):
    def test_tick_bands(self):
        self.assertEqual([dv.tick(p) for p in (9.99, 10, 49.95, 50, 99.9, 100, 499.5, 500, 999, 1000)],
                         [0.01, 0.05, 0.05, 0.1, 0.1, 0.5, 0.5, 1.0, 1.0, 5.0])

    def test_round_tick(self):
        self.assertEqual(dv.round_tick(288.3), 288.5)
        self.assertEqual(dv.round_tick(1163), 1165)
        self.assertEqual(dv.round_tick(48.12), 48.1)

    def test_formats(self):
        self.assertEqual(dv.fmt_price(1160), "1,160")
        self.assertEqual(dv.fmt_price(288.5), "288.5")
        self.assertEqual(dv.fmt_price(48.1), "48.10")
        self.assertEqual(dv.fmt_pct(10.94), "+10.9%")
        self.assertEqual(dv.fmt_pct(None), "無資料")
        self.assertEqual(dv.fmt_rr(-0.814), "-0.81")


class Rating(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(dv.rating_of(15.1)[0], "買進")
        self.assertEqual(dv.rating_of(15.0)[0], "中立")
        self.assertEqual(dv.rating_of(-5.0)[0], "中立")
        self.assertEqual(dv.rating_of(-5.1)[0], "賣出")


class Uptrend(unittest.TestCase):
    """Close above both MAs; cost zone overlaps the MA band."""

    def setUp(self):
        d, a = inputs(close=150, ma10=145, ma20=140, high60=160, low60=120, maxvol_low=135,
                      zone={"low": 141, "high": 147})
        self.x = dv.derive(d, a)

    def test_targets_and_rating(self):
        x = self.x
        self.assertEqual([s["target"] for s in x["scenarios"]], [240, 180, 96])
        self.assertEqual(x["base"]["upside_pct"], 20.0)
        self.assertEqual(x["rating_zh"], "買進")
        self.assertEqual(x["weighted_target"], 174)

    def test_trade_setup(self):
        x = self.x
        self.assertEqual((x["zone_low"], x["zone_high"], x["zone_source"]), (141, 145, "overlap"))
        self.assertEqual(x["entry"], 143)
        self.assertEqual(x["t1"], 160)
        self.assertEqual((x["hard_stop"], x["hard_stop_source"]), (136, "candidate"))
        self.assertEqual(x["breakout_stop"], 152)
        self.assertEqual(x["rr_pullback"], round((180 - 143) / (143 - 136), 2))
        self.assertEqual(x["rr_breakout"], round((180 - 160) / (160 - 152), 2))


class InactiveSetups(unittest.TestCase):
    """Close below the MA band (the 2492 case): both setups are inactive and R:R is None."""

    def test_below_zone(self):
        d, a = inputs(close=100, ma10=115, ma20=125, high60=150, low60=90, maxvol_low=126,
                      eps=(6, 5, 4), mult=(24, 22, 14))
        x = dv.derive(d, a)
        self.assertEqual(x["zone_source"], "ma_band")
        self.assertEqual(x["pullback_status"], "below_zone")
        self.assertEqual(x["breakout_status"], "target_below_trigger")
        self.assertIsNone(x["rr_pullback"])
        self.assertIsNone(x["rr_breakout"])
        self.assertEqual(dv.fmt_rr(x["rr_pullback"]), "不適用")
        self.assertEqual(x["entry"], 120)

    def test_target_below_entry(self):
        d, a = inputs(close=150, ma10=145, ma20=140, high60=160, low60=120, maxvol_low=135,
                      eps=(8, 7, 6), mult=(20, 20, 12))
        x = dv.derive(d, a)
        self.assertEqual(x["pullback_status"], "target_below_entry")
        self.assertIsNone(x["rr_pullback"])

    def test_active_statuses_in_uptrend(self):
        d, a = inputs(close=150, ma10=145, ma20=140, high60=160, low60=120, maxvol_low=135)
        x = dv.derive(d, a)
        self.assertEqual((x["pullback_status"], x["breakout_status"]), ("active", "active"))


if __name__ == "__main__":
    unittest.main()
