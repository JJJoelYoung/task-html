#!/usr/bin/env python3
"""Generate the 6834 equity report HTML from data_6834.json and analysis_6834.json.

The generator owns layout and charts only. Every figure comes from the two JSON
files or from the skill's shared derive.py (methodology.md sections 6 to 8).
"""

import html
import math
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CODE = "6834"
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "tw-equity-report" / "scripts"))
import derive as dv  # noqa: E402

E = html.escape
fp, fpct, fmult, frr = dv.fmt_price, dv.fmt_pct, dv.fmt_mult, dv.fmt_rr

ALIGN_ZH = {"bullish": "多頭排列", "bearish": "空頭排列", "mixed": "交錯"}
LEVEL_ZH = {"low": "低", "medium": "中", "high": "高，具軋空潛力"}
GROUP_ZH = {"foreign": "外資", "trust": "投信", "dealer": "自營商"}
MARKET_ZH = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}
POS_ZH = {"below_p25": "低於第 25 百分位", "p25_p75": "第 25 至 75 百分位", "p75_p90": "第 75 至 90 百分位", "above_p90": "高於第 90 百分位"}
METRIC_ZH = {"PER": "本益比", "PBR": "淨值比"}


def fn(v, dec=0):
    return "無資料" if v is None else f"{v:,.{dec}f}"


def fsg(v, dec=0, suffix=""):
    """Signed number for flows and changes."""
    return "無資料" if v is None else f"{v:+,.{dec}f}{suffix}"


def yi(v):
    """NT$ to 億元."""
    return f"{v / 1e8:,.2f}"


def judge():
    return '<span class="tag">分析師判斷</span>'


# ------------------------------------------------------------------ svg

class Scale:
    def __init__(self, d0, d1, r0, r1):
        self.d0, self.d1, self.r0, self.r1 = d0, d1, r0, r1

    def __call__(self, v):
        if self.d1 == self.d0:
            return (self.r0 + self.r1) / 2
        return self.r0 + (v - self.d0) * (self.r1 - self.r0) / (self.d1 - self.d0)


def nice_ticks(lo, hi, n=4):
    span = (hi - lo) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    v = math.ceil(lo / step) * step
    out = []
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def svg_open(w, h, label):
    return f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{E(label)}">'


def grid(ys, sy, x0, x1, fmt):
    out = []
    for v in ys:
        y = sy(v)
        out.append(f'<line class="grid" x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="axis" x="{x1 + 8}" y="{y + 4:.1f}">{E(fmt(v))}</text>')
    return "".join(out)


def pathd(points):
    """SVG path; a None y breaks the line so missing days show as a gap."""
    out, pen = [], "M"
    for x, y in points:
        if y is None:
            pen = "M"
            continue
        out.append(f"{pen}{x:.1f},{y:.1f}")
        pen = "L"
    return " ".join(out)


def hit(x, w, y0, h, tip):
    return (f'<rect class="hit" x="{x:.1f}" y="{y0}" width="{w:.1f}" height="{h}" data-tip="{E(tip)}">'
            f'<title>{E(tip)}</title></rect>')


def x_labels(labels, sx, H, every):
    out = []
    n = len(labels)
    for i, lab in enumerate(labels):
        if i % every == 0 or i == n - 1:
            if i != n - 1 and n - 1 - i < every * 0.6:
                continue
            anchor = "end" if i == n - 1 else ("start" if i == 0 else "middle")
            out.append(f'<text class="axis" x="{sx(i):.1f}" y="{H - 6}" text-anchor="{anchor}">{E(lab)}</text>')
    return "".join(out)


def kline(series, label, spikes=(), lines=None, H=440, W=1150):
    """Candles, MA5/10/20, volume; spike-volume days filled volt. lines: [(key, text, value)]."""
    x0, x1 = 6, W - 70
    py0, py1 = 14, H - 128
    vy0, vy1 = H - 108, H - 26
    extra = [v for _, _, v in (lines or [])]
    lo = min([s["low"] for s in series] + extra)
    hi = max([s["high"] for s in series] + extra)
    pad = (hi - lo) * 0.05
    sy = Scale(lo - pad, hi + pad, py1, py0)
    n = len(series)
    step = (x1 - x0) / n
    sx = lambda i: x0 + step * (i + 0.5)  # noqa: E731
    vmax = max(s["volume_lots"] for s in series)
    sv = Scale(0, vmax, vy1, vy0)
    bw = max(step * 0.62, 1.4)
    out = [svg_open(W, H, label), grid(nice_ticks(lo, hi, 5), sy, x0, x1, lambda v: fn(v))]
    out.append(f'<line class="grid" x1="{x0}" x2="{x1}" y1="{vy1}" y2="{vy1}"/>'
               f'<text class="axis" x="{x1 + 8}" y="{vy0 + 10}">{fn(vmax)} 張</text>')
    spikes = set(spikes)
    for i, s in enumerate(series):
        x = sx(i)
        vcls = "vol spike" if s["date"] in spikes else "vol"
        out.append(f'<rect class="{vcls}" x="{x - bw / 2:.1f}" y="{sv(s["volume_lots"]):.1f}" width="{bw:.1f}" '
                   f'height="{max(vy1 - sv(s["volume_lots"]), 0.5):.1f}"/>')
        up = s["close"] >= s["open"]
        top, bot = sorted((sy(s["open"]), sy(s["close"])))
        out.append(f'<line class="wick" x1="{x:.1f}" x2="{x:.1f}" y1="{sy(s["high"]):.1f}" y2="{sy(s["low"]):.1f}"/>'
                   f'<rect class="candle {"up" if up else "down"}" x="{x - bw / 2:.1f}" y="{top:.1f}" '
                   f'width="{bw:.1f}" height="{max(bot - top, 1):.1f}"/>')
    for key in ("ma20", "ma10", "ma5"):
        out.append(f'<path class="ma {key}" d="{pathd([(sx(i), sy(s[key]) if s[key] is not None else None) for i, s in enumerate(series)])}"/>')
    placed = {"start": [], "end": []}
    for key, text, v in sorted(lines or [], key=lambda t: -t[2]):
        y = sy(v)
        side = "start"
        if any(abs(y - p) < 18 for p in placed["start"]):
            side = "end"
        placed[side].append(y)
        lx = x0 + 6 if side == "start" else x1 - 6
        out.append(f'<g class="level level-{key}" data-line="{key}" data-value="{v}">'
                   f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="level-label" x="{lx}" y="{y - 6:.1f}" text-anchor="{side}">{E(text)} {fp(v)}</text></g>')
    for i, s in enumerate(series):
        tip = (f'{s["date"]}　開 {fp(s["open"])}　高 {fp(s["high"])}　低 {fp(s["low"])}　收 {fp(s["close"])}'
               f'　量 {fn(s["volume_lots"])} 張　MA5 {fn(s["ma5"], 2)}　MA10 {fn(s["ma10"], 2)}　MA20 {fn(s["ma20"], 2)}')
        out.append(hit(x0 + step * i, step, py0, vy1 - py0, tip))
    out.append(x_labels([s["date"][5:] for s in series], sx, H, max(n // 6, 1)))
    out.append("</svg>")
    return "".join(out)


def lines_chart(points, label, keys, fmt, H=260, zero=False, refs=None, W=560):
    """points: [{'x': label, key: value|None}], keys: [(key, name, cls)], refs: [(name, value)]."""
    x0, x1, y0, y1 = 6, W - 78, 14, H - 30
    vals = [p[k] for p in points for k, _, _ in keys if p[k] is not None]
    rv = [v for _, v in (refs or [])]
    base = [0] if zero else []
    lo, hi = min(vals + rv + base), max(vals + rv + base)
    pad = (hi - lo) * 0.08 or 1
    sy = Scale(lo - pad, hi + pad, y1, y0)
    n = len(points)
    sx = lambda i: x0 + (x1 - x0) * (i / max(n - 1, 1))  # noqa: E731
    out = [svg_open(W, H, label), grid(nice_ticks(lo, hi), sy, x0, x1, fmt)]
    groups = []
    for name, v in sorted(refs or [], key=lambda t: -t[1]):
        y = sy(v)
        out.append(f'<line class="ref" x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        if groups and y - groups[-1][0] < 16:
            groups[-1][1].append(f"{name} {fmt(v)}")
        else:
            groups.append((y, [f"{name} {fmt(v)}"]))
    for y, labs in groups:
        out.append(f'<text class="axis ref-label" x="{x0 + 4}" y="{y - 4:.1f}">{E("、".join(labs))}</text>')
    if zero:
        out.append(f'<line class="zero" x1="{x0}" x2="{x1}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>')
    for key, _, cls in keys:
        out.append(f'<path class="series {cls}" d="{pathd([(sx(i), sy(p[key]) if p[key] is not None else None) for i, p in enumerate(points)])}"/>')
        last = next((i for i in range(n - 1, -1, -1) if points[i][key] is not None), None)
        if last is not None:
            out.append(f'<circle class="dot {cls}" cx="{sx(last):.1f}" cy="{sy(points[last][key]):.1f}" r="3.5"/>')
    step = (x1 - x0) / max(n - 1, 1)
    for i, p in enumerate(points):
        tip = p["x"] + "　" + "　".join(f"{nm} {fmt(p[k]) if p[k] is not None else '無資料'}" for k, nm, _ in keys)
        out.append(hit(sx(i) - step / 2, step, y0, y1 - y0, tip))
    out.append(x_labels([p["x"] for p in points], sx, H, max(n // 5, 1)))
    out.append("</svg>")
    return "".join(out)


def bars_chart(items, label, fmt, tipfmt, H=240, hi_last=True, W=560):
    """items: [(xlabel, value|None)]; the latest bar is the one volt fill."""
    x0, x1, y0, y1 = 6, W - 78, 14, H - 30
    vals = [v for _, v in items if v is not None]
    lo, hi = min(vals + [0]), max(vals + [0])
    pad = (hi - lo) * 0.06
    sy = Scale(lo - (pad if lo < 0 else 0), hi + pad, y1, y0)
    n = len(items)
    step = (x1 - x0) / n
    bw = min(step - 4, 24)
    out = [svg_open(W, H, label), grid(nice_ticks(lo, hi), sy, x0, x1, fmt)]
    for i, (xl, v) in enumerate(items):
        if v is None:
            continue
        x = x0 + step * i + (step - bw) / 2
        top, bot = sorted((sy(v), sy(0)))
        cls = "bar" + (" bar-hi" if hi_last and i == n - 1 else "") + (" bar-neg" if v < 0 else "")
        out.append(f'<rect class="{cls}" x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bot - top, 1):.1f}"/>')
    out.append(f'<line class="zero" x1="{x0}" x2="{x1}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>')
    for i, (xl, v) in enumerate(items):
        out.append(hit(x0 + step * i, step, y0, y1 - y0, tipfmt(xl, v) if v is not None else f"{xl}　無資料"))
    out.append(x_labels([xl for xl, _ in items], lambda i: x0 + step * (i + 0.5), H, max(n // 6, 1)))
    out.append("</svg>")
    return "".join(out)


def legend(entries):
    return '<ul class="legend">' + "".join(
        f'<li><span class="swatch {cls}" aria-hidden="true"></span>{E(nm)}</li>' for nm, cls in entries) + "</ul>"


def figure(inner, caption, legend_html="", cls="chart-wrap"):
    return (f'<figure class="fig">{legend_html}<div class="{cls}">{inner}</div>'
            f'<figcaption>{caption}</figcaption></figure>')


def table(head, rows, hi_rows=()):
    th = "".join(f'<th scope="col"{" class=num" if num else ""}>{E(h)}</th>' for h, num in head)
    body = []
    for ri, r in enumerate(rows):
        tds = "".join(f'<td class="num">{c}</td>' if head[i][1] else f"<td>{c}</td>" for i, c in enumerate(r))
        body.append(f'<tr class="hi">{tds}</tr>' if ri in hi_rows else f"<tr>{tds}</tr>")
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def stats(pairs):
    """Ruled figure row: (label, value_html, note_html)."""
    return '<dl class="stats">' + "".join(
        f'<div><dt>{E(k)}</dt><dd><span class="stat-v">{v}</span>{f"<small>{n}</small>" if n else ""}</dd></div>'
        for k, v, n in pairs) + "</dl>"


# ------------------------------------------------------------------ css

CSS = r"""/* Hallmark · shape: Stat-Led · genre: editorial · theme: Sport (deal 2/3, seed 6834-equity-research-8c5f·ce12e4cc·2026-11-12·r0) · job: decide (act on the call, then read the plan) · draw: manual
 * hero: Stat-Led split, the call and its condition beside the price ladder · nav: edge-aligned wordmark, six section links, mode toggle · footer: ruled colophon with sources and disclaimer · imagery: none · signature: the price ladder, every level of the plan on one scale with the close on a volt fill
 * axes: light/display-condensed/chromatic-volt · posture: restrained · contrast: pass · fold: pass · modes: light+dark · data: FinMind · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S5 R4 V4 · weakest: H, six contract sections make a long page; each opens on one verdict line and one chart */
/* Hallmark · hero-review: not run, the report contract fixes the hero content · finish-review: subagent · 8 findings · 8 resolved · gap: none */
/* Hallmark · dismissed 58 · the page total counts six contract-required research sections; no single screen exceeds the budget */
/* Hallmark · waive 46b · report-contract.md section 4 fixes six sections, each with a chart · the reader needs the price, flow, revenue, band and trade charts to act */
/* Hallmark · dismissed F25 · every wide table pins its first column (th:first-child sticky) and scrolls inside .table-wrap */
/* Hallmark · waive 44c · the ladder is a scale instrument whose rungs must keep their price spacing, so it keeps a fixed column · the call, its condition and both actions sit in the first screen */
/* Hallmark · waive 79 · the six-figure stat row continues the hero below the ladder · the call, its condition and the primary action sit inside the fold */
:root {
  color-scheme: light dark;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.8125rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.25rem; --text-xl: 1.5625rem; --text-2xl: 1.953rem; --text-3xl: 2.441rem;
  --text-display-s: clamp(2.25rem, 4vw + 0.5rem, 3.75rem); --text-display: clamp(2.75rem, 5vw + 1rem, 5.25rem);
  --text-section: clamp(2rem, 2.5vw + 1rem, 3.5rem); --text-title: clamp(1.25rem, 0.75vw + 0.875rem, 1.625rem); --text-lead: clamp(1.125rem, 0.35vw + 1rem, 1.375rem);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --dur-micro: 120ms; --dur-short: 220ms;
  --container: 1280px; --gutter: 64px; --gap-columns: 32px; --section-gap: 128px;
  --z-sticky-nav: 300; --z-tooltip: 600;
  --color-paper: oklch(98% 0.005 250); --color-paper-2: oklch(95% 0.006 250); --color-paper-3: oklch(91.5% 0.007 250);
  --color-ink: oklch(16% 0.080 260); --color-ink-2: oklch(22% 0.060 258); --color-muted: oklch(50% 0.020 250);
  --color-rule: oklch(78% 0.008 250); --color-rule-2: oklch(36% 0.060 255);
  --color-accent: oklch(88% 0.200 120); --color-accent-ink: oklch(16% 0.080 260); --color-accent-deep: oklch(58% 0.145 125);
  --color-focus: oklch(58% 0.145 125);
  --color-s1: oklch(58% 0.145 125); --color-s2: oklch(38% 0.090 125); --color-s3: oklch(62% 0.015 250);
  --color-vol: oklch(78% 0.012 250);
  --font-display: "Saira Condensed", "PingFang TC", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
  --font-body: "Albert Sans", "PingFang TC", "Microsoft JhengHei", "Noto Sans TC", ui-sans-serif, sans-serif;
  --font-outlier: "JetBrains Mono", ui-monospace, monospace;
  --radius-card: 4px; --rule-hair: 1px; --rule-bar: 2px;
  --tracking-display: -0.015em; --display-weight: 800;
}
[data-mode="dark"] {
  --color-paper: oklch(17% 0.030 258); --color-paper-2: oklch(21% 0.032 258); --color-paper-3: oklch(25% 0.034 258);
  --color-ink: oklch(96% 0.006 250); --color-ink-2: oklch(88% 0.010 250); --color-muted: oklch(72% 0.020 250);
  --color-rule: oklch(34% 0.030 255); --color-rule-2: oklch(76% 0.040 255);
  --color-accent-deep: oklch(82% 0.170 122); --color-focus: oklch(82% 0.170 122);
  --color-s1: oklch(84% 0.180 122); --color-s2: oklch(64% 0.120 125); --color-s3: oklch(60% 0.020 250);
  --color-vol: oklch(38% 0.025 255);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-mode]) {
    --color-paper: oklch(17% 0.030 258); --color-paper-2: oklch(21% 0.032 258); --color-paper-3: oklch(25% 0.034 258);
    --color-ink: oklch(96% 0.006 250); --color-ink-2: oklch(88% 0.010 250); --color-muted: oklch(72% 0.020 250);
    --color-rule: oklch(34% 0.030 255); --color-rule-2: oklch(76% 0.040 255);
    --color-accent-deep: oklch(82% 0.170 122); --color-focus: oklch(82% 0.170 122);
    --color-s1: oklch(84% 0.180 122); --color-s2: oklch(64% 0.120 125); --color-s3: oklch(60% 0.020 250);
    --color-vol: oklch(38% 0.025 255);
  }
}
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scroll-padding-top: 80px; scrollbar-color: var(--color-muted) var(--color-paper); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink-2); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.6; -webkit-font-smoothing: antialiased; }
::selection { background: var(--color-accent); color: var(--color-accent-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight); letter-spacing: var(--tracking-display); text-transform: uppercase; line-height: 1.02; color: var(--color-ink); overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h2 { font-size: var(--text-section); max-width: 30ch; }
h3 { font-size: var(--text-title); line-height: 1.2; }
p { margin: 0; text-wrap: pretty; max-width: 68ch; }
a { color: var(--color-ink); text-decoration-thickness: 1px; text-underline-offset: 0.16em; text-decoration-color: var(--color-rule); transition: text-decoration-color var(--dur-micro) var(--ease-out); }
a:hover { text-decoration-color: var(--color-accent-deep); text-decoration-thickness: 2px; }
b, strong { font-weight: 500; color: var(--color-ink); }
.container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
.mono, .num, td.num { font-family: var(--font-outlier); font-variant-numeric: tabular-nums; }

/* nav */
.nav { position: sticky; top: 0; z-index: var(--z-sticky-nav); background: var(--color-paper); border-bottom: var(--rule-hair) solid var(--color-rule); }
.nav-inner { display: flex; align-items: center; gap: var(--space-lg); min-height: 60px; }
.wordmark { font: var(--display-weight) var(--text-lg)/1 var(--font-display); text-transform: uppercase; color: var(--color-ink); text-decoration: none; white-space: nowrap; }
.nav-links { display: flex; gap: var(--space-lg); margin: 0 0 0 auto; padding: 0; list-style: none; }
.nav-links a { font: 500 var(--text-sm)/1 var(--font-body); color: var(--color-ink-2); text-decoration: none; padding: var(--space-xs) 0; border-bottom: var(--rule-bar) solid transparent; transition: border-color var(--dur-micro) var(--ease-out); }
.nav-links a:hover { border-bottom-color: var(--color-accent-deep); }
.btn, .mode-toggle { display: inline-flex; align-items: center; min-height: 44px; padding: var(--space-sm) var(--space-lg); border: var(--rule-bar) solid var(--color-ink); border-radius: var(--radius-card); font: var(--display-weight) var(--text-md)/1.25 var(--font-display); text-transform: uppercase; color: var(--color-ink); background: transparent; text-decoration: none; cursor: pointer; transition: background-color var(--dur-micro) var(--ease-out), color var(--dur-micro) var(--ease-out), border-color var(--dur-micro) var(--ease-out); }
.mode-toggle { min-height: 40px; padding: var(--space-xs) var(--space-md); white-space: nowrap; }
.btn:hover, .mode-toggle:hover { background: var(--color-paper-3); }
.btn:active, .mode-toggle:active { transform: translateY(1px); }
.btn--primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-accent-ink); }
.btn--primary:hover { background: var(--color-accent); border-color: var(--color-ink); }
.btn[aria-disabled="true"], .mode-toggle:disabled { opacity: 0.45; cursor: not-allowed; }

/* hero */
.hero { padding-block: var(--space-2xl) var(--space-xl); }
.hero-grid { display: grid; grid-template-columns: minmax(0, max-content) minmax(0, 1fr); gap: var(--space-2xl); align-items: center; }
.hero h1 { font-size: var(--text-display); max-width: 12ch; }
.hero h1 .co { display: block; font-size: var(--text-display-s); }
.hero h1 .call { display: block; margin-top: var(--space-xs); font-size: calc(var(--text-display) * 1.4); line-height: 0.95; }
.hero .lead { margin-top: var(--space-lg); font-size: var(--text-lead); line-height: 1.45; color: var(--color-ink); max-width: 36ch; }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-sm); margin-top: var(--space-xl); }
.meta { display: grid; grid-template-columns: repeat(4, minmax(0, auto)); gap: var(--space-2xs) var(--space-xl); margin: var(--space-xl) 0 0; }
.meta div { display: grid; gap: var(--space-3xs); }
.meta dt { font-size: var(--text-sm); color: var(--color-muted); }
.meta dd { margin: 0; color: var(--color-ink); font-weight: 500; }

/* price ladder (signature) */
.ladder { margin: 0; border-top: var(--rule-bar) solid var(--color-rule-2); border-bottom: var(--rule-bar) solid var(--color-rule-2); background: var(--color-paper-2); padding: var(--space-lg); }
.ladder-track { position: relative; height: 480px; margin-left: var(--space-3xl); border-left: var(--rule-bar) solid var(--color-rule-2); }
.tick { position: absolute; left: -8px; width: 16px; height: 0; border-top: var(--rule-bar) solid var(--color-rule-2); }
.tick.now { left: -12px; width: 24px; border-top: 3px solid var(--color-ink); }
.zone { position: absolute; left: -7px; width: 14px; background: var(--color-accent-deep); border-radius: 2px; }
.leader { position: absolute; left: 12px; width: 0; border-left: var(--rule-hair) solid var(--color-muted); }
.rung { position: absolute; left: 0; right: 0; height: 0; }
.rung-p { position: absolute; right: calc(100% + 16px); top: 0; transform: translateY(-50%); font: 500 var(--text-sm)/1 var(--font-outlier); font-variant-numeric: tabular-nums; color: var(--color-ink); white-space: nowrap; }
.rung-l { position: absolute; left: var(--space-lg); top: 0; transform: translateY(-50%); font-size: var(--text-sm); line-height: 1.3; color: var(--color-ink-2); white-space: nowrap; }
.rung.now .rung-l { background: var(--color-accent); color: var(--color-accent-ink); font-weight: 500; padding: var(--space-2xs) var(--space-xs); border-radius: var(--radius-card); }
.rung.now .rung-p { font-weight: 500; }
.ladder figcaption { margin-top: var(--space-md); font-size: var(--text-xs); color: var(--color-muted); }

/* the race in figures */
.figs { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); margin: 0; border-top: var(--rule-bar) solid var(--color-rule-2); border-bottom: var(--rule-hair) solid var(--color-rule); }
.figs > div { padding: var(--space-md) var(--space-md) var(--space-lg); border-left: var(--rule-hair) solid var(--color-rule); min-width: 0; }
.figs > div:first-child { border-left: none; padding-left: 0; }
.figs dt { font-size: var(--text-sm); color: var(--color-muted); }
.figs dd { margin: var(--space-2xs) 0 0; font: var(--display-weight) var(--text-display-s)/0.95 var(--font-display); font-variant-numeric: tabular-nums; color: var(--color-ink); overflow-wrap: anywhere; }
.figs dd.small-fig { font-size: var(--text-2xl); line-height: 1.1; }
.figs small { display: block; margin-top: var(--space-xs); font-size: var(--text-xs); color: var(--color-muted); }

/* sections */
.dim { padding-top: var(--section-gap); }
.dim-head { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: var(--gap-columns); align-items: end; padding-bottom: var(--space-md); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.dim-head .verdict { font-size: var(--text-lead); line-height: 1.45; color: var(--color-ink); max-width: 48ch; }
.dim-body { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-2xl); margin-top: var(--space-xl); }
.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--gap-columns); align-items: start; }
.trio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--gap-columns); align-items: start; }
.trio .chart { min-width: 360px; }
.stack { display: grid; gap: var(--space-xl); min-width: 0; }
.split-wide { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); gap: var(--gap-columns); align-items: start; }
.block h3 { margin-bottom: var(--space-md); }

.fig { margin: 0; min-width: 0; }
.chart-wrap { overflow-x: auto; border-top: var(--rule-bar) solid var(--color-rule-2); padding-top: var(--space-sm); }
.chart { display: block; width: 100%; min-width: 540px; height: auto; overflow: visible; }
.table-wrap { overflow-x: auto; border-top: var(--rule-bar) solid var(--color-rule-2); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.fig figcaption { margin-top: var(--space-xs); font-size: var(--text-xs); color: var(--color-muted); max-width: 90ch; }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-2xs) var(--space-lg); margin: 0 0 var(--space-xs); padding: 0; list-style: none; font-size: var(--text-sm); }
.legend li { display: inline-flex; align-items: center; gap: var(--space-xs); }
.swatch { display: inline-block; width: 20px; height: 3px; background: var(--color-s3); }
.swatch.s1 { background: var(--color-s1); } .swatch.s2 { background: var(--color-s2); } .swatch.s3 { background: var(--color-s3); }
.swatch.ink { background: var(--color-ink); }
.swatch.box { width: 12px; height: 12px; background: var(--color-vol); }
.swatch.volt { width: 12px; height: 12px; background: var(--color-accent); outline: 1px solid var(--color-rule-2); outline-offset: -1px; }

.chart .grid { stroke: var(--color-rule); stroke-width: 1; }
.chart .zero { stroke: var(--color-rule-2); stroke-width: 1; }
.chart .ref { stroke: var(--color-muted); stroke-width: 1; opacity: 0.6; }
.chart .axis { fill: var(--color-muted); font: 500 12px var(--font-outlier); font-variant-numeric: tabular-nums; }
.chart .ref-label { fill: var(--color-ink-2); paint-order: stroke; stroke: var(--color-paper); stroke-width: 3px; }
.chart .wick { stroke: var(--color-ink); stroke-width: 1; }
.chart .candle.up { fill: var(--color-paper); stroke: var(--color-ink); stroke-width: 1; }
.chart .candle.down { fill: var(--color-ink); }
.chart .vol { fill: var(--color-vol); }
.chart .vol.spike { fill: var(--color-accent); stroke: var(--color-ink); stroke-width: 1; }
.chart .ma, .chart .series { fill: none; stroke-width: 2; stroke-linejoin: round; }
.chart .ma5, .chart .series.s1 { stroke: var(--color-s1); }
.chart .ma10, .chart .series.s2 { stroke: var(--color-s2); }
.chart .ma20, .chart .series.s3 { stroke: var(--color-s3); }
.chart .dot.s1 { fill: var(--color-s1); } .chart .dot.s2 { fill: var(--color-s2); } .chart .dot.s3 { fill: var(--color-s3); }
.chart .bar { fill: var(--color-s3); }
.chart .bar.bar-hi { fill: var(--color-accent); stroke: var(--color-ink); stroke-width: 1; }
.chart .bar.bar-neg { fill: var(--color-paper-3); stroke: var(--color-s3); stroke-width: 1; }
.chart .level line { stroke-width: 1.5; }
.chart .level-entry line { stroke: var(--color-ink); }
.chart .level-t1 line { stroke: var(--color-s1); }
.chart .level-t2 line { stroke: var(--color-s2); }
.chart .level-sl line { stroke: var(--color-muted); stroke-dasharray: 6 4; }
.chart .level-label { fill: var(--color-ink); font: 500 13px var(--font-outlier); paint-order: stroke; stroke: var(--color-paper); stroke-width: 4px; }
.chart .hit { fill: transparent; cursor: crosshair; }
.chart .hit:hover { fill: color-mix(in oklab, var(--color-ink) 7%, transparent); }

.tip { position: fixed; left: 0; top: 0; z-index: var(--z-tooltip); pointer-events: none; max-width: min(440px, 92vw); padding: var(--space-xs) var(--space-sm); background: var(--color-ink); color: var(--color-paper); border-radius: var(--radius-card); font: 500 var(--text-xs)/1.5 var(--font-outlier); font-variant-numeric: tabular-nums; opacity: 0; transition: opacity var(--dur-micro) var(--ease-out); }
.tip.on { opacity: 1; }

table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
th { font: 500 var(--text-sm)/1.3 var(--font-body); color: var(--color-muted); text-align: left; padding: var(--space-sm); white-space: nowrap; }
th.num { text-align: right; }
td { padding: var(--space-sm); border-top: var(--rule-hair) solid var(--color-rule); vertical-align: top; color: var(--color-ink-2); }
td.num { text-align: right; white-space: nowrap; color: var(--color-ink); }
.wrap { display: block; min-width: 16em; }
th:first-child, td:first-child { min-width: 6.5em; }
tr.hi td { background: var(--color-paper-3); color: var(--color-ink); }
tr.hi td:first-child { box-shadow: inset 4px 0 0 var(--color-accent); }
th:first-child, td:first-child { position: sticky; left: 0; background: var(--color-paper); z-index: 1; }
tr.hi td:first-child { background: var(--color-paper-3); }
td small { display: block; color: var(--color-muted); font-family: var(--font-body); }

.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-top: var(--rule-bar) solid var(--color-rule-2); }
.stats > div { padding: var(--space-md) var(--space-md) var(--space-md) 0; border-bottom: var(--rule-hair) solid var(--color-rule); min-width: 0; }
.stats dt { font-size: var(--text-sm); color: var(--color-muted); }
.stats dd { margin: var(--space-2xs) 0 0; }
.stat-v { display: block; font: 500 var(--text-xl)/1.15 var(--font-outlier); font-variant-numeric: tabular-nums; color: var(--color-ink); }
.stats small { display: block; margin-top: var(--space-2xs); font-size: var(--text-xs); color: var(--color-muted); }
.stats .flag .stat-v { display: inline-block; background: var(--color-accent); color: var(--color-accent-ink); padding: 0 var(--space-xs); border-radius: var(--radius-card); }

.tag { display: inline-block; font: 500 var(--text-xs)/1.5 var(--font-body); color: var(--color-ink); border: var(--rule-hair) solid var(--color-rule-2); border-radius: var(--radius-card); padding: 0 var(--space-2xs); margin-left: var(--space-2xs); white-space: nowrap; vertical-align: middle; text-transform: none; letter-spacing: 0; font-weight: 500; }
.src { font-size: var(--text-xs); color: var(--color-muted); overflow-wrap: anywhere; }
.derive { margin-top: var(--space-md); border-bottom: var(--rule-hair) solid var(--color-rule); }
.derive summary { cursor: pointer; padding: var(--space-sm) 0; font-weight: 500; color: var(--color-ink); }
.derive summary:hover { text-decoration: underline; text-decoration-color: var(--color-accent-deep); }
.derive ul { margin: 0 0 var(--space-md); padding-left: 1.1em; }
.derive li + li { margin-top: var(--space-xs); }
.prose p + p { margin-top: var(--space-sm); }
.daylist { font: 500 var(--text-sm)/1.7 var(--font-outlier); color: var(--color-ink); }
.note { padding: var(--space-md) var(--space-lg); background: var(--color-paper-2); border-top: var(--rule-bar) solid var(--color-rule-2); }
.note ul { margin: var(--space-xs) 0 0; padding-left: 1.1em; font-size: var(--text-sm); }
.note li + li { margin-top: var(--space-xs); }
.note .src { display: block; }

.rows { margin: 0; padding: 0; list-style: none; border-top: var(--rule-bar) solid var(--color-rule-2); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.rows > li { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 2fr) minmax(0, 1fr) minmax(0, 5fr); gap: var(--space-md); padding: var(--space-md) 0; border-top: var(--rule-hair) solid var(--color-rule); }
.rows > li:first-child { border-top: none; }
.rows .t { font-weight: 500; color: var(--color-ink); }
.rows .k { display: none; font-size: var(--text-xs); color: var(--color-muted); }
.rows .ind { font-size: var(--text-sm); }
.dir { font-weight: 500; color: var(--color-ink); }
.moat { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--gap-columns); margin: 0; padding: 0; list-style: none; }
.moat li { border-top: var(--rule-bar) solid var(--color-rule-2); padding-top: var(--space-md); min-width: 0; }
.moat h3 { margin-bottom: var(--space-xs); }

/* the course as stages: dim6 */
.stages { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; padding: 0; list-style: none; border-top: var(--rule-bar) solid var(--color-rule-2); }
.stages li { padding: var(--space-md) var(--space-md) var(--space-lg); border-left: var(--rule-hair) solid var(--color-rule); min-width: 0; }
.stages li:first-child { border-left: none; padding-left: 0; }
.stages .s-n { font: var(--display-weight) var(--text-display-s)/0.95 var(--font-display); font-variant-numeric: tabular-nums; color: var(--color-ink); }
.stages .s-n.s-range { font-size: var(--text-2xl); line-height: 1.1; }
.stages .s-t { margin-top: var(--space-xs); font-weight: 500; color: var(--color-ink); }
.stages .s-d { margin-top: var(--space-2xs); font-size: var(--text-sm); }
.stages li.live { background: var(--color-accent); color: var(--color-accent-ink); padding-left: var(--space-md); border-radius: var(--radius-card); }
.stages li.live .s-n, .stages li.live .s-t, .stages li.live .s-d { color: var(--color-accent-ink); }
.rr { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-top: var(--rule-bar) solid var(--color-rule-2); border-bottom: var(--rule-bar) solid var(--color-rule-2); }
.rr > div { padding: var(--space-md) var(--space-md) var(--space-lg); border-left: var(--rule-hair) solid var(--color-rule); min-width: 0; }
.rr > div:first-child { border-left: none; padding-left: 0; }
.rr dt { font-size: var(--text-sm); color: var(--color-muted); }
.rr dd { margin: var(--space-2xs) 0 0; }
.rr .v { display: block; font: var(--display-weight) var(--text-display-s)/0.95 var(--font-display); font-variant-numeric: tabular-nums; color: var(--color-ink); }
.rr small { display: block; margin-top: var(--space-xs); font-size: var(--text-sm); color: var(--color-ink-2); }
.rr .warn { font-weight: 500; color: var(--color-ink); }

.band { margin-top: var(--section-gap); background: var(--color-ink); color: var(--color-paper); padding-block: var(--space-2xl); }
.footer { margin-top: var(--section-gap); padding-block: var(--space-xl) var(--space-2xl); border-top: var(--rule-bar) solid var(--color-rule-2); font-size: var(--text-sm); color: var(--color-muted); }
.footer-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: var(--gap-columns); }
.footer p + p { margin-top: var(--space-xs); }
.footer .disclaimer { color: var(--color-ink); font-weight: 500; }

@media (max-width: 72rem) {
  .figs { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .figs > div:nth-child(4) { border-left: none; padding-left: 0; }
}
@media (max-width: 60rem) {
  :root { --gutter: 24px; --section-gap: 96px; }
  .hero-grid, .dim-head, .split, .split-wide, .trio, .footer-grid { grid-template-columns: minmax(0, 1fr); }
  .moat, .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .nav-links { display: none; }
  .mode-toggle { margin-left: auto; }
  .ladder-track { height: 380px; }
  .rows > li { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .rows .k { display: block; }
  .stages { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stages li:nth-child(3) { border-left: none; padding-left: 0; }
  .stages li.live:nth-child(3) { padding-left: var(--space-md); }
}
@media (max-width: 40rem) {
  :root { --gutter: 16px; --section-gap: 72px; --gap-columns: 16px; }
  .figs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .figs > div:nth-child(4) { border-left: var(--rule-hair) solid var(--color-rule); padding-left: var(--space-md); }
  .figs > div:nth-child(odd) { border-left: none; padding-left: 0; }
  .moat, .stats, .rr { grid-template-columns: minmax(0, 1fr); }
  .rr > div { border-left: none; padding-left: 0; border-top: var(--rule-hair) solid var(--color-rule); }
  .rows > li { grid-template-columns: minmax(0, 1fr); gap: var(--space-2xs); }
  .meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ladder { padding: var(--space-md); }
  .ladder-track { margin-left: 72px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
@media print { .nav, .actions { display: none; } }
"""

HEAD_JS = ("try{var m=localStorage.getItem('eq6834-mode');"
           "if(m==='dark'||m==='light')document.documentElement.dataset.mode=m;}catch(e){}")

JS = r"""
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('mode-toggle');
  function current() {
    return root.dataset.mode || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function label() { if (btn) btn.textContent = current() === 'dark' ? '淺色' : '深色'; }
  if (btn) {
    btn.hidden = false;
    label();
    btn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      root.dataset.mode = next;
      try { localStorage.setItem('eq6834-mode', next); } catch (e) {}
      label();
    });
  }
  document.querySelectorAll('.chart-wrap').forEach(function (w) { w.scrollLeft = w.scrollWidth; });
  var tip = document.createElement('div');
  tip.className = 'tip';
  tip.setAttribute('role', 'status');
  document.body.appendChild(tip);
  function show(t, x, y) {
    tip.textContent = t.getAttribute('data-tip');
    tip.classList.add('on');
    var nx = Math.max(8, Math.min(x + 14, window.innerWidth - tip.offsetWidth - 8));
    var ny = y + 16;
    if (ny + tip.offsetHeight > window.innerHeight - 8) ny = y - tip.offsetHeight - 12;
    tip.style.transform = 'translate(' + nx + 'px,' + ny + 'px)';
  }
  document.addEventListener('pointermove', function (ev) {
    var t = ev.target.closest ? ev.target.closest('[data-tip]') : null;
    if (!t) { tip.classList.remove('on'); return; }
    show(t, ev.clientX, ev.clientY);
  });
  document.addEventListener('pointerdown', function (ev) {
    var t = ev.target.closest ? ev.target.closest('[data-tip]') : null;
    if (t) show(t, ev.clientX, ev.clientY); else tip.classList.remove('on');
  });
  document.addEventListener('scroll', function () { tip.classList.remove('on'); }, { passive: true });
})();
"""


# ------------------------------------------------------------------ sections

def section(sid, num, title, verdict, body):
    return (f'<section id="{sid}" class="dim" aria-labelledby="{sid}-h"><div class="container">'
            f'<header class="dim-head"><h2 id="{sid}-h">{num} {E(title)}</h2>'
            f'<p class="verdict">{verdict}</p></header>'
            f'<div class="dim-body">{body}</div></div></section>')


def dim1(d, a):
    m, s = d["price"]["metrics"], d["price"]["series"]
    src = d["sources"]["price"]
    fsig = m["float_settling"]
    chart = kline(s, f"{a['name_zh']}日 K 線、均線與成交量，{s[0]['date']} 至 {s[-1]['date']}", spikes=m["spike_days"])
    lg = legend([("MA5", "s1"), ("MA10", "s2"), ("MA20", "s3"), ("成交量", "box"), ("爆量日", "volt")])
    verdict = (f"收盤 {fp(m['close'])}，低於 MA20 {fn(m['ma20'], 2)} 達 {fpct(m['bias_ma20_pct'])}；均線{ALIGN_ZH[m['alignment']]}，"
               f"近 1 個月由 {fp(m['w20_high'])} 跌到 {fp(m['w20_low'])}，量縮 {fsig['dryup_count']} 天，賣壓在退但趨勢未轉。")
    st = stats([
        ("近 1 個月高點", fp(m["w20_high"]), m["w20_high_date"]),
        ("近 1 個月低點", fp(m["w20_low"]), m["w20_low_date"]),
        ("5、10、20 日均線", f"{fn(m['ma5'], 2)} / {fn(m['ma10'], 2)} / {fn(m['ma20'], 2)}", f"乖離 MA20 {fpct(m['bias_ma20_pct'])}"),
        ("均線排列", ALIGN_ZH[m["alignment"]], f"均線價差 {fn(m['ma_spread_pct'], 1)}%，{'糾結' if m['squeeze'] else '未糾結'}（門檻 2%）"),
        ("20 日均量", f"{fn(m['vol_avg20_lots'])} 張", f"爆量 &gt; {fn(m['vol_avg20_lots'] * 1.5)} 張，量縮 &lt; {fn(m['vol_avg20_lots'] * 0.6)} 張"),
        ("浮額沉澱", "成立" if fsig["signal"] else "未成立",
         f"融資餘額 {fsg(fsig['margin_change'], 0, ' 張')}，量縮 {fsig['dryup_count']} 天（門檻 5 天且融資減少）"),
    ])
    days = (f'<div class="split"><div class="block"><h3>爆量日 {len(m["spike_days"])} 天</h3><p class="daylist">{E("、".join(m["spike_days"]) or "無")}</p></div>'
            f'<div class="block"><h3>量縮日 {len(m["dryup_days"])} 天</h3><p class="daylist">{E("、".join(m["dryup_days"]) or "無")}</p></div></div>')
    cap = (f"資料：FinMind TaiwanStockPrice，{src['range'][0]} 至 {src['range'][1]}，日 K 共 {len(s)} 個交易日。"
           "空心 K 棒收高於開，實心收低於開；黃綠量柱為爆量日（量 &gt; 1.5 × 20 日均量）。")
    return section("dim1", "01", "價量與均線", verdict, figure(chart, cap, lg) + st + days)


def dim2(d, a):
    inst, fh, mg = d["institutional"], d["foreign_holding"], d["margin"]
    src = d["sources"]
    c, zone = inst["cum"], inst["cost_zone"]
    r0 = src["institutional"]["range"]
    cum = lines_chart([{"x": r["date"][5:], "f": r["foreign_cum"], "t": r["trust_cum"], "d": r["dealer_cum"]} for r in inst["daily"]],
                      "三大法人近 20 日累計買賣超（張）",
                      [("f", "外資累計", "s1"), ("t", "投信累計", "s2"), ("d", "自營商累計", "s3")], lambda v: fn(v), H=280, zero=True)
    daily = bars_chart([(r["date"][5:], r["foreign"]) for r in inst["daily"]], "外資每日買賣超（張）",
                       lambda v: fn(v), lambda x, v: f"{x}　外資 {fsg(v, 0, ' 張')}", H=220, hi_last=False)
    fhc = lines_chart([{"x": r["date"][5:], "v": r["ratio"]} for r in fh["series"]], "外資持股比率（%）",
                      [("v", "外資持股", "s1")], lambda v: f"{v:.1f}%", H=240, W=380)
    mgc = lines_chart([{"x": r["date"][5:], "m": r["margin"]} for r in mg["series"]], "融資餘額（張）",
                      [("m", "融資餘額", "s2")], lambda v: fn(v), H=240, W=380)
    shc = lines_chart([{"x": r["date"][5:], "s": r["short"]} for r in mg["series"]], "融券餘額（張）",
                      [("s", "融券餘額", "s3")], lambda v: fn(v), H=240, W=380)
    verdict = (f"外資近 1 個月累計 {fsg(c['foreign'], 0, ' 張')}，持股比率由 {fh['first']:.2f}% 降至 {fh['last']:.2f}%；"
               f"融資減少 {fn(-mg['margin_change'])} 張（{fpct(mg['margin_change_pct'])}），短線籌碼在清洗。")
    zone_v = (f"{fp(zone['low'])} 至 {fp(zone['high'])}" if zone else "無")
    zone_n = (f"{GROUP_ZH[zone['group']]} {zone['days']} 個買超日量加權均價 {fp(zone['price'])} ± 2%" if zone
              else "外資與投信買超日皆少於 3 天")
    st = stats([
        ("外資累計", f"{fsg(c['foreign'], 0, ' 張')}", f"投信 {fsg(c['trust'], 0, ' 張')}，自營商 {fsg(c['dealer'], 0, ' 張')}"),
        ("外資持股比率", f"{fh['last']:.2f}%", f"首日 {fh['first']:.2f}%，高 {fh['high']:.2f}%，低 {fh['low']:.2f}%，變化 {fsg(fh['change_pp'], 2, ' pp')}"),
        ("法人成本區", zone_v, zone_n),
        ("融資餘額", f"{fn(mg['margin_last'])} 張", f"由 {fn(mg['margin_first'])} 張，{fsg(mg['margin_change'], 0, ' 張')}（{fpct(mg['margin_change_pct'])}）"),
        ("融券餘額", f"{fn(mg['short_last'])} 張", f"由 {fn(mg['short_first'])} 張，{fsg(mg['short_change'], 0, ' 張')}（{fpct(mg['short_change_pct'])}）"),
        ("券資比", f"{mg['short_margin_ratio_pct']:.2f}%", f"水位{LEVEL_ZH[mg['short_margin_level']]}（&lt; 5% 低，5% 至 20% 中，&gt; 20% 高）"),
    ])
    rows = [(r["date"], fsg(r["foreign"]), fsg(r["trust"]), fsg(r["dealer"]), fsg(r["foreign_cum"]), fsg(r["trust_cum"]), fsg(r["dealer_cum"]))
            for r in inst["daily"]]
    tbl = table([("日期", False), ("外資", True), ("投信", True), ("自營商", True), ("外資累計", True), ("投信累計", True), ("自營商累計", True)],
                rows, hi_rows=(len(rows) - 1,))
    rf, rm = src["foreign_holding"]["range"], src["margin"]["range"]
    body = (
        '<div class="split">'
        + figure(cum, f"資料：FinMind TaiwanStockInstitutionalInvestorsBuySell，{r0[0]} 至 {r0[1]}；單位：張。外資含外資自營商，自營商含避險。",
                 legend([("外資", "s1"), ("投信", "s2"), ("自營商", "s3")]))
        + figure(daily, f"資料：FinMind TaiwanStockInstitutionalInvestorsBuySell，{r0[0]} 至 {r0[1]}；外資每日淨買賣（張），零線以下為賣超。")
        + "</div>" + st
        + '<div class="trio">'
        + figure(fhc, f"資料：FinMind TaiwanStockShareholding，{rf[0]} 至 {rf[1]}；外資持股比率（%）。")
        + figure(mgc, f"資料：FinMind TaiwanStockMarginPurchaseShortSale，{rm[0]} 至 {rm[1]}；融資餘額（張）。")
        + figure(shc, f"資料：FinMind TaiwanStockMarginPurchaseShortSale，{rm[0]} 至 {rm[1]}；融券餘額（張）。")
        + "</div>"
        + figure(tbl, f"資料：FinMind TaiwanStockInstitutionalInvestorsBuySell，{r0[0]} 至 {r0[1]}；每日淨買賣與累計（張）。", cls="table-wrap")
    )
    return section("dim2", "02", "籌碼結構", verdict, body)


def ext_facts(a):
    return "".join(
        f'<li>{E(f["text"])}<span class="src">來源：<a href="{E(f["url"])}" rel="noopener">{E(f["source"])}</a>，{E(f["date"])}</span></li>'
        for f in a["external_facts"])


def dim3(d, a):
    rev, fin, src = d["revenue"], d["financials"], d["sources"]
    last = rev["last12"][-1]
    q4 = fin["quarters"][-4:]
    rr24 = src["revenue"]["range"]
    revc = bars_chart([(r["period"], r["revenue"] / 1e8) for r in rev["series24"]], "月營收（億元）",
                      lambda v: f"{v:,.1f}", lambda x, v: f"{x}　營收 {v:,.2f} 億元", W=660)
    yoyc = bars_chart([(r["period"], r["yoy_pct"]) for r in rev["last12"]], "月營收年增率（%）",
                      lambda v: f"{v:.0f}%", lambda x, v: f"{x}　YoY {fpct(v)}", H=220, W=660)
    verdict = (f"{rev['latest_period'][:4]} 年 1 至 {int(rev['latest_period'][5:])} 月營收 {yi(rev['ytd'])} 億元，年增 {fpct(rev['ytd_yoy_pct'])}；"
               f"{last['period']} 單月年增 {fpct(last['yoy_pct'])}，最新季營業利益率 {q4[-1]['operating_margin_pct']:.2f}%。")
    qrows = [(q["quarter"], yi(q["revenue"]), f"{q['eps']:.2f}", f"{q['gross_margin_pct']:.2f}%", f"{q['operating_margin_pct']:.2f}%",
              yi(q["non_operating"]), fn(q["dsi_days"], 1)) for q in fin["quarters"]]
    qtbl = table([("季度", False), ("營收（億）", True), ("EPS（元）", True), ("毛利率", True), ("營益率", True), ("業外（億）", True), ("DSI（天）", True)],
                 qrows, hi_rows=tuple(range(len(qrows) - 4, len(qrows))))
    mrows = [(r["period"], yi(r["revenue"]), fpct(r["mom_pct"]), fpct(r["yoy_pct"])) for r in rev["last12"]]
    mtbl = table([("月份", False), ("營收（億）", True), ("MoM", True), ("YoY", True)], mrows, hi_rows=(len(mrows) - 1,))
    cc, eq = fin["cash_conversion"], a["earnings_quality"]
    st = stats([
        ("累計營收（YTD）", f"{yi(rev['ytd'])} 億", f"去年同期 {yi(rev['ytd_prev'])} 億，YoY {fpct(rev['ytd_yoy_pct'])}"),
        ("最新月營收", f"{yi(last['revenue'])} 億", f"{last['period']}，MoM {fpct(last['mom_pct'])}，YoY {fpct(last['yoy_pct'])}"),
        ("近四季 EPS", f"{fin['ttm_eps']:.2f} 元", f"{fin['last4'][0]} 至 {fin['last4'][-1]} 加總"),
        ("DSI（最新季）", f"{fn(q4[-1]['dsi_days'], 1)} 天", f"前一季 {fn(q4[-2]['dsi_days'], 1)} 天"),
        ("現金轉換率", f"{cc['ratio']:.2f}x" if cc else "無資料",
         f"TTM 營業現金流 {yi(cc['ttm_ocf'])} 億 ÷ 稅後淨利 {yi(cc['ttm_net_income'])} 億" if cc else ""),
        ("每股淨值", f"{fin['bvps_latest']:.2f} 元", f"{fin['latest_quarter']}，股數 {fn(fin['shares_outstanding'] / 1e3)} 張"),
    ])
    gaps = ""
    if d["gaps"]:
        gaps = ('<aside class="note" aria-label="資料缺口"><p><b>資料缺口</b></p><ul>'
                + "".join(f"<li>{E(g)}</li>" for g in d["gaps"]) + "</ul></aside>")
    fsrc = src["financials"]
    body = (
        gaps
        + '<div class="split-wide"><div class="stack">'
        + figure(revc, f"資料：FinMind TaiwanStockMonthRevenue，{rr24[0]} 至 {rr24[1]}；黃綠為最新月。")
        + figure(yoyc, f"資料：FinMind TaiwanStockMonthRevenue，{rev['last12'][0]['period']} 至 {rev['last12'][-1]['period']}；單月營收年增率。")
        + "</div>"
        + figure(mtbl, f"資料：FinMind TaiwanStockMonthRevenue，{rev['last12'][0]['period']} 至 {rev['last12'][-1]['period']}。", cls="table-wrap")
        + "</div>"
        + st
        + figure(qtbl, f"資料：FinMind {E(fsrc['dataset'])}，{fsrc['range'][0]} 至 {fsrc['range'][1]}；淺底為近四季。"
                 "DSI =（期初＋期末存貨）÷ 2 ÷ 當季營業成本 × 91。", cls="table-wrap")
        + f'<div class="split"><div class="prose block"><h3>盈餘品質：{E(eq["focus"])} {judge()}</h3><p>{E(eq["text"])}</p>'
        + f'<p class="src">依據：{E(eq["basis"])}</p></div>'
        + f'<aside class="note"><p><b>外部資訊</b>（FinMind 未收錄的事實，各附來源與日期）</p><ul>{ext_facts(a)}</ul></aside></div>'
    )
    return section("dim3", "03", "營運與財務", verdict, body)


def dim4(d, a, x):
    val, peers = d["valuation"], d["peers"]
    vsrc = d["sources"]["valuation"]
    per, pbr = val["PER"], val["PBR"]
    method = a["valuation_method"]
    mb = val[method]

    def band(key, fmt):
        b = val[key]
        pts = [{"x": p["date"][:7], "v": p["v"]} for p in b["series"] if (p["v"] > 0 or key != "PER")]
        refs = [(k.upper(), b[k]) for k in ("p25", "p50", "p75", "p90") if b[k] <= max(p["v"] for p in pts) * 1.15]
        return lines_chart(pts, f"5 年 {key} 與分位", [("v", key, "s1")], fmt, H=260, refs=refs)

    up_word = "上漲" if x["base"]["upside_pct"] >= 0 else "下跌"
    verdict = (f"PER {per['current']:.2f}x 落在 5 年第 {per['current_percentile']:.1f} 百分位，PBR {pbr['current']:.2f}x 落在第 {pbr['current_percentile']:.1f} 百分位；"
               f"基本情境目標價 {fp(x['base']['target'])}，潛在{up_word} {fpct(x['base']['upside_pct'])}，評等{x['rating_zh']}。")
    btbl = table([("指標", False), ("目前", True), ("百分位", True), ("P10", True), ("P25", True), ("P50", True), ("P75", True), ("P90", True)],
                 [(k, fmult(val[k]["current"]), f"{val[k]['current_percentile']:.1f}%", *(fmult(val[k][p]) for p in ("p10", "p25", "p50", "p75", "p90")))
                  for k in ("PER", "PBR")])
    reasons = {p["code"]: p for p in a["peers"]}
    prow = []
    for r in peers["rows"]:
        if r["code"] == CODE:
            prow.append((f"{CODE} {E(a['name_zh'])}", fmult(r["PER"]), fmult(r["PBR"]), f"{r['dividend_yield']:.2f}%", "本報告標的"))
        else:
            p = reasons[r["code"]]
            prow.append((f"{r['code']} {E(p['name'])}", fmult(r["PER"]) if r["PER"] else "無資料", fmult(r["PBR"]),
                         f"{r['dividend_yield']:.2f}%", f'<span class="wrap">{E(p["reason"])} {judge()}</span>'))
    md = peers["median"]
    prow.append(("同業中位數", fmult(md["PER"]), fmult(md["PBR"]), f"{md['dividend_yield']:.2f}%", f"不含{E(a['name_zh'])}"))
    ptbl = table([("公司", False), ("PER", True), ("PBR", True), ("殖利率", True), ("選擇理由", False)], prow, hi_rows=(0,))
    unit = "前瞻 EPS" if method == "PER" else "BVPS"
    srow = []
    for s in x["scenarios"]:
        im = s["implied"]
        imp = (f'<span data-implied="{s["name"]}">{fmult(im["value"])}</span><small>{METRIC_ZH[im["metric"]]}{POS_ZH[im["position"]]}</small>'
               if im else "無資料")
        srow.append((f"{s['label']}（{s['name']}）", f"{s['eps']:.2f}", fmult(s["multiple"]), fp(s["target"]), fpct(s["upside_pct"]),
                     imp, f"{s['probability']}%", f'<span class="wrap">{E(s["assumptions"])}</span>'))
    srow.append(("機率加權", "", "", fp(x["weighted_target"]), fpct(x["weighted_upside_pct"]), "", "100%", ""))
    other = "PBR" if method == "PER" else "PER"
    stbl = table([("情境", False), (unit, True), (method, True), ("目標價", True), ("潛在漲跌", True), (f"隱含 {other}", True), ("機率", True), ("假設", False)],
                 srow, hi_rows=(1,))
    basis = "".join(f"<li><b>{E(s['label'])}：</b>{E(s['basis'])}</li>" for s in x["scenarios"])
    r = vsrc["range"]
    body = (
        '<div class="split">'
        + figure(band("PER", lambda v: f"{v:.0f}x"), f"資料：FinMind TaiwanStockPER，{r[0]} 至 {r[1]}；剔除 PER ≤ 0，分位以全部 {per['n']} 日計算，每週取樣繪圖；高於圖頂的分位線不畫。")
        + figure(band("PBR", lambda v: f"{v:.1f}x"), f"資料：FinMind TaiwanStockPER，{r[0]} 至 {r[1]}；分位以全部 {pbr['n']} 日計算。")
        + "</div>"
        + figure(btbl, f"資料：FinMind TaiwanStockPER，{r[0]} 至 {r[1]}；百分位 = 5 年序列中小於等於目前值的天數占比。", cls="table-wrap")
        + figure(ptbl, f"資料：FinMind TaiwanStockPER，{peers['rows'][0]['date']} 最新一筆；同業選擇為分析師判斷。", cls="table-wrap")
        + f'<div class="block"><h3>三情境目標價（12 個月，{E(method)} 法）{judge()}</h3>'
        + figure(stbl, f"倍數錨定依 FinMind TaiwanStockPER {r[0]} 至 {r[1]} 的 {method} 分位：悲觀 ≤ P25（{fmult(mb['p25'])}），基本介於 P25 至 P75，樂觀 ≤ P90（{fmult(mb['p90'])}）。"
                 f"目標價 = {unit} × {method}，依跳動單位取整；隱含 {other} = 目標價 ÷ {'每股淨值' if method == 'PER' else 'TTM EPS'}。", cls="table-wrap")
        + f'<details class="derive"><summary>推導依據：方法、三情境的 EPS 與倍數 {judge()}</summary><p class="src">{E(a["valuation_method_basis"])}</p><ul class="src">{basis}</ul></details></div>'
        + stats([
            ("投資評等", f"{x['rating_zh']}（{x['rating_en']}）", "依基本情境潛在漲跌：&gt; +15% 買進，−5% 至 +15% 中立，&lt; −5% 賣出"),
            ("基本情境目標價", fp(x["base"]["target"]), f"{x['base']['eps']:.2f} × {fmult(x['base']['multiple'])}，潛在漲跌 {fpct(x['base']['upside_pct'])}"),
            ("機率加權目標價", fp(x["weighted_target"]), f"潛在漲跌 {fpct(x['weighted_upside_pct'])}"),
        ])
    )
    return section("dim4", "04", "估值與目標價", verdict, body)


def dim5(a):
    moat = '<ul class="moat">' + "".join(
        f'<li><h3>{E(m["title"])}</h3><p>{E(m["text"])}</p><p class="src">依據：{E(m["basis"])}</p></li>' for m in a["moat"]) + "</ul>"

    def rows(items):
        return '<ul class="rows">' + "".join(
            f'<li><div><span class="t">{E(i["title"])}</span><p class="src">依據：{E(i["basis"])}</p></div>'
            f'<div><span class="k">預期時點</span>{E(i["timing"])}</div>'
            f'<div><span class="k">方向</span><span class="dir">{E(i["direction"])}</span></div>'
            f'<div class="ind"><span class="k">觀察指標</span>{E(i["indicator"])}</div></li>' for i in items) + "</ul>"

    body = (f'<div class="block"><h3>護城河 {judge()}</h3>{moat}</div>'
            f'<div class="block"><h3>催化劑 {len(a["catalysts"])} 項 {judge()}</h3>{rows(a["catalysts"])}</div>'
            f'<div class="block"><h3>風險 {len(a["risks"])} 項 {judge()}</h3>{rows(a["risks"])}</div>')
    return section("dim5", "05", "催化劑與風險", E(a["dim5_verdict"]), body)


def rr_item(label, hook, v, status, formula):
    if v is None:
        note = f'<span class="warn">{E(dv.SETUP_STATUS_ZH[status])}</span>'
    else:
        note = (f'<span class="warn">不具交易吸引力</span>，' if v < 1.5 else "") + formula
    return f'<div><dt>{E(label)}</dt><dd><span class="v" data-rr="{hook}">{frr(v)}</span><small>{note}</small></dd></div>'


def dim6(d, a, x):
    m = d["price"]["metrics"]
    s = d["price"]["series"][-60:]
    lines = [("t2", "T2", x["t2"]), ("t1", "T1", x["t1"]), ("entry", "Entry", x["entry"]), ("sl", "SL", x["hard_stop"])]
    chart = kline(s, "近 60 日 K 線與 Entry、T1、T2、SL 價位", spikes=m["spike_days"], lines=lines, H=460)
    zone = d["institutional"]["cost_zone"]
    zone_note = ("MA10 至 MA20 區間與法人成本區重疊，取交集" if x["zone_source"] == "overlap"
                 else (f"法人成本區 {fp(zone['low'])} 至 {fp(zone['high'])} 與 MA10 至 MA20 區間未重疊，改用均線區間" if zone
                       else "法人成本區不存在，改用均線區間"))
    pos = ("收盤低於進場區" if x["close"] < x["zone_low"] else "收盤在進場區內" if x["close"] <= x["zone_high"] else "收盤高於進場區")
    stages = [
        ("sl", fp(x["hard_stop"]), "硬停損 SL",
         "最大量日低點與 MA20 × 0.97 中最接近 Entry 且低於區間下緣者" if x["hard_stop_source"] == "candidate" else "進場區下緣 × 0.95"),
        ("entry", f"{fp(x['zone_low'])} 至 {fp(x['zone_high'])}", "回檔進場區", f"{zone_note}；Entry {fp(x['entry'])} 取中點"),
        ("t1", fp(x["t1"]), "T1 技術目標", "60 日最高價" if x["t1"] == m["high60"] else "Entry + 0.618 × 60 日振幅"),
        ("t2", fp(x["t2"]), "T2 波段目標", "60 日低點 + 1.618 × 振幅，以樂觀目標價為上限"),
    ]
    live = "entry" if x["zone_low"] <= x["close"] <= x["zone_high"] else None
    stg = '<ol class="stages">' + "".join(
        f'<li class="{"live" if k == live else ""}"><div class="s-n{" s-range" if "至" in v else ""}">{v}</div><div class="s-t">{E(t)}</div><p class="s-d">{E(dsc)}</p></li>'
        for k, v, t, dsc in stages) + "</ol>"
    swing = table([("項目", False), ("價位", True), ("條件與計算", False)], [
        ("回檔進場區", f"{fp(x['zone_low'])} 至 {fp(x['zone_high'])}", f"{E(zone_note)}；{pos}（收盤 {fp(x['close'])}）"),
        ("進場價 Entry", fp(x["entry"]), "進場區中點"),
        ("突破觸發價", fp(x["trigger"]), f"60 日最高價（{m['high60_date']}），當日量需 &gt; {fn(x['trigger_volume_lots'])} 張（1.5 × 20 日均量）"),
        ("T1 技術目標", fp(x["t1"]), "60 日最高價" if x["t1"] == m["high60"] else "Entry + 0.618 ×（60 日高 − 60 日低）"),
        ("T2 波段目標", fp(x["t2"]), "min（60 日低 + 1.618 × 振幅，樂觀目標價）"),
        ("硬停損 SL", fp(x["hard_stop"]), "最大量日低點或 MA20 × 0.97，取最接近 Entry 且低於區間下緣者" if x["hard_stop_source"] == "candidate" else "進場區下緣 × 0.95"),
        ("突破停損", fp(x["breakout_stop"]), "突破觸發價 × 0.95"),
    ], hi_rows=(1,))
    bear = next(sc for sc in x["scenarios"] if sc["name"] == "Bear")
    hold = table([("項目", False), ("價位", True), ("說明", False)], [
        ("合理買進價", fp(x["fair_buy"]), "Base 目標價 ÷ 1.15；收盤低於此價，評等轉為買進"),
        ("Base 目標價", fp(x["base"]["target"]), f"12 個月，潛在漲跌 {fpct(x['base']['upside_pct'])}"),
        ("Bear 目標價", fp(bear["target"]), f"12 個月，潛在漲跌 {fpct(bear['upside_pct'])}"),
    ], hi_rows=(0,))
    rr = ('<dl class="rr">'
          + rr_item("回檔 R:R", "pullback", x["rr_pullback"], x["pullback_status"], "(T2 − Entry) ÷ (Entry − SL)")
          + rr_item("突破 R:R", "breakout", x["rr_breakout"], x["breakout_status"], "(T2 − 觸發價) ÷ (觸發價 − 突破停損)")
          + rr_item("長線持有 R:R", "hold", x["rr_hold"], x["hold_status"], "(Base − 收盤) ÷ (收盤 − Bear)")
          + "</dl>")
    brk = '<ul class="rows">' + "".join(
        f'<li><div><span class="t">{E(b["condition"])}</span></div><div><span class="k">門檻</span>{E(b["threshold"])}</div>'
        f'<div></div><div class="ind"><span class="k">觀察資料集</span><span class="mono">{E(b["dataset"])}</span></div></li>'
        for b in a["thesis_breakers"]) + "</ul>"
    verdict = f"{x['action_zh']}：{E(x['action_note'])}。" + E(a["dim6_verdict"])
    body = (
        stg
        + figure(chart, f"資料：FinMind TaiwanStockPrice，{s[0]['date']} 至 {s[-1]['date']}；水平線為 T2、T1、Entry 與虛線 SL。",
                 legend([("Entry", "ink"), ("T1", "s1"), ("T2", "s2"), ("SL", "s3"), ("爆量日", "volt")]))
        + rr
        + f'<div class="block"><h3>波段層（數週）</h3>' + figure(swing, f"資料：FinMind TaiwanStockPrice、TaiwanStockInstitutionalInvestorsBuySell，{s[0]['date']} 至 {s[-1]['date']}。", cls="table-wrap") + "</div>"
        + f'<div class="block"><h3>持有層（12 個月）{judge()}</h3>' + figure(hold, f"Base 與 Bear 目標價見估值章節；收盤取自 FinMind TaiwanStockPrice {d['asof']}。", cls="table-wrap") + "</div>"
        + f'<div class="block"><h3>論點失效條件 {judge()}</h3>{brk}</div>'
    )
    return section("dim6", "06", "交易部位與風控", verdict, body)


# ------------------------------------------------------------------ hero

def ladder_html(d, x):
    """Every level of the plan on one price scale; labels are spread so none overlap."""
    sc = {s["name"]: s for s in x["scenarios"]}
    levels = [
        (sc["Bull"]["target"], "Bull 目標"), (sc["Base"]["target"], "Base 目標"), (x["t2"], "T2"),
        (x["trigger"], "突破觸發"), (x["fair_buy"], "合理買進價"), (x["close"], "收盤"),
        (x["entry"], "Entry"), (x["hard_stop"], "SL"), (sc["Bear"]["target"], "Bear 目標"),
    ]
    merged = {}
    for v, lab in levels:
        merged.setdefault(v, []).append(lab)
    vs = sorted(merged, reverse=True)
    hi, lo = vs[0], vs[-1]
    pad = (hi - lo) * 0.02
    pct = lambda v: (hi + pad - v) / (hi - lo + 2 * pad) * 100  # noqa: E731
    gap = min(100 / len(vs), 5.2)
    lab = [pct(v) for v in vs]
    for _ in range(200):
        moved = False
        for i in range(len(lab) - 1):
            over = gap - (lab[i + 1] - lab[i])
            if over > 1e-6:
                lab[i] -= over / 2
                lab[i + 1] += over / 2
                moved = True
        lab = [min(max(v, 0.0), 100.0) for v in lab]
        if not moved:
            break
    zt, zb = pct(x["zone_high"]), pct(x["zone_low"])
    out = [f'<div class="zone" style="top:{zt:.2f}%;height:{max(zb - zt, 0.8):.2f}%" aria-hidden="true"></div>']
    for v, lp in zip(vs, lab):
        now = " now" if "收盤" in merged[v] else ""
        tip = f"{'、'.join(merged[v])} {fp(v)}，相對收盤 {fpct((v / x['close'] - 1) * 100)}"
        lo_, hi_ = sorted((pct(v), lp))
        if hi_ - lo_ > 0.4:
            out.append(f'<div class="leader" style="top:{lo_:.2f}%;height:{hi_ - lo_:.2f}%" aria-hidden="true"></div>')
        out.append(f'<div class="tick{now}" style="top:{pct(v):.2f}%" aria-hidden="true"></div>'
                   f'<div class="rung{now}" style="top:{lp:.2f}%" data-tip="{E(tip)}">'
                   f'<span class="rung-p">{fp(v)}</span><span class="rung-l">{E("、".join(merged[v]))}</span></div>')
    return "".join(out)


def build(d, a):
    x = dv.derive(d, a)
    gen = date.today().isoformat()
    up_word = "潛在上漲" if x["base"]["upside_pct"] >= 0 else "潛在下跌"
    name = a["name_zh"]
    nav_items = [("dim1", "價量"), ("dim2", "籌碼"), ("dim3", "財務"), ("dim4", "估值"), ("dim5", "催化劑"), ("dim6", "交易")]
    nav = ('<nav class="nav" aria-label="報告章節"><div class="container nav-inner">'
           f'<a class="wordmark" href="#top">{E(name)} {CODE}</a><ul class="nav-links">'
           + "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in nav_items)
           + '</ul><button class="mode-toggle" id="mode-toggle" type="button" hidden>深色</button></div></nav>')
    hero = f"""
<header class="hero" id="top"><div class="container">
  <div class="hero-grid">
    <div>
      <h1><span class="co">{E(name)} {CODE}</span><span class="call" data-kpi="action">{E(x['action_zh'])}</span></h1>
      <p class="lead">{E(x['action_note'])}。</p>
      <div class="actions">
        <a class="btn btn--primary" href="#dim6">看交易計畫</a>
        <a class="btn" href="#dim4">看估值推導</a>
      </div>
      <dl class="meta">
        <div><dt>公司</dt><dd>{E(name)}（{E(a['name_en'])}）</dd></div>
        <div><dt>市場</dt><dd>{MARKET_ZH[a['market']]} {CODE}</dd></div>
        <div><dt>產業</dt><dd>{E(a['industry'])}</dd></div>
        <div><dt>資料日</dt><dd class="mono">{d['asof']}</dd></div>
      </dl>
    </div>
    <figure class="ladder" aria-label="交易計畫價位階梯">
      <div class="ladder-track">{ladder_html(d, x)}</div>
      <figcaption>價位階梯：收盤取自 FinMind TaiwanStockPrice {d['asof']}，其餘價位由方法論推算；軸上綠段為回檔進場區，細線連接偏移的標籤與實際價位。</figcaption>
    </figure>
  </div>
  <dl class="figs">
    <div><dt>收盤價</dt><dd data-kpi="close">{fp(x['close'])}</dd><small>{d['asof']}</small></div>
    <div><dt>投資評等</dt><dd data-kpi="rating">{x['rating_zh']}</dd><small>12 個月評等</small></div>
    <div><dt>Base 目標價</dt><dd data-kpi="target">{fp(x['base']['target'])}</dd><small>{x['base']['eps']:.2f} × {fmult(x['base']['multiple'])}</small></div>
    <div><dt>{up_word}</dt><dd data-kpi="upside">{fpct(x['base']['upside_pct'])}</dd><small>機率加權 {fp(x['weighted_target'])}</small></div>
    <div><dt>回檔 R:R</dt><dd class="{'small-fig' if x['rr_pullback'] is None else ''}" data-kpi="rr">{frr(x['rr_pullback'])}</dd><small>{E(dv.SETUP_STATUS_ZH[x['pullback_status']]) if x['rr_pullback'] is None else ('不具交易吸引力' if x['rr_pullback'] < 1.5 else 'Entry ' + fp(x['entry']) + '，SL ' + fp(x['hard_stop']))}</small></div>
    <div><dt>資料日</dt><dd class="small-fig" data-kpi="asof">{d['asof']}</dd><small>產生 {gen}</small></div>
  </dl>
</div></header>"""
    footer = f"""
<footer class="footer"><div class="container footer-grid">
  <div><p><b>{E(name)}（{CODE}）投資決策報告</b></p><p>資料日 <span class="mono">{d['asof']}</span>，產生日 <span class="mono">{gen}</span>，工具版本 <span class="mono">{E(d['tool_version'])}</span>。</p></div>
  <div><p>資料來源：FinMind（TaiwanStockPrice、TaiwanStockInstitutionalInvestorsBuySell、TaiwanStockShareholding、TaiwanStockMarginPurchaseShortSale、TaiwanStockMonthRevenue、TaiwanStockFinancialStatements、TaiwanStockBalanceSheet、TaiwanStockCashFlowsStatement、TaiwanStockPER）。標示「分析師判斷」者為主觀判斷；外部資訊註明來源與日期。</p>
  <p class="disclaimer">本報告僅供研究參考，不構成任何投資建議。</p></div>
</div></footer>"""
    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(name)} {CODE} 決策報告</title>
<meta name="description" content="{E(name)}（{CODE}）投資決策報告：目前動作、波段與長線交易計畫、價量、籌碼、財務、估值與風險，資料日 {d['asof']}。">
<script>{HEAD_JS}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@800&family=Albert+Sans:wght@400;500&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
{nav}
<main>
{hero}
{dim1(d, a)}
{dim2(d, a)}
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
    d, a = dv.load_work(HERE, CODE)
    doc, x = build(d, a)
    out = ROOT / dv.report_relpath(d, a)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: action={x['action_zh']} rating={x['rating_zh']} target={x['base']['target']} "
          f"upside={x['base']['upside_pct']} rr_pb={x['rr_pullback']} rr_bo={x['rr_breakout']} rr_hold={x['rr_hold']}")


if __name__ == "__main__":
    main()
