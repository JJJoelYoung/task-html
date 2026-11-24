"""Unit tests for factors.py on synthetic panels, revenue, and quarters (no network)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from factors import adv20, history_days, momentum_6_1, persistence, price_rows, stock_factors, week_ends  # noqa: E402
from helpers import panel_with  # noqa: E402

FLOW = {"foreign": 600.0, "trust": 400.0, "dealer": 5000.0}           # dealer never counts
FLOW0 = {"foreign": 1000.0, "trust": 0.0, "dealer": 0.0}
SEASONS = [(2024, 4), (2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2), (2026, 3)]


def quarters(op=(5, 5, 5, 5, 8, 10, 12, 10), eps=(0.5, 0.5, 0.5, 0.5, 1.0, 1.2, 1.5, 1.3), seasons=SEASONS):
    return [{"year": y, "season": s, "revenue": 100, "op_income": o, "pretax": None, "net_income": None,
             "net_parent": None, "eps": e} for (y, s), o, e in zip(seasons, op, eps)]


def factors_for(rev=None, latest=(2026, 10), market=(2026, 10), qs=None, closes=None, flows=None, per=20.0,
                pbr=2.0, shares=2_000_000, note=None, yoy=10.0, drop=()):
    """stock_factors for code X with defaults: 25 months of revenue 100..124 ending at `latest`, the 8 quarters
    above, closes of 100 over 130 dates, and foreign + trust = 1,000 shares (trust 400) on each of the last 20."""
    rev = [100 + k for k in range(25)] if rev is None else rev
    y, m = latest
    rows = []
    for k, r in enumerate(rev):
        t = y * 12 + m - 1 - (len(rev) - 1 - k)
        if (t // 12, t % 12 + 1) not in drop:
            rows.append({"revenue_year": t // 12, "revenue_month": t % 12 + 1, "revenue": r})
    closes = [100.0] * 130 if closes is None else closes
    flows = [None] * (len(closes) - 20) + [FLOW] * 20 if flows is None else flows
    return stock_factors("X", panel_with("X", closes, flows=flows), rows, {"note": note, "yoy_pct": yoy},
                         quarters() if qs is None else qs, {"per": per, "pbr": pbr, "yield": 1.0}, shares, market)


def multi_panel(series):
    """One Panel holding several codes' closes of equal length."""
    panels = [panel_with(code, closes) for code, closes in series.items()]
    base = panels[0]
    for p in panels[1:]:
        for d in base.dates:
            base.days[d]["quotes"].update(p.days[d]["quotes"])
    return base


class PanelHelpers(unittest.TestCase):
    def test_history_days_spans_board_transfer(self):        # Review Focus 1: one code, quotes on TPEx, then TWSE
        p = panel_with("8908", [10.0] * 300)
        for d in p.dates[:150]:
            p.days[d]["quotes"]["8908"]["market"] = "tpex"
        self.assertEqual(history_days(p, "8908"), 300)

    def test_history_days_breaks_at_long_gap(self):
        self.assertEqual(history_days(panel_with("X", [10.0] * 100 + [None] * 100 + [10.0] * 100), "X"), 100)

    def test_history_days_keeps_short_suspension(self):
        self.assertEqual(history_days(panel_with("X", [10.0] * 135 + [None] * 30 + [10.0] * 135), "X"), 270)

    def test_history_days_gap_limit_is_per_gap(self):         # 60 empty dates keep the run, 61 break it
        self.assertEqual(history_days(panel_with("X", [10.0] * 50 + [None] * 60 + [10.0] * 50), "X"), 100)
        self.assertEqual(history_days(panel_with("X", [10.0] * 50 + [None] * 61 + [10.0] * 50), "X"), 50)
        two_gaps = [10.0] * 50 + [None] * 40 + [10.0] * 50 + [None] * 40 + [10.0] * 50
        self.assertEqual(history_days(panel_with("X", two_gaps), "X"), 150)

    def test_adv20_missing_days_are_zero(self):
        p = panel_with("X", [10.0] * 20 + [None] * 10, values=[100e6] * 10 + [50e6] * 10 + [None] * 10)
        self.assertEqual(adv20(p, "X"), 25e6)                 # the 100e6 dates fall outside the last 20

    def test_adv20_is_median(self):
        self.assertEqual(adv20(panel_with("X", [10.0] * 20, values=[10e6] * 19 + [210e6]), "X"), 10e6)

    def test_week_ends_by_iso_week(self):                   # Jan 5–9, Jan 12–16, Jan 19–20
        p = panel_with("X", [1.0] * 12)
        self.assertEqual((week_ends(p), week_ends(p, 2)), ([4, 9, 11], [9, 11]))

    def test_momentum_6_1_never_wraps(self):
        p = panel_with("X", [float(i + 1) for i in range(130)])
        self.assertAlmostEqual(momentum_6_1(p, "X", 129), 109 / 4 - 1)
        self.assertIsNone(momentum_6_1(p, "X", 125))         # close(−1) must not read the last date

    def test_price_rows_last_n_traded(self):
        p = panel_with("X", [10.0, None, 11.0, 12.0, 13.0])
        p.days[p.dates[4]]["quotes"]["X"]["close"] = None    # a "--" row: listed, not traded
        rows = price_rows(p, "X", n=2)
        self.assertEqual(rows, [{"date": "2026-01-07", "open": 11.0, "max": 11.0, "min": 11.0, "close": 11.0,
                                 "Trading_Volume": 1000.0, "Trading_money": 11000.0},
                                {"date": "2026-01-08", "open": 12.0, "max": 12.0, "min": 12.0, "close": 12.0,
                                 "Trading_Volume": 1000.0, "Trading_money": 12000.0}])

    def test_persistence_counts_top_third(self):
        p = multi_panel({"A": [100 * 1.01 ** i for i in range(200)], "B": [100 * 1.005 ** i for i in range(200)],
                         "C": [100.0] * 200, "D": [None] * 150 + [100.0] * 50})
        self.assertEqual(persistence(p, ["A", "B", "C", "D"]), {"A": 13, "B": 0, "C": 0, "D": None})
        q = multi_panel({"A": [100 * 1.01 ** i for i in range(200)], "B": [100 * 1.007 ** i for i in range(200)],
                         "C": [100 * 1.005 ** i for i in range(200)], "E": [100.0] * 200})
        self.assertEqual(persistence(q, ["A", "B", "C", "E"]), {"A": 13, "B": 13, "C": 0, "E": 0})  # ceil(4/3) = 2


class StockFactors(unittest.TestCase):
    def test_rev_surge(self):
        R = [100] * 12 + [100, 102] * 6 + [110]              # d over months 13–24 alternates 0, 2; d_25 = 10
        self.assertAlmostEqual(factors_for(rev=R)["rev_surge"], 9.0)

    def test_on_time_filer_revenue_inputs(self):             # yoy_k = 1200 / (88 + k), rounded to 0.1
        f = factors_for()
        self.assertEqual((f["latest_month"], f["rev3"], f["rev3_ly"], f["rev_surge"]), ((2026, 10), 369, 333, None))
        self.assertAlmostEqual(f["rev_yoy_med6"], 10.95)
        self.assertAlmostEqual(f["rev_accel"], 10.8 - 135.3 / 12)
        self.assertAlmostEqual(f["rev_yoy3"], 369 / 333 * 100 - 100)

    def test_quality_valuation_flow(self):
        f = factors_for()
        for key, want in (("opm_ttm", 10.0), ("opm_delta_4q", 5.0), ("opm_spread_4q", 4.0), ("roe_ttm", 10.0),
                          ("earnings_yield", 5.0), ("book_yield", 50.0), ("flow20_pct", 1.0), ("op_income_recent", 40)):
            self.assertAlmostEqual(f[key], want, msg=key)
        self.assertEqual((f["trust_days20"], f["close"], f["adv20"]), (20, 100.0, 100000.0))

    def test_rev_accel_needs_twelve_consecutive_months(self):
        f = factors_for(drop=[(2026, 5)])
        self.assertIsNone(f["rev_accel"])
        self.assertAlmostEqual(f["rev_yoy3"], 369 / 333 * 100 - 100)

    def test_quarter_gap_gives_none(self):
        f = factors_for(qs=[q for q in quarters() if (q["year"], q["season"]) != (2026, 1)])
        self.assertEqual([f[k] for k in ("opm_ttm", "opm_delta_4q", "opm_spread_4q", "roe_ttm")], [None] * 4)

    def test_recent_op_income_sums_the_latest_run(self):     # final review I2: the L2 loss test on fewer quarters
        gap = [q for q in quarters() if (q["year"], q["season"]) != (2026, 1)]
        self.assertEqual(factors_for(qs=gap)["op_income_recent"], 22)          # 2026Q2 + Q3; the gap ends the run
        self.assertEqual(factors_for(qs=quarters()[-1:])["op_income_recent"], 10)
        self.assertIsNone(factors_for(qs=[])["op_income_recent"])
        unknown = quarters(op=(5, 5, 5, 5, 8, 10, None, 10))
        self.assertIsNone(factors_for(qs=unknown)["op_income_recent"])

    def test_nonpositive_valuation_and_missing_shares(self):
        f = factors_for(per=-5.0, pbr=-1.0, shares=None)
        self.assertEqual([f[k] for k in ("earnings_yield", "book_yield", "roe_ttm", "flow20_pct")], [None] * 4)

    def test_flow_missing_days_count_zero(self):
        f = factors_for(flows=[FLOW] * 110 + [None] * 5 + [FLOW0] * 5 + [FLOW] * 10)
        self.assertAlmostEqual(f["flow20_pct"], 0.75)        # (5 × 1,000 + 10 × 1,000) / 2,000,000
        self.assertEqual(f["trust_days20"], 10)

    def test_ret13w(self):
        self.assertAlmostEqual(factors_for(closes=[50.0] + [100.0] * 65)["ret13w"], 100.0)

    def test_late_filer_revenue_inputs_null(self):           # Review Focus 5: latest month 2026-09, market month 2026-10
        f = factors_for(latest=(2026, 9), market=(2026, 10))
        self.assertEqual([f[k] for k in ("rev_yoy_med6", "rev_accel", "rev_surge", "rev_yoy3", "rev3", "rev3_ly")],
                         [None] * 6)
        self.assertEqual(f["latest_month"], (2026, 9))

    def test_no_revenue_rows(self):
        self.assertEqual([factors_for(rev=[])[k] for k in ("rev_yoy_med6", "latest_month")], [None, None])

    def test_one_off_flag(self):
        self.assertEqual([factors_for(note=n, yoy=y)["one_off"] for n, y in (("x", 150), ("x", 100), ("x", 50), (None, 150))],
                         [True, False, False, False])


if __name__ == "__main__":
    unittest.main()
