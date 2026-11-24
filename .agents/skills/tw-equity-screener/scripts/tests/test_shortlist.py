"""Unit tests for shortlist.py: hysteresis selection, deep metrics cache, BUY proxy, and tiers (no network)."""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import NotPublishedError, QuotaError  # noqa: E402
from shortlist import DEEP_FIELDS, buy_proxy, deep_metrics, select, tier  # noqa: E402

BUILD = {"gaps": ["g1"], "price": {"metrics": {"close": 120.0}},
         "valuation": {"PER": {"p50": 15.0, "current_percentile": 40.0}, "PBR": {"current_percentile": 55.0}},
         "financials": {"core_baseline": {"ntm_eps": 10.0, "applicable": True, "high_volatility": False},
                        "cash_conversion": 0.9},
         "institutional": {"cost_zone": {"low": 100.0, "high": 110.0}}}


def rows(passing=(), failing=()):
    """Ranked rows: trend-pass codes get rank_trend 1, 2, … in order, and trend-fail codes likewise."""
    out = [{"code": c, "trend_ok": True, "rank_trend": i} for i, c in enumerate(passing, 1)]
    return out + [{"code": c, "trend_ok": False, "rank_trend": i} for i, c in enumerate(failing, 1)]


def with_code_at(code, rank, n=45):
    names = [f"P{i}" for i in range(1, n + 1)]
    names[rank - 1] = code
    return names


class Select(unittest.TestCase):
    def test_incumbent_stays_within_40(self):
        self.assertIn("B", select(rows(with_code_at("B", 35)), {"B"})[0])
        self.assertNotIn("C", select(rows(with_code_at("C", 25)), {"B"})[0])
        self.assertNotIn("B", select(rows(with_code_at("B", 41)), {"B"})[0])
        self.assertIn("B", select(rows(with_code_at("B", 40)), {"B"})[0])     # the stay bound is inclusive

    def test_entrants_are_top_20(self):
        actionable, _ = select(rows(with_code_at("X", 21)), set())
        self.assertEqual(actionable, [f"P{i}" for i in range(1, 21)])

    def test_incumbent_failing_trend_leaves_actionable(self):
        actionable, left = select(rows(passing=["P1"], failing=["B"]), {"B"})
        self.assertEqual((actionable, left), (["P1"], ["B"]))

    def test_cap_30_keeps_best_ranks(self):
        prev = {f"P{i}" for i in range(21, 36)}
        actionable, _ = select(rows([f"P{i}" for i in range(1, 46)]), prev)
        self.assertEqual(actionable, [f"P{i}" for i in range(1, 31)])

    def test_order_follows_rank_not_input(self):
        r = rows([f"P{i}" for i in range(1, 6)])[::-1]
        self.assertEqual(select(r, set())[0], [f"P{i}" for i in range(1, 6)])

    def test_left_watch_top_10(self):
        _, left = select(rows(passing=["A"], failing=[f"F{i}" for i in range(1, 16)])[::-1], set())
        self.assertEqual(left, [f"F{i}" for i in range(1, 11)])


class Proxy(unittest.TestCase):
    def test_buy_proxy(self):
        self.assertAlmostEqual(buy_proxy({"cb_applicable": True, "ntm_eps": 10, "per_p50": 15, "close": 120}), 25.0)

    def test_buy_proxy_none_when_not_applicable(self):
        dm = {"cb_applicable": True, "ntm_eps": 10, "per_p50": 15, "close": 120}
        for change in ({"cb_applicable": False}, {"ntm_eps": -1}, {"per_p50": 0}, {"close": None}, {"ntm_eps": None}):
            self.assertIsNone(buy_proxy(dict(dm, **change)), change)

    def test_tier_rules(self):
        self.assertEqual(tier("actionable", True, set(), 16.0), "A")
        self.assertEqual(tier("actionable", True, set(), 15.0), "B")
        self.assertEqual(tier("actionable", True, {"attention"}, 30.0), "B")
        self.assertEqual(tier("left_watch", False, set(), 30.0), "B")
        self.assertEqual(tier("actionable", False, set(), 30.0), "B")
        self.assertEqual(tier("actionable", True, set(), None), "B")
        self.assertEqual(tier("actionable", True, {"tib", "cash_offering", "exception_lane"}, 30.0), "A")
        for flag in ("disposition", "periodic_auction", "one_off_revenue"):
            self.assertEqual(tier("actionable", True, {flag}, 30.0), "B", flag)


class Deep(unittest.TestCase):
    def test_deep_metrics_cached(self):
        calls = []

        def build(code, peers, asof):
            calls.append((code, peers, asof))
            return BUILD

        with tempfile.TemporaryDirectory() as tmp:
            first = deep_metrics("2330", "2026-11-20", Path(tmp), build=build)
            second = deep_metrics("2330", "2026-11-20", Path(tmp), build=build)
            path = Path(tmp) / "finmind" / "2026-11-20" / "2330.json"
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), BUILD)
        self.assertEqual(calls, [("2330", [], "2026-11-20")])
        self.assertEqual(first, second)
        self.assertEqual(first, {"close": 120.0, "per_p50": 15.0, "per_pct": 40.0, "pbr_pct": 55.0, "ntm_eps": 10.0,
                                 "cb_applicable": True, "cb_high_vol": False, "cash_conversion": 0.9,
                                 "cost_zone": {"low": 100.0, "high": 110.0}, "gaps": ["g1"]})

    def test_deep_metrics_missing_sections_are_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            dm = deep_metrics("1101", "2026-11-20", Path(tmp), build=lambda c, p, a: {"gaps": [], "valuation": None})
        self.assertEqual((dm["per_p50"], dm["ntm_eps"], dm["cb_applicable"], dm["gaps"]), (None, None, None, []))

    def test_quota_error_propagates_and_caches_nothing(self):
        def build(code, peers, asof):
            raise QuotaError("quota")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(QuotaError):
                deep_metrics("2330", "2026-11-20", Path(tmp), build=build)
            self.assertFalse((Path(tmp) / "finmind" / "2026-11-20" / "2330.json").exists())

    def test_build_behind_asof_is_not_published(self):     # final review I3: FinMind has not added asof yet
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NotPublishedError) as caught:
                deep_metrics("2330", "2026-11-20", Path(tmp), build=lambda c, p, a: dict(BUILD, asof="2026-11-19"))
            self.assertFalse((Path(tmp) / "finmind").exists())
            dm = deep_metrics("2330", "2026-11-20", Path(tmp), build=lambda c, p, a: dict(BUILD, asof="2026-11-20"))
        self.assertIn("2026-11-19", str(caught.exception))
        self.assertEqual(dm["close"], 120.0)

    def test_failed_build_gives_empty_metrics_uncached(self):     # final review I5: one name never stops the week
        def build(code, peers, asof):
            raise IndexError("list index out of range")

        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            dm = deep_metrics("2330", "2026-11-20", Path(tmp), build=build)
            self.assertFalse((Path(tmp) / "finmind").exists())
        self.assertEqual(dm, dict(dict.fromkeys(DEEP_FIELDS),
                                  gaps=["deep metrics unavailable: IndexError: list index out of range"]))
        self.assertIsNone(buy_proxy(dm))
        self.assertIn("deep metrics unavailable for 2330", out.getvalue())

    def test_network_and_unpublished_errors_propagate(self):     # a rerun resumes from the cache
        for error in (urllib.error.URLError("down"), ConnectionResetError("reset"), NotPublishedError("W20")):
            def build(code, peers, asof, error=error):
                raise error

            with tempfile.TemporaryDirectory() as tmp, self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    deep_metrics("2330", "2026-11-20", Path(tmp), build=build)


if __name__ == "__main__":
    unittest.main()
