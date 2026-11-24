"""Unit tests for history.py: week folders, diff, tag changes, invariants, forward tracking (no network)."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from history import (append_forward, buy_conversion, check_invariants, diff, forward_stats, previous_week,  # noqa: E402
                     read_week, report_index, status_changes, tags_from_universe, week_id, write_week)

REPORT = '<p>評等 <strong data-kpi="rating">{rating}</strong>（Buy）</p><span data-kpi="action">{action}</span>'


def bundle(actionable, scores, universe=None, left=(), streak=None):
    """A week as diff() reads it: shortlist lists, scores rows, universe rows, and last week's diff."""
    return {"shortlist": {"actionable": [{"code": c} for c in actionable], "left_watch": [{"code": c} for c in left]},
            "scores": [{"code": c, "rank": r, "trend_ok": t, "composite": x} for c, r, t, x in scores],
            "universe": [{"code": c, "status": s} for c, s in (universe or [(c, "ranked") for c, *_ in scores])],
            "diff": {"streak": streak or {}}}


class Weeks(unittest.TestCase):
    def test_week_id(self):
        self.assertEqual((week_id("2026-11-20"), week_id("2027-01-01")), ("2026-w47", "2026-w53"))

    def test_write_week_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_week(root, "2026-w47", {"funnel.json": {"counts": {"L0": 1}}, "old.json": {}}, "2026-11-20")
            folder = write_week(root, "2026-w47", {"funnel.json": {"counts": {"L0": 2}},
                                                   "universe.csv": [{"key": "0050@2003-06-30", "code": "0050",
                                                                     "flags": ["tib", "attention"]}]}, "2026-11-20")
            self.assertEqual(folder, root / "scripts" / "screens" / "2026-w47")
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["funnel.json", "universe.csv"])
            funnel = json.loads((folder / "funnel.json").read_text(encoding="utf-8"))
            self.assertEqual(funnel, {"asof": "2026-11-20", "week": "2026-w47", "methodology_version": "1.0",
                                      "counts": {"L0": 2}})
            with open(folder / "universe.csv", encoding="utf-8", newline="") as f:
                self.assertEqual(list(csv.reader(f)), [["asof", "week", "methodology_version", "key", "code", "flags"],
                                                       ["2026-11-20", "2026-w47", "1.0", "0050@2003-06-30", "0050",
                                                        "attention;tib"]])
            week = read_week(root, "2026-w47")
            self.assertEqual((week["universe"][0]["code"], week["universe"][0]["flags"]), ("0050", ["attention", "tib"]))
            self.assertIsNone(read_week(root, "2026-w40"))

    def test_read_week_types_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_week(Path(tmp), "2026-w47", {"scores.csv": [{"code": "2330", "z_opm_ttm": 1.25, "rank": 3,
                                                               "rank_trend": None, "trend_ok": False, "list": ""}]},
                       "2026-11-20")
            row = read_week(Path(tmp), "2026-w47")["scores"][0]
        self.assertEqual((row["code"], row["z_opm_ttm"], row["rank"], row["rank_trend"], row["trend_ok"], row["list"]),
                         ("2330", 1.25, 3, None, False, None))

    def test_previous_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            screens = Path(tmp) / "scripts" / "screens"
            for name in ("2026-w45", "2026-w46", "2026-w48", "notes"):
                (screens / name).mkdir(parents=True)
            self.assertEqual(previous_week(Path(tmp), "2026-w48"), "2026-w46")
            self.assertIsNone(previous_week(Path(tmp), "2026-w45"))


class Changes(unittest.TestCase):
    def test_status_changes(self):
        self.assertEqual(status_changes({"A": {"attention"}}, {"A": {"disposition"}, "B": set()}),
                         [{"code": "A", "added": ["disposition"], "removed": ["attention"]}])
        self.assertEqual(status_changes(None, {"A": {"attention"}}), [])
        self.assertEqual(status_changes({"A": {"tib", "attention"}}, {"A": {"attention", "exception_lane"}}), [])
        self.assertEqual(status_changes({"Z": {"suspended"}}, {}), [{"code": "Z", "added": [], "removed": ["suspended"]}])

    def test_tags_from_universe(self):
        rows = [{"code": "A", "status": "excluded_status", "reason": "managed,suspended", "flags": ["attention"]},
                {"code": "B", "status": "ranked", "reason": None, "flags": ["tib", "exception_lane"]},
                {"code": "C", "status": "watch_track", "reason": None, "flags": [], "tags": ["suspended"]}]
        self.assertEqual(tags_from_universe(rows), {"A": {"attention", "managed", "suspended"}, "B": set(),
                                                    "C": {"suspended"}})

    def test_invariants(self):
        self.assertEqual(check_invariants(10, {"ranked": 6, "watch_track": 4}, 9, {"new": ["a"], "exits": []}), [])
        self.assertEqual(len(check_invariants(10, {"ranked": 6}, 9, {"new": [], "exits": []})), 2)
        self.assertEqual(check_invariants(10, {"ranked": 10}, None, {"new": [], "exits": []}), [])

    def test_diff_entries_exits_streak(self):
        prev = bundle(["A", "B"], [("A", 3, True, 1.0), ("B", 5, True, 0.9), ("C", 30, True, 0.1)],
                      streak={"A": 2, "B": 1})
        cur = bundle(["A", "C"], [("A", 1, True, 1.5), ("C", 2, True, 1.2), ("B", 4, False, 1.1)])
        d = diff(prev, cur, {"A": {"path": "reports/equity/a.html"}})
        self.assertEqual(d["entered"], [{"code": "C", "list": "actionable", "rank": 2}])
        self.assertEqual(d["exited"], [{"code": "B", "list": "actionable", "reason": "trend_failed"}])
        self.assertEqual((d["rank_delta"], d["streak"]), ({"A": 2, "C": 28}, {"A": 3, "C": 1}))
        self.assertAlmostEqual(d["composite_delta"]["A"], 0.5)
        self.assertEqual(d["reports"], {"A": {"path": "reports/equity/a.html"}})

    def test_diff_exit_reasons(self):
        prev = bundle(["A", "B", "C", "D"], [("A", 1, True, 1), ("B", 2, True, 1), ("C", 3, True, 1), ("D", 4, True, 1)],
                      left=["E"])
        prev["scores"].append({"code": "E", "rank": 9, "trend_ok": False, "composite": 0.5})
        cur = bundle([], [("A", 45, True, 0.1), ("E", 9, True, 0.5)],
                     universe=[("A", "ranked"), ("B", "excluded_floor"), ("C", "watch_track"), ("E", "ranked")])
        reasons = {(x["code"], x["list"]): x["reason"] for x in diff(prev, cur, {})["exited"]}
        self.assertEqual(reasons, {("A", "actionable"): "rank_out", ("B", "actionable"): "excluded_floor",
                                   ("C", "actionable"): "watch_track", ("D", "actionable"): "delisted",
                                   ("E", "left_watch"): "trend_passed"})

    def test_diff_first_week(self):
        d = diff(None, bundle(["A"], [("A", 1, True, 1.0)], left=["B"]), {})
        self.assertEqual((d["entered"], d["exited"], d["streak"], d["rank_delta"]),
                         ([{"code": "A", "list": "actionable", "rank": 1}, {"code": "B", "list": "left_watch",
                                                                             "rank": None}], [], {"A": 1, "B": 1}, {}))

    def test_report_index_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            eq = Path(tmp) / "reports" / "equity"
            eq.mkdir(parents=True)
            (eq / "2330-tsmc-20261109.html").write_text(REPORT.format(rating="中立", action="觀望"), encoding="utf-8")
            (eq / "2330-tsmc-20261120.html").write_text(REPORT.format(rating="買進", action="可分批布局"),
                                                        encoding="utf-8")
            (eq / "2501-cathay-real-estate.html").write_text(REPORT.format(rating="買進", action="x"), encoding="utf-8")
            (eq / "6834-ever-ohms-20261112.html").write_text("<p>no kpi</p>", encoding="utf-8")
            idx = report_index(Path(tmp))
        self.assertEqual(sorted(idx), ["2330", "6834"])
        self.assertEqual(idx["2330"], {"path": "reports/equity/2330-tsmc-20261120.html", "date": "2026-11-20",
                                       "rating": "買進", "action": "可分批布局"})
        self.assertEqual((idx["6834"]["rating"], idx["6834"]["action"]), (None, None))


class Forward(unittest.TestCase):
    def test_forward_rows_idempotent(self):              # Review Focus 4
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forward.csv"
            append_forward(path, "2026-w46", "2026-11-13", [{"list": "actionable", "code": "A", "close": 10.0}])
            for _ in range(2):
                append_forward(path, "2026-w47", "2026-11-20", [{"list": "actionable", "code": "B", "close": 20.0},
                                                                {"list": "tier_a", "code": "B", "close": 20.0}])
            with open(path, encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows, [["week", "asof", "list", "code", "close"],
                                ["2026-w46", "2026-11-13", "actionable", "A", "10.0"],
                                ["2026-w47", "2026-11-20", "actionable", "B", "20.0"],
                                ["2026-w47", "2026-11-20", "tier_a", "B", "20.0"]])

    def test_forward_stats_hit_rate(self):
        rows = [{"week": "2026-w40", "asof": "2026-10-02", "list": "actionable", "code": c, "close": "100"}
                for c in ("A", "B")]
        rows.append({"week": "2026-w44", "asof": "2026-10-30", "list": "actionable", "code": "A", "close": "110"})
        later = {"A": 110.0, "B": 95.0}
        stats = forward_stats(rows, lambda code, d: later[code], lambda d: 1000.0, lambda week, d: 1.0)
        self.assertEqual(len(stats), 1)                  # only w40's 4-week horizon has elapsed by 2026-10-30
        s = stats[0]
        self.assertEqual((s["list"], s["horizon"], s["weeks"], s["names"]), ("actionable", 4, 1, 2))
        self.assertEqual(s["hit_rate"], 50.0)
        self.assertAlmostEqual(s["median_excess_taiex"], 2.5)
        self.assertAlmostEqual(s["median_excess_ew"], 1.5)
        self.assertEqual(s["turnover"], 50.0)            # B left between w40 and w44

    def test_forward_stats_tie_is_not_a_hit(self):       # "beating the TAIEX" is strict
        rows = [{"week": "2026-w40", "asof": "2026-10-02", "list": "tier_a", "code": "A", "close": "100"},
                {"week": "2026-w44", "asof": "2026-10-30", "list": "tier_a", "code": "A", "close": "100"}]
        s = forward_stats(rows, lambda code, d: 100.0, lambda d: 1000.0, lambda week, d: None)[0]
        self.assertEqual((s["list"], s["hit_rate"], s["median_excess_ew"], s["turnover"]), ("tier_a", 0.0, None, 0.0))

    def test_buy_conversion_rate(self):
        rows = [{"week": "2026-w40", "asof": "2026-10-02", "list": "tier_a", "code": c, "close": "1"}
                for c in ("A", "B", "C", "D", "E", "F")]
        rows.append({"week": "2026-w40", "asof": "2026-10-02", "list": "actionable", "code": "G", "close": "1"})
        reports = {"A": {"date": "2026-10-05", "rating": "買進", "action": "可分批布局"},
                   "B": {"date": "2026-10-02", "rating": "買進", "action": "分批買進"},
                   "C": {"date": "2026-10-09", "rating": "買進", "action": "左側觀察"},
                   "D": {"date": "2026-10-09", "rating": "中立", "action": "觀望"},
                   "E": {"date": "2026-09-30", "rating": "買進", "action": "可分批布局"},
                   "G": {"date": "2026-10-09", "rating": "買進", "action": "可分批布局"}}
        self.assertEqual(buy_conversion(rows, reports), {"eligible": 4, "converted": 2, "rate": 50.0})
        self.assertEqual(buy_conversion([], {}), {"eligible": 0, "converted": 0, "rate": None})


if __name__ == "__main__":
    unittest.main()
