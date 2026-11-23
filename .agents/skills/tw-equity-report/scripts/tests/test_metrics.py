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
        self.assertEqual(m["ma60"], round(sum(closes) / 60, 2))
        self.assertGreater(m["ma20_slope_5d"], 0)
        self.assertIsNone(m["ma60_slope_5d"])
        self.assertEqual(m["alignment"], "bullish")
        self.assertEqual(m["high60"], 160)
        self.assertEqual(m["low60"], 99)
        self.assertEqual(len(series), 60)

    def test_slopes_over_70_bars(self):
        _, up = mt.price_metrics(price_rows(list(range(100, 170))))
        self.assertGreater(up["ma20_slope_5d"], 0)
        self.assertGreater(up["ma60_slope_5d"], 0)
        _, dn = mt.price_metrics(price_rows(list(range(170, 100, -1))))
        self.assertLess(dn["ma20_slope_5d"], 0)
        self.assertLess(dn["ma60_slope_5d"], 0)

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

    def test_absent_day_is_null_not_zero(self):
        rows = self.inst("Foreign_Investor", {d: 100 for d in self.dates if d != self.dates[5]})
        self.assertEqual(mt.missing_dates(rows, self.dates), [self.dates[5]])
        daily, cum, _ = mt.institutional(rows, self.dates, self.by_date)
        self.assertIsNone(daily[5]["foreign"])
        self.assertEqual(daily[5]["foreign_cum"], 500)
        self.assertEqual(cum["foreign"], 1900)

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
        gaps = []
        r = mt.revenue(rows, gaps)
        self.assertEqual(gaps, [])
        self.assertEqual(r["latest_period"], "2026-03")
        self.assertEqual((r["ytd"], r["ytd_prev"], r["ytd_yoy_pct"]), (600, 300, 100.0))
        jan = next(x for x in r["last12"] if x["period"] == "2026-01")
        self.assertEqual((jan["mom_pct"], jan["yoy_pct"]), (100.0, 100.0))

    def test_revenue_missing_prior_month_is_null(self):
        rows = [{"revenue_year": y, "revenue_month": m, "revenue": 100}
                for y in (2025, 2026) for m in range(1, 4) if (y, m) != (2025, 2)]
        gaps = []
        r = mt.revenue(rows, gaps)
        self.assertIsNone(r["ytd_prev"])
        self.assertIsNone(r["ytd_yoy_pct"])
        self.assertIn("2025-02", gaps[0])

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

    def test_non_consecutive_quarters_null_ttm(self):
        inc = [{"date": q, "type": t, "value": v}
               for q in ("2025-06-30", "2025-12-31", "2026-03-31", "2026-06-30")
               for t, v in (("Revenue", 1000), ("EPS", 1.0), ("IncomeAfterTaxes", 100))]
        cf = [{"date": q, "type": "CashFlowsFromOperatingActivities", "value": 100}
              for q in ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")]
        gaps = []
        f = mt.financials(inc, [], cf, "2026-11-10", gaps)
        self.assertIsNone(f["ttm_eps"])
        self.assertIsNone(f["cash_conversion"])
        self.assertEqual(len(gaps), 1)
        self.assertIn("TTM EPS", gaps[0])

    def test_next_quarter(self):
        self.assertEqual(mt.next_quarter("2025-12-31"), "2026-03-31")
        self.assertEqual(mt.next_quarter("2026-06-30"), "2026-09-30")

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


class Yoy6Median(unittest.TestCase):
    def test_yoy6_median_last_six(self):
        rev = {"last12": [{"yoy_pct": v} for v in [5, 1, 2, 3, 4, 9, 10, 20, None, 40, 50, 60]]}
        self.assertEqual(mt.yoy6_median(rev), 40.0)  # last six: 10, 20, None, 40, 50, 60

    def test_yoy6_median_none(self):
        self.assertIsNone(mt.yoy6_median({"last12": [{"yoy_pct": None}] * 6}))


class CoreBaseline(unittest.TestCase):
    @staticmethod
    def _rev(yoy=20.0, rev=100.0):
        # 24 months ending 2026-10: YTD(2026) = 10*rev*1.2, Rem(2025-11..12) = 2*rev, TTM(2025-11..2026-10) = 2*rev + 10*rev*1.2
        rows = []
        for y in (2024, 2025, 2026):
            for m in range(1, 13):
                if y == 2026 and m > 10:
                    continue
                val = rev * (1 + yoy / 100.0) if y == 2026 else rev
                rows.append({"revenue_year": y, "revenue_month": m, "revenue": val})
        return mt.revenue(rows, [])

    @staticmethod
    def _fin(tax=25.0, pt=100.0, nip=63.75, ni=75.0, eps=0.6375, share_cap=5000.0,
             ois=(200.0, 200.0, 200.0, 200.0), qs=("2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30")):
        inc = []
        for q, oi in zip(qs, ois):
            for t, v in (("Revenue", 1000.0), ("OperatingIncome", oi), ("EPS", eps),
                         ("EquityAttributableToOwnersOfParent", nip), ("IncomeAfterTaxes", ni),
                         ("TAX", tax), ("PreTaxIncome", pt)):
                if v is not None:
                    inc.append({"date": q, "type": t, "value": v})
        bal = [{"date": qs[-1], "type": "OrdinaryShare", "value": share_cap}]
        return mt.financials(inc, bal, [], "2026-11-15", [])

    def test_minority_custom_tax_and_par5_shares(self):
        rev = self._rev(yoy=20.0, rev=100.0)
        # Par 5 stock: OrdinaryShare=5000 -> par10=500, actual shares=1000 (nip=63.75 / eps=0.06375? Wait use nip=250, eps=0.25 -> 1000)
        fin = self._fin(tax=25.0, pt=100.0, nip=250.0, ni=294.117647, eps=0.25, share_cap=5000.0)
        # Note parent_ratio = 250 / 294.117647 = 0.85, tax = 0.25, TTM OPM = 800 / 4000 = 0.20
        # core_margin = 0.20 * 0.75 * 0.85 = 0.1275
        # cy_rev = 10*120 + 2*100*1.2 = 1440 -> cy_eps = 1440 * 0.1275 / 1000 = 0.1836 -> 0.18
        # Scale rev=10000 for crisp decimals:
        rev = self._rev(yoy=20.0, rev=10000.0)
        cb = mt.core_baseline(rev, fin)
        self.assertTrue(cb["applicable"])
        self.assertEqual(cb["shares_used"], 1000)
        self.assertEqual(cb["shares_source"], "implied_latest_q")
        self.assertEqual(cb["tax_source"], "ttm_actual")
        self.assertEqual(cb["parent_source"], "ttm_actual")
        self.assertEqual(cb["effective_tax_rate_pct"], 25.0)
        self.assertEqual(cb["parent_ratio_pct"], 85.0)
        self.assertEqual(cb["core_net_margin_pct"], 12.75)
        self.assertTrue(cb["cy_late_year"])
        self.assertEqual(cb["cy_eps"], round(144000 * 0.1275 / 1000, 2))
        # ntm_rev = (2*10000 + 10*12000) * 1.2 = 140000 * 1.2 = 168000 -> ntm_eps = 168000 * 0.1275 / 1000 = 21.42
        self.assertEqual(cb["ntm_eps"], 21.42)
        self.assertFalse(cb["high_volatility"])

    def test_fallback_guards_and_share_tiers(self):
        rev = self._rev(yoy=20.0, rev=10000.0)
        # Anomalous tax > 40% + parent > 100% + small quarterly EPS -> implied_ttm + default tax & parent
        fin = self._fin(tax=50.0, pt=100.0, nip=120.0, ni=100.0, eps=0.12, share_cap=5000.0)
        cb = mt.core_baseline(rev, fin)
        self.assertTrue(cb["applicable"])
        self.assertEqual(cb["tax_source"], "default_20pct")
        self.assertEqual(cb["effective_tax_rate_pct"], 20.0)
        self.assertEqual(cb["parent_source"], "default_100pct")
        self.assertEqual(cb["parent_ratio_pct"], 100.0)
        self.assertEqual(cb["shares_source"], "implied_ttm")
        self.assertEqual(cb["shares_used"], 1000)

        # Missing parent NI -> ordinary_share_par10 fallback + PreTaxIncome <= 0 -> default_20pct
        fin2 = self._fin(tax=10.0, pt=-5.0, nip=None, ni=100.0, eps=1.0, share_cap=5000.0)
        cb2 = mt.core_baseline(rev, fin2)
        self.assertEqual(cb2["shares_source"], "ordinary_share_par10")
        self.assertEqual(cb2["shares_used"], 500)
        self.assertEqual(cb2["tax_source"], "default_20pct")

    def test_inapplicable_cases(self):
        rev = self._rev(yoy=20.0, rev=10000.0)
        fin_loss = self._fin(ois=(-50.0, -20.0, 10.0, 20.0))
        cb_loss = mt.core_baseline(rev, fin_loss)
        self.assertFalse(cb_loss["applicable"])
        self.assertEqual(cb_loss["reason"], "nonpositive_operating_income")

        fin_gap = self._fin(qs=("2025-09-30", "2026-03-31", "2026-06-30", "2026-09-30"))
        cb_gap = mt.core_baseline(rev, fin_gap)
        self.assertFalse(cb_gap["applicable"])
        self.assertEqual(cb_gap["reason"], "non_consecutive_quarters")

    def test_high_volatility_triggers(self):
        rev_high = self._rev(yoy=60.0, rev=10000.0)
        fin_vol = self._fin(ois=(-10.0, 100.0, 150.0, 200.0))
        cb = mt.core_baseline(rev_high, fin_vol)
        self.assertTrue(cb["applicable"])
        self.assertTrue(cb["high_volatility"])
        self.assertEqual(set(cb["volatility_reasons"]),
                         {"opm_spread_gt_5pp", "negative_quarter_opm", "yoy_gt_50pct"})


if __name__ == "__main__":
    unittest.main()
