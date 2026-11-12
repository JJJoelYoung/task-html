"""Unit tests for metrics.py on small synthetic rows (no network)."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metrics as mt  # noqa: E402


def price_rows(closes, volumes=None, start=date(2026, 1, 5)):
    rows = []
    for i, c in enumerate(closes):
        v = (volumes[i] if volumes else 10) * 1000
        rows.append({"date": (start + timedelta(days=i)).isoformat(), "open": c, "max": c + 1, "min": c - 1,
                     "close": c, "Trading_Volume": v, "Trading_money": v * c})
    return rows


class Helpers(unittest.TestCase):
    def test_percentile_linear(self):
        self.assertEqual(mt.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(mt.percentile([1, 2, 3, 4], 25), 1.75)
        self.assertIsNone(mt.percentile([], 50))

    def test_pct(self):
        self.assertAlmostEqual(mt.pct(110, 100), 10.0)
        self.assertIsNone(mt.pct(1, 0))


class Price(unittest.TestCase):
    def test_bullish_series(self):
        closes = list(range(100, 160))
        series, m = mt.price_metrics(price_rows(closes))
        self.assertEqual(m["close"], 159)
        self.assertEqual(m["ma20"], round(sum(closes[-20:]) / 20, 2))
        self.assertEqual(m["alignment"], "bullish")
        self.assertEqual(m["high60"], 160)
        self.assertEqual(m["low60"], 99)
        self.assertEqual(len(series), 60)

    def test_bearish_and_zero_volume_dropped(self):
        rows = price_rows(list(range(160, 100, -1)))
        rows.append({**rows[-1], "date": "2026-12-31", "Trading_Volume": 0, "Trading_money": 0})
        series, m = mt.price_metrics(rows)
        self.assertEqual(len(series), 60)
        self.assertEqual(m["alignment"], "bearish")

    def test_spike_dryup_and_squeeze(self):
        vols = [10] * 58 + [30, 2]
        _, m = mt.price_metrics(price_rows([100] * 60, vols))
        self.assertTrue(m["squeeze"])
        self.assertEqual(m["alignment"], "mixed")
        self.assertEqual(len(m["spike_days"]), 1)
        self.assertEqual(len(m["dryup_days"]), 1)
        self.assertEqual(m["w20_maxvol_lots"], 30)

    def test_float_settling(self):
        pm = {"dryup_days": ["d"] * 5}
        self.assertTrue(mt.float_settling(pm, {"margin_change": -1})["signal"])
        self.assertFalse(mt.float_settling(pm, {"margin_change": 0})["signal"])
        self.assertFalse(mt.float_settling({"dryup_days": ["d"] * 4}, {"margin_change": -1})["signal"])
        self.assertFalse(mt.float_settling(pm, None)["signal"])


class Chips(unittest.TestCase):
    def setUp(self):
        self.dates = [f"2026-01-{i:02d}" for i in range(1, 21)]
        self.by_date = {d: {"avg_price": 100.0} for d in self.dates}

    def inst(self, name, net_by_day):
        return [{"date": d, "name": name, "buy": max(n, 0) * 1000, "sell": max(-n, 0) * 1000}
                for d, n in net_by_day.items()]

    def test_foreign_cost_zone(self):
        rows = self.inst("Foreign_Investor", {self.dates[i]: 100 for i in range(3)})
        daily, cum, zone = mt.institutional(rows, self.dates, self.by_date)
        self.assertEqual(cum["foreign"], 300)
        self.assertEqual(zone, {"group": "foreign", "days": 3, "price": 100.0, "low": 98.0, "high": 102.0})
        self.assertEqual(daily[-1]["foreign_cum"], 300)

    def test_falls_back_to_trust_then_none(self):
        rows = self.inst("Foreign_Investor", {self.dates[0]: 100}) + \
            self.inst("Investment_Trust", {self.dates[i]: 50 for i in range(4)})
        self.assertEqual(mt.institutional(rows, self.dates, self.by_date)[2]["group"], "trust")
        self.assertIsNone(mt.institutional(rows[:1], self.dates, self.by_date)[2])

    def test_short_margin_levels(self):
        def lvl(short):
            rows = [{"date": self.dates[0], "MarginPurchaseTodayBalance": 1000, "ShortSaleTodayBalance": short}]
            return mt.margin(rows, self.dates)["short_margin_level"]
        self.assertEqual(lvl(49), "low")
        self.assertEqual(lvl(200), "medium")
        self.assertEqual(lvl(201), "high")


class Operations(unittest.TestCase):
    def test_revenue_ytd_mom_yoy(self):
        rows = [{"revenue_year": y, "revenue_month": m, "revenue": (200 if y == 2026 else 100)}
                for y in (2025, 2026) for m in range(1, 13) if not (y == 2026 and m > 3)]
        r = mt.revenue(rows)
        self.assertEqual(r["latest_period"], "2026-03")
        self.assertEqual((r["ytd"], r["ytd_prev"], r["ytd_yoy_pct"]), (600, 300, 100.0))
        jan = next(x for x in r["last12"] if x["period"] == "2026-01")
        self.assertEqual((jan["mom_pct"], jan["yoy_pct"]), (100.0, 100.0))

    def test_usable_deadlines(self):
        self.assertFalse(mt.usable("2026-09-30", "2026-11-13"))
        self.assertTrue(mt.usable("2026-09-30", "2026-11-14"))
        self.assertTrue(mt.usable("2025-12-31", "2026-03-31"))

    def test_financials(self):
        qs = ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
        inc, bal, cf = [], [], []
        for i, q in enumerate(qs):
            for t, v in (("Revenue", 1000), ("GrossProfit", 250), ("OperatingIncome", 100),
                         ("CostOfGoodsSold", 750), ("EPS", 1.0 + i), ("IncomeAfterTaxes", 100)):
                inc.append({"date": q, "type": t, "value": v})
            bal.append({"date": q, "type": "Inventories", "value": 300 + 100 * i})
        bal += [{"date": qs[-1], "type": "EquityAttributableToOwnersOfParent", "value": 5000},
                {"date": qs[-1], "type": "OrdinaryShare", "value": 1000}]
        # Cumulative within the fiscal year.
        for q, v in (("2025-06-30", 100), ("2025-09-30", 250), ("2025-12-31", 400),
                     ("2026-03-31", 120), ("2026-06-30", 300)):
            cf.append({"date": q, "type": "CashFlowsFromOperatingActivities", "value": v})
        gaps = []
        f = mt.financials(inc, bal, cf, "2026-11-10", gaps)
        self.assertEqual(f["ttm_eps"], 10.0)
        self.assertEqual(f["quarters"][-1]["gross_margin_pct"], 25.0)
        self.assertEqual(f["quarters"][-1]["dsi_days"], round((600 + 500) / 2 / 750 * 91, 1))
        self.assertEqual(f["ocf_quarterly"]["2025-09-30"], 150)
        self.assertEqual(f["ocf_quarterly"]["2026-06-30"], 180)
        self.assertEqual(f["cash_conversion"]["ratio"], round((150 + 150 + 120 + 180) / 400, 2))
        self.assertEqual(f["bvps_latest"], 50.0)
        self.assertEqual(gaps, [])

    def test_missing_quarter_gap(self):
        self.assertIn("2026-09-30", mt.missing_quarter_gap("2026-06-30", "2026-11-10"))
        self.assertIsNone(mt.missing_quarter_gap("2026-09-30", "2026-11-10"))
        self.assertIsNone(mt.missing_quarter_gap("2025-09-30", "2026-01-15"))


class Valuation(unittest.TestCase):
    def test_bands_drop_nonpositive_per(self):
        rows = [{"date": f"2026-01-{i:02d}", "PER": v, "PBR": 1.0 + i / 10, "dividend_yield": 2.0}
                for i, v in enumerate([-5, 0, 10, 20, 30, 40], start=1)]
        b = mt.bands(rows)
        self.assertEqual(b["PER"]["n"], 4)
        self.assertEqual(b["PER"]["p50"], 25.0)
        self.assertEqual(b["PER"]["current_percentile"], 100.0)
        self.assertEqual(b["PBR"]["n"], 6)

    def test_peer_median_excludes_target(self):
        rows = [{"code": "T", "PER": 99, "PBR": 9, "dividend_yield": 0}] + \
            [{"code": c, "PER": p, "PBR": 1, "dividend_yield": 2} for c, p in (("A", 10), ("B", 20), ("C", -3))]
        self.assertEqual(mt.peer_matrix(rows)["median"]["PER"], 15.0)
        self.assertIsNone(mt.peer_matrix(rows[:1])["median"])


if __name__ == "__main__":
    unittest.main()
