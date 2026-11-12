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


# Why a trade setup is inactive; the report shows this text in place of R:R.
SETUP_STATUS_ZH = {
    "below_zone": "收盤低於進場區，拉回策略條件未成立",
    "target_below_entry": "Base 目標價不高於進場價，拉回策略條件未成立",
    "target_below_trigger": "Base 目標價不高於突破點，突破策略條件未成立",
}


def rating_of(upside_pct):
    if upside_pct > 15:
        return "買進", "BUY"
    if upside_pct >= -5:
        return "中立", "NEUTRAL"
    return "賣出", "SELL"


# ---------------------------------------------------------------- derivation

def band_position(v, band):
    """Where v sits in a percentile band: below_p25, p25_p75, p75_p90, or above_p90."""
    if v < band["p25"]:
        return "below_p25"
    if v <= band["p75"]:
        return "p25_p75"
    return "p75_p90" if v <= band["p90"] else "above_p90"


def implied_multiple(d, a, name, target):
    """Cross-check a target against the other valuation band (methodology section 6).

    With the PER method the target implies a PBR (target / BVPS); with the PBR method it
    implies a PER (target / TTM EPS). needs_basis marks a Base above P90 or a Bull above
    1.5 x P90, whose basis must then name the metric. None when the input is missing.
    """
    metric = "PER" if a.get("valuation_method") == "PBR" else "PBR"
    f = d.get("financials") or {}
    denom = f.get("ttm_eps") if metric == "PER" else f.get("bvps_latest")
    band = (d.get("valuation") or {}).get(metric)
    if not denom or denom <= 0 or not band:
        return None
    v = round(target / denom, 2)
    limit = {"Base": band["p90"], "Bull": 1.5 * band["p90"]}.get(name)
    return {"metric": metric, "value": v, "position": band_position(v, band),
            "needs_basis": limit is not None and v > limit}


def derive(d, a):
    m = d["price"]["metrics"]
    close = m["close"]
    scen = []
    for s in a["scenarios"]:
        target = round_tick(s["eps"] * s["multiple"])
        scen.append({**s, "target": target, "upside_pct": round((target / close - 1) * 100, 1),
                     "implied": implied_multiple(d, a, s["name"], target)})
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
    if close < z_lo:
        pb_status = "below_zone"
    elif t2 <= entry:
        pb_status = "target_below_entry"
    else:
        pb_status = "active"
    bo_status = "target_below_trigger" if t2 <= trigger else "active"
    rr_pb = round((t2 - entry) / (entry - hard_stop), 2) if pb_status == "active" else None
    rr_bo = round((t2 - trigger) / (trigger - bo_stop), 2) if bo_status == "active" else None
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
        "pullback_status": pb_status,
        "breakout_status": bo_status,
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


def fmt_mult(v):
    """Valuation multiple, e.g. 2.34x."""
    return f"{v:.2f}x"


def fmt_rr(v):
    """R:R with 2 decimals; 不適用 for an inactive setup (None)."""
    return "不適用" if v is None else f"{v:.2f}"
