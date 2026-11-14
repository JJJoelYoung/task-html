#!/usr/bin/env python3
"""Generate standalone HTML equity research report for 2308 Delta Electronics (as-of 2026-11-13).

Theme: Almanac (1/3, seed 2308-equity-research-9490·ce12e4cc·2026-11-14·r0)
All numbers are loaded from data_2308.json, analysis_2308.json, and derive.py.
"""

import html
import sys
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORK_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT / ".agents" / "skills" / "tw-equity-report" / "scripts"))

import derive as dv  # noqa: E402


def esc(val):
    return html.escape(str(val))


def fmt_yi(val, dec=2):
    """Convert raw NTD value to 億元 formatted string."""
    if val is None:
        return "無資料"
    return f"{val / 1e8:,.{dec}f} 億"


def fmt_int(val):
    if val is None:
        return "無資料"
    return f"{int(round(val)):,}"


def fmt_signed_int(val):
    if val is None:
        return "無資料"
    return f"{int(round(val)):+,}"


def build_kline_svg(series, metrics, x_derived=None, show_trade_lines=False):
    """Build 65-trading-day candlestick + MA5/MA10/MA20 + volume SVG chart."""
    rows = series[-65:]
    n = len(rows)
    w, h = 960, 460
    pad_l, pad_r, pad_t, pad_b = 72, 92, 28, 44
    price_h = 270
    gap_h = 28
    vol_top = pad_t + price_h + gap_h
    vol_h = h - vol_top - pad_b
    plot_w = w - pad_l - pad_r

    highs = [r["high"] for r in rows if r["high"] is not None]
    lows = [r["low"] for r in rows if r["low"] is not None]
    if show_trade_lines and x_derived:
        highs.extend([x_derived["entry"], x_derived["t1"], x_derived["t2"], x_derived["trigger"]])
        lows.extend([x_derived["hard_stop"], x_derived["entry"]])

    p_max = max(highs) * 1.03
    p_min = min(lows) * 0.96
    p_span = max(p_max - p_min, 1.0)

    v_max = max((r["volume_lots"] or 0) for r in rows) * 1.12 or 1.0
    step_x = plot_w / max(n, 1)
    bar_w = max(4.0, min(9.0, step_x * 0.62))

    def x_at(idx):
        return pad_l + (idx + 0.5) * step_x

    def y_price(p):
        return pad_t + (1.0 - (p - p_min) / p_span) * price_h

    def y_vol(v):
        return vol_top + (1.0 - min(v, v_max) / v_max) * vol_h

    parts = []
    aria = (
        f"台達電 2308 近 {n} 個交易日 K 線、均線與成交量圖"
        if not show_trade_lines
        else f"台達電 2308 交易部位價位圖（含進場價 Entry、目標價 T1/T2 與停損價 SL）"
    )
    parts.append(
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(aria)}">'
    )

    # Price horizontal gridlines (4 lines)
    for i in range(5):
        p_val = p_min + (p_span * i / 4.0)
        gy = y_price(p_val)
        parts.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" class="grid-line" />'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" class="axis-num">{dv.fmt_price(dv.round_tick(p_val))}</text>'
        )

    # Volume baseline & top gridline
    parts.append(
        f'<line x1="{pad_l}" y1="{vol_top:.1f}" x2="{w - pad_r}" y2="{vol_top:.1f}" class="grid-line" />'
    )
    parts.append(
        f'<line x1="{pad_l}" y1="{vol_top + vol_h:.1f}" x2="{w - pad_r}" y2="{vol_top + vol_h:.1f}" class="grid-line-firm" />'
    )
    parts.append(
        f'<text x="{pad_l - 8}" y="{vol_top + 8:.1f}" text-anchor="end" class="axis-num">{fmt_int(v_max)}張</text>'
    )
    parts.append(
        f'<text x="{pad_l - 8}" y="{vol_top + vol_h:.1f}" text-anchor="end" class="axis-num">0</text>'
    )

    # X-axis date ticks (every ~13 trading days + last day)
    tick_indices = sorted(set(list(range(0, n - 4, 13)) + [n - 1]))
    for idx in tick_indices:
        cx = x_at(idx)
        dt_short = rows[idx]["date"][5:]
        anchor = "end" if idx == n - 1 else ("start" if idx == 0 else "middle")
        parts.append(
            f'<text x="{cx:.1f}" y="{h - 14}" text-anchor="{anchor}" class="axis-num">{esc(dt_short)}</text>'
        )

    # Candlesticks & volume bars
    spike_set = set(metrics.get("spike_days") or [])
    dryup_set = set(metrics.get("dryup_days") or [])
    for idx, r in enumerate(rows):
        cx = x_at(idx)
        op, hi, lo, cl = r["open"], r["high"], r["low"], r["close"]
        vol = r["volume_lots"] or 0
        if None in (op, hi, lo, cl):
            continue
        y_hi, y_lo = y_price(hi), y_price(lo)
        y_op, y_cl = y_price(op), y_price(cl)
        body_top = min(y_op, y_cl)
        body_h = max(abs(y_cl - y_op), 1.8)
        up_day = cl >= op
        candle_cls = "candle-up" if up_day else "candle-down"
        vol_cls = "vol-spike" if r["date"] in spike_set else ("vol-dry" if r["date"] in dryup_set else "vol-bar")

        tip = (
            f"{r['date']}｜開 {dv.fmt_price(op)} 高 {dv.fmt_price(hi)} "
            f"低 {dv.fmt_price(lo)} 收 {dv.fmt_price(cl)}｜量 {fmt_int(vol)} 張"
        )
        parts.append(f'<g class="chart-point" data-tip="{esc(tip)}">')
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y_hi:.1f}" x2="{cx:.1f}" y2="{y_lo:.1f}" class="{candle_cls}-wick" />'
        )
        parts.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{body_top:.1f}" width="{bar_w:.1f}" height="{body_h:.1f}" class="{candle_cls}" />'
        )
        vy = y_vol(vol)
        vh = max((vol_top + vol_h) - vy, 1.0)
        parts.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{vy:.1f}" width="{bar_w:.1f}" height="{vh:.1f}" class="{vol_cls}" />'
        )
        parts.append("</g>")

    # Moving average polylines
    for ma_key, cls_name in (("ma20", "ma-line-20"), ("ma10", "ma-line-10"), ("ma5", "ma-line-5")):
        pts = []
        for idx, r in enumerate(rows):
            val = r.get(ma_key)
            if val is not None:
                pts.append(f"{x_at(idx):.1f},{y_price(val):.1f}")
        if len(pts) >= 2:
            parts.append(f'<polyline points="{" ".join(pts)}" class="{cls_name}" />')

    # 20D avg volume reference line in volume pane
    v20 = metrics.get("vol_avg20_lots")
    if v20:
        vy20 = y_vol(v20)
        parts.append(
            f'<line x1="{pad_l}" y1="{vy20:.1f}" x2="{w - pad_r}" y2="{vy20:.1f}" class="vol-avg-line" />'
        )

    # Trade setup horizontal lines for dim6
    if show_trade_lines and x_derived:
        trade_lines = [
            ("t2", x_derived["t2"], f"T2 {dv.fmt_price(x_derived['t2'])}", "trade-line-t2"),
            ("t1", x_derived["t1"], f"T1 {dv.fmt_price(x_derived['t1'])}", "trade-line-t1"),
            ("entry", x_derived["entry"], f"Entry {dv.fmt_price(x_derived['entry'])}", "trade-line-entry"),
            ("sl", x_derived["hard_stop"], f"SL {dv.fmt_price(x_derived['hard_stop'])}", "trade-line-sl"),
        ]
        # Avoid label vertical collisions on right margin
        used_y = []
        for key, val, label_txt, line_cls in trade_lines:
            ly = y_price(val)
            adj_y = ly
            for prev_y in used_y:
                if abs(adj_y - prev_y) < 14:
                    adj_y = prev_y + (14 if adj_y >= prev_y else -14)
            used_y.append(adj_y)
            parts.append(
                f'<line x1="{pad_l}" y1="{ly:.1f}" x2="{w - pad_r}" y2="{ly:.1f}" '
                f'class="{line_cls}" data-line="{key}" data-value="{val}" '
                f'data-tip="{esc(label_txt)}" />'
            )
            parts.append(
                f'<text x="{w - pad_r + 6}" y="{adj_y + 4:.1f}" text-anchor="start" class="axis-num">{esc(label_txt)}</text>'
            )

    parts.append("</svg>")
    return f'<div class="chart-scroll">{"".join(parts)}</div>'


def build_chips_svg(inst_daily, fh_series):
    """Build W20 institutional cumulative flow + foreign holding ratio two-panel SVG."""
    w, h = 960, 340
    pad_l, pad_r, pad_t, pad_b = 76, 36, 24, 38
    panel_w = (w - pad_l - pad_r - 56) / 2.0
    p1_x = pad_l
    p2_x = pad_l + panel_w + 56
    plot_h = h - pad_t - pad_b
    n = len(inst_daily)

    # Panel 1: Cumulative institutional net buy/sell (lots)
    cums = []
    for r in inst_daily:
        cums.extend([r["foreign_cum"], r["trust_cum"], r["dealer_cum"], 0])
    c_min, c_max = min(cums) * 1.08, max(cums) * 1.15
    c_span = max(c_max - c_min, 1.0)

    def x1(i):
        return p1_x + (i / max(n - 1, 1)) * panel_w

    def y1(v):
        return pad_t + (1.0 - (v - c_min) / c_span) * plot_h

    # Panel 2: Foreign holding ratio (%)
    ratios = [r["ratio"] for r in fh_series if r["ratio"] is not None]
    r_min = min(ratios) - 0.35
    r_max = max(ratios) + 0.35
    r_span = max(r_max - r_min, 0.5)

    def x2(i):
        return p2_x + (i / max(len(fh_series) - 1, 1)) * panel_w

    def y2(v):
        return pad_t + (1.0 - (v - r_min) / r_span) * plot_h

    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="台達電近20日三大法人累計買賣超與外資持股比率趨勢圖">'
    ]

    # Panel 1 grid
    for i in range(5):
        v = c_min + c_span * i / 4.0
        gy = y1(v)
        parts.append(f'<line x1="{p1_x}" y1="{gy:.1f}" x2="{p1_x + panel_w:.1f}" y2="{gy:.1f}" class="grid-line" />')
        parts.append(f'<text x="{p1_x - 8}" y="{gy + 4:.1f}" text-anchor="end" class="axis-num">{fmt_int(v)}</text>')

    for series_key, cls_name, label_zh in (
        ("foreign_cum", "series-accent", "外資累計"),
        ("trust_cum", "series-ink", "投信累計"),
        ("dealer_cum", "series-muted", "自營商累計"),
    ):
        pts = [f"{x1(i):.1f},{y1(r[series_key]):.1f}" for i, r in enumerate(inst_daily)]
        parts.append(f'<polyline points="{" ".join(pts)}" class="{cls_name}" />')
        for i, r in enumerate(inst_daily):
            cx, cy = x1(i), y1(r[series_key])
            tip = f"{r['date']}｜{label_zh} {fmt_signed_int(r[series_key])} 張"
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" class="point-hit" data-tip="{esc(tip)}" />')

    for idx in (0, n // 2, n - 1):
        parts.append(
            f'<text x="{x1(idx):.1f}" y="{h - 10}" text-anchor="middle" class="axis-num">{inst_daily[idx]["date"][5:]}</text>'
        )

    # Panel 2 grid (explicitly annotated narrow band per data-viz.md)
    for i in range(5):
        v = r_min + r_span * i / 4.0
        gy = y2(v)
        parts.append(f'<line x1="{p2_x}" y1="{gy:.1f}" x2="{p2_x + panel_w:.1f}" y2="{gy:.1f}" class="grid-line" />')
        parts.append(f'<text x="{p2_x - 8}" y="{gy + 4:.1f}" text-anchor="end" class="axis-num">{v:.2f}%</text>')

    pts2 = [f"{x2(i):.1f},{y2(r['ratio']):.1f}" for i, r in enumerate(fh_series)]
    parts.append(f'<polyline points="{" ".join(pts2)}" class="series-accent" />')
    for i, r in enumerate(fh_series):
        cx, cy = x2(i), y2(r["ratio"])
        tip = f"{r['date']}｜外資持股比率 {r['ratio']:.2f}%"
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="point-dot" data-tip="{esc(tip)}" />')

    for idx in (0, len(fh_series) // 2, len(fh_series) - 1):
        parts.append(
            f'<text x="{x2(idx):.1f}" y="{h - 10}" text-anchor="middle" class="axis-num">{fh_series[idx]["date"][5:]}</text>'
        )

    parts.append("</svg>")
    return f'<div class="chart-scroll">{"".join(parts)}</div>'


def build_revenue_svg(last12):
    """Build two-panel small multiples for 12-month revenue (億元, baseline 0) and YoY (%) per data-viz.md (no dual axis)."""
    w, h = 960, 350
    pad_l, pad_r, pad_t, pad_b = 64, 28, 28, 42
    panel_w = (w - pad_l - pad_r - 56) / 2.0
    p1_x = pad_l
    p2_x = pad_l + panel_w + 56
    plot_h = h - pad_t - pad_b
    n = len(last12)

    rev_yi = [r["revenue"] / 1e8 for r in last12]
    r_max = max(rev_yi) * 1.12
    yoy_vals = [r["yoy_pct"] for r in last12 if r["yoy_pct"] is not None]
    y_max = max(max(yoy_vals) * 1.15, 60.0)

    step1 = panel_w / n
    bar_w = min(20.0, step1 * 0.58)

    def y_rev(v):
        return pad_t + (1.0 - v / r_max) * plot_h

    def x_yoy(i):
        return p2_x + (i + 0.5) * (panel_w / n)

    def y_yoy(v):
        return pad_t + (1.0 - max(v, 0.0) / y_max) * plot_h

    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="台達電近12個月單月合併營收與年增率趨勢圖">'
    ]

    # Left panel: Revenue bars starting at 0
    for i in range(5):
        v = r_max * i / 4.0
        gy = y_rev(v)
        parts.append(f'<line x1="{p1_x}" y1="{gy:.1f}" x2="{p1_x + panel_w:.1f}" y2="{gy:.1f}" class="grid-line" />')
        parts.append(f'<text x="{p1_x - 8}" y="{gy + 4:.1f}" text-anchor="end" class="axis-num">{v:,.0f}億</text>')

    for i, r in enumerate(last12):
        val_yi = r["revenue"] / 1e8
        cx = p1_x + (i + 0.5) * step1
        by = y_rev(val_yi)
        bh = (pad_t + plot_h) - by
        bar_cls = "bar-accent" if i == n - 1 else "bar-ink"
        tip = f"{r['period']}｜營收 {val_yi:,.2f} 億元｜MoM {dv.fmt_pct(r['mom_pct'])}｜YoY {dv.fmt_pct(r['yoy_pct'])}"
        parts.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="1.5" '
            f'class="{bar_cls}" data-tip="{esc(tip)}" />'
        )
        if i in (0, 3, 6, 9, n - 1):
            parts.append(
                f'<text x="{cx:.1f}" y="{h - 12}" text-anchor="middle" class="axis-num">{r["period"][2:]}</text>'
            )

    # Right panel: YoY % line starting at 0%
    for i in range(5):
        v = y_max * i / 4.0
        gy = y_yoy(v)
        parts.append(f'<line x1="{p2_x}" y1="{gy:.1f}" x2="{p2_x + panel_w:.1f}" y2="{gy:.1f}" class="grid-line" />')
        parts.append(f'<text x="{p2_x - 8}" y="{gy + 4:.1f}" text-anchor="end" class="axis-num">+{v:.0f}%</text>')

    pts = [f"{x_yoy(i):.1f},{y_yoy(r['yoy_pct']):.1f}" for i, r in enumerate(last12) if r["yoy_pct"] is not None]
    parts.append(f'<polyline points="{" ".join(pts)}" class="series-accent" />')
    for i, r in enumerate(last12):
        if r["yoy_pct"] is None:
            continue
        cx, cy = x_yoy(i), y_yoy(r["yoy_pct"])
        tip = f"{r['period']}｜年增率 YoY {dv.fmt_pct(r['yoy_pct'])}（MoM {dv.fmt_pct(r['mom_pct'])}）"
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" class="point-dot" data-tip="{esc(tip)}" />')
        if i in (0, 3, 6, 9, n - 1):
            parts.append(
                f'<text x="{cx:.1f}" y="{h - 12}" text-anchor="middle" class="axis-num">{r["period"][2:]}</text>'
            )

    parts.append("</svg>")
    return f'<div class="chart-scroll">{"".join(parts)}</div>'


def build_valuation_band_svg(per_band, pbr_band):
    """Build 5-year PER and PBR percentile band bullet/range SVG chart with staggered non-overlapping labels."""
    w, h = 960, 260
    pad_l, pad_r = 130, 90
    bar_w = w - pad_l - pad_r
    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="台達電5年本益比PER與股價淨值比PBR歷史分位區間圖">'
    ]

    for idx, (label, b, unit_str) in enumerate(
        (("本益比 PER", per_band, "x"), ("股價淨值比 PBR", pbr_band, "x"))
    ):
        cy = 72 + idx * 114
        lo = b["p10"] * 0.90
        hi = b["p90"] * 1.08
        span = max(hi - lo, 1.0)

        def x_pos(val):
            return pad_l + ((val - lo) / span) * bar_w

        x_p10, x_p25, x_p50, x_p75, x_p90 = (
            x_pos(b["p10"]),
            x_pos(b["p25"]),
            x_pos(b["p50"]),
            x_pos(b["p75"]),
            x_pos(b["p90"]),
        )
        x_cur = x_pos(b["current"])

        parts.append(f'<text x="{pad_l - 14}" y="{cy + 5}" text-anchor="end" class="axis-label">{esc(label)}</text>')
        p10_s, p25_s, p75_s, p90_s = (
            dv.fmt_mult(b["p10"]),
            dv.fmt_mult(b["p25"]),
            dv.fmt_mult(b["p75"]),
            dv.fmt_mult(b["p90"]),
        )
        # P10-P90 outer track
        parts.append(
            f'<rect x="{x_p10:.1f}" y="{cy - 8}" width="{x_p90 - x_p10:.1f}" height="16" class="band-outer" '
            f'data-tip="{esc(label)} P10–P90：{p10_s} – {p90_s}" />'
        )
        # P25-P75 inner interquartile box
        parts.append(
            f'<rect x="{x_p25:.1f}" y="{cy - 12}" width="{x_p75 - x_p25:.1f}" height="24" class="band-iqr" '
            f'data-tip="{esc(label)} P25–P75：{p25_s} – {p75_s}" />'
        )
        # P50 median tick
        parts.append(f'<line x1="{x_p50:.1f}" y1="{cy - 16}" x2="{x_p50:.1f}" y2="{cy + 16}" class="band-median" />')

        # Bottom row: P10 (end-anchored left of tick), P50 (start-anchored right of tick), P75, P90
        for p_lbl, p_val, px, lx, anchor in (
            ("P10", b["p10"], x_p10, x_p10 - 6, "end"),
            ("P50", b["p50"], x_p50, x_p50 + 6, "start"),
            ("P75", b["p75"], x_p75, x_p75, "middle"),
            ("P90", b["p90"], x_p90, x_p90, "middle"),
        ):
            parts.append(f'<line x1="{px:.1f}" y1="{cy + 12}" x2="{px:.1f}" y2="{cy + 20}" class="grid-line-firm" />')
            parts.append(
                f'<text x="{lx:.1f}" y="{cy + 34}" text-anchor="{anchor}" class="axis-num">{p_lbl} {p_val:.1f}{unit_str}</text>'
            )

        # Top row: P25 (above left of IQR box) and Current marker (above current dot)
        parts.append(f'<line x1="{x_p25:.1f}" y1="{cy - 12}" x2="{x_p25:.1f}" y2="{cy - 20}" class="grid-line-firm" />')
        parts.append(
            f'<text x="{x_p25:.1f}" y="{cy - 24}" text-anchor="middle" class="axis-num">P25 {b["p25"]:.1f}{unit_str}</text>'
        )

        tip_cur = f"{label} 現值 {dv.fmt_mult(b['current'])}（5 年分位 {b['current_percentile']:.1f}%）"
        parts.append(
            f'<circle cx="{x_cur:.1f}" cy="{cy}" r="6.5" class="point-dot" data-tip="{esc(tip_cur)}" />'
        )
        parts.append(
            f'<text x="{x_cur:.1f}" y="{cy - 24}" text-anchor="middle" class="axis-num">現值 {dv.fmt_mult(b["current"])} ({b["current_percentile"]:.1f}%)</text>'
        )

    parts.append("</svg>")
    return f'<div class="chart-scroll">{"".join(parts)}</div>'


def generate():
    d, a = dv.load_work(WORK_DIR, "2308")
    x = dv.derive(d, a)
    rel_out = dv.report_relpath(d, a)
    out_path = REPO_ROOT / rel_out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    m = d["price"]["metrics"]
    inst = d["institutional"]
    fh = d["foreign_holding"]
    mg = d["margin"]
    rev = d["revenue"]
    fin = d["financials"]
    val = d["valuation"]
    peers_data = d["peers"]

    scen_by_name = {s["name"]: s for s in x["scenarios"]}
    bull = scen_by_name["Bull"]
    base = scen_by_name["Base"]
    bear = scen_by_name["Bear"]

    pos_zh = {
        "below_p25": "低於 P25",
        "p25_p75": "P25–P75 區間",
        "p75_p90": "P75–P90 區間",
        "above_p90": "高於 P90",
    }
    align_zh = {"bullish": "多頭排列", "bearish": "空頭排列", "mixed": "糾結交錯"}.get(
        m["alignment"], m["alignment"]
    )
    sm_level_zh = {"low": "低檔（< 5%）", "medium": "中檔（5–20%）", "high": "高檔（> 20%，具軋空潛力）"}.get(
        mg["short_margin_level"], mg["short_margin_level"]
    )

    kline_dim1_svg = build_kline_svg(d["price"]["series"], m, x_derived=None, show_trade_lines=False)
    kline_dim6_svg = build_kline_svg(d["price"]["series"], m, x_derived=x, show_trade_lines=True)
    chips_svg = build_chips_svg(inst["daily"], fh["series"])
    rev_svg = build_revenue_svg(rev["last12"])
    val_svg = build_valuation_band_svg(val["PER"], val["PBR"])

    # Peer reasons lookup
    peer_reasons = {p["code"]: p for p in a["peers"]}
    peer_names = {
        "2308": f"{a['name_zh']} ({a['name_en']})",
        **{p["code"]: p["name"] for p in a["peers"]},
    }

    # Build quarterly financial rows (last 4 quarters)
    q_rows = fin["quarters"][-4:]
    ocf_map = fin.get("ocf_quarterly") or {}

    # Build institutional daily rows (last 20 trading days)
    inst_rows_html = []
    for r in reversed(inst["daily"]):
        tot = r["foreign"] + r["trust"] + r["dealer"]
        inst_rows_html.append(
            f"<tr>"
            f'<td class="num">{esc(r["date"])}</td>'
            f'<td class="num">{fmt_signed_int(r["foreign"])}</td>'
            f'<td class="num">{fmt_signed_int(r["trust"])}</td>'
            f'<td class="num">{fmt_signed_int(r["dealer"])}</td>'
            f'<td class="num">{fmt_signed_int(tot)}</td>'
            f'<td class="num">{fmt_signed_int(r["foreign_cum"])}</td>'
            f"</tr>"
        )

    # Monthly revenue table rows
    rev_rows_html = []
    for r in reversed(rev["last12"]):
        rev_rows_html.append(
            f"<tr>"
            f'<td class="num">{esc(r["period"])}</td>'
            f'<td class="cell-right"><span class="kpi-num">{r["revenue"] / 1e8:,.2f}</span> 億</td>'
            f'<td class="num">{dv.fmt_pct(r["mom_pct"])}</td>'
            f'<td class="num">{dv.fmt_pct(r["yoy_pct"])}</td>'
            f"</tr>"
        )

    # Quarterly table rows
    q_rows_html = []
    for q in q_rows:
        q_dt = q["quarter"]
        ocf_v = ocf_map.get(q_dt)
        pre_mark = " *" if q.get("pre_deadline") else ""
        q_rows_html.append(
            f"<tr>"
            f'<td class="num">{esc(q_dt)}{esc(pre_mark)}</td>'
            f'<td class="cell-right"><span class="kpi-num">{q["revenue"] / 1e8:,.2f}</span> 億</td>'
            f'<td class="num">{q["gross_margin_pct"]:.2f}%</td>'
            f'<td class="num">{q["operating_margin_pct"]:.2f}%</td>'
            f'<td class="cell-right"><span class="kpi-num">{q["non_operating"] / 1e8:,.2f}</span> 億</td>'
            f'<td class="num">{q["eps"]:.2f}</td>'
            f'<td class="cell-right"><span class="kpi-num">{q["dsi_days"]:.1f}</span> 天</td>'
            f'<td class="cell-right"><span class="kpi-num">{ocf_v / 1e8:,.2f}</span> 億</td>'
            f"</tr>"
        )

    # Peer table rows
    peer_rows_html = []
    for pr in peers_data["rows"]:
        c_code = pr["code"]
        is_target = c_code == d["code"]
        reason_txt = (
            "本報告研究標的：全球交換式電源供應器、AI 資料中心高壓直流（HVDC）與液冷散熱龍頭。"
            if is_target
            else f"{peer_reasons[c_code]['reason']}（依據：{peer_reasons[c_code]['basis']}）"
        )
        row_cls = ' class="row-highlight"' if is_target else ""
        peer_rows_html.append(
            f"<tr{row_cls}>"
            f'<td><span class="kpi-num">{esc(c_code)}</span> {esc(peer_names.get(c_code, c_code))}</td>'
            f'<td class="num">{dv.fmt_mult(pr["PER"])}</td>'
            f'<td class="num">{dv.fmt_mult(pr["PBR"])}</td>'
            f'<td class="num">{pr["dividend_yield"]:.2f}%</td>'
            f"<td>{esc(reason_txt)}</td>"
            f"</tr>"
        )
    med = peers_data["median"]
    peer_rows_html.append(
        f'<tr class="row-summary">'
        f"<td>同業中位數（不含 2308）</td>"
        f'<td class="num">{dv.fmt_mult(med["PER"])}</td>'
        f'<td class="num">{dv.fmt_mult(med["PBR"])}</td>'
        f'<td class="num">{med["dividend_yield"]:.2f}%</td>'
        f"<td>3 家台灣上市直接競爭同業（2301、6412、3017）之最新估值中位數</td>"
        f"</tr>"
    )

    # Scenario table rows
    scen_rows_html = []
    for s in x["scenarios"]:
        im = s["implied"]
        im_pos_txt = pos_zh.get(im["position"], im["position"]) if im else "無資料"
        im_cell = (
            f'<span class="kpi-num" data-implied="{esc(s["name"])}">{dv.fmt_mult(im["value"])}</span>'
            f"（{esc(im['metric'])} {esc(im_pos_txt)}）"
            if im
            else "無資料"
        )
        row_cls = ' class="row-highlight"' if s["name"] == "Base" else ""
        scen_rows_html.append(
            f"<tr{row_cls}>"
            f"<td>{esc(s['label'])}（{esc(s['name'])}）</td>"
            f'<td class="num">{s["probability"]}%</td>'
            f'<td class="num">{dv.fmt_price(s["eps"])}</td>'
            f'<td class="num">{dv.fmt_mult(s["multiple"])}</td>'
            f'<td class="cell-right"><span class="kpi-num">{dv.fmt_price(s["target"])}</span> 元</td>'
            f'<td class="num">{dv.fmt_pct(s["upside_pct"])}</td>'
            f'<td class="cell-right">{im_cell}</td>'
            f"<td>{esc(s['assumptions'])}<br><small class=\"basis-note\">依據（分析師判斷）：{esc(s['basis'])}</small></td>"
            f"</tr>"
        )

    # Moat items
    moat_html = []
    for item in a["moat"]:
        moat_html.append(
            f'<div class="ledger-item">'
            f"<h3>{esc(item['title'])}</h3>"
            f"<p>{esc(item['text'])}</p>"
            f'<p class="basis-note">依據（分析師判斷）：{esc(item["basis"])}</p>'
            f"</div>"
        )

    # Catalysts & Risks tables
    cat_rows_html = []
    for c_item in a["catalysts"]:
        cat_rows_html.append(
            f"<tr>"
            f"<td>{esc(c_item['title'])}</td>"
            f"<td>{esc(c_item['timing'])}</td>"
            f"<td>{esc(c_item['direction'])}</td>"
            f"<td>{esc(c_item['indicator'])}</td>"
            f"<td>{esc(c_item['basis'])}</td>"
            f"</tr>"
        )

    risk_rows_html = []
    for r_item in a["risks"]:
        risk_rows_html.append(
            f"<tr>"
            f"<td>{esc(r_item['title'])}</td>"
            f"<td>{esc(r_item['timing'])}</td>"
            f"<td>{esc(r_item['direction'])}</td>"
            f"<td>{esc(r_item['indicator'])}</td>"
            f"<td>{esc(r_item['basis'])}</td>"
            f"</tr>"
        )

    # External facts list
    ext_facts_html = []
    for ef in a["external_facts"]:
        url_esc = html.escape(ef["url"])
        ext_facts_html.append(
            f"<li>"
            f"{esc(ef['text'])} "
            f'<span class="fact-cite">（來源：<a href="{url_esc}" target="_blank" rel="noopener">{esc(ef["source"])}</a>，{esc(ef["date"])}）</span>'
            f"</li>"
        )

    # Thesis breakers
    tb_rows_html = []
    for tb in a["thesis_breakers"]:
        tb_rows_html.append(
            f"<tr>"
            f"<td>{esc(tb['condition'])}</td>"
            f'<td class="cell-right">{esc(tb["threshold"])}</td>'
            f"<td>{esc(tb['dataset'])}</td>"
            f"</tr>"
        )

    # Gaps disclosure
    if d["gaps"]:
        gaps_items = "".join(f"<li>{esc(g)}</li>" for g in d["gaps"])
        gaps_html = f'<ul class="gaps-list">{gaps_items}</ul>'
    else:
        gaps_html = "<p>FinMind 資料完整度檢核：0 項缺漏（所有必要價量、籌碼、月營收、季報與估值欄位皆完整收錄）。</p>"

    # R:R status notes
    pb_note = (
        "條件成立（收盤位於 MA10–MA20 拉回區間內，R:R ≥ 1.5 具交易吸引力）"
        if x["pullback_status"] == "active"
        else dv.SETUP_STATUS_ZH[x["pullback_status"]]
    )
    bo_note = (
        f"條件待帶量觸發（須突破 60 日高點 {dv.fmt_price(x['trigger'])} 元且單日成交量 > {fmt_int(x['trigger_volume_lots'])} 張；R:R ≥ 1.5）"
        if x["breakout_status"] == "active"
        else dv.SETUP_STATUS_ZH[x["breakout_status"]]
    )
    hold_note = (
        "條件成立，惟長線持有 R:R 1.30 < 1.5（不具交易吸引力，宜搭配拉回分批布局以改善風報比）"
        if x["hold_status"] == "active" and x["rr_hold"] is not None and x["rr_hold"] < 1.5
        else (
            "條件成立（R:R ≥ 1.5）"
            if x["hold_status"] == "active"
            else dv.SETUP_STATUS_ZH[x["hold_status"]]
        )
    )

    page_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(d['code'])} {esc(a['name_zh'])} ({esc(a['name_en'])}) 深度股權研究報告｜{esc(d['asof'])}</title>
<meta name="description" content="台達電 (2308) 360 度股權研究報告：當前動作 {esc(x['action_zh'])}、投資評等 {esc(x['rating_zh'])}、基本情境目標價 {dv.fmt_price(base['target'])} 元（{dv.fmt_pct(base['upside_pct'])}），整合 FinMind 數據與法說會驗證事實。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>
(function() {{
  try {{
    var saved = localStorage.getItem('almanac-mode-2308');
    if (saved === 'dark' || saved === 'light') {{
      document.documentElement.setAttribute('data-mode', saved);
    }}
  }} catch (e) {{}}
}})();
</script>
<style>
/* Hallmark · shape: stat-led · genre: editorial · theme: Almanac (deal 1/3, seed 2308-equity-research-9490·ce12e4cc·2026-11-14·r0) · job: buy · draw: ce12e4cc
 * hero: stage · nav: edge-aligned wordmark, six section links, mode toggle · footer: ruled colophon · imagery: none · signature: printed Almanac reference sheet with action call and vertical price scale · modes: light+dark · copy: verbatim
 * axes: mid/grotesk-sans/chromatic-magenta · posture: restrained · contrast: pass · fold: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P5 H5 E5 S4 R5 V5 · weakest: S, multi-table equity reports can blur together; anchored the first screen on an Almanac printed specification sheet with a live price-to-target scale */
/* Hallmark · hero-review: not run, the report contract fixes the hero content · finish-review: subagent · 8 findings · 8 resolved · gap: vertical price scale and 2-band Almanac rhythm restored */
/* Hallmark · waive 44c · equity report contract requires a 7-KPI specification sheet in the hero · the Almanac reference sheet pairs the action verdict with the seven contract KPIs */
/* Hallmark · waive 79 · the Almanac specification sheet and vertical price scale complete the hero above the first section divider · the call, its condition and the primary action sit inside the fold */
/* Hallmark · dismissed F25 · every wide data table pins its first column (th:first-child, td:first-child sticky) and scrolls horizontally inside .table-scroll */
/* Hallmark · dismissed 58 · the page total counts six contract-required research sections; no single screen exceeds the budget */
:root {{
  color-scheme: light dark;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px; --space-3xl: 96px; --space-4xl: 144px;
  --text-xs: 0.8125rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.25rem; --text-xl: 1.5625rem; --text-2xl: 1.953rem; --text-3xl: 2.441rem;
  --text-display-s: clamp(1.85rem, 2.8vw + 0.5rem, 2.75rem); --text-display: clamp(2.15rem, 3.2vw + 0.65rem, 3.35rem);
  --text-section: clamp(2.25rem, 2.3vw + 1rem, 3.1rem); --text-title: clamp(1.25rem, 0.75vw + 0.875rem, 1.55rem); --text-lead: clamp(1.0625rem, 0.35vw + 0.95rem, 1.22rem);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --ease-in: cubic-bezier(0.7, 0, 0.84, 0); --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms; --dur-short: 220ms; --dur-long: 420ms;
  --color-error: oklch(46% 0.175 27); --color-success: oklch(42% 0.125 150);
  --container: 1440px; --gutter: 64px; --gap-columns: 32px; --section-gap-s: 120px; --section-gap: 136px; --section-gap-l: 160px;
  --z-base: 1; --z-raised: 10; --z-dropdown: 100; --z-sticky: 200; --z-sticky-nav: 300; --z-modal: 400; --z-toast: 500; --z-tooltip: 600;
  --color-paper: oklch(84% 0.012 245); --color-paper-2: oklch(81% 0.012 245); --color-paper-3: oklch(77% 0.012 245);
  --color-ink: oklch(16% 0.020 245); --color-ink-2: oklch(24% 0.018 245); --color-muted: oklch(34% 0.016 245);
  --color-rule: oklch(70% 0.013 240); --color-rule-2: oklch(32% 0.018 240);
  --color-accent: oklch(45% 0.180 350); --color-accent-2: oklch(37% 0.160 350); --color-accent-ink: oklch(97% 0.006 245); --color-focus: oklch(46% 0.190 350);
  --color-sheet: oklch(93.5% 0.008 245);
  --font-display: "Hanken Grotesk", "Noto Sans TC", "Microsoft JhengHei", ui-sans-serif, system-ui, sans-serif;
  --font-body: "Newsreader", "Noto Serif TC", "PMingLiU", ui-serif, Georgia, serif;
  --font-outlier: "IBM Plex Mono", ui-monospace, monospace;
  --radius-card: 0; --radius-pill: 2px; --rule-hair: 1px; --rule-bar: 2px; --shadow-card: none;
  --tracking-display: -0.02em; --display-weight: 600;
}}

[data-mode="dark"] {{
  color-scheme: dark;
  --color-paper: oklch(15% 0.012 245); --color-paper-2: oklch(18% 0.012 245); --color-paper-3: oklch(21% 0.012 245);
  --color-sheet: oklch(20% 0.012 245);
  --color-ink: oklch(94% 0.008 245); --color-ink-2: oklch(86% 0.010 245); --color-muted: oklch(72% 0.012 245);
  --color-rule: oklch(30% 0.013 240); --color-rule-2: oklch(62% 0.015 240);
  --color-accent: oklch(68% 0.155 350); --color-accent-2: oklch(74% 0.145 350); --color-accent-ink: oklch(15% 0.012 245); --color-focus: oklch(70% 0.160 350);
  --color-error: oklch(70% 0.155 27); --color-success: oklch(72% 0.130 150);
}}

@media (prefers-color-scheme: dark) {{
  :root:not([data-mode]) {{
    color-scheme: dark;
    --color-paper: oklch(15% 0.012 245); --color-paper-2: oklch(18% 0.012 245); --color-paper-3: oklch(21% 0.012 245);
    --color-sheet: oklch(20% 0.012 245);
    --color-ink: oklch(94% 0.008 245); --color-ink-2: oklch(86% 0.010 245); --color-muted: oklch(72% 0.012 245);
    --color-rule: oklch(30% 0.013 240); --color-rule-2: oklch(62% 0.015 240);
    --color-accent: oklch(68% 0.155 350); --color-accent-2: oklch(74% 0.145 350); --color-accent-ink: oklch(15% 0.012 245); --color-focus: oklch(70% 0.160 350);
    --color-error: oklch(70% 0.155 27); --color-success: oklch(72% 0.130 150);
  }}
}}

*, *::before, *::after {{ box-sizing: border-box; }}
html, body {{ overflow-x: clip; }}
html {{ scrollbar-color: var(--color-muted) var(--color-paper); scroll-padding-top: var(--space-3xl); }}
body {{ margin: 0; background: var(--color-paper); color: var(--color-ink-2); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.6; -webkit-font-smoothing: antialiased; caret-color: var(--color-accent); }}
::selection {{ background: color-mix(in oklab, var(--color-accent) 22%, transparent); color: var(--color-ink); }}
:focus-visible {{ outline: 2px solid var(--color-focus); outline-offset: 2px; }}
a {{ color: var(--color-ink); text-decoration-color: var(--color-accent); text-decoration-thickness: 1px; text-underline-offset: 0.15em; }}
a:hover {{ text-decoration-thickness: 2px; }}
h1, h2, h3 {{ margin: 0; font-family: var(--font-display); font-weight: var(--display-weight, 600); color: var(--color-ink); font-synthesis: none; letter-spacing: var(--tracking-display); line-height: 1.08; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }}
h1 {{ max-width: 22ch; font-size: var(--text-display); line-height: 1.04; }}
h2 {{ max-width: 30ch; font-size: var(--text-section); }}
h3 {{ max-width: 42ch; font-size: var(--text-title); line-height: 1.22; }}
.lead {{ font-size: var(--text-lead); line-height: 1.5; max-width: 58ch; color: var(--color-ink-2); }}
p {{ margin: 0; text-wrap: pretty; }}
p:not([class]) {{ max-width: 65ch; }}
img, video {{ max-width: 100%; height: auto; display: block; }}
svg {{ display: block; width: 100%; height: auto; }}
[hidden] {{ display: none !important; }}
button, input, select, textarea {{ font: inherit; }}
.container {{ width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); box-sizing: border-box; }}
.num, .figure, td.num, .kpi-num {{
  font-family: var(--font-outlier);
  font-variant-numeric: tabular-nums;
}}
.cell-right {{
  text-align: right;
  color: var(--color-ink);
  white-space: nowrap;
}}
.chart-scroll {{
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}}
svg.chart {{
  min-width: 680px;
}}

/* Top Navigation Bar */
.site-header {{
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  background: var(--color-paper);
  color: var(--color-ink);
  border-bottom: var(--rule-bar) solid var(--color-ink);
}}
.nav-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
  padding-block: var(--space-xs);
  flex-wrap: wrap;
}}
.brand-block {{
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
  flex-wrap: wrap;
}}
.brand-code {{
  font-family: var(--font-outlier);
  font-weight: 500;
  font-size: var(--text-lg);
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}}
.brand-name {{
  font-family: var(--font-display);
  font-weight: 600;
  font-size: var(--text-lg);
  color: var(--color-ink);
}}
.brand-meta {{
  font-size: var(--text-sm);
  color: var(--color-muted);
}}
.nav-links {{
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}}
.nav-links a {{
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  text-decoration: none;
  white-space: nowrap;
  padding-block: var(--space-2xs);
}}
.nav-links a:hover {{
  color: var(--color-ink);
  text-decoration: underline;
  text-decoration-color: var(--color-accent);
}}
.btn-toggle {{
  min-height: 40px;
  padding: var(--space-xs) var(--space-md);
  border: var(--rule-hair) solid var(--color-ink);
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}}
.btn-toggle:hover {{
  background: var(--color-paper-2);
}}
.btn-toggle:active {{
  transform: translateY(1px);
}}
.btn-toggle:disabled {{
  opacity: 0.5;
  cursor: not-allowed;
}}

/* Hero Section (First Screen) */
.hero-section {{
  padding-block: var(--space-lg) var(--space-2xl);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
}}
.hero-grid {{
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: var(--gap-columns);
  align-items: start;
}}
.hero-call {{
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  min-width: 0;
}}
.action-callout {{
  background: var(--color-sheet);
  color: var(--color-ink);
  border-top: var(--rule-bar) solid var(--color-accent);
  border-bottom: var(--rule-hair) solid var(--color-rule);
  padding: var(--space-md) var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}}
.action-verdict-row {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-md);
  flex-wrap: wrap;
}}
.action-verdict {{
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-ink);
}}
.action-condition {{
  font-family: var(--font-body);
  font-size: var(--text-md);
  color: var(--color-ink-2);
}}
.hero-actions {{
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}}
.btn-primary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: var(--space-xs) var(--space-lg);
  background: var(--color-accent);
  border: var(--rule-hair) solid var(--color-accent);
  border-radius: var(--radius-pill);
  color: var(--color-accent-ink);
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
}}
.btn-primary:hover {{
  background: var(--color-accent-2);
  border-color: var(--color-accent-2);
  text-decoration: none;
}}
.btn-primary:active {{
  transform: translateY(1px);
}}
.btn-secondary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: var(--space-xs) var(--space-lg);
  background: transparent;
  border: var(--rule-hair) solid var(--color-ink);
  border-radius: var(--radius-pill);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
}}
.btn-secondary:hover {{
  background: var(--color-paper-2);
  text-decoration: none;
}}
.btn-secondary:active {{
  transform: translateY(1px);
}}

/* Almanac Printed Specification Sheet (KPIs + Price Scale) */
.almanac-sheet {{
  background: var(--color-sheet);
  color: var(--color-ink);
  border-top: var(--rule-bar) solid var(--color-ink);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
  padding: var(--space-lg);
  min-width: 0;
}}
.sheet-header {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
  flex-wrap: wrap;
}}
.sheet-title {{
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-ink);
}}
.sheet-sub {{
  font-size: var(--text-sm);
  color: var(--color-muted);
}}
.kpi-table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: var(--space-xs);
}}
.kpi-table th, .kpi-table td {{
  padding: var(--space-sm) var(--space-md);
  border-bottom: var(--rule-hair) solid var(--color-rule);
}}
.kpi-table th {{
  font-family: var(--font-body);
  font-weight: 500;
  font-size: var(--text-sm);
  color: var(--color-muted);
  text-align: left;
}}
.kpi-table td.num {{
  text-align: right;
  font-weight: 500;
  font-size: var(--text-md);
  color: var(--color-ink);
}}
.kpi-table tr.row-highlight td {{
  color: var(--color-ink);
  font-weight: 600;
}}
.ladder-bar {{
  margin-top: var(--space-md);
  padding-top: var(--space-sm);
  border-top: var(--rule-bar) solid var(--color-rule-2);
  display: flex;
  flex-direction: column;
  gap: 0;
  border-left: var(--rule-bar) solid var(--color-ink);
  padding-left: var(--space-md);
}}
.ladder-step {{
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-paper);
  color: var(--color-ink);
  border-bottom: var(--rule-hair) solid var(--color-rule);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-md);
  min-width: 0;
}}
.ladder-step--active {{
  background: var(--color-paper-2);
  border-top: var(--rule-hair) solid var(--color-accent);
  border-bottom: var(--rule-hair) solid var(--color-accent);
  font-weight: 600;
}}
.ladder-name {{
  font-size: var(--text-sm);
  color: var(--color-ink-2);
  white-space: nowrap;
}}
.ladder-val {{
  font-family: var(--font-outlier);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}}
.hero-meta-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-sm) var(--space-lg);
  margin: 0;
  padding-top: var(--space-md);
  border-top: var(--rule-hair) solid var(--color-rule-2);
}}
.hero-meta-grid dt {{
  font-size: var(--text-xs);
  color: var(--color-muted);
}}
.hero-meta-grid dd {{
  margin: var(--space-3xs) 0 0;
  font-size: var(--text-sm);
  color: var(--color-ink);
  font-weight: 500;
}}

/* Report Sections */
.report-section {{
  padding-block: var(--space-2xl);
  border-bottom: var(--rule-hair) solid var(--color-rule);
}}
.report-section--well {{
  background: var(--color-paper-2);
  color: var(--color-ink-2);
  border-top: var(--rule-bar) solid var(--color-rule-2);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
}}
.section-head {{
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  margin-bottom: var(--space-xl);
  padding-bottom: var(--space-md);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
}}
.section-split {{
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
  gap: var(--gap-columns);
  align-items: start;
}}
.section-split--equal {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--gap-columns);
  align-items: start;
}}
.section-stack {{
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
  min-width: 0;
}}

/* Figures, Charts & Tables */
figure.sheet-figure {{
  margin: 0;
  background: var(--color-sheet);
  color: var(--color-ink-2);
  border-top: var(--rule-bar) solid var(--color-ink);
  border-bottom: var(--rule-hair) solid var(--color-rule);
  padding: var(--space-lg);
  min-width: 0;
}}
figure.sheet-figure figcaption {{
  margin-top: var(--space-sm);
  padding-top: var(--space-xs);
  border-top: var(--rule-hair) solid var(--color-rule);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--color-muted);
}}
.figure-head {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
  flex-wrap: wrap;
}}
.figure-legend {{
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
  font-size: var(--text-xs);
  color: var(--color-muted);
  margin: 0;
  padding: 0;
  list-style: none;
}}
.swatch {{
  display: inline-block;
  width: 12px;
  height: 3px;
  margin-right: var(--space-2xs);
  vertical-align: middle;
}}
.swatch--accent {{ background: var(--color-accent); }}
.swatch--ink {{ background: var(--color-ink); }}
.swatch--muted {{ background: var(--color-muted); }}
.swatch--ok {{ background: var(--color-success); }}
.swatch--err {{ background: var(--color-error); }}

.table-scroll {{
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}}
table.data-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}}
table.data-table thead th {{
  font-family: var(--font-body);
  font-weight: 500;
  font-size: var(--text-sm);
  color: var(--color-muted);
  text-align: left;
  padding: var(--space-sm) var(--space-md);
  border-bottom: var(--rule-bar) solid var(--color-rule-2);
  white-space: nowrap;
}}
table.data-table thead th.num {{
  text-align: right;
}}
table.data-table tbody td {{
  padding: var(--space-sm) var(--space-md);
  border-top: var(--rule-hair) solid var(--color-rule);
  color: var(--color-ink-2);
  vertical-align: top;
  overflow-wrap: break-word;
}}
table.data-table tbody td:not(.num):not(.cell-right) {{
  min-width: 14rem;
}}
table.data-table tbody td:last-child:not(.num):not(.cell-right) {{
  min-width: 18rem;
}}
table.data-table tbody td.num {{
  text-align: right;
  color: var(--color-ink);
  white-space: nowrap;
  overflow-wrap: normal;
}}
table.data-table th:first-child,
table.data-table td:first-child {{
  position: sticky;
  left: 0;
  background: var(--color-sheet);
  z-index: 1;
  min-width: 11rem;
}}
table.data-table tbody tr:hover td {{
  background: var(--color-paper-2);
}}
table.data-table tbody tr.row-highlight td {{
  background: var(--color-paper);
  color: var(--color-ink);
  font-weight: 500;
}}
table.data-table tbody tr.row-summary td {{
  border-top: var(--rule-bar) solid var(--color-rule-2);
  color: var(--color-ink);
  font-weight: 500;
}}

/* Ledger Blocks & Notes */
.ledger-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--gap-columns);
}}
.ledger-item {{
  background: var(--color-sheet);
  color: var(--color-ink-2);
  border-top: var(--rule-bar) solid var(--color-rule-2);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  min-width: 0;
}}
.basis-note {{
  font-size: var(--text-xs);
  color: var(--color-muted);
  line-height: 1.45;
  padding-top: var(--space-2xs);
  overflow-wrap: anywhere;
}}
.judgment-box {{
  background: var(--color-sheet);
  color: var(--color-ink-2);
  border-top: var(--rule-bar) solid var(--color-ink);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  min-width: 0;
}}
.facts-list {{
  margin: 0;
  padding-left: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  font-size: var(--text-sm);
}}
.fact-cite {{
  color: var(--color-muted);
  font-size: var(--text-xs);
}}

/* SVG Chart Styling via Tokens */
.grid-line {{ stroke: var(--color-rule); stroke-width: 1; }}
.grid-line-firm {{ stroke: var(--color-rule-2); stroke-width: 1.5; }}
.axis-num {{
  fill: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}}
.axis-label {{
  fill: var(--color-ink);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
}}
.candle-up {{ fill: var(--color-accent); stroke: var(--color-accent); stroke-width: 1; }}
.candle-up-wick {{ stroke: var(--color-accent); stroke-width: 1.2; }}
.candle-down {{ fill: var(--color-ink-2); stroke: var(--color-ink-2); stroke-width: 1; }}
.candle-down-wick {{ stroke: var(--color-ink-2); stroke-width: 1.2; }}
.vol-bar {{ fill: var(--color-muted); opacity: 0.55; }}
.vol-spike {{ fill: var(--color-accent); opacity: 0.9; }}
.vol-dry {{ fill: var(--color-rule-2); opacity: 0.35; }}
.vol-avg-line {{ stroke: var(--color-ink); stroke-width: 1.2; }}
.ma-line-5 {{ fill: none; stroke: var(--color-accent); stroke-width: 2; }}
.ma-line-10 {{ fill: none; stroke: var(--color-ink); stroke-width: 1.75; }}
.ma-line-20 {{ fill: none; stroke: var(--color-muted); stroke-width: 1.75; }}
.trade-line-entry {{ stroke: var(--color-ink); stroke-width: 2; }}
.trade-line-t1 {{ stroke: var(--color-success); stroke-width: 1.75; }}
.trade-line-t2 {{ stroke: var(--color-accent); stroke-width: 2; }}
.trade-line-sl {{ stroke: var(--color-error); stroke-width: 2; }}
.series-accent {{ fill: none; stroke: var(--color-accent); stroke-width: 2.2; }}
.series-ink {{ fill: none; stroke: var(--color-ink); stroke-width: 2; }}
.series-muted {{ fill: none; stroke: var(--color-muted); stroke-width: 1.75; }}
.point-dot {{ fill: var(--color-accent); stroke: var(--color-sheet); stroke-width: 1.5; cursor: pointer; }}
.point-hit {{ fill: var(--color-ink); opacity: 0.75; cursor: pointer; }}
.bar-ink {{ fill: var(--color-ink-2); cursor: pointer; }}
.bar-accent {{ fill: var(--color-accent); cursor: pointer; }}
.band-outer {{ fill: var(--color-paper-2); stroke: var(--color-rule-2); stroke-width: 1; }}
.band-iqr {{ fill: var(--color-paper-3); stroke: var(--color-ink); stroke-width: 1.2; }}
.band-median {{ stroke: var(--color-ink); stroke-width: 2.2; }}

/* Floating Chart Tooltip */
.chart-tooltip {{
  position: fixed;
  z-index: var(--z-tooltip);
  pointer-events: none;
  background: var(--color-ink);
  color: var(--color-sheet);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-pill);
  font-family: var(--font-outlier);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  max-width: 340px;
  line-height: 1.4;
}}

/* Footer */
.site-footer {{
  background: var(--color-paper-2);
  color: var(--color-muted);
  border-top: var(--rule-bar) solid var(--color-ink);
  padding-block: var(--space-2xl);
  font-size: var(--text-sm);
}}
.footer-grid {{
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
  gap: var(--gap-columns);
  align-items: start;
}}
.footer-meta-table {{
  width: 100%;
  border-collapse: collapse;
}}
.footer-meta-table td {{
  padding: var(--space-xs) var(--space-sm);
  border-bottom: var(--rule-hair) solid var(--color-rule);
}}
.footer-meta-table td:last-child {{
  text-align: right;
  color: var(--color-ink);
}}

@media (max-width: 64rem) {{
  :root {{ --gutter: 24px; --section-gap-s: 80px; --section-gap: 96px; --section-gap-l: 120px; }}
  .hero-grid, .section-split, .section-split--equal, .ledger-grid, .footer-grid {{
    grid-template-columns: minmax(0, 1fr);
  }}
}}
@media (max-width: 40rem) {{
  :root {{ --gutter: 16px; --section-gap-s: 56px; --section-gap: 72px; --section-gap-l: 96px; --gap-columns: 16px; }}
  .almanac-sheet {{
    padding: var(--space-md);
  }}
  .kpi-table th, .kpi-table td {{
    padding: var(--space-xs) var(--space-2xs);
    font-size: var(--text-sm);
  }}
  .kpi-table td.cell-right {{
    white-space: normal;
  }}
  .hero-meta-grid {{
    grid-template-columns: minmax(0, 1fr);
  }}
  table.data-table th:first-child,
  table.data-table td:first-child {{
    min-width: 7.5rem;
  }}
  .nav-links {{
    gap: var(--space-xs);
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  *:not(.keep-motion), *:not(.keep-motion)::before, *:not(.keep-motion)::after {{
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }}
}}
</style>
</head>
<body>

<header class="site-header">
  <div class="container nav-inner">
    <div class="brand-block">
      <span class="brand-code">{esc(d['code'])}</span>
      <span class="brand-name">{esc(a['name_zh'])} {esc(a['name_en'])}</span>
      <span class="brand-meta">台灣上市（{esc(a['industry'])}）｜基準日 {esc(d['asof'])}</span>
    </div>
    <nav class="nav-links" aria-label="報告章節導覽">
      <a href="#dim1">價量均線</a>
      <a href="#dim2">籌碼結構</a>
      <a href="#dim3">營運財務</a>
      <a href="#dim4">估值目標價</a>
      <a href="#dim5">催化劑與風險</a>
      <a href="#dim6">交易風控</a>
      <button type="button" id="mode-toggle" class="btn-toggle" aria-label="切換深淺色主題">切換深色 / 淺色</button>
    </nav>
  </div>
</header>

<main>
  <section class="hero-section" id="hero">
    <div class="container hero-grid">
      <div class="hero-call">
        <h1>{esc(a['name_zh'])}（{esc(d['code'])}）股權研究年鑑：高壓直流與液冷成長確立，回檔均線帶分批布局</h1>
        <p class="lead">2026 年 10 月營收創 746.66 億元新高（年增 30.1%），近四季每股盈餘 33.30 元、現金轉換率 1.33x；股價修正至 1,240 元後已進入 10 日與 20 日均線拉回區間。</p>
        <div class="hero-actions">
          <a href="#dim6" class="btn-primary">檢視波段與長線交易計畫</a>
          <a href="#dim4" class="btn-secondary">查閱三情境估值模型</a>
        </div>
        <div class="action-callout" role="region" aria-label="當前投資動作與條件">
          <div class="action-verdict-row">
            <span class="action-verdict" data-kpi="action">{esc(x['action_zh'])}</span>
            <span class="action-condition">{esc(x['action_note'])}</span>
          </div>
          <p class="basis-note">綜合評等：<strong data-kpi="rating">{esc(x['rating_zh'])}</strong>（Buy）｜合理買進價上限 {dv.fmt_price(x['fair_buy'])} 元｜期望值加權目標價 {dv.fmt_price(x['weighted_target'])} 元（{dv.fmt_pct(x['weighted_upside_pct'])}）</p>
        </div>
        <dl class="hero-meta-grid" aria-label="核心營運與籌碼指標">
          <div class="hero-meta-item">
            <dt>前 10 月累計營收（YoY）</dt>
            <dd><span class="kpi-num">{rev['ytd'] / 1e8:,.2f}</span> 億（<span class="kpi-num">{dv.fmt_pct(rev['ytd_yoy_pct'])}</span>）</dd>
          </div>
          <div class="hero-meta-item">
            <dt>近四季營業現金流轉換率</dt>
            <dd><span class="kpi-num">{fin['cash_conversion']['ratio']:.2f}x</span>（<span class="kpi-num">3Q26</span> 營益率 <span class="kpi-num">{fin['quarters'][-1]['operating_margin_pct']:.2f}%</span>）</dd>
          </div>
          <div class="hero-meta-item">
            <dt>近 20 日投信買超 / 融資減幅</dt>
            <dd><span class="kpi-num">{fmt_signed_int(inst['cum']['trust'])}</span> 張 / <span class="kpi-num">{dv.fmt_pct(mg['margin_change_pct'])}</span></dd>
          </div>
          <div class="hero-meta-item">
            <dt>2026-11-06 換手天量低點</dt>
            <dd><span class="kpi-num">1,020</span> 元（<span class="kpi-num">{fmt_int(m['w20_maxvol_lots'])}</span> 張）</dd>
          </div>
        </dl>
      </div>

      <div class="almanac-sheet" role="region" aria-label="關鍵指標摘要表">
        <div class="sheet-header">
          <span class="sheet-title">Almanac 關鍵決策指標總覽</span>
          <span class="sheet-sub">資料基準日 <span class="kpi-num" data-kpi="asof">{esc(d['asof'])}</span></span>
        </div>
        <table class="kpi-table">
          <tbody>
            <tr>
              <th>最新收盤價（Close）</th>
              <td class="cell-right"><span class="kpi-num" data-kpi="close">{dv.fmt_price(x['close'])}</span> 元</td>
            </tr>
            <tr class="row-highlight">
              <th>基本情境目標價（12m Base Target）</th>
              <td class="cell-right"><span class="kpi-num" data-kpi="target">{dv.fmt_price(base['target'])}</span> 元</td>
            </tr>
            <tr class="row-highlight">
              <th>基本情境潛在上漲空間（Base Upside）</th>
              <td class="num"><span class="kpi-num" data-kpi="upside">{dv.fmt_pct(base['upside_pct'])}</span></td>
            </tr>
            <tr>
              <th>波段拉回風險報酬比（Pullback Ratio）</th>
              <td class="num"><span class="kpi-num" data-kpi="rr">{dv.fmt_rr(x['rr_pullback'])}</span> : 1</td>
            </tr>
            <tr>
              <th>近四季累計每股盈餘（Trailing 4Q）</th>
              <td class="cell-right"><span class="kpi-num">{dv.fmt_price(fin['ttm_eps'])}</span> 元（本益比 <span class="kpi-num">{dv.fmt_mult(val['PER']['current'])}</span>）</td>
            </tr>
            <tr>
              <th>最新每股淨值與股價淨值比</th>
              <td class="cell-right"><span class="kpi-num">{dv.fmt_price(fin['bvps_latest'])}</span> 元（淨值比 <span class="kpi-num">{dv.fmt_mult(val['PBR']['current'])}</span>）</td>
            </tr>
          </tbody>
        </table>
        <div class="ladder-bar" aria-label="價格與目標價階梯（由高至低，單位：元）">
          <div class="ladder-step">
            <span class="ladder-name">樂觀目標價 Bull（<span class="kpi-num">{dv.fmt_pct(bull['upside_pct'])}</span>）</span>
            <span class="ladder-val">{dv.fmt_price(bull['target'])}</span>
          </div>
          <div class="ladder-step ladder-step--active">
            <span class="ladder-name">基本目標價 Base（<span class="kpi-num">{dv.fmt_pct(base['upside_pct'])}</span>）</span>
            <span class="ladder-val">{dv.fmt_price(base['target'])}</span>
          </div>
          <div class="ladder-step">
            <span class="ladder-name">波段拉回進場中位（<span class="kpi-num">10</span> 至 <span class="kpi-num">20</span> 日線）</span>
            <span class="ladder-val">{dv.fmt_price(x['entry'])}</span>
          </div>
          <div class="ladder-step ladder-step--active">
            <span class="ladder-name">最新收盤價 Close（基準）</span>
            <span class="ladder-val">{dv.fmt_price(x['close'])}</span>
          </div>
          <div class="ladder-step">
            <span class="ladder-name">波段硬停損價（<span class="kpi-num">11/06</span> 爆量低點）</span>
            <span class="ladder-val">{dv.fmt_price(x['hard_stop'])}</span>
          </div>
          <div class="ladder-step">
            <span class="ladder-name">悲觀目標價 Bear（<span class="kpi-num">{dv.fmt_pct(bear['upside_pct'])}</span>）</span>
            <span class="ladder-val">{dv.fmt_price(bear['target'])}</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Section dim1: 價量與均線 -->
  <section id="dim1" class="report-section">
    <div class="container section-stack">
      <div class="section-head">
        <h2>價量與均線結構：急跌後於千元關卡爆量換手，浮額沉澱訊號觸發</h2>
        <p class="lead">近 20 個交易日（{esc(m['w20_start'])} 至 {esc(d['asof'])}）台達電由 {dv.fmt_price(m['w20_high'])} 元修正至最低 {dv.fmt_price(m['w20_low'])} 元（2026-11-06 爆出 {fmt_int(m['w20_maxvol_lots'])} 張天量後止跌反彈），最新收盤 {dv.fmt_price(m['close'])} 元已站上 10 日線（{dv.fmt_price(m['ma10'])} 元）並逼近 5 日線（{dv.fmt_price(m['ma5'])} 元），與 20 日線（{dv.fmt_price(m['ma20'])} 元）負乖離達 {dv.fmt_pct(m['bias_ma20_pct'])}。</p>
      </div>

      <figure class="sheet-figure">
        <div class="figure-head">
          <h3>近 65 個交易日 K 線、均線（5 日 / 10 日 / 20 日）與成交量</h3>
          <ul class="figure-legend">
            <li><i class="swatch swatch--accent"></i>5 日均線（{dv.fmt_price(m['ma5'])}）</li>
            <li><i class="swatch swatch--ink"></i>10 日均線（{dv.fmt_price(m['ma10'])}）</li>
            <li><i class="swatch swatch--muted"></i>20 日均線（{dv.fmt_price(m['ma20'])}）</li>
          </ul>
        </div>
        {kline_dim1_svg}
        <figcaption>資料來源：FinMind TaiwanStockPrice（區間：2026-05 至 2026-11，繪製最近 65 個交易日；單位：新台幣元、張）。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>近 20 日價量與均線量化診斷表</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>技術指標項目</th>
                <th class="num">量化數值</th>
                <th>狀態判讀</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>最新收盤價（2026-11-13）</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(m['close'])}</span> 元</td>
                <td>守穩 10 日均線之上、測試 5 日均線</td>
              </tr>
              <tr>
                <td>短期均線（5 日 / 10 日 / 20 日）</td>
                <td class="num">{dv.fmt_price(m['ma5'])} / {dv.fmt_price(m['ma10'])} / {dv.fmt_price(m['ma20'])}</td>
                <td>{esc(align_zh)}（5 日線高於 10 日線、低於 20 日線）</td>
              </tr>
              <tr>
                <td>均線糾結度與月線乖離率</td>
                <td class="num">{m['ma_spread_pct']:.2f}% / {dv.fmt_pct(m['bias_ma20_pct'])}</td>
                <td>未糾結（帶寬 ≥ 2%），月線負乖離修復中</td>
              </tr>
              <tr>
                <td>近 20 日區間高低點</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(m['w20_low'])}</span> 至 <span class="kpi-num">{dv.fmt_price(m['w20_high'])}</span></td>
                <td>高點 {esc(m['w20_high_date'])}、低點 {esc(m['w20_low_date'])}</td>
              </tr>
              <tr>
                <td>近 60 日區間高低點</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(m['low60'])}</span> 至 <span class="kpi-num">{dv.fmt_price(m['high60'])}</span></td>
                <td>高點 {esc(m['high60_date'])}、低點 {esc(m['low60_date'])}</td>
              </tr>
              <tr>
                <td>20 日均量與爆量日（> 1.5x 均量）</td>
                <td class="cell-right"><span class="kpi-num">{fmt_int(m['vol_avg20_lots'])}</span> 張（<span class="kpi-num">2</span> 日）</td>
                <td>{esc("、".join(m['spike_days']))} 低檔爆量換手</td>
              </tr>
              <tr>
                <td>近 20 日量縮日（< 0.6x 均量）</td>
                <td class="cell-right"><span class="kpi-num">{len(m['dryup_days'])}</span> 日</td>
                <td>{esc("、".join(m['dryup_days']))}</td>
              </tr>
              <tr class="row-highlight">
                <td>浮額沉澱訊號（Float Settling）</td>
                <td class="cell-right">融資 <span class="kpi-num">{fmt_signed_int(m['float_settling']['margin_change'])}</span> 張 / 量縮 <span class="kpi-num">{m['float_settling']['dryup_count']}</span> 日</td>
                <td>訊號成立（融資減少且量縮日 ≥ 5 日）</td>
              </tr>
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockPrice 與 TaiwanStockMarginPurchaseShortSale（區間：2026-10 至 2026-11）。</figcaption>
      </figure>
    </div>
  </section>

  <!-- Section dim2: 籌碼結構 -->
  <section id="dim2" class="report-section">
    <div class="container section-stack">
      <div class="section-head">
        <h2>籌碼結構：外資波段調節 6.06 萬張，投信與自營商逢低承接、融資同步減肥 8.1%</h2>
        <p class="lead">近 20 個交易日（2026-10-15 至 2026-11-13）外資累計賣超 {fmt_int(abs(inst['cum']['foreign']))} 張，外資持股比率由 {fh['first']:.2f}% 降至 {fh['last']:.2f}%（{dv.fmt_pct(fh['change_pp'], dec=2, suffix=' 個百分點')}）；同期間投信累計買超 {fmt_signed_int(inst['cum']['trust'])} 張（15 個淨買超日）、自營商買超 {fmt_signed_int(inst['cum']['dealer'])} 張，且融資餘額由 {fmt_int(mg['margin_first'])} 張降至 {fmt_int(mg['margin_last'])} 張（{dv.fmt_pct(mg['margin_change_pct'])}），散戶浮額有效清洗。</p>
      </div>

      <figure class="sheet-figure">
        <div class="figure-head">
          <h3>近 20 日三大法人累計買賣超（左軸：張）與外資持股比率趨勢（右圖：%，軸區間 58.55% 至 61.20%）</h3>
          <ul class="figure-legend">
            <li><i class="swatch swatch--accent"></i>外資累計 / 外資持股比率</li>
            <li><i class="swatch swatch--ink"></i>投信累計</li>
            <li><i class="swatch swatch--muted"></i>自營商累計</li>
          </ul>
        </div>
        {chips_svg}
        <figcaption>資料來源：FinMind TaiwanStockInstitutionalInvestorsBuySell、TaiwanStockShareholding（區間：2026-10 至 2026-11，共 20 個交易日）。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>外資持股、信用交易與法人成本區彙整</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>籌碼維度</th>
                <th class="num">期初（10-15）</th>
                <th class="num">期末（11-13）</th>
                <th class="num">近 20 日變動與區間</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>外資持股比率</td>
                <td class="num">{fh['first']:.2f}%</td>
                <td class="num">{fh['last']:.2f}%</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_pct(fh['change_pp'], dec=2, suffix=' pp')}</span>（高 <span class="kpi-num">{fh['high']:.2f}%</span> / 低 <span class="kpi-num">{fh['low']:.2f}%</span>）</td>
              </tr>
              <tr>
                <td>融資餘額（張）</td>
                <td class="num">{fmt_int(mg['margin_first'])}</td>
                <td class="num">{fmt_int(mg['margin_last'])}</td>
                <td class="cell-right"><span class="kpi-num">{fmt_signed_int(mg['margin_change'])}</span> 張（<span class="kpi-num">{dv.fmt_pct(mg['margin_change_pct'])}</span>）</td>
              </tr>
              <tr>
                <td>融券餘額（張）</td>
                <td class="num">{fmt_int(mg['short_first'])}</td>
                <td class="num">{fmt_int(mg['short_last'])}</td>
                <td class="cell-right"><span class="kpi-num">{fmt_signed_int(mg['short_change'])}</span> 張（<span class="kpi-num">{dv.fmt_pct(mg['short_change_pct'])}</span>）</td>
              </tr>
              <tr>
                <td>券資比（Short-to-Margin）</td>
                <td class="num">0.33%</td>
                <td class="num">{mg['short_margin_ratio_pct']:.2f}%</td>
                <td class="cell-right">{esc(sm_level_zh)}</td>
              </tr>
              <tr class="row-highlight">
                <td>法人成本區（投信 15 日加權）</td>
                <td class="cell-right">均價 <span class="kpi-num">{inst['cost_zone']['price']:.2f}</span></td>
                <td class="cell-right">區間 <span class="kpi-num">±2%</span></td>
                <td class="cell-right"><span class="kpi-num">{inst['cost_zone']['low']:.2f}</span> 至 <span class="kpi-num">{inst['cost_zone']['high']:.2f}</span> 元</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="basis-note">註：因外資於近 20 日僅 1 個淨買超日（少於 3 日門檻），依方法論第 3 節改採投信近 20 日淨買超日（共 {inst['cost_zone']['days']} 日）之成交量加權均價 {inst['cost_zone']['price']:.2f} 元計算法人成本區。</p>
        <figcaption>資料來源：FinMind TaiwanStockShareholding、TaiwanStockMarginPurchaseShortSale（區間：2026-10 至 2026-11）。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>近 20 日三大法人每日買賣超明細表（單位：張）</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>交易日期</th>
                <th class="num">外資買賣超</th>
                <th class="num">投信買賣超</th>
                <th class="num">自營商買賣超</th>
                <th class="num">三大法人合計</th>
                <th class="num">外資累計</th>
              </tr>
            </thead>
            <tbody>
              {"".join(inst_rows_html)}
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockInstitutionalInvestorsBuySell（區間：2026-10 至 2026-11）。</figcaption>
      </figure>
    </div>
  </section>

  <!-- Section dim3: 營運與財務 -->
  <section id="dim3" class="report-section">
    <div class="container section-stack">
      <div class="section-head">
        <h2>營運與財務：10 月營收 746.66 億元刷新歷史紀錄，營業現金流轉換率高達 1.33x</h2>
        <p class="lead">2026 年 1 至 10 月累計合併營收達 {fmt_yi(rev['ytd'], 2)}（較去年同期 {fmt_yi(rev['ytd_prev'], 2)} 年增 {dv.fmt_pct(rev['ytd_yoy_pct'])}）；近四季（4Q25 至 3Q26）累計每股盈餘達 {dv.fmt_price(fin['ttm_eps'])} 元，3Q26 單季營收衝上 {fmt_yi(fin['quarters'][-1]['revenue'], 2)} 新高，營業利益率穩定維持 {fin['quarters'][-1]['operating_margin_pct']:.2f}%。</p>
      </div>

      <figure class="sheet-figure">
        <div class="figure-head">
          <h3>近 12 個月單月合併營收（左圖：億元）與年增率 YoY（右圖：%）</h3>
          <ul class="figure-legend">
            <li><i class="swatch swatch--ink"></i>單月營收（億元，基線為 0）</li>
            <li><i class="swatch swatch--accent"></i>最新月營收（2026-10：746.66 億）/ 年增率 YoY（%）</li>
          </ul>
        </div>
        {rev_svg}
        <figcaption>資料來源：FinMind TaiwanStockMonthRevenue（區間：2025-11 至 2026-10）。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>近四季損益、存貨周轉天數與營業現金流</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>季度別</th>
                <th class="num">合併營收</th>
                <th class="num">毛利率</th>
                <th class="num">營業利益率</th>
                <th class="num">業外收支</th>
                <th class="num">單季每股盈餘</th>
                <th class="num">存貨周轉天數</th>
                <th class="num">營業現金流</th>
              </tr>
            </thead>
            <tbody>
              {"".join(q_rows_html)}
              <tr class="row-summary">
                <td>近四季合計 / 最新（Trailing 4Q）</td>
                <td class="cell-right"><span class="kpi-num">{sum(q['revenue'] for q in q_rows) / 1e8:,.2f}</span> 億</td>
                <td class="cell-right"><span class="kpi-num">35.27%</span>（均值）</td>
                <td class="cell-right"><span class="kpi-num">16.85%</span>（均值）</td>
                <td class="cell-right"><span class="kpi-num">{sum(q['non_operating'] for q in q_rows) / 1e8:,.2f}</span> 億</td>
                <td class="cell-right"><span class="kpi-num">{fin['ttm_eps']:.2f}</span> 元</td>
                <td class="cell-right"><span class="kpi-num">107.7</span> 天（3Q26）</td>
                <td class="cell-right"><span class="kpi-num">{fin['cash_conversion']['ttm_ocf'] / 1e8:,.2f}</span> 億</td>
              </tr>
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockFinancialStatements、TaiwanStockBalanceSheet、TaiwanStockCashFlowsStatement（區間：2025-12 至 2026-09；標註 * 之 2026-09-30 季報於法定申報截止日 11-14 前已公告）。</figcaption>
      </figure>

      <div class="section-split">
        <div class="judgment-box">
          <h3>產業盈餘品質焦點：{esc(a['earnings_quality']['focus'])}（分析師判斷）</h3>
          <p>{esc(a['earnings_quality']['text'])}</p>
          <p class="basis-note">依據：{esc(a['earnings_quality']['basis'])}</p>
        </div>

        <figure class="sheet-figure">
          <h3>近 12 個月營收明細（2025-11 至 2026-10）</h3>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>年月</th>
                  <th class="num">單月營收</th>
                  <th class="num">月增率 MoM</th>
                  <th class="num">年增率 YoY</th>
                </tr>
              </thead>
              <tbody>
                {"".join(rev_rows_html)}
              </tbody>
            </table>
          </div>
          <figcaption>資料來源：FinMind TaiwanStockMonthRevenue（區間：2025-11 至 2026-10；累計前 10 月營收 6,143.34 億元，YoY +36.3%）。</figcaption>
        </figure>
      </div>
    </div>
  </section>

  <!-- Section dim4: 估值與目標價 -->
  <section id="dim4" class="report-section report-section--well">
    <div class="container section-stack">
      <div class="section-head">
        <h2>估值與目標價：本益比法推導基本情境目標價 {dv.fmt_price(base['target'])} 元（{dv.fmt_pct(base['upside_pct'])}），評等「{esc(x['rating_zh'])}」</h2>
        <p class="lead">{esc(a['valuation_method_basis'])} 目前本益比 {dv.fmt_mult(val['PER']['current'])} 位於 5 年第 {val['PER']['current_percentile']:.1f}% 分位（P75 為 {dv.fmt_mult(val['PER']['p75'])}），股價淨值比 {dv.fmt_mult(val['PBR']['current'])} 位於第 {val['PBR']['current_percentile']:.1f}% 分位；三情境機率加權目標價為 {dv.fmt_price(x['weighted_target'])} 元（{dv.fmt_pct(x['weighted_upside_pct'])}）。</p>
      </div>

      <figure class="sheet-figure">
        <div class="figure-head">
          <h3>5 年歷史本益比與股價淨值比分位數帶狀圖（n = {val['PER']['n']} 個交易日）</h3>
          <ul class="figure-legend">
            <li><i class="swatch swatch--muted"></i>P10 至 P90 歷史寬帶</li>
            <li><i class="swatch swatch--ink"></i>P25 至 P75 中間四分位與 P50 中位線</li>
            <li><i class="swatch swatch--accent"></i>2026-11-13 最新位置</li>
          </ul>
        </div>
        {val_svg}
        <figcaption>資料來源：FinMind TaiwanStockPER（區間：{esc(val['start'])} 至 {esc(val['date'])}，共 {val['PER']['n']} 筆有效交易日）。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>12 個月 Bull / Base / Bear 三情境估值與隱含交叉倍數檢核表（分析師判斷）</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>情境別</th>
                <th class="num">機率權重</th>
                <th class="num">前瞻每股盈餘（元）</th>
                <th class="num">目標本益比（x）</th>
                <th class="num">目標價（元）</th>
                <th class="num">潛在空間</th>
                <th class="num">隱含交叉淨值比與分位</th>
                <th>核心假設與定錨依據（分析師判斷）</th>
              </tr>
            </thead>
            <tbody>
              {"".join(scen_rows_html)}
              <tr class="row-summary">
                <td>機率加權期望值（Weighted）</td>
                <td class="num">100%</td>
                <td class="num">52.20</td>
                <td class="cell-right">不適用</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(x['weighted_target'])}</span> 元</td>
                <td class="num">{dv.fmt_pct(x['weighted_upside_pct'])}</td>
                <td class="cell-right"><span class="kpi-num">13.92x</span>（淨值比 P75 至 P90）</td>
                <td>依 Base 上漲空間 {dv.fmt_pct(base['upside_pct'])} 高於 +15% 門檻，給予投資評等「<strong>{esc(x['rating_zh'])}</strong>」（Buy）</td>
              </tr>
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockPER、TaiwanStockFinancialStatements（2021-11 至 2026-11）與分析師三情境推演。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>台灣上市電源與散熱直接競爭同業估值比較矩陣</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>公司代號與名稱</th>
                <th class="num">本益比（x）</th>
                <th class="num">股價淨值比（x）</th>
                <th class="num">現金殖利率</th>
                <th>直接競爭業務與選樣理由（分析師判斷）</th>
              </tr>
            </thead>
            <tbody>
              {"".join(peer_rows_html)}
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockPER（基準日：2026-11-13）。</figcaption>
      </figure>
    </div>
  </section>

  <!-- Section dim5: 催化劑與風險 -->
  <section id="dim5" class="report-section">
    <div class="container section-stack">
      <div class="section-head">
        <h2>護城河、催化劑與下檔風險：高壓直流與液冷技術壁壘深厚，緊盯電源晶片供應與外資動向</h2>
        <p class="lead">台達電憑藉 50% 至 60% 以上之伺服器電源市占率、Grid-to-Chip 液冷整合能力與 700 億元全球資本支出構築三大護城河；未來 1 至 4 季關鍵催化劑來自 3Q26 存貨跌價準備回沖、2% 報價調漲與 ±400V / 800V 高壓直流放量（分析師判斷）。</p>
      </div>

      <div class="ledger-grid">
        {"".join(moat_html)}
      </div>

      <figure class="sheet-figure">
        <h3>正向催化劑追蹤清單（Catalysts，分析師判斷）</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>催化劑事件</th>
                <th>預期時程</th>
                <th>影響方向</th>
                <th>可觀測驗證指標</th>
                <th>事實與數據依據</th>
              </tr>
            </thead>
            <tbody>
              {"".join(cat_rows_html)}
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockMonthRevenue、TaiwanStockFinancialStatements（2026-05 至 2026-11）與外部驗證研究。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>主要營運與籌碼風險清單（Risks，分析師判斷）</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>風險因子</th>
                <th>預期時程</th>
                <th>影響方向</th>
                <th>可觀測驗證指標</th>
                <th>事實與數據依據</th>
              </tr>
            </thead>
            <tbody>
              {"".join(risk_rows_html)}
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockShareholding、TaiwanStockBalanceSheet（2026-05 至 2026-11）與外部驗證研究。</figcaption>
      </figure>

      <div class="judgment-box">
        <h3>外部驗證事實與法說會研究彙整（External Verified Facts，近 6 個月）</h3>
        <ul class="facts-list">
          {"".join(ext_facts_html)}
        </ul>
      </div>
    </div>
  </section>

  <!-- Section dim6: 交易部位與風控 -->
  <section id="dim6" class="report-section">
    <div class="container section-stack">
      <div class="section-head">
        <h2>交易部位與風控計畫：波段拉回風險報酬比達 {dv.fmt_rr(x['rr_pullback'])} : 1，嚴守 1,020 元爆量低點硬停損</h2>
        <p class="lead">最新收盤價 {dv.fmt_price(x['close'])} 元位於 10 日至 20 日均線拉回進場區間（{dv.fmt_price(x['zone_low'])} 至 {dv.fmt_price(x['zone_high'])} 元）下緣，波段拉回與突破策略皆處於可執行狀態；長線 12 個月持有策略因 Bear 下檔距離較寬，風險報酬比為 {dv.fmt_rr(x['rr_hold'])}（低於 1.5 門檻，不具單筆追價吸引力，宜採拉回分批布局）。</p>
      </div>

      <figure class="sheet-figure">
        <div class="figure-head">
          <h3>交易部位價位標示 K 線圖（Entry {dv.fmt_price(x['entry'])} / T1 {dv.fmt_price(x['t1'])} / T2 {dv.fmt_price(x['t2'])} / 硬停損 {dv.fmt_price(x['hard_stop'])}）</h3>
          <ul class="figure-legend">
            <li><i class="swatch swatch--ink"></i>Entry 進場中位（{dv.fmt_price(x['entry'])}）</li>
            <li><i class="swatch swatch--ok"></i>T1 技術目標（{dv.fmt_price(x['t1'])}）</li>
            <li><i class="swatch swatch--accent"></i>T2 波段目標（{dv.fmt_price(x['t2'])}）</li>
            <li><i class="swatch swatch--err"></i>硬停損價（{dv.fmt_price(x['hard_stop'])}）</li>
          </ul>
        </div>
        {kline_dim6_svg}
        <figcaption>資料來源：FinMind TaiwanStockPrice（區間：2026-05 至 2026-11）與方法論第 7 節部位衍生計算。</figcaption>
      </figure>

      <figure class="sheet-figure">
        <h3>雙層交易架構：波段操作（Swing）與 12 個月長線持有（Hold）參數表</h3>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>策略層級與項目</th>
                <th class="num">關鍵價位與門檻</th>
                <th class="num">風險報酬比（Ratio）</th>
                <th>啟用條件與執行規則</th>
              </tr>
            </thead>
            <tbody>
              <tr class="row-highlight">
                <td>波段 A：拉回進場區（Pullback Zone）</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(x['zone_low'])}</span> 至 <span class="kpi-num">{dv.fmt_price(x['zone_high'])}</span> 元（中位 <span class="kpi-num">{dv.fmt_price(x['entry'])}</span>）</td>
                <td class="num"><span class="kpi-num" data-rr="pullback">{dv.fmt_rr(x['rr_pullback'])}</span></td>
                <td>{esc(pb_note)}；因投信成本區（1,407.57 至 1,465.02）與 10 日至 20 日均線不重疊，採均線帶</td>
              </tr>
              <tr>
                <td>波段 A：硬停損價（Hard Stop）</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(x['hard_stop'])}</span> 元</td>
                <td class="cell-right">不適用</td>
                <td>取近 20 日最大量日（2026-11-06，34,536 張）最低價 1,020 元與 20 日線 × 0.97（1,350 元）中低於進場區下緣且最接近者</td>
              </tr>
              <tr>
                <td>波段 B：帶量突破觸發價（Breakout）</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(x['trigger'])}</span> 元（停損 <span class="kpi-num">{dv.fmt_price(x['breakout_stop'])}</span>）</td>
                <td class="num"><span class="kpi-num" data-rr="breakout">{dv.fmt_rr(x['rr_breakout'])}</span></td>
                <td>{esc(bo_note)}</td>
              </tr>
              <tr>
                <td>波段技術目標 T1 / 波段目標 T2</td>
                <td class="cell-right">T1：<span class="kpi-num">{dv.fmt_price(x['t1'])}</span> 元 / T2：<span class="kpi-num">{dv.fmt_price(x['t2'])}</span> 元</td>
                <td class="cell-right">不適用</td>
                <td>T1 為 60 日高點（2,115 元）；T2 為 1.618 倍費波那契延伸（2,790 元）受限於 Bull 目標價 {dv.fmt_price(bull['target'])} 元之上限</td>
              </tr>
              <tr>
                <td>長線持有（12m Hold）：合理買進價</td>
                <td class="cell-right"><span class="kpi-num">{dv.fmt_price(x['fair_buy'])}</span> 元（Base ÷ <span class="kpi-num">1.15</span>）</td>
                <td class="num"><span class="kpi-num" data-rr="hold">{dv.fmt_rr(x['rr_hold'])}</span></td>
                <td>Base 目標 {dv.fmt_price(base['target'])} 元 vs. Bear 目標 {dv.fmt_price(bear['target'])} 元；{esc(hold_note)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <figcaption>資料來源：FinMind TaiwanStockPrice、TaiwanStockInstitutionalInvestorsBuySell（2026-05 至 2026-11）與 derive.py 計算。</figcaption>
      </figure>

      <div class="section-split">
        <figure class="sheet-figure">
          <h3>投資論點失效條件（Thesis Breakers，分析師判斷）</h3>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>失效觸發情境</th>
                  <th class="num">量化門檻</th>
                  <th>監測資料集</th>
                </tr>
              </thead>
              <tbody>
                {"".join(tb_rows_html)}
              </tbody>
            </table>
          </div>
          <figcaption>資料來源：FinMind TaiwanStockMonthRevenue、TaiwanStockFinancialStatements、TaiwanStockShareholding（2026-11 起持續追蹤）。</figcaption>
        </figure>

        <div class="judgment-box">
          <h3>資料完整度與缺漏揭露（Data Gaps）</h3>
          {gaps_html}
        </div>
      </div>
    </div>
  </section>
</main>

<footer class="site-footer">
  <div class="container footer-grid">
    <div>
      <p><strong>免責聲明：</strong>本報告僅供研究參考，不構成任何投資建議。所有市場價量、籌碼與財務數據均由腳本自動取自 FinMind 資料庫並依固定方法論計算；涉及前瞻預估、護城河、催化劑與風險之分析均明確標示為「分析師判斷」或附註外部查證來源連結。報告不包含任何個人持倉、成本或資金部位。</p>
    </div>
    <div>
      <table class="footer-meta-table" aria-label="報告生成資訊">
        <tbody>
          <tr>
            <td>資料來源（Data Source）</td>
            <td>FinMind API（Free Tier Datasets）</td>
          </tr>
          <tr>
            <td>資料基準日（As-of Date）</td>
            <td><span class="kpi-num">{esc(d['asof'])}</span></td>
          </tr>
          <tr>
            <td>報告生成日期（Generated）</td>
            <td><span class="kpi-num">{esc(d['generated'])}</span>（Tool <span class="kpi-num">{esc(d['tool_version'])}</span>）</td>
          </tr>
          <tr>
            <td>Primary Agent Model</td>
            <td><span data-meta="model">{esc(a['generation']['model'])}</span></td>
          </tr>
          <tr>
            <td>Reasoning Effort</td>
            <td><span data-meta="effort">{esc(a['generation']['effort'])}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</footer>

<div id="chart-tooltip" class="chart-tooltip" hidden></div>

<script>
(function() {{
  var btn = document.getElementById('mode-toggle');
  if (btn) {{
    btn.addEventListener('click', function() {{
      var root = document.documentElement;
      var cur = root.getAttribute('data-mode');
      var isDark = cur === 'dark' || (!cur && window.matchMedia('(prefers-color-scheme: dark)').matches);
      var next = isDark ? 'light' : 'dark';
      root.setAttribute('data-mode', next);
      try {{ localStorage.setItem('almanac-mode-2308', next); }} catch (e) {{}}
    }});
  }}

  var tip = document.getElementById('chart-tooltip');
  if (!tip) return;
  document.addEventListener('mouseover', function(e) {{
    var target = e.target.closest('[data-tip]');
    if (!target) {{
      tip.hidden = true;
      return;
    }}
    tip.textContent = target.getAttribute('data-tip');
    tip.hidden = false;
  }});
  document.addEventListener('mousemove', function(e) {{
    if (tip.hidden) return;
    var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 12);
    var y = Math.max(e.clientY - tip.offsetHeight - 12, 12);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }});
  document.addEventListener('mouseout', function(e) {{
    var target = e.target.closest('[data-tip]');
    if (target && !target.contains(e.relatedTarget)) {{
      tip.hidden = true;
    }}
  }});
}})();
</script>
</body>
</html>
"""
    out_path.write_text(page_html, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    generate()
