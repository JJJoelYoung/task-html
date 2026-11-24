"""The L0–L4 funnel: track split, investability and red-flag exclusions, factor z-scores, sector gate, composite.

Rows are keyed by Security.key. `tracks` is keyed by Security.key as well; tags,
factors, trend results, and the non-general set are keyed by code. Industries are
the ISIN labels, shared by TWSE and TPEx, so a cable maker on either board is
scored against the same peers.
"""

import math
from statistics import mean, pstdev

from shared import mt
from snapshots import EXCLUDE_TAGS, FLAG_TAGS

PARAMS = {
    "min_history": 120, "adv20_min": 30_000_000, "close_min": 10.0, "winsor": (5, 95), "z_clip": 3.0,
    "small_industry_n": 5, "floor_z": -1.0, "availability_min": 0.70,
    "group_weights": {"growth": 0.35, "valuation": 0.25, "quality": 0.15, "flow": 0.15, "persistence": 0.10},
    "mix": (0.8, 0.2), "unfavoured_fraction": 1 / 3, "exception_top_pct": 5.0,
}
GROUPS = {
    "growth": [("rev_yoy_med6", 1, 1), ("rev_accel", 1, 1), ("rev_surge", 1, 1), ("opm_delta_4q", 1, 1)],
    "valuation": [("earnings_yield", 0.67, 1), ("book_yield", 0.33, 1)],
    "quality": [("opm_ttm", 1, 1), ("opm_spread_4q", 1, -1), ("roe_ttm", 1, 1)],
    "flow": [("flow20_pct", 1, 1), ("trust_days20", 1, 1)],
    "persistence": [("persist13", 1, 1)],
}
VARIABLES = [v for members in GROUPS.values() for v, _, _ in members]
FINANCIAL_INDUSTRIES = {"金融保險業"}
STATUSES = ["watch_track", "excluded_status", "excluded_no_quote", "excluded_liquidity", "excluded_price",
            "excluded_financial", "excluded_loss", "insufficient_data", "excluded_sector", "excluded_floor", "ranked",
            "shortlist_actionable", "shortlist_left_watch"]
SECTOR_INPUTS = ("rev_breadth", "rev_yoy3", "rel_ret13", "trend_breadth")


def track(s, history_days, params=PARAMS):
    return "full" if s.market in ("twse", "tpex") and history_days >= params["min_history"] else "watch"


def winsorize(values, lo, hi):
    ordered = sorted(values.values())
    a, b = mt.percentile(ordered, lo), mt.percentile(ordered, hi)
    return {k: min(max(v, a), b) for k, v in values.items()}


def _z(v, pool):
    sd = pstdev(pool)
    return (v - mean(pool)) / sd if sd else 0.0


def zscores(values, industry, min_n, clip):
    """Within-industry z (population sd); an industry with fewer than min_n values uses the market-wide z."""
    members = {}
    for k in values:
        members.setdefault(industry[k], []).append(values[k])
    market = list(values.values())
    out = {}
    for k, v in values.items():
        pool = members[industry[k]]
        out[k] = max(-clip, min(clip, _z(v, pool if len(pool) >= min_n else market)))
    return out


def _pct(hits, total):
    return hits / total * 100 if total else None


def sector_scores(eligible, industry, factors, trend_ok, min_n, fraction=PARAMS["unfavoured_fraction"]):
    by = {}
    for c in eligible:
        by.setdefault(industry[c], []).append(c)
    rets = [factors[c]["ret13w"] for c in eligible if factors[c].get("ret13w") is not None]
    market_ret = mean(rets) if rets else None
    out = {}
    for ind, codes in by.items():
        f = [factors[c] for c in codes]
        filed = [x["rev_yoy3"] for x in f if x.get("rev_yoy3") is not None]
        pairs = [(x["rev3"], x["rev3_ly"]) for x in f if x.get("rev3") is not None and x.get("rev3_ly") is not None]
        ly = sum(p[1] for p in pairs)
        own = [x["ret13w"] for x in f if x.get("ret13w") is not None]
        out[ind] = {
            "n": len(codes),
            "rev_breadth": _pct(sum(1 for y in filed if y > 0), len(filed)),
            "rev_yoy3": sum(p[0] for p in pairs) / ly * 100 - 100 if ly > 0 else None,
            "rel_ret13": mean(own) - market_ret if own and market_ret is not None else None,
            "trend_breadth": _pct(sum(1 for c in codes if trend_ok.get(c)), len(codes)),
            "score": 0.0, "unfavoured": False,
        }
    big = sorted(ind for ind, s in out.items() if s["n"] >= min_n)
    zs = {ind: [] for ind in big}
    for key in SECTOR_INPUTS:
        have = {ind: out[ind][key] for ind in big if out[ind][key] is not None}
        for ind, v in have.items():
            zs[ind].append(_z(v, list(have.values())))
    for ind in big:
        out[ind]["score"] = mean(zs[ind]) if zs[ind] else 0.0
    for ind in sorted(big, key=lambda i: (out[i]["score"], i))[:math.floor(len(big) * fraction)]:
        out[ind]["unfavoured"] = True
    return out


def composite(groups, sector, params=PARAMS):
    w = params["group_weights"]
    availability = sum(w[g] for g, v in groups.items() if v is not None)
    if availability < params["availability_min"]:
        return None, availability
    blend = sum(w[g] * v for g, v in groups.items() if v is not None) / availability
    return params["mix"][0] * blend + params["mix"][1] * sector, availability


def _group(z):
    out = {}
    for g, members in GROUPS.items():
        have = [(w, sign * z[v]) for v, w, sign in members if z.get(v) is not None]
        out[g] = sum(w * x for w, x in have) / sum(w for w, _ in have) if have else None
    return out


def _gate(s, track_, tags, f, non_general, params):
    """The track, L1, and L2 status for one security, or None when it reaches scoring."""
    if track_ != "full":
        return "watch_track", None
    if tags & EXCLUDE_TAGS:
        return "excluded_status", ",".join(sorted(tags & EXCLUDE_TAGS))
    if f.get("close") is None:
        return "excluded_no_quote", None
    if (f.get("adv20") or 0) < params["adv20_min"]:
        return "excluded_liquidity", None
    if f["close"] < params["close_min"]:
        return "excluded_price", None
    if s.industry in FINANCIAL_INDUSTRIES:
        return "excluded_financial", None
    if s.code in non_general:
        return "insufficient_data", "non_general_template"
    if f.get("op_income_recent") is None:              # profitability unknown: never passed through the loss test
        return "insufficient_data", "no_income"
    if f["op_income_recent"] <= 0:
        return "excluded_loss", None
    return None, None


def run_funnel(master, tracks, tags, factors, trend_ok, non_general, params=PARAMS):
    rows, survivors = {}, []
    for s in master:
        f, t = factors.get(s.code) or {}, tags.get(s.code, set())
        flags = set(t & FLAG_TAGS)
        flags |= {"one_off_revenue"} if f.get("one_off") or "one_off_revenue" in t else set()
        flags |= {"tib"} if s.board == "tib" else set()
        status, reason = _gate(s, tracks.get(s.key), t, f, non_general, params)
        rows[s.key] = dict({"code": s.code, "name": s.name, "industry": s.industry, "market": s.market,
                            "board": s.board, "status": status, "reason": reason, "flags": flags,
                            "sector_score": None, "availability": None, "composite": None, "rank": None,
                            "rank_trend": None, "trend_ok": trend_ok.get(s.code)},
                           **{f"z_{v}": None for v in VARIABLES}, **{f"g_{g}": None for g in GROUPS})
        if status is None:
            survivors.append(s)

    codes = [s.code for s in survivors]
    industry = {s.code: s.industry for s in survivors}
    z = {c: {} for c in codes}
    for v in VARIABLES:
        values = {c: factors[c][v] for c in codes if factors[c].get(v) is not None}
        if values:
            for c, x in zscores(winsorize(values, *params["winsor"]), industry, params["small_industry_n"],
                                params["z_clip"]).items():
                z[c][v] = x
    sectors = sector_scores(codes, industry, factors, trend_ok, params["small_industry_n"],
                            params["unfavoured_fraction"])

    scored = []
    for s in survivors:
        row, groups = rows[s.key], _group(z[s.code])
        row.update({f"z_{v}": x for v, x in z[s.code].items()}, **{f"g_{g}": x for g, x in groups.items()})
        row["sector_score"] = sectors[s.industry]["score"]
        row["composite"], row["availability"] = composite(groups, row["sector_score"], params)
        if row["composite"] is None:
            row["status"], row["reason"] = "insufficient_data", "availability"
        else:
            scored.append(row)
    scored.sort(key=lambda r: (-r["composite"], r["code"]))
    top = math.ceil(len(scored) * params["exception_top_pct"] / 100)

    ranked = []
    for i, row in enumerate(scored):
        if sectors[row["industry"]]["unfavoured"]:
            if i >= top:
                row["status"], row["reason"] = "excluded_sector", row["industry"]
                continue
            row["flags"].add("exception_lane")
        low = [g for g in GROUPS if row[f"g_{g}"] is not None and row[f"g_{g}"] < params["floor_z"]]
        if low:
            row["status"], row["reason"] = "excluded_floor", ",".join(low)
            continue
        row["status"] = "ranked"
        ranked.append(row)
    lanes = {True: 0, False: 0}
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
        lane = bool(row["trend_ok"])
        lanes[lane] += 1
        row["rank_trend"] = lanes[lane]
    for row in rows.values():
        row["flags"] = sorted(row["flags"])

    statuses = dict.fromkeys(STATUSES, 0)
    for row in rows.values():
        statuses[row["status"]] += 1
    full = sum(1 for s in master if tracks.get(s.key) == "full")
    l1 = full - sum(statuses[k] for k in ("excluded_status", "excluded_no_quote", "excluded_liquidity",
                                           "excluded_price"))
    counts = {"L0": len(master), "L0_full": full, "L0_watch": len(master) - full, "L1": l1, "L2": len(survivors),
              "L3": len(scored) - statuses["excluded_sector"], "L4": len(ranked), "statuses": statuses,
              "sectors": sectors}
    return rows, counts
