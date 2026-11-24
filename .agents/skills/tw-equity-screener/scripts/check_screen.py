"""Check a rendered weekly screen: the week folder, the page, the portal card, and the README row.

Usage, from the repo root:
    python .agents/skills/tw-equity-screener/scripts/check_screen.py scripts/screens/{yyyy}-w{ww} [--root .]

Prints one FAIL line per failed check, then a PASS or FAIL summary; exits 1 on any failure.
The contract is references/page-contract.md.
"""

import argparse
import html
import re
import sys
from collections import Counter
from pathlib import Path

import history as hs
import render as rd
from shared import check_report as cr

DISCLAIMER = "本頁僅供研究參考，不構成任何投資建議。"
SECTIONS = ("summary", "tier-a", "shortlist", "changes", "sectors", "funnel", "watch", "forward", "method")
LAYERS = ("L0", "L0_full", "L0_watch", "L1", "L2", "L3", "L4", "L5", "L6")
LADDER = ("L0_full", "L1", "L2", "L3", "L4", "L5", "L6")
KPI_LAYERS = {"universe": "L0", "ranked": "L4", "shortlist": "L5", "tier_a": "L6"}
CARD_LAYERS = {"全市場": "L0", "完整漏斗": "L0_full", "入圍": "L5", "Tier A": "L6"}
DIRS = ("up", "down", "flat")
TELEMETRY_RE = re.compile(r'<div class="telemetry-item[^"]*">([^：<]+)：<span class="telemetry-val[^"]*">([^<]*)</span>')


def section(page, sec_id):
    m = re.search(rf'<section id="{re.escape(sec_id)}"(?:\s[^>]*)?>(.*?)</section>', page, re.S)
    return m.group(1) if m else None


def check_folder(c, folder, root):
    """Check 1: the seven files sit in scripts/screens/{week}/, share one stamp, and review.json names its model."""
    want = hs.screens_dir(root) / folder.name
    c.ok(folder.resolve() == want.resolve(), f"folder: {folder} is not {want}")
    d = hs.read_folder(folder) or {}
    missing = [name for name in hs.WEEK_FILES if Path(name).stem not in d]
    c.ok(not missing, f"folder: missing {', '.join(missing)}")
    stamps = Counter()
    for name in hs.WEEK_FILES:
        obj = d.get(Path(name).stem)
        for row in (obj if isinstance(obj, list) else [obj] if obj is not None else []):
            stamps[tuple(row.get(k) for k in hs.STAMP)] += 1
    if c.ok(len(stamps) == 1, f"folder: files disagree on {'/'.join(hs.STAMP)}: {sorted(map(str, stamps))[:3]}"):
        asof, week, _ = next(iter(stamps))
        c.ok(week == folder.name, f"folder: stamp week {week} differs from the folder name {folder.name}")
        c.ok(isinstance(asof, str) and hs.week_id(asof) == week, f"folder: asof {asof} is not in week {week}")
    gen = (d.get("review") or {}).get("generation")
    gen = gen if isinstance(gen, dict) else {}
    for field in ("model", "effort"):
        c.ok(isinstance(gen.get(field), str) and gen[field].strip(), f"folder: review.json generation.{field} is empty")
    return d, not missing


def check_counts(c, d, root, week):
    """Check 2: history.check_invariants, and the funnel counts tie to universe.csv and the shortlist.

    Returns whether every layer count is present, which the page and portal checks need."""
    universe, funnel, sl = d["universe"], d["funnel"], d["shortlist"]
    statuses = funnel.get("statuses") or {}
    prev = hs.previous_week(root, week)
    prev_n = len(hs.read_csv(hs.screens_dir(root) / prev / "universe.csv")) if prev else None
    for error in hs.check_invariants(len(universe), statuses, prev_n, d["events"]):
        c.ok(False, f"invariants: {error}")
    tally = Counter(r.get("status") for r in universe)
    c.ok(tally == Counter({k: v for k, v in statuses.items() if v}),
         f"invariants: funnel.json statuses differ from the universe.csv status column")
    counts = funnel.get("counts") or {}
    absent = [k for k in LAYERS if not isinstance(counts.get(k), int)]
    if not c.ok(not absent, f"invariants: funnel.json counts lack {', '.join(absent)}"):
        return False
    c.ok(counts["L0"] == len(universe), f"invariants: L0 is {counts['L0']}, universe.csv has {len(universe)} rows")
    c.ok(counts["L0"] == counts["L0_full"] + counts["L0_watch"], "invariants: L0 is not L0_full + L0_watch")
    c.ok(counts["L0_watch"] == statuses.get("watch_track", 0), "invariants: L0_watch differs from the watch_track count")
    ladder = [counts[k] for k in LADDER]
    c.ok(all(a >= b for a, b in zip(ladder, ladder[1:])),
         f"invariants: the funnel widens somewhere in {dict(zip(LADDER, ladder))}")
    actionable = [r["code"] for r in sl.get("actionable", [])]
    listed = len(actionable) + len(sl.get("left_watch", []))
    marked = statuses.get("shortlist_actionable", 0) + statuses.get("shortlist_left_watch", 0)
    c.ok(counts["L5"] == listed == marked, f"invariants: L5 is {counts['L5']}, shortlist.json lists {listed}, "
                                           f"statuses mark {marked}")
    c.ok(counts["L4"] == statuses.get("ranked", 0) + marked, "invariants: L4 is not ranked plus the shortlist")
    tier_a = sl.get("tier_a", [])
    c.ok(counts["L6"] == len(tier_a), f"invariants: L6 is {counts['L6']}, shortlist.json has {len(tier_a)} Tier A")
    c.ok(set(tier_a) <= set(actionable), "invariants: a Tier A code is not on the actionable list")
    return True


def check_colours(c, page):
    """Taiwan colours: --tw-up red and --tw-down green in :root and both dark blocks, and every hook uses them."""
    blocks = {":root": cr.css_block(page, ":root {"), "prefers-color-scheme: dark":
              cr.css_block(page, "@media (prefers-color-scheme: dark)"),
              ':root[data-mode="dark"]': cr.css_block(page, ':root[data-mode="dark"]')}
    for key in ("up", "down", "flat"):
        for where, block in blocks.items():
            c.ok(f"--tw-{key}:" in block, f"page: --tw-{key} not declared in {where}")
        c.ok(f"var(--tw-{key})" in page, f"page: no rule uses var(--tw-{key})")
    for key, ranges in cr.TW_HUES.items():
        for v in re.findall(rf"--tw-{key}\s*:\s*([^;}}]+)", page):
            if v.strip().startswith("var("):
                continue
            m = re.match(r"oklch\(\s*[\d.]+%?\s+([\d.]+)\s+([\d.]+)", v.strip())
            good = m and float(m.group(1)) >= 0.10 and any(lo <= float(m.group(2)) <= hi for lo, hi in ranges)
            c.ok(good, f"page: --tw-{key}: {v.strip()} is not an oklch {'red' if key == 'up' else 'green'} "
                       f"(chroma >= 0.10)")
    hooks = list(cr.tagged(page, "data-dir"))
    c.ok(hooks, "page: no data-dir hooks")
    bad = [f'{a["data-dir"]} {t}' for a, t in hooks
           if a["data-dir"] not in DIRS or (re.search(r"[1-9]", t) and cr.text_dir(t) != a["data-dir"])]
    c.ok(not bad, f"page: signed figures with the wrong data-dir: {', '.join(bad[:5])}")


def check_page(c, page, d, review):
    """Check 3: sections, KPI and funnel hooks, Tier A rows, colours, the mobile basics, and the footer.

    Hooks are read from <body> on, so a CSS attribute selector never stands in for a hook."""
    body = page[page.find("<body"):]
    f = d["funnel"]
    counts, asof = f["counts"], f["asof"]
    for sec in SECTIONS:
        c.ok(section(page, sec) is not None, f"page: section #{sec} missing")
    c.ok('aria-label="往期週報"' in page, "page: the earlier-weeks nav is missing")
    want = {"asof": asof, "regime": rd.regime_label(f.get("regime"))}
    want.update({key: f"{counts[layer]:,}" for key, layer in KPI_LAYERS.items()})
    for key, value in want.items():
        got = cr.text_of(body, "data-kpi", key)
        c.ok(got is not None and html.unescape(got) == value, f"page: data-kpi={key} shows {got!r}, expected {value!r}")
    for layer in LAYERS:
        got = cr.text_of(body, "data-layer", layer)
        c.ok(got == f"{counts[layer]:,}", f"page: data-layer={layer} shows {got!r}, expected {counts[layer]:,}")
    rows = re.findall(r'<tr[^>]*\bdata-code="([^"]+)"[^>]*>(.*?)</tr>', section(page, "tier-a") or "", re.S)
    tier_a = d["shortlist"].get("tier_a", [])
    c.ok(sorted(code for code, _ in rows) == sorted(tier_a),
         f"page: Tier A rows {sorted(code for code, _ in rows)} differ from shortlist.json {sorted(tier_a)}")
    for code, row in rows:
        c.ok(f"<code>/tw-equity-report {code}</code>" in row, f"page: Tier A row {code} lacks its report command")
    check_colours(c, page)
    c.ok(re.search(r'<meta name="viewport" content="width=device-width', page), "page: viewport meta missing")
    c.ok(re.search(r"html,\s*body\s*\{[^}]*overflow-x:\s*clip", page), "page: html, body lack overflow-x: clip")
    footer = re.search(r"<footer\b[^>]*>.*?</footer>", page, re.S)
    footer = footer.group(0) if footer else ""
    for needle in (DISCLAIMER, "資料來源", asof, str(f.get("methodology_version"))):
        c.ok(needle in footer, f"page: footer lacks {needle!r}")
    cr.check_generation_meta(c, page, review)
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    dead = sorted({a for a in re.findall(r'href="#([^"]+)"', page) if a not in ids})
    c.ok(not dead, f"page: in-page links to missing ids: {', '.join(dead)}")


def check_portal(c, root, rel, d, review):
    """Check 4: one screener card in index.html and one screens row in README.md, both for this week."""
    f, gen = d["funnel"], review.get("generation") or {}
    counts = f["counts"]
    index = (root / "index.html").read_text(encoding="utf-8")
    cards = [k for k in re.findall(r'<article class="artifact-card".*?</article>', index, re.S)
             if 'data-keywords="tw-equity-screener' in k.split(">", 1)[0]]
    if c.ok(len(cards) == 1, f"portal: {len(cards)} screener cards in index.html, expected 1"):
        card = cards[0]
        c.ok(f'href="{rel}"' in card, f"portal: the screener card does not link {rel}")
        c.ok(f'<span class="artifact-date">{f["asof"]}</span>' in card, f"portal: card date is not {f['asof']}")
        tele = {label.strip(): html.unescape(value) for label, value in TELEMETRY_RE.findall(card)}
        want = {label: f"{counts[layer]:,} 檔" for label, layer in CARD_LAYERS.items()}
        want["市場狀態"] = rd.regime_label(f.get("regime"))
        for label, value in want.items():
            c.ok(tele.get(label) == value, f"portal: card {label} shows {tele.get(label)!r}, expected {value!r}")
        c.ok(f"本週 Tier A：{counts['L6']} 檔" in card, "portal: card badge does not count this week's Tier A")
        for field in ("model", "effort"):
            got = cr.text_of(card, "data-meta", field)
            c.ok(got is not None and html.unescape(got) == str(gen.get(field) or ""),
                 f"portal: card data-meta={field} shows {got!r}, expected {gen.get(field)!r}")
        for r in cr.relative_refs(card):
            c.ok((root / r).exists(), f"links: card link {r} does not exist")
    readme = (root / "README.md").read_text(encoding="utf-8")
    rows = [ln for ln in readme.splitlines() if ln.startswith("|") and "reports/screens/" in ln]
    if c.ok(len(rows) == 1, f"portal: {len(rows)} README rows link reports/screens/, expected 1"):
        c.ok(rel in rows[0] and "View Online" in rows[0], f"portal: the README row does not point to {rel}")
        for target in re.findall(r"\]\((\./[^)]+)\)", rows[0]):
            c.ok((root / target).exists(), f"links: README link {target} does not exist")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path, help="scripts/screens/{yyyy}-w{ww}")
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root holding index.html and README.md")
    args = ap.parse_args(argv)
    root, folder = args.root.resolve(), args.folder.resolve()
    c = cr.Check()
    d, complete = check_folder(c, folder, root)
    rel = rd.page_rel(folder.name)
    if complete and check_counts(c, d, root, folder.name):
        page_path = root / rel
        if c.ok(page_path.is_file(), f"page: {rel} does not exist"):
            page = page_path.read_text(encoding="utf-8")
            check_page(c, page, d, d.get("review") or {})
            for r in cr.relative_refs(page):
                c.ok((page_path.parent / r).exists(), f"links: page link {r} does not exist")
        check_portal(c, root, rel, d, d.get("review") or {})
    for msg in c.failures:
        print(f"FAIL {msg}")
    verdict = "FAIL" if c.failures else "PASS"
    print(f"{verdict} {c.count - len(c.failures)}/{c.count} checks passed for {rel}")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
