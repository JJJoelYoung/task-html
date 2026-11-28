#!/usr/bin/env python3
"""Generate the 9933 CTCI equity report (Hallmark theme: Carnival, pressroom drop).

Layout and charts only: every number comes from data_9933.json,
analysis_9933.json, or derive.derive(). Run from anywhere:

  python scripts/equity/9933-20261127/generate_report.py
"""

import html
import re
import sys
from datetime import date
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
sys.path.insert(0, str(ROOT / ".agents" / "skills" / "tw-equity-report" / "scripts"))

import derive as dv  # noqa: E402

CODE = "9933"
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


def dspan(text, v):
    """Signed figure in Taiwan colours: red up, green down."""
    return f'<span data-dir="{dv.sign_dir(v)}">{text}</span>'


def yi(v):
    """NT$ amount in 億元."""
    return "無資料" if v is None else f"{v / 1e8:,.1f} 億"


def pct_plain(v, dec=1):
    return "無資料" if v is None else f"{v:.{dec}f}%"


def qlabel(q):
    y, mth = q[:4], int(q[5:7])
    return f"{y[2:]}Q{(mth - 1) // 3 + 1}"


POS_ZH = {"below_p25": "低於 P25", "p25_p75": "P25 至 P75", "p75_p90": "P75 至 P90", "above_p90": "高於 P90"}
ALIGN_ZH = {"bullish": "多頭排列", "bearish": "空頭排列", "mixed": "交錯"}
LEVEL_ZH = {"low": "低", "medium": "中", "high": "高，具軋空潛力"}
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


def kline_svg(series, title, lines=None, zone=None, vh=440, prev=None):
    """Candles, MA5/10/20/60 and volume. lines: [(key, label, value)]; prev: the bar before series[0]."""
    W, H = 1000, vh
    pad_l, pad_r, top = 8, 76, 16
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
    cw = max(1.4, pw / n * 0.6)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" class="chart">']
    for t in range(5):
        p = lo + (hi - lo) * t / 4
        yy = y(p)
        parts.append(f'<line class="grid" x1="{pad_l}" x2="{W - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        if t:
            parts.append(f'<text class="axis" x="{W - pad_r + 6}" y="{yy + 5:.1f}">{fp(dv.round_tick(p))}</text>')
    parts.append(f'<line class="grid" x1="{pad_l}" x2="{W - pad_r}" y1="{vol_bot:.1f}" y2="{vol_bot:.1f}"/>')
    parts.append(f'<text class="axis" x="{W - pad_r + 6}" y="{vol_top + 12:.1f}">{vmax:,} 張</text>')
    if zone:
        z0, z1 = y(zone[1]), y(zone[0])
        parts.append(f'<rect class="zone" x="{pad_l}" width="{pw}" y="{z0:.1f}" height="{max(2, z1 - z0):.1f}"/>')
    for k in ("ma60", "ma20", "ma10", "ma5"):
        pts = [f"{sx(i, n, pad_l, pw):.1f},{y(s[k]):.1f}" for i, s in enumerate(series) if s.get(k) is not None]
        if pts:
            parts.append(f'<polyline class="ln {k}" points="{" ".join(pts)}"/>')
    full = ([prev] if prev else []) + series
    off = 1 if prev else 0
    for i, s in enumerate(series):
        cx = sx(i, n, pad_l, pw)
        hook = f'data-date="{s["date"]}" data-dir="{dv.bar_dir(full, i + off)}"'
        yo, yc = y(s["open"]), y(s["close"])
        parts.append(f'<g class="k" {hook}><line class="wick" x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(s["high"]):.1f}" y2="{y(s["low"]):.1f}"/>'
                     f'<rect class="body" x="{cx - cw / 2:.1f}" y="{min(yo, yc):.1f}" width="{cw:.1f}" height="{max(1, abs(yc - yo)):.1f}"/></g>')
        vh_ = s["volume_lots"] / vmax * vol_h
        parts.append(f'<rect class="vol" {hook} x="{cx - cw / 2:.1f}" y="{vol_bot - vh_:.1f}" width="{cw:.1f}" height="{vh_:.1f}"/>')
    if lines:
        ly = spread([y(v) - 7 for _, _, v in lines], 26, top + 16, price_h - 4)
        for (key, label, v), lyy in zip(lines, ly):
            yy = y(v)
            parts.append(f'<g data-line="{key}" data-value="{v}" class="lvl lvl-{key}" data-tip="{esc(label)} {fp(v)}">'
                         f'<line x1="{pad_l}" x2="{W - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                         f'<text x="{pad_l + 6}" y="{lyy:.1f}">{esc(label)} {fp(v)}</text></g>')
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
    sw = "".join(f'<li><span class="sw sw-{k}" aria-hidden="true"></span>{lab}</li>' for k, lab in items)
    return (f'<ul class="legend">{sw}<li><span class="sw sw-k" data-dir="up" aria-hidden="true"></span>收紅（收 &gt; 開）</li>'
            f'<li><span class="sw sw-k" data-dir="down" aria-hidden="true"></span>收綠（收 &lt; 開）</li>'
            f'<li>十字線（收 = 開）依昨收定紅綠</li></ul>')


def bars_svg(labels, values, title, tips, unit="", vh=220, W=1000, hooks=None, cls_fn=None):
    """Vertical bars around a zero baseline; hooks add data attributes per bar."""
    H = vh
    pad_l, pad_r, top, bot = 8, 96, 14, 30
    n = len(values)
    known = [v for v in values if v is not None]
    vmax = max([0] + known)
    vmin = min([0] + known)
    if vmax == vmin:
        vmax = vmin + 1
    pw = W - pad_l - pad_r

    def y(v):
        return top + (vmax - v) / (vmax - vmin) * (H - top - bot)

    bw = min(24, pw / n * 0.66)
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
        cls = cls_fn(i, v) if cls_fn else ("bar pos" if v >= 0 else "bar neg")
        hk = f" {hooks[i]}" if hooks else ""
        out.append(f'<rect class="{cls}"{hk} x="{cx - bw / 2:.1f}" y="{min(yy, y0):.1f}" width="{bw:.1f}" height="{max(1, abs(y0 - yy)):.1f}"/>')
    out.append(f'<line class="zero" x1="{pad_l}" x2="{W - pad_r}" y1="{y0:.1f}" y2="{y0:.1f}"/>')
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
    pad_l, pad_r, top, bot = 8, 132, 16, 30
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
    for (lab, v), ly in zip(marks, spread([y(v) + 5 for _, v in marks], 24, top + 10, H - bot)):
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


def N(v):
    """Mark a table cell as numeric (tabular, right aligned)."""
    return (v,)


def table_fig(head, rows, caption, cls=""):
    """rows: lists of cells (N(...) marks numeric); ("FULL", html, label) adds a full-width note row."""
    labels = [esc(TAG_RE.sub("", h).strip()) for h in head]
    numcols = {k for r in rows if not (isinstance(r, tuple) and r[0] == "FULL")
               for k, c in enumerate(r) if isinstance(c, tuple)}
    th = "".join(f'<th scope="col"{" class=" + chr(34) + "num" + chr(34) if k in numcols else ""}>{h}</th>'
                 for k, h in enumerate(head))
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


def rows_dl(items):
    """Carnival ruled rows: (name, value_html, note_html)."""
    return '<dl class="rows">' + "".join(
        f'<div class="row"><dt>{esc(k)}</dt><dd><span class="row-v">{v}</span>{f"<small>{nt}</small>" if nt else ""}</dd></div>'
        for k, v, nt in items) + "</dl>"


# ---------------------------------------------------------------- content

series = d["price"]["series"]
src = d["sources"]
asof = d["asof"]
name_zh, name_en = a["name_zh"], a["name_en"]
scen = {s["name"]: s for s in x["scenarios"]}
base, bull, bear = scen["Base"], scen["Bull"], scen["Bear"]
method = a["valuation_method"]
imp_metric = "PBR" if method == "PER" else "PER"
verdicts = a.get("verdicts", {})
judg = '<span class="tag">分析師判斷</span>'


def rng(key):
    r = src[key]["range"]
    return f"{r[0]} 至 {r[1]}"


def sec_head(i, title):
    v = verdicts.get(f"dim{i}")
    lead = f'<p class="lead">{esc(v)} {judg}</p>' if v else ""
    return f'<header class="sec-head"><h2 id="h{i}x">{esc(title)}</h2>{lead}</header>'


# --- hero
def kfig(label, key, value, sign=None, small=False):
    d_ = f' data-dir="{dv.sign_dir(sign)}"' if sign is not None else ""
    return (f'<div class="kf{" kf--s" if small else ""}"><p class="kf-v num" data-kpi="{key}"{d_}>{esc(value)}</p>'
            f'<p class="kf-l">{label}</p></div>')


gaps_txt = "、".join(esc(g) for g in d["gaps"]) if d["gaps"] else "本次 FinMind 抓取無缺口。"
hero = f"""
<section class="hero" aria-labelledby="hero-h">
  <div class="container hero-head">
    <h1 id="hero-h"><span class="h1-name">{esc(name_zh)}</span> <span class="h1-code">{CODE}</span></h1>
    <div class="hero-side">
      <p class="lead">{esc(a['hero_line'])}</p>
      <div class="actions"><a class="btn btn--primary" href="#dim6">看交易計畫</a><a class="btn" href="#dim4">看估值</a></div>
    </div>
  </div>
  <div class="label-band">
    <div class="container">
      <div class="call">
        <div class="call-main">
          <p class="kf-l">當前動作，{esc(name_en)}，{MARKET_ZH.get(a['market'], a['market'])}，{esc(a['industry'])}</p>
          <p class="act" data-kpi="action">{esc(x['action_zh'])}</p>
          <p class="note"><samp class="derived">{esc(x['action_note'])}</samp></p>
        </div>
        <div class="halftone" aria-hidden="true"></div>
      </div>
      <div class="kfs">
        {kfig("收盤價（NT$）", "close", fp(x["close"]))}
        {kfig("投資評等", "rating", x["rating_zh"])}
        {kfig("Base 目標價", "target", fp(base["target"]))}
        {kfig("Base 潛在漲跌", "upside", fpct(base["upside_pct"]), sign=base["upside_pct"])}
        {kfig("拉回 R:R", "rr", frr(x["rr_pullback"]))}
        {kfig("資料日期", "asof", asof, small=True)}
      </div>
    </div>
  </div>
</section>
"""

# --- dim1
last = series[-1]
fs = m["float_settling"]
dim1_chart = kline_svg(series, f"{name_zh} 日 K 線與均線，{rng('price')}")
trend_txt = "通過" if x["trend_ok"] else "未通過"
dim1 = f"""
<section id="dim1" class="sec" aria-labelledby="h1x">
  <div class="container">
  {sec_head(1, "價量與均線")}
  {figure(dim1_chart, f"日 K、MA5／10／20／60 與成交量（張）。價格軸非零起點。來源：FinMind TaiwanStockPrice，{rng('price')}。", ma_legend(), wide=True)}
  <div class="split-rows">
    {rows_dl([
        ("均線排列", ALIGN_ZH[m['alignment']], f"MA5 {fp(m['ma5'])}，MA10 {fp(m['ma10'])}，MA20 {fp(m['ma20'])}，MA60 {fp(m['ma60'])}"),
        ("均線斜率", f"MA20 {m['ma20_slope_5d']:+,.2f}", f"5 日變動；MA60 {m['ma60_slope_5d']:+,.2f}。趨勢濾網{trend_txt}"),
        ("均線糾結", "是" if m['squeeze'] else "否", f"MA5／10／20 價差 {pct_plain(m['ma_spread_pct'])}，門檻 2%"),
        ("乖離 MA20", dspan(fpct(m['bias_ma20_pct']), m['bias_ma20_pct']), f"收盤 {fp(m['close'])} 對 MA20 {fp(m['ma20'])}"),
    ])}
    {rows_dl([
        ("近 20 日高低", f"{fp(m['w20_high'])}／{fp(m['w20_low'])}", f"高 {m['w20_high_date']}，低 {m['w20_low_date']}"),
        ("20 日均量", f"{m['vol_avg20_lots']:,} 張", f"{asof} 成交 {last['volume_lots']:,} 張"),
        ("爆量日", f"{len(m['spike_days'])} 天", "、".join(m['spike_days']) or "無"),
        ("浮額沉澱", "成立" if fs['signal'] else "未成立", f"融資增減 {lots_signed(fs['margin_change'])}，量縮日 {fs['dryup_count']} 天（需融資減少且 ≥ 5 天）"),
    ])}
  </div>
  <p class="read">量縮日（&lt; 0.6 倍均量）{len(m['dryup_days'])} 天：{'、'.join(m['dryup_days']) or '無'}。近 60 日高點 {fp(m['high60'])}（{m['high60_date']}），低點 {fp(m['low60'])}（{m['low60_date']}）。</p>
  </div>
</section>
"""

# --- dim2
inst = d["institutional"]
days = inst["daily"]
dl = [r["date"][5:] for r in days]


def flow_fig(key):
    vals = [r[key] for r in days]
    tips = [f"{r['date']}　{GROUP_ZH[key]}買賣超 {lots_signed(r[key])}　累計 {lots_signed(r[key + '_cum'])}" for r in days]
    hooks = [f'data-flow="{key}" data-date="{r["date"]}" data-dir="{dv.sign_dir(r[key])}"' for r in days]
    svg = bars_svg(dl, vals, f"{GROUP_ZH[key]}每日買賣超", tips, vh=240, W=480, hooks=hooks,
                   cls_fn=lambda i, v: "bar flow")
    return (f'<div class="flow"><p class="flow-l">{GROUP_ZH[key]}，近 20 日累計</p>'
            f'<p class="flow-v num">{dspan(lots_signed(inst["cum"][key]), inst["cum"][key])}</p>'
            f'{figure(svg, f"每日買賣超（張）。來源：FinMind TaiwanStockInstitutionalInvestorsBuySell，{rng("institutional")}。")}</div>')


fh = d["foreign_holding"]
fh_svg = line_svg([r["date"][5:] for r in fh["series"]], [r["ratio"] for r in fh["series"]], "外資持股比率",
                  [f"{r['date']}　外資持股 {r['ratio']:.2f}%" for r in fh["series"]], lambda v: f"{v:.2f}%",
                  current=fh["last"], vh=250)
mg = d["margin"]
mg_svg = line_svg([r["date"][5:] for r in mg["series"]], [r["short"] for r in mg["series"]], "融券餘額",
                  [f"{r['date']}　融資 {r['margin']:,} 張　融券 {r['short']:,} 張　券資比 {r['short'] / r['margin'] * 100:.1f}%" for r in mg["series"]],
                  lambda v: f"{v:,.0f}", current=mg["short_last"], vh=250)
cz = inst["cost_zone"]
cz_txt = (f"{fp(dv.round_tick(cz['low']))} 至 {fp(dv.round_tick(cz['high']))}，依{GROUP_ZH[cz['group']]} {cz['days']} 個買超日量加權"
          if cz else "無（外資與投信買超日皆不足 3 天）")
dim2 = f"""
<section id="dim2" class="sec" aria-labelledby="h2x">
  <div class="container">
  {sec_head(2, "籌碼結構")}
  <div class="flows">{flow_fig('foreign')}{flow_fig('trust')}{flow_fig('dealer')}</div>
  <div class="pair">
    <div><p class="flow-l">外資持股比率，{fh['first']:.2f}% 至 {fh['last']:.2f}%</p><p class="flow-v num">{dspan(f"{fh['change_pp']:+.2f} 個百分點", fh['change_pp'])}</p>
      {figure(fh_svg, f"外資持股比率（%），縱軸非零起點，區間高 {fh['high']:.2f}%、低 {fh['low']:.2f}%。來源：FinMind TaiwanStockShareholding，{rng('foreign_holding')}。")}</div>
    <div><p class="flow-l">融券餘額，{mg['short_first']:,} 至 {mg['short_last']:,} 張</p><p class="flow-v num">{dspan(lots_signed(mg['short_change']), mg['short_change'])}</p>
      {figure(mg_svg, f"融券餘額（張），縱軸非零起點；停在任一天可看當日融資與券資比。來源：FinMind TaiwanStockMarginPurchaseShortSale，{rng('margin')}。")}</div>
  </div>
  {rows_dl([
      ("融資餘額", f"{mg['margin_last']:,} 張", f"由 {mg['margin_first']:,} 張變動 {lots_signed(mg['margin_change'])}（{fpct(mg['margin_change_pct'])}）"),
      ("券資比", pct_plain(mg['short_margin_ratio_pct']), f"水位：{LEVEL_ZH[mg['short_margin_level']]}；低於 5% 為低，5% 至 20% 為中，高於 20% 為高"),
      ("法人成本區", fp(dv.round_tick(cz['price'])) if cz else "無", esc(cz_txt)),
  ])}
  </div>
</section>
"""

# --- dim3
rev = d["revenue"]
s24 = rev["series24"]
l12 = rev["last12"]
yoy_map = {r["period"]: r["yoy_pct"] for r in l12}
mom_map = {r["period"]: r["mom_pct"] for r in l12}
rev_svg = bars_svg([r["period"] for r in s24], [r["revenue"] / 1e8 for r in s24], "月營收（億元）",
                   [f"{r['period']}　營收 {yi(r['revenue'])}" + (f"　MoM {fpct(mom_map[r['period']])}　YoY {fpct(yoy_map[r['period']])}" if r['period'] in yoy_map else "") for r in s24],
                   vh=250, cls_fn=lambda i, v: "bar rev" + (" rev-last" if i == len(s24) - 1 else ""))
yoy_hooks = [f'data-dir="{dv.sign_dir(r["yoy_pct"])}"' for r in l12]
yoy_svg = bars_svg([r["period"] for r in l12], [r["yoy_pct"] for r in l12], "月營收年增率（%）",
                   [f"{r['period']}　YoY {fpct(r['yoy_pct'])}" for r in l12], unit="%", vh=190, hooks=yoy_hooks,
                   cls_fn=lambda i, v: "bar flow")
qs = fin["quarters"][-4:]
q_rows = [[qlabel(q["quarter"]), N(f"{q['eps']:.2f}"), N(yi(q["revenue"])), N(pct_plain(q["gross_margin_pct"], 2)),
           N(pct_plain(q["operating_margin_pct"], 2)), N(yi(q["non_operating"])),
           N(f"{q['dsi_days']:.1f}" if q.get("dsi_days") is not None else "無資料")] for q in qs]
q_tbl = table_fig(["季度", "EPS（元）", "營收", "毛利率", "營益率", "業外收支", "存貨天數"], q_rows,
                  f"近 4 季財報；存貨天數 = 期初期末平均存貨 ÷ 季營業成本 × 91。來源：FinMind TaiwanStockFinancialStatements／TaiwanStockBalanceSheet，{qs[0]['quarter']} 至 {qs[-1]['quarter']}。")
cc = fin["cash_conversion"]
dil = a["dilution"]
eq = a["earnings_quality"]
dim3 = f"""
<section id="dim3" class="sec" aria-labelledby="h3x">
  <div class="container">
  {sec_head(3, "營運與財務")}
  <div class="figs4">
    <div><p class="fg-v num">{yi(l12[-1]['revenue'])}</p><p class="fg-l">{rev['latest_period']} 單月營收，MoM {dspan(fpct(l12[-1]['mom_pct']), l12[-1]['mom_pct'])}，YoY {dspan(fpct(l12[-1]['yoy_pct']), l12[-1]['yoy_pct'])}</p></div>
    <div><p class="fg-v num">{yi(rev['ytd'])}</p><p class="fg-l">今年累計至 {rev['latest_period']}，YoY {dspan(fpct(rev['ytd_yoy_pct']), rev['ytd_yoy_pct'])}，去年同期 {yi(rev['ytd_prev'])}</p></div>
    <div><p class="fg-v num">{fin['ttm_eps']:.2f} 元</p><p class="fg-l">近 4 季 EPS 合計（TTM），最新季 {qlabel(qs[-1]['quarter'])} {qs[-1]['eps']:.2f} 元</p></div>
    <div><p class="fg-v num">{cc['ratio']:.2f}</p><p class="fg-l">現金轉換率（TTM 營業現金流 {yi(cc['ttm_ocf'])} ÷ 淨利 {yi(cc['ttm_net_income'])}）</p></div>
  </div>
  {figure(rev_svg, f"月營收（億元），縱軸自零起，最新月為琥珀色。來源：FinMind TaiwanStockMonthRevenue，{rng('revenue')}。", wide=True)}
  {figure(yoy_svg, f"近 12 個月營收年增率（%），紅為正、綠為負。來源：FinMind TaiwanStockMonthRevenue，{l12[0]['period']} 至 {l12[-1]['period']}。", wide=True)}
  {q_tbl}
  <div class="pair">
    <div class="well" data-dilution><p class="well-h">股本稀釋：可轉債與現金增資</p>
      <p class="well-v">可轉債 {'有' if dil['has_cb'] else '無'}；現增 {'有' if dil['has_spo'] else '無'}</p>
      <p>{linkify(dil['summary'])}</p><p class="basis">依據：{linkify(dil['basis'])}</p></div>
    <div class="well"><p class="well-h">獲利品質：{esc(eq['focus'])} {judg}</p><p>{linkify(eq['text'])}</p><p class="basis">依據：{linkify(eq['basis'])}</p></div>
  </div>
  </div>
</section>
"""

# --- dim4
val = d["valuation"]


def band_fig(key):
    b = val[key]
    ser = b["series"]
    svg = line_svg([r["date"][:7] for r in ser], [r["v"] for r in ser], f"5 年 {key} 區間",
                   [f"{r['date']}　{key} {r['v']:.2f}x" for r in ser], lambda v: f"{v:.1f}x",
                   refs=[(p.upper(), b[p]) for p in ("p10", "p25", "p50", "p75", "p90")], current=b["current"], vh=270)
    return (f'<div><p class="flow-l">{key} 現值，5 年百分位 {b["current_percentile"]:.1f}%</p><p class="flow-v num">{fmult(b["current"])}</p>'
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
                     f"同業估值矩陣，{d['peers']['rows'][0]['date']} 收盤。來源：FinMind TaiwanStockPER，{val['date']}。", cls="wide")

sc_rows = []
for s in x["scenarios"]:
    im = s["implied"]
    sc_rows.append([
        f"<strong>{esc(s['label'])}</strong>（{s['name']}）",
        N(f"{s['probability']}%"),
        N(f"{s['eps']:.2f}"),
        N(fmult(s["multiple"])),
        N(fp(s["target"])),
        N(dspan(fpct(s["upside_pct"]), s["upside_pct"])),
        N(f'<span data-implied="{s["name"]}">{fmult(im["value"])}</span>' if im else "無資料"),
        POS_ZH[im["position"]] if im else "",
    ])
    sc_rows.append(("FULL", f"<p>{esc(s['assumptions'])}</p><p class=\"basis\">依據：{linkify(s['basis'])}</p>", f"{s['label']}情境假設與依據"))
sc_tbl = table_fig(["情境", "機率", "前瞻 EPS（元）" if method == "PER" else "BVPS（元）", f"{method} 倍數", "目標價", "潛在漲跌",
                    f"隱含 {imp_metric}", f"{imp_metric} 帶位置"], sc_rows,
                   f"12 個月情境目標價，{judg}；每個情境下一列為假設與依據。倍數錨定 FinMind TaiwanStockPER 5 年 {method} 區間（{val['start']} 至 {val['date']}），隱含 {imp_metric} 以 BVPS {fin['bvps_latest']:.2f} 元（{fin['latest_quarter']}）計。", cls="wide")
hv = ""
if cb.get("applicable") and cb.get("high_volatility"):
    hv = f'<p class="warn">高波動提示：{"；".join(VOL_ZH.get(r, r) for r in cb["volatility_reasons"])}。基準只供量級比對，不宜直接當預測。</p>'
dev = x["baseline_deviation_pct"]
bl_on = cb.get("applicable") and method == "PER"
baseline = f"""
<div class="figs4 baseline">
  <div><p class="fg-v num" data-baseline="cy">{feps(cb.get('cy_eps') if bl_on else None)}</p><p class="fg-l">核心基準 EPS，{asof[:4]} 曆年（CY）：今年累計營收加去年剩餘月份 ×（1 + 6 個月 YoY 中位數 {pct_plain(cb.get('yoy6_median_pct'))}）</p></div>
  <div><p class="fg-v num" data-baseline="ntm">{feps(cb.get('ntm_eps') if bl_on else None)}</p><p class="fg-l">核心基準 EPS，未來 12 個月（NTM）：TTM 營收 ×（1 + 6 個月 YoY 中位數）</p></div>
  <div><p class="fg-v num">{pct_plain(cb.get('core_net_margin_pct'), 2)}</p><p class="fg-l">核心淨利率：TTM 營益率 {pct_plain(cb.get('ttm_opm_pct'), 2)} ×（1 − 稅率 {pct_plain(cb.get('effective_tax_rate_pct'), 2)}）× 母公司比 {pct_plain(cb.get('parent_ratio_pct'), 2)}</p></div>
  <div><p class="fg-v num">{dspan(fpct(dev), dev) if dev is not None else '不適用'}</p><p class="fg-l">Base 前瞻 EPS {base['eps']:.2f} 元對 NTM 基準的差距</p></div>
</div>
{hv}
"""
scen_figs = '<div class="figs3 scen-figs">' + "".join(
    f'<div><p class="fg-v num">{fp(s["target"])}</p><p class="fg-l">{esc(s["label"])}（{s["name"]}），機率 {s["probability"]}%，'
    f'{dspan(fpct(s["upside_pct"]), s["upside_pct"])}；EPS {s["eps"]:.2f} 元 × {s["multiple"]:g}x</p></div>'
    for s in (bull, base, bear)) + "</div>"
dim4 = f"""
<section id="dim4" class="sec" aria-labelledby="h4x">
  <div class="container">
  {sec_head(4, "估值與目標價")}
  <div class="pair">{band_fig('PER')}{band_fig('PBR')}</div>
  <p class="read">估值方法：{esc(method)}。{linkify(a['valuation_method_basis'])}</p>
  {peer_tbl}
  {scen_figs}
  {sc_tbl}
  {baseline}
  </div>
  <div class="slate-band">
    <div class="container figs3">
      <div><p class="sb-v num">{fp(x['weighted_target'])}</p><p class="sb-l">機率加權目標價，對收盤 {dspan(fpct(x['weighted_upside_pct']), x['weighted_upside_pct'])}</p></div>
      <div><p class="sb-v">{x['rating_zh']}</p><p class="sb-l">評等依 Base {fp(base['target'])}（{dspan(fpct(base['upside_pct']), base['upside_pct'])}）；高於 +15% 買進，−5% 至 +15% 中立，低於 −5% 賣出</p></div>
      <div><p class="sb-v num">{fp(x['fair_buy'])}</p><p class="sb-l">合理買進價（Base ÷ 1.15），收盤低於此價時評等為買進</p></div>
    </div>
  </div>
</section>
"""

# --- dim5
def item_rows(items):
    return [[f"<strong>{esc(i['title'])}</strong>", esc(i["timing"]), esc(i["direction"]), esc(i["indicator"]),
             f"{linkify(i['basis'])}"] for i in items]


moat = "".join(f'<li><h3>{esc(mo["title"])}</h3><p>{esc(mo["text"])}</p><p class="basis">依據：{linkify(mo["basis"])}</p></li>' for mo in a["moat"])
facts = "".join(f'<li><p>{esc(f["text"])}</p><p class="src"><a href="{esc(f["url"])}" rel="noopener" target="_blank">{esc(f["source"])}</a>，{esc(f["date"])}</p></li>' for f in a["external_facts"])
dim5 = f"""
<section id="dim5" class="sec" aria-labelledby="h5x">
  <div class="container">
  {sec_head(5, "催化劑與風險")}
  <p class="moat-l">護城河 {judg}</p>
  <ul class="moat">{moat}</ul>
  {table_fig(["催化劑", "時間", "方向", "觀察指標", "依據"], item_rows(a['catalysts']), f"催化劑，{judg}；外部事實出處見下方清單，市場數據來源 FinMind，截至 {asof}。", cls="wide")}
  {table_fig(["風險", "時間", "方向", "觀察指標", "依據"], item_rows(a['risks']), f"風險，{judg}；外部事實出處見下方清單，市場數據來源 FinMind，截至 {asof}。", cls="wide")}
  <h3 class="sub-h">外部事實與出處</h3>
  <ol class="facts">{facts}</ol>
  </div>
</section>
"""

# --- dim6
def status_txt(k):
    st = x[k]
    return "成立" if st == "active" else dv.SETUP_STATUS_ZH[st]


def rr_block(key, v):
    flag = '<p class="sub">R:R &lt; 1.5，不具交易吸引力</p>' if v is not None and v < 1.5 else ""
    return f'<p class="rr num" data-rr="{key}">{frr(v)}</p>{flag}'


zone_src = "均線帶與法人成本區重疊" if x["zone_source"] == "overlap" else "MA10 與 MA20 均線帶"
stop_src = "量最大日低點與 MA20 × 0.97 中較近者" if x["hard_stop_source"] == "candidate" else "進場區下緣 × 0.95"
last60 = series[-60:]
lines6 = [("entry", "進場", x["entry"]), ("t1", "T1", x["t1"]), ("t2", "T2", x["t2"]), ("sl", "停損", x["hard_stop"])]
dim6_svg = kline_svg(last60, f"{name_zh} 近 60 日 K 線與交易價位", lines=lines6, zone=(x["zone_low"], x["zone_high"]), vh=470,
                     prev=series[-61] if len(series) > 60 else None)
breakers_tbl = table_fig(["條件", "門檻", "資料集"], [[esc(t["condition"]), esc(t["threshold"]), esc(t["dataset"])] for t in a["thesis_breakers"]],
                         f"論點破功條件，{judg}；以 FinMind 資料集追蹤，基準日 {asof}。")
dim6 = f"""
<section id="dim6" class="sec" aria-labelledby="h6x">
  <div class="container">
  {sec_head(6, "交易部位與風控")}
  {figure(dim6_svg, f"近 60 日 K 線；琥珀帶為拉回進場區 {fp(x['zone_low'])} 至 {fp(x['zone_high'])}，水平線為進場、T1、T2 與停損。價格軸非零起點。來源：FinMind TaiwanStockPrice，{last60[0]['date']} 至 {last60[-1]['date']}。", ma_legend(), wide=True)}
  <h3 class="sub-h">波段層，數週：回檔 R:R {dv.fmt_rr(x['rr_pullback'])}，突破 R:R {dv.fmt_rr(x['rr_breakout'])}</h3>
  <div class="pair">
    <div class="well"><p class="well-h">拉回策略：{esc(status_txt('pullback_status'))}</p>
      <dl class="kv">
        <dt>進場區（{zone_src}）</dt><dd class="num">{fp(x['zone_low'])} 至 {fp(x['zone_high'])}</dd>
        <dt>進場價（區間中點）</dt><dd class="num">{fp(x['entry'])}</dd>
        <dt>T1 技術目標</dt><dd class="num">{fp(x['t1'])}</dd>
        <dt>T2 波段目標（費波納契 1.618 與 Bull 取低）</dt><dd class="num">{fp(x['t2'])}</dd>
        <dt>硬停損（{stop_src}）</dt><dd class="num">{fp(x['hard_stop'])}</dd>
      </dl>
      <p class="well-h">拉回 R:R</p>{rr_block('pullback', x['rr_pullback'])}</div>
    <div class="well"><p class="well-h">突破策略：{esc(status_txt('breakout_status'))}</p>
      <dl class="kv">
        <dt>突破點（近 60 日最高）</dt><dd class="num">{fp(x['trigger'])}</dd>
        <dt>量能條件（&gt; 1.5 倍 20 日均量）</dt><dd class="num">{x['trigger_volume_lots']:,} 張</dd>
        <dt>T2 波段目標</dt><dd class="num">{fp(x['t2'])}</dd>
        <dt>突破停損（突破點 × 0.95）</dt><dd class="num">{fp(x['breakout_stop'])}</dd>
      </dl>
      <p class="well-h">突破 R:R</p>{rr_block('breakout', x['rr_breakout'])}</div>
  </div>
  <h3 class="sub-h">持有層，12 個月：R:R {dv.fmt_rr(x['rr_hold'])}{'，下檔大於上檔' if (x['rr_hold'] or 0) < 1 else ''}</h3>
  <div class="figs4">
    <div><p class="fg-v num">{fp(x['fair_buy'])}</p><p class="fg-l">合理買進價（Base 目標 ÷ 1.15）</p></div>
    <div><p class="fg-v num">{fp(base['target'])}</p><p class="fg-l">Base 目標價，{dspan(fpct(base['upside_pct']), base['upside_pct'])}</p></div>
    <div><p class="fg-v num">{fp(bear['target'])}</p><p class="fg-l">Bear 目標價，{dspan(fpct(bear['upside_pct']), bear['upside_pct'])}</p></div>
    <div><p class="fg-l">持有 R:R：{esc(status_txt('hold_status'))}</p>{rr_block('hold', x['rr_hold'])}</div>
  </div>
  <h3 class="sub-h">論點破功條件</h3>
  {breakers_tbl}
  </div>
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

CSS = r"""/* Hallmark · shape: stat-led · genre: editorial · theme: Carnival (deal 1/3, seed 9933-equity-research-b9e6·ce12e4cc·2026-11-28·r0) · job: decide (read the current action, then the trade plan) · draw: none (sections fixed by report-contract)
 * hero: banner, the company head over a full-bleed amber label band · nav: slab, an ink bar with the wordmark, six section links and the mode toggle · footer: mast, the company name large over the colophon · imagery: none (charts are the material) · signature: the amber plant tag, the call at poster size over its six figures parted by ink bars, a halftone corner · carnival: pressroom
 * axes: light/display-heavy/chromatic-yellow · posture: full-palette (field amber, seal slate, ink, paper) · contrast: pass · fold: pass · modes: light+dark · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 · weakest: S, a contract-fixed report reads like any other stock; made the amber plant tag the first screen and pinned every chart as a print on the hard shadow */
/* Hallmark · waive 26b · no control on the page can ever be disabled · the controls are two anchor buttons, six nav links and the mode toggle */
/* Hallmark · waive 79 · the linter stops the hero at the actions, above the full-bleed amber band · that band holds the current action, its condition and the six contract KPI figures built from FinMind */
/* Hallmark · waive 82 · the repeated rects are transparent per-day hover targets that carry data-tip values · they are not visible counting marks */
TOKENS_CSS
BASE_CSS
:root {
  color-scheme: light dark;
  --font-display: "Big Shoulders Display", "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", Impact, sans-serif;
  --font-body: "Golos Text", "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", system-ui, sans-serif;
  --chart-ma5: oklch(72% 0.05 240); --chart-ma10: oklch(58% 0.07 240); --chart-ma20: oklch(44% 0.09 240); --chart-ma60: var(--color-ink);
  --chart-zone: color-mix(in oklab, var(--color-accent) 50%, transparent);
  --chart-bar: var(--color-accent-2);
  --tw-up: oklch(45% 0.18 27); --tw-down: oklch(43% 0.12 150); --tw-flat: var(--color-muted);
  --tw-up-acc: oklch(40% 0.17 27); --tw-down-acc: oklch(37% 0.11 150);
  --container: 1360px;
}
[data-mode="dark"] {
  --color-paper: oklch(17% 0.015 65); --color-paper-2: oklch(20.5% 0.017 65); --color-paper-3: oklch(24% 0.019 65);
  --color-ink: oklch(93% 0.015 65); --color-ink-2: oklch(85% 0.015 65); --color-muted: oklch(73% 0.02 65);
  --color-rule: oklch(70% 0.08 240); --color-accent: oklch(80% 0.15 75); --color-accent-2: oklch(70% 0.08 240);
  --color-accent-ink: oklch(16% 0.02 60); --color-focus: oklch(76% 0.09 240);
  --shadow-card: none;
  --chart-ma5: oklch(50% 0.05 240); --chart-ma10: oklch(62% 0.07 240); --chart-ma20: oklch(76% 0.08 240);
  --chart-zone: color-mix(in oklab, var(--color-accent) 30%, transparent);
  --tw-up: oklch(72% 0.16 25); --tw-down: oklch(74% 0.14 150); --tw-up-sb: oklch(32% 0.13 27); --tw-down-sb: oklch(32% 0.10 150);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-mode="light"]) {
    --color-paper: oklch(17% 0.015 65); --color-paper-2: oklch(20.5% 0.017 65); --color-paper-3: oklch(24% 0.019 65);
    --color-ink: oklch(93% 0.015 65); --color-ink-2: oklch(85% 0.015 65); --color-muted: oklch(73% 0.02 65);
    --color-rule: oklch(70% 0.08 240); --color-accent: oklch(80% 0.15 75); --color-accent-2: oklch(70% 0.08 240);
    --color-accent-ink: oklch(16% 0.02 60); --color-focus: oklch(76% 0.09 240);
    --shadow-card: none;
    --chart-ma5: oklch(50% 0.05 240); --chart-ma10: oklch(62% 0.07 240); --chart-ma20: oklch(76% 0.08 240);
    --chart-zone: color-mix(in oklab, var(--color-accent) 30%, transparent);
    --tw-up: oklch(72% 0.16 25); --tw-down: oklch(74% 0.14 150); --tw-up-sb: oklch(32% 0.13 27); --tw-down-sb: oklch(32% 0.10 150);
  }
}
html, body { overflow-x: clip; }
body { font-size: 1.0625rem; line-height: 1.6; }
strong, b { font-weight: 500; }
h1, h2 { text-transform: uppercase; line-height: 1.02; }
h3 { font-family: var(--font-body); font-weight: 500; letter-spacing: 0; }
a { text-decoration-color: var(--color-accent-2); }
a:hover { text-decoration-thickness: 2px; }
abbr { text-decoration: none; }
[data-dir="up"] { color: var(--tw-up); } [data-dir="down"] { color: var(--tw-down); } [data-dir="flat"] { color: var(--tw-flat); }

.slab { background: var(--color-ink); color: var(--color-paper); }
.slab .container { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-xs) var(--space-lg); padding-block: var(--space-sm); }
.mark { font: 800 var(--text-xl)/1 var(--font-display); text-transform: uppercase; text-decoration: none; color: var(--color-paper); }
.slab nav { margin-inline-start: auto; }
.slab ul { display: flex; flex-wrap: wrap; gap: var(--space-2xs) var(--space-lg); margin: 0; padding: 0; list-style: none; font-size: var(--text-md); }
.slab nav a { color: var(--color-paper); text-decoration: none; font-weight: 500; }
.slab nav a:hover { color: var(--color-accent); }
.slab a:focus-visible, .btn-mode:focus-visible { outline: 2px solid var(--color-paper); outline-offset: 3px; }
.btn-mode { min-height: 44px; padding: 0 var(--space-md); border: var(--rule-bar) solid var(--color-paper); border-radius: var(--radius-pill); background: transparent; color: var(--color-paper); font: 500 var(--text-sm)/1 var(--font-body); white-space: nowrap; cursor: pointer; transition: background-color var(--dur-short) var(--ease-out), color var(--dur-short) var(--ease-out); }
.btn-mode:hover { background: var(--color-paper); color: var(--color-ink); }
.btn-mode:active { background: var(--color-accent); color: var(--color-accent-ink); }

.hero { padding-block: var(--space-xl) 0; }
.hero-head { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); gap: var(--space-lg) var(--space-2xl); align-items: end; padding-bottom: var(--space-xl); }
.hero h1 { max-width: none; font-size: clamp(2.75rem, 4.5vw + 0.75rem, 5.5rem); line-height: 1; }
.h1-code { font-variant-numeric: tabular-nums; }
.hero-side .lead { color: var(--color-ink-2); }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-md); margin-top: var(--space-lg); }
.btn { display: inline-flex; align-items: center; min-height: 48px; padding: 0 var(--space-lg); border: var(--rule-bar) solid var(--color-ink); border-radius: var(--radius-pill); background: var(--color-paper); color: var(--color-ink); box-shadow: var(--shadow-card); font: 800 var(--text-lg)/1 var(--font-display); text-decoration: none; white-space: nowrap; transition: background-color var(--dur-micro) var(--ease-out), color var(--dur-micro) var(--ease-out); }
.btn:hover { background: var(--color-paper-3); }
.btn--primary { background: var(--color-accent); color: var(--color-accent-ink); }
.btn--primary:hover { background: var(--color-ink); color: var(--color-paper); }
.btn:active { box-shadow: 1px 1px 0 var(--color-ink); }
.btn:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 3px; }

.label-band { background: var(--color-accent); color: var(--color-accent-ink); border-block: var(--rule-bar) solid var(--color-ink); padding-block: var(--space-2xl) var(--space-xl); --tw-up: var(--tw-up-acc); --tw-down: var(--tw-down-acc); }
.call { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--space-lg) var(--space-xl); }
.call-main { min-width: 0; }
.act { font: 800 clamp(4rem, 13vw, 12.5rem)/1 var(--font-display); letter-spacing: var(--tracking-display); overflow-wrap: break-word; min-width: 0; margin-block: var(--space-xs) var(--space-md); }
.note { font-size: var(--text-lead); font-weight: 500; line-height: 1.4; max-width: 40ch; }
samp.derived { font: inherit; }
.halftone { width: 144px; height: 144px; background-image: radial-gradient(var(--color-accent-ink) 1.5px, transparent 1.5px); background-size: 12px 12px; }
.kfs { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); margin-top: var(--space-xl); border-top: var(--rule-bar) solid var(--color-accent-ink); }
.kf { padding: var(--space-md) var(--space-md) 0; border-left: var(--rule-bar) solid var(--color-accent-ink); min-width: 0; }
.kf:first-child { padding-left: 0; border-left: 0; }
.kf-v { font: 800 clamp(2rem, 2.6vw + 0.75rem, 3.25rem)/1.05 var(--font-display); white-space: nowrap; }
.kf--s .kf-v { font-size: var(--text-xl); }
.kf-l { font-size: var(--text-sm); font-weight: 500; margin-top: var(--space-2xs); }
.gapnote { font-size: var(--text-sm); color: var(--color-muted); padding-block: var(--space-md); }

#dim1 { padding-top: var(--section-gap-s); }
.sec { padding-block: var(--space-3xl); border-top: var(--rule-bar) solid var(--color-accent-2); }
.sec:nth-of-type(odd) { padding-block: var(--space-4xl) var(--space-3xl); }
.sec-head { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: var(--space-md) var(--space-2xl); align-items: end; margin-bottom: var(--space-2xl); }
.sec-head h2 { max-width: none; }
.sec-head .lead { color: var(--color-ink-2); }
.sub-h { font-size: var(--text-title); margin-block: var(--space-3xl) var(--space-sm); }
.read { max-width: 72ch; margin-block: var(--space-lg); }
.tag { display: inline-block; font-size: var(--text-xs); font-weight: 500; line-height: 1.5; padding: 0 var(--space-2xs); border: var(--rule-hair) solid currentColor; border-radius: var(--radius-pill); vertical-align: 0.12em; white-space: nowrap; }

.fig { margin: var(--space-lg) 0 0; min-width: 0; }
.fig figcaption { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-sm); max-width: 90ch; }
.plot { border: var(--rule-bar) solid var(--color-ink); border-radius: var(--radius-card); background: var(--color-paper-2); box-shadow: var(--shadow-card); padding: var(--space-sm); }
.chart { width: 100%; height: auto; }
.chart text { font-family: var(--font-body); font-size: var(--fs, 13px); fill: var(--color-muted); font-variant-numeric: tabular-nums; }
.chart .grid, .chart .ref { stroke: var(--color-paper-3); stroke-width: 1; }
.chart .ref-mid { stroke: var(--color-muted); }
.chart .zero { stroke: var(--color-muted); stroke-width: 1; }
.chart .wick { stroke: currentColor; stroke-width: 1; }
.chart .body { fill: currentColor; }
.chart .k[data-dir="flat"] .body { stroke: currentColor; stroke-width: 1.5; }
.chart .vol { fill: currentColor; fill-opacity: 0.55; }
.chart .ln { fill: none; stroke-width: 2; stroke-linejoin: round; }
.chart .ma5 { stroke: var(--chart-ma5); } .chart .ma10 { stroke: var(--chart-ma10); } .chart .ma20 { stroke: var(--chart-ma20); } .chart .ma60 { stroke: var(--chart-ma60); stroke-width: 2.5; }
.chart .main { stroke: var(--color-ink); }
.chart .dot { fill: var(--color-accent); stroke: var(--color-ink); stroke-width: 2; }
.chart .bar.flow { fill: currentColor; }
.chart .bar.rev { fill: var(--chart-bar); }
.chart .bar.rev-last { fill: var(--color-accent); stroke: var(--color-ink); stroke-width: 1.5; }
.chart .zone { fill: var(--chart-zone); }
.chart .lvl line { stroke: var(--color-ink); stroke-width: 1.5; }
.chart .lvl-sl line { stroke-width: 3; }
.chart .lvl-entry line { stroke: var(--color-accent-2); stroke-width: 2.5; }
.chart .lvl text { fill: var(--color-ink); font-weight: 500; paint-order: stroke; stroke: var(--color-paper-2); stroke-width: 5px; }
.chart .hit { fill: transparent; }
.chart .hit:hover { fill: color-mix(in oklab, var(--color-accent) 35%, transparent); }
.legend { display: flex; flex-wrap: wrap; gap: var(--space-2xs) var(--space-lg); list-style: none; margin: 0 0 var(--space-sm); padding: 0; font-size: var(--text-sm); }
.legend li { display: inline-flex; align-items: center; gap: var(--space-xs); }
.sw { display: inline-block; width: 20px; height: 3px; background: var(--chart-ma60); }
.sw-ma5 { background: var(--chart-ma5); } .sw-ma10 { background: var(--chart-ma10); } .sw-ma20 { background: var(--chart-ma20); }
.sw-k { width: 10px; height: 14px; background: currentColor; }

.split-rows { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 var(--space-2xl); margin-top: var(--space-2xl); }
.rows { margin: 0; }
.row { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: var(--space-md); padding-block: var(--space-md); border-top: var(--rule-bar) solid var(--color-accent-2); }
.row dt { font: 800 var(--text-xl)/1.1 var(--font-display); text-transform: uppercase; }
.row dd { margin: 0; min-width: 0; }
.row-v { display: block; font: 800 var(--text-xl)/1.1 var(--font-display); font-variant-numeric: tabular-nums; }
.row dd small { display: block; font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-2xs); }
#dim2 .rows { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 var(--space-2xl); margin-top: var(--space-2xl); }
#dim2 .row { grid-template-columns: minmax(0, 1fr); }

.flows { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2xl) var(--gap-columns); }
.pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2xl) var(--gap-columns); margin-top: var(--space-2xl); }
.flow-l { font-size: var(--text-sm); font-weight: 500; color: var(--color-muted); }
.flow-v { font: 800 var(--text-2xl)/1.1 var(--font-display); margin-top: var(--space-2xs); }

.figs4, .figs3 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-block: var(--space-xl); }
.figs3 { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-block: 0; }
.scen-figs { margin-block: var(--space-xl); }
.scen-figs .fg-v { font-size: var(--text-display-s); }
.scen-figs > * { border-top-color: var(--color-accent-2); }
.scroll.wide td:first-child strong { font: 500 var(--text-title)/1.3 var(--font-body); }
th.num { text-align: right; }
.nw { white-space: nowrap; }
.figs4 > *, .figs3 > * { padding-inline: var(--space-lg); border-left: var(--rule-bar) solid var(--color-accent-2); min-width: 0; }
.figs4 > :first-child, .figs3 > :first-child { padding-left: 0; border-left: 0; }
.fg-v { font: 800 var(--text-3xl)/1.05 var(--font-display); white-space: nowrap; }
.fg-l { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-xs); }
.baseline { margin-top: var(--space-2xl); }

.well { border: var(--rule-bar) solid var(--color-ink); border-radius: var(--radius-card); background: var(--color-paper-2); box-shadow: var(--shadow-card); padding: var(--space-xl); min-width: 0; }
.well-h { font-size: var(--text-sm); font-weight: 500; color: var(--color-muted); margin-bottom: var(--space-xs); }
.well-v { font: 800 var(--text-2xl)/1.1 var(--font-display); margin-bottom: var(--space-sm); }
.well p + p { margin-top: var(--space-sm); }
.basis { font-size: var(--text-sm); color: var(--color-muted); overflow-wrap: anywhere; }
.basis a, .src a, td a { overflow-wrap: anywhere; }
.warn { border-left: var(--rule-bar) solid var(--color-accent-2); padding: var(--space-sm) var(--space-md); background: var(--color-paper-2); font-weight: 500; }
.kv { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-xs) var(--space-md); margin: var(--space-sm) 0 var(--space-lg); }
.kv dt { font-size: var(--text-sm); color: var(--color-muted); }
.kv dd { margin: 0; font: 800 var(--text-xl)/1.1 var(--font-display); text-align: right; }
.rr { font: 800 clamp(2.5rem, 3vw + 1rem, 3.75rem)/1 var(--font-display); }
.sub { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-2xs); }

.slate-band { background: var(--color-accent-2); color: var(--color-paper); padding-block: var(--space-2xl); margin-top: var(--space-2xl); --tw-up: var(--tw-up-sb); --tw-down: var(--tw-down-sb); }
.slate-band .figs3 > * { border-left-color: var(--color-paper); }
.sb-v { font: 800 clamp(2.75rem, 4vw + 1rem, 4.5rem)/1 var(--font-display); white-space: nowrap; }
.sb-l { font-size: var(--text-sm); margin-top: var(--space-xs); }

.moat-l { font-size: var(--text-sm); color: var(--color-muted); }
.moat { list-style: none; margin: var(--space-sm) 0 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2xl) var(--gap-columns); }
.moat li { border-top: var(--rule-bar) solid var(--color-accent-2); padding-top: var(--space-md); min-width: 0; }
.moat h3 { font: 800 var(--text-2xl)/1.1 var(--font-display); margin-bottom: var(--space-sm); }
.moat p + p { margin-top: var(--space-xs); }
.facts { margin: 0; padding: 0; list-style: none; counter-reset: f; }
.facts li { position: relative; counter-increment: f; padding: var(--space-md) 0 var(--space-md) var(--space-3xl); border-top: var(--rule-bar) solid var(--color-accent-2); }
.facts li::before { content: counter(f); position: absolute; left: 0; top: var(--space-sm); font: 800 var(--text-2xl)/1 var(--font-display); font-variant-numeric: tabular-nums; }
.facts li p { max-width: 72ch; }
.src { font-size: var(--text-sm); color: var(--color-muted); margin-top: var(--space-2xs); }

.scroll { overflow-x: auto; border-block: var(--rule-bar) solid var(--color-ink); }
.scroll :is(th, td):first-child { position: sticky; inset-inline-start: 0; z-index: var(--z-base); background: var(--color-paper); }
table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
.scroll.wide table { min-width: 960px; }
th { text-align: left; font-weight: 500; color: var(--color-muted); padding: var(--space-sm); border-bottom: var(--rule-bar) solid var(--color-accent-2); white-space: nowrap; }
td { padding: var(--space-sm); border-bottom: var(--rule-hair) solid var(--color-paper-3); vertical-align: top; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: var(--color-paper-2); }
th:first-child, td:first-child { position: sticky; left: 0; background: var(--color-paper); z-index: var(--z-raised); }
tbody tr:hover td:first-child { background: var(--color-paper-2); }
.scroll.wide td { min-width: 8em; }
.scroll.wide td:last-child { min-width: 18em; }
td.num { text-align: right; font-weight: 500; white-space: nowrap; font-variant-numeric: tabular-nums; }
tr.full td { position: static; background: var(--color-paper-2); border-bottom: var(--rule-bar) solid var(--color-accent-2); }
tr.full td p { max-width: 72ch; }
tr.full td p + p { margin-top: var(--space-xs); }

.mast-foot { background: var(--color-ink); color: var(--color-paper); padding-block: var(--space-3xl) var(--space-2xl); margin-top: var(--space-3xl); }
.mast-foot .big { font: 800 clamp(3.5rem, 9vw, 9rem)/0.95 var(--font-display); text-transform: uppercase; margin-bottom: var(--space-xl); }
.mast-foot .meta { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: var(--rule-bar) solid var(--color-paper); }
.mast-foot .meta > div { padding: var(--space-md) var(--space-lg) 0; border-left: var(--rule-bar) solid var(--color-paper); min-width: 0; }
.mast-foot .meta > :first-child { padding-left: 0; border-left: 0; }
.mast-foot .ml { font-size: var(--text-sm); color: var(--color-paper-3); }
.mast-foot a { color: var(--color-paper); text-decoration-color: var(--color-accent); }
.mast-foot a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; }
.mast-foot .disc { font-weight: 500; font-size: var(--text-lead); margin-top: var(--space-xl); }
.mast-foot .fine { font-size: var(--text-sm); color: var(--color-paper-3); margin-top: var(--space-sm); }

.tip { position: fixed; left: 0; top: 0; z-index: var(--z-tooltip); pointer-events: none; max-width: min(92vw, 440px); background: var(--color-ink); color: var(--color-paper); font-size: var(--text-sm); padding: var(--space-xs) var(--space-sm); border-radius: var(--radius-card); font-variant-numeric: tabular-nums; }

@media (max-width: 60rem) {
  .hero-head, .sec-head { grid-template-columns: minmax(0, 1fr); }
  .kfs { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .kf:nth-child(4) { padding-left: 0; border-left: 0; }
  .kf:nth-child(n+4) { border-top: var(--rule-bar) solid var(--color-accent-ink); margin-top: var(--space-md); }
  .flows, .moat { grid-template-columns: minmax(0, 1fr); }
  .split-rows { grid-template-columns: minmax(0, 1fr); }
  .figs4, .mast-foot .meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .figs4 > :nth-child(3), .mast-foot .meta > :nth-child(3) { padding-left: 0; border-left: 0; }
  .figs4 > :nth-child(n+3), .mast-foot .meta > :nth-child(n+3) { margin-top: var(--space-lg); }
  .figs3 { grid-template-columns: minmax(0, 1fr); }
  .figs3 > * { padding: var(--space-md) 0; border-left: 0; border-top: var(--rule-bar) solid var(--color-paper); }
  .figs3 > :first-child { border-top: 0; }
  #dim2 .rows { grid-template-columns: minmax(0, 1fr); }
  .halftone { width: 96px; height: 96px; }
}
@media (max-width: 40rem) {
  .pair { grid-template-columns: minmax(0, 1fr); }
  .kfs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kf:nth-child(4) { padding-left: var(--space-md); border-left: var(--rule-bar) solid var(--color-accent-ink); }
  .kf:nth-child(odd) { padding-left: 0; border-left: 0; }
  .kf:nth-child(n+3) { border-top: var(--rule-bar) solid var(--color-accent-ink); margin-top: var(--space-md); }
  .call { grid-template-columns: minmax(0, 1fr); }
  .halftone { display: none; }
  .row { grid-template-columns: minmax(0, 1fr); gap: var(--space-2xs); }
  .slab nav { margin-inline-start: 0; width: 100%; }
  .well { padding: var(--space-lg); }
  .plot--wide { overflow-x: auto; }
  .plot--wide .chart { min-width: 640px; }
  .figs4 { grid-template-columns: minmax(0, 1fr); }
  .figs4 > * { padding: var(--space-md) 0; border-left: 0; border-top: var(--rule-bar) solid var(--color-accent-2); margin-top: 0; }
  .figs4 > :first-child { border-top: 0; }
  .mast-foot .meta { grid-template-columns: minmax(0, 1fr); }
  .mast-foot .meta > * { padding: var(--space-md) 0; border-left: 0; margin-top: 0; }
  .scroll { overflow-x: visible; }
  .scroll.wide table { min-width: 0; }
  table.stack thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  table.stack, table.stack tbody, table.stack tr, table.stack td { display: block; width: 100%; }
  table.stack tr { border-bottom: var(--rule-bar) solid var(--color-accent-2); }
  table.stack td, .scroll.wide td, .scroll.wide td:last-child { position: static; min-width: 0; border-bottom: var(--rule-hair) solid var(--color-paper-3); text-align: left; white-space: normal; padding: var(--space-xs) 0; }
  table.stack td::before { content: attr(data-label); display: block; font-size: var(--text-xs); color: var(--color-muted); }
  table.stack td:empty { display: none; }
  table.stack td { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: var(--space-sm); align-items: baseline; }
  table.stack tr.full td { display: block; }
}
"""

# The scaffold folder is gitignored, so its tokens.css and base.css are inlined here,
# with the Carnival pressroom drop applied to the colour tokens.
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
  --color-paper: oklch(89% 0.025 65); --color-paper-2: oklch(85% 0.030 65); --color-paper-3: oklch(79% 0.035 65);
  --color-ink: oklch(16% 0.02 60); --color-ink-2: oklch(26% 0.02 60); --color-muted: oklch(38% 0.025 60);
  --color-rule: oklch(34% 0.10 240); --color-accent: oklch(78% 0.18 75); --color-accent-2: oklch(34% 0.10 240);
  --color-accent-ink: oklch(16% 0.02 60); --color-focus: oklch(34% 0.10 240);
  --tw-up-sb: oklch(84% 0.10 25); --tw-down-sb: oklch(86% 0.10 150);
  --font-display: "Big Shoulders Display", Impact, sans-serif; --font-body: "Golos Text", system-ui, sans-serif;
  --font-outlier: var(--font-body);
  --radius-card: 2px; --radius-pill: 2px; --rule-hair: 1px; --rule-bar: 2px; --shadow-card: 4px 4px 0 var(--color-ink);
  --tracking-display: 0.015em; --display-weight: 800;
}"""
BASE = """*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); scroll-padding-top: var(--space-3xl); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }
::selection { background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }
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
@media (max-width: 60rem) { :root { --gutter: 24px; --section-gap-s: 80px; --section-gap: 96px; --section-gap-l: 120px; } }
@media (max-width: 40rem) { :root { --gutter: 16px; --section-gap-s: 56px; --section-gap: 72px; --section-gap-l: 96px; --gap-columns: 16px; } }
@media (prefers-reduced-motion: reduce) { *:not(.keep-motion), *:not(.keep-motion)::before, *:not(.keep-motion)::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }"""
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
<meta name="description" content="{esc(name_zh)}（{CODE}）{asof} 投資決策報告：當前動作{esc(x['action_zh'])}，評等{x['rating_zh']}，Base 目標價 {fp(base['target'])}。">
<script>try {{ var s = localStorage.getItem('mode'); if (s === 'dark' || s === 'light') document.documentElement.dataset.mode = s; }} catch (e) {{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800&family=Golos+Text:wght@400;500&family=Noto+Sans+TC:wght@900&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
<header class="slab">
  <div class="container">
    <a class="mark" href="../../index.html" aria-label="回到報告目錄">{CODE} {esc(name_zh)}</a>
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
<footer class="mast-foot">
  <div class="container">
    <p class="big">{esc(name_zh)} {CODE}</p>
    <div class="meta">
      <div><p class="ml">資料來源</p><p>FinMind：股價、三大法人、外資持股、融資融券、月營收、財報、本益比</p></div>
      <div><p class="ml">資料日期</p><p class="num">{asof}</p><p class="ml">生成日 {date.today().isoformat()}</p><p class="ml">資料缺口：{gaps_txt}</p></div>
      <div><p class="ml">工具版本</p><p class="num">{esc(d['tool_version'])}</p></div>
      <div><p class="ml">生成模型</p><p><span data-meta="model">{esc(gen['model'])}</span>，推理強度 <span data-meta="effort">{esc(gen['effort'])}</span></p></div>
    </div>
    <p class="disc">本報告僅供研究參考，不構成任何投資建議。</p>
    <p class="fine">標示「分析師判斷」者為判斷，其餘數字皆由腳本自 FinMind 計算；外部事實附出處與日期。<a href="../../index.html">回到報告目錄</a></p>
  </div>
</footer>
<script>{JS}</script>
</body>
</html>
"""

DATE_RE = re.compile(r"(?<![\d-])(\d{4}-\d{2}-\d{2})(?![\d-])")
SKIP_TAGS = ("svg", "script", "style", "title")
HOOK_ATTRS = ("data-kpi=", "data-meta=", "data-value=", "data-baseline=", "data-rr=", "data-implied=")


def wrap_dates(html_page):
    """Keep ISO dates on one line in reader text; leave SVG, scripts, styles and hook values untouched."""
    out, skip, last_tag = [], [], ""
    for part in re.split(r"(<[^>]+>)", html_page):
        if part.startswith("<"):
            m = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            name = m.group(1).lower() if m else ""
            if name in SKIP_TAGS:
                if part.startswith("</"):
                    if skip and skip[-1] == name:
                        skip.pop()
                elif not part.endswith("/>"):
                    skip.append(name)
            last_tag = part
            out.append(part)
        elif skip or any(h in last_tag for h in HOOK_ATTRS):
            out.append(part)
        else:
            out.append(DATE_RE.sub(r'<span class="nw">\1</span>', part))
    return "".join(out)


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(wrap_dates(page), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
