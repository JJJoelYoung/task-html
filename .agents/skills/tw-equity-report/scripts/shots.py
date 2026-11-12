#!/usr/bin/env python3
"""Capture review screenshots of one equity report.

Usage:
  python shots.py <work-folder> [--root <repo-root>] [--out <dir>]

Captures the first screen and each section dim1-dim6 at 1440 and 375 px in the
light and dark themes (28 PNGs), by default into <work-folder>/.hallmark/shots/.
Sticky and fixed elements are made static so they do not cover a section.

Needs Playwright (optional; the other scripts use only the standard library):
  pip install playwright && python -m playwright install chromium
Exit code 4 means Playwright or its browser is missing.
"""

import argparse
import sys
from pathlib import Path

import derive as dv
from check_report import find_root

WIDTHS = (1440, 375)
SCHEMES = ("light", "dark")
UNSTICK = """() => {
  for (const el of document.querySelectorAll('*')) {
    const p = getComputedStyle(el).position;
    if (p === 'sticky' || p === 'fixed') el.style.setProperty('position', 'static', 'important');
  }
}"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("work", type=Path)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    work = args.work.resolve()
    data_files = sorted(work.glob("data_*.json"))
    if len(data_files) != 1:
        print(f"expected one data_*.json in {work}, found {len(data_files)}", file=sys.stderr)
        return 1
    code = data_files[0].stem.split("_", 1)[1]
    root = args.root or find_root(work)
    if root is None:
        print("repo root with index.html not found; pass --root", file=sys.stderr)
        return 1
    d, a = dv.load_work(work, code)
    report = (root / dv.report_relpath(d, a)).resolve()
    if not report.exists():
        print(f"report {report} does not exist", file=sys.stderr)
        return 1
    out = (args.out or work / ".hallmark" / "shots").resolve()
    out.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        print("Playwright is not installed: pip install playwright && python -m playwright install chromium",
              file=sys.stderr)
        return 4
    shots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for w in WIDTHS:
                for scheme in SCHEMES:
                    page = browser.new_page(viewport={"width": w, "height": 900}, color_scheme=scheme)
                    page.goto(report.as_uri(), wait_until="networkidle")
                    page.evaluate("document.fonts.ready")
                    path = out / f"top-{w}-{scheme}.png"
                    page.screenshot(path=str(path))
                    shots.append(path)
                    page.evaluate(UNSTICK)
                    for i in range(1, 7):
                        sec = page.locator(f"#dim{i}")
                        if sec.count():
                            path = out / f"dim{i}-{w}-{scheme}.png"
                            sec.first.screenshot(path=str(path))
                            shots.append(path)
                    page.close()
            browser.close()
    except Error as e:
        print(f"Playwright browser failed ({e.message.splitlines()[0]}); run: python -m playwright install chromium",
              file=sys.stderr)
        return 4
    for s in shots:
        print(s)
    print(f"{len(shots)} screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
