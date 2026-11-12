"""Derived values from methodology.md sections 6 and 7, plus the number formats.

The report generator and check_report.py both import this module, so the HTML
and the checks use one implementation. Generators must format prices, signed
percentages, and R:R with fmt_price, fmt_pct, and fmt_rr.
"""

import json
from pathlib import Path


# ---------------------------------------------------------------- work folder

def load_work(work_dir, code):
    """Return (data, analysis) from a work folder."""
    work_dir = Path(work_dir)
    d = json.loads((work_dir / f"data_{code}.json").read_text(encoding="utf-8"))
    a = json.loads((work_dir / f"analysis_{code}.json").read_text(encoding="utf-8"))
    return d, a


def report_relpath(d, a):
    """Report path relative to the repository root."""
    return f"reports/equity/{d['code']}-{a['slug']}-{d['asof'].replace('-', '')}.html"


# ---------------------------------------------------------------- prices

def tick(p):
    """TWSE/TPEx tick size for a price."""
    if p < 10:
        return 0.01
    if p < 50:
        return 0.05
    if p < 100:
        return 0.1
    if p < 500:
        return 0.5
    if p < 1000:
        return 1.0
    return 5.0


def round_tick(p):
    """Round a price to its tick size."""
    t = tick(p)
    return round(round(p / t) * t, 2)


def rating_of(upside_pct):
    if upside_pct > 15:
        return "買進", "BUY"
    if upside_pct >= -5:
        return "中立", "NEUTRAL"
    return "賣出", "SELL"


# ---------------------------------------------------------------- derivation

def derive(d, a):
    m = d["price"]["metrics"]
    close = m["close"]
    scen = []
    for s in a["scenarios"]:
        target = round_tick(s["eps"] * s["multiple"])
        scen.append({**s, "target": target, "upside_pct": round((target / close - 1) * 100, 1)})
    base = next(s for s in scen if s["name"] == "Base")
    weighted = round_tick(sum(s["probability"] * s["target"] for s in scen) / 100)
    rating_zh, rating_en = rating_of(base["upside_pct"])

    lo_ma, hi_ma = min(m["ma10"], m["ma20"]), max(m["ma10"], m["ma20"])
    zone = d["institutional"]["cost_zone"]
    if zone and max(lo_ma, zone["low"]) <= min(hi_ma, zone["high"]):
        z_lo, z_hi, z_src = max(lo_ma, zone["low"]), min(hi_ma, zone["high"]), "overlap"
    else:
        z_lo, z_hi, z_src = lo_ma, hi_ma, "ma_band"
    z_lo, z_hi = round_tick(z_lo), round_tick(z_hi)
    entry = round_tick((z_lo + z_hi) / 2)
    trigger = m["high60"]
    t1 = m["high60"] if m["high60"] >= entry * 1.03 else round_tick(entry + 0.618 * (m["high60"] - m["low60"]))
    t2 = base["target"]
    cands = [c for c in (m["w20_maxvol_low"], round_tick(m["ma20"] * 0.97)) if c < z_lo]
    hard_stop = round_tick(max(cands)) if cands else round_tick(z_lo * 0.95)
    stop_src = "candidate" if cands else "zone_low_x_0.95"
    bo_stop = round_tick(trigger * 0.95)
    rr_pb = round((t2 - entry) / (entry - hard_stop), 2)
    rr_bo = round((t2 - trigger) / (trigger - bo_stop), 2)
    return {
        "close": close,
        "scenarios": scen,
        "base": base,
        "weighted_target": weighted,
        "weighted_upside_pct": round((weighted / close - 1) * 100, 1),
        "rating_zh": rating_zh,
        "rating_en": rating_en,
        "zone_low": z_lo,
        "zone_high": z_hi,
        "zone_source": z_src,
        "entry": entry,
        "trigger": trigger,
        "trigger_volume_lots": round(1.5 * m["vol_avg20_lots"]),
        "t1": t1,
        "t2": t2,
        "hard_stop": hard_stop,
        "hard_stop_source": stop_src,
        "breakout_stop": bo_stop,
        "rr_pullback": rr_pb,
        "rr_breakout": rr_bo,
    }


# ---------------------------------------------------------------- formats

def fmt_price(p):
    """Price with its tick's decimals and thousands separators, e.g. 1,160 or 288.5."""
    t = tick(p)
    dec = 0 if t >= 1 else (1 if t >= 0.1 else 2)
    return f"{p:,.{dec}f}"


def fmt_pct(v, dec=1, suffix="%"):
    """Signed percentage, e.g. +10.9%."""
    if v is None:
        return "無資料"
    return f"{v:+,.{dec}f}{suffix}"


def fmt_rr(v):
    return f"{v:.2f}"
