"""L5 shortlist with hysteresis, FinMind deep metrics per shortlisted stock, the BUY proxy, and L6 tiers."""

import json
import os

import shared

RED_FLAGS = {"disposition", "attention", "periodic_auction", "one_off_revenue"}
TIER_A_PROXY = 15.0
DEEP_FIELDS = {                     # field -> path in the fetch.build output
    "close": ("price", "metrics", "close"),
    "per_p50": ("valuation", "PER", "p50"),
    "per_pct": ("valuation", "PER", "current_percentile"),
    "pbr_pct": ("valuation", "PBR", "current_percentile"),
    "ntm_eps": ("financials", "core_baseline", "ntm_eps"),
    "cb_applicable": ("financials", "core_baseline", "applicable"),
    "cb_high_vol": ("financials", "core_baseline", "high_volatility"),
    "cash_conversion": ("financials", "cash_conversion"),
    "cost_zone": ("institutional", "cost_zone"),
    "gaps": ("gaps",),
}


def select(ranked, prev_actionable, enter=20, stay=40, cap=30, left_n=10):
    """(actionable codes, left-side watch codes), each ordered by rank_trend."""
    passing = sorted((r for r in ranked if r["trend_ok"]), key=lambda r: r["rank_trend"])
    failing = sorted((r for r in ranked if not r["trend_ok"]), key=lambda r: r["rank_trend"])
    actionable = [r["code"] for r in passing
                  if r["rank_trend"] <= enter or (r["code"] in prev_actionable and r["rank_trend"] <= stay)]
    return actionable[:cap], [r["code"] for r in failing[:left_n]]


def _dig(d, path):
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def deep_metrics(code, asof, cache_dir, build=shared.fetch_build):
    """DEEP_FIELDS from fetch.build(code, [], asof), cached whole at {cache_dir}/finmind/{asof}/{code}.json."""
    path = cache_dir / "finmind" / asof / f"{code}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = build(code, [], asof)            # QuotaError / NotPublishedError propagate; nothing is written
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    return {field: _dig(data, p) for field, p in DEEP_FIELDS.items()}


def _positive(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def buy_proxy(dm):
    """(NTM core baseline EPS × own 5-year PER P50 ÷ close − 1) × 100, or None."""
    eps, p50, close = dm.get("ntm_eps"), dm.get("per_p50"), dm.get("close")
    if dm.get("cb_applicable") is not True or not all(_positive(x) for x in (eps, p50, close)):
        return None
    return (eps * p50 / close - 1) * 100


def tier(list_name, trend_ok, flags, proxy):
    ok = list_name == "actionable" and trend_ok and not (set(flags) & RED_FLAGS)
    return "A" if ok and proxy is not None and proxy > TIER_A_PROXY else "B"
