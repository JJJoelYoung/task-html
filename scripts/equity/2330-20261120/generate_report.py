#!/usr/bin/env python3
"""Generate the 2330 TSMC equity report (Hallmark theme: Brutal).

Layout and charts only: every number comes from data_2330.json,
analysis_2330.json, or derive.derive(). Run from anywhere:

  python scripts/equity/2330-20261120/generate_report.py
"""

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "tw-equity-report" / "scripts"))

import derive as dv  # noqa: E402

CODE = "2330"
d, a = dv.load_work(WORK, CODE)
x = dv.derive(d, a)
m = d["price"]["metrics"]
fin = d["financials"]
cb = fin["core_baseline"]
OUT = ROOT / dv.report_relpath(d, a)

fp, fpct, fmult, feps, frr = dv.fmt_price, dv.fmt_pct, dv.fmt_mult, dv.fmt_eps, dv.fmt_rr


def esc(s):
    return html.escape(str(s), quote=True)


URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#@!$&*+=%]+")


def linkify(text):
    """Escape text and turn each URL into a link (same URL rule as check_report.py)."""
    out, pos = [], 0
    for mt in URL_RE.finditer(text):
        url = mt.group(0).rstrip(".:!?")
        out.append(esc(text[pos:mt.start()]))
        host = re.sub(r"^www[.]", "", url.split("/")[2])
        out.append(f'<a href="{esc(url)}" rel="noopener" target="_blank">{esc(host)}</a>')
        pos = mt.start() + len(url)
    out.append(esc(text[pos:]))
    return "".join(out)


def lots(v):
    return "無資料" if v is None else f"{v:,.0f} 張"


def lots_signed(v):
    return "無資料" if v is None else f"{v:+,.0f} 張"


def yi(v):
    """NT$ amount in 億元."""
    return "無資料" if v is None else f"{v / 1e8:,.1f} 億"


def pct_plain(v, dec=1):
    return "無資料" if v is None else f"{v:.{dec}f}%"


def qlabel(q):
    y, mth = q[:4], int(q[5:7])
    return f"{y[2:]}Q{(mth - 1) // 3 + 1}"


POS_ZH = {"below_p25": "低於 P25", "p25_p75": "P25 至 P75", "p75_p90": "P75 至 P90", "above_p90": "高於 P90"}
ALIGN_ZH = {"bullish": "多頭排列", "bearish": "空頭排列", "mixed": "糾結／交錯"}
LEVEL_ZH = {"low": "低", "medium": "中", "high": "高"}
GROUP_ZH = {"foreign": "外資", "trust": "投信", "dealer": "自營商"}
MARKET_ZH = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}
VOL_ZH = {"opm_spread_gt_5pp": "近 4 季營益率差距逾 5 個百分點",
          "opm_nonpositive": "近 4 季有營益率 ≤ 0 的季度",
          "yoy_gt_50pct": "近 6 個月營收 YoY 中位數絕對值逾 50%"}


# ---------------------------------------------------------------- charts

def sx(i, n, x0, w):
    return x0 + (i + 0.5) * w / n


def spread(ys, gap, lo, hi):
    """Push label y positions at least gap apart inside [lo, hi], keeping their order."""
    if not ys:
        return []
    idx = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = [min(max(ys[i], lo), hi) for i in idx]
    for k in range(1, len(pos)):
        pos[k] = max(pos[k], pos[k - 1] + gap)
    if pos[-1] > hi:
        pos[-1] = hi
        for k in range(len(pos) - 2, -1, -1):
            pos[k] = min(pos[k], pos[k + 1] - gap)
    out = [0.0] * len(ys)
    for k, i in enumerate(idx):
        out[i] = pos[k]
    return out


def kline_svg(series, title, lines=None, zone=None, vh=420):
    """Candles + MA5/10/20/60 + volume, inline SVG. lines: [(key, label, value)]."""
    W, H = 1000, vh
    pad_l, pad_r, top = 8, 72, 14
    price_h = H * 0.64
    vol_top, vol_bot = price_h + 30, H - 30
    vol_h = vol_bot - vol_top
    n = len(series)
    vals = [s["high"] for s in series] + [s["low"] for s in series]
    for k in ("ma5", "ma10", "ma20", "ma60"):
        vals += [s[k] for s in series if s.get(k) is not None]
    if lines:
        vals += [v for _, _, v in lines]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    lo, hi = lo - span * 0.04, hi + span * 0.04
    pw = W - pad_l - pad_r

    def y(p):
        return top + (hi - p) / (hi - lo) * (price_h - top)

    vmax = max(s["volume_lots"] for s in series)
    cw = max(1.2, pw / n * 0.62)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" class="chart">']
    for t in range(5):
        p = lo + (hi - lo) * t / 4
        yy = y(p)
        parts.append(f'<line class="grid" x1="{pad_l}" x2="{W - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        if t:
            parts.append(f'<text class="axis" x="{W - pad_r + 6}" y="{yy + 5:.1f}">{fp(dv.round_tick(p))}</text>')
    parts.append(f'<line class="grid" x1="{pad_l}" x2="{W - pad_r}" y1="{vol_bot:.1f}" y2="{vol_bot:.1f}"/>')
    parts.append(f'<text class="axis" x="{W - pad_r + 6}" y="{vol_top + 12:.1f}">{vmax:,}</text>')
    if zone:
        z0, z1 = y(zone[1]), y(zone[0])
        parts.append(f'<rect class="zone" x="{pad_l}" width="{pw}" y="{z0:.1f}" height="{max(2, z1 - z0):.1f}"/>')
    for k in ("ma5", "ma10", "ma20", "ma60"):
        pts = [f"{sx(i, n, pad_l, pw):.1f},{y(s[k]):.1f}" for i, s in enumerate(series) if s.get(k) is not None]
        if pts:
            parts.append(f'<polyline class="ln {k}" points="{" ".join(pts)}"/>')
    for i, s in enumerate(series):
        cx = sx(i, n, pad_l, pw)
        cls = "up" if s["close"] >= s["open"] else "dn"
        yo, yc = y(s["open"]), y(s["close"])
        parts.append(f'<line class="wick" x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(s["high"]):.1f}" y2="{y(s["low"]):.1f}"/>')
        parts.append(f'<rect class="{cls}" x="{cx - cw / 2:.1f}" y="{min(yo, yc):.1f}" width="{cw:.1f}" height="{max(1, abs(yc - yo)):.1f}"/>')
        vh_ = s["volume_lots"] / vmax * vol_h
        parts.append(f'<rect class="vol {cls}" x="{cx - cw / 2:.1f}" y="{vol_bot - vh_:.1f}" width="{cw:.1f}" height="{vh_:.1f}"/>')
    if lines:
        ly = spread([y(v) - 6 for _, _, v in lines], 26, top + 16, price_h - 4)
        for (key, label, v), lyy in zip(lines, ly):
            yy = y(v)
            parts.append(f'<g data-line="{key}" data-value="{v}" class="lvl lvl-{key}" data-tip="{esc(label)} {fp(v)}">'
                         f'<line x1="{pad_l}" x2="{W - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                         f'<text x="{pad_l + 4}" y="{lyy:.1f}">{esc(label)} {fp(v)}</text></g>')
    step = pw / n
    for i, s in enumerate(series):
        ma = "　".join(f"{k.upper()} {fp(s[k])}" for k in ("ma5", "ma10", "ma20", "ma60") if s.get(k) is not None)
        tip = (f"{s['date']}　開 {fp(s['open'])}　高 {fp(s['high'])}　低 {fp(s['low'])}　收 {fp(s['close'])}"
               f"　量 {s['volume_lots']:,} 張" + (f"　{ma}" if ma else ""))
        parts.append(f'<rect class="hit" x="{pad_l + i * step:.1f}" y="0" width="{step:.1f}" height="{H}" data-tip="{esc(tip)}"/>')
    for i in (0, n // 2, n - 1):
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        parts.append(f'<text class="axis" text-anchor="{anchor}" x="{sx(i, n, pad_l, pw):.1f}" y="{H - 6}">{series[i]["date"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def ma_legend():
    items = [("ma5", "MA5"), ("ma10", "MA10"), ("ma20", "MA20"), ("ma60", "MA60")]
    sw = "".join(f'<li><span class="sw sw-{k}"></span>{lab}</li>' for k, lab in items)
    return f'<ul class="legend">{sw}<li><span class="sw sw-up"></span>收紅（收 ≥ 開）</li><li><span class="sw sw-dn"></span>收黑（收 &lt; 開）</li></ul>'


def bars_svg(labels, values, title, tips, unit="", vh=200, W=1000):
    """Signed vertical bars around a zero baseline."""
    H = vh
    pad_l, pad_r, top, bot = 8, 96, 12, 30
    n = len(values)
    known = [v for v in values if v is not None]
    vmax = max([0] + known)
    vmin = min([0] + known)
    if vmax == vmin:
        vmax = vmin + 1
    pw = W - pad_l - pad_r

    def y(v):
        return top + (vmax - v) / (vmax - vmin) * (H - top - bot)

    bw = min(24, pw / n * 0.7)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" class="chart">']
    ticks = (vmax, 0, vmin) if vmin < 0 else (vmax, vmax / 2, 0)
    for v in ticks:
        out.append(f'<line class="grid" x1="{pad_l}" x2="{W - pad_r}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
    for v, ly in zip(ticks, spread([y(v) + 5 for v in ticks], 24, top + 10, H - bot)):
        out.append(f'<text class="axis" x="{W - pad_r + 6}" y="{ly:.1f}">{v:,.0f}{unit}</text>')
    y0 = y(0)
    for i, v in enumerate(values):
        cx = sx(i, n, pad_l, pw)
        if v is None:
            out.append(f'<text class="axis na" text-anchor="middle" x="{cx:.1f}" y="{y0 - 4:.1f}">缺</text>')
            continue
        yy = y(v)
        cls = "bar pos" if v >= 0 else "bar neg"
        out.append(f'<rect class="{cls}" x="{cx - bw / 2:.1f}" y="{min(yy, y0):.1f}" width="{bw:.1f}" height="{max(1, abs(y0 - yy)):.1f}"/>')
    step = pw / n
    for i, t in enumerate(tips):
        out.append(f'<rect class="hit" x="{pad_l + i * step:.1f}" y="0" width="{step:.1f}" height="{H}" data-tip="{esc(t)}"/>')
    for i in (0, n - 1):
        anchor = "start" if i == 0 else "end"
        out.append(f'<text class="axis" text-anchor="{anchor}" x="{sx(i, n, pad_l, pw):.1f}" y="{H - 6}">{esc(labels[i])}</text>')
    out.append("</svg>")
    return "".join(out)


def line_svg(labels, values, title, tips, fmt, refs=None, vh=240, current=None, W=560):
    """Single-series line; refs: [(label, value)] horizontal reference lines."""
    H = vh
    pad_l, pad_r, top, bot = 8, 150, 14, 30
    n = len(values)
    vals = [v for v in values if v is not None] + [v for _, v in refs or []]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    lo, hi = lo - span * 0.06, hi + span * 0.06
    pw = W - pad_l - pad_r

    def y(v):
        return top + (hi - v) / (hi - lo) * (H - top - bot)

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" class="chart">']
    marks = refs if refs else [(None, lo + (hi - lo) * (t + 0.5) / 4) for t in range(4)]
    for lab, v in marks:
        cls = "grid" if lab is None else ("ref ref-mid" if lab == "P50" else "ref")
        out.append(f'<line class="{cls}" x1="{pad_l}" x2="{W - pad_r}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
    for (lab, v), ly in zip(marks, spread([y(v) + 5 for _, v in marks], 26, top + 10, H - bot)):
        txt = f"{lab} {fmt(v)}" if lab else fmt(v)
        out.append(f'<text class="axis" x="{W - pad_r + 6}" y="{ly:.1f}">{txt}</text>')
    seg, segs = [], []
    for i, v in enumerate(values):
        if v is None:
            if seg:
                segs.append(seg)
            seg = []
            continue
        seg.append(f"{sx(i, n, pad_l, pw):.1f},{y(v):.1f}")
    if seg:
        segs.append(seg)
    for s in segs:
        out.append(f'<polyline class="ln main" points="{" ".join(s)}"/>')
    if current is not None:
        out.append(f'<circle class="dot" cx="{sx(n - 1, n, pad_l, pw):.1f}" cy="{y(current):.1f}" r="6"/>')
    step = pw / n
    for i, t in enumerate(tips):
        out.append(f'<rect class="hit" x="{pad_l + i * step:.1f}" y="0" width="{step:.1f}" height="{H}" data-tip="{esc(t)}"/>')
    for i in (0, n - 1):
        anchor = "start" if i == 0 else "end"
        out.append(f'<text class="axis" text-anchor="{anchor}" x="{sx(i, n, pad_l, pw):.1f}" y="{H - 6}">{esc(labels[i])}</text>')
    out.append("</svg>")
    return "".join(out)


def figure(svg, caption, extra="", wide=False):
    return (f'<figure class="fig">{extra}<div class="plot{" plot--wide" if wide else ""}">{svg}</div>'
            f'<figcaption>{caption}</figcaption></figure>')


TAG_RE = re.compile(r"<[^>]+>")


def table_fig(head, rows, caption, cls=""):
    """rows: lists of cells (N(...) marks numeric); ("FULL", html, label) adds a full-width note row."""
    labels = [esc(TAG_RE.sub("", h).strip()) for h in head]
    th = "".join(f'<th scope="col">{h}</th>' for h in head)
    body = []
    for r in rows:
        if isinstance(r, tuple) and r[0] == "FULL":
            body.append(f'<tr class="full"><td colspan="{len(head)}" data-label="{esc(r[2])}">{r[1]}</td></tr>')
            continue
        cells = []
        for k, c in enumerate(r):
            num = isinstance(c, tuple)
            cells.append(f'<td{" class=" + chr(34) + "num" + chr(34) if num else ""} data-label="{labels[k]}">{c[0] if num else c}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<figure class="fig"><div class="scroll {cls}"><table class="stack"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div><figcaption>{caption}</figcaption></figure>')


def N(v):
    """Mark a table cell as numeric (tabular, right aligned)."""
    return (v,)


# ---------------------------------------------------------------- content

series = d["price"]["series"]
src = d["sources"]
asof = d["asof"]
name_zh, name_en = a["name_zh"], a["name_en"]
base, bull, bear = x["base"], next(s for s in x["scenarios"] if s["name"] == "Bull"), next(s for s in x["scenarios"] if s["name"] == "Bear")
method = a["valuation_method"]
imp_metric = "PBR" if method == "PER" else "PER"


def rng(key):
    r = src[key]["range"]
    return f"{r[0]} 至 {r[1]}"


judg = '<span class="tag">分析師判斷</span>'

# --- hero
def kpi(label, key, value, cls=""):
    return f'<div class="cell {cls}"><p class="lab">{label}</p><p class="val num" data-kpi="{key}">{esc(value)}</p></div>'


hero_cells = "".join([
    kpi("收盤價（NT$）", "close", fp(x["close"])),
    kpi("投資評等", "rating", x["rating_zh"]),
    kpi("Base 目標價", "target", fp(base["target"])),
    kpi("Base 潛在漲跌", "upside", fpct(base["upside_pct"])),
    kpi("拉回 R:R", "rr", frr(x["rr_pullback"])),
    kpi("資料日期", "asof", asof),
])

ma_cells = (
    f'<div class="cell cell--ink"><p class="lab">20 日均線，5 日斜率 {m["ma20_slope_5d"]:+,.2f}</p>'
    f'<p class="big num">{fp(m["ma20"])}</p><p class="sub">收盤距 20MA {fpct(m["bias_ma20_pct"])}</p></div>'
    f'<div class="cell cell--ink"><p class="lab">60 日均線，5 日斜率 {m["ma60_slope_5d"]:+,.2f}</p>'
    f'<p class="big num">{fp(m["ma60"])}</p><p class="sub">收盤距 60MA {fpct((x["close"] / m["ma60"] - 1) * 100)}</p></div>'
)

hero = f"""
<section class="hero container" aria-labelledby="hero-h">
  <div class="hero-top">
    <div>
      <h1 id="hero-h">{esc(name_zh)} {CODE}</h1>
      <p class="lead">{esc(name_en)}，{MARKET_ZH.get(a['market'], a['market'])}，{esc(a['industry'])}。資料截至 {asof} 收盤。</p>
    </div>
    <div class="actions"><a class="btn btn--ink" href="#dim6">看交易計畫</a><a class="btn" href="#dim4">看估值與目標價</a></div>
  </div>
  <div class="cells hero-cells">
    <div class="cell cell--act">
      <p class="lab">當前動作</p>
      <p class="act" data-kpi="action">{esc(x['action_zh'])}</p>
      <p class="note">{esc(x['action_note'])}</p>
    </div>
    {ma_cells}
  </div>
  <div class="cells kpi-cells" aria-label="關鍵數字">{hero_cells}</div>
  <p class="gapnote">資料缺口：{('、'.join(esc(g) for g in d['gaps'])) if d['gaps'] else '本次 FinMind 抓取無缺口。'}</p>
</section>
"""

# --- dim1
last = series[-1]
fs = m["float_settling"]
dim1_chart = kline_svg(series, f"{name_zh} 日 K 線與均線，{rng('price')}")
dim1 = f"""
<section id="dim1" class="sec container" aria-labelledby="h1x">
  <div class="sec-head"><p class="idx num">01</p><h2 id="h1x">價量與均線</h2></div>
  {figure(dim1_chart, f"日 K、MA5／10／20／60 與成交量（張）。價格軸非零起點。來源：FinMind TaiwanStockPrice，{rng('price')}。", ma_legend(), wide=True)}
  <div class="cells grid-4">
    <div class="cell"><p class="lab">均線排列</p><p class="mid">{ALIGN_ZH[m['alignment']]}</p><p class="sub"><abbr>MA5</abbr> {fp(m['ma5'])}，<abbr>MA10</abbr> {fp(m['ma10'])}，<abbr>MA20</abbr> {fp(m['ma20'])}</p></div>
    <div class="cell"><p class="lab">均線糾結（價差 &lt; 2%）</p><p class="mid">{'是' if m['squeeze'] else '否'}</p><p class="sub">MA5／10／20 價差 {pct_plain(m['ma_spread_pct'])}</p></div>
    <div class="cell"><p class="lab">近 20 日高點</p><p class="mid num">{fp(m['w20_high'])}</p><p class="sub">{m['w20_high_date']}</p></div>
    <div class="cell"><p class="lab">近 20 日低點</p><p class="mid num">{fp(m['w20_low'])}</p><p class="sub">{m['w20_low_date']}</p></div>
    <div class="cell"><p class="lab">20 日均量</p><p class="mid num">{m['vol_avg20_lots']:,}</p><p class="sub">張；{asof} 成交 {last['volume_lots']:,} 張</p></div>
    <div class="cell"><p class="lab">爆量日（&gt; 1.5 倍均量）</p><p class="mid num">{len(m['spike_days'])} 天</p><p class="sub">{'、'.join(m['spike_days']) or '無'}</p></div>
    <div class="cell"><p class="lab">量縮日（&lt; 0.6 倍均量）</p><p class="mid num">{len(m['dryup_days'])} 天</p><p class="sub">{'、'.join(m['dryup_days']) or '無'}</p></div>
    <div class="cell"><p class="lab">浮額沉澱</p><p class="mid">{'成立' if fs['signal'] else '未成立'}</p><p class="sub">融資增減 {lots_signed(fs['margin_change'])}，量縮日 {fs['dryup_count']} 天（需 ≥ 5）</p></div>
  </div>
  <p class="read">近 60 日高點 {fp(m['high60'])}（{m['high60_date']}），低點 {fp(m['low60'])}（{m['low60_date']}）。20MA 5 日斜率 {m['ma20_slope_5d']:+,.2f}、60MA 5 日斜率 {m['ma60_slope_5d']:+,.2f}，收盤同時低於兩條下彎均線，趨勢濾網{'通過' if x['trend_ok'] else '未通過'}。</p>
</section>
"""

# --- dim2
inst = d["institutional"]
days = inst["daily"]
dl = [r["date"][5:] for r in days]


def flow_fig(key):
    vals = [r[key] for r in days]
    tips = [f"{r['date']}　{GROUP_ZH[key]}買賣超 {lots_signed(r[key])}　累計 {lots_signed(r[key + '_cum'])}" for r in days]
    svg = bars_svg(dl, vals, f"{GROUP_ZH[key]}每日買賣超", tips, vh=220, W=480)
    return (f'<div class="cell flow"><p class="lab">{GROUP_ZH[key]}，近 20 日累計</p><p class="mid num">{lots_signed(inst["cum"][key])}</p>'
            f'{figure(svg, f"每日買賣超（張）。來源：FinMind TaiwanStockInstitutionalInvestorsBuySell，{rng("institutional")}。")}</div>')


fh = d["foreign_holding"]
fh_svg = line_svg([r["date"][5:] for r in fh["series"]], [r["ratio"] for r in fh["series"]], "外資持股比率",
                  [f"{r['date']}　外資持股 {r['ratio']:.2f}%" for r in fh["series"]], lambda v: f"{v:.2f}%",
                  current=fh["last"], vh=230)
mg = d["margin"]
mg_svg = line_svg([r["date"][5:] for r in mg["series"]], [r["margin"] for r in mg["series"]], "融資餘額",
                  [f"{r['date']}　融資 {r['margin']:,} 張　融券 {r['short']:,} 張" for r in mg["series"]],
                  lambda v: f"{v:,.0f}", current=mg["margin_last"], vh=230)
cz = inst["cost_zone"]
cz_txt = (f"{fp(dv.round_tick(cz['low']))} 至 {fp(dv.round_tick(cz['high']))}（中心 {fp(dv.round_tick(cz['price']))}，依 {GROUP_ZH[cz['group']]} {cz['days']} 個買超日量加權）"
          if cz else "無（外資與投信買超日皆不足 3 天）")
dim2 = f"""
<section id="dim2" class="sec container" aria-labelledby="h2x">
  <div class="sec-head"><p class="idx num">02</p><h2 id="h2x">籌碼結構</h2></div>
  <div class="cells grid-3">{flow_fig('foreign')}{flow_fig('trust')}{flow_fig('dealer')}</div>
  <div class="cells grid-2">
    <div class="cell"><p class="lab">外資持股比率，{fh['first']:.2f}% 至 {fh['last']:.2f}%</p><p class="mid num">{fh['change_pp']:+.2f} 個百分點</p>
      {figure(fh_svg, f"外資持股比率（%），縱軸非零起點，區間高 {fh['high']:.2f}%、低 {fh['low']:.2f}%。來源：FinMind TaiwanStockShareholding，{rng('foreign_holding')}。")}</div>
    <div class="cell"><p class="lab">融資餘額，{mg['margin_first']:,} 至 {mg['margin_last']:,} 張</p><p class="mid num">{fpct(mg['margin_change_pct'])}</p>
      {figure(mg_svg, f"融資餘額（張），縱軸非零起點。來源：FinMind TaiwanStockMarginPurchaseShortSale，{rng('margin')}。")}</div>
  </div>
  <div class="cells grid-3">
    <div class="cell"><p class="lab">融券餘額</p><p class="mid num">{mg['short_last']:,} 張</p><p class="sub">由 {mg['short_first']:,} 張變動 {lots_signed(mg['short_change'])}（{fpct(mg['short_change_pct'])}）</p></div>
    <div class="cell"><p class="lab">券資比</p><p class="mid num">{pct_plain(mg['short_margin_ratio_pct'])}</p><p class="sub">水位：{LEVEL_ZH[mg['short_margin_level']]}（低於 5% 為低，5% 至 20% 為中，高於 20% 為高）</p></div>
    <div class="cell"><p class="lab">法人成本區</p><p class="mid num">{fp(dv.round_tick(cz['price'])) if cz else '無'}</p><p class="sub">{esc(cz_txt)}</p></div>
  </div>
</section>
"""

# --- dim3
rev = d["revenue"]
s24 = rev["series24"]
yoy_map = {r["period"]: r["yoy_pct"] for r in rev["last12"]}
mom_map = {r["period"]: r["mom_pct"] for r in rev["last12"]}
rev_svg = bars_svg([r["period"] for r in s24], [r["revenue"] / 1e8 for r in s24], "月營收（億元）",
                   [f"{r['period']}　營收 {yi(r['revenue'])}" + (f"　MoM {fpct(mom_map[r['period']])}　YoY {fpct(yoy_map[r['period']])}" if r['period'] in yoy_map else "") for r in s24],
                   vh=240)
l12 = rev["last12"]
yoy_svg = bars_svg([r["period"] for r in l12], [r["yoy_pct"] for r in l12], "月營收年增率（%）",
                   [f"{r['period']}　YoY {fpct(r['yoy_pct'])}" for r in l12], unit="%", vh=170)
qs = fin["quarters"][-4:]
q_rows = [[qlabel(q["quarter"]), N(f"{q['eps']:.2f}"), N(yi(q["revenue"])), N(pct_plain(q["gross_margin_pct"], 2)),
           N(pct_plain(q["operating_margin_pct"], 2)), N(f"{q['dsi_days']:.1f}" if q.get("dsi_days") is not None else "無資料")] for q in qs]
q_tbl = table_fig(["季度", "EPS（元）", "營收", "毛利率", "營益率", "存貨天數 DSI"], q_rows,
                  f"近 4 季財報。來源：FinMind TaiwanStockFinancialStatements／TaiwanStockBalanceSheet，{qs[0]['quarter']} 至 {qs[-1]['quarter']}。")
cc = fin["cash_conversion"]
dil = a["dilution"]
eq = a["earnings_quality"]
dim3 = f"""
<section id="dim3" class="sec container" aria-labelledby="h3x">
  <div class="sec-head"><p class="idx num">03</p><h2 id="h3x">營運與財務</h2></div>
  <div class="cells grid-4">
    <div class="cell"><p class="lab">{rev['latest_period']} 單月營收</p><p class="mid num">{yi(l12[-1]['revenue'])}</p><p class="sub">MoM {fpct(l12[-1]['mom_pct'])}，YoY {fpct(l12[-1]['yoy_pct'])}</p></div>
    <div class="cell"><p class="lab">今年累計營收（至 {rev['latest_period']}）</p><p class="mid num">{yi(rev['ytd'])}</p><p class="sub">YoY {fpct(rev['ytd_yoy_pct'])}，去年同期 {yi(rev['ytd_prev'])}</p></div>
    <div class="cell"><p class="lab">近 4 季 <abbr>EPS</abbr> 合計（<abbr>TTM</abbr>）</p><p class="mid num">{fin['ttm_eps']:.2f} 元</p><p class="sub">最新季 {qlabel(qs[-1]['quarter'])} EPS {qs[-1]['eps']:.2f} 元</p></div>
    <div class="cell"><p class="lab">現金轉換率（TTM 營業現金流／淨利）</p><p class="mid num">{cc['ratio']:.2f}</p><p class="sub">營業現金流 {yi(cc['ttm_ocf'])}，淨利 {yi(cc['ttm_net_income'])}</p></div>
  </div>
  {figure(rev_svg, f"月營收（億元），縱軸自零起。來源：FinMind TaiwanStockMonthRevenue，{rng('revenue')}。", wide=True)}
  {figure(yoy_svg, f"近 12 個月營收年增率（%）。來源：FinMind TaiwanStockMonthRevenue，{l12[0]['period']} 至 {l12[-1]['period']}。", wide=True)}
  {q_tbl}
  <div class="cells grid-2">
    <div class="cell" data-dilution><p class="lab">股本稀釋：可轉債與現金增資</p>
      <p class="mid">可轉債 {'有' if dil['has_cb'] else '無'}；現增 {'有' if dil['has_spo'] else '無'}</p>
      <p>{linkify(dil['summary'])}</p><p class="basis">依據：{linkify(dil['basis'])}</p></div>
    <div class="cell"><p class="lab">獲利品質：{esc(eq['focus'])} {judg}</p><p>{linkify(eq['text'])}</p><p class="basis">依據：{linkify(eq['basis'])}</p></div>
  </div>
</section>
"""

# --- dim4
val = d["valuation"]


def band_fig(key, unit_fmt):
    b = val[key]
    ser = b["series"]
    svg = line_svg([r["date"][:7] for r in ser], [r["v"] for r in ser], f"5 年 {key} 區間",
                   [f"{r['date']}　{key} {r['v']:.2f}x" for r in ser], unit_fmt,
                   refs=[(p.upper(), b[p]) for p in ("p10", "p25", "p50", "p75", "p90")], current=b["current"], vh=260)
    return (f'<div class="cell"><p class="lab">{key} 現值，5 年百分位 {b["current_percentile"]:.1f}%</p><p class="mid num">{fmult(b["current"])}</p>'
            f'{figure(svg, f"5 年 {key}（週取樣顯示，百分位以 {b["n"]:,} 個交易日計），縱軸非零起點。來源：FinMind TaiwanStockPER，{val["start"]} 至 {val["date"]}。")}</div>')


peer_info = {p["code"]: p for p in a["peers"]}
peer_rows = []
for r in d["peers"]["rows"]:
    p = peer_info.get(r["code"])
    nm = esc(name_zh) if r["code"] == CODE else esc(p["name"]) if p else r["code"]
    reason = "目標公司" if r["code"] == CODE else (f"{esc(p['reason'])} {judg}" if p else "")
    peer_rows.append([f"{r['code']} {nm}", N(fmult(r["PER"]) if r["PER"] else "無資料"), N(fmult(r["PBR"]) if r["PBR"] else "無資料"),
                      N(pct_plain(r["dividend_yield"], 2)), reason])
med = d["peers"]["median"]
peer_rows.append(["同業中位數（不含目標）", N(fmult(med["PER"])), N(fmult(med["PBR"])), N(pct_plain(med["dividend_yield"], 2)), ""])
peer_tbl = table_fig(["公司", "PER", "PBR", "殖利率", "選入理由"], peer_rows,
                     f"同業估值矩陣，{d['peers']['rows'][0]['date']} 收盤。來源：FinMind TaiwanStockPER，{val['date']}。")

sc_rows = []
for s in x["scenarios"]:
    im = s["implied"]
    sc_rows.append([
        f"<strong>{esc(s['label'])}</strong>（{s['name']}）",
        N(f"{s['probability']}%"),
        N(f"{s['eps']:.2f}"),
        N(fmult(s["multiple"])),
        N(fp(s["target"])),
        N(fpct(s["upside_pct"])),
        N(f'<span data-implied="{s["name"]}">{fmult(im["value"])}</span>' if im else "無資料"),
        POS_ZH[im["position"]] if im else "",
    ])
    sc_rows.append(("FULL", f"<p>{esc(s['assumptions'])}</p><p class=\"basis\">依據：{linkify(s['basis'])}</p>", f"{s['label']}情境假設與依據"))
sc_tbl = table_fig(["情境", "機率", "前瞻 EPS（元）" if method == "PER" else "BVPS（元）", f"{method} 倍數", "目標價", "潛在漲跌",
                    f"隱含 {imp_metric}", f"{imp_metric} 帶位置"], sc_rows,
                   f"12 個月情境目標價，{judg}；每個情境下方一列為假設與依據。倍數錨定 FinMind TaiwanStockPER 5 年 {method} 區間（{val['start']} 至 {val['date']}），隱含 {imp_metric} 以 BVPS {fin['bvps_latest']:.2f} 元（{fin['latest_quarter']}）計。")
hv = ""
if cb.get("applicable") and cb.get("high_volatility"):
    hv = f'<p class="warn">高波動提示：{"；".join(VOL_ZH.get(r, r) for r in cb["volatility_reasons"])}。基準僅供量級比對，不宜直接當作預測。</p>'
dev = x["baseline_deviation_pct"]
baseline = f"""
<div class="cells grid-4 baseline">
  <div class="cell"><p class="lab">核心基準 EPS，{asof[:4]} 曆年（CY）</p><p class="mid num" data-baseline="cy">{feps(cb.get('cy_eps') if cb.get('applicable') and method == 'PER' else None)}</p><p class="sub">今年累計營收加上去年剩餘月份 ×（1 + 6 個月 YoY 中位數 {pct_plain(cb.get('yoy6_median_pct'))}）</p></div>
  <div class="cell"><p class="lab">核心基準 EPS，未來 12 個月（NTM）</p><p class="mid num" data-baseline="ntm">{feps(cb.get('ntm_eps') if cb.get('applicable') and method == 'PER' else None)}</p><p class="sub">TTM 營收 ×（1 + 6 個月 YoY 中位數）</p></div>
  <div class="cell"><p class="lab">核心淨利率</p><p class="mid num">{pct_plain(cb.get('core_net_margin_pct'), 2)}</p><p class="sub">TTM 營益率 {pct_plain(cb.get('ttm_opm_pct'), 2)} ×（1 − 稅率 {pct_plain(cb.get('effective_tax_rate_pct'), 2)}）× 母公司比 {pct_plain(cb.get('parent_ratio_pct'), 2)}</p></div>
  <div class="cell"><p class="lab">Base EPS 對 NTM 基準</p><p class="mid num">{fpct(dev)}</p><p class="sub">Base 前瞻 EPS {base['eps']:.2f} 元</p></div>
</div>
{hv}
"""
dim4 = f"""
<section id="dim4" class="sec container" aria-labelledby="h4x">
  <div class="sec-head"><p class="idx num">04</p><h2 id="h4x">估值與目標價</h2></div>
  <div class="cells grid-2">{band_fig('PER', lambda v: f'{v:.1f}x')}{band_fig('PBR', lambda v: f'{v:.1f}x')}</div>
  {peer_tbl}
  <p class="read">估值方法：{esc(method)}。{linkify(a['valuation_method_basis'])}</p>
  {sc_tbl}
  {baseline}
  <div class="band"><div class="cells grid-3">
    <div class="cell cell--ink"><p class="lab">機率加權目標價</p><p class="big num">{fp(x['weighted_target'])}</p><p class="sub">對收盤 {fpct(x['weighted_upside_pct'])}</p></div>
    <div class="cell"><p class="lab">評等（依 Base 潛在漲跌）</p><p class="big">{x['rating_zh']}</p><p class="sub">Base {fp(base['target'])}，{fpct(base['upside_pct'])}；&gt; +15% 買進，−5% 至 +15% 中立，&lt; −5% 賣出</p></div>
    <div class="cell"><p class="lab">合理買進價（Base ÷ 1.15）</p><p class="big num">{fp(x['fair_buy'])}</p><p class="sub">收盤低於此價時評等為買進</p></div>
  </div></div>
</section>
"""

# --- dim5
def item_rows(items):
    return [[f"<strong>{esc(i['title'])}</strong>", esc(i["timing"]), esc(i["direction"]), esc(i["indicator"]),
             f"{linkify(i['basis'])}"] for i in items]


moat = "".join(f'<div class="cell"><h3>{esc(mo["title"])}</h3><p>{esc(mo["text"])}</p><p class="basis">依據：{linkify(mo["basis"])}</p></div>' for mo in a["moat"])
facts = "".join(f'<li><p>{esc(f["text"])}</p><p class="src"><a href="{esc(f["url"])}" rel="noopener" target="_blank">{esc(f["source"])}</a>，{esc(f["date"])}</p></li>' for f in a["external_facts"])
dim5 = f"""
<section id="dim5" class="sec container" aria-labelledby="h5x">
  <div class="sec-head"><p class="idx num">05</p><h2 id="h5x">催化劑與風險</h2></div>
  <p class="read">護城河 {judg}</p>
  <div class="cells grid-3">{moat}</div>
  {table_fig(["催化劑", "時間", "方向", "觀察指標", "依據"], item_rows(a['catalysts']), f"催化劑，{judg}；外部事實出處見下方清單，市場數據來源 FinMind，截至 {asof}。", cls="wide")}
  {table_fig(["風險", "時間", "方向", "觀察指標", "依據"], item_rows(a['risks']), f"風險，{judg}；外部事實出處見下方清單，市場數據來源 FinMind，截至 {asof}。", cls="wide")}
  <h3 class="sub-h">外部事實與出處</h3>
  <ol class="facts">{facts}</ol>
</section>
"""

# --- dim6
def status_txt(k):
    st = x[k]
    return "成立" if st == "active" else dv.SETUP_STATUS_ZH[st]


def rr_cell(key, v):
    flag = '<p class="sub">R:R &lt; 1.5，不具交易吸引力</p>' if v is not None and v < 1.5 else ""
    return f'<p class="big num" data-rr="{key}">{frr(v)}</p>{flag}'


zone_src = "均線帶與法人成本區重疊" if x["zone_source"] == "overlap" else "MA10 與 MA20 均線帶"
stop_src = "量最大日低點與 MA20 × 0.97 中較近者" if x["hard_stop_source"] == "candidate" else "進場區下緣 × 0.95"
last60 = series[-60:]
lines6 = [("entry", "進場 Entry", x["entry"]), ("t1", "T1", x["t1"]), ("t2", "T2", x["t2"]), ("sl", "停損 SL", x["hard_stop"])]
dim6_svg = kline_svg(last60, f"{name_zh} 近 60 日 K 線與交易價位", lines=lines6, zone=(x["zone_low"], x["zone_high"]), vh=460)
breakers_tbl = table_fig(["條件", "門檻", "資料集"], [[esc(t["condition"]), N(esc(t["threshold"])), esc(t["dataset"])] for t in a["thesis_breakers"]],
                         f"論點破功條件，{judg}；以 FinMind 資料集追蹤，基準日 {asof}。")
dim6 = f"""
<section id="dim6" class="sec container" aria-labelledby="h6x">
  <div class="sec-head"><p class="idx num">06</p><h2 id="h6x">交易部位與風控</h2></div>
  {figure(dim6_svg, f"近 60 日 K 線，黃色帶為拉回進場區 {fp(x['zone_low'])} 至 {fp(x['zone_high'])}，水平線為進場、T1、T2 與停損。價格軸非零起點。來源：FinMind TaiwanStockPrice，{last60[0]['date']} 至 {last60[-1]['date']}。", ma_legend(), wide=True)}
  <h3 class="sub-h">波段層（數週）</h3>
  <div class="cells grid-2">
    <div class="cell"><p class="lab">拉回策略：{esc(status_txt('pullback_status'))}</p>
      <dl class="kv">
        <dt>進場區（{zone_src}）</dt><dd class="num">{fp(x['zone_low'])} 至 {fp(x['zone_high'])}</dd>
        <dt>進場價（區間中點）</dt><dd class="num">{fp(x['entry'])}</dd>
        <dt>T1 技術目標</dt><dd class="num">{fp(x['t1'])}</dd>
        <dt>T2 波段目標（費波納契 1.618 與 Bull 取低）</dt><dd class="num">{fp(x['t2'])}</dd>
        <dt>硬停損（{stop_src}）</dt><dd class="num">{fp(x['hard_stop'])}</dd>
      </dl>
      <p class="lab">拉回 R:R</p>{rr_cell('pullback', x['rr_pullback'])}</div>
    <div class="cell"><p class="lab">突破策略：{esc(status_txt('breakout_status'))}</p>
      <dl class="kv">
        <dt>突破點（近 60 日最高）</dt><dd class="num">{fp(x['trigger'])}</dd>
        <dt>量能條件（&gt; 1.5 倍 20 日均量）</dt><dd class="num">{x['trigger_volume_lots']:,} 張</dd>
        <dt>T2 波段目標</dt><dd class="num">{fp(x['t2'])}</dd>
        <dt>突破停損（突破點 × 0.95）</dt><dd class="num">{fp(x['breakout_stop'])}</dd>
      </dl>
      <p class="lab">突破 R:R</p>{rr_cell('breakout', x['rr_breakout'])}</div>
  </div>
  <h3 class="sub-h">持有層（12 個月）</h3>
  <div class="cells grid-4">
    <div class="cell"><p class="lab">合理買進價</p><p class="mid num">{fp(x['fair_buy'])}</p><p class="sub">Base 目標 ÷ 1.15</p></div>
    <div class="cell"><p class="lab">Base 目標價</p><p class="mid num">{fp(base['target'])}</p><p class="sub">{fpct(base['upside_pct'])}</p></div>
    <div class="cell"><p class="lab">Bear 目標價</p><p class="mid num">{fp(bear['target'])}</p><p class="sub">{fpct(bear['upside_pct'])}</p></div>
    <div class="cell cell--ink"><p class="lab">持有 R:R：{esc(status_txt('hold_status'))}</p>{rr_cell('hold', x['rr_hold'])}</div>
  </div>
  <h3 class="sub-h">論點破功條件</h3>
  {breakers_tbl}
</section>
"""

CAPS = re.compile(r"(?<![A-Za-z0-9&;#/])([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)?)(?![A-Za-z])")


def abbr_caps(frag):
    """Wrap all-caps tokens in text nodes in <abbr> (not inside tags, svg, or existing abbr)."""
    out, depth_skip = [], 0
    for part in re.split(r"(<[^>]+>)", frag):
        if part.startswith("<"):
            tag = re.match(r"</?([a-zA-Z0-9]+)", part)
            name = tag.group(1).lower() if tag else ""
            if name in ("svg", "abbr", "script", "style"):
                depth_skip += -1 if part.startswith("</") else (0 if part.endswith("/>") else 1)
            out.append(part)
        elif depth_skip > 0:
            out.append(part)
        else:
            out.append(CAPS.sub(r"<abbr>\g<1></abbr>", part))
    return "".join(out)


hero, dim1, dim2, dim3, dim4, dim5, dim6 = (abbr_caps(f) for f in (hero, dim1, dim2, dim3, dim4, dim5, dim6))
gen = a["generation"]
nav = "".join(f'<li><a href="#dim{i}">{t}</a></li>' for i, t in enumerate(["價量", "籌碼", "營運", "估值", "催化劑", "交易"], 1))

CSS = r"""/* Hallmark · shape: stat-led · genre: editorial · theme: Brutal (deal 2/3, seed 2330-equity-research-1833·ce12e4cc·2026-11-21·r0) · job: decide (read the current action, then the trade plan) · draw: none (sections fixed by report-contract)
 * hero: stat cells under the company head · nav: edge-aligned wordmark, six section links, mode toggle · footer: ruled colophon with source, model and disclaimer · imagery: none (charts are the material) · signature: the yellow action cell beside the two falling averages it must reclaim
 * axes: light/grotesk-heavy/chromatic-yellow · posture: committed · contrast: pass · fold: pass · modes: light+dark · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R3 V4 · weakest: R (a long report runs past the word budget), kept every section in boxed cells so it scans as a sheet */
/* Hallmark · finish-review: subagent · 8 findings · 7 resolved 1 rejected (7: report-contract requires following prefers-color-scheme) · gap: none */
/* Hallmark · waive 26b · no control on the page can ever be disabled · the controls are two anchor buttons and the mode toggle */
/* Hallmark · waive 44c · the hero continues past the head into the yellow action cell, the two average cells and the contract's KPI strip · the call, its condition and both actions sit inside the 1280x800 fold */
/* Hallmark · waive 79 · the linter stops the hero at the actions, above the bordered cells · the 當前動作 cell, both moving-average cells and the Base target strip built from FinMind fill that space */
/* Hallmark · waive 82 · the repeated rects are transparent per-day hover targets that carry data-tip values · they are not visible counting marks */
TOKENS_CSS
BASE_CSS
:root {
  color-scheme: light dark;
  --font-display: "Libre Franklin", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", ui-sans-serif, system-ui, sans-serif;
  --font-body: var(--font-display);
  --chart-1: oklch(60% 0.006 95); --chart-2: oklch(44% 0.006 95); --chart-3: oklch(28% 0.006 95); --chart-4: oklch(10% 0.006 95);
  --chart-zone: color-mix(in oklab, var(--color-accent) 55%, transparent);
  --container: 1280px;
}
[data-mode="dark"] {
  --color-paper: oklch(19% 0.006 95); --color-paper-2: oklch(22% 0.007 95); --color-paper-3: oklch(25% 0.008 95);
  --color-ink: oklch(95% 0.006 95); --color-ink-2: oklch(88% 0.006 95); --color-muted: oklch(74% 0.008 95);
  --color-rule: oklch(80% 0.006 95);
  --color-accent: oklch(86% 0.16 105); --color-accent-ink: oklch(14% 0.006 95); --color-focus: oklch(80% 0.12 110);
  --chart-1: oklch(58% 0.006 95); --chart-2: oklch(70% 0.006 95); --chart-3: oklch(83% 0.006 95); --chart-4: oklch(95% 0.006 95);
  --chart-zone: color-mix(in oklab, var(--color-accent) 35%, transparent);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-mode="light"]) {
    --color-paper: oklch(19% 0.006 95); --color-paper-2: oklch(22% 0.007 95); --color-paper-3: oklch(25% 0.008 95);
    --color-ink: oklch(95% 0.006 95); --color-ink-2: oklch(88% 0.006 95); --color-muted: oklch(74% 0.008 95);
    --color-rule: oklch(80% 0.006 95);
    --color-accent: oklch(86% 0.16 105); --color-accent-ink: oklch(14% 0.006 95); --color-focus: oklch(80% 0.12 110);
    --chart-1: oklch(58% 0.006 95); --chart-2: oklch(70% 0.006 95); --chart-3: oklch(83% 0.006 95); --chart-4: oklch(95% 0.006 95);
    --chart-zone: color-mix(in oklab, var(--color-accent) 35%, transparent);
  }
}
html, body { overflow-x: clip; }
body { font-size: 1.0625rem; line-height: 1.6; }
h1, h2 { text-transform: uppercase; line-height: 1; }
h3 { font-weight: 700; letter-spacing: 0; }
a:hover { background: var(--color-accent); color: var(--color-accent-ink); }
.mast { border-bottom: var(--rule-bar) solid var(--color-rule); }
.mast .container { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-sm) var(--space-lg); padding-block: var(--space-sm); }
.mark { font-weight: 900; font-size: var(--text-lg); text-decoration: none; letter-spacing: -0.02em; }
.mast nav { margin-inline-start: auto; }
.mast ul { display: flex; flex-wrap: wrap; gap: var(--space-2xs) var(--space-md); margin: 0; padding: 0; list-style: none; font-size: var(--text-sm); }
.mast nav a { text-decoration: none; font-weight: 700; padding: var(--space-2xs) 0; }
.mast nav a:hover { text-decoration: underline; }
.btn-mode { border: var(--rule-bar) solid var(--color-rule); border-radius: 0; background: var(--color-paper); color: var(--color-ink); font-weight: 700; font-size: var(--text-sm); min-height: 44px; padding: 0 var(--space-md); cursor: pointer; transition: none; }
.btn-mode:hover { background: var(--color-ink); color: var(--color-paper); }
.btn-mode:active { background: var(--color-accent); color: var(--color-accent-ink); }
.btn-mode:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
.hero { padding-block: var(--space-xl) var(--space-2xl); }
.hero-top { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: var(--space-md) var(--space-xl); }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-sm); }
.btn { display: inline-flex; align-items: center; min-height: 48px; border: var(--rule-bar) solid var(--color-rule); border-radius: 0; padding: 0 var(--space-lg); background: var(--color-paper); color: var(--color-ink); font-weight: 700; text-decoration: none; transition: none; }
.btn:hover, .btn--ink { background: var(--color-ink); color: var(--color-paper); }
.btn--ink:hover { background: var(--color-paper); color: var(--color-ink); }
.btn:active { background: var(--color-accent); color: var(--color-accent-ink); }
.btn:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
.kpi-cells { grid-template-columns: repeat(6, minmax(0, 1fr)); margin-top: 0; }
.kpi-cells > .cell { padding: var(--space-sm) var(--space-md); }
.kpi-cells .val { font-size: var(--text-xl); white-space: nowrap; }
.hero-cells { grid-template-columns: 2fr 1fr 1fr; margin-bottom: 0; }
.cell--act { grid-row: span 1; }
.hero h1 { max-width: none; font-size: clamp(2.5rem, 5vw + 1rem, 4.75rem); }
.hero .lead { margin-top: var(--space-sm); color: var(--color-muted); }
.cells { display: grid; gap: 0; border: var(--rule-bar) solid var(--color-rule); margin-block: var(--space-lg); }
.cells > .cell { margin: calc(var(--rule-bar) * -1) 0 0 calc(var(--rule-bar) * -1); border: var(--rule-bar) solid var(--color-rule); padding: var(--space-md) var(--space-lg); min-width: 0; }
.cell--act { background: var(--color-accent); color: var(--color-accent-ink); display: flex; flex-direction: column; justify-content: space-between; gap: var(--space-md); }
.cell--act .lab { color: var(--color-accent-ink); }
.act { font-weight: 900; font-size: clamp(2.75rem, 6vw + 0.5rem, 5.5rem); line-height: 1; letter-spacing: -0.03em; overflow-wrap: break-word; min-width: 0; }
.note { font-weight: 700; font-size: var(--text-lead); line-height: 1.4; max-width: 34ch; }
.cell--ink { background: var(--color-ink); color: var(--color-paper); }
.cell--ink .lab, .cell--ink .sub { color: color-mix(in oklab, var(--color-paper) 78%, var(--color-ink)); }
.lab { font-size: var(--text-sm); color: var(--color-muted); margin-bottom: var(--space-2xs); }
.val { font-weight: 900; font-size: var(--text-2xl); line-height: 1.1; }
.big { font-weight: 900; font-size: clamp(2rem, 3vw + 0.75rem, 3.25rem); line-height: 1.05; letter-spacing: -0.02em; }
.mid { font-weight: 900; font-size: var(--text-xl); line-height: 1.2; }
.sub { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-2xs); }
.gapnote { font-size: var(--text-sm); color: var(--color-muted); }
.sec { padding-block: var(--space-2xl); border-top: var(--rule-bar) solid var(--color-rule); }
.sec-head { display: flex; align-items: baseline; gap: var(--space-md); margin-bottom: var(--space-lg); }
.idx { font-weight: 900; font-size: var(--text-section); line-height: 1; }
.sub-h { margin-block: var(--space-xl) var(--space-sm); font-size: var(--text-title); }
.read { max-width: 72ch; margin-block: var(--space-md); }
.grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.fig { margin: var(--space-md) 0; min-width: 0; }
.fig figcaption { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-xs); }
.cell--ink .fig figcaption { color: inherit; }
.plot { border: var(--rule-hair) solid var(--color-rule); background: var(--color-paper); }
.chart { width: 100%; height: auto; }
.chart text { font-family: var(--font-body); font-size: var(--fs, 13px); fill: var(--color-muted); font-variant-numeric: tabular-nums; }
.chart .grid { stroke: var(--color-paper-3); stroke-width: 1; }
.chart .ref { stroke: var(--color-paper-3); stroke-width: 1; }
.chart .ref-mid { stroke: var(--color-muted); }
.chart .wick { stroke: var(--color-ink); stroke-width: 1; }
.chart .up { fill: var(--color-paper); stroke: var(--color-ink); stroke-width: 1; }
.chart .dn { fill: var(--color-ink); }
.chart .vol.up { fill: var(--chart-1); stroke: none; }
.chart .vol.dn { fill: var(--chart-3); }
.chart .ln { fill: none; stroke-width: 2; stroke-linejoin: round; }
.chart .ma5 { stroke: var(--chart-1); } .chart .ma10 { stroke: var(--chart-2); } .chart .ma20 { stroke: var(--chart-3); } .chart .ma60 { stroke: var(--chart-4); stroke-width: 3; }
.chart .main { stroke: var(--color-ink); }
.chart .dot { fill: var(--color-accent); stroke: var(--color-ink); stroke-width: 2; }
.chart .bar.pos { fill: var(--color-ink); } .chart .bar.neg { fill: var(--chart-1); }
.chart .zone { fill: var(--chart-zone); }
.chart .lvl line { stroke: var(--color-ink); stroke-width: 1.5; }
.chart .lvl-sl line { stroke-width: 3; }
.chart .lvl text { fill: var(--color-ink); font-weight: 700; paint-order: stroke; stroke: var(--color-paper); stroke-width: 4px; }
.chart .hit { fill: transparent; }
.chart .hit:hover { fill: color-mix(in oklab, var(--color-accent) 40%, transparent); }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-2xs) var(--space-md); list-style: none; margin: 0 0 var(--space-xs); padding: 0; font-size: var(--text-sm); }
.legend li { display: inline-flex; align-items: center; gap: var(--space-2xs); }
.sw { display: inline-block; width: 18px; height: 3px; background: var(--chart-4); }
.sw-ma5 { background: var(--chart-1); } .sw-ma10 { background: var(--chart-2); } .sw-ma20 { background: var(--chart-3); } .sw-ma60 { height: 4px; }
.sw-up { width: 10px; height: 14px; background: var(--color-paper); border: 1px solid var(--color-ink); } .sw-dn { width: 10px; height: 14px; background: var(--color-ink); }
.scroll { overflow-x: auto; border: var(--rule-bar) solid var(--color-rule); }
tr.full td { border-bottom: var(--rule-bar) solid var(--color-rule); position: static; background: var(--color-paper-2); }
tr.full td p { max-width: 72ch; }
.band { background: var(--color-paper-2); color: var(--color-ink); border-block: var(--rule-bar) solid var(--color-rule); padding: var(--space-lg); margin-block: var(--space-lg); }
.band .cells { margin: 0; background: var(--color-paper); color: var(--color-ink); }
table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
.scroll.wide table { min-width: 960px; }
th { text-align: left; font-weight: 400; color: var(--color-muted); padding: var(--space-xs) var(--space-sm); border-bottom: var(--rule-bar) solid var(--color-rule); white-space: nowrap; }
td { padding: var(--space-sm); border-bottom: var(--rule-hair) solid var(--color-rule); vertical-align: top; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: var(--color-paper-2); }
th:first-child, td:first-child { position: sticky; left: 0; background: var(--color-paper); z-index: 1; }
tbody tr:hover td:first-child { background: var(--color-paper-2); }
.scroll.wide td { min-width: 8em; }
.scroll.wide td:last-child { min-width: 18em; }
td.num { text-align: right; font-weight: 700; white-space: nowrap; }
.basis { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-xs); overflow-wrap: anywhere; }
.basis a, .src a, td a { overflow-wrap: anywhere; }
abbr { text-decoration: none; }
.tag { display: inline-block; font-size: var(--text-xs); font-weight: 700; border: var(--rule-hair) solid currentColor; padding: 0 var(--space-2xs); vertical-align: 0.15em; }
.warn { border: var(--rule-bar) solid var(--color-rule); background: var(--color-paper-2); padding: var(--space-sm) var(--space-md); font-weight: 700; }
.kv { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2xs) var(--space-md); margin: var(--space-sm) 0 var(--space-md); }
.kv dt { color: var(--color-muted); font-size: var(--text-sm); }
.kv dd { margin: 0; font-weight: 900; text-align: right; }
.cell h3 { font-size: var(--text-lg); margin-bottom: var(--space-xs); }
.flow .fig { margin-bottom: 0; }
.facts { margin: 0; padding: 0; list-style: none; border: var(--rule-bar) solid var(--color-rule); counter-reset: f; }
.facts li { padding: var(--space-sm) var(--space-md) var(--space-sm) 3.5rem; border-bottom: var(--rule-hair) solid var(--color-rule); position: relative; counter-increment: f; }
.facts li:last-child { border-bottom: 0; }
.facts li::before { content: counter(f); position: absolute; left: var(--space-md); top: var(--space-sm); font-weight: 900; font-variant-numeric: tabular-nums; }
.src { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-2xs); }
.colophon { border-top: var(--rule-bar) solid var(--color-rule); padding-block: var(--space-xl) var(--space-2xl); font-size: var(--text-sm); }
.colophon .cells { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.colophon .disc { font-weight: 700; font-size: var(--text-md); margin-top: var(--space-md); }
.tip { position: fixed; left: 0; top: 0; z-index: var(--z-tooltip); pointer-events: none; max-width: min(92vw, 440px); background: var(--color-ink); color: var(--color-paper); font-size: var(--text-sm); padding: var(--space-xs) var(--space-sm); font-variant-numeric: tabular-nums; }
@media (max-width: 60rem) {
  .grid-4, .colophon .cells { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kpi-cells { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .hero-cells { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cell--act { grid-column: 1 / -1; }
  .grid-3 { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 40rem) {
  .grid-2 { grid-template-columns: minmax(0, 1fr); }
  .kpi-cells { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cells > .cell { padding: var(--space-sm) var(--space-md); }
  .mast nav { margin-inline-start: 0; width: 100%; }
  .plot--wide { overflow-x: auto; }
  .plot--wide .chart { min-width: 640px; }
  .kpi-cells .val { font-size: var(--text-lg); }
  .band { padding: var(--space-sm); }
  .scroll { overflow-x: visible; }
  .scroll.wide table { min-width: 0; }
  table.stack thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  table.stack, table.stack tbody, table.stack tr, table.stack td { display: block; width: 100%; }
  table.stack tr { border-bottom: var(--rule-bar) solid var(--color-rule); }
  table.stack td, .scroll.wide td, .scroll.wide td:last-child { position: static; min-width: 0; border-bottom: var(--rule-hair) solid var(--color-paper-3); text-align: left; white-space: normal; padding: var(--space-xs) var(--space-sm); }
  table.stack td::before { content: attr(data-label); display: block; font-weight: 400; font-size: var(--text-xs); color: var(--color-muted); }
  table.stack td:empty { display: none; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
"""

# The scaffold folder is gitignored, so its rules are inlined here verbatim (copied once).
TOKENS = """:root {
  color-scheme: light;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.8125rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.25rem; --text-xl: 1.5625rem; --text-2xl: 1.953rem; --text-3xl: 2.441rem;
  --text-display-s: clamp(2.25rem, 4vw + 0.5rem, 3.75rem); --text-display: clamp(2.75rem, 5vw + 1rem, 5.25rem);
  --text-section: clamp(2rem, 2.5vw + 1rem, 3.5rem); --text-title: clamp(1.25rem, 0.75vw + 0.875rem, 1.625rem); --text-lead: clamp(1.125rem, 0.35vw + 1rem, 1.375rem);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --ease-in: cubic-bezier(0.7, 0, 0.84, 0); --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms; --dur-short: 220ms; --dur-long: 420ms;
  --color-error: oklch(52% 0.19 27); --color-success: oklch(50% 0.12 150);
  --container: 1440px; --gutter: 64px; --gap-columns: 32px; --section-gap-s: 120px; --section-gap: 144px; --section-gap-l: 176px;
  --z-base: 1; --z-raised: 10; --z-dropdown: 100; --z-sticky: 200; --z-sticky-nav: 300; --z-modal: 400; --z-toast: 500; --z-tooltip: 600;
  --color-paper: oklch(97.5% 0.006 95); --color-paper-2: oklch(94% 0.007 95); --color-paper-3: oklch(89.5% 0.008 95);
  --color-ink: oklch(10% 0.006 95); --color-ink-2: oklch(16% 0.006 95); --color-muted: oklch(40% 0.008 95);
  --color-rule: oklch(10% 0.006 95);
  --color-accent: oklch(90% 0.19 105); --color-accent-ink: oklch(10% 0.006 95); --color-focus: oklch(48% 0.1 110);
  --font-display: "Libre Franklin", ui-sans-serif, system-ui, sans-serif; --font-body: var(--font-display);
  --font-outlier: var(--font-display);
  --radius-card: 0; --radius-pill: 0; --rule-hair: 1px; --rule-bar: 3px; --shadow-card: none;
  --tracking-display: -0.03em; --display-weight: 900;
}"""
BASE = """*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); scroll-padding-top: var(--space-3xl); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }
::selection { background: var(--color-accent); color: var(--color-accent-ink); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 0.16em; }
h1, h2, h3 { margin: 0; font-family: var(--font-display); font-weight: var(--display-weight, 700); font-synthesis: none; letter-spacing: var(--tracking-display); line-height: 1.05; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1 { max-width: 20ch; font-size: var(--text-display); } h2 { max-width: 30ch; font-size: var(--text-section); } h3 { max-width: 40ch; font-size: var(--text-title); line-height: 1.2; }
.lead { font-size: var(--text-lead); line-height: 1.45; max-width: 52ch; }
p { margin: 0; text-wrap: pretty; }
p:not([class]) { max-width: 65ch; }
img, video { max-width: 100%; height: auto; display: block; }
svg { display: block; }
[hidden] { display: none !important; }
button, input, select, textarea { font: inherit; }
.container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); box-sizing: border-box; }
.num, .figure, td.num { font-variant-numeric: tabular-nums; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
[data-slot] { position: relative; overflow: hidden; background: linear-gradient(160deg, var(--color-paper-2, var(--color-paper)), var(--color-paper-3, var(--color-paper))); }
[data-slot] > img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1; }
[data-slot]:has(> img) > :not(img):not([data-keep]) { display: none !important; }
@media (max-width: 60rem) { :root { --gutter: 24px; --section-gap-s: 80px; --section-gap: 96px; --section-gap-l: 120px; } }
@media (max-width: 40rem) { :root { --gutter: 16px; --section-gap-s: 56px; --section-gap: 72px; --section-gap-l: 96px; --gap-columns: 16px; } }
@media (prefers-reduced-motion: reduce) { *:not(.keep-motion), *:not(.keep-motion)::before, *:not(.keep-motion)::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }
/* photographs: duotone ink paper con=24 */
[data-slot]:has(> img) { isolation: isolate; background: var(--color-paper); outline: 1px solid color-mix(in oklab, var(--color-ink) 8%, transparent); outline-offset: -1px; }
[data-slot] > img { z-index: 0; filter: grayscale(1) contrast(1.24); mix-blend-mode: multiply; }
[data-slot]:has(> img)::before { content: ""; position: absolute; inset: 0; z-index: 1; background: var(--color-ink); mix-blend-mode: lighten; pointer-events: none; }"""
css = CSS.replace("TOKENS_CSS", TOKENS).replace("BASE_CSS", BASE)

JS = r"""
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('mode-toggle');
  function cur() { return root.dataset.mode || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); }
  function label() { btn.textContent = cur() === 'dark' ? '切換淺色' : '切換深色'; btn.setAttribute('aria-pressed', cur() === 'dark' ? 'true' : 'false'); }
  btn.addEventListener('click', function () {
    var next = cur() === 'dark' ? 'light' : 'dark';
    root.dataset.mode = next;
    try { localStorage.setItem('mode', next); } catch (e) {}
    label();
  });
  label();
  function fit() {
    document.querySelectorAll('svg.chart').forEach(function (s) {
      var w = s.getBoundingClientRect().width, vb = s.viewBox.baseVal.width;
      if (w && vb) s.style.setProperty('--fs', Math.min(Math.max(13, 12 * vb / w), 30).toFixed(1) + 'px');
    });
  }
  fit();
  window.addEventListener('resize', fit);
  var tip = document.createElement('div');
  tip.className = 'tip'; tip.hidden = true; tip.setAttribute('role', 'status');
  document.body.appendChild(tip);
  function show(el, cx, cy) {
    tip.textContent = el.getAttribute('data-tip'); tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var px = Math.min(Math.max(8, cx + 14), window.innerWidth - w - 8);
    var py = cy - h - 14 < 8 ? cy + 18 : cy - h - 14;
    tip.style.transform = 'translate(' + px + 'px,' + py + 'px)';
  }
  document.addEventListener('pointermove', function (e) {
    var el = e.target.closest && e.target.closest('[data-tip]');
    if (el) show(el, e.clientX, e.clientY); else tip.hidden = true;
  });
  document.addEventListener('pointerleave', function () { tip.hidden = true; });
})();
"""

page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name_zh)} {CODE} 投資決策報告</title>
<meta name="description" content="{esc(name_zh)}（{CODE}）{asof} 投資決策報告：當前動作 {esc(x['action_zh'])}，評等 {x['rating_zh']}，Base 目標價 {fp(base['target'])}。">
<script>try {{ var s = localStorage.getItem('mode'); if (s === 'dark' || s === 'light') document.documentElement.dataset.mode = s; }} catch (e) {{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;700;900&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
<header class="mast">
  <div class="container">
    <a class="mark" href="../../index.html">{CODE} {esc(name_zh)}</a>
    <nav aria-label="章節"><ul>{nav}</ul></nav>
    <button type="button" id="mode-toggle" class="btn-mode" aria-pressed="false">切換深色</button>
  </div>
</header>
<main>
{hero}
{dim1}
{dim2}
{dim3}
{dim4}
{dim5}
{dim6}
</main>
<footer class="colophon">
  <div class="container">
    <div class="cells">
      <div class="cell"><p class="lab">資料來源</p><p>FinMind（TaiwanStockPrice、法人、持股、融資券、月營收、財報、PER）</p></div>
      <div class="cell"><p class="lab">資料日期</p><p class="num">{asof}</p><p class="sub">生成日 {date.today().isoformat()}</p></div>
      <div class="cell"><p class="lab">工具版本</p><p class="num">{esc(d['tool_version'])}</p></div>
      <div class="cell"><p class="lab">生成模型</p><p><span data-meta="model">{esc(gen['model'])}</span>，推理強度 <span data-meta="effort">{esc(gen['effort'])}</span></p></div>
    </div>
    <p class="disc">本報告僅供研究參考，不構成任何投資建議。</p>
    <p class="sub">標示「分析師判斷」者為判斷，其餘數字皆由腳本自 FinMind 計算；外部事實附出處與日期。<a href="../../index.html">回到報告目錄</a></p>
  </div>
</footer>
<script>{JS}</script>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
