"""Unit tests for check_screen.py against a rendered synthetic week (no network)."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_screen import DISCLAIMER, main  # noqa: E402
from history import screens_dir, write_week  # noqa: E402
from render import render  # noqa: E402
from test_render import ROW, WEEK, make_repo, universe_rows  # noqa: E402

PAGE = f"reports/screens/tw-screen-{WEEK}.html"

# (old, new, a fragment the FAIL lines must hold); each edit is applied once to a fresh copy
PAGE_EDITS = [
    ('data-kpi="universe">1,240<', 'data-kpi="universe">1,241<', "data-kpi=universe"),
    ('data-kpi="regime">跌破季線（轉折）<', 'data-kpi="regime">站上季線<', "data-kpi=regime"),
    ('data-layer="L3">259<', 'data-layer="L3">260<', "data-layer=L3"),
    ('data-dir="up">+25.0%<', 'data-dir="down">+25.0%<', "wrong data-dir: down +25.0%"),
    ('data-dir="flat">0<', 'data-dir="red">0<', "wrong data-dir: red 0"),
    ('<section id="watch"', '<section id="watch2"', "section #watch missing"),
    ('aria-label="往期週報"', 'aria-label="x"', "earlier-weeks nav"),
    ('data-code="2330"', 'data-code="2331"', "Tier A rows ['2331']"),
    ('<code>/tw-equity-report 2330</code>', '<code>/tw-equity-report</code>', "2330 lacks its report command"),
    ('--tw-down: oklch(72% 0.14 150)', '--tw-dn: oklch(72% 0.14 150)',
     "--tw-down not declared in prefers-color-scheme: dark"),
    ('--tw-up: oklch(53% 0.19 33)', '--tw-up: oklch(53% 0.19 250)', "is not an oklch red"),
    ('color: var(--tw-flat)', 'color: var(--color-muted)', "no rule uses var(--tw-flat)"),
    ('<meta name="viewport"', '<meta name="vp"', "viewport meta"),
    ('html, body { overflow-x: clip; }', 'html, body { overflow-x: hidden; }', "overflow-x: clip"),
    (DISCLAIMER, "x", "footer lacks"),
    ('<span data-meta="model">claude-opus-5-5</span>', '<span data-meta="model">x</span>', "footer data-meta=model"),
    ('href="#tier-a"', 'href="#tier-x"', "missing ids: tier-x"),
    ('href="../../index.html"', 'href="../../missing.html"', "page link ../../missing.html does not exist"),
]

# (file, edit of the parsed JSON, fragment); stamps stay intact
JSON_EDITS = [
    ("funnel.json", lambda f: f["statuses"].update(ranked=1), "statuses sum to 986, master has 1240"),
    ("funnel.json", lambda f: f["statuses"].update(excluded_liquidity=599, excluded_price=1),
     "statuses differ from the universe.csv"),
    ("funnel.json", lambda f: f["counts"].pop("L6"), "counts lack L6"),
    ("funnel.json", lambda f: f["counts"].update(L0=1241, L0_full=1040), "universe.csv has 1240 rows"),
    ("funnel.json", lambda f: f["counts"].update(L0_full=1038), "L0 is not L0_full + L0_watch"),
    ("funnel.json", lambda f: f["statuses"].update(watch_track=200, excluded_liquidity=601), "L0_watch differs"),
    ("funnel.json", lambda f: f["counts"].update(L3=340), "the funnel widens"),
    ("funnel.json", lambda f: f["counts"].update(L5=4), "L5 is 4"),
    ("funnel.json", lambda f: f["counts"].update(L4=257), "L4 is not ranked plus the shortlist"),
    ("shortlist.json", lambda s: s.update(tier_a=[]), "L6 is 1, shortlist.json has 0"),
    ("shortlist.json", lambda s: s.update(tier_a=["3008"]), "not on the actionable list"),
    ("watch.json", lambda w: w.update(asof="2026-11-19"), "files disagree"),
    ("review.json", lambda r: r["generation"].update(model=""), "generation.model is empty"),
]

INDEX_EDITS = [
    ('入圍：<span class="telemetry-val tone-accent">3 檔', '入圍：<span class="telemetry-val tone-accent">4 檔',
     "card 入圍 shows '4 檔'"),
    ('<span class="artifact-date">2026-11-20</span>', '<span class="artifact-date">2026-11-19</span>', "card date"),
    ('本週 Tier A：1 檔', '本週 Tier A：2 檔', "card badge"),
    ('data-meta="effort">high<', 'data-meta="effort">low<', "card data-meta=effort"),
    ('href="reports/screens/tw-screen-2026-w47.html" class="artifact-title-link"',
     'href="reports/screens/tw-screen-2026-w46.html" class="artifact-title-link"',
     "card link reports/screens/tw-screen-2026-w46.html does not exist"),
]


def run_check(root, folder=None):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main([str(folder or screens_dir(root) / WEEK), "--root", str(root)])
    return code, out.getvalue()


def failures(out):
    return "\n".join(ln for ln in out.splitlines() if ln.startswith("FAIL "))


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError(f"{path.name} lacks {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")


def edit_json(path, fn):
    obj = json.loads(path.read_text(encoding="utf-8"))
    fn(obj)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class CheckScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.template = Path(cls.tmp.name) / "template"
        cls.template.mkdir()
        render(make_repo(cls.template), cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fresh(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.template, root, dirs_exist_ok=True)
        return root

    def assertFails(self, root, fragment, folder=None):
        code, out = run_check(root, folder)
        self.assertEqual(code, 1, out)
        self.assertIn(fragment, failures(out))

    def test_check_passes_on_rendered_week(self):
        code, out = run_check(self.fresh())
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)
        self.assertTrue(out.strip().splitlines()[-1].startswith("PASS"))

    def test_check_passes_after_same_week_rerender(self):    # Review Focus 4
        root = self.fresh()
        render(screens_dir(root) / WEEK, root)
        self.assertEqual(run_check(root)[0], 0)

    def test_check_fails_on_kpi_mismatch(self):
        root = self.fresh()
        edit(root / PAGE, 'data-kpi="universe">1,240<', 'data-kpi="universe">1,241<')
        self.assertFails(root, "data-kpi=universe")

    def test_check_fails_on_wrong_dir(self):
        root = self.fresh()
        edit(root / PAGE, 'data-dir="up">+25.0%<', 'data-dir="down">+25.0%<')
        self.assertFails(root, "wrong data-dir")

    def test_page_edits_fail(self):
        for old, new, fragment in PAGE_EDITS:
            with self.subTest(fragment=fragment):
                root = self.fresh()
                edit(root / PAGE, old, new)
                self.assertFails(root, fragment)

    def test_week_file_edits_fail(self):
        for name, fn, fragment in JSON_EDITS:
            with self.subTest(fragment=fragment):
                root = self.fresh()
                edit_json(screens_dir(root) / WEEK / name, fn)
                self.assertFails(root, fragment)

    def test_portal_edits_fail(self):
        for old, new, fragment in INDEX_EDITS:
            with self.subTest(fragment=fragment):
                root = self.fresh()
                edit(root / "index.html", old, new)
                self.assertFails(root, fragment)

    def test_card_must_link_this_week(self):
        root = self.fresh()
        index = root / "index.html"
        index.write_text(index.read_text(encoding="utf-8").replace("tw-screen-2026-w47.html", "tw-screen-2026-w46.html"),
                         encoding="utf-8")
        (root / "reports" / "screens" / "tw-screen-2026-w46.html").write_text("old", encoding="utf-8")
        self.assertFails(root, "does not link reports/screens/tw-screen-2026-w47.html")

    def test_css_selector_does_not_stand_in_for_a_hook(self):
        root = self.fresh()
        edit(root / PAGE, "</style>", '[data-kpi="universe"] { font-weight: 700; }\n</style>')
        code, out = run_check(root)
        self.assertEqual(code, 0, out)

    def test_check_fails_on_duplicate_card(self):
        root = self.fresh()
        index = root / "index.html"
        text = index.read_text(encoding="utf-8")
        start = text.index('<article class="artifact-card" data-category="equity" data-keywords="tw-equity-screener')
        card = text[start:text.index("</article>", start) + len("</article>")]
        index.write_text(text.replace(card, card + "\n    " + card, 1), encoding="utf-8")
        self.assertFails(root, "2 screener cards")

    def test_readme_failures(self):
        root = self.fresh()
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("| **Equity Research**", ROW.format(w="46") + "\n| **Equity Research**", 1),
                          encoding="utf-8")
        self.assertFails(root, "2 README rows")
        readme.write_text(text.replace("2026-w47", "2026-w46").replace("2026-W47", "2026-W46"), encoding="utf-8")
        self.assertFails(root, "does not point to reports/screens/tw-screen-2026-w47.html")

    def test_folder_failures(self):
        root = self.fresh()
        (screens_dir(root) / WEEK / "diff.json").unlink()
        self.assertFails(root, "missing diff.json")

        root = self.fresh()
        outside = root / "elsewhere" / WEEK
        shutil.copytree(screens_dir(root) / WEEK, outside)
        self.assertFails(root, "is not", folder=outside)

        root = self.fresh()
        moved = screens_dir(root) / "2026-w48"
        (screens_dir(root) / WEEK).rename(moved)
        self.assertFails(root, "differs from the folder name", folder=moved)

        root = self.fresh()
        (root / PAGE).unlink()
        self.assertFails(root, f"page: {PAGE} does not exist")
        self.assertFails(root, f"README link ./{PAGE} does not exist")

    def test_asof_outside_week_fails(self):
        root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        render(make_repo(root, asof="2026-11-27"), root)
        self.assertFails(root, "asof 2026-11-27 is not in week 2026-w47")

    def test_previous_week_net_change(self):
        root = self.fresh()
        write_week(root, "2026-w46", {"universe.csv": universe_rows()[:1239]}, "2026-11-13")
        self.assertEqual(run_check(root)[0], 0)
        write_week(root, "2026-w46", {"universe.csv": universe_rows()[:1238]}, "2026-11-13")
        self.assertFails(root, "master moved 2 but events net 1")


if __name__ == "__main__":
    unittest.main()
