#!/usr/bin/env python3
"""Generate the 2492 Walsin Technology equity report HTML from data and analysis JSON.

All figures come from data_2492.json / analysis_2492.json; the derived values in
methodology.md sections 6 and 7 come from the skill's shared derive.py.
"""

import html
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CODE = "2492"
DATA = HERE / f"data_{CODE}.json"
ANALYSIS = HERE / f"analysis_{CODE}.json"
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "tw-equity-report" / "scripts"))
import derive as dv  # noqa: E402
from derive import derive  # noqa: E402


def load():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    a = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    return d, a


def report_path(d, a):
    return ROOT / "reports" / "equity" / f"{CODE}-{a['slug']}-{d['asof'].replace('-', '')}.html"


# ------------------------------------------------------------------ formatting

E = html.escape


fp = dv.fmt_price


def fs(v, dec=1, suffix="%"):
    if v is None:
        return "無資料"
    return f"{v:+,.{dec}f}{suffix}"


def fn(v, dec=0):
    return "無資料" if v is None else f"{v:,.{dec}f}"


def yi(v):
    """NT$ to 億."""
    return f"{v / 1e8:,.1f}"


rr_txt = dv.fmt_rr


ALIGN_ZH = {"bullish": "多頭排列", "bearish": "空頭排列", "mixed": "均線糾結交錯"}
LEVEL_ZH = {"low": "低", "medium": "中", "high": "高（具軋空潛力）"}
GROUP_ZH = {"foreign": "外資", "trust": "投信", "dealer": "自營商"}
MARKET_ZH = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}


# ------------------------------------------------------------------ svg helpers

class Scale:
    def __init__(self, d0, d1, r0, r1):
        self.d0, self.d1, self.r0, self.r1 = d0, d1, r0, r1

    def __call__(self, v):
        if self.d1 == self.d0:
            return (self.r0 + self.r1) / 2
        return self.r0 + (v - self.d0) * (self.r1 - self.r0) / (self.d1 - self.d0)


def nice_ticks(lo, hi, n=4):
    import math

    span = hi - lo or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=10 * mag)
    start = math.ceil(lo / step) * step
    out = []
    v = start
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def svg_open(w, h, label):
    return (
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{E(label)}" '
        f'preserveAspectRatio="none">'
    )


def grid(ys, sy, x0, x1, fmt):
    out = []
    for v in ys:
        y = sy(v)
        out.append(f'<line class="grid" x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="axis" x="{x1 + 6}" y="{y + 4:.1f}">{E(fmt(v))}</text>')
    return "".join(out)


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


def price_chart(series, label, lines=None, height=420):
    """Candles + MA5/10/20 + volume. `lines` = [(key, label, value)] horizontal levels."""
    W, H = 960, height
    x0, x1 = 8, W - 64
    py0, py1 = 16, H - 110
    vy0, vy1 = H - 92, H - 24
    lows = [s["low"] for s in series]
    highs = [s["high"] for s in series]
    extra = [v for _, _, v in (lines or [])]
    lo, hi = min(lows + extra), max(highs + extra)
    pad = (hi - lo) * 0.06
    sy = Scale(lo - pad, hi + pad, py1, py0)
    n = len(series)
    step = (x1 - x0) / n
    sx = lambda i: x0 + step * (i + 0.5)
    vmax = max(s["volume_lots"] for s in series)
    sv = Scale(0, vmax, vy1, vy0)
    avg20 = None
    out = [svg_open(W, H, label)]
    out.append(grid(nice_ticks(lo, hi), sy, x0, x1, lambda v: fn(v)))
    out.append(f'<line class="grid" x1="{x0}" x2="{x1}" y1="{vy1}" y2="{vy1}"/>')
    out.append(f'<text class="axis" x="{x1 + 6}" y="{vy0 + 8}">{fn(vmax / 1000, 0)}k 張</text>')
    bw = max(step * 0.6, 1.5)
    for i, s in enumerate(series):
        x = sx(i)
        up = s["close"] >= s["open"]
        cls = "candle up" if up else "candle down"
        yo, yc = sy(s["open"]), sy(s["close"])
        top, bot = min(yo, yc), max(yo, yc)
        out.append(f'<line class="wick" x1="{x:.1f}" x2="{x:.1f}" y1="{sy(s["high"]):.1f}" y2="{sy(s["low"]):.1f}"/>')
        out.append(f'<rect class="{cls}" x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bot - top, 1):.1f}"/>')
        vcls = "vol"
        out.append(
            f'<rect class="{vcls}" x="{x - bw / 2:.1f}" y="{sv(s["volume_lots"]):.1f}" width="{bw:.1f}" '
            f'height="{vy1 - sv(s["volume_lots"]):.1f}"/>'
        )
    for key, cls in (("ma20", "ma ma20"), ("ma10", "ma ma10"), ("ma5", "ma ma5")):
        pts = [(sx(i), sy(s[key])) for i, s in enumerate(series) if s[key] is not None]
        out.append(f'<path class="{cls}" d="{path(pts)}"/>')
    for key, lab, v in lines or []:
        y = sy(v)
        below = key == "sl"
        right = key == "t2"
        lx = x1 - 4 if right else x0 + 4
        anchor = "end" if right else "start"
        ly = y + 15 if below else y - 5
        out.append(
            f'<g class="level level-{key}" data-line="{key}" data-value="{v}">'
            f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text class="level-label" x="{lx}" y="{ly:.1f}" text-anchor="{anchor}">{E(lab)} {fp(v)}</text></g>'
        )
    for i, s in enumerate(series):
        tip = (
            f'{s["date"]}　開 {fp(s["open"])}　高 {fp(s["high"])}　低 {fp(s["low"])}　收 {fp(s["close"])}'
            f'　量 {fn(s["volume_lots"])} 張　MA5 {fn(s["ma5"], 2)}　MA10 {fn(s["ma10"], 2)}　MA20 {fn(s["ma20"], 2)}'
        )
        out.append(
            f'<rect class="hit" x="{x0 + step * i:.1f}" y="{py0}" width="{step:.1f}" height="{vy1 - py0}" '
            f'data-tip="{E(tip)}"><title>{E(tip)}</title></rect>'
        )
    out.append(f'<text class="axis" x="{x0}" y="{H - 6}">{series[0]["date"]}</text>')
    out.append(f'<text class="axis" x="{x1}" y="{H - 6}" text-anchor="end">{series[-1]["date"]}</text>')
    out.append("</svg>")
    return "".join(out)


def line_chart(points, label, series_keys, fmt, height=260, zero=False, refs=None):
    """points: list of dicts with 'x' label and series values. series_keys: [(key, name, cls)]."""
    W, H = 960, height
    x0, x1, y0, y1 = 8, W - 72, 16, H - 28
    vals = [p[k] for p in points for k, _, _ in series_keys if p[k] is not None]
    ref_vals = [v for _, v in (refs or [])]
    lo, hi = min(vals + ref_vals + ([0] if zero else [])), max(vals + ref_vals + ([0] if zero else []))
    pad = (hi - lo) * 0.08 or 1
    sy = Scale(lo - pad, hi + pad, y1, y0)
    n = len(points)
    sx = lambda i: x0 + (x1 - x0) * (i / max(n - 1, 1))
    out = [svg_open(W, H, label), grid(nice_ticks(lo, hi), sy, x0, x1, fmt)]
    for name, v in refs or []:
        y = sy(v)
        out.append(
            f'<line class="ref" x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text class="axis ref-label" x="{x1 - 4}" y="{y - 4:.1f}" text-anchor="end">{E(name)} {E(fmt(v))}</text>'
        )
    if zero:
        out.append(f'<line class="zero" x1="{x0}" x2="{x1}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>')
    for key, _, cls in series_keys:
        pts = [(sx(i), sy(p[key])) for i, p in enumerate(points) if p[key] is not None]
        out.append(f'<path class="series {cls}" d="{path(pts)}"/>')
    step = (x1 - x0) / max(n - 1, 1)
    for i, p in enumerate(points):
        tip = p["x"] + "　" + "　".join(f"{nm} {fmt(p[k])}" for k, nm, _ in series_keys)
        out.append(
            f'<rect class="hit" x="{sx(i) - step / 2:.1f}" y="{y0}" width="{step:.1f}" height="{y1 - y0}" '
            f'data-tip="{E(tip)}"><title>{E(tip)}</title></rect>'
        )
    out.append(f'<text class="axis" x="{x0}" y="{H - 6}">{E(points[0]["x"])}</text>')
    out.append(f'<text class="axis" x="{x1}" y="{H - 6}" text-anchor="end">{E(points[-1]["x"])}</text>')
    out.append("</svg>")
    return "".join(out)


def bar_chart(items, label, fmt, tipfmt, height=240, highlight_last=True, zero_center=False):
    """items: list of (xlabel, value)."""
    W, H = 960, height
    x0, x1, y0, y1 = 8, W - 72, 16, H - 28
    vals = [v for _, v in items if v is not None]
    lo, hi = min(vals + [0]), max(vals + [0])
    pad = (hi - lo) * 0.06
    sy = Scale(lo - (pad if lo < 0 else 0), hi + pad, y1, y0)
    n = len(items)
    step = (x1 - x0) / n
    bw = min(step - 3, 24)
    out = [svg_open(W, H, label), grid(nice_ticks(lo, hi), sy, x0, x1, fmt)]
    out.append(f'<line class="zero" x1="{x0}" x2="{x1}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>')
    for i, (xl, v) in enumerate(items):
        if v is None:
            continue
        x = x0 + step * i + (step - bw) / 2
        top, bot = sorted((sy(v), sy(0)))
        cls = "bar"
        if highlight_last and i == n - 1:
            cls += " bar-hi"
        if v < 0:
            cls += " bar-neg"
        tip = tipfmt(xl, v)
        out.append(f'<rect class="{cls}" x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bot - top, 1):.1f}"/>')
        out.append(
            f'<rect class="hit" x="{x0 + step * i:.1f}" y="{y0}" width="{step:.1f}" height="{y1 - y0}" '
            f'data-tip="{E(tip)}"><title>{E(tip)}</title></rect>'
        )
    out.append(f'<text class="axis" x="{x0}" y="{H - 6}">{E(items[0][0])}</text>')
    out.append(f'<text class="axis" x="{x1}" y="{H - 6}" text-anchor="end">{E(items[-1][0])}</text>')
    out.append("</svg>")
    return "".join(out)


def legend(entries):
    return '<ul class="legend">' + "".join(
        f'<li><span class="swatch {cls}" aria-hidden="true"></span>{E(nm)}</li>' for nm, cls in entries
    ) + "</ul>"


def figure(svg, caption, legend_html=""):
    return (
        f'<figure class="fig">{legend_html}<div class="chart-wrap">{svg}</div>'
        f'<figcaption>{caption}</figcaption></figure>'
    )


def table(head, rows, cls=""):
    th = "".join(f'<th scope="col"{" class=num" if n else ""}>{E(h)}</th>' for h, n in head)
    body = []
    for r in rows:
        rcls = ""
        if isinstance(r, tuple) and len(r) == 2 and isinstance(r[1], str) and r[1].startswith("row:"):
            r, rcls = r[0], r[1][4:]
        tds = "".join(
            f'<td class="num">{c}</td>' if head[i][1] else f"<td>{c}</td>" for i, c in enumerate(r)
        )
        body.append(f'<tr class="{rcls}">{tds}</tr>' if rcls else f"<tr>{tds}</tr>")
    return f'<div class="table-wrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def facts(pairs):
    """Definition list of label/value pairs; values are already-escaped HTML."""
    return '<dl class="facts">' + "".join(f"<div><dt>{E(k)}</dt><dd>{v}</dd></div>" for k, v in pairs) + "</dl>"


def judge():
    return '<span class="tag">分析師判斷</span>'


# ------------------------------------------------------------------ CSS

CSS = r"""
/* Hallmark · shape: Long Document · genre: editorial · theme: Almanac (deal 1/3, seed institutional-equity-research-report-1a69·ce12e4cc·2026-11-10·r0) · job: read the thesis and act on the trade setup · draw: manual
 * hero: Stat-Led split, the verdict sheet beside the head · nav: edge-aligned wordmark, six section links and a mode toggle · footer: a ruled colophon with source and disclaimer · imagery: none · signature: the verdict sheet, rating and Base target set in mono on the printed page
 * axes: mid/grotesk-sans/chromatic-magenta · posture: restrained · contrast: pass · fold: pass · modes: light+dark · data: FinMind · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S5 R4 V4 · weakest: H, six required sections make a long page; each opens on one verdict line and one chart so the squint finds the argument */
/* Hallmark · dismissed 58 · the page total counts six contract-required research sections; no single screen exceeds the budget */
/* Hallmark · dismissed F25 · the 7-column daily flow table scrolls inside its own container with the date column pinned */
/* Hallmark · waive 46b · six required sections each carry a chart · the report contract requires a price, flow, revenue, band and trade chart */
:root {
  color-scheme: light dark;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px;
  --text-xs: 0.8125rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.25rem; --text-xl: 1.5625rem; --text-2xl: 1.953rem; --text-3xl: 2.441rem;
  --text-display: clamp(2.5rem, 4.5vw + 1rem, 4.75rem);
  --text-section: clamp(1.875rem, 2vw + 1rem, 3rem); --text-title: clamp(1.25rem, 0.75vw + 0.875rem, 1.5rem); --text-lead: clamp(1.125rem, 0.35vw + 1rem, 1.3125rem);
  --text-figure: clamp(2.5rem, 4vw + 1rem, 4.5rem);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --dur-micro: 120ms; --dur-short: 220ms;
  --container: 1240px; --gutter: 64px; --gap-columns: 32px; --section-gap: 120px;
  --z-sticky-nav: 300; --z-tooltip: 600;
  --color-paper: oklch(84% 0.012 245); --color-paper-2: oklch(81% 0.012 245); --color-paper-3: oklch(77% 0.012 245);
  --color-ink: oklch(16% 0.020 245); --color-ink-2: oklch(24% 0.018 245); --color-muted: oklch(38% 0.016 245);
  --color-rule: oklch(73% 0.013 240); --color-rule-2: oklch(32% 0.018 240);
  --color-accent: oklch(45% 0.180 350); --color-accent-2: oklch(37% 0.160 350); --color-accent-3: oklch(60% 0.130 350); --color-accent-ink: oklch(97% 0.006 245); --color-focus: oklch(46% 0.190 350);
  --color-sheet: oklch(93.5% 0.008 245);
  --color-up: oklch(45% 0.180 350); --color-down: oklch(24% 0.018 245);
  --font-display: "Hanken Grotesk", ui-sans-serif, system-ui, sans-serif;
  --font-body: "Newsreader", ui-serif, Georgia, serif;
  --font-outlier: "IBM Plex Mono", ui-monospace, monospace;
  --radius-pill: 2px; --rule-hair: 1px; --rule-bar: 2px;
  --tracking-display: -0.02em; --display-weight: 600; --body-weight: 400;
}
[data-mode="dark"] {
  --color-paper: oklch(17% 0.012 245); --color-paper-2: oklch(20% 0.012 245); --color-paper-3: oklch(23% 0.012 245);
  --color-ink: oklch(94% 0.010 245); --color-ink-2: oklch(86% 0.012 245); --color-muted: oklch(72% 0.014 245);
  --color-rule: oklch(32% 0.013 240); --color-rule-2: oklch(64% 0.016 240);
  --color-accent: oklch(68% 0.150 350); --color-accent-2: oklch(76% 0.130 350); --color-accent-3: oklch(52% 0.110 350); --color-accent-ink: oklch(15% 0.020 245); --color-focus: oklch(72% 0.150 350);
  --color-sheet: oklch(21% 0.012 245);
  --color-up: oklch(68% 0.150 350); --color-down: oklch(86% 0.012 245);
  --body-weight: 350;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-mode]) {
    --color-paper: oklch(17% 0.012 245); --color-paper-2: oklch(20% 0.012 245); --color-paper-3: oklch(23% 0.012 245);
    --color-ink: oklch(94% 0.010 245); --color-ink-2: oklch(86% 0.012 245); --color-muted: oklch(72% 0.014 245);
    --color-rule: oklch(32% 0.013 240); --color-rule-2: oklch(64% 0.016 240);
    --color-accent: oklch(68% 0.150 350); --color-accent-2: oklch(76% 0.130 350); --color-accent-3: oklch(52% 0.110 350); --color-accent-ink: oklch(15% 0.020 245); --color-focus: oklch(72% 0.150 350);
    --color-sheet: oklch(21% 0.012 245);
    --color-up: oklch(68% 0.150 350); --color-down: oklch(86% 0.012 245);
    --body-weight: 350;
  }
}
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scroll-padding-top: 88px; scrollbar-color: var(--color-muted) var(--color-paper); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink-2); font-family: var(--font-body); font-weight: var(--body-weight); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; }
::selection { background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight); color: var(--color-ink); letter-spacing: var(--tracking-display); line-height: 1.05; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1 { font-size: var(--text-display); letter-spacing: -0.035em; line-height: 1; max-width: 14ch; }
h2 { font-size: var(--text-section); max-width: 24ch; }
h3 { font-size: var(--text-title); line-height: 1.2; }
p { margin: 0; text-wrap: pretty; max-width: 68ch; }
a { color: var(--color-ink); text-decoration-color: var(--color-accent); text-decoration-thickness: 1px; text-underline-offset: 0.15em; }
a:hover { text-decoration-thickness: 2px; }
.container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
.num, td.num, th.num { font-family: var(--font-outlier); font-variant-numeric: tabular-nums; text-align: right; }
.mono { font-family: var(--font-outlier); font-variant-numeric: tabular-nums; }

/* nav */
.nav { position: sticky; top: 0; z-index: var(--z-sticky-nav); background: var(--color-paper); border-bottom: var(--rule-hair) solid var(--color-rule-2); }
.nav-inner { display: flex; align-items: center; gap: var(--space-lg); min-height: 60px; }
.wordmark { font: 600 var(--text-md)/1 var(--font-display); color: var(--color-ink); text-decoration: none; letter-spacing: -0.01em; white-space: nowrap; }
.wordmark span { color: var(--color-accent); font-family: var(--font-outlier); font-weight: 500; }
.nav-links { display: flex; gap: var(--space-md); margin: 0 0 0 auto; padding: 0; list-style: none; overflow-x: auto; scrollbar-width: none; }
.nav-links a { font: 500 var(--text-sm)/1 var(--font-display); color: var(--color-ink-2); text-decoration: none; white-space: nowrap; padding: var(--space-xs) 0; border-bottom: var(--rule-bar) solid transparent; transition: border-color var(--dur-micro) var(--ease-out), color var(--dur-micro) var(--ease-out); }
.nav-links a:hover { color: var(--color-ink); border-bottom-color: var(--color-accent); }
.mode-toggle { font: 500 var(--text-sm)/1 var(--font-display); color: var(--color-ink); background: transparent; border: var(--rule-hair) solid var(--color-ink); border-radius: var(--radius-pill); padding: var(--space-xs) var(--space-sm); cursor: pointer; white-space: nowrap; transition: background-color var(--dur-micro) var(--ease-out), color var(--dur-micro) var(--ease-out); }
.mode-toggle:hover { background: var(--color-ink); color: var(--color-paper); }
.mode-toggle:active { transform: translateY(1px); }
.mode-toggle:disabled, .btn[aria-disabled="true"] { opacity: 0.45; cursor: not-allowed; }

/* hero */
.hero { min-height: calc(100svh - 61px); display: grid; align-items: center; padding-block: var(--space-2xl); }
.hero-grid { display: grid; grid-template-columns: minmax(0, 6fr) minmax(0, 5fr); gap: var(--space-2xl); align-items: center; }
.hero-meta { display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-lg); margin: 0 0 var(--space-lg); padding: 0; list-style: none; font-size: var(--text-sm); color: var(--color-muted); }
.hero-meta b { font-weight: 500; color: var(--color-ink); }
.hero .lead { margin-top: var(--space-lg); font-size: var(--text-lead); line-height: 1.45; max-width: 34ch; color: var(--color-ink-2); }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-sm); margin-top: var(--space-xl); }
.btn { display: inline-flex; align-items: center; min-height: 44px; padding: var(--space-sm) var(--space-lg); border: var(--rule-hair) solid var(--color-ink); border-radius: var(--radius-pill); font: 500 var(--text-sm)/1 var(--font-display); color: var(--color-ink); background: transparent; text-decoration: none; transition: background-color var(--dur-micro) var(--ease-out), color var(--dur-micro) var(--ease-out), border-color var(--dur-micro) var(--ease-out); }
.btn:hover { background: var(--color-paper-2); }
.btn:active { transform: translateY(1px); }
.btn--primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-accent-ink); }
.btn--primary:hover { background: var(--color-accent-2); border-color: var(--color-accent-2); color: var(--color-accent-ink); }

.sheet { margin: 0; background: var(--color-sheet); border-top: var(--rule-bar) solid var(--color-ink); padding: var(--space-lg) var(--space-lg) var(--space-md); }
.verdict { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-lg); padding-bottom: var(--space-lg); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.verdict-label { font-size: var(--text-sm); color: var(--color-muted); }
.verdict-value { display: block; margin-top: var(--space-2xs); font: 500 var(--text-figure)/1 var(--font-outlier); letter-spacing: -0.04em; color: var(--color-ink); font-variant-numeric: tabular-nums; }
.verdict-value.rating { font-family: var(--font-display); font-weight: 600; letter-spacing: -0.03em; }
.verdict-sub { display: block; margin-top: var(--space-xs); font-size: var(--text-sm); color: var(--color-muted); }
.kpis { margin: 0; }
.kpis div { display: flex; justify-content: space-between; gap: var(--space-md); padding: var(--space-sm) 0; border-bottom: var(--rule-hair) solid var(--color-rule); }
.kpis dt { color: var(--color-ink-2); }
.kpis dd { margin: 0; font-family: var(--font-outlier); font-variant-numeric: tabular-nums; color: var(--color-ink); text-align: right; }
.kpis .hi dd { color: var(--color-accent); }
.sheet-note { margin-top: var(--space-sm); font-size: var(--text-xs); font-style: italic; color: var(--color-muted); }

/* gaps note */
.gaps ul { margin: var(--space-2xs) 0 0; padding-left: 1.2em; font-size: var(--text-sm); }
.gaps li { max-width: 80ch; }

/* sections */
.dim { padding-block: var(--section-gap) 0; }
.dim-head { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 7fr); gap: var(--gap-columns); align-items: end; padding-bottom: var(--space-md); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.dim-num { font-family: var(--font-outlier); font-size: 0.5em; line-height: 1; color: inherit; vertical-align: 0.5em; margin-right: var(--space-sm); letter-spacing: 0; }
.dim-head .verdict-line { font-size: var(--text-lead); line-height: 1.45; color: var(--color-ink); max-width: 46ch; }
.dim-body { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-xl); margin-top: var(--space-lg); }
.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--gap-columns); }
.split-wide { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 4fr); gap: var(--gap-columns); align-items: start; }

.fig { margin: 0; }
.chart-wrap { position: relative; background: var(--color-sheet); border-top: var(--rule-bar) solid var(--color-ink); padding: var(--space-md) var(--space-sm) var(--space-xs); }
.chart { width: 100%; height: auto; aspect-ratio: 960 / var(--h, 420); overflow: visible; }
.fig figcaption { margin-top: var(--space-xs); font-size: var(--text-xs); color: var(--color-muted); }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-lg); margin: 0 0 var(--space-xs); padding: 0; list-style: none; font-size: var(--text-sm); color: var(--color-ink-2); }
.legend li { display: inline-flex; align-items: center; gap: var(--space-xs); }
.swatch { display: inline-block; width: 18px; height: 2px; background: var(--color-muted); }
.swatch.s1 { background: var(--color-accent); height: 3px; }
.swatch.s2 { background: var(--color-accent-3); }
.swatch.s3 { background: var(--color-muted); }
.swatch.s4 { background: var(--color-ink); }
.swatch.box { height: 10px; width: 10px; }

.chart .grid { stroke: var(--color-rule); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart .zero { stroke: var(--color-rule-2); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart .ref { stroke: var(--color-rule-2); stroke-width: 1; vector-effect: non-scaling-stroke; opacity: 0.55; }
.chart .axis { fill: var(--color-muted); font: 400 11px var(--font-outlier); font-variant-numeric: tabular-nums; }
.chart .wick { stroke: var(--color-ink-2); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart .candle.up { fill: var(--color-sheet); stroke: var(--color-up); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart .candle.down { fill: var(--color-down); }
.chart .vol { fill: var(--color-muted); opacity: 0.45; }
.chart .ma { fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }
.chart .ma5 { stroke: var(--color-accent); }
.chart .ma10 { stroke: var(--color-accent-3); }
.chart .ma20 { stroke: var(--color-muted); }
.chart .series { fill: none; stroke-width: 2; vector-effect: non-scaling-stroke; }
.chart .series.s1 { stroke: var(--color-accent); }
.chart .series.s2 { stroke: var(--color-accent-3); }
.chart .series.s3 { stroke: var(--color-muted); }
.chart .bar { fill: var(--color-muted); }
.chart .bar.bar-hi { fill: var(--color-accent); }
.chart .bar.bar-neg { fill: var(--color-paper-3); stroke: var(--color-muted); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart .level line { stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.chart .level-entry line { stroke: var(--color-ink); }
.chart .level-t1 line, .chart .level-t2 line { stroke: var(--color-accent); stroke-dasharray: none; }
.chart .level-t2 line { stroke: var(--color-accent-3); }
.chart .level-sl line { stroke: var(--color-muted); }
.chart .level-label { fill: var(--color-ink); font: 500 12px var(--font-outlier); paint-order: stroke; stroke: var(--color-sheet); stroke-width: 3px; }
.chart .hit { fill: transparent; cursor: crosshair; }
.chart .hit:hover { fill: color-mix(in oklab, var(--color-ink) 7%, transparent); }

.tip { position: fixed; z-index: var(--z-tooltip); pointer-events: none; max-width: min(420px, 90vw); padding: var(--space-xs) var(--space-sm); background: var(--color-ink); color: var(--color-paper); font: 400 var(--text-xs)/1.5 var(--font-outlier); font-variant-numeric: tabular-nums; opacity: 0; transition: opacity var(--dur-micro) var(--ease-out); }
.tip.on { opacity: 1; }

.table-wrap { overflow-x: auto; background: var(--color-sheet); border-top: var(--rule-bar) solid var(--color-ink); }
table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
th { font: 500 var(--text-sm)/1.3 var(--font-body); color: var(--color-muted); text-align: left; padding: var(--space-sm); border-bottom: var(--rule-bar) solid var(--color-rule-2); white-space: nowrap; }
td { padding: var(--space-sm); border-top: var(--rule-hair) solid var(--color-rule); vertical-align: top; color: var(--color-ink-2); }
td.num { white-space: nowrap; color: var(--color-ink); }
tr.hi td { background: color-mix(in oklab, var(--color-accent) 9%, transparent); }
tr.hi td:first-child { color: var(--color-accent); font-weight: 500; }
td.wrap { min-width: 22ch; }
th:first-child, td:first-child { position: sticky; left: 0; background: var(--color-sheet); }
b, strong { font-weight: 500; color: var(--color-ink); }
.kpis dd.txt { font-family: var(--font-body); }

.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 var(--gap-columns); margin: 0; }
.facts div { padding: var(--space-sm) 0; border-bottom: var(--rule-hair) solid var(--color-rule); }
.facts dt { font-size: var(--text-sm); color: var(--color-muted); }
.facts dd { margin: var(--space-2xs) 0 0; font-family: var(--font-outlier); font-variant-numeric: tabular-nums; color: var(--color-ink); font-size: var(--text-lg); }
.facts dd small { display: block; font-family: var(--font-body); font-size: var(--text-xs); color: var(--color-muted); }

.tag { display: inline-block; font: 500 var(--text-xs)/1.4 var(--font-body); color: var(--color-accent); border: var(--rule-hair) solid var(--color-accent); border-radius: var(--radius-pill); padding: 0 var(--space-2xs); margin-left: var(--space-2xs); white-space: nowrap; }
.prose p + p { margin-top: var(--space-sm); }
.src { font-size: var(--text-xs); color: var(--color-muted); }
.note { padding: var(--space-md) var(--space-lg); background: var(--color-paper-2); border-left: var(--rule-bar) solid var(--color-accent); }
.note p { font-size: var(--text-sm); }
.note .ext { margin: var(--space-2xs) 0 0; padding-left: 1.2em; font-size: var(--text-sm); }
.note .ext li + li { margin-top: var(--space-xs); }
.note .ext .src { display: block; }
.moat { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--gap-columns); margin: 0; padding: 0; list-style: none; }
.moat li { border-top: var(--rule-bar) solid var(--color-rule-2); padding-top: var(--space-md); }
.moat h3 { margin-bottom: var(--space-xs); }
.moat p { font-size: var(--text-md); }
.moat p.src { font-size: var(--text-xs); }
.unattractive { color: var(--color-accent); font-weight: 500; }

.band { margin-top: var(--section-gap); background: var(--color-ink); color: var(--color-paper); padding-block: var(--space-2xl); }
.band h2 { color: var(--color-paper); }
.footer { padding-block: var(--space-xl) var(--space-2xl); border-top: var(--rule-bar) solid var(--color-rule-2); margin-top: var(--section-gap); font-size: var(--text-sm); color: var(--color-muted); }
.footer-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: var(--gap-columns); }
.footer .disclaimer { color: var(--color-ink); font-weight: 500; margin-top: var(--space-sm); }

@media (max-width: 60rem) {
  :root { --gutter: 24px; --section-gap: 88px; }
  .hero-grid, .dim-head, .split, .split-wide, .footer-grid { grid-template-columns: minmax(0, 1fr); }
  .moat { grid-template-columns: minmax(0, 1fr); }
  .facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .nav-links { display: none; }
  .mode-toggle { margin-left: auto; }
}
@media (max-width: 40rem) {
  :root { --gutter: 16px; --section-gap: 64px; --gap-columns: 16px; }
  .sheet { padding: var(--space-md); }
  .verdict { gap: var(--space-md); }
  .facts { grid-template-columns: minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
@media print { .nav, .mode-toggle, .actions { display: none; } }
"""

JS = r"""
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('mode-toggle');
  function current() {
    return root.dataset.mode || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function label() { if (btn) btn.textContent = current() === 'dark' ? '淺色模式' : '深色模式'; }
  if (btn) {
    label();
    btn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      root.dataset.mode = next;
      try { localStorage.setItem('wtc-report-mode', next); } catch (e) {}
      label();
    });
  }
  var tip = document.createElement('div');
  tip.className = 'tip';
  tip.setAttribute('role', 'status');
  document.body.appendChild(tip);
  document.addEventListener('pointermove', function (ev) {
    var t = ev.target.closest ? ev.target.closest('[data-tip]') : null;
    if (!t) { tip.classList.remove('on'); return; }
    tip.textContent = t.getAttribute('data-tip');
    var x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    var y = ev.clientY + 16;
    if (y + tip.offsetHeight > window.innerHeight - 8) y = ev.clientY - tip.offsetHeight - 12;
    tip.style.transform = 'translate(' + Math.max(8, x) + 'px,' + y + 'px)';
    tip.style.left = '0'; tip.style.top = '0';
    tip.classList.add('on');
  });
  document.addEventListener('pointerleave', function () { tip.classList.remove('on'); });
})();
"""

HEAD_JS = (
    "try{var m=localStorage.getItem('wtc-report-mode');"
    "if(m==='dark'||m==='light')document.documentElement.dataset.mode=m;}catch(e){}"
)


# ------------------------------------------------------------------ sections

def section(sid, num, title, verdict, body):
    return (
        f'<section id="{sid}" class="dim" aria-labelledby="{sid}-h"><div class="container">'
        f'<header class="dim-head"><h2 id="{sid}-h"><span class="dim-num">{num}</span>{E(title)}</h2>'
        f'<p class="verdict-line">{verdict}</p></header>'
        f'<div class="dim-body">{body}</div></div></section>'
    )


def dim1(d):
    m = d["price"]["metrics"]
    s = d["price"]["series"]
    src = d["sources"]["price"]
    chart = price_chart(s, f"華新科日 K 線、均線與成交量，{s[0]['date']} 至 {s[-1]['date']}")
    lg = legend([("MA5", "s1"), ("MA10", "s2"), ("MA20", "s3"), ("成交量（張）", "s3 box")])
    fs_sig = m["float_settling"]
    verdict = (
        f"收盤 {fp(m['close'])}，低於 MA20 {fp(m['ma20'])} 達 {fs(m['bias_ma20_pct'])}；"
        f"均線{ALIGN_ZH[m['alignment']]}，短線趨勢偏空。"
    )
    fact = facts([
        ("近 1 個月高點", f"{fp(m['w20_high'])}<small>{m['w20_high_date']}</small>"),
        ("近 1 個月低點", f"{fp(m['w20_low'])}<small>{m['w20_low_date']}</small>"),
        ("5、10、20 日均線", f"{fn(m['ma5'], 2)} / {fn(m['ma10'], 2)} / {fn(m['ma20'], 2)}"),
        ("均線排列", f"{ALIGN_ZH[m['alignment']]}<small>MA 價差 {fn(m['ma_spread_pct'], 2)}%，{'糾結' if m['squeeze'] else '未糾結'}（門檻 2%）</small>"),
        ("20 日均量", f"{fn(m['vol_avg20_lots'])} 張<small>爆量門檻 {fn(m['vol_avg20_lots'] * 1.5)}，量縮門檻 {fn(m['vol_avg20_lots'] * 0.6)}</small>"),
        ("浮額沉澱訊號", f"{'成立' if fs_sig['signal'] else '未成立'}<small>融資餘額變化 {fn(fs_sig['margin_change'])} 張；量縮日 {fs_sig['dryup_count']} 天（門檻 5）</small>"),
    ])
    days = (
        f'<div class="split"><div><h3>爆量日（量 &gt; 1.5 × 均量）</h3><p class="mono">{E("、".join(m["spike_days"]) or "無")}</p></div>'
        f'<div><h3>量縮日（量 &lt; 0.6 × 均量）</h3><p class="mono">{E("、".join(m["dryup_days"]) or "無")}</p></div></div>'
    )
    cap = f"資料：FinMind TaiwanStockPrice，{src['range'][0]} 至 {src['range'][1]}。空心 K 棒為收紅，實心為收黑。"
    return section("dim1", "01", "價量與均線", verdict, figure(chart.replace('class="chart"', 'class="chart" style="--h:420"'), cap, lg) + fact + days)


def dim2(d):
    inst = d["institutional"]
    fh, mg = d["foreign_holding"], d["margin"]
    src = d["sources"]
    pts = [{"x": r["date"], "f": r["foreign_cum"], "t": r["trust_cum"], "d": r["dealer_cum"]} for r in inst["daily"]]
    cum_chart = line_chart(
        pts, "三大法人近 20 日累計買賣超（張）",
        [("f", "外資累計", "s1"), ("t", "投信累計", "s2"), ("d", "自營商累計", "s3")],
        lambda v: fn(v), height=280, zero=True,
    ).replace('class="chart"', 'class="chart" style="--h:280"')
    fh_chart = line_chart(
        [{"x": r["date"], "v": r["ratio"]} for r in fh["series"]], "外資持股比率（%）",
        [("v", "外資持股", "s1")], lambda v: f"{v:.2f}%", height=220,
    ).replace('class="chart"', 'class="chart" style="--h:220"')
    mg_chart = line_chart(
        [{"x": r["date"], "v": r["margin"]} for r in mg["series"]], "融資餘額（張）",
        [("v", "融資餘額", "s3")], lambda v: fn(v), height=220,
    ).replace('class="chart"', 'class="chart" style="--h:220"')
    c = inst["cum"]
    zone = inst["cost_zone"]
    verdict = (
        f"外資近 1 個月累計賣超 {fn(-c['foreign'])} 張，持股比率由 {fh['first']:.2f}% 降至 {fh['last']:.2f}%；"
        f"投信逆勢買超 {fn(c['trust'])} 張，融資減少 {fn(-mg['margin_change'])} 張。"
        if c["foreign"] < 0 else
        f"外資近 1 個月累計買超 {fn(c['foreign'])} 張，持股比率 {fh['last']:.2f}%。"
    )
    rows = [
        (r["date"], fs(r["foreign"], 0, ""), fs(r["trust"], 0, ""), fs(r["dealer"], 0, ""),
         fs(r["foreign_cum"], 0, ""), fs(r["trust_cum"], 0, ""), fs(r["dealer_cum"], 0, ""))
        for r in inst["daily"]
    ]
    tbl = table(
        [("日期", False), ("外資", True), ("投信", True), ("自營商", True), ("外資累計", True), ("投信累計", True), ("自營商累計", True)],
        rows,
    )
    zone_txt = (
        f"{fp(zone['low'])} 至 {fp(zone['high'])}<small>{GROUP_ZH[zone['group']]} {zone['days']} 個買超日的量加權均價 {fp(zone['price'])} ± 2%</small>"
        if zone else "無<small>外資與投信買超日皆少於 3 天</small>"
    )
    fact = facts([
        ("外資持股比率", f"{fh['last']:.2f}%<small>首 {fh['first']:.2f}%，高 {fh['high']:.2f}%，低 {fh['low']:.2f}%，變化 {fs(fh['change_pp'], 2, ' pp')}</small>"),
        ("融資餘額", f"{fn(mg['margin_last'])} 張<small>由 {fn(mg['margin_first'])} 張，{fs(mg['margin_change'], 0, ' 張')}（{fs(mg['margin_change_pct'])}）</small>"),
        ("融券餘額", f"{fn(mg['short_last'])} 張<small>由 {fn(mg['short_first'])} 張，{fs(mg['short_change'], 0, ' 張')}（{fs(mg['short_change_pct'])}）</small>"),
        ("券資比", f"{mg['short_margin_ratio_pct']:.2f}%<small>水位：{LEVEL_ZH[mg['short_margin_level']]}（&lt;5% 低、5% 至 20% 中、&gt;20% 高）</small>"),
        ("法人成本區", zone_txt),
    ])
    r0 = src["institutional"]["range"]
    body = (
        figure(cum_chart, f"資料：FinMind TaiwanStockInstitutionalInvestorsBuySell，{r0[0]} 至 {r0[1]}；單位：張。外資含外資自營商，自營商含避險。",
               legend([("外資", "s1"), ("投信", "s2"), ("自營商", "s3")]))
        + fact
        + '<div class="split">'
        + figure(fh_chart, f"資料：FinMind TaiwanStockShareholding，{src['foreign_holding']['range'][0]} 至 {src['foreign_holding']['range'][1]}。")
        + figure(mg_chart, f"資料：FinMind TaiwanStockMarginPurchaseShortSale，{src['margin']['range'][0]} 至 {src['margin']['range'][1]}。")
        + "</div>"
        + f'<div><h3>每日買賣超明細（張）</h3>{tbl}<p class="src">資料：FinMind TaiwanStockInstitutionalInvestorsBuySell，{r0[0]} 至 {r0[1]}。</p></div>'
    )
    return section("dim2", "02", "籌碼結構", verdict, body)


def dim3(d, a):
    rev, fin = d["revenue"], d["financials"]
    src = d["sources"]
    items = [(r["period"], r["revenue"] / 1e8) for r in rev["series24"]]
    rev_chart = bar_chart(items, "月營收（億元）", lambda v: fn(v), lambda x, v: f"{x}　營收 {v:,.2f} 億").replace(
        'class="chart"', 'class="chart" style="--h:240"')
    yoy_items = [(r["period"], r["yoy_pct"]) for r in rev["last12"]]
    yoy_chart = bar_chart(yoy_items, "月營收年增率（%）", lambda v: f"{v:.0f}%", lambda x, v: f"{x}　YoY {v:+.1f}%", height=200).replace(
        'class="chart"', 'class="chart" style="--h:200"')
    last = rev["last12"][-1]
    last4 = fin["quarters"][-4:]
    q_by = {q["quarter"]: q for q in fin["quarters"]}
    verdict = (
        f"{rev['latest_period'][:4]} 年 1 至 {int(rev['latest_period'][5:])} 月營收 {yi(rev['ytd'])} 億，年增 {fs(rev['ytd_yoy_pct'])}；"
        f"最新季（{fin['latest_quarter']}）毛利率 {last4[-1]['gross_margin_pct']:.2f}%，獲利與毛利同步回升。"
    )
    qrows = []
    for q in last4:
        qrows.append((
            q["quarter"], yi(q["revenue"]), f"{q['eps']:.2f}", f"{q['gross_margin_pct']:.2f}%",
            f"{q['operating_margin_pct']:.2f}%", yi(q["non_operating"]), fn(q["dsi_days"], 1),
        ))
    qtbl = table(
        [("季度", False), ("營收（億）", True), ("EPS（元）", True), ("毛利率", True), ("營業利益率", True), ("業外收支（億）", True), ("DSI（天）", True)],
        qrows,
    )
    mrows = [
        ((r["period"], yi(r["revenue"]), fs(r["mom_pct"]), fs(r["yoy_pct"])), "row:hi") if r is last
        else (r["period"], yi(r["revenue"]), fs(r["mom_pct"]), fs(r["yoy_pct"]))
        for r in rev["last12"]
    ]
    mtbl = table([("月份", False), ("營收（億）", True), ("MoM", True), ("YoY", True)], mrows)
    cc = fin["cash_conversion"]
    eq = a["earnings_quality"]
    ext_items = "".join(
        f'<li>{E(f["text"])}<span class="src">來源：<a href="{E(f["url"])}" rel="noopener">{E(f["source"])}</a>，{E(f["date"])}。</span></li>'
        for f in a["external_facts"]
    )
    fact = facts([
        ("累計營收（YTD）", f"{yi(rev['ytd'])} 億<small>去年同期 {yi(rev['ytd_prev'])} 億，YoY {fs(rev['ytd_yoy_pct'])}</small>"),
        ("最新月營收", f"{yi(last['revenue'])} 億<small>{last['period']}，MoM {fs(last['mom_pct'])}，YoY {fs(last['yoy_pct'])}</small>"),
        ("近四季每股盈餘", f"{fin['ttm_eps']:.2f} 元<small>{fin['last4'][0]} 至 {fin['last4'][-1]} 四季加總</small>"),
        ("DSI（最新季）", f"{fn(last4[-1]['dsi_days'], 1)} 天<small>前一季 {fn(last4[-2]['dsi_days'], 1)} 天</small>"),
        ("現金轉換率", f"{cc['ratio']:.2f}x<small>TTM 營業現金流 {yi(cc['ttm_ocf'])} 億 ÷ 稅後淨利 {yi(cc['ttm_net_income'])} 億</small>" if cc else "無資料"),
        ("每股淨值", f"{fin['bvps_latest']:.2f} 元<small>{fin['latest_quarter']} 歸屬母公司權益 ÷ 股數</small>"),
    ])
    fsrc = src["financials"]
    gaps = ""
    if d["gaps"]:
        gaps = (
            '<aside class="note gaps" aria-label="資料缺口"><p><b>資料缺口：</b></p><ul>'
            + "".join(f"<li>{E(g)}</li>" for g in d["gaps"])
            + "</ul></aside>"
        )
    body = (
        gaps
        + '<div class="split-wide">'
        + figure(rev_chart, f"資料：FinMind TaiwanStockMonthRevenue，{src['revenue']['range'][0]} 至 {src['revenue']['range'][1]}；最新月以洋紅標示。")
        + f"<div>{mtbl}</div></div>"
        + figure(yoy_chart, f"月營收年增率，{rev['last12'][0]['period']} 至 {rev['last12'][-1]['period']}；資料：FinMind TaiwanStockMonthRevenue。")
        + fact
        + f'<div><h3>近 4 季損益與庫存</h3>{qtbl}<p class="src">資料：FinMind {E(fsrc["dataset"])}，{fsrc["range"][0]} 至 {fsrc["range"][1]}；DSI =（期初＋期末存貨）÷ 2 ÷ 當季營業成本 × 91。</p></div>'
        + f'<div class="split"><div class="prose"><h3>盈餘品質：{E(eq["focus"])} {judge()}</h3><p>{E(eq["text"])}</p></div>'
        + f'<div class="note"><p><b>外部資訊（尚未進入 FinMind）：</b></p><ul class="ext">{ext_items}</ul></div></div>'
    )
    return section("dim3", "03", "營運與財務", verdict, body)


def dim4(d, a, x):
    val, peers = d["valuation"], d["peers"]
    src = d["sources"]["valuation"]

    def band_chart(key, title, fmt):
        b = val[key]
        pts = [{"x": p["date"], "v": p["v"]} for p in b["series"] if (p["v"] > 0 or key != "PER")]
        refs = [("P10", b["p10"]), ("P25", b["p25"]), ("P50", b["p50"]), ("P75", b["p75"]), ("P90", b["p90"])]
        return line_chart(pts, title, [("v", key, "s1")], fmt, height=260, refs=refs).replace(
            'class="chart"', 'class="chart" style="--h:260"')

    per, pbr = val["PER"], val["PBR"]
    verdict = (
        f"本益比 {per['current']:.2f}x，位於 5 年分布第 {per['current_percentile']:.1f} 百分位；"
        f"基本情境目標價 {fp(x['base']['target'])}，潛在{'上漲' if x['base']['upside_pct'] >= 0 else '下跌'} {fs(x['base']['upside_pct'])}，評等{x['rating_zh']}。"
    )
    band_tbl = table(
        [("指標", False), ("目前", True), ("百分位", True), ("P10", True), ("P25", True), ("P50", True), ("P75", True), ("P90", True)],
        [(k, f"{val[k]['current']:.2f}", f"{val[k]['current_percentile']:.1f}%", *(f"{val[k][p]:.2f}" for p in ("p10", "p25", "p50", "p75", "p90")))
         for k in ("PER", "PBR")],
    )
    reasons = {p["code"]: p for p in a["peers"]}
    prow = []
    for r in peers["rows"]:
        if r["code"] == CODE:
            prow.append(((f"{CODE} 華新科", f"{r['PER']:.2f}", f"{r['PBR']:.2f}", f"{r['dividend_yield']:.2f}%", "本報告標的"), "row:hi"))
        else:
            p = reasons[r["code"]]
            prow.append((f"{r['code']} {E(p['name'])}", f"{r['PER']:.2f}", f"{r['PBR']:.2f}", f"{r['dividend_yield']:.2f}%",
                         f"{E(p['reason'])} {judge()}"))
    md = peers["median"]
    prow.append(("同業中位數", f"{md['PER']:.2f}", f"{md['PBR']:.2f}", f"{md['dividend_yield']:.2f}%", "不含華新科"))
    peer_tbl = table([("公司", False), ("PER", True), ("PBR", True), ("殖利率", True), ("選擇理由", False)], prow)

    srow = []
    for s in x["scenarios"]:
        row = (
            f"{s['label']}（{s['name']}）", f"{s['eps']:.2f}", f"{s['multiple']:.1f}x", fp(s["target"]),
            fs(s["upside_pct"]), f"{s['probability']}%", f'<span class="wrap">{E(s["assumptions"])}</span>',
        )
        srow.append((row, "row:hi") if s["name"] == "Base" else row)
    srow.append(("機率加權", "", "", fp(x["weighted_target"]), fs(x["weighted_upside_pct"]), "100%", ""))
    scen_tbl = table(
        [("情境", False), ("前瞻 EPS", True), ("PER", True), ("目標價", True), ("潛在漲跌", True), ("機率", True), ("假設", False)],
        srow,
    )
    basis = "".join(f"<li><b>{E(s['label'])}：</b>{E(s['basis'])}</li>" for s in x["scenarios"])
    body = (
        '<div class="split">'
        + figure(band_chart("PER", "5 年本益比與 P10 至 P90 分位", lambda v: f"{v:.1f}x"), f"資料：FinMind TaiwanStockPER，{src['range'][0]} 至 {src['range'][1]}；剔除 PER ≤ 0；每 5 個交易日取樣繪圖，分位以全部 {per['n']} 日計算。")
        + figure(band_chart("PBR", "5 年股價淨值比與 P10 至 P90 分位", lambda v: f"{v:.2f}x"), f"資料：FinMind TaiwanStockPER，{src['range'][0]} 至 {src['range'][1]}；PBR 目前 {pbr['current']:.2f}x，第 {pbr['current_percentile']:.1f} 百分位。")
        + "</div>"
        + band_tbl
        + f'<div><h3>同業比較</h3>{peer_tbl}<p class="src">資料：FinMind TaiwanStockPER 最新一筆（{peers["rows"][0]["date"]}）；同業選擇為{judge()}。</p></div>'
        + f'<div><h3>三情境目標價（12 個月，{E(a["valuation_method"])} 法）{judge()}</h3>{scen_tbl}'
        + f'<p class="src">目標價 = 前瞻 EPS × PER，依跳動單位取整；倍數錨定：悲觀 ≤ P25（{per["p25"]:.2f}x）、基本介於 P25 至 P75、樂觀 ≤ P90（{per["p90"]:.2f}x）。{E(a["valuation_method_basis"])}</p>'
        + f'<ul class="src">{basis}</ul></div>'
        + facts([
            ("投資評等", f"{x['rating_zh']}（{x['rating_en']}）<small>依基本情境潛在漲跌：&gt; +15% 買進，−5% 至 +15% 中立，&lt; −5% 賣出</small>"),
            ("基本情境目標價", f"{fp(x['base']['target'])}<small>{x['base']['eps']:.2f} 元 × {x['base']['multiple']:.1f}x</small>"),
            ("機率加權目標價", f"{fp(x['weighted_target'])}<small>潛在漲跌 {fs(x['weighted_upside_pct'])}</small>"),
        ])
    )
    return section("dim4", "04", "估值與目標價", verdict, body)


def dim5(a):
    moat = '<ul class="moat">' + "".join(
        f'<li><h3>{E(m["title"])}</h3><p>{E(m["text"])}</p><p class="src">依據：{E(m["basis"])}</p></li>' for m in a["moat"]
    ) + "</ul>"

    def rows(items):
        return [
            (E(i["title"]), E(i["timing"]), E(i["direction"]), E(i["indicator"]), f'<span class="src">{E(i["basis"])}</span>')
            for i in items
        ]

    head = [("項目", False), ("預期時點", False), ("影響方向", False), ("觀察指標", False), ("依據", False)]
    verdict = "缺貨與漲價是多方主軸；外資調節、消費性庫存修正與業外波動是三個最需要盯的指標。"
    body = (
        f'<div><h3>護城河 {judge()}</h3>{moat}</div>'
        + f'<div><h3>催化劑</h3>{table(head, rows(a["catalysts"]))}</div>'
        + f'<div><h3>風險</h3>{table(head, rows(a["risks"]))}</div>'
    )
    return section("dim5", "05", "催化劑與風險", verdict, body)


def dim6(d, a, x):
    m = d["price"]["metrics"]
    s = d["price"]["series"][-60:]
    lines = [("entry", "Entry", x["entry"]), ("t1", "T1", x["t1"]), ("t2", "T2", x["t2"]), ("sl", "SL", x["hard_stop"])]
    chart = price_chart(s, "近 60 日 K 線與進場、目標、停損價位", lines=lines, height=440).replace(
        'class="chart"', 'class="chart" style="--h:440"')
    zone = d["institutional"]["cost_zone"]
    zone_note = (
        "MA10 至 MA20 區間與法人成本區重疊，取交集。" if x["zone_source"] == "overlap"
        else (f"法人成本區 {fp(zone['low'])} 至 {fp(zone['high'])} 與 MA10 至 MA20 區間未重疊，改用均線區間。" if zone else "法人成本區不存在，改用均線區間。")
    )
    below = x["close"] < x["zone_low"]
    setups = (("回檔", "rr_pullback", "pullback_status"), ("突破", "rr_breakout", "breakout_status"))
    no_trade = all(x[k] is None or x[k] < 1.5 for _, k, _ in setups)
    verdict = "、".join(
        f"{label} R:R {rr_txt(x[k])}" + ("" if x[st] == "active" else f"（{dv.SETUP_STATUS_ZH[x[st]]}）")
        for label, k, st in setups
    ) + ("；現階段不建議建立部位。" if no_trade else "。")

    def rr_cell(hook, k, st, formula):
        v = x[k]
        if v is None:
            note = dv.SETUP_STATUS_ZH[x[st]]
        else:
            note = ("不具交易吸引力" if v < 1.5 else "具交易吸引力") + f"；{formula}"
        cls = "unattractive" if v is None or v < 1.5 else ""
        return f'<span data-rr="{hook}">{rr_txt(v)}</span><small class="{cls}">{note}</small>'
    plan = table(
        [("項目", False), ("價位", True), ("條件與計算", False)],
        [
            ("回檔進場區", f"{fp(x['zone_low'])} 至 {fp(x['zone_high'])}", E(zone_note) + (f" 現價 {fp(x['close'])} 低於區間下緣，此區目前是反彈壓力區，需先站回才成立。" if below else "")),
            (("進場價（Entry）", fp(x["entry"]), "進場區中點"), "row:hi"),
            ("突破觸發價", fp(x["trigger"]), f"60 日最高價（{m['high60_date']}），當日量需 &gt; {fn(x['trigger_volume_lots'])} 張（1.5 × 20 日均量）"),
            ("T1（技術）", fp(x["t1"]), "60 日最高價" if x["t1"] == m["high60"] else "Entry + 0.618 × 60 日振幅"),
            (("T2（基本面）", fp(x["t2"]), "基本情境目標價"), "row:hi"),
            ("硬停損（SL）", fp(x["hard_stop"]),
             "進場區下緣 × 0.95（最大量日低點與 MA20 × 0.97 皆不低於區間下緣）" if x["hard_stop_source"] != "candidate"
             else "最大量日低點與 MA20 × 0.97 中，最接近進場價且低於區間下緣者"),
            ("突破停損", fp(x["breakout_stop"]), "突破觸發價 × 0.95"),
        ],
    )
    rr = facts([
        ("回檔 R:R", rr_cell("pullback", "rr_pullback", "pullback_status", "(T2 − Entry) ÷ (Entry − SL)")),
        ("突破 R:R", rr_cell("breakout", "rr_breakout", "breakout_status", "(T2 − 觸發價) ÷ (觸發價 − 突破停損)")),
    ])
    breakers = table(
        [("論點失效條件", False), ("門檻", False), ("觀察資料集", False)],
        [(E(b["condition"]), E(b["threshold"]), f'<span class="mono">{E(b["dataset"])}</span>') for b in a["thesis_breakers"]],
    )
    body = (
        figure(chart, f"資料：FinMind TaiwanStockPrice，{s[0]['date']} 至 {s[-1]['date']}。水平線：Entry、T1、T2、SL。",
               legend([("Entry", "s4"), ("T1", "s1"), ("T2", "s2"), ("SL", "s3")]))
        + '<div class="split-wide">' + f"<div>{plan}</div>" + f"<div>{rr}</div></div>"
        + f'<div><h3>論點失效條件 {judge()}</h3>{breakers}</div>'
    )
    return section("dim6", "06", "交易部位與風控", verdict, body)


# ------------------------------------------------------------------ page

def build(d, a):
    x = derive(d, a)
    m = d["price"]["metrics"]
    gen = date.today().isoformat()
    up_word = "潛在上漲" if x["base"]["upside_pct"] >= 0 else "潛在下跌"
    hero = f"""
<header class="hero" id="top"><div class="container hero-grid">
  <div>
    <h1>華新科：盈餘起飛，評價已滿</h1>
    <p class="lead">被動元件缺貨推升獲利，但現價離基本目標價只剩 {fs(x['base']['upside_pct'])}。</p>
    <div class="actions">
      <a class="btn btn--primary" href="#dim6">看交易部位</a>
      <a class="btn" href="#dim4">看估值推導</a>
    </div>
  </div>
  <figure class="sheet" aria-label="投資結論">
    <div class="verdict">
      <div><span class="verdict-label">投資評等</span><span class="verdict-value rating" data-kpi="rating">{x['rating_zh']}</span><span class="verdict-sub">12 個月評等</span></div>
      <div><span class="verdict-label">基本情境目標價</span><span class="verdict-value" data-kpi="target">{fp(x['base']['target'])}</span><span class="verdict-sub">{x['base']['eps']:.2f} 元 × {x['base']['multiple']:.1f}x</span></div>
    </div>
    <dl class="kpis">
      <div><dt>公司</dt><dd class="txt">{E(a['name_zh'])}（{E(a['name_en'])}）</dd></div>
      <div><dt>代號與市場</dt><dd>{CODE}　{MARKET_ZH[a['market']]}</dd></div>
      <div><dt>產業</dt><dd class="txt">{E(a['industry'])}</dd></div>
      <div><dt>收盤價</dt><dd data-kpi="close">{fp(x['close'])}</dd></div>
      <div class="hi"><dt>{up_word}</dt><dd data-kpi="upside">{fs(x['base']['upside_pct'])}</dd></div>
      <div><dt>回檔 R:R</dt><dd data-kpi="rr">{rr_txt(x['rr_pullback'])}</dd></div>
      <div><dt>資料日</dt><dd data-kpi="asof">{d['asof']}</dd></div>
    </dl>
    <figcaption class="sheet-note">數據來源 FinMind；評等依方法論由基本情境潛在漲跌決定。</figcaption>
  </figure>
</div></header>"""
    nav_items = [("dim1", "價量"), ("dim2", "籌碼"), ("dim3", "財務"), ("dim4", "估值"), ("dim5", "風險"), ("dim6", "交易")]
    nav = (
        '<nav class="nav" aria-label="報告章節"><div class="container nav-inner">'
        f'<a class="wordmark" href="#top">華新科 <span>{CODE}</span></a><ul class="nav-links">'
        + "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in nav_items)
        + '</ul><button class="mode-toggle" id="mode-toggle" type="button">深色模式</button></div></nav>'
    )
    footer = f"""
<footer class="footer"><div class="container footer-grid">
  <div><p><b>{E(a['name_zh'])}（{CODE}）360 度研究報告</b></p><p>資料日 <span class="mono">{d['asof']}</span>，產生日 <span class="mono">{gen}</span>。</p></div>
  <div><p>資料來源：FinMind（TaiwanStockPrice、TaiwanStockInstitutionalInvestorsBuySell、TaiwanStockShareholding、TaiwanStockMarginPurchaseShortSale、TaiwanStockMonthRevenue、TaiwanStockFinancialStatements、TaiwanStockBalanceSheet、TaiwanStockCashFlowsStatement、TaiwanStockPER）。標示「分析師判斷」者為主觀判斷；外部資訊註明來源與日期。語氣：{E(a['tone'])}</p>
  <p class="disclaimer">本報告僅供研究參考，不構成任何投資建議。</p></div>
</div></footer>"""
    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>華新科 2492 研究報告</title>
<meta name="description" content="華新科（2492）360 度股票研究：價量、籌碼、財務、估值、催化劑與交易部位，資料日 {d['asof']}。">
<script>{HEAD_JS}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
{nav}
<main>
{hero}
{dim1(d)}
{dim2(d)}
{dim3(d, a)}
{dim4(d, a, x)}
{dim5(a)}
{dim6(d, a, x)}
</main>
{footer}
<script>{JS}</script>
</body>
</html>
"""
    return doc, x


def main():
    d, a = load()
    doc, x = build(d, a)
    out = report_path(d, a)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: rating={x['rating_zh']} target={x['base']['target']} "
          f"upside={x['base']['upside_pct']} rr_pb={x['rr_pullback']} rr_bo={x['rr_breakout']}")


if __name__ == "__main__":
    main()
