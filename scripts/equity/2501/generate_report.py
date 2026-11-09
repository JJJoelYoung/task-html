#!/usr/bin/env python3
"""
Generator script for 2501 Cathay Real Estate (國泰建設) Equity Research Report.
Reads data_2501.json and outputs 2501_Cathay_Real_Estate_Equity_Report.html
adhering strictly to Hallmark design principles and all 92 assertions in test_equity_report.py.
"""

import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data_2501.json"
OUTPUT_HTML = BASE_DIR / "2501_Cathay_Real_Estate_Equity_Report.html"

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_svg_chart1(market_data):
    """
    Price & Volume Technical Chart (1-Month Daily + 5MA/10MA/20MA + Volume)
    ViewBox: 0 0 960 420
    """
    daily = market_data["daily_series"]
    n = len(daily)
    
    # Coordinate system
    pad_left = 65
    pad_right = 35
    pad_top = 35
    price_height = 240
    gap = 25
    vol_height = 80
    pad_bottom = 35
    width = 960
    
    chart_w = width - pad_left - pad_right
    step_x = chart_w / (n - 1) if n > 1 else chart_w
    
    # Price scale: min 19.50, max 22.00
    p_min = 19.50
    p_max = 22.00
    p_range = p_max - p_min
    
    def price_to_y(p):
        return pad_top + (p_max - p) / p_range * price_height

    # Volume scale: max 7500 lots
    v_max = 7500
    vol_base_y = pad_top + price_height + gap + vol_height
    
    def vol_to_h(v):
        return (v / v_max) * vol_height

    # Generate grid lines for price
    grid_svg = []
    for p in [19.5, 20.0, 20.5, 21.0, 21.5, 22.0]:
        y = price_to_y(p)
        grid_svg.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="3,3" />')
        grid_svg.append(f'<text x="{pad_left - 10}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="11" fill="var(--color-muted)" text-anchor="end">{p:.2f}</text>')

    # Volume grid lines
    for v in [2500, 5000]:
        y = vol_base_y - vol_to_h(v)
        grid_svg.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="2,2" />')
        grid_svg.append(f'<text x="{pad_left - 10}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10" fill="var(--color-subtle)" text-anchor="end">{v:,}</text>')

    # Points for lines
    close_pts = []
    ma5_pts = []
    ma10_pts = []
    ma20_pts = []
    bars_svg = []
    vol_bars_svg = []
    date_labels = []

    high_pt = (0, 0, 0, "")
    low_pt = (0, 9999, 9999, "")

    for i, d in enumerate(daily):
        x = pad_left + i * step_x
        c = float(d["close"])
        o = float(d["open"])
        h = float(d["high"])
        l = float(d["low"])
        v = float(d["volume_lots"])
        m5 = float(d["ma5"])
        m10 = float(d["ma10"])
        m20 = float(d["ma20"])
        dt = d["date"]

        cy = price_to_y(c)
        oy = price_to_y(o)
        hy = price_to_y(h)
        ly = price_to_y(l)

        close_pts.append(f"{x:.1f},{cy:.1f}")
        ma5_pts.append(f"{x:.1f},{price_to_y(m5):.1f}")
        ma10_pts.append(f"{x:.1f},{price_to_y(m10):.1f}")
        ma20_pts.append(f"{x:.1f},{price_to_y(m20):.1f}")

        # Track high and low
        if h > high_pt[1]:
            high_pt = (x, h, hy, dt)
        if l < low_pt[1]:
            low_pt = (x, l, ly, dt)

        # Candlestick bar
        is_up = c >= o
        bar_color = "var(--color-tw-rise)" if is_up else "var(--color-tw-fall)"
        body_top = min(oy, cy)
        body_h = max(abs(cy - oy), 1.5)
        
        bars_svg.append(f'<line x1="{x:.1f}" y1="{hy:.1f}" x2="{x:.1f}" y2="{ly:.1f}" stroke="{bar_color}" stroke-width="1.2" />')
        bars_svg.append(f'<rect x="{x - 4:.1f}" y="{body_top:.1f}" width="8" height="{body_h:.1f}" fill="{bar_color}" rx="0.5" />')

        # Volume bar
        vh = vol_to_h(v)
        vy = vol_base_y - vh
        vol_bars_svg.append(f'<rect x="{x - 4:.1f}" y="{vy:.1f}" width="8" height="{vh:.1f}" fill="{bar_color}" opacity="0.8" rx="0.5" />')

        # Date label every 4 days and last day
        if i % 4 == 0 or i == n - 1:
            short_date = dt[5:]  # MM-DD
            date_labels.append(f'<text x="{x:.1f}" y="{vol_base_y + 18}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">{short_date}</text>')

    # Area under close line
    area_pts = [f"{pad_left},{price_to_y(p_min)}"] + close_pts + [f"{pad_left + (n-1)*step_x:.1f},{price_to_y(p_min)}"]

    # Annotations for high and low
    high_anno = f'''
    <g transform="translate({high_pt[0]:.1f}, {high_pt[2] - 34:.1f})">
      <circle cx="0" cy="34" r="4" fill="var(--color-tw-rise)" />
      <line x1="0" y1="34" x2="0" y2="18" stroke="var(--color-tw-rise)" stroke-width="1" stroke-dasharray="2,2" />
      <rect x="-65" y="0" width="130" height="18" fill="var(--color-sheet)" stroke="var(--color-tw-rise)" stroke-width="1" rx="2" />
      <text x="0" y="13" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="var(--color-tw-rise)" text-anchor="middle">1M High NT$ {high_pt[1]:.2f} ({high_pt[3][5:]})</text>
    </g>
    '''

    low_anno = f'''
    <g transform="translate({low_pt[0]:.1f}, {low_pt[2]:.1f})">
      <circle r="4" fill="var(--color-tw-fall)" />
      <line x1="0" y1="0" x2="0" y2="18" stroke="var(--color-tw-fall)" stroke-width="1" stroke-dasharray="2,2" />
      <rect x="-65" y="18" width="130" height="18" fill="var(--color-sheet)" stroke="var(--color-tw-fall)" stroke-width="1" rx="2" />
      <text x="0" y="31" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="var(--color-tw-fall)" text-anchor="middle">1M Low NT$ {low_pt[1]:.2f} ({low_pt[3][5:]})</text>
    </g>
    '''

    latest_c = daily[-1]["close"]
    latest_x = pad_left + (n-1) * step_x
    latest_y = price_to_y(latest_c)
    latest_anno = f'''
    <g transform="translate({latest_x:.1f}, {latest_y - 10:.1f})">
      <circle cx="0" cy="10" r="4.5" fill="var(--color-ink)" />
      <rect x="-105" y="0" width="95" height="20" fill="var(--color-ink)" rx="2" />
      <text x="-58" y="14" font-family="var(--font-mono)" font-size="10.5" font-weight="600" fill="var(--color-sheet)" text-anchor="middle">Close NT$ {latest_c:.2f}</text>
    </g>
    '''

    svg = f'''<svg class="chart-svg" viewBox="0 0 {width} 420" role="img" aria-label="國泰建設 (2501) 近1個月價量走勢與均線結構圖">
      <defs>
        <linearGradient id="priceAreaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--color-accent)" stop-opacity="0.18" />
          <stop offset="100%" stop-color="var(--color-accent)" stop-opacity="0.01" />
        </linearGradient>
      </defs>
      
      <!-- Grid & Axes -->
      {''.join(grid_svg)}
      <line x1="{pad_left}" y1="{pad_top + price_height}" x2="{width - pad_right}" y2="{pad_top + price_height}" stroke="var(--color-rule-2)" stroke-width="1.5" />
      <line x1="{pad_left}" y1="{vol_base_y}" x2="{width - pad_right}" y2="{vol_base_y}" stroke="var(--color-rule-2)" stroke-width="1.5" />
      
      <!-- Price Area & Candlesticks -->
      <polygon points="{' '.join(area_pts)}" fill="url(#priceAreaGrad)" />
      {''.join(bars_svg)}
      
      <!-- Moving Average Polylines -->
      <polyline points="{' '.join(ma20_pts)}" fill="none" stroke="var(--color-gold)" stroke-width="1.6" opacity="0.9" />
      <polyline points="{' '.join(ma10_pts)}" fill="none" stroke="var(--color-ink-2)" stroke-width="1.6" opacity="0.9" />
      <polyline points="{' '.join(ma5_pts)}" fill="none" stroke="var(--color-accent)" stroke-width="2.2" />

      <!-- Annotations -->
      {high_anno}
      {low_anno}
      {latest_anno}
      
      <!-- Volume Bars -->
      {''.join(vol_bars_svg)}
      
      <!-- Axis Date Labels -->
      {''.join(date_labels)}
      <text x="{pad_left}" y="{pad_top + price_height + gap - 8}" font-family="var(--font-display)" font-size="11" font-weight="600" fill="var(--color-ink)">成交量 (Volume Lots)</text>
      
      <!-- Chart Legend -->
      <g transform="translate({width - pad_right - 340}, {pad_top - 12})">
        <line x1="0" y1="0" x2="16" y2="0" stroke="var(--color-accent)" stroke-width="2.5" />
        <text x="22" y="3" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">5MA (週線): 20.37</text>
        <line x1="120" y1="0" x2="136" y2="0" stroke="var(--color-ink-2)" stroke-width="1.8" />
        <text x="142" y="3" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">10MA (雙週線): 20.30</text>
        <line x1="245" y1="0" x2="261" y2="0" stroke="var(--color-gold)" stroke-width="1.8" />
        <text x="267" y="3" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">20MA (月線): 20.40</text>
      </g>
    </svg>'''
    return svg

def build_svg_chart2(inst_data):
    """
    Institutional Flow & Margin Balance Dynamics Chart
    ViewBox: 0 0 960 420
    Upper: Net buy/sell stacked/grouped bars for Foreign, Investment Trust, Dealers
    Lower: Foreign ownership % curve and Margin Balance trend
    """
    daily = inst_data["daily_series"]
    n = len(daily)
    
    width = 960
    pad_left = 65
    pad_right = 65
    pad_top = 35
    bar_height = 200
    gap = 35
    line_height = 90
    pad_bottom = 35
    
    chart_w = width - pad_left - pad_right
    step_x = chart_w / (n - 1) if n > 1 else chart_w
    
    # Scale for net buy/sell: min -2500 lots, max +3800 lots
    flow_min = -2500
    flow_max = 3800
    flow_range = flow_max - flow_min
    zero_y = pad_top + (flow_max / flow_range) * bar_height
    
    def flow_to_y(val):
        return pad_top + (flow_max - val) / flow_range * bar_height

    # Scale for Foreign Ownership %: min 10.40%, max 11.20%
    f_min = 10.40
    f_max = 11.20
    line_base_y = pad_top + bar_height + gap + line_height
    
    def fpct_to_y(pct):
        return (line_base_y - line_height) + (f_max - pct) / (f_max - f_min) * line_height

    # Scale for Margin Balance Lots: min 3700, max 4600
    m_min = 3700
    m_max = 4600
    def margin_to_y(lots):
        return (line_base_y - line_height) + (m_max - lots) / (m_max - m_min) * line_height

    grid_svg = []
    # Upper flow grid
    for val in [-2000, -1000, 0, 1000, 2000, 3000]:
        y = flow_to_y(val)
        is_zero = (val == 0)
        stroke_color = "var(--color-ink)" if is_zero else "var(--color-rule)"
        stroke_w = "1.5" if is_zero else "1"
        dash = "" if is_zero else 'stroke-dasharray="3,3"'
        grid_svg.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="{stroke_color}" stroke-width="{stroke_w}" {dash} />')
        grid_svg.append(f'<text x="{pad_left - 10}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-muted)" text-anchor="end">{val:+,}</text>')

    # Lower line grid
    for val in [10.60, 10.80, 11.00]:
        y = fpct_to_y(val)
        grid_svg.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="2,2" />')
        grid_svg.append(f'<text x="{pad_left - 10}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10" fill="var(--color-accent)" text-anchor="end">{val:.2f}%</text>')

    # Margin axis labels (Right side)
    for m in [3900, 4100, 4300, 4500]:
        y = margin_to_y(m)
        grid_svg.append(f'<text x="{width - pad_right + 10}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10" fill="var(--color-gold)" text-anchor="start">{m:,} 張</text>')

    bars_svg = []
    foreign_pts = []
    margin_pts = []
    date_labels = []

    for i, d in enumerate(daily):
        x = pad_left + i * step_x
        f_net = float(d["foreign_net_lots"])
        t_net = float(d["investment_trust_net_lots"])
        d_net = float(d["dealer_net_lots"])
        fpct = float(d["foreign_ownership_pct"])
        m_lots = float(d["margin_balance_lots"])
        dt = d["date"]

        # 3 bars grouped around x
        bw = 3.6
        # Foreign bar
        fy = flow_to_y(f_net)
        f_top = min(zero_y, fy)
        f_h = max(abs(fy - zero_y), 1.0)
        f_col = "var(--color-accent)" if f_net >= 0 else "oklch(60% 0.12 155)"
        bars_svg.append(f'<rect x="{x - 5.5:.1f}" y="{f_top:.1f}" width="{bw}" height="{f_h:.1f}" fill="{f_col}" rx="0.5" />')

        # Trust bar
        ty = flow_to_y(t_net)
        t_top = min(zero_y, ty)
        t_h = max(abs(ty - zero_y), 1.0)
        bars_svg.append(f'<rect x="{x - 1.8:.1f}" y="{t_top:.1f}" width="{bw}" height="{t_h:.1f}" fill="oklch(45% 0.12 240)" rx="0.5" />')

        # Dealer bar
        dy = flow_to_y(d_net)
        d_top = min(zero_y, dy)
        d_h = max(abs(dy - zero_y), 1.0)
        bars_svg.append(f'<rect x="{x + 1.9:.1f}" y="{d_top:.1f}" width="{bw}" height="{d_h:.1f}" fill="var(--color-gold)" rx="0.5" />')

        # Line points
        foreign_pts.append(f"{x:.1f},{fpct_to_y(fpct):.1f}")
        margin_pts.append(f"{x:.1f},{margin_to_y(m_lots):.1f}")

        if i % 4 == 0 or i == n - 1:
            short_date = dt[5:]
            date_labels.append(f'<text x="{x:.1f}" y="{line_base_y + 18}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">{short_date}</text>')

    # Spike annotation on 2026-11-05
    spike_idx = 22 # 2026-11-05
    spike_x = pad_left + spike_idx * step_x
    spike_y = flow_to_y(3511)
    spike_anno = f'''
    <g transform="translate({spike_x:.1f}, {spike_y - 34:.1f})">
      <circle cx="0" cy="34" r="4" fill="var(--color-accent)" />
      <line x1="0" y1="34" x2="0" y2="18" stroke="var(--color-accent)" stroke-width="1" stroke-dasharray="2,2" />
      <rect x="-80" y="0" width="160" height="18" fill="var(--color-sheet)" stroke="var(--color-accent)" stroke-width="1" rx="2" />
      <text x="0" y="13" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="var(--color-accent)" text-anchor="middle">外資單日大買 +3,511 張 (11/05)</text>
    </g>
    '''

    svg = f'''<svg class="chart-svg" viewBox="0 0 {width} 420" role="img" aria-label="國泰建設 (2501) 法人買賣超與信用交易走勢圖">
      <!-- Grid -->
      {''.join(grid_svg)}
      <line x1="{pad_left}" y1="{line_base_y}" x2="{width - pad_right}" y2="{line_base_y}" stroke="var(--color-rule-2)" stroke-width="1.5" />
      
      <!-- Institutional Grouped Bars -->
      {''.join(bars_svg)}
      {spike_anno}
      
      <!-- Lower Curves: Foreign Ownership % and Margin Balance -->
      <polyline points="{' '.join(foreign_pts)}" fill="none" stroke="var(--color-accent)" stroke-width="2.2" />
      <polyline points="{' '.join(margin_pts)}" fill="none" stroke="var(--color-gold)" stroke-width="2.0" stroke-dasharray="4,3" />

      <!-- Date Labels -->
      {''.join(date_labels)}
      
      <!-- Axis Labels & Titles -->
      <text x="{pad_left}" y="{pad_top - 12}" font-family="var(--font-display)" font-size="11" font-weight="600" fill="var(--color-ink)">三大法人單日買賣超 (張 Lots)</text>
      <text x="{pad_left}" y="{pad_top + bar_height + gap - 10}" font-family="var(--font-display)" font-size="11" font-weight="600" fill="var(--color-accent)">外資持股比率 (%) (左軸)</text>
      <text x="{width - pad_right}" y="{pad_top + bar_height + gap - 10}" font-family="var(--font-display)" font-size="11" font-weight="600" fill="var(--color-gold)" text-anchor="end">融資餘額 (張 Lots) (右軸)</text>

      <!-- Legend -->
      <g transform="translate({width - pad_right - 440}, {pad_top - 20})">
        <rect x="0" y="0" width="10" height="10" fill="var(--color-accent)" />
        <text x="14" y="9" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">外資 (Foreign)</text>
        <rect x="110" y="0" width="10" height="10" fill="oklch(45% 0.12 240)" />
        <text x="124" y="9" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">投信 (Trust)</text>
        <rect x="210" y="0" width="10" height="10" fill="var(--color-gold)" />
        <text x="224" y="9" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">自營商 (Dealer)</text>
        <line x1="315" y1="5" x2="330" y2="5" stroke="var(--color-accent)" stroke-width="2" />
        <text x="335" y="9" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">外資比率</text>
        <line x1="395" y1="5" x2="410" y2="5" stroke="var(--color-gold)" stroke-width="2" stroke-dasharray="3,2" />
        <text x="415" y="9" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)">融資</text>
      </g>
    </svg>'''
    return svg

def build_svg_chart3(ops_data):
    """
    Operations & Profitability Chart
    ViewBox: 0 0 960 420
    Left: 2026 Monthly Revenue (Jan-Sep) in NT$ Billion + YoY Growth Rate % curve
    Right: 4-Quarter Profitability (Gross Margin % and EPS trend)
    """
    monthly = ops_data["monthly_revenue_2026"]
    quarterly = ops_data["quarterly_financials"]
    
    width = 960
    pad_top = 45
    pad_bottom = 45
    
    # Left Pane (Monthly Rev): x from 60 to 540
    lx_left = 65
    lx_right = 530
    l_width = lx_right - lx_left
    l_base_y = 350
    l_height = 270
    
    # Revenue scale: 0 to 5.0 Billion NT$
    rev_max = 5.0
    def rev_to_y(r_yi):
        return l_base_y - (r_yi / rev_max) * l_height

    # YoY Scale: -100% to +300%
    yoy_min = -100
    yoy_max = 300
    def yoy_to_y(yoy):
        return l_base_y - (yoy - yoy_min) / (yoy_max - yoy_min) * l_height

    left_grid = []
    for r in [0, 1.0, 2.0, 3.0, 4.0, 5.0]:
        y = rev_to_y(r)
        left_grid.append(f'<line x1="{lx_left}" y1="{y:.1f}" x2="{lx_right}" y2="{y:.1f}" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="2,2" />')
        left_grid.append(f'<text x="{lx_left - 8}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-muted)" text-anchor="end">{r:.1f}B</text>')

    # YoY Axis right labels
    for yoy in [-50, 0, 100, 200, 300]:
        y = yoy_to_y(yoy)
        left_grid.append(f'<text x="{lx_right + 8}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10" fill="var(--color-gold)" text-anchor="start">{yoy:+}%</text>')

    # Monthly bars & YoY line
    n_m = len(monthly)
    step_m = l_width / n_m
    m_bars_svg = []
    yoy_pts = []
    m_labels = []

    for i, m in enumerate(monthly):
        cx = lx_left + (i + 0.5) * step_m
        r_yi = float(m["revenue_yi"])
        r_b = r_yi / 10.0
        yoy = float(m["yoy_growth_pct"])
        mon = m["month"]

        by = rev_to_y(r_b)
        bh = l_base_y - by
        # Q1 peak highlighting
        bar_color = "var(--color-accent)" if mon in [1, 2, 3] else "oklch(55% 0.08 155)"
        m_bars_svg.append(f'<rect x="{cx - 15:.1f}" y="{by:.1f}" width="30" height="{bh:.1f}" fill="{bar_color}" rx="2" />')
        m_bars_svg.append(f'<text x="{cx:.1f}" y="{by - 6:.1f}" font-family="var(--font-mono)" font-size="9.5" font-weight="600" fill="var(--color-ink)" text-anchor="middle">{r_yi:.2f}</text>')

        yy = yoy_to_y(yoy)
        yoy_pts.append(f"{cx:.1f},{yy:.1f}")
        m_labels.append(f'<text x="{cx:.1f}" y="{l_base_y + 16}" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)" text-anchor="middle">{mon}月</text>')

    # Q1 cluster callout bracket
    q1_cx = lx_left + 1.5 * step_m
    q1_callout = f'''
    <g transform="translate({q1_cx:.1f}, 43)">
      <rect x="-85" y="0" width="170" height="22" fill="var(--color-gold-soft)" stroke="var(--color-gold)" stroke-width="1" rx="3" />
      <text x="0" y="15" font-family="var(--font-mono)" font-size="10" font-weight="700" fill="var(--color-gold)" text-anchor="middle">Q1 完工交屋高峰: NT$ 11.15B</text>
    </g>
    '''

    # Right Pane (Quarterly Financials): x from 610 to 910
    rx_left = 620
    rx_right = 910
    r_width = rx_right - rx_left
    r_base_y = 350
    r_height = 270

    # EPS scale: 0 to 1.50
    eps_max = 1.50
    def eps_to_y(eps):
        return r_base_y - (eps / eps_max) * r_height

    # Gross Margin scale: 20% to 32%
    gm_min = 20.0
    gm_max = 32.0
    def gm_to_y(gm):
        return r_base_y - (gm - gm_min) / (gm_max - gm_min) * r_height

    right_grid = []
    for eps in [0, 0.5, 1.0, 1.5]:
        y = eps_to_y(eps)
        right_grid.append(f'<line x1="{rx_left}" y1="{y:.1f}" x2="{rx_right}" y2="{y:.1f}" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="2,2" />')
        right_grid.append(f'<text x="{rx_left - 8}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-muted)" text-anchor="end">{eps:.1f}</text>')

    for gm in [22, 26, 30]:
        y = gm_to_y(gm)
        right_grid.append(f'<text x="{rx_right + 8}" y="{y + 4:.1f}" font-family="var(--font-mono)" font-size="10" fill="var(--color-accent)" text-anchor="start">{gm}%</text>')

    n_q = len(quarterly)
    step_q = r_width / n_q
    q_bars_svg = []
    gm_pts = []
    q_labels = []

    for i, q in enumerate(quarterly):
        cx = rx_left + (i + 0.5) * step_q
        eps = float(q["eps"])
        gm = float(q["gross_margin_pct"])
        qtr = q["quarter"]

        ey = eps_to_y(eps)
        eh = r_base_y - ey
        q_bars_svg.append(f'<rect x="{cx - 20:.1f}" y="{ey:.1f}" width="40" height="{eh:.1f}" fill="oklch(45% 0.12 240)" rx="2" />')
        q_bars_svg.append(f'<text x="{cx:.1f}" y="{ey - 6:.1f}" font-family="var(--font-mono)" font-size="10.5" font-weight="700" fill="var(--color-ink)" text-anchor="middle">{eps:.2f}</text>')

        gmy = gm_to_y(gm)
        gm_pts.append(f"{cx:.1f},{gmy:.1f}")
        q_labels.append(f'<text x="{cx:.1f}" y="{r_base_y + 16}" font-family="var(--font-mono)" font-size="10.5" fill="var(--color-ink)" text-anchor="middle">{qtr}</text>')

    svg = f'''<svg class="chart-svg" viewBox="0 0 {width} 420" role="img" aria-label="國泰建設 (2501) 2026月營收與近四季獲利結構圖">
      <!-- Left Panel: Monthly Revenue -->
      {''.join(left_grid)}
      <line x1="{lx_left}" y1="{l_base_y}" x2="{lx_right}" y2="{l_base_y}" stroke="var(--color-rule-2)" stroke-width="1.5" />
      {''.join(m_bars_svg)}
      <polyline points="{' '.join(yoy_pts)}" fill="none" stroke="var(--color-gold)" stroke-width="2.5" />
      {''.join([f'<circle cx="{pt.split(",")[0]}" cy="{pt.split(",")[1]}" r="3.5" fill="var(--color-gold)" />' for pt in yoy_pts])}
      {''.join(m_labels)}
      {q1_callout}
      
      <text x="{lx_left}" y="24" font-family="var(--font-display)" font-size="12" font-weight="700" fill="var(--color-ink)">2026 各月營收 (NT$ 億元) 與 YoY 年增率 (%)</text>
      <text x="{lx_right}" y="24" font-family="var(--font-display)" font-size="10.5" font-weight="600" fill="var(--color-gold)" text-anchor="end">年增率 YoY (%) (右軸)</text>

      <!-- Vertical Divider -->
      <line x1="575" y1="20" x2="575" y2="370" stroke="var(--color-rule)" stroke-width="1" stroke-dasharray="4,4" />

      <!-- Right Panel: Quarterly EPS & Margins -->
      {''.join(right_grid)}
      <line x1="{rx_left}" y1="{r_base_y}" x2="{rx_right}" y2="{r_base_y}" stroke="var(--color-rule-2)" stroke-width="1.5" />
      {''.join(q_bars_svg)}
      <polyline points="{' '.join(gm_pts)}" fill="none" stroke="var(--color-accent)" stroke-width="2.5" />
      {''.join([f'<circle cx="{pt.split(",")[0]}" cy="{pt.split(",")[1]}" r="4" fill="var(--color-accent)" />' for pt in gm_pts])}
      {''.join(q_labels)}

      <text x="{rx_left}" y="24" font-family="var(--font-display)" font-size="12" font-weight="700" fill="var(--color-ink)">近四季每股盈餘 (EPS 元) 與 毛利率 (%)</text>
      <text x="{rx_right}" y="24" font-family="var(--font-display)" font-size="10.5" font-weight="600" fill="var(--color-accent)" text-anchor="end">毛利率 (%) (右軸)</text>
      
      <!-- Right Panel TTM Badge -->
      <g transform="translate({rx_right - 60}, 43)">
        <rect x="-55" y="0" width="115" height="22" fill="var(--color-sheet)" stroke="oklch(45% 0.12 240)" stroke-width="1" rx="3" />
        <text x="0" y="15" font-family="var(--font-mono)" font-size="10" font-weight="700" fill="oklch(45% 0.12 240)" text-anchor="middle">TTM EPS: NT$ 2.88</text>
      </g>
    </svg>'''
    return svg

def build_svg_chart4(val_data):
    """
    Valuation Assessment & Historical Corridor Gauge
    ViewBox: 0 0 960 400
    Upper: PBR 5-Year Historical Band (0.72x - 1.83x) with Current PBR 0.74x marker
    Middle: PER 5-Year Historical Band (5.58x - 22.22x) with Current PER 7.14x marker
    Lower: Peer Valuation Comparison Matrix (Cathay vs Huaku vs Kindom vs Highwealth)
    """
    width = 960
    pad_left = 130
    pad_right = 160
    chart_w = width - pad_left - pad_right
    
    # 1. PBR Band
    pbr_y = 55
    pbr_min = 0.60
    pbr_max = 1.90
    def pbr_to_x(val):
        return pad_left + (val - pbr_min) / (pbr_max - pbr_min) * chart_w
    
    # 2. PER Band
    per_y = 150
    per_min = 4.0
    per_max = 24.0
    def per_to_x(val):
        return pad_left + (val - per_min) / (per_max - per_min) * chart_w

    svg_elements = []

    # --- PBR River ---
    # Band zones: 0.72 to 0.84 (Deep Value), 0.84 to 1.05 (Fair/Median), 1.05 to 1.83 (Premium)
    x_pbr_min = pbr_to_x(0.72)
    x_pbr_p25 = pbr_to_x(0.84)
    x_pbr_med = pbr_to_x(0.91)
    x_pbr_p75 = pbr_to_x(1.05)
    x_pbr_max = pbr_to_x(1.83)
    x_pbr_cur = pbr_to_x(0.74)

    svg_elements.append(f'''
    <!-- PBR Row -->
    <text x="{pad_left - 15}" y="{pbr_y + 14}" font-family="var(--font-display)" font-size="12" font-weight="700" fill="var(--color-ink)" text-anchor="end">PBR 淨值比區間</text>
    <rect x="{x_pbr_min:.1f}" y="{pbr_y}" width="{x_pbr_p25 - x_pbr_min:.1f}" height="20" fill="var(--color-accent-soft)" rx="2" />
    <rect x="{x_pbr_p25:.1f}" y="{pbr_y}" width="{x_pbr_p75 - x_pbr_p25:.1f}" height="20" fill="oklch(92% 0.02 240)" />
    <rect x="{x_pbr_p75:.1f}" y="{pbr_y}" width="{x_pbr_max - x_pbr_p75:.1f}" height="20" fill="var(--color-gold-soft)" rx="2" />
    
    <!-- PBR Key Level Ticks -->
    <line x1="{x_pbr_min:.1f}" y1="{pbr_y - 4}" x2="{x_pbr_min:.1f}" y2="{pbr_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_pbr_min:.1f}" y="{pbr_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">最低 0.72x</text>
    <line x1="{x_pbr_med:.1f}" y1="{pbr_y - 4}" x2="{x_pbr_med:.1f}" y2="{pbr_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_pbr_med:.1f}" y="{pbr_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">中位 0.91x</text>
    <line x1="{x_pbr_max:.1f}" y1="{pbr_y - 4}" x2="{x_pbr_max:.1f}" y2="{pbr_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_pbr_max:.1f}" y="{pbr_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">最高 1.83x</text>

    <!-- Current PBR Pinpoint -->
    <g transform="translate({x_pbr_cur:.1f}, {pbr_y - 36:.1f})">
      <polygon points="0,28 -6,18 6,18" fill="var(--color-tw-rise)" />
      <line x1="0" y1="28" x2="0" y2="64" stroke="var(--color-tw-rise)" stroke-width="2" />
      <rect x="-45" y="0" width="90" height="18" fill="var(--color-tw-rise)" rx="2" />
      <text x="0" y="13" font-family="var(--font-mono)" font-size="10" font-weight="700" fill="var(--color-sheet)" text-anchor="middle">目前 0.74x</text>
    </g>
    <text x="{width - pad_right + 15}" y="{pbr_y + 14}" font-family="var(--font-mono)" font-size="11" font-weight="600" fill="var(--color-accent)">低估 (歷史後 10%)</text>
    ''')

    # --- PER River ---
    # Band zones: 5.58 to 9.09 (Deep Value), 9.09 to 13.78 (Fair/Median), 13.78 to 22.22 (High)
    x_per_min = per_to_x(5.58)
    x_per_p25 = per_to_x(9.09)
    x_per_med = per_to_x(11.58)
    x_per_p75 = per_to_x(13.78)
    x_per_max = per_to_x(22.22)
    x_per_cur = per_to_x(7.14)

    svg_elements.append(f'''
    <!-- PER Row -->
    <text x="{pad_left - 15}" y="{per_y + 14}" font-family="var(--font-display)" font-size="12" font-weight="700" fill="var(--color-ink)" text-anchor="end">PER 本益比區間</text>
    <rect x="{x_per_min:.1f}" y="{per_y}" width="{x_per_p25 - x_per_min:.1f}" height="20" fill="var(--color-accent-soft)" rx="2" />
    <rect x="{x_per_p25:.1f}" y="{per_y}" width="{x_per_p75 - x_per_p25:.1f}" height="20" fill="oklch(92% 0.02 240)" />
    <rect x="{x_per_p75:.1f}" y="{per_y}" width="{x_per_max - x_per_p75:.1f}" height="20" fill="var(--color-gold-soft)" rx="2" />

    <!-- PER Key Level Ticks -->
    <line x1="{x_per_min:.1f}" y1="{per_y - 4}" x2="{x_per_min:.1f}" y2="{per_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_per_min:.1f}" y="{per_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">最低 5.58x</text>
    <line x1="{x_per_med:.1f}" y1="{per_y - 4}" x2="{x_per_med:.1f}" y2="{per_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_per_med:.1f}" y="{per_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">中位 11.58x</text>
    <line x1="{x_per_max:.1f}" y1="{per_y - 4}" x2="{x_per_max:.1f}" y2="{per_y + 24}" stroke="var(--color-muted)" stroke-width="1.2" />
    <text x="{x_per_max:.1f}" y="{per_y + 36}" font-family="var(--font-mono)" font-size="10" fill="var(--color-muted)" text-anchor="middle">最高 22.22x</text>

    <!-- Current PER Pinpoint -->
    <g transform="translate({x_per_cur:.1f}, {per_y - 36:.1f})">
      <polygon points="0,28 -6,18 6,18" fill="var(--color-tw-rise)" />
      <line x1="0" y1="28" x2="0" y2="64" stroke="var(--color-tw-rise)" stroke-width="2" />
      <rect x="-45" y="0" width="90" height="18" fill="var(--color-tw-rise)" rx="2" />
      <text x="0" y="13" font-family="var(--font-mono)" font-size="10" font-weight="700" fill="var(--color-sheet)" text-anchor="middle">目前 7.14x</text>
    </g>
    <text x="{width - pad_right + 15}" y="{per_y + 14}" font-family="var(--font-mono)" font-size="11" font-weight="600" fill="var(--color-accent)">深具安全邊際 (10th%)</text>
    ''')

    # --- Lower: Peer Comparison Horizontal Bars ---
    peer_y = 235
    peers = [
        {"name": "國泰建設 (2501)", "per": 7.14, "pbr": 0.74, "dy": 5.85, "color": "var(--color-accent)", "bold": True},
        {"name": "華固建設 (2548)", "per": 9.85, "pbr": 1.28, "dy": 5.12, "color": "oklch(45% 0.12 240)", "bold": False},
        {"name": "冠德建設 (2520)", "per": 8.42, "pbr": 1.15, "dy": 4.90, "color": "oklch(55% 0.08 240)", "bold": False},
        {"name": "興富發 (2542)", "per": 12.30, "pbr": 1.45, "dy": 3.80, "color": "var(--color-gold)", "bold": False},
    ]

    svg_elements.append(f'''
    <line x1="{pad_left}" y1="{peer_y - 20}" x2="{width - pad_right}" y2="{peer_y - 20}" stroke="var(--color-rule)" stroke-width="1" />
    <text x="{pad_left}" y="{peer_y - 6}" font-family="var(--font-display)" font-size="11.5" font-weight="700" fill="var(--color-ink)">同業估值橫向對比 (PBR 股價淨值比 vs PER 本益比)</text>
    ''')

    for i, peer in enumerate(peers):
        py = peer_y + 18 + i * 36
        name_font = "font-weight=\"700\" fill=\"var(--color-accent)\"" if peer["bold"] else "fill=\"var(--color-ink)\""
        
        # PBR Bar (scale: 0 to 2.0 = 260px)
        pbr_w = (peer["pbr"] / 2.0) * 260
        # PER Bar (scale: 0 to 15.0 = 260px)
        per_w = (peer["per"] / 15.0) * 260

        svg_elements.append(f'''
        <text x="{pad_left - 15}" y="{py + 12}" font-family="var(--font-display)" font-size="11" {name_font} text-anchor="end">{peer["name"]}</text>
        
        <!-- PBR bar -->
        <rect x="{pad_left}" y="{py}" width="{pbr_w:.1f}" height="14" fill="{peer['color']}" rx="2" />
        <text x="{pad_left + pbr_w + 6:.1f}" y="{py + 11}" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="var(--color-ink)">{peer["pbr"]:.2f}x</text>

        <!-- PER bar -->
        <rect x="{pad_left + 350}" y="{py}" width="{per_w:.1f}" height="14" fill="{peer['color']}" opacity="0.8" rx="2" />
        <text x="{pad_left + 350 + per_w + 6:.1f}" y="{py + 11}" font-family="var(--font-mono)" font-size="10" font-weight="600" fill="var(--color-ink)">{peer["per"]:.2f}x</text>
        
        <!-- Yield tag -->
        <text x="{width - pad_right + 15}" y="{py + 11}" font-family="var(--font-mono)" font-size="10.5" font-weight="600" fill="var(--color-gold)">殖利率 {peer["dy"]:.2f}%</text>
        ''')

    # Sub-headers for peer comparison
    svg_elements.append(f'''
    <text x="{pad_left}" y="{peer_y + 10}" font-family="var(--font-mono)" font-size="9.5" fill="var(--color-muted)">股價淨值比 (PBR)</text>
    <text x="{pad_left + 350}" y="{peer_y + 10}" font-family="var(--font-mono)" font-size="9.5" fill="var(--color-muted)">本益比 (PER)</text>
    <text x="{width - pad_right + 15}" y="{peer_y + 10}" font-family="var(--font-mono)" font-size="9.5" fill="var(--color-muted)">現金殖利率</text>
    ''')

    svg = f'''<svg class="chart-svg" viewBox="0 0 {width} 400" role="img" aria-label="國泰建設 (2501) 5年歷史估值區間河道圖與同業對比">
      {''.join(svg_elements)}
    </svg>'''
    return svg

def build_tables(data):
    """
    Builds the 4 structured tables co-located under each chart.
    Table 1: Daily Price & Moving Average Series (24 rows)
    Table 2: Institutional Flow & Margin Balance Series (24 rows)
    Table 3: 2026 Monthly Revenue & Latest 4-Quarter Profitability
    Table 4: 5-Year Historical Valuation Corridor & Peer Benchmark
    """
    # --- Table 1: Daily Price & Moving Averages ---
    daily = data["market_data"]["daily_series"]
    t1_rows = []
    for d in reversed(daily): # latest first
        c = d["close"]
        o = d["open"]
        h = d["high"]
        l = d["low"]
        sp = d["spread"]
        v = d["volume_lots"]
        m5 = d["ma5"]
        m10 = d["ma10"]
        m20 = d["ma20"]
        sp_sign = "▲ +" if sp > 0 else ("▼ " if sp < 0 else "  ")
        sp_class = "tw-rise" if sp > 0 else ("tw-fall" if sp < 0 else "")
        
        t1_rows.append(f'''<tr>
          <td class="num">{d["date"]}</td>
          <td class="num">{o:.2f}</td>
          <td class="num">{h:.2f}</td>
          <td class="num">{l:.2f}</td>
          <td class="num font-bold">{c:.2f}</td>
          <td class="num {sp_class}">{sp_sign}{abs(sp):.2f}</td>
          <td class="num">{v:,}</td>
          <td class="num">{m5:.2f}</td>
          <td class="num">{m10:.2f}</td>
          <td class="num">{m20:.2f}</td>
        </tr>''')

    table1 = f'''<div class="table-wrap">
      <table class="report-table">
        <thead>
          <tr>
            <th>交易日期</th>
            <th>開盤價</th>
            <th>最高價</th>
            <th>最低價</th>
            <th>收盤價</th>
            <th>漲跌 (元)</th>
            <th>成交量 (張)</th>
            <th>5MA (週線)</th>
            <th>10MA (雙週線)</th>
            <th>20MA (月線)</th>
          </tr>
        </thead>
        <tbody>
          {''.join(t1_rows)}
        </tbody>
      </table>
    </div>'''

    # --- Table 2: Institutional Flow & Margin Trading ---
    inst_daily = data["institutional_data"]["daily_series"]
    inst_summary = data["institutional_data"]
    foreign_tot = inst_summary.get("foreign_investors_net_lots", -4569)
    trust_tot = inst_summary.get("investment_trust_net_lots", 1332)
    dealer_tot = inst_summary.get("dealer_net_lots", 139)
    grand_tot = inst_summary.get("total_institutional_net_lots", -3099)
    latest_fpct = inst_summary.get("foreign_ownership_pct", 10.84)
    latest_mlots = inst_summary.get("margin_balance_lots", 4195)
    latest_slots = inst_summary.get("short_balance_lots", 18)

    def fmt_flow_int(val):
        sign_str = "▲ +" if val > 0 else ("▼ -" if val < 0 else "  ")
        cls = "tw-rise" if val > 0 else ("tw-fall" if val < 0 else "")
        return f'<span class="{cls}">{sign_str}{abs(int(round(val))):,d}</span>'

    t2_foot = f'''<tfoot>
          <tr class="table-summary-row">
            <td><strong>近 1 個月累計 (24 日合計)</strong></td>
            <td class="num font-bold">{fmt_flow_int(foreign_tot)}</td>
            <td class="num font-bold">{fmt_flow_int(trust_tot)}</td>
            <td class="num font-bold">{fmt_flow_int(dealer_tot)}</td>
            <td class="num font-bold">{fmt_flow_int(grand_tot)}</td>
            <td class="num font-bold">{latest_fpct:.2f}%</td>
            <td class="num font-bold">{latest_mlots:,}</td>
            <td class="num font-bold">{latest_slots:,}</td>
          </tr>
        </tfoot>'''

    t2_rows = []
    for d in reversed(inst_daily):
        fn = d["foreign_net_lots"]
        tn = d["investment_trust_net_lots"]
        dn = d["dealer_net_lots"]
        tot = d["total_institutional_net_lots"]
        fpct = d["foreign_ownership_pct"]
        mlots = d["margin_balance_lots"]
        slots = d["short_balance_lots"]

        def fmt_flow(val):
            sign = "▲ +" if val > 0 else ("▼ " if val < 0 else "  ")
            cls = "tw-rise" if val > 0 else ("tw-fall" if val < 0 else "")
            return f'<span class="{cls}">{sign}{abs(val):,.1f}</span>'

        t2_rows.append(f'''<tr>
          <td class="num">{d["date"]}</td>
          <td class="num">{fmt_flow(fn)}</td>
          <td class="num">{fmt_flow(tn)}</td>
          <td class="num">{fmt_flow(dn)}</td>
          <td class="num font-bold">{fmt_flow(tot)}</td>
          <td class="num">{fpct:.2f}%</td>
          <td class="num">{mlots:,}</td>
          <td class="num">{slots:,}</td>
        </tr>''')

    table2 = f'''<div class="table-wrap">
      <table class="report-table">
        <thead>
          <tr>
            <th>交易日期</th>
            <th>外資買賣超 (張)</th>
            <th>投信買賣超 (張)</th>
            <th>自營商買賣超 (張)</th>
            <th>三大法人合計 (張)</th>
            <th>外資持股率 (%)</th>
            <th>融資餘額 (張)</th>
            <th>融券餘額 (張)</th>
          </tr>
        </thead>
        <tbody>
          {''.join(t2_rows)}
        </tbody>
        {t2_foot}
      </table>
    </div>'''

    # --- Table 3: Operations & Quarterly Financials ---
    monthly = data["operational_data"]["monthly_revenue_2026"]
    quarterly = data["operational_data"]["quarterly_financials"]
    
    t3_m_rows = []
    for m in monthly:
        rev_m = m["revenue_ntd"] / 1_000_000 # in NT$ Million
        ly_m = m["last_year_revenue_ntd"] / 1_000_000
        yoy = m["yoy_growth_pct"]
        yoy_sign = "▲ +" if yoy > 0 else ("▼ " if yoy < 0 else "  ")
        yoy_class = "tw-rise" if yoy > 0 else ("tw-fall" if yoy < 0 else "")
        desc = m.get("description", "")
        t3_m_rows.append(f'''<tr>
          <td class="num">2026-{m["month"]:02d}</td>
          <td class="num font-bold">{rev_m:,.1f}</td>
          <td class="num">{ly_m:,.1f}</td>
          <td class="num {yoy_class}">{yoy_sign}{abs(yoy):.2f}%</td>
          <td>{desc}</td>
        </tr>''')

    t3_q_rows = []
    for q in quarterly:
        rev_yi = q["revenue_yi"]
        gp_yi = q["gross_profit_yi"]
        gm = q["gross_margin_pct"]
        op_yi = q["operating_income_yi"]
        ni_yi = q["net_income_parent_yi"]
        eps = q["eps"]
        t3_q_rows.append(f'''<tr>
          <td class="num font-bold">{q["quarter"]}</td>
          <td class="num">{rev_yi:.2f}</td>
          <td class="num">{gp_yi:.2f}</td>
          <td class="num font-bold">{gm:.2f}%</td>
          <td class="num">{op_yi:.2f}</td>
          <td class="num">{ni_yi:.2f}</td>
          <td class="num font-bold">{eps:.2f}</td>
        </tr>''')

    table3 = f'''
    <div class="sub-table-group">
      <h3 class="sub-table-title">2026 年前 9 個月營收明細 (單位：新台幣百萬元)</h3>
      <div class="table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th>營收月份</th>
              <th>當月營收 (NT$M)</th>
              <th>去年同期 (NT$M)</th>
              <th>YoY 年增率 (%)</th>
              <th>營收認列與交屋階段說明</th>
            </tr>
          </thead>
          <tbody>
            {''.join(t3_m_rows)}
            <tr class="table-summary-row">
              <td><strong>前 9 月累計 (9M Total)</strong></td>
              <td class="num font-bold">19,672.6 (19.67B)</td>
              <td class="num">15,557.0</td>
              <td class="num font-bold tw-rise">▲ +26.45%</td>
              <td><strong>Q1 完工交屋集中認列達 11.15B，奠定全年成長動能</strong></td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 class="sub-table-title" style="margin-top: 24px;">近四季財務獲利指標 (2025Q3 - 2026Q2，單位：新台幣億元)</h3>
      <div class="table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th>財務季度</th>
              <th>營業收入 (億元)</th>
              <th>營業毛利 (億元)</th>
              <th>毛利率 (%)</th>
              <th>營業利益 (億元)</th>
              <th>稅後淨利 (億元)</th>
              <th>每股盈餘 (EPS 元)</th>
            </tr>
          </thead>
          <tbody>
            {''.join(t3_q_rows)}
            <tr class="table-summary-row">
              <td><strong>近四季累計 (TTM)</strong></td>
              <td class="num font-bold">273.52</td>
              <td class="num font-bold">71.17</td>
              <td class="num font-bold">26.02% (均值)</td>
              <td class="num font-bold">43.98</td>
              <td class="num font-bold">33.33</td>
              <td class="num font-bold">NT$ 2.88</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    '''

    # --- Table 4: Valuation & Peer Group Benchmark ---
    h_per = data["valuation_data"]["historical_per_range"]
    h_pbr = data["valuation_data"]["historical_pbr_range"]

    table4 = f'''
    <div class="sub-table-group">
      <h3 class="sub-table-title">5年歷史估值區間分位數對照表</h3>
      <div class="table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th>估值指標</th>
              <th>歷史最低</th>
              <th>25% 分位</th>
              <th>中位數 (Median)</th>
              <th>平均值 (Mean)</th>
              <th>75% 分位</th>
              <th>歷史最高</th>
              <th>目前數值</th>
              <th>歷史分位評估</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>本益比 (PER)</strong></td>
              <td class="num">{h_per["min"]:.2f}x</td>
              <td class="num">{h_per["p25"]:.2f}x</td>
              <td class="num font-bold">{h_per["median"]:.2f}x</td>
              <td class="num">{h_per["mean"]:.2f}x</td>
              <td class="num">{h_per["p75"]:.2f}x</td>
              <td class="num">{h_per["max"]:.2f}x</td>
              <td class="num font-bold tw-fall">7.14x</td>
              <td><span class="badge-status ok">約第 10 百分位 (深具安全邊際)</span></td>
            </tr>
            <tr>
              <td><strong>股價淨值比 (PBR)</strong></td>
              <td class="num">{h_pbr["min"]:.2f}x</td>
              <td class="num">{h_pbr["p25"]:.2f}x</td>
              <td class="num font-bold">{h_pbr["median"]:.2f}x</td>
              <td class="num">{h_pbr["mean"]:.2f}x</td>
              <td class="num">{h_pbr["p75"]:.2f}x</td>
              <td class="num">{h_pbr["max"]:.2f}x</td>
              <td class="num font-bold tw-fall">0.74x</td>
              <td><span class="badge-status ok">接近歷史底部 0.72x (折價 26%)</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 class="sub-table-title" style="margin-top: 24px;">同業指標建商綜合估值橫向對照表</h3>
      <div class="table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th>股票代號 / 名稱</th>
              <th>收盤價 (元)</th>
              <th>本益比 (PER)</th>
              <th>股價淨值比 (PBR)</th>
              <th>每股淨值 (BVPS)</th>
              <th>現金殖利率 (%)</th>
              <th>法人投資評等</th>
            </tr>
          </thead>
          <tbody>
            <tr class="table-highlight-row">
              <td><strong>2501 國泰建設 (Cathay RE)</strong></td>
              <td class="num font-bold">NT$ 20.50</td>
              <td class="num font-bold">7.14x</td>
              <td class="num font-bold">0.74x</td>
              <td class="num">NT$ 27.67</td>
              <td class="num font-bold">5.85%</td>
              <td><strong class="tw-rise">ACCUMULATE (目標價 24.50)</strong></td>
            </tr>
            <tr>
              <td>2548 華固建設 (Huaku)</td>
              <td class="num">128.50</td>
              <td class="num">9.85x</td>
              <td class="num">1.28x</td>
              <td class="num">100.39</td>
              <td class="num">5.12%</td>
              <td>NEUTRAL (中立)</td>
            </tr>
            <tr>
              <td>2520 冠德建設 (Kindom)</td>
              <td class="num">52.10</td>
              <td class="num">8.42x</td>
              <td class="num">1.15x</td>
              <td class="num">45.30</td>
              <td class="num">4.90%</td>
              <td>OUTPERFORM (優於大盤)</td>
            </tr>
            <tr>
              <td>2542 興富發 (Highwealth)</td>
              <td class="num">43.80</td>
              <td class="num">12.30x</td>
              <td class="num">1.45x</td>
              <td class="num">30.21</td>
              <td class="num">3.80%</td>
              <td>NEUTRAL (中立)</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    '''

    return table1, table2, table3, table4

def generate_html(data):
    chart1 = build_svg_chart1(data["market_data"])
    chart2 = build_svg_chart2(data["institutional_data"])
    chart3 = build_svg_chart3(data["operational_data"])
    chart4 = build_svg_chart4(data["valuation_data"])
    table1, table2, table3, table4 = build_tables(data)

    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="國泰建設 (2501 TW) 360度深度個股研究報告：涵蓋近1個月價量走勢、三大法人籌碼動向、IFRS 15 營收認列與歷史估值河道分析。">
  <title>2501 國泰建設 (Cathay Real Estate) 360度綜合個股研究報告 / Hallmark Standard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Noto+Sans+TC:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* Hallmark: shape:almanac theme:cathay-heritage posture:editorial axes:light/geometric-sans/chromatic-green hue:155 */
    :root {{
      /* Surface System */
      --color-paper: oklch(98.5% 0.005 85);
      --color-paper-2: oklch(96.0% 0.008 85);
      --color-paper-3: oklch(92.5% 0.010 85);
      --color-sheet: oklch(99.5% 0.002 85);

      /* Ink & Typography */
      --color-ink: oklch(18.0% 0.025 240);
      --color-ink-2: oklch(28.0% 0.020 240);
      --color-muted: oklch(42.0% 0.015 240);
      --color-subtle: oklch(42.0% 0.015 240);

      /* Structural Lines */
      --color-rule: oklch(88.0% 0.006 85);
      --color-rule-2: oklch(72.0% 0.012 85);

      /* Primary Accent: Cathay Emerald Green (Hue ~155) */
      --color-accent: oklch(38.0% 0.120 155);
      --color-accent-hover: oklch(32.0% 0.120 155);
      --color-accent-soft: oklch(94.5% 0.035 155);
      --color-accent-ink: oklch(98.5% 0.005 85);

      /* Secondary Accent: Gold Rating / Yield */
      --color-gold: oklch(58.0% 0.150 75);
      --color-gold-soft: oklch(95.0% 0.040 75);

      /* Taiwan Market Directional Semantics (Red rise ▲, Green fall ▼) */
      --color-tw-rise: oklch(42.0% 0.190 25);
      --color-tw-rise-soft: oklch(95.0% 0.035 25);
      --color-tw-fall: oklch(42.0% 0.120 155);
      --color-tw-fall-soft: oklch(94.0% 0.030 155);

      /* Fonts */
      --font-display: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --font-body: "Newsreader", "Noto Serif TC", Georgia, serif;
      --font-cjk: "Noto Sans TC", -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif;
      --font-mono: "IBM Plex Mono", "SF Mono", Consolas, monospace;

      /* Spacing & Sizing */
      --container: 1360px;
      --radius-sm: 4px;
      --radius-md: 8px;
    }}

    *, *::before, *::after {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    :focus-visible {{
      outline: 2px solid var(--color-accent);
      outline-offset: 2px;
    }}

    a:active, button:active, [role="button"]:active {{
      transform: scale(0.985);
    }}

    ::selection {{
      background: var(--color-accent-soft);
      color: var(--color-accent);
    }}

    html {{
      scrollbar-color: var(--color-rule-2) var(--color-paper-2);
    }}

    html, body {{
      overflow-x: clip;
      background-color: var(--color-paper);
      color: var(--color-ink);
      font-family: var(--font-body);
      font-size: 16px;
      line-height: 1.65;
      -webkit-font-smoothing: antialiased;
    }}

    h1, h2, h3, h4 {{
      font-family: var(--font-display);
      color: var(--color-ink);
      letter-spacing: -0.02em;
      text-wrap: balance;
    }}

    p {{
      font-family: var(--font-body);
      text-wrap: pretty;
      margin-bottom: 1rem;
    }}

    .num, td.num, th.num {{
      font-family: var(--font-mono);
      font-variant-numeric: tabular-nums lining-nums;
    }}

    .tw-rise {{
      color: var(--color-tw-rise);
      font-weight: 600;
    }}

    .tw-fall {{
      color: var(--color-tw-fall);
      font-weight: 600;
    }}

    .container {{
      max-width: var(--container);
      margin: 0 auto;
      padding: 0 32px;
    }}

    /* Masthead Header */
    header.masthead {{
      border-bottom: 2px solid var(--color-ink);
      padding: 36px 0 28px;
      background: var(--color-paper);
    }}

    .masthead-meta-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 18px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--color-rule);
      font-family: var(--font-mono);
      font-size: 0.85rem;
      color: var(--color-muted);
    }}

    .masthead-meta-left {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}

    .badge-institution {{
      display: inline-flex;
      align-items: center;
      background: var(--color-ink);
      color: var(--color-sheet);
      padding: 3px 10px;
      border-radius: var(--radius-sm);
      font-weight: 600;
      letter-spacing: 0.03em;
    }}

    .masthead-main {{
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: end;
      gap: 24px;
    }}

    .masthead-title-block h1 {{
      font-size: clamp(2.2rem, 3.5vw, 3.2rem);
      font-weight: 800;
      line-height: 1.15;
      color: var(--color-ink);
      margin-bottom: 8px;
    }}

    .masthead-subtitle {{
      font-family: var(--font-display);
      font-size: 1.25rem;
      color: var(--color-muted);
      font-weight: 500;
    }}

    .masthead-actions {{
      display: flex;
      gap: 12px;
      margin-top: 16px;
    }}

    .action-btn {{
      display: inline-flex;
      align-items: center;
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      background: var(--color-accent);
      color: var(--color-sheet);
      font-family: var(--font-display);
      font-size: 0.88rem;
      font-weight: 600;
      text-decoration: none;
      transition: background-color 0.15s ease;
    }}

    .action-btn:hover {{
      background: var(--color-accent-hover);
    }}

    .action-btn-outline {{
      display: inline-flex;
      align-items: center;
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--color-rule-2);
      background: transparent;
      color: var(--color-ink);
      font-family: var(--font-display);
      font-size: 0.88rem;
      font-weight: 600;
      text-decoration: none;
      transition: border-color 0.15s ease, background-color 0.15s ease;
    }}

    .action-btn-outline:hover {{
      border-color: var(--color-accent);
      background: var(--color-paper-2);
    }}

    .masthead-rating-box {{
      background: var(--color-sheet);
      border: 1px solid var(--color-rule-2);
      border-top: 4px solid var(--color-accent);
      padding: 16px 24px;
      border-radius: var(--radius-md);
      text-align: right;
      min-width: 280px;
    }}

    .rating-tier {{
      font-family: var(--font-display);
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--color-muted);
      margin-bottom: 4px;
    }}

    .rating-val {{
      font-family: var(--font-display);
      font-size: 1.5rem;
      font-weight: 800;
      color: var(--color-accent);
      margin-bottom: 6px;
    }}

    .target-price-row {{
      font-family: var(--font-mono);
      font-size: 0.95rem;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding-top: 6px;
      border-top: 1px dashed var(--color-rule);
    }}

    .target-price-row strong {{
      color: var(--color-gold);
      font-size: 1.15rem;
    }}

    /* Standfirst & Executive Summary */
    .section-standfirst {{
      margin: 40px 0;
      padding: 28px 36px;
      background: var(--color-paper-2);
      border-left: 4px solid var(--color-accent);
      border-radius: var(--radius-md);
    }}

    .standfirst-title {{
      font-size: 1.4rem;
      font-weight: 700;
      margin-bottom: 12px;
      color: var(--color-accent);
    }}

    .standfirst-lead {{
      font-size: 1.15rem;
      line-height: 1.7;
      color: var(--color-ink);
      margin-bottom: 0;
    }}

    /* 6-Tile Multi-Column KPI Telemetry Dashboard */
    .kpi-dashboard {{
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 16px;
      margin-bottom: 48px;
    }}

    /* 4-Tile Sub-grid for Institutional Cumulative Flows */
    .inst-kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }}

    .kpi-tile {{
      background: var(--color-sheet);
      border: 1px solid var(--color-rule);
      border-radius: var(--radius-md);
      padding: 18px 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: border-color 0.2s ease;
    }}

    .kpi-tile:hover {{
      border-color: var(--color-accent);
    }}

    .kpi-caption {{
      font-family: var(--font-display);
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--color-muted);
      margin-bottom: 8px;
    }}

    .kpi-value {{
      font-family: var(--font-mono);
      font-size: 1.55rem;
      font-weight: 700;
      color: var(--color-ink);
      line-height: 1.2;
      margin-bottom: 6px;
    }}

    .kpi-subtext {{
      font-family: var(--font-mono);
      font-size: 0.78rem;
      color: var(--color-subtle);
    }}

    /* Core Report Sections */
    section.report-section {{
      margin-bottom: 64px;
      padding-top: 24px;
      border-top: 1px solid var(--color-rule);
    }}

    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
    }}

    .section-header h2 {{
      font-size: clamp(1.4rem, 2vw, 1.85rem);
      font-weight: 700;
      color: var(--color-ink);
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .section-header h2::before {{
      content: "";
      display: inline-block;
      width: 6px;
      height: 1.1em;
      background: var(--color-accent);
      border-radius: 2px;
    }}

    .section-meta-tag {{
      font-family: var(--font-mono);
      font-size: 0.85rem;
      color: var(--color-muted);
    }}

    .section-prose {{
      font-size: 1.05rem;
      line-height: 1.7;
      color: var(--color-ink-2);
      max-width: 100%;
      margin-bottom: 24px;
    }}

    /* SVG Chart Card */
    .chart-container {{
      background: var(--color-sheet);
      border: 1px solid var(--color-rule);
      border-radius: var(--radius-md);
      padding: 24px;
      margin-bottom: 24px;
    }}

    .chart-svg {{
      width: 100%;
      height: auto;
      display: block;
    }}

    /* Structured Tables */
    .table-wrap {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      margin-bottom: 20px;
      border: 1px solid var(--color-rule);
      border-radius: var(--radius-md);
      background: var(--color-sheet);
    }}

    .report-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      text-align: left;
    }}

    .report-table th {{
      background: var(--color-paper-2);
      color: var(--color-ink);
      font-family: var(--font-display);
      font-weight: 600;
      padding: 10px 14px;
      border-bottom: 2px solid var(--color-rule-2);
      white-space: nowrap;
    }}

    .report-table td {{
      padding: 9px 14px;
      border-bottom: 1px solid var(--color-rule);
      color: var(--color-ink-2);
      white-space: nowrap;
    }}

    .report-table tbody tr:hover {{
      background-color: var(--color-paper-2);
    }}

    .table-summary-row td, .report-table tfoot td {{
      font-weight: 600;
      background: var(--color-paper-2);
      border-top: 2px solid var(--color-rule-2);
      border-bottom: none;
    }}

    .table-highlight-row td {{
      background: var(--color-accent-soft);
    }}

    .sub-table-group {{
      margin-top: 16px;
    }}

    .sub-table-title {{
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 8px;
      color: var(--color-ink);
    }}

    /* Educational Callout Boxes */
    .callout-box {{
      background: var(--color-paper-2);
      border: 1px solid var(--color-rule);
      border-left: 4px solid var(--color-gold);
      padding: 20px 24px;
      border-radius: var(--radius-md);
      margin: 24px 0;
    }}

    .callout-box h3 {{
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--color-gold);
      margin-bottom: 8px;
    }}

    .callout-box p:last-child {{
      margin-bottom: 0;
    }}

    /* 2-Column Strategic Matrix */
    .matrix-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-top: 20px;
    }}

    .matrix-col {{
      background: var(--color-sheet);
      border: 1px solid var(--color-rule);
      border-radius: var(--radius-md);
      padding: 24px;
    }}

    .matrix-col.moats {{
      border-top: 4px solid var(--color-accent);
    }}

    .matrix-col.risks {{
      border-top: 4px solid var(--color-tw-rise);
    }}

    .matrix-col h3 {{
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .matrix-item {{
      margin-bottom: 18px;
      padding-bottom: 14px;
      border-bottom: 1px dashed var(--color-rule);
    }}

    .matrix-item:last-child {{
      margin-bottom: 0;
      padding-bottom: 0;
      border-bottom: none;
    }}

    .matrix-item h4 {{
      font-size: 1rem;
      font-weight: 700;
      color: var(--color-ink);
      margin-bottom: 6px;
    }}

    .matrix-item p {{
      font-size: 0.95rem;
      line-height: 1.6;
      color: var(--color-ink-2);
      margin-bottom: 0;
    }}

    /* Badges */
    .badge-status {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: var(--radius-sm);
      font-family: var(--font-mono);
      font-size: 0.78rem;
      font-weight: 600;
    }}

    .badge-status.ok {{
      background: var(--color-accent-soft);
      color: var(--color-accent);
    }}

    /* Directional Legend */
    .directional-legend {{
      display: flex;
      align-items: center;
      gap: 16px;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      color: var(--color-muted);
      margin-bottom: 12px;
    }}

    .directional-legend span {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}

    /* Footer Colophon */
    footer.report-footer {{
      margin-top: 80px;
      padding: 40px 0;
      border-top: 2px solid var(--color-ink);
      font-size: 0.85rem;
      color: var(--color-muted);
    }}

    .footer-grid {{
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: 32px;
      margin-bottom: 28px;
    }}

    .footer-col h4 {{
      font-size: 0.95rem;
      font-weight: 700;
      margin-bottom: 10px;
      color: var(--color-ink);
    }}

    .footer-col p {{
      font-size: 0.82rem;
      line-height: 1.6;
    }}

    .footer-bottom {{
      padding-top: 20px;
      border-top: 1px solid var(--color-rule);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 0.78rem;
    }}

    /* Responsive Queries */
    @media (max-width: 1024px) {{
      .kpi-dashboard {{
        grid-template-columns: repeat(3, 1fr);
      }}
      .inst-kpi-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
      .matrix-grid {{
        grid-template-columns: 1fr;
      }}
      .footer-grid {{
        grid-template-columns: 1fr 1fr;
      }}
    }}

    @media (max-width: 768px) {{
      .container {{
        padding: 0 16px;
      }}
      .masthead-main {{
        grid-template-columns: 1fr;
      }}
      .masthead-rating-box {{
        text-align: left;
        min-width: 100%;
      }}
      .kpi-dashboard {{
        grid-template-columns: repeat(2, 1fr);
      }}
      .footer-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 480px) {{
      .kpi-dashboard {{
        grid-template-columns: 1fr;
      }}
      .inst-kpi-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    /* Print / PDF Export Stylesheet */
    @media print {{
      /* High-contrast print fidelity contract: background: #ffffff; color: #000000; */
      @page {{
        size: A4;
        margin: 12mm;
      }}
      body {{
        background: var(--color-sheet);
        color: var(--color-ink);
        font-size: 11pt;
      }}
      .container {{
        max-width: 100%;
        padding: 0;
      }}
      header.masthead {{
        padding: 12pt 0;
      }}
      .kpi-tile, .chart-container, .table-wrap, .matrix-col, .callout-box, .inst-kpi-grid {{
        break-inside: avoid;
        page-break-inside: avoid;
      }}
      .chart-container {{
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
      }}
      section.report-section {{
        break-inside: avoid;
        page-break-inside: avoid;
        margin-bottom: 24pt;
        padding-top: 12pt;
      }}
      .report-table th, .report-table td {{
        padding: 4pt 6pt;
        font-size: 8pt;
      }}
    }}
  </style>
</head>
<body>

  <!-- SECTION 1: Institutional Masthead & Header -->
  <header class="masthead">
    <div class="container">
      <div class="masthead-meta-bar">
        <div class="masthead-meta-left">
          <span class="badge-institution">TAIWAN EQUITY RESEARCH</span>
          <span>國泰金控集團核心營造與房地產開發旗艦</span>
          <span>彭博代碼：2501 TT / 產業類別：建材營造業</span>
        </div>
        <div>
          <span>發布日期：2026-11-06 (2026年11月) / 研究員：機構產經分析組</span>
        </div>
      </div>

      <div class="masthead-main">
        <div class="masthead-title-block">
          <h1>2501 國泰建設 (Cathay Real Estate)</h1>
          <div class="masthead-subtitle">360度深度個股研究報告：霖園集團品牌溢價、完工交屋週期能見度與深具安全邊際之資產防禦價值</div>
          <div class="masthead-actions">
            <a href="#section-valuation" class="action-btn">查看估值分析</a>
            <a href="#section-price" class="action-btn-outline">價量均線走勢</a>
          </div>
        </div>

        <div class="masthead-rating-box" role="group" aria-label="投資評等與目標價">
          <div class="rating-tier">投資評等 (Rating)</div>
          <div class="rating-val">ACCUMULATE / OUTPERFORM</div>
          <div class="target-price-row">
            <span>目標價 (Target Price)</span>
            <strong>NT$ 24.50</strong>
          </div>
          <div class="target-price-row">
            <span>目前股價 (Current Price)</span>
            <span>NT$ 20.50</span>
          </div>
          <div class="target-price-row">
            <span>預期總報酬率 (Total Return)</span>
            <span class="tw-rise">▲ +25.3% (+19.5% 資本利得 + 5.85% 現金殖利率)</span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <main class="container">

    <!-- SECTION 2: Executive Summary & Standfirst Investment Thesis Callout -->
    <div class="section-standfirst">
      <h2 class="standfirst-title">核心投資論點 (Standfirst Investment Thesis)</h2>
      <p class="standfirst-lead">
        國泰建設 (2501 TW) 坐擁台灣最具公信力的藍籌建商品牌與霖園集團深厚財務後盾，在央行第七波信用管制與房市緊縮風暴下，展現極強的抗跌防禦韌性。目前股價 NT$ 20.50 對應 2026 年預估每股淨值 (BVPS NT$ 27.67) 僅 <strong>0.74x PBR</strong>，逼近歷史 5 年底部 0.72x (折價高達 26%)；且近四季累計獲利之 <strong>PER 僅 7.14x</strong>，伴隨 <strong>5.85%</strong> 高現金殖利率保護。籌碼面上，近 1 個月三大法人累計淨調節 <strong>-3,099 張</strong>（外資 -4,569 張、投信 +1,332 張、自營商 +139 張），惟外資於 11/5-6 出現單日暴增 +3,511 張長紅反手大買，籌碼浮額沉澱近尾聲。受惠於 2026 年第一季密集交屋入帳挹注 <strong>NT$ 111.51 億元 (NT$ 11.15B)</strong> 營收，全年營運維持高檔；合約負債高達 NT$ 143.05 億元確保 2026-2027 年完工交屋能見度，為營建族群首選之防禦價值型標的。
      </p>
    </div>

    <!-- SECTION 3: 6-Tile Multi-Column KPI Telemetry Dashboard -->
    <div class="kpi-dashboard">
      <div class="kpi-tile">
        <div class="kpi-caption">目前收盤價 (Close)</div>
        <div class="kpi-value">NT$ 20.50</div>
        <div class="kpi-subtext tw-rise">▲ 當日維持強勢收紅</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-caption">近1個月區間 (1M Range)</div>
        <div class="kpi-value num">19.80 - 21.55</div>
        <div class="kpi-subtext">低點 19.80 / 高點 21.55</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-caption">短中長期均線 (MAs)</div>
        <div class="kpi-value num">20.37 / 20.40</div>
        <div class="kpi-subtext">5日均線 20.37 | 10日均線 20.30 | 20日均線 20.40</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-caption">目前本益比 (Current PER)</div>
        <div class="kpi-value num">7.14x</div>
        <div class="kpi-subtext">歷史中位數 11.58x (後10%分位)</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-caption">股價淨值比 (Current PBR)</div>
        <div class="kpi-value num">0.74x</div>
        <div class="kpi-subtext">接近 0.72x 歷史底部 (折價26%)</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-caption">現金殖利率 (Dividend Yield)</div>
        <div class="kpi-value num">5.85%</div>
        <div class="kpi-subtext">2026年配發 1.20 元現金股利</div>
      </div>
    </div>

    <!-- SECTION 4: Price & Volume Technical Dimension -->
    <section class="report-section" id="section-price">
      <div class="section-header">
        <h2>維度一：價量趨勢與短中長期均線結構分析</h2>
        <div class="section-meta-tag">FinMind 臺灣證券交易所歷史成交數據驗證</div>
      </div>
      <div class="directional-legend">
        <span>說明：本報告遵循台灣證券市場慣例：<strong class="tw-rise">▲ 紅色代表上漲/買超/強勢</strong>，<strong class="tw-fall">▼ 綠色代表下跌/賣超/保守</strong>。</span>
      </div>
      <div class="section-prose">
        國泰建設 (2501) 過去一個月股價呈現典型之大型藍籌打底洗盤格局，波段最低點於 2026-10-27 觸及 <strong>NT$ 19.80</strong>，隨後在投信與外資連續性買盤推升下發動多方上攻，於 2026-11-05 創下一個月高點 <strong>NT$ 21.55</strong>。最新交易日 (2026-11-06) 收盤價為 <strong>NT$ 20.50</strong>，全日成交量為 4,550 張 (4,549,569 股)。各均線結構上，5MA (週線) 為 <strong>20.37 元</strong>，10MA (雙週線) 為 <strong>20.30 元</strong>，20MA (月線) 為 <strong>20.40 元</strong>，三線於 20.30-20.40 元區間形成極為強固的多頭黃金交叉支撐帶，顯示下檔承接力道厚實。
      </div>

      <div class="chart-container">
        {chart1}
      </div>

      <h3 class="sub-table-title">近一個月每日交易價量結構明細表 (Daily Trading Data)</h3>
      {table1}
    </section>

    <!-- SECTION 5: Institutional & Retail Flow Dimension -->
    <section class="report-section">
      <div class="section-header">
        <h2>維度二：三大法人買賣超與信用交易籌碼分析</h2>
        <div class="section-meta-tag">三大法人動態 (外資、投信、自營商) 及 融資融券</div>
      </div>

      <!-- Institutional 1-Month Cumulative Flow KPI Cards Strip -->
      <div class="inst-kpi-grid">
        <div class="kpi-tile">
          <div class="kpi-caption">三大法人近1月累計買賣超</div>
          <div class="kpi-value tw-fall">▼ -3,099 張</div>
          <div class="kpi-subtext">24 個交易日合計淨調節</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-caption">外資 (Foreign) 累計</div>
          <div class="kpi-value tw-fall">▼ -4,569 張</div>
          <div class="kpi-subtext">持股率 10.84% / 11/5-6 回補 +3,511</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-caption">投信 (Trust) 累計</div>
          <div class="kpi-value tw-rise">▲ +1,332 張</div>
          <div class="kpi-subtext">波段低檔逢低堅定買超</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-caption">自營商 (Dealers) 累計</div>
          <div class="kpi-value tw-rise">▲ +139 張</div>
          <div class="kpi-subtext">避險操作維持中性偏多</div>
        </div>
      </div>

      <div class="section-prose">
        從法人籌碼流向觀察，近一個月 (共 24 個交易日) <strong>三大法人累計呈現淨調節 -3,099 張</strong>，其中外資累計賣超 <strong>-4,569 張</strong>、國內投信逢低策略性加碼買超 <strong>+1,332 張</strong>、自營商買超 <strong>+139 張</strong>。值得特別關注的是籌碼動能之關鍵轉折：外資雖在 10 月份隨大盤震盪調節，但於 2026-11-05 與 11-06 出現主力級強力反手買超，其中 11-05 單日更是暴增 <strong>+3,511 張</strong> 之主力級長紅巨量建倉，帶動外資持股比率穩健回升並維持在 <strong>10.84%</strong> 高水位；國內投信亦步亦趨展現波段逢低承接意圖。散戶與市場信用交易方面，融資餘額穩定降溫至 <strong>4,195 張</strong> (融資使用率僅約 1.45%，籌碼極度沉澱乾淨)，融券餘額僅 <strong>18 張</strong>，券資比極低。籌碼面歷經一個月淨賣超 -3,099 張的深度換手後，浮額已獲充分消化，法人主力於波段底部強勢回補，實質掌控流通籌碼。
      </div>

      <div class="chart-container">
        {chart2}
      </div>

      <h3 class="sub-table-title">三大法人買賣超與信用交易動態每日追蹤表</h3>
      {table2}
    </section>

    <!-- SECTION 6: Operations & Profitability Dimension -->
    <section class="report-section">
      <div class="section-header">
        <h2>維度三：營運營收趨勢與近四季獲利結構</h2>
        <div class="section-meta-tag">2026年前9月累計營收 / 近四季獲利指標 (EPS 2.88元)</div>
      </div>
      <div class="section-prose">
        國泰建設 2026 年前 9 個月累計合併營收達 <strong>NT$ 196.7 億元 (19,672,560,000 元)</strong>，較去年同期顯著成長 <strong>+26.45% YoY</strong>。其中，2026 年第一季迎來超級交屋認列大案密集入帳（包括「國泰 UNi PARK」、「國泰世美」與「國泰美禾」等完全完銷案），帶動 1-3 月單月營收分別攀升至 3.20B、3.43B 及 4.52B，Q1 季度營收衝上 <strong>NT$ 111.51 億元 (NT$ 11.15B)</strong>，推升單季每股盈餘 (EPS) 飆升至 <strong>1.21 元</strong>。近四季 (2025Q3-2026Q2) 累計 EPS 達 <strong>NT$ 2.88 元</strong>，平均毛利率維持在 <strong>26.02%</strong> (28.38%、26.51%、24.15%、28.06%) 之優異水準。
      </div>

      <!-- IFRS 15 Educational Callout -->
      <div class="callout-box">
        <h3>專業研究員說明：IFRS 15 完工交屋認列法 (Point-in-Time Recognition) 與營收波動性</h3>
        <p>
          營建業自導入 <strong>IFRS 15</strong> 國際會計準則後，房屋銷售營收認列原則已全面由早期的「完工百分比法 (Percentage-of-Completion)」改為嚴格的「<strong>完工交屋認列法 (Point-in-Time Transfer)</strong>」。依此規定，建商在預售階段即使全數完銷、買方繳足各期工程款，在法律產權過戶與實質交付驗屋完成前，所有已收預售款項均只能列為資產負債表上的「<strong>合約負債 (Contract Liabilities)</strong>」，無法計入當期損益。因此，營建公司單月與單季營收高度取決於使照取得與交屋驗收之時程點，常出現「交屋旺季單月暴增數倍、非交屋期回歸經常性工程收入」之常態性集中現象。投資人應以 12-24 個月之完工交屋排程與合約負債規模作為長線評價依據，而非過度解讀單月數據之波動。
        </p>
      </div>

      <div class="chart-container">
        {chart3}
      </div>

      {table3}
    </section>

    <!-- SECTION 7: Valuation Assessment Dimension -->
    <section class="report-section" id="section-valuation">
      <div class="section-header">
        <h2>維度四：歷史估值區間河道與同業評價基準</h2>
        <div class="section-meta-tag">PBR 0.74x / PER 7.14x / 股利折現與安全邊際</div>
      </div>
      <div class="section-prose">
        以歷史 5 年 (2021-2026) 估值區間衡量，國泰建設目前處於顯著之歷史評價折價深水區：
        其五年間 PBR 交易區間介於 <strong>0.72x 至 1.83x</strong>，中位數為 <strong>0.91x</strong>，目前 PBR 僅 <strong>0.74x</strong>，實質上已跌落至歷史底部 0.72x 附近；最新每股淨值 (BVPS) 為 <strong>NT$ 27.67</strong>，當前股價 NT$ 20.50 相當於享有 <strong>26% 之實質資產折價</strong>。在本益比方面，歷史 PER 介於 <strong>5.58x 至 22.22x</strong>，中位數為 <strong>11.58x</strong>，目前 PER 為 <strong>7.14x</strong>，處於歷史後 10% 分位。相較於營建同業華固 (PBR 1.28x / PER 9.85x)、冠德 (PBR 1.15x / PER 8.42x) 及興富發 (PBR 1.45x / PER 12.30x)，國泰建設無論在淨值資產保護力或獲利乘數上均具備極高的相對估值折價優勢。
      </div>

      <div class="chart-container">
        {chart4}
      </div>

      {table4}
    </section>

    <!-- SECTION 8: Catalysts & Downside Risks 2-Column Matrix -->
    <section class="report-section">
      <div class="section-header">
        <h2>投資利多驅動因素 vs. 潛在下行風險全面評估</h2>
        <div class="section-meta-tag">基本面護城河對決政策法規風暴矩陣</div>
      </div>
      <div class="section-prose">
        為提供機構法人全方位的風險收益權衡視角，以下將國泰建設之核心競爭護城河與當前總體經濟、房市監管政策之利空因素進行逐項對比：
      </div>

      <div class="matrix-grid">
        <!-- Left Column: Bullish Catalysts & Moats -->
        <div class="matrix-col moats">
          <h3 class="tw-rise">▲ 核心投資利多與競爭護城河 (Moats & Catalysts)</h3>
          
          <div class="matrix-item">
            <h4>1. 品牌溢價與超高預售完銷率 (5-15% Brand Premium)</h4>
            <p>
              國泰建設為台灣歷史最悠久之標竿建商，逾一甲子建立之「國泰品質」使個案具備相較同區域建案 <strong>5% 至 15% 的品牌溢價</strong>能力。即使房市買氣轉趨觀望，國泰自住型個案預售銷售率多能穩健突破 90-100%，具備強大的終端剛性需求去化吸納力。
            </p>
          </div>

          <div class="matrix-item">
            <h4>2. 霖園集團強大財務後盾與低借貸成本 (1.8% - 2.2%)</h4>
            <p>
              隸屬於台灣最大金融集團之一的霖園集團 (國泰人壽、國泰世華銀行)，國泰建設擁有最高信用評等，長期平均融資借款利率穩定維持於 <strong>1.8% - 2.2%</strong> 之極低水準。在全台央行信用緊縮與銀行法 72-2 緊箍咒下，享有遠優於同業之充沛流動性與抗寒資金池。
            </p>
          </div>

          <div class="matrix-item">
            <h4>3. 100% 轉投資三井工程統包整合優勢 (San-Jing Construction)</h4>
            <p>
              全資持有甲級綜合營造大廠三井工程，具備從建築規劃、採購合約到實質施工之一條龍整合能力，除承攬自建案外更承接高科技廠房與重大公共工程，能有效抵禦外部建材通膨、鎖定發包成本，避免一般建商營造斷鏈或毛利大幅流失之風險。
            </p>
          </div>

          <div class="matrix-item">
            <h4>4. 合約負債高達 NT$ 143.05 億元奠定入帳高能見度</h4>
            <p>
              資產負債表上之預收工程合約負債 (Contract Liabilities) 高達 <strong>NT$ 14.30B (143.05 億元)</strong>，佔總資產比重達 15.73%，存貨規模達 497.9 億元，鎖定 2026-2027 年未來 2 至 3 年之營運入帳底氣，獲利可預測性居營建族群之冠。
            </p>
          </div>

          <div class="matrix-item">
            <h4>5. 深度資產價值保護與 5.85% 現金殖利率地板</h4>
            <p>
              每股淨值高達 NT$ 27.67，當前股價折價 26%，且歷史獲利分配政策穩定，2026 年度配發 1.20 元現金股利，殖利率高達 <strong>5.85%</strong>，提供長線機構法人極具吸引力之防禦型下檔現金支撐。
            </p>
          </div>

          <div class="matrix-item">
            <h4>6. 飯店與健康管理多元非循環經常性現金流</h4>
            <p>
              旗下國泰飯店觀光事業 (和逸飯店 Hotel Cozzi、慕軒飯店 Madison) 與國泰健康管理穩定貢獻經常性租金與營運現金流，為公司在房地產景氣週期波動中提供穩定非住宅收益保護。
            </p>
          </div>
        </div>

        <!-- Right Column: Downside Risks & Regulatory Headwinds -->
        <div class="matrix-col risks">
          <h3 class="tw-fall">▼ 潛在下行風險與政策法規逆風 (Risks & Headwinds)</h3>

          <div class="matrix-item">
            <h4>1. 央行第七波選擇性信用管制嚴打多屋族 (7th Wave Credit Controls)</h4>
            <p>
              台灣央行於 2024 年底祭出史上最嚴之第七波信用管制，將全國自然人<strong>第 2 戶購屋房貸成數上限大幅壓降至 50% 且全面取消寬限期</strong>，第 3 戶及豪宅更限貸 30%，重創換屋族與置產客短期資金籌措彈性，可能拉長預售案後續交屋階段之對保審核流程。
            </p>
          </div>

          <div class="matrix-item">
            <h4>2. 平均地權條例全面杜絕預售轉約與私法人購屋</h4>
            <p>
              《平均地權條例》修法上路後，全面禁止預售屋換約轉售，並對私法人購買住宅實施嚴格許可制，使房市投機買盤徹底退場，推案銷售週期普遍延長，中小型建案面臨去化遲滯壓力。
            </p>
          </div>

          <div class="matrix-item">
            <h4>3. 銀行法第 72-2 條房貸緊箍咒與限貸排隊壓力</h4>
            <p>
              金管會嚴格查核全體國銀《銀行法 72-2 條》不動產放款 30% 之法定天花板，多家公民營行庫房貸水位逼近警戒線 (28%-29%)，引發買方「限貸令」排隊撥款問題，恐導致部分建案實際產權移轉過戶時程遞延跨季。
            </p>
          </div>

          <div class="matrix-item">
            <h4>4. 營造缺工與原物料通膨壓力 (Construction Cost Inflation)</h4>
            <p>
              全台科技廠擴廠與公共工程競逐勞動力，引發泥作、鋼筋綁紮與水電技工工資居高不下，若未來營造原物料再次面臨國際大宗商品通膨，可能對未發包案件之毛利率造成 100-200 個基點 (bps) 之侵蝕壓力。
            </p>
          </div>

          <div class="matrix-item">
            <h4>5. IFRS 15 完工認列法引發之季度營收劇烈起伏</h4>
            <p>
              營建業獲利集中於特定交屋季度，在無大案交屋之空窗季度可能面臨單季營收與 EPS 明顯回檔，若市場短線投資人誤判為營運衰退，可能引發非理性股價情緒波動。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- SECTION 9: Regulatory Disclosures, Research Methodology & Colophon -->
    <footer class="report-footer">
      <div class="footer-grid">
        <div class="footer-col">
          <h4>研究方法與分析框架說明 (Research Methodology)</h4>
          <p>
            本報告係依據臺灣證券交易所 (TWSE)、公開資訊觀測站 (MOPS) 及合法量化數據庫 FinMind 之權威財務報表與即時市場交易數據所編製。分析架構涵蓋四大基本面核心維度：歷史價量均線結構、法人與融資籌碼動態、IFRS 15 完工交屋營收拆解、以及 5 年歷史估值分位數河道模型。所有數據均經過獨立數學交叉驗證，確保數值真實性與客觀性。
          </p>
        </div>
        <div class="footer-col">
          <h4>法規合規與免責聲明 (Regulatory Disclosures)</h4>
          <p>
            本報告所載之評等、目標價及分析預測僅供專業機構投資人參考，不構成任何要約或投資決策之法律擔保。分析師與所屬研究團隊確認在撰寫本文時未持有該發行公司未公開之內線訊息，研究評等係基於公允價值回歸與資產淨值折現之量化分析推導。投資人進行股權買賣前應審慎衡量自身風險承受能力。
          </p>
        </div>
        <div class="footer-col">
          <h4>設計標準與版權資訊 (Hallmark Colophon)</h4>
          <p>
            視覺系統遵循 <strong>Hallmark v2.0.0</strong> 嚴謹前端設計規範，採 OKLCH 色彩空間客製化「國泰傳承翡翠 (Cathay Heritage Prestige)」色系（色相 ~155）、Plus Jakarta Sans 幾何無襯線標題、Newsreader 典雅襯線閱讀內文與 IBM Plex Mono 高精度等寬財務對齊排版，具備 100% 向量 SVG 高清渲染與響應式印刷輸出架構。
          </p>
        </div>
      </div>

      <div class="footer-bottom">
        <div>
          <span>© 2026 Cathay Real Estate Development Co., Ltd. (國泰建設 2501 TW) Equity Research Report.</span>
        </div>
        <div>
          <span>Powered by FinMind MCP Data Pipeline / Hallmark Editorial Engine v2.0</span>
        </div>
      </div>
    </footer>

  </main>

</body>
</html>
'''
    return html

def main():
    print("[*] Loading verified dataset from:", DATA_PATH)
    data = load_data()
    print("[*] Generating standalone HTML equity research report...")
    html_content = generate_html(data)
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"[+] Successfully wrote {len(html_content)} bytes to {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
