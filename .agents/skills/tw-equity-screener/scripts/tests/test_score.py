"""Unit tests for score.py: track split, winsorize, z-scores, sector gate, composite, and the funnel."""

import sys
import unittest
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import sec  # noqa: E402
from score import (PARAMS, STATUSES, composite, run_funnel, sector_scores, track, winsorize,  # noqa: E402
                   zscores)

P0 = dict(PARAMS, winsor=(0, 100))      # no clamping, so synthetic z-scores stay exact
BASE = {"close": 50.0, "adv20": 1e8, "op_income_recent": 100,"rev_yoy_med6": 5.0, "rev_accel": 0.0, "rev_surge": 0.0,
        "opm_delta_4q": 0.0, "earnings_yield": 5.0, "book_yield": 50.0, "opm_ttm": 10.0, "opm_spread_4q": 2.0,
        "roe_ttm": 10.0, "flow20_pct": 0.1, "trust_days20": 5, "persist13": 4, "rev3": 110, "rev3_ly": 100,
        "rev_yoy3": 10.0, "ret13w": 5.0, "one_off": False}
WEAK = {"rev3": 90, "rev3_ly": 100, "rev_yoy3": -10.0, "ret13w": -5.0}      # worst on every sector input
SCORED_VARS = ("rev_yoy_med6", "rev_accel", "rev_surge", "opm_delta_4q", "earnings_yield", "book_yield",
               "opm_ttm", "roe_ttm", "flow20_pct", "trust_days20")


def high(v):
    """Factor overrides that set every scored variable to v (and the spread to −v, lower being better)."""
    return dict({k: v for k in SCORED_VARS}, opm_spread_4q=-v)


def S(code, industry="I", **kw):
    return dict(code=code, industry=industry, **kw)


def universe(*stocks, non_general=(), params=P0):
    master, tracks, tags, factors, trend = [], {}, {}, {}, {}
    for st in stocks:
        s = sec(st["code"], "2020-01-02", st.get("market", "twse"), industry=st["industry"],
                board=st.get("board", "main"))
        master.append(s)
        tracks[s.key] = st.get("track", "full")
        tags[s.code] = set(st.get("tags", ()))
        factors[s.code] = dict(BASE, **st.get("f", {}))
        trend[s.code] = st.get("trend", True)
    rows, counts = run_funnel(master, tracks, tags, factors, trend, set(non_general), params)
    return {k.split("@")[0]: r for k, r in rows.items()}, counts


def sector_universe(sizes, weak=()):
    """Industries of the given sizes; members of `weak` industries are worst on every sector input."""
    industry, factors, trend = {}, {}, {}
    for name, n in sizes.items():
        for i in range(n):
            code = f"{name}{i}"
            industry[code] = name
            factors[code] = dict(BASE, **(WEAK if name in weak else {}))
            trend[code] = name not in weak
    return sector_scores(list(industry), industry, factors, trend, 5)


class Pieces(unittest.TestCase):
    def test_track_split(self):
        self.assertEqual(track(sec("7000", "2020-01-02", "emerging"), 500), "watch")
        self.assertEqual(track(sec("7001", "2020-01-02", "tpex"), 119), "watch")
        self.assertEqual(track(sec("7002", "2020-01-02", "tpex"), 120), "full")
        self.assertEqual(track(sec("7003", "2020-01-02", "twse"), 120), "full")

    def test_winsorize_bounds(self):
        w = winsorize({str(i): float(i) for i in range(1, 101)}, 5, 95)
        self.assertAlmostEqual(w["1"], 5.95)
        self.assertAlmostEqual(w["100"], 95.05)
        self.assertEqual(w["50"], 50.0)

    def test_industry_z_and_clip(self):
        z = zscores({str(i): float(i) for i in range(1, 7)}, {str(i): "I" for i in range(1, 7)}, 5, 3.0)
        self.assertAlmostEqual(z["6"], 1.4639, places=4)
        vals = dict({f"z{i}": 0.0 for i in range(19)}, big=100.0)
        self.assertEqual(zscores(vals, dict.fromkeys(vals, "I"), 5, 3.0)["big"], 3.0)
        flat = zscores(dict.fromkeys("abcde", 7.0), dict.fromkeys("abcde", "I"), 5, 3.0)
        self.assertEqual(set(flat.values()), {0.0})

    def test_small_industry_uses_market_z(self):         # Review Focus 3
        vals = dict({f"a{i}": float(i) for i in range(1, 7)}, t1=10.0, t2=20.0)
        ind = dict({f"a{i}": "big" for i in range(1, 7)}, t1="tiny", t2="tiny")
        z = zscores(vals, ind, 5, 3.0)
        everything = list(vals.values())
        self.assertAlmostEqual(z["t1"], (10.0 - mean(everything)) / pstdev(everything))
        self.assertAlmostEqual(z["a6"], 1.4639, places=4)    # the big industry stays within-industry
        five = dict({f"f{i}": float(i) for i in range(1, 6)}, o1=100.0, o2=-50.0, o3=0.0, o4=9.0, o5=1.0)
        z5 = zscores(five, {k: k[0] for k in five}, 5, 3.0)
        self.assertAlmostEqual(z5["f5"], (5 - 3) / pstdev(range(1, 6)))   # exactly min_n members is enough

    def test_small_industry_never_unfavoured(self):      # Review Focus 3
        sec_ = sector_universe({"X": 5, "Y": 5, "Z": 6, "T": 4}, weak=("Z", "T"))
        self.assertEqual((sec_["T"]["n"], sec_["T"]["score"], sec_["T"]["unfavoured"]), (4, 0.0, False))
        self.assertEqual([sec_[k]["unfavoured"] for k in "XYZ"], [False, False, True])
        self.assertLess(sec_["Z"]["score"], sec_["X"]["score"])

    def test_sector_inputs(self):
        industry = dict.fromkeys(("a", "b", "c", "d"), "I")
        factors = {"a": dict(BASE, rev3=120, rev3_ly=100, rev_yoy3=20.0, ret13w=10.0),
                   "b": dict(BASE, rev3=80, rev3_ly=100, rev_yoy3=-20.0, ret13w=0.0),
                   "c": dict(BASE, rev3=None, rev3_ly=None, rev_yoy3=None, ret13w=None),
                   "d": dict(BASE, rev3=100, rev3_ly=100, rev_yoy3=0.0, ret13w=2.0)}
        out = sector_scores(list(industry), industry, factors, {"a": True, "b": False, "c": True, "d": False}, 5)
        i = out["I"]
        self.assertEqual((i["n"], i["trend_breadth"]), (4, 50.0))
        self.assertAlmostEqual(i["rev_breadth"], 100 / 3)    # 1 of the 3 members that filed is above 0
        self.assertAlmostEqual(i["rev_yoy3"], 0.0)            # 300 / 300
        self.assertAlmostEqual(i["rel_ret13"], 0.0)           # one industry: its mean is the eligible mean

    def test_composite_renormalizes(self):
        c, a = composite({"growth": 1.0, "valuation": 0.0, "quality": 0.0, "flow": None, "persistence": None}, 1.0,
                         PARAMS)
        self.assertAlmostEqual(a, 0.75)
        self.assertAlmostEqual(c, 0.8 * 0.35 / 0.75 + 0.2)

    def test_availability_below_70_is_insufficient(self):
        c, a = composite({"growth": 1.0, "valuation": 1.0, "quality": None, "flow": None, "persistence": None}, 0.0,
                         PARAMS)
        self.assertIsNone(c)
        self.assertAlmostEqual(a, 0.60)

    def test_availability_exactly_70_is_scored(self):     # 0.35 + 0.25 + 0.10 must not round below 0.70
        c, a = composite({"growth": 1.0, "valuation": 1.0, "quality": None, "flow": None, "persistence": 1.0}, 0.0,
                         PARAMS)
        self.assertAlmostEqual(c, 0.8)
        self.assertAlmostEqual(a, 0.70)


class Funnel(unittest.TestCase):
    def test_floor_excludes_group_below_minus_one(self):  # opm_ttm 1..10: z(2) ≈ −1.22, z(3) ≈ −0.87
        stocks = [S(f"Q{v}", f=dict(opm_ttm=float(v), opm_spread_4q=None, roe_ttm=None)) for v in range(1, 11)]
        rows, _ = universe(*stocks)
        self.assertAlmostEqual(rows["Q2"]["g_quality"], (2 - 5.5) / pstdev(range(1, 11)))
        self.assertEqual((rows["Q2"]["status"], rows["Q2"]["reason"]), ("excluded_floor", "quality"))
        self.assertEqual(rows["Q3"]["status"], "ranked")

    def test_valuation_member_weights(self):              # 0.67 × earnings yield + 0.33 × book yield
        rows, _ = universe(*[S(f"V{v}", f={"earnings_yield": float(v)}) for v in range(1, 11)])
        z = rows["V10"]["z_earnings_yield"]
        self.assertAlmostEqual(z, 4.5 / pstdev(range(1, 11)))
        self.assertAlmostEqual(rows["V10"]["g_valuation"], 0.67 * z)    # book-yield z is 0 for every stock

    def test_funnel_winsorizes_before_z(self):            # default 5/95 bounds clamp the lone outlier
        stocks = [S(f"W{i}", f={"opm_ttm": float(i)}) for i in range(1, 20)] + [S("W20", f={"opm_ttm": 40.0})]
        rows, _ = universe(*stocks, params=PARAMS)
        w = winsorize({f"W{i}": float(i) for i in range(1, 20)} | {"W20": 40.0}, 5, 95)
        self.assertAlmostEqual(rows["W20"]["z_opm_ttm"], (w["W20"] - mean(w.values())) / pstdev(w.values()))

    def test_exception_lane(self):                        # 20 scored → the top 5% is 1 stock
        good = [S(f"{ind}{i}", ind) for ind in "ABC" for i in range(5)]
        weak = [S("D1", "D", f=dict(WEAK, **high(10.0)), trend=False), S("D2", "D", f=dict(WEAK, **high(8.0)),
                trend=False)] + [S(f"D{i}", "D", f=dict(WEAK, **high(0.0)), trend=False) for i in range(3, 6)]
        rows, counts = universe(*good, *weak)
        self.assertTrue(counts["sectors"]["D"]["unfavoured"])
        self.assertEqual((rows["D1"]["status"], rows["D1"]["rank"], rows["D1"]["rank_trend"]), ("ranked", 1, 1))
        self.assertIn("exception_lane", rows["D1"]["flags"])
        self.assertEqual((rows["D2"]["status"], rows["D2"]["reason"]), ("excluded_sector", "D"))
        self.assertGreater(rows["D2"]["composite"], rows["A0"]["composite"])   # second market-wide, still out
        rows, _ = universe(*good, S("C5", "C"), *weak)    # 21 scored → the top 5% rounds up to 2 stocks
        self.assertEqual((rows["D2"]["status"], rows["D2"]["flags"]), ("ranked", ["exception_lane"]))

    def test_terminal_status_exactly_once(self):
        stocks = [
            S("E1", market="emerging", track="watch"), S("Y1", track="watch"),
            S("X1", tags={"altered_trading"}), S("X2", tags={"suspended", "attention"}),
            S("N1", f={"close": None}), S("L1", f={"adv20": 29_999_999.0}), S("P1", f={"close": 9.99}),
            S("F1", "金融保險業"), S("G1", "紡織纖維"), S("O1", f={"op_income_recent": 0}),
            S("U1", "B", f={k: None for k in ("opm_ttm", "opm_spread_4q", "roe_ttm", "flow20_pct", "trust_days20",
                                              "persist13")}),
            S("A0", "A", f={"opm_ttm": 0.0, "opm_spread_4q": 20.0, "roe_ttm": 0.0}),
            S("D0", "D", f=dict(WEAK, **high(10.0)), trend=False),
            S("C0", "C", tags={"disposition"}), S("C1", "C", board="tib"), S("B0", "B", f={"one_off": True}),
        ]
        stocks += [S(f"A{i}", "A") for i in range(1, 7)] + [S(f"B{i}", "B") for i in range(1, 7)]
        stocks += [S(f"C{i}", "C") for i in range(2, 8)] + [S(f"D{i}", "D", f=WEAK, trend=False) for i in range(1, 7)]
        rows, counts = universe(*stocks, non_general={"G1"})
        self.assertEqual(len(rows), 40)
        self.assertTrue(all(r["status"] in STATUSES[:11] for r in rows.values()))
        want = {"E1": "watch_track", "Y1": "watch_track", "X1": "excluded_status", "X2": "excluded_status",
                "N1": "excluded_no_quote", "L1": "excluded_liquidity", "P1": "excluded_price",
                "F1": "excluded_financial", "G1": "insufficient_data", "O1": "excluded_loss",
                "U1": "insufficient_data", "A0": "excluded_floor", "D0": "ranked", "D1": "excluded_sector",
                "C0": "ranked", "C1": "ranked", "B0": "ranked"}
        self.assertEqual({k: rows[k]["status"] for k in want}, want)
        self.assertEqual((rows["G1"]["reason"], rows["U1"]["reason"]), ("non_general_template", "availability"))
        self.assertEqual(rows["X2"]["reason"], "suspended")
        self.assertEqual((rows["C0"]["flags"], rows["C1"]["flags"], rows["B0"]["flags"], rows["X2"]["flags"]),
                         (["disposition"], ["tib"], ["one_off_revenue"], ["attention"]))
        self.assertEqual(sum(counts["statuses"].values()), 40)
        self.assertEqual(counts["statuses"], dict(dict.fromkeys(STATUSES, 0), **Counter(r["status"] for r in rows.values())))
        ranked = sorted((r for r in rows.values() if r["status"] == "ranked"), key=lambda r: r["rank"])
        self.assertEqual([r["rank"] for r in ranked], list(range(1, len(ranked) + 1)))
        self.assertEqual([r["composite"] for r in ranked], sorted((r["composite"] for r in ranked), reverse=True))
        self.assertEqual(rows["D0"]["rank_trend"], 1)        # the only trend-fail stock ranked
        self.assertEqual(sorted(r["rank_trend"] for r in ranked if r["trend_ok"]), list(range(1, len(ranked))))
        self.assertEqual({k: counts[k] for k in ("L0", "L0_full", "L0_watch", "L1", "L2", "L3", "L4")},
                         {"L0": 40, "L0_full": 38, "L0_watch": 2, "L1": 33, "L2": 30, "L3": 23, "L4": 22})

    def test_financial_excluded(self):
        rows, _ = universe(S("2801", "金融保險業"), *[S(f"A{i}") for i in range(5)])
        self.assertEqual(rows["2801"]["status"], "excluded_financial")

    def test_non_general_template_not_financial_is_insufficient(self):   # Review Focus 5
        rows, _ = universe(S("1409", "紡織纖維"), *[S(f"A{i}") for i in range(5)], non_general={"1409"})
        self.assertEqual((rows["1409"]["status"], rows["1409"]["reason"]), ("insufficient_data", "non_general_template"))

    def test_unknown_operating_income_is_insufficient(self):     # final review I2: never passed through L2
        rows, _ = universe(S("Q1", f={"op_income_recent": None}), S("Q2", f={"op_income_recent": -1}),
                           *[S(f"A{i}") for i in range(5)])
        self.assertEqual((rows["Q1"]["status"], rows["Q1"]["reason"]), ("insufficient_data", "no_income"))
        self.assertEqual(rows["Q2"]["status"], "excluded_loss")


if __name__ == "__main__":
    unittest.main()
