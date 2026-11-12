"""Derived values from methodology.md sections 6 to 8, plus the number formats.

The report generator and check_report.py both import this module, so the HTML
and the checks use one implementation. Generators must format prices, signed
percentages, multiples, and R:R with fmt_price, fmt_pct, fmt_mult, and fmt_rr.
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


# Why a setup is inactive; the report shows this text in place of R:R.
SETUP_STATUS_ZH = {
    "below_zone": "收盤低於進場區，拉回策略條件未成立",
    "target_below_entry": "波段目標不高於進場價，拉回策略條件未成立",
    "target_below_trigger": "波段目標不高於突破點，突破策略條件未成立",
    "base_below_close": "Base 目標價不高於收盤，長線持有沒有上檔空間",
    "bear_above_close": "Bear 目標價不低於收盤，無法以悲觀情境衡量下檔",
}

# Current action (methodology section 8).
ACTION_ZH = {
    "avoid": "避開",
    "watch": "觀望",
    "accumulate": "可分批布局",
    "wait_pullback": "等回檔或突破",
    "wait_reclaim": "等站回進場區",
}

# Base upside above which the rating is BUY; the fair buy price is Base target / (1 + this).
BUY_UPSIDE_PCT = 15


def rating_of(upside_pct):
    if upside_pct > BUY_UPSIDE_PCT:
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
    bull = next(s for s in scen if s["name"] == "Bull")
    t2 = min(round_tick(m["low60"] + 1.618 * (m["high60"] - m["low60"])), bull["target"])
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

    bear = next(s for s in scen if s["name"] == "Bear")
    fair_buy = round_tick(base["target"] / (1 + BUY_UPSIDE_PCT / 100))
    if base["target"] <= close:
        hold_status = "base_below_close"
    elif bear["target"] >= close:
        hold_status = "bear_above_close"
    else:
        hold_status = "active"
    rr_hold = (round((base["target"] - close) / (close - bear["target"]), 2)
               if hold_status == "active" else None)

    zone_txt = f"{fmt_price(z_lo)}–{fmt_price(z_hi)}"
    if rating_en == "SELL":
        action, note = "avoid", f"Base 上漲空間 {fmt_pct(base['upside_pct'])}，評等賣出"
    elif rating_en == "NEUTRAL":
        action, note = "watch", f"合理買進價 {fmt_price(fair_buy)} 以下再評估"
    elif close < z_lo:
        action, note = "wait_reclaim", f"收盤低於進場區 {zone_txt}，等重新站回"
    elif close <= z_hi:
        action, note = "accumulate", f"進場區 {zone_txt}，停損 {fmt_price(hard_stop)}"
    else:
        action, note = "wait_pullback", f"等回檔至 {zone_txt}，或帶量突破 {fmt_price(trigger)}"
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
        "fair_buy": fair_buy,
        "hold_status": hold_status,
        "rr_hold": rr_hold,
        "action": action,
        "action_zh": ACTION_ZH[action],
        "action_note": note,
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
