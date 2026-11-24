"""Weekly screen orchestrator: plan steps 0–6, from the trading calendar to the written week folder.

Usage: run.py [--asof YYYY-MM-DD] [--backfill] [--root .]

Exit codes:
  0  the week folder is written
  1  an invariant failed; nothing is written
  2  the FinMind quota is exhausted; cached work is kept, so a rerun resumes
  3  a source has not published `asof` yet
  4  a past `asof` lacks the ISIN lists or OpenAPI snapshots that a live run would have cached
  5  the daily tables need a backfill; rerun with --backfill
"""

import argparse
import sys
from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

import exchange as ex
import factors as fa
import history as hs
import mops
import score
import shared
import shortlist as sl
import snapshots as sn
import universe as un
import watch as wa
from cache import Fetcher, NoDataError

TRADING_DATE_DAYS = 450         # calendar days of TaiwanStockTradingDate before the anchor date
PANEL_DATES = 270               # trading dates of daily tables (the regime flag needs 270 closes)
FLOW_DATES = 30                 # the latest dates, which also fetch flows and holdings
BACKFILL_FREE = 30              # a run may fetch this many uncached dates without --backfill
REVENUE_MONTHS = 25             # the revenue surge needs 25 consecutive months
REQUEST_PAUSE_S = 3.0           # cache.Fetcher's default spacing between live requests
SHORTLIST = {"enter": 20, "stay": 40, "cap": 30, "left_n": 10}
L1_OUT = {"watch_track", "excluded_status", "excluded_no_quote", "excluded_liquidity", "excluded_price"}
SCORE_FIELDS = ("code", "industry", *(f"z_{v}" for v in score.VARIABLES), *(f"g_{g}" for g in score.GROUPS),
                "sector_score", "availability", "composite", "rank", "rank_trend", "trend_ok")
EXIT_INVARIANT, EXIT_QUOTA, EXIT_UNPUBLISHED, EXIT_SNAPSHOT, EXIT_BACKFILL = 1, 2, 3, 4, 5


def latest_month(asof):
    """The latest month every company must have filed revenue for (the deadline is the 10th): the previous month
    from the 11th on, else the month before that."""
    y, m, d = (int(x) for x in asof.split("-"))
    t = y * 12 + m - 1 - (1 if d >= 11 else 2)
    return t // 12, t % 12 + 1


def revenue_months(asof, n=REVENUE_MONTHS):
    """The n months up to latest_month(asof), oldest first."""
    y, m = latest_month(asof)
    t = y * 12 + m - 1
    return [((t - k) // 12, (t - k) % 12 + 1) for k in range(n - 1, -1, -1)]


def day_sources(with_flows):
    """The cache sources exchange.fetch_day reads for one date."""
    return ("twse_quotes", "tpex_quotes") + (("twse_t86", "tpex_insti", "twse_qfiis") if with_flows else ())


def uncached(fetcher, past, flow_dates, months, seasons):
    """(panel dates with an uncached table, uncached requests over the panel, revenue files, and income pages)."""
    missing = {d: [s for s in day_sources(d in flow_dates) if not fetcher.has(s, d)] for d in past}
    requests = sum(len(m) for m in missing.values())
    requests += sum(not fetcher.has(f"rev_{board}_{kind}", f"{y:04d}-{m:02d}")
                    for y, m in months for board, kind in mops.REVENUE_FILES)
    requests += sum(not fetcher.has(f"inc_{board}", f"{y:04d}-Q{s}") for y, s in seasons for board in mops.INCOME_BOARDS)
    return [d for d, m in missing.items() if m], requests


def load_master(fetcher, asof, live):
    """The ISIN master. Like the OpenAPI, the ISIN lists serve only today, so a past `asof` needs the copy an
    earlier live run cached."""
    if not live and not all(fetcher.has(f"isin{mode}", asof) for mode in un.ISIN_MODES):
        raise sn.SnapshotMissing(f"no ISIN lists cached for {asof}, and the ISIN pages serve only today")
    return un.load_master(fetcher, asof)


def securities(rows):
    """Security records rebuilt from a universe.csv, which keeps no ISIN or CFI code (events never reads them)."""
    return [un.Security(code=r["code"], name=r["name"] or "", isin="", listing_date=r["listing_date"],
                        market=r["market"], board=r["board"], industry=r["industry"] or "", cfi="") for r in rows]


def shares_of(day, code):
    """Shares outstanding: the TWSE holdings table, else the TPEx quote row."""
    for table in (day["holdings"] or {}, day["quotes"]):
        shares = (table.get(code) or {}).get("shares")
        if shares:
            return shares
    return None


def listed_row(r, list_name, deep, latest):
    """A shortlist row. `latest` is the code's latest revenue row; its 備註 note is kept for the Step 2 review."""
    proxy = sl.buy_proxy(deep)
    note = {"month": latest["month"], "note": latest["note"]} if latest and latest["note"] else None
    return {"code": r["code"], "name": r["name"], "industry": r["industry"], "rank": r["rank"],
            "rank_trend": r["rank_trend"], "composite": r["composite"],
            "groups": {g: r[f"g_{g}"] for g in score.GROUPS}, "flags": r["flags"], "deep": deep, "buy_proxy": proxy,
            "tier": sl.tier(list_name, r["trend_ok"], r["flags"], proxy), "command": f"/tw-equity-report {r['code']}",
            "revenue_note": note}


def universe_row(s, r, track, days, tags):
    return {"key": s.key, "code": s.code, "name": s.name, "market": s.market, "board": s.board,
            "industry": s.industry, "listing_date": s.listing_date, "track": track, "history_days": days,
            "status": r["status"], "reason": r["reason"], "flags": r["flags"], "tags": sorted(tags & hs.STATUS_TAGS)}


class PanelLookup:
    """The forward-tracking lookups over the price panel; a date before the panel gives None."""

    def __init__(self, panel, root):
        self.panel, self.root, self.l1 = panel, root, {}

    def _index(self, d):
        return bisect_right(self.panel.dates, d) - 1

    def close_at(self, code, d):
        for i in range(self._index(d), -1, -1):
            c = self.panel.close(code, i)
            if c is not None:
                return c
        return None

    def taiex_at(self, d):
        i = self._index(d)
        return self.panel.days[self.panel.dates[i]]["taiex"] if i >= 0 else None

    def universe_ret(self, week, end):
        """The equal-weight percent return to `end` of the stocks that passed L1 in `week`."""
        if week not in self.l1:
            path = hs.screens_dir(self.root) / week / "universe.csv"
            rows = hs.read_csv(path) if path.exists() else []
            self.l1[week] = ([r["code"] for r in rows if r["status"] not in L1_OUT], rows[0]["asof"] if rows else None)
        codes, start = self.l1[week]
        if start is None:
            return None
        rets = [(b / a - 1) * 100 for a, b in ((self.close_at(c, start), self.close_at(c, end)) for c in codes) if a and b]
        return mean(rets) if rets else None


def run(args, fetcher, finmind, build, today):
    root = Path(args.root)

    # Step 0: the trading calendar, asof, and the week.
    anchor = min(today, args.asof or today)
    start = (date.fromisoformat(anchor) - timedelta(days=TRADING_DATE_DAYS)).isoformat()
    dates = sorted({r["date"] for r in finmind("TaiwanStockTradingDate", "", start)})
    latest = ex.resolve_asof(fetcher, today, dates)
    asof = latest if args.asof is None else ex.resolve_asof(fetcher, args.asof, dates)
    live, week = asof == latest, hs.week_id(asof)
    past = [d for d in dates if d <= asof][-PANEL_DATES:]
    flow_dates = set(past[-FLOW_DATES:])
    months, seasons = revenue_months(asof), mops.due_seasons(asof)
    print(f"asof {asof}, week {week}, {'live' if live else 'archived snapshots'}", flush=True)
    missing, requests = uncached(fetcher, past, flow_dates, months, seasons)
    if len(missing) > BACKFILL_FREE and not args.backfill:
        pause = getattr(fetcher, "pause_s", REQUEST_PAUSE_S)
        print(f"backfill needed: {len(missing)} of {len(past)} trading dates are not cached; about {requests} "
              f"requests, {requests * pause / 60:.0f} minutes at {pause:g} s each. Rerun with --backfill.")
        return EXIT_BACKFILL

    # Step 1: the master, statuses, valuation, and universe events.
    master = load_master(fetcher, asof, live)
    info = finmind("TaiwanStockInfo", "", "")
    snaps = {name: sn.snapshot(fetcher, name, asof, live) for name in sn.OPENAPI}
    val = ex.fetch_valuation(fetcher, asof)
    pipeline = sn.parse_pipeline(asof, snaps)
    prev_week = hs.previous_week(root, week)
    prev = hs.read_week(root, prev_week) if prev_week else None
    events = un.events(securities(prev["universe"]) if prev else None, master, pipeline["delisted"])

    # Step 2: the daily tables, newest first. A date before asof that neither board traded is a closure the calendar
    # still lists (a typhoon day): it is skipped and never cached, and the next older date takes its place.
    print(f"daily tables: {len(past)} dates, {len(missing)} not cached", flush=True)
    days, closed = {}, []
    for i, d in enumerate(reversed([d for d in dates if d <= asof]), 1):
        if len(days) == PANEL_DATES:
            break
        try:
            days[d] = ex.fetch_day(fetcher, d, len(days) < FLOW_DATES)
        except NoDataError:
            if d == asof or ex.traded(fetcher, d):
                raise
            closed.append(d)
        if len(missing) > BACKFILL_FREE and i % 50 == 0:
            print(f"daily tables: {len(days)}/{len(past)}", flush=True)
    past, closed = sorted(days), sorted(closed)
    if closed:
        print(f"skipped {len(closed)} calendar date{'s' * (len(closed) > 1)} that neither board traded: "
              f"{', '.join(closed)}", flush=True)
    panel = fa.Panel(dates=past, days=days)
    day = days[asof]

    # Step 3: monthly revenue and quarterly income.
    by_month = {ym: mops.fetch_revenue(fetcher, *ym, asof) for ym in months}
    rev = mops.revenue_rows(by_month)
    latest_rows = {r["code"]: dict(r, month=f"{y:04d}-{m:02d}") for (y, m) in sorted(by_month)
                   for r in by_month[(y, m)] if r["revenue"] is not None}
    incomes = [mops.fetch_income(fetcher, y, s, asof) for y, s in seasons]
    quarters = mops.standalone({ys: general for ys, (general, _) in zip(seasons, incomes)})
    non_general = set().union(*(other for _, other in incomes)) - set(incomes[-1][0])

    # Step 4: factors, trend, tags, and the L0–L4 funnel.
    history = {s.code: fa.history_days(panel, s.code) for s in master}
    tracks = {s.key: score.track(s, history[s.code]) for s in master}
    full = sorted({s.code for s in master if tracks[s.key] == "full"})
    factors = {c: fa.stock_factors(c, panel, rev.get(c, []), latest_rows.get(c), quarters.get(c, []), val.get(c),
                                   shares_of(day, c), months[-1]) for c in full}
    for c, p in fa.persistence(panel, full).items():
        factors[c]["persist13"] = p
    trend_ok = {c: shared.trend_gate(fa.price_rows(panel, c))[1]["ok"] for c in full}
    tags = sn.parse_statuses(asof, snaps)
    for c in day["managed"]:
        tags.setdefault(c, set()).add("managed")
    rows, counts = score.run_funnel(master, tracks, tags, factors, trend_ok, non_general)
    sectors = counts.pop("sectors")
    counts.pop("statuses")

    # Step 5: the L5 shortlist, deep metrics, L6 tiers, the watch track, and the regime.
    ranked = [r for r in rows.values() if r["status"] == "ranked"]
    prev_actionable = {r["code"] for r in prev["shortlist"]["actionable"]} if prev else set()
    lists = dict(zip(hs.LISTS, sl.select(ranked, prev_actionable, **SHORTLIST)))
    by_code = {r["code"]: r for r in ranked}
    shortlist = {name: [listed_row(by_code[c], name, sl.deep_metrics(c, asof, fetcher.root, build), latest_rows.get(c))
                        for c in codes]
                 for name, codes in lists.items()}
    shortlist["tier_a"] = [r["code"] for r in shortlist["actionable"] if r["tier"] == "A"]
    for name, codes in lists.items():
        for c in codes:
            by_code[c]["status"] = f"shortlist_{name}"
    statuses = dict.fromkeys(score.STATUSES, 0)
    for r in rows.values():
        statuses[r["status"]] += 1
    counts.update(L5=sum(len(codes) for codes in lists.values()), L6=len(shortlist["tier_a"]))
    emerging_rev = {s.code: rev[s.code] for s in master if s.market == "emerging" and s.code in rev}
    watch = wa.watch_tables(master, tracks, history, pipeline, emerging_rev, asof)
    regime = wa.regime([(d, days[d]["taiex"]) for d in past])

    # Step 6: changes, invariants, the week folder, and forward tracking.
    on_list = {c: name for name, codes in lists.items() for c in codes}
    universe = [universe_row(s, rows[s.key], tracks[s.key], history[s.code], tags.get(s.code, set())) for s in master]
    scores = [dict({"key": key}, **{k: r[k] for k in SCORE_FIELDS}, list=on_list.get(r["code"]))
              for key, r in rows.items() if r["availability"] is not None]
    cur_tags = {s.code: tags.get(s.code, set()) for s in master}
    events["status_changes"] = hs.status_changes(hs.tags_from_universe(prev["universe"]) if prev else None, cur_tags)
    events["reconciliation"] = un.reconcile(master, set(day["quotes"]), info)
    reports = hs.report_index(root)
    diff = hs.diff(prev, {"shortlist": shortlist, "scores": scores, "universe": universe}, reports)
    errors = hs.check_invariants(len(master), statuses, len(prev["universe"]) if prev else None, events)
    if errors:
        for e in errors:
            print(f"invariant failed: {e}")
        return EXIT_INVARIANT

    forward_path = hs.screens_dir(root) / "forward.csv"
    new_rows = [{"list": name, "code": c, "close": panel.close(c, len(past) - 1)}
                for name, codes in (("tier_a", shortlist["tier_a"]), ("actionable", lists["actionable"])) for c in codes]
    # Rows of later weeks are left out: the panel ends at asof, so it cannot price their horizons.
    kept = [r for r in (hs.read_csv(forward_path) if forward_path.exists() else [])
            if r["week"] != week and r["asof"] <= asof]
    tracked = kept + [dict(r, week=week, asof=asof) for r in new_rows]
    look = PanelLookup(panel, root)
    funnel = {"counts": counts, "statuses": statuses, "sectors": sectors, "regime": regime, "closed_dates": closed,
              "params": dict(score.PARAMS, shortlist=dict(SHORTLIST, tier_a_proxy=sl.TIER_A_PROXY)),
              "forward": {"stats": hs.forward_stats(tracked, look.close_at, look.taiex_at, look.universe_ret),
                          "buy_conversion": hs.buy_conversion(tracked, reports)}}
    folder = hs.write_week(root, week, {"universe.csv": universe, "scores.csv": scores, "events.json": events,
                                        "funnel.json": funnel, "shortlist.json": shortlist, "watch.json": watch,
                                        "diff.json": diff}, asof)
    hs.append_forward(forward_path, week, asof, new_rows)
    print(f"week folder: {folder.as_posix()}")
    print("funnel: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    return 0


def parse_args(argv):
    p = argparse.ArgumentParser(description="Run the weekly Taiwan equity screen and write its week folder.")
    p.add_argument("--asof", type=lambda s: date.fromisoformat(s).isoformat(),
                   help="screen as of this date, YYYY-MM-DD (default: the latest published trading date)")
    p.add_argument("--backfill", action="store_true",
                   help=f"allow fetching more than {BACKFILL_FREE} uncached trading dates")
    p.add_argument("--root", default=".", help="the repository root (default: .)")
    return p.parse_args(argv)


def main(argv=None, *, fetcher=None, finmind=shared.finmind_fetch, build=shared.fetch_build, today=None):
    args = parse_args(argv)
    try:
        return run(args, fetcher or Fetcher(), finmind, build, today or date.today().isoformat())
    except shared.QuotaError as e:
        print(f"FinMind quota exhausted: {e}")
        return EXIT_QUOTA
    except (NoDataError, shared.NotPublishedError) as e:
        print(f"not published yet: {e}")
        return EXIT_UNPUBLISHED
    except sn.SnapshotMissing as e:
        print(f"no archived snapshot: {e}")
        return EXIT_SNAPSHOT


if __name__ == "__main__":
    sys.exit(main())
