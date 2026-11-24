"""Week folders under scripts/screens/, the week-over-week diff, invariants, and forward tracking.

Every JSON file in a week folder starts with asof, week, and methodology_version,
and every CSV row starts with those three columns, so any one file identifies its run.
"""

import csv
import io
import json
import re
import shutil
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from snapshots import EXCLUDE_TAGS, FLAG_TAGS

METHODOLOGY_VERSION = "1.0"
STAMP = ("asof", "week", "methodology_version")
WEEK_RE = re.compile(r"^\d{4}-w\d{2}$")
TEXT_COLUMNS = {"asof", "week", "methodology_version", "key", "code", "name", "market", "board", "industry",
                "listing_date", "track", "status", "reason", "list"}
LIST_COLUMNS = {"flags", "tags"}
STATUS_TAGS = EXCLUDE_TAGS | FLAG_TAGS          # board and lane flags (tib, exception_lane) are not status tags
LISTS = ("actionable", "left_watch")
WEEK_FILES = ("universe.csv", "scores.csv", "events.json", "funnel.json", "shortlist.json", "watch.json",
              "diff.json")
FORWARD_FIELDS = ("week", "asof", "list", "code", "close")
FORWARD_LISTS = ("tier_a", "actionable")
HORIZONS = (4, 13, 26, 52)
REPORT_RE = re.compile(r"^([0-9A-Z]{4,6})-.+-(\d{8})\.html$")
TAG_RE = re.compile(r"<[^>]+>")


def week_id(asof):
    y, w, _ = date.fromisoformat(asof).isocalendar()
    return f"{y}-w{w:02d}"


def screens_dir(root):
    return Path(root) / "scripts" / "screens"


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (list, set, tuple)):
        return ";".join(sorted(str(x) for x in v))
    return str(v)


def _csv_text(rows, stamp):
    fields = list(STAMP)
    for r in rows:
        fields += [k for k in r if k not in fields]
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        full = dict(r, **stamp)
        w.writerow([_cell(full.get(k)) for k in fields])
    return buf.getvalue()


def write_week(root, week, files, asof, version=METHODOLOGY_VERSION):
    """Write scripts/screens/{week}/ under root, replacing the folder's previous contents entirely.

    `files` maps a file name to a dict (.json) or a list of row dicts (.csv)."""
    stamp = {"asof": asof, "week": week, "methodology_version": version}
    folder = screens_dir(root) / week
    staging = folder.with_name(f".{week}.tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for name, obj in files.items():
        if name.endswith(".json"):
            text = json.dumps(dict(stamp, **{k: v for k, v in obj.items() if k not in STAMP}),
                              ensure_ascii=False, indent=1, default=sorted) + "\n"
        elif name.endswith(".csv"):
            text = _csv_text(obj, stamp)
        else:
            raise ValueError(f"unsupported week file: {name}")
        (staging / name).write_text(text, encoding="utf-8", newline="")
    shutil.rmtree(folder, ignore_errors=True)
    staging.rename(folder)
    return folder


def _parse(column, v):
    if column in LIST_COLUMNS:
        return [x for x in v.split(";") if x]
    if v == "":
        return None
    if column in TEXT_COLUMNS:
        return v
    if v in ("True", "False"):
        return v == "True"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: _parse(k, v) for k, v in row.items()} for row in csv.DictReader(f)]


def read_week(root, week):
    """A written week folder as {stem: parsed content}, or None when the folder does not exist."""
    return read_folder(screens_dir(root) / week)


def read_folder(folder):
    """Every .json and .csv file in a week folder, parsed, keyed by file stem; None when the folder is absent."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    out = {}
    for p in sorted(folder.iterdir()):
        if p.suffix == ".json":
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        elif p.suffix == ".csv":
            out[p.stem] = read_csv(p)
    return out


def previous_week(root, week):
    d = screens_dir(root)
    names = [p.name for p in d.iterdir() if p.is_dir() and WEEK_RE.match(p.name) and p.name < week] if d.is_dir() else []
    return max(names, default=None)


def tags_from_universe(rows):
    """Status tags per code from a universe.csv: the `tags` column when present, else `flags` plus the
    exclusion tags held in `reason` for excluded_status rows."""
    out = {}
    for r in rows:
        if r.get("tags") is not None:
            tags = set(r["tags"])
        else:
            tags = set(r.get("flags") or [])
            if r.get("status") == "excluded_status" and r.get("reason"):
                tags |= set(r["reason"].split(","))
        out[r["code"]] = tags & STATUS_TAGS
    return out


def status_changes(prev_tags, cur_tags):
    if prev_tags is None:
        return []
    out = []
    for code in sorted(set(prev_tags) | set(cur_tags)):
        a, b = set(prev_tags.get(code, ())) & STATUS_TAGS, set(cur_tags.get(code, ())) & STATUS_TAGS
        if a != b:
            out.append({"code": code, "added": sorted(b - a), "removed": sorted(a - b)})
    return out


def check_invariants(master_n, statuses, prev_master_n, events):
    errors = []
    if sum(statuses.values()) != master_n:
        errors.append(f"statuses sum to {sum(statuses.values())}, master has {master_n}")
    if prev_master_n is not None and master_n - prev_master_n != len(events["new"]) - len(events["exits"]):
        errors.append(f"master moved {master_n - prev_master_n} but events net "
                      f"{len(events['new']) - len(events['exits'])} (new {len(events['new'])}, "
                      f"exits {len(events['exits'])})")
    return errors


def _members(week):
    return {name: [r["code"] for r in week["shortlist"].get(name, [])] for name in LISTS}


def _exit_reason(code, name, cur, scores, status):
    if code not in status:
        return "delisted"
    if status[code] != "ranked":
        return status[code]
    trend = (scores.get(code) or {}).get("trend_ok")
    if name == "actionable" and trend is False:
        return "trend_failed"
    if name == "left_watch" and trend is True:
        return "trend_passed"
    return "rank_out"


def diff(prev, cur, reports):
    """Week-over-week changes. A week bundle holds `shortlist`, `scores` rows, `universe` rows, and its `diff`."""
    now, scores = _members(cur), {r["code"]: r for r in cur["scores"]}
    status = {r["code"]: r["status"] for r in cur["universe"]}
    listed = [c for name in LISTS for c in now[name]]
    before = _members(prev) if prev else {name: [] for name in LISTS}
    old = {r["code"]: r for r in prev["scores"]} if prev else {}
    old_streak = ((prev or {}).get("diff") or {}).get("streak") or {}
    out = {"entered": [], "exited": [], "rank_delta": {}, "streak": {}, "composite_delta": {}, "reports": {}}
    for name in LISTS:
        for c in now[name]:
            if c not in before[name]:
                out["entered"].append({"code": c, "list": name, "rank": (scores.get(c) or {}).get("rank")})
        for c in before[name]:
            if c not in now[name]:
                out["exited"].append({"code": c, "list": name, "reason": _exit_reason(c, name, cur, scores, status)})
    was_listed = {c for name in LISTS for c in before[name]}
    for c in dict.fromkeys(listed):
        out["streak"][c] = (old_streak.get(c, 0) if c in was_listed else 0) + 1
        a, b = old.get(c) or {}, scores.get(c) or {}
        if a.get("rank") is not None and b.get("rank") is not None:
            out["rank_delta"][c] = a["rank"] - b["rank"]
        if a.get("composite") is not None and b.get("composite") is not None:
            out["composite_delta"][c] = b["composite"] - a["composite"]
        if c in reports:
            out["reports"][c] = reports[c]
    return out


def _kpi(html, name):
    m = re.search(rf'data-kpi="{name}"[^>]*>(.*?)</', html, re.S)
    text = TAG_RE.sub("", m.group(1)).strip() if m else ""
    return text or None


def report_index(repo_root):
    """The newest dated tw-equity-report page per code, with its rating and action."""
    out = {}
    for p in sorted((Path(repo_root) / "reports" / "equity").glob("*.html")):
        m = REPORT_RE.match(p.name)
        if not m:
            continue
        code, ymd = m.groups()
        d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        if code in out and out[code]["date"] >= d:
            continue
        html = p.read_text(encoding="utf-8")
        out[code] = {"path": f"reports/equity/{p.name}", "date": d, "rating": _kpi(html, "rating"),
                     "action": _kpi(html, "action")}
    return out


def append_forward(path, week, asof, rows):
    """Rewrite forward.csv without `week`'s earlier rows, then append `rows`."""
    path = Path(path)
    kept = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            kept = [r for r in csv.DictReader(f) if r["week"] != week]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FORWARD_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(kept)
        w.writerows({"week": week, "asof": asof, "list": r["list"], "code": r["code"], "close": r["close"]}
                    for r in rows)


def _by_week(rows, name):
    weeks = {}
    for r in rows:
        if r["list"] == name:
            weeks.setdefault((r["week"], r["asof"]), []).append(r)
    return dict(sorted(weeks.items()))


def _turnover(weeks):
    sets = [{r["code"] for r in names} for names in weeks.values()]
    shares = [(1 - len(a & b) / len(a)) * 100 for a, b in zip(sets, sets[1:]) if a]
    return sum(shares) / len(shares) if shares else None


def forward_stats(rows, close_at, taiex_at, universe_ret):
    """Per list and fully elapsed horizon: hit rate vs TAIEX and median excess returns, in percent.

    close_at(code, date) and taiex_at(date) give the close on or before a date; universe_ret(week, date) is the
    equal-weight percent return of that week's L1 stocks to the date. A name with no later close is skipped, and
    so is a cohort whose TAIEX close at either end is unknown (taiex_at gives None before the price history)."""
    if not rows:
        return []
    latest = max(r["asof"] for r in rows)
    out = []
    for name in FORWARD_LISTS:
        weeks = _by_week(rows, name)
        turnover = _turnover(weeks)
        for h in HORIZONS:
            cohorts, hits, ex_taiex, ex_ew = 0, 0, [], []
            for (week, asof), names in weeks.items():
                end = (date.fromisoformat(asof) + timedelta(weeks=h)).isoformat()
                if end > latest:
                    continue
                t0, t1 = taiex_at(asof), taiex_at(end)
                if not t0 or not t1:
                    continue                    # the cohort starts before the price history the run holds
                cohorts += 1
                bench = (t1 / t0 - 1) * 100
                ew = universe_ret(week, end)
                for r in names:
                    c1 = close_at(r["code"], end)
                    if c1 is None:
                        continue
                    ret = (c1 / float(r["close"]) - 1) * 100
                    hits += ret > bench
                    ex_taiex.append(ret - bench)
                    if ew is not None:
                        ex_ew.append(ret - ew)
            if cohorts and ex_taiex:
                out.append({"list": name, "horizon": h, "weeks": cohorts, "names": len(ex_taiex),
                            "hit_rate": hits / len(ex_taiex) * 100, "median_excess_taiex": median(ex_taiex),
                            "median_excess_ew": median(ex_ew) if ex_ew else None, "turnover": turnover})
    return out


def buy_conversion(rows, reports):
    """Tier A names later covered by a report: how many the report rated 買進 with an action other than 左側觀察."""
    eligible = converted = 0
    for r in rows:
        rep = reports.get(r["code"])
        if r["list"] != "tier_a" or not rep or rep["date"] < r["asof"]:
            continue
        eligible += 1
        converted += rep.get("rating") == "買進" and rep.get("action") != "左側觀察"
    return {"eligible": eligible, "converted": converted, "rate": converted / eligible * 100 if eligible else None}
