"""Unit tests for render.py: the weekly page, the portal card, and the README row (no network)."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from history import write_week  # noqa: E402
from render import (card_html, numbers, pages_base, readme_row, regime_label, render, upsert_card,  # noqa: E402
                    upsert_readme)
from score import PARAMS  # noqa: E402

WEEK, ASOF = "2026-w47", "2026-11-20"
SHORTLIST_PARAMS = {"enter": 20, "stay": 40, "cap": 30, "left_n": 10, "tier_a_proxy": 15.0}
EQUITY_CARD = ('<article class="artifact-card" data-category="equity" data-keywords="{code} x">\n'
               '      <a href="reports/equity/{code}.html" class="artifact-title-link">{code}</a>\n    </article>')
INDEX = ('<!doctype html>\n<main class="artifacts-grid" id="artifactsContainer">\n    {a}\n    {b}\n  </main>\n'
         .format(a=EQUITY_CARD.format(code="2330"), b=EQUITY_CARD.format(code="2308")))
README = ("# Portal\n\n## Published Deliverables\n\n| Category | Deliverable | Live Link | Local Path |\n"
          "| :--- | :--- | :--- | :--- |\n"
          "| **Equity Research** | [2330](https://user.github.io/repo/reports/equity/2330.html) | "
          "[View Online](https://user.github.io/repo/reports/equity/2330.html) | "
          "[`reports/equity/2330.html`](./reports/equity/2330.html) |\n\n## Next\n")
ROW = ("| **Equity Screen** | [台股每週選股 2026-W{w}](https://user.github.io/repo/reports/screens/tw-screen-2026-w{w}.html)"
       " | [View Online](https://user.github.io/repo/reports/screens/tw-screen-2026-w{w}.html) | "
       "[`reports/screens/tw-screen-2026-w{w}.html`](./reports/screens/tw-screen-2026-w{w}.html) |")
# 1,240 securities: five named ones plus filler, so every count ties to universe.csv
NAMED = (("2330", "台積電", "shortlist_actionable"), ("2454", "聯發科", "shortlist_actionable"),
         ("3008", "大立光", "shortlist_left_watch"), ("1101", "台泥", "excluded_floor"), ("2002", "中鋼", "watch_track"))
FILLER = (("watch_track", 200), ("excluded_liquidity", 600), ("excluded_loss", 100), ("excluded_sector", 80),
          ("ranked", 255))
STATUSES = {"watch_track": 201, "excluded_liquidity": 600, "excluded_loss": 100, "excluded_sector": 80,
            "excluded_floor": 1, "ranked": 255, "shortlist_actionable": 2, "shortlist_left_watch": 1}
COUNTS = {"L0": 1240, "L0_full": 1039, "L0_watch": 201, "L1": 439, "L2": 339, "L3": 259, "L4": 258, "L5": 3, "L6": 1}


def shortlist_row(code, name, rank, tier, proxy, flags=()):
    return {"code": code, "name": name, "industry": "半導體業", "rank": rank, "rank_trend": rank, "composite": 1.2 - rank / 10,
            "groups": {"growth": 0.8, "valuation": -0.2, "quality": 0.5, "flow": None, "persistence": 0.1},
            "flags": list(flags), "deep": None, "buy_proxy": proxy, "tier": tier,
            "command": f"/tw-equity-report {code}"}


def universe_rows():
    statuses = [status for status, n in FILLER for _ in range(n)]
    filler = [(f"{5000 + i}", f"股{i}", status) for i, status in enumerate(statuses)]
    return [{"key": f"{c}@2000-01-01", "code": c, "name": n, "market": "twse", "board": "main", "industry": "半導體業",
             "listing_date": "2000-01-01", "track": "watch" if s == "watch_track" else "full", "history_days": 300,
             "status": s, "reason": None, "flags": [], "tags": []} for c, n, s in NAMED + tuple(filler)]


def make_repo(root, week=WEEK, asof=ASOF):
    """A repo root holding index.html, README.md, the portal targets, and one render-ready week folder."""
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "reports" / "equity").mkdir(parents=True, exist_ok=True)
    for code in ("2330", "2308"):
        (root / "reports" / "equity" / f"{code}.html").write_text("x", encoding="utf-8")
    universe = universe_rows()
    funnel = {"counts": dict(COUNTS), "statuses": dict(STATUSES),
              "sectors": {"半導體業": {"n": 40, "rev_breadth": 70.0, "rev_yoy3": 12.5, "rel_ret13": -3.2,
                                    "trend_breadth": 55.0, "score": 0.42, "unfavoured": False},
                          "塑膠工業": {"n": 12, "rev_breadth": 20.0, "rev_yoy3": -8.0, "rel_ret13": -6.0,
                                   "trend_breadth": 10.0, "score": -1.1, "unfavoured": True}},
              "regime": {"close": 22000.0, "ma60": 23000.0, "ma60_slope_5d": -40.0, "ret12m": 8.0, "above_ma60": False,
                         "transition": True, "reasons": ["ma60_cross"]},
              "params": dict(PARAMS, shortlist=SHORTLIST_PARAMS),
              "forward": {"stats": [{"list": "actionable", "horizon": 4, "weeks": 2, "names": 30, "hit_rate": 56.7,
                                     "median_excess_taiex": 1.8, "median_excess_ew": -0.4, "turnover": 35.0}],
                          "buy_conversion": {"eligible": 4, "converted": 2, "rate": 50.0}}}
    shortlist = {"actionable": [shortlist_row("2330", "台積電", 1, "A", 25.0),
                                shortlist_row("2454", "聯發科", 2, "B", -4.5, ["attention"])],
                 "left_watch": [shortlist_row("3008", "大立光", 9, "B", None)], "tier_a": ["2330"]}
    diff = {"entered": [{"code": "2454", "list": "actionable", "rank": 2}],
            "exited": [{"code": "1101", "list": "actionable", "reason": "excluded_floor"}],
            "rank_delta": {"2330": 2, "2454": 0, "3008": -3}, "streak": {"2330": 3, "2454": 1, "3008": 1},
            "composite_delta": {"2330": 0.15}, "reports": {}}
    events = {"new": ["7777@2026-11-18"], "exits": [], "transfers": [{"code": "8908", "from": "tpex", "to": "twse"}],
              "renames": [], "code_reuse": [], "status_changes": [{"code": "2454", "added": ["attention"], "removed": []}],
              "reconciliation": {"not_in_finmind": [], "not_quoted": [], "finmind_stale": []}}
    watch = {"upcoming": [{"code": "7799", "name": "新創", "market": "tpex", "applied": "2026-10-01",
                           "listing_date": "2026-12-01", "price": 50.0}],
             "recent": [{"code": "2002", "name": "中鋼", "market": "twse", "listing_date": "2026-07-01", "history_days": 80,
                         "days_to_full": 40, "first_five": None}],
             "emerging": [{"code": "7701", "name": "興櫃甲", "industry": "生技醫療業", "latest_period": "2026-10",
                           "rev_yoy_med6": 35.0, "last3_yoy": [30.0, 40.0, 20.0], "avg": 30.0, "last": 31.0,
                           "volume": 5000.0, "applying_status": "申請上櫃"}]}
    scores = [{"key": r["key"], "code": r["code"], "industry": r["industry"], "composite": 1.0, "rank": 1,
               "rank_trend": 1, "trend_ok": True, "list": "actionable"} for r in universe[:3]]
    folder = write_week(root, week, {"universe.csv": universe, "scores.csv": scores, "events.json": events,
                                     "funnel.json": funnel, "shortlist.json": shortlist, "watch.json": watch,
                                     "diff.json": diff}, asof)
    review = {"generation": {"model": "claude-opus-5-5", "effort": "high"}, "notes": {"2330": "營收連續創高"},
              "events_zh": "本週新增一檔上櫃。"}
    (folder / "review.json").write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    return folder


def render_week_without_recent(root):
    """Re-render the fixture week with an empty recent-listings table; return the page text."""
    watch = root / "scripts" / "screens" / WEEK / "watch.json"
    obj = json.loads(watch.read_text(encoding="utf-8"))
    obj["recent"] = []
    watch.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return render(watch.parent, root).read_text(encoding="utf-8")


class Portal(unittest.TestCase):
    SUMMARY = {"week": WEEK, "asof": ASOF, "counts": {"L0": 1, "L0_full": 1, "L5": 1, "L6": 0}, "tier_a": [],
               "regime": {"above_ma60": True, "transition": False}, "generation": {"model": "m", "effort": "e"}}

    def test_card_replaced_not_duplicated(self):          # Review Focus 4
        once = upsert_card(INDEX, card_html(self.SUMMARY))
        twice = upsert_card(once, card_html(dict(self.SUMMARY, counts={"L0": 2, "L0_full": 2, "L5": 2, "L6": 0})))
        self.assertEqual(twice.count('data-keywords="tw-equity-screener'), 1)
        self.assertEqual(twice.count('<article class="artifact-card"'), 3)
        self.assertIn("入圍：<span class=\"telemetry-val tone-accent\">2 檔", twice)

    def test_duplicate_cards_collapse_to_one(self):
        card = card_html(self.SUMMARY)
        doubled = INDEX.replace("<main class=\"artifacts-grid\" id=\"artifactsContainer\">\n",
                                "<main class=\"artifacts-grid\" id=\"artifactsContainer\">\n    " + card + "\n    " + card
                                + "\n", 1)
        self.assertEqual(upsert_card(doubled, card).count('data-keywords="tw-equity-screener'), 1)

    def test_card_inserted_first_when_absent(self):
        s = dict(self.SUMMARY, counts={"L0": 1, "L0_full": 1, "L5": 1, "L6": 1}, tier_a=["2330"],
                 regime={"above_ma60": None, "transition": None})
        out = upsert_card(INDEX, card_html(s))
        first = re.search(r'<article class="artifact-card"[^>]*>', out).group(0)
        self.assertIn('data-keywords="tw-equity-screener 選股 weekly screen', first)
        self.assertLess(out.index('<main class="artifacts-grid"'), out.index('data-keywords="tw-equity-screener'))
        self.assertIn("artifact-badge--active", out)
        self.assertIn("Tier A 1 檔：2330", out)

    def test_card_badge_neutral_without_tier_a(self):
        card = card_html(self.SUMMARY)
        self.assertIn('artifact-badge artifact-badge--neutral">本週 Tier A：0 檔', card)
        self.assertIn('<a href="reports/screens/tw-screen-2026-w47.html" class="artifact-title-link">台股每週選股 2026 第 47 週',
                      card)

    def test_readme_row_replaced(self):
        old = README.replace("| **Equity Research**", ROW.format(w="46") + "\n| **Equity Research**", 1)
        new = upsert_readme(old, ROW.format(w="47"))
        self.assertEqual(new.count("\n|"), old.count("\n|"))
        self.assertIn("tw-screen-2026-w47.html", new)
        self.assertNotIn("tw-screen-2026-w46.html", new)

    def test_readme_rows_collapse_to_one(self):
        old = README.replace("| **Equity Research**",
                             ROW.format(w="45") + "\n" + ROW.format(w="46") + "\n| **Equity Research**", 1)
        new = upsert_readme(old, ROW.format(w="47"))
        self.assertEqual([ln for ln in new.splitlines() if "reports/screens/" in ln], [ROW.format(w="47")])

    def test_readme_row_pads_the_week(self):
        url = "https://u.github.io/r/reports/screens/tw-screen-2026-w05.html"
        self.assertEqual(readme_row("2026-w05", "https://u.github.io/r/"),
                         f"| **Equity Screen** | [台股每週選股 2026-W05]({url}) | [View Online]({url}) | "
                         "[`reports/screens/tw-screen-2026-w05.html`](./reports/screens/tw-screen-2026-w05.html) |")

    def test_readme_row_inserted_first_when_absent(self):
        new = upsert_readme(README, ROW.format(w="47"))
        rows = [ln for ln in new.splitlines() if ln.startswith("| **")]
        self.assertEqual((len(rows), rows[0]), (2, ROW.format(w="47")))

    def test_readme_without_table_raises(self):
        with self.assertRaises(ValueError):
            upsert_readme("# Portal\n", ROW.format(w="47"))

    def test_pages_base(self):
        self.assertEqual(pages_base("[View Online](https://user.github.io/repo/reports/x.html)"),
                         "https://user.github.io/repo/")


class Labels(unittest.TestCase):
    def test_regime_label(self):
        self.assertEqual(regime_label({"above_ma60": False, "transition": True}), "跌破季線（轉折）")
        self.assertEqual(regime_label({"above_ma60": True, "transition": False}), "站上季線")
        self.assertEqual(regime_label({"above_ma60": None, "transition": None}), "資料不足")
        self.assertEqual(regime_label(None), "資料不足")

    def test_numbers_come_from_params(self):
        n = numbers(dict(PARAMS, shortlist=SHORTLIST_PARAMS))
        self.assertEqual((n["availability_pct"], n["unfavoured_pct"], n["tier_a_proxy"], n["floor_z"], n["mix"]),
                         ("70%", "33%", "15", "-1", ("0.8", "0.2")))
        self.assertEqual((n["adv20_m"], n["close_min"], n["exception_pct"], n["enter"]), ("30", "10", "5%", 20))


class Page(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        screens = self.root / "reports" / "screens"
        screens.mkdir(parents=True)
        for w in ("46", "48"):
            (screens / f"tw-screen-2026-w{w}.html").write_text("old", encoding="utf-8")
        self.page = render(make_repo(self.root), self.root)
        self.text = self.page.read_text(encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_page_sections_and_hooks(self):
        self.assertEqual(self.page.name, "tw-screen-2026-w47.html")
        for sec in ("summary", "tier-a", "shortlist", "changes", "sectors", "funnel", "watch", "forward", "method"):
            self.assertIn(f'<section id="{sec}"', self.text)
        self.assertRegex(self.text, r'data-kpi="universe"[^>]*>1,240<')
        self.assertRegex(self.text, r'data-kpi="regime"[^>]*>跌破季線（轉折）<')
        self.assertRegex(self.text, r'data-layer="L6"[^>]*>1<')
        self.assertRegex(self.text, r'<tr data-code="2330">[\s\S]*?<code>/tw-equity-report 2330</code>')
        self.assertRegex(self.text, r'data-dir="up"[^>]*>\+25\.0%<')
        self.assertRegex(self.text, r'data-dir="down"[^>]*>-3<')
        self.assertIn("營收連續創高", self.text)
        self.assertIn("本週新增一檔上櫃。", self.text)

    def test_earlier_weeks_only(self):
        self.assertIn('href="tw-screen-2026-w46.html"', self.text)
        self.assertNotIn('href="tw-screen-2026-w48.html"', self.text)

    def test_method_numbers_follow_params(self):
        self.assertIn("BUY 代理值高於 15%", self.text)
        self.assertIn("可用權重低於 70% 不評分", self.text)
        self.assertIn("成長 35%、評價 25%、品質 15%、籌碼 15%、持續 10%", self.text)
        self.assertIn("上市櫃且有 120 個交易日以上股價", self.text)
        self.assertIn("沒有交易日不足 120 日", render_week_without_recent(self.root))

    def test_forward_leads_with_buy_conversion(self):
        forward = re.search(r'<section id="forward">(.*?)</section>', self.text, re.S).group(1)
        self.assertLess(forward.index("BUY 轉換率"), forward.index("勝率"))
        self.assertIn(">50.0%<", forward)

    def test_portal_files_updated(self):
        index = (self.root / "index.html").read_text(encoding="utf-8")
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn('href="reports/screens/tw-screen-2026-w47.html"', index)
        self.assertIn("https://user.github.io/repo/reports/screens/tw-screen-2026-w47.html", readme)

    def test_render_requires_every_week_file(self):
        (self.root / "scripts" / "screens" / WEEK / "diff.json").unlink()
        with self.assertRaises(FileNotFoundError):
            render(self.root / "scripts" / "screens" / WEEK, self.root)

    def test_crlf_index_keeps_crlf(self):
        index = self.root / "index.html"
        index.write_bytes(INDEX.replace("\n", "\r\n").encode("utf-8"))
        render(self.root / "scripts" / "screens" / WEEK, self.root)
        raw = index.read_bytes().decode("utf-8")
        self.assertNotIn("\n", raw.replace("\r\n", ""))
        self.assertEqual(raw.count('data-keywords="tw-equity-screener'), 1)


if __name__ == "__main__":
    unittest.main()
