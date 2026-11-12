#!/usr/bin/env python3
"""Check one equity report against report-contract.md section 7.

Usage:
  python check_report.py <work-folder> [--root <repo-root>]

The work folder holds data_{code}.json, analysis_{code}.json, and
research_{code}.md. The repo root
(default: the nearest parent of the work folder that has index.html) holds the
report, index.html, and README.md. Exit code 1 means at least one check failed.
"""

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import derive as dv

DISCLAIMER = "本報告僅供研究參考，不構成任何投資建議。"


class Check:
    def __init__(self):
        self.failures = []
        self.count = 0

    def ok(self, cond, msg):
        self.count += 1
        if not cond:
            self.failures.append(msg)
        return cond


def text_of(page, attr, value):
    m = re.search(rf'{attr}="{re.escape(value)}"[^>]*>([^<]*)<', page)
    return m.group(1).strip() if m else None


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.refs.append(v)


def relative_refs(text):
    p = _Refs()
    p.feed(text)
    out = []
    for r in p.refs:
        u = urlparse(r)
        if u.scheme or r.startswith(("#", "//", "mailto:")):
            continue
        out.append(unquote(u.path))
    return out


def check_data(c, d):
    gaps = " ".join(d["gaps"]).lower()
    c.ok(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.get("asof", "")), "data: asof missing or malformed")
    for k in ("price", "institutional", "foreign_holding", "margin", "revenue", "financials", "valuation"):
        c.ok(k in d["sources"], f"data: sources lacks {k}")
    m = d["price"]["metrics"]
    for k in ("close", "ma5", "ma10", "ma20", "bias_ma20_pct", "w20_high", "w20_low", "squeeze", "alignment",
              "vol_avg20_lots", "spike_days", "dryup_days", "float_settling", "high60", "low60"):
        c.ok(m.get(k) is not None, f"data: price.metrics.{k} is null")
    c.ok(len(d["price"]["series"]) >= 60, "data: price series shorter than 60 days")
    closes = [s["close"] for s in d["price"]["series"][-20:]]
    c.ok(abs(m["ma20"] - round(sum(closes) / 20, 2)) < 0.006, "data: MA20 does not match the last 20 closes")
    c.ok(len(d["institutional"]["daily"]) == 20, "data: institutional daily is not 20 rows")
    if d["institutional"]["cost_zone"] is None:
        c.ok("cost zone" in gaps, "data: null cost zone not listed in gaps")
    for k in ("first", "last", "high", "low", "change_pp"):
        c.ok((d["foreign_holding"] or {}).get(k) is not None, f"data: foreign_holding.{k} is null")
    for k in ("margin_last", "short_last", "short_margin_ratio_pct", "short_margin_level"):
        c.ok((d["margin"] or {}).get(k) is not None, f"data: margin.{k} is null")
    r, f = d["revenue"], d["financials"]
    c.ok(len(r["last12"]) == 12, "data: revenue.last12 is not 12 months")
    c.ok(r["ytd_yoy_pct"] is not None or "ytd yoy" in gaps, "data: null revenue YTD YoY not listed in gaps")
    c.ok(len(f["last4"]) == 4, "data: financials.last4 is not 4 quarters")
    if f["ttm_eps"] is None:
        c.ok("ttm eps" in gaps, "data: null TTM EPS not listed in gaps")
    else:
        c.ok(abs(f["ttm_eps"] - round(sum(q["eps"] for q in f["quarters"][-4:]), 2)) < 0.006,
             "data: TTM EPS does not equal the sum of the last 4 quarters")
    if f["cash_conversion"] is None:
        c.ok("cash" in gaps, "data: null cash conversion not listed in gaps")
    c.ok(f["quarters"][-1]["dsi_days"] is not None, "data: latest DSI is null")
    for k in ("PER", "PBR"):
        b = d["valuation"][k]
        vals = [b[p] for p in ("p10", "p25", "p50", "p75", "p90")]
        c.ok(vals == sorted(vals), f"data: {k} band percentiles not ascending")
        c.ok(b["current_percentile"] is not None, f"data: {k} current percentile is null")
    c.ok(len(d["peers"]["rows"]) == 4, "data: peer matrix needs the target plus 3 peers (re-run fetch.py with --peers)")
    c.ok((d["peers"]["median"] or {}).get("PER") is not None, "data: peer median PER is null")


def check_analysis(c, d, a, x):
    sc = {s["name"]: s for s in a["scenarios"]}
    c.ok(set(sc) == {"Bull", "Base", "Bear"}, "analysis: scenarios must be Bull, Base, Bear")
    c.ok(sum(s["probability"] for s in a["scenarios"]) == 100, "analysis: probabilities do not sum to 100")
    for group in ("scenarios", "peers", "catalysts", "risks"):
        for item in a.get(group, []):
            c.ok(str(item.get("basis", "")).strip(), f"analysis: {group} item without basis: {item.get('name') or item.get('title') or item.get('code')}")
    c.ok(len(a.get("peers", [])) == 3, "analysis: need exactly 3 peers")
    c.ok(3 <= len(a.get("catalysts", [])) <= 5, "analysis: need 3-5 catalysts")
    c.ok(3 <= len(a.get("risks", [])) <= 5, "analysis: need 3-5 risks")
    c.ok(2 <= len(a.get("thesis_breakers", [])) <= 3, "analysis: need 2-3 thesis breakers")
    method = "PBR" if a.get("valuation_method") == "PBR" else "PER"
    b = d["valuation"][method]
    inside = {
        "Bear": sc["Bear"]["multiple"] <= b["p25"],
        "Base": b["p25"] <= sc["Base"]["multiple"] <= b["p75"],
        "Bull": sc["Bull"]["multiple"] <= b["p90"],
    }
    for name, ok in inside.items():
        if not ok:
            c.ok(re.search(r"P(10|25|50|75|90)", sc[name]["basis"]),
                 f"analysis: {name} multiple is outside its anchor band and its basis cites no percentile")
    for s in x["scenarios"]:
        im = s["implied"]
        if im and im["needs_basis"]:
            c.ok(im["metric"] in sc[s["name"]]["basis"],
                 f"analysis: {s['name']} target implies {im['metric']} {dv.fmt_mult(im['value'])} ({im['position']}) "
                 f"and its basis does not address {im['metric']}")


URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#@!$&*+=%]+")


def urls_in(text):
    """URLs in text; CJK punctuation ends a URL and trailing ASCII punctuation is dropped."""
    return {u.rstrip(".:!?") for u in URL_RE.findall(text)}


def strings_in(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v)


def check_research(c, work, code, a, page=None):
    """External facts carry source, date, and url; every url in the analysis is in research_{code}.md."""
    md = work / f"research_{code}.md"
    if not c.ok(md.exists(), f"research: {md.name} missing"):
        return
    listed = urls_in(md.read_text(encoding="utf-8"))
    for f in a.get("external_facts", []):
        label = str(f.get("text", ""))[:40]
        c.ok(str(f.get("source", "")).strip(), f"research: external fact without source: {label}")
        c.ok(re.match(r"\d{4}-\d{2}", str(f.get("date", ""))), f"research: external fact without date: {label}")
        url = str(f.get("url", ""))
        if c.ok(URL_RE.fullmatch(url), f"research: external fact without url: {label}"):
            c.ok(page is None or f'href="{html.escape(url)}"' in page, f"html: external fact not linked: {url}")
    for url in sorted({u for s in strings_in(a) for u in urls_in(s)}):
        c.ok(url in listed, f"research: {url} is cited in the analysis but not listed in {md.name}")


def check_calculations(c, page, x):
    for s in x["scenarios"]:
        c.ok(dv.fmt_price(s["target"]) in page, f"html: {s['name']} target {dv.fmt_price(s['target'])} not shown")
        c.ok(dv.fmt_pct(s["upside_pct"]) in page, f"html: {s['name']} upside {dv.fmt_pct(s['upside_pct'])} not shown")
        if s["implied"]:
            v = dv.fmt_mult(s["implied"]["value"])
            c.ok(text_of(page, "data-implied", s["name"]) == v,
                 f"html: data-implied={s['name']} does not show the implied {s['implied']['metric']} {v}")
    c.ok(dv.fmt_price(x["weighted_target"]) in page, "html: probability-weighted target not shown")
    c.ok(text_of(page, "data-rr", "pullback") == dv.fmt_rr(x["rr_pullback"]), "html: data-rr=pullback does not match")
    c.ok(text_of(page, "data-rr", "breakout") == dv.fmt_rr(x["rr_breakout"]), "html: data-rr=breakout does not match")
    c.ok(text_of(page, "data-rr", "hold") == dv.fmt_rr(x["rr_hold"]), "html: data-rr=hold does not match")
    for k in ("pullback_status", "breakout_status", "hold_status"):
        if x[k] != "active":
            c.ok(dv.SETUP_STATUS_ZH[x[k]] in page, f"html: inactive setup reason missing: {dv.SETUP_STATUS_ZH[x[k]]}")
    for k in ("entry", "hard_stop", "breakout_stop", "t1", "t2", "trigger", "fair_buy"):
        c.ok(dv.fmt_price(x[k]) in page, f"html: {k} {dv.fmt_price(x[k])} not shown")


def check_structure(c, page, d, x):
    for i in range(1, 7):
        c.ok(re.search(rf'<section id="dim{i}"', page), f"html: section dim{i} missing")
    exp = {
        "close": dv.fmt_price(x["close"]),
        "rating": x["rating_zh"],
        "target": dv.fmt_price(x["base"]["target"]),
        "upside": dv.fmt_pct(x["base"]["upside_pct"]),
        "rr": dv.fmt_rr(x["rr_pullback"]),
        "action": x["action_zh"],
        "asof": d["asof"],
    }
    for k, v in exp.items():
        got = text_of(page, "data-kpi", k)
        c.ok(got == v, f"html: data-kpi={k} shows {got!r}, expected {v!r}")
    c.ok(x["action_note"] in page, f"html: action condition missing: {x['action_note']}")
    if '<section id="dim6"' in page:
        dim6 = page[page.index('<section id="dim6"'):]
        dim6 = dim6[: dim6.index("</section>")]
        for key, val in (("entry", x["entry"]), ("t1", x["t1"]), ("t2", x["t2"]), ("sl", x["hard_stop"])):
            m = re.search(rf'data-line="{key}" data-value="([\d.]+)"', dim6)
            c.ok(m and abs(float(m.group(1)) - val) < 1e-6, f"html: dim6 chart line {key} missing or not {val}")
    c.ok(DISCLAIMER in page, "html: disclaimer missing")
    c.ok(d["asof"] in page, "html: asof missing")
    c.ok("分析師判斷" in page, "html: no 分析師判斷 label")
    for gp in d["gaps"]:
        c.ok(html.escape(gp) in page, f"html: gap not disclosed: {gp[:60]}")
    for fig in re.findall(r"<figure\b.*?</figure>", page, re.S):
        if "<svg" not in fig and "<table" not in fig:
            continue
        cap = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S)
        c.ok(cap and "FinMind" in cap.group(1) and re.search(r"\d{4}-\d{2}", cap.group(1)),
             "html: a figure caption lacks the FinMind source or its date range")
    c.ok("prefers-color-scheme: dark" in page, "html: no dark theme")
    c.ok('id="mode-toggle"' in page, 'html: no theme toggle (id="mode-toggle")')
    c.ok('name="viewport"' in page, "html: no viewport meta")
    c.ok("overflow-x: clip" in page, "html: no overflow-x: clip")
    c.ok("data-tip=" in page, "html: no chart hover values (data-tip)")


def check_portal(c, root, rel, x, d):
    index = (root / "index.html").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    cards = [k for k in re.findall(r'<article class="artifact-card".*?</article>', index, re.S) if rel in k]
    if c.ok(len(cards) == 1, f"portal: {len(cards)} index.html cards link the report, expected 1"):
        card = cards[0]
        for needle in ('data-category="equity"', f'<span class="artifact-date">{d["asof"]}</span>',
                       f"NT$ {dv.fmt_price(x['base']['target'])}", dv.fmt_pct(x["base"]["upside_pct"]),
                       x["rating_zh"], rr_card(x["rr_pullback"]), "aria-label="):
            c.ok(needle in card, f"portal: card lacks {needle!r}")
        for r in relative_refs(card):
            c.ok((root / r).exists(), f"links: card link {r} does not exist")
    rows = [ln for ln in readme.splitlines() if ln.startswith("|") and rel in ln]
    if c.ok(len(rows) == 1, f"portal: {len(rows)} README rows link the report, expected 1"):
        c.ok("View Online" in rows[0], "portal: README row lacks View Online")
        for target in re.findall(r"\]\((\./[^)]+)\)", rows[0]):
            c.ok((root / target).exists(), f"links: README link {target} does not exist")


def rr_card(v):
    """Card telemetry text for the pullback R:R."""
    return dv.fmt_rr(v) if v is None else f"{dv.fmt_rr(v)} : 1"


def find_root(start):
    for p in [start, *start.parents]:
        if (p / "index.html").exists():
            return p
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("work", type=Path)
    ap.add_argument("--root", type=Path, default=None)
    args = ap.parse_args(argv)
    work = args.work.resolve()
    data_files = sorted(work.glob("data_*.json"))
    if len(data_files) != 1:
        print(f"expected one data_*.json in {work}, found {len(data_files)}", file=sys.stderr)
        return 1
    code = data_files[0].stem.split("_", 1)[1]
    root = (args.root or find_root(work))
    if root is None:
        print("repo root with index.html not found; pass --root", file=sys.stderr)
        return 1
    root = root.resolve()
    d, a = dv.load_work(work, code)
    x = dv.derive(d, a)
    rel = dv.report_relpath(d, a)
    report = root / rel
    c = Check()
    check_data(c, d)
    check_analysis(c, d, a, x)
    page = report.read_text(encoding="utf-8") if report.exists() else None
    check_research(c, work, code, a, page)
    if c.ok(page is not None, f"html: report {rel} does not exist"):
        check_calculations(c, page, x)
        check_structure(c, page, d, x)
        for r in relative_refs(page):
            c.ok((report.parent / r).exists(), f"links: report link {r} does not exist")
    check_portal(c, root, rel, x, d)
    for f in c.failures:
        print(f"FAIL {f}")
    print(f"{c.count - len(c.failures)}/{c.count} checks passed for {rel}")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
