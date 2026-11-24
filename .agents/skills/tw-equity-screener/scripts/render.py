"""Render a week folder into the weekly page and register it in index.html and README.md.

Usage, from the repo root:
    python .agents/skills/tw-equity-screener/scripts/render.py scripts/screens/{yyyy}-w{ww} [--root .]

Every number on the page comes from the week folder and review.json. The page
contract is references/page-contract.md.
"""

import argparse
import html
import re
import sys
from pathlib import Path

from history import WEEK_FILES, read_folder
from shared import derive as dv

PAGE_DIR = Path("reports") / "screens"
DISCLAIMER = "本頁僅供研究參考，不構成任何投資建議。"
LAYERS = (
    ("L0", "全市場", "ISIN 普通股，含上市、上櫃、興櫃"),
    ("L0_full", "完整漏斗", "上市櫃且有 {min_history} 個交易日以上股價"),
    ("L0_watch", "觀察軌", "興櫃與交易日不足 {min_history} 日的新股"),
    ("L1", "可投資", "排除變更交易、管理、停牌；成交值與股價門檻"),
    ("L2", "排除紅旗", "排除金融保險、營業虧損"),
    ("L3", "產業閘門", "可用權重達 {availability_pct} 以上，且不在不利產業或走例外通道"),
    ("L4", "排名", "通過因子底線"),
    ("L5", "入圍", "可行動與左側觀察"),
    ("L6", "Tier A", "BUY 代理值高於 {tier_a_proxy}%、趨勢通過、無紅旗"),
)
KPIS = (("asof", "資料日"), ("universe", "全市場"), ("ranked", "排名"), ("shortlist", "入圍"), ("tier_a", "Tier A"),
        ("regime", "市場狀態"))
GROUPS = (("growth", "成長"), ("valuation", "評價"), ("quality", "品質"), ("flow", "籌碼"), ("persistence", "持續"))
FLAG_ZH = {"disposition": "處置", "attention": "注意", "periodic_auction": "分盤交易", "cash_offering": "現金增資",
           "one_off_revenue": "一次性營收", "tib": "創新板", "exception_lane": "例外通道"}
STATUS_ZH = {"watch_track": "觀察軌", "excluded_status": "狀態排除", "excluded_no_quote": "無報價",
             "excluded_liquidity": "流動性不足", "excluded_price": "股價過低", "excluded_financial": "金融保險",
             "excluded_loss": "營業虧損", "insufficient_data": "資料不足", "excluded_sector": "不利產業",
             "excluded_floor": "因子底線", "ranked": "已排名", "shortlist_actionable": "可行動",
             "shortlist_left_watch": "左側觀察"}
REASON_ZH = dict(STATUS_ZH, rank_out="排名滑出", trend_failed="趨勢轉弱", trend_passed="趨勢轉強", delisted="下市櫃")
LIST_ZH = {"actionable": "可行動", "left_watch": "左側觀察", "tier_a": "Tier A"}
MARKET_ZH = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}
SOURCES = "臺灣證券交易所、證券櫃檯買賣中心、公開資訊觀測站、FinMind"
FONTS = "https://fonts.googleapis.com/css2?family=Bevan&family=Archivo+Narrow:wght@400;700&display=swap"
esc = html.escape


# ----------------------------------------------------------------- values shared with check_screen

def week_parts(week):
    y, w = week.split("-w")
    return y, int(w)


def page_name(week):
    return f"tw-screen-{week}.html"


def page_rel(week):
    return f"{PAGE_DIR.as_posix()}/{page_name(week)}"


def fmt_int(n):
    return "無資料" if n is None else f"{n:,}"


def regime_label(r):
    """站上季線 / 跌破季線, with （轉折） when either regime input changed within 20 dates."""
    r = r or {}
    if r.get("above_ma60") is None:
        return "資料不足"
    base = "站上季線" if r["above_ma60"] else "跌破季線"
    return base + "（轉折）" if r.get("transition") else base


def kpi_values(funnel):
    c = funnel["counts"]
    return {"asof": funnel["asof"], "universe": fmt_int(c.get("L0")), "ranked": fmt_int(c.get("L4")),
            "shortlist": fmt_int(c.get("L5")), "tier_a": fmt_int(c.get("L6")), "regime": regime_label(funnel.get("regime"))}


def layer_values(funnel):
    return {layer: fmt_int(funnel["counts"].get(layer)) for layer, _, _ in LAYERS}


def numbers(params):
    """The method numbers the page prints, from funnel.json params (score.PARAMS plus the shortlist rules)."""
    sl = params["shortlist"]
    mix = params["mix"]
    return {"min_history": params["min_history"], "availability_pct": f"{params['availability_min'] * 100:.0f}%",
            "tier_a_proxy": f"{sl['tier_a_proxy']:g}", "small_n": params["small_industry_n"],
            "unfavoured_pct": f"{params['unfavoured_fraction'] * 100:.0f}%", "floor_z": f"{params['floor_z']:+g}",
            "mix": (f"{mix[0]:g}", f"{mix[1]:g}"), "adv20_m": f"{params['adv20_min'] / 1e6:,.0f}",
            "close_min": f"{params['close_min']:g}", "exception_pct": f"{params['exception_top_pct']:g}%",
            "enter": sl["enter"], "stay": sl["stay"], "cap": sl["cap"], "left_n": sl["left_n"]}


def card_telemetry(s):
    """(label, value, tone, wide) rows of the portal card, before the model row."""
    c, n = s["counts"], len(s["tier_a"])
    regime = s.get("regime") or {}
    tone = "tone-muted" if regime.get("above_ma60") is None else ("tone-ok" if regime["above_ma60"] else "tone-bad")
    return [("全市場", f"{fmt_int(c.get('L0'))} 檔", "", False), ("完整漏斗", f"{fmt_int(c.get('L0_full'))} 檔", "", False),
            ("入圍", f"{fmt_int(c.get('L5'))} 檔", "tone-accent", False),
            ("Tier A", f"{n} 檔", "tone-ok" if n else "tone-muted", False),
            ("市場狀態", regime_label(regime), tone, True)]


# ----------------------------------------------------------------- formatting

def signed(v, text=None):
    """A signed figure with its Taiwan-colour direction hook; 無資料 (no hook) for None."""
    if v is None:
        return '<span class="muted">無資料</span>'
    return f'<span class="num" data-dir="{dv.sign_dir(v)}">{esc(text if text is not None else dv.fmt_pct(v))}</span>'


def signed_int(v):
    return signed(v, f"{v:+d}" if v else "0") if v is not None else signed(None)


def fixed(v, dec=2, suffix=""):
    return "無資料" if v is None else f"{v:,.{dec}f}{suffix}"


def flags_zh(flags):
    return "、".join(FLAG_ZH.get(f, f) for f in flags or []) or "無"


CELL_CLASS = {True: ' class="num"', None: ' class="note"', False: ""}


def table(label, head, rows, empty):
    """A scrollable ruled table, or its one-line empty note.

    head is [(text, kind)] and rows are [(cells, row attrs)] with cells [(html, kind)]; kind True is a figure,
    None a wrapping note, False plain text."""
    if not rows:
        return f'<p class="empty">{esc(empty)}</p>'
    th = "".join(f'<th scope="col"{CELL_CLASS[bool(kind)]}>{esc(t)}</th>' for t, kind in head)
    body = []
    for cells, attrs in rows:
        tds = "".join(f"<td{CELL_CLASS[kind]}>{h}</td>" for h, kind in cells)
        body.append(f"<tr{attrs}>{tds}</tr>")
    return (f'<div class="table-wrap" role="region" aria-label="{esc(label)}" tabindex="0"><table>'
            f'<thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


# ----------------------------------------------------------------- sections

def _names(d):
    names = {r["code"]: r.get("name") for r in d["universe"]}
    for name in ("actionable", "left_watch"):
        names.update({r["code"]: r.get("name") for r in d["shortlist"].get(name, [])})
    return names


def sec_summary(d):
    f, k = d["funnel"], kpi_values(d["funnel"])
    y, w = week_parts(d["funnel"]["week"])
    c = f["counts"]
    cells = "".join(f'<div><dt>{esc(label)}</dt><dd class="{"regime" if key == "regime" else "num"}" '
                    f'data-kpi="{key}">{esc(k[key])}</dd></div>'
                    for key, label in KPIS)
    lead = (f"{esc(f['asof'])} 收盤，全市場 {fmt_int(c.get('L0'))} 檔普通股逐層篩選，排名 {fmt_int(c.get('L4'))} 檔，"
            f"入圍 {fmt_int(c.get('L5'))} 檔，其中 Tier A {fmt_int(c.get('L6'))} 檔。")
    return (f'<section id="summary"><h1>{y} 第 {w} 週台股選股</h1>'
            f'<p class="lead">{lead}</p><dl class="kpis">{cells}</dl></section>')


def stock(code, name):
    """The cell that names a row: the code in figures, then the name. Every table pins this column."""
    return f'<span class="num">{esc(code)}</span> {esc(name or "")}'.rstrip()


def sec_tier_a(d, notes):
    rows = {r["code"]: r for r in d["shortlist"].get("actionable", [])}
    out = []
    for code in d["shortlist"].get("tier_a", []):
        r = rows.get(code, {"code": code})
        cells = [(stock(code, r.get("name")), False), (f"<code>/tw-equity-report {esc(code)}</code>", False),
                 (signed(r.get("buy_proxy")), True), (fmt_int(r.get("rank")), True), (fixed(r.get("composite")), True),
                 (esc(r.get("industry") or ""), False), (esc(flags_zh(r.get("flags"))), False),
                 (esc(notes.get(code, "")), None)]
        out.append((cells, f' data-code="{esc(code)}"'))
    head = [("股票", False), ("下一步", False), ("BUY 代理值", True), ("排名", True), ("綜合分數", True), ("產業", False),
            ("標記", False), ("備註", False)]
    n = numbers(d["funnel"]["params"])
    return (f'<section id="tier-a"><h2>Tier A</h2>'
            f'<p class="lead">BUY 代理值高於 {n["tier_a_proxy"]}%、通過趨勢閘門且沒有紅旗的可行動名單，下一步跑完整個股報告。</p>'
            f'{table("Tier A 名單", head, out, "本週沒有 Tier A。")}</section>')


def _shortlist_rows(d, name, notes):
    diff = d["diff"]
    out = []
    for r in d["shortlist"].get(name, []):
        code, g = r["code"], r.get("groups") or {}
        cells = [(stock(code, r.get("name")), False), (fmt_int(r.get("rank")), True),
                 (fmt_int(r.get("rank_trend")), True), (esc(r.get("industry") or ""), False),
                 (fixed(r.get("composite")), True)]
        cells += [(fixed(g.get(key)), True) for key, _ in GROUPS]
        cells += [(signed(r.get("buy_proxy")), True), (esc(r.get("tier") or ""), False),
                  (signed_int(diff.get("rank_delta", {}).get(code)), True),
                  (fmt_int(diff.get("streak", {}).get(code)), True), (esc(flags_zh(r.get("flags"))), False),
                  (esc(notes.get(code, "")), None)]
        out.append((cells, ""))
    return out


def sec_shortlist(d, notes):
    head = [("股票", False), ("排名", True), ("趨勢內排名", True), ("產業", False), ("綜合分數", True)]
    head += [(label, True) for _, label in GROUPS]
    head += [("BUY 代理值", True), ("Tier", False), ("名次變化", True), ("連續週數", True), ("標記", False), ("備註", False)]
    n = numbers(d["funnel"]["params"])
    lead = (f"可行動：趨勢通過且趨勢內排名前 {n['enter']}，上週已入圍者在 {n['stay']} 名內保留，最多 {n['cap']} 檔。"
            f"左側觀察：趨勢未通過的前 {n['left_n']} 檔。")
    return (f'<section id="shortlist"><h2>入圍名單</h2><p class="lead">{lead}</p>'
            f'<h3>可行動</h3>{table("可行動名單", head, _shortlist_rows(d, "actionable", notes), "本週沒有可行動名單。")}'
            f'<h3>左側觀察</h3>{table("左側觀察名單", head, _shortlist_rows(d, "left_watch", notes), "本週沒有左側觀察名單。")}'
            f'</section>')


def sec_changes(d, review):
    names, diff, ev = _names(d), d["diff"], d["events"]
    entered = [([(stock(x["code"], names.get(x["code"])), False), (esc(LIST_ZH.get(x["list"], x["list"])), False),
                 (fmt_int(x.get("rank")), True)], "") for x in diff.get("entered", [])]
    exited = [([(stock(x["code"], names.get(x["code"])), False), (esc(LIST_ZH.get(x["list"], x["list"])), False),
                (esc(REASON_ZH.get(x["reason"], x["reason"])), False)], "") for x in diff.get("exited", [])]
    tags = [([(stock(x["code"], names.get(x["code"])), False), (esc(flags_zh(x.get("added"))), False),
              (esc(flags_zh(x.get("removed"))), False)], "") for x in ev.get("status_changes", [])]
    counts = (("新上市櫃", len(ev.get("new", []))), ("下市櫃", len(ev.get("exits", []))),
              ("轉板", len(ev.get("transfers", []))), ("更名", len(ev.get("renames", []))),
              ("代號重用", len(ev.get("code_reuse", []))), ("狀態變化", len(ev.get("status_changes", []))))
    facts = "".join(f'<div><dt>{label}</dt><dd class="num">{n:,}</dd></div>' for label, n in counts)
    zh = f'<p class="lead">{esc(review["events_zh"])}</p>' if review.get("events_zh") else ""
    heads = {"entered": [("股票", False), ("清單", False), ("排名", True)],
             "exited": [("股票", False), ("清單", False), ("原因", False)],
             "tags": [("股票", False), ("新增", False), ("移除", False)]}
    return (f'<section id="changes"><h2>本週變化</h2>{zh}<dl class="facts">{facts}</dl>'
            f'<h3>新進名單</h3>{table("新進名單", heads["entered"], entered, "本週沒有新進名單。")}'
            f'<h3>移出名單</h3>{table("移出名單", heads["exited"], exited, "本週沒有移出名單。")}'
            f'<h3>狀態標記變化</h3>{table("狀態標記變化", heads["tags"], tags, "本週沒有狀態標記變化。")}'
            f'</section>')


def sec_sectors(d):
    sectors = d["funnel"].get("sectors") or {}
    rows = []
    for ind, s in sorted(sectors.items(), key=lambda kv: (-(kv[1].get("score") or 0), kv[0])):
        cells = [(esc(ind), False), (fmt_int(s.get("n")), True), (fixed(s.get("rev_breadth"), 1, "%"), True),
                 (signed(s.get("rev_yoy3")), True),
                 (signed(s.get("rel_ret13"), None if s.get("rel_ret13") is None else dv.fmt_pct(s["rel_ret13"], suffix="")),
                  True),
                 (fixed(s.get("trend_breadth"), 1, "%"), True),
                 (signed(s.get("score"), None if s.get("score") is None else f"{s['score']:+.2f}"), True),
                 ("不利" if s.get("unfavoured") else "通過", False)]
        rows.append((cells, ""))
    head = [("產業", False), ("檔數", True), ("營收成長家數比", True), ("3 個月營收 YoY", True), ("13 週相對報酬（百分點）", True),
            ("趨勢通過比", True), ("產業分數", True), ("閘門", False)]
    n = numbers(d["funnel"]["params"])
    lead = (f"產業分數是下表各項輸入的 z 分數平均；分數最低的 {n['unfavoured_pct']} 產業列為不利，其成員只有綜合分數居全市場前 "
            f"{n['exception_pct']} 者能走例外通道。少於 {n['small_n']} 檔的產業不參與排序，分數記為 0。")
    return (f'<section id="sectors"><h2>產業閘門</h2><p class="lead">{lead}</p>'
            f'{table("產業閘門", head, rows, "本週沒有可評分的產業。")}</section>')


def sec_funnel(d):
    f = d["funnel"]
    c, values, n = f["counts"], layer_values(f), numbers(f["params"])
    top = c.get("L0") or 0
    items = []
    for layer, label, note in LAYERS:
        count = c.get(layer) or 0
        width = f"{count / top * 100:.1f}%" if top else "0%"
        cls = ' class="tier"' if layer == "L6" else ""
        items.append(f'<li{cls}><span class="layer"><strong>{esc(label)}</strong> '
                     f'<span class="muted">{esc(note.format(**n))}</span></span>'
                     f'<span class="num count" data-layer="{layer}">{values[layer]}</span>'
                     f'<span class="track" aria-hidden="true"><span class="bar" style="--w: {width}"></span></span></li>')
    statuses = [([(esc(STATUS_ZH.get(k, k)), False), (fmt_int(v), True)], "")
                for k, v in (f.get("statuses") or {}).items() if v]
    return (f'<section id="funnel"><h2>篩選漏斗</h2><ol class="ladder">{"".join(items)}</ol>'
            f'<h3>各狀態檔數</h3>{table("各狀態檔數", [("狀態", False), ("檔數", True)], statuses, "沒有狀態資料。")}</section>')


def sec_watch(d):
    w, n = d["watch"], numbers(d["funnel"]["params"])
    upcoming = [([(stock(u["code"], u.get("name")), False), (esc(MARKET_ZH.get(u.get("market"), "")), False),
                  (esc(u.get("applied") or "未定"), False), (esc(u.get("listing_date") or "未定"), False),
                  (fixed(u.get("price")), True)], "") for u in w.get("upcoming", [])]
    recent = [([(stock(r["code"], r.get("name")), False), (esc(MARKET_ZH.get(r.get("market"), "")), False),
                (esc(r.get("listing_date") or ""), False), (fmt_int(r.get("history_days")), True),
                (fmt_int(r.get("days_to_full")), True)], "") for r in w.get("recent", [])]
    emerging = [([(stock(e["code"], e.get("name")), False), (esc(e.get("industry") or ""), False),
                  (esc(e.get("latest_period") or ""), False), (signed(e.get("rev_yoy_med6")), True),
                  (" / ".join(fixed(y, 1, "%") for y in e.get("last3_yoy") or []), True), (fixed(e.get("avg")), True),
                  (fixed(e.get("last")), True), (fixed(e.get("volume"), 0), True),
                  (esc(e.get("applying_status") or "無"), False)], "") for e in w.get("emerging", [])]
    heads = {"upcoming": [("股票", False), ("市場", False), ("申請日", False), ("預計掛牌日", False), ("承銷價", True)],
             "recent": [("股票", False), ("市場", False), ("掛牌日", False), ("交易日數", True), ("距完整漏斗", True)],
             "emerging": [("股票", False), ("產業", False), ("營收月份", False), ("6 個月 YoY 中位數", True),
                          ("近 3 月 YoY", True), ("均價", True), ("最新價", True), ("成交量", True), ("申請狀態", False)]}
    no_recent = f"沒有交易日不足 {n['min_history']} 日的上市櫃股票。"
    return (f'<section id="watch"><h2>觀察軌</h2>'
            f'<h3>即將上市櫃</h3>{table("即將上市櫃", heads["upcoming"], upcoming, "目前沒有排隊中的申請案。")}'
            f'<h3>新上市櫃</h3>{table("新上市櫃", heads["recent"], recent, no_recent)}'
            f'<h3>興櫃營收亮點</h3>{table("興櫃營收亮點", heads["emerging"], emerging, "本週沒有符合條件的興櫃股票。")}'
            f'</section>')


def sec_forward(d):
    fw = d["funnel"].get("forward") or {}
    bc = fw.get("buy_conversion") or {}
    rate = "無資料" if bc.get("rate") is None else f"{bc['rate']:.1f}%"
    rows = [([(esc(LIST_ZH.get(s["list"], s["list"])), False), (fmt_int(s.get("horizon")), True),
              (fmt_int(s.get("weeks")), True), (fmt_int(s.get("names")), True), (fixed(s.get("hit_rate"), 1, "%"), True),
              (signed(s.get("median_excess_taiex")), True), (signed(s.get("median_excess_ew")), True),
              (fixed(s.get("turnover"), 1, "%"), True)], "") for s in fw.get("stats", [])]
    head = [("清單", False), ("持有週數", True), ("期數", True), ("檔數", True), ("勝率（對大盤）", True),
            ("超額報酬中位數（對大盤）", True), ("超額報酬中位數（對等權）", True), ("每週換手率", True)]
    return (f'<section id="forward"><h2>追蹤成效</h2>'
            f'<dl class="facts"><div><dt>BUY 轉換率</dt><dd class="num">{rate}</dd></div>'
            f'<div><dt>合格檔數</dt><dd class="num">{fmt_int(bc.get("eligible"))}</dd></div>'
            f'<div><dt>轉換檔數</dt><dd class="num">{fmt_int(bc.get("converted"))}</dd></div></dl>'
            f'<p class="lead">BUY 轉換率是主要指標：Tier A 名單在之後的個股報告中被評為買進、且動作不是左側觀察的比例。</p>'
            f'{table("追蹤成效", head, rows, "還沒有期滿的追蹤資料。")}</section>')


def sec_method(d):
    f = d["funnel"]
    p, r = f["params"], f.get("regime") or {}
    n = numbers(p)
    weights = "、".join(f"{label} {p['group_weights'][key] * 100:.0f}%" for key, label in GROUPS)
    facts = [
        ("方法版本", f.get("methodology_version") or ""),
        ("範圍", f"ISIN 全部普通股；上市櫃有 {n['min_history']} 個交易日以上股價者進完整漏斗，其餘進觀察軌"),
        ("可投資門檻", f"20 日成交值中位數 NT$ {n['adv20_m']} 百萬以上，收盤價 NT$ {n['close_min']} 以上"),
        ("因子權重", weights),
        ("綜合分數", f"{n['mix'][0]} × 因子群加權 z 分數 + {n['mix'][1]} × 產業分數；可用權重低於 {n['availability_pct']} 不評分"),
        ("因子底線", f"任一因子群 z 分數低於 {n['floor_z']} 即排除"),
        ("入圍", f"趨勢內排名前 {n['enter']} 入選，上週已入圍者 {n['stay']} 名內保留，最多 {n['cap']} 檔；"
                 f"左側觀察取趨勢未通過的前 {n['left_n']} 檔"),
        ("大盤", f"加權指數 {fixed(r.get('close'))}，季線 {fixed(r.get('ma60'))}，12 個月報酬 {fixed(r.get('ret12m'), 1, '%')}"),
    ]
    rows = "".join(f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>" for label, value in facts)
    return f'<section id="method"><h2>方法</h2><dl class="particulars">{rows}</dl></section>'


# ----------------------------------------------------------------- page

DARK = ("color-scheme: dark; --color-paper: oklch(17% 0.01 60); --color-paper-2: oklch(21.5% 0.012 60); "
        "--color-paper-3: oklch(25% 0.012 60); --color-ink: oklch(92% 0.028 88); --color-ink-2: oklch(84% 0.026 88); "
        "--color-muted: oklch(74% 0.02 80); --color-rule: oklch(38% 0.014 60); --color-accent: oklch(66% 0.18 33); "
        "--color-accent-ink: oklch(17% 0.01 60); --color-focus: oklch(66% 0.18 33); --color-selection: oklch(66% 0.18 33 / 0.35); "
        "--tw-up: oklch(68% 0.17 33); --tw-down: oklch(72% 0.14 150); --tw-flat: var(--color-muted);")

CSS = """/* Hallmark · shape: app screen · genre: editorial · theme: Broadside (deal 1/3, seed weekly-taiwan-equity-screener-9445·ce12e4cc·2026-11-24·r0)
 * nav: a top bar with the wordmark, the section links and the mode toggle; the earlier weeks close the page · signature: the funnel ladder from the whole market down to Tier A · states: every table prints a one-line empty note; the toggle stays disabled until its script runs · broadside: bill, inked in dark mode; Bevan over bold CJK heads, Six Caps dropped (no CJK glyphs)
 * axes: light/slab-serif/warm · posture: committed · contrast: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H3 E4 S4 R4 V3 · weakest: H, the fixed app scale keeps the bill's capitals small, so the five-point rules and the ladder carry the weight */
/* Hallmark · answered F25 · the stock column is pinned with position: sticky, and each wide table scrolls inside its own labelled region, as the page contract asks */
:root {
  color-scheme: light;
  --space-3xs: 2px; --space-2xs: 4px; --space-xs: 8px; --space-sm: 12px; --space-md: 16px; --space-lg: 24px; --space-xl: 40px; --space-2xl: 64px;
  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-md: 1rem; --text-lg: 1.2rem; --text-xl: 1.44rem; --text-2xl: 1.728rem; --text-3xl: 2.074rem;
  --dur-micro: 120ms; --container: 1280px; --gutter: 64px;
  --color-paper: oklch(92% 0.028 88); --color-paper-2: oklch(88.5% 0.032 88); --color-paper-3: oklch(85% 0.036 86);
  --color-ink: oklch(18% 0.01 50); --color-ink-2: oklch(30% 0.012 50); --color-muted: oklch(43% 0.02 62);
  --color-rule: oklch(75% 0.028 82);
  --color-accent: oklch(53% 0.19 33); --color-accent-ink: oklch(95.5% 0.018 88); --color-focus: oklch(53% 0.19 33);
  --color-selection: oklch(53% 0.19 33 / 0.28);
  --tw-up: oklch(53% 0.19 33); --tw-down: oklch(47% 0.12 150); --tw-flat: var(--color-muted);
  --font-display: "Bevan", "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", Georgia, serif;
  --font-body: "Archivo Narrow", "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", "Arial Narrow", ui-sans-serif, sans-serif;
  --font-code: ui-monospace, "Cascadia Mono", Consolas, monospace;
  --rule-hair: 1px; --rule-bar: 5px; --rule-frame: 3px; --tracking-display: 0.02em;
}
@media (prefers-color-scheme: dark) { :root:not([data-mode="light"]) { DARK } }
:root[data-mode="dark"] { DARK }
*, *::before, *::after { box-sizing: border-box; }
html, body { overflow-x: clip; }
html { scrollbar-color: var(--color-muted) var(--color-paper); scroll-padding-top: var(--space-xl); }
body { margin: 0; background: var(--color-paper); color: var(--color-ink); font-family: var(--font-body); font-size: var(--text-md); line-height: 1.55; -webkit-font-smoothing: antialiased; }
::selection { background: var(--color-selection); }
:focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }
a { color: var(--color-ink); text-decoration-thickness: 1px; text-underline-offset: 0.16em; transition: color var(--dur-micro) linear; }
a:hover { color: var(--color-accent); }
h1, h2, h3 { margin: 0; overflow-wrap: break-word; min-width: 0; text-wrap: balance; }
h1, h2 { font-family: var(--font-display); font-weight: 700; font-synthesis: none; text-transform: uppercase; }
h1 { font-size: var(--text-3xl); line-height: 1.15; letter-spacing: var(--tracking-display); max-width: 24ch; }
h2 { font-size: var(--text-xl); line-height: 1.2; border-top: var(--rule-bar) solid var(--color-ink); padding-top: var(--space-sm); margin-bottom: var(--space-md); }
h3 { font-family: var(--font-body); font-weight: 700; font-size: var(--text-md); margin: var(--space-lg) 0 var(--space-xs); }
p { margin: 0; text-wrap: pretty; }
.lead { max-width: 42em; margin-bottom: var(--space-md); }
.muted { color: var(--color-muted); }
.num { font-variant-numeric: tabular-nums; }
code { font-family: var(--font-code); font-size: var(--text-sm); }
.container { width: 100%; max-width: var(--container); margin-inline: auto; padding-inline: var(--gutter); }
.top { border-bottom: var(--rule-hair) solid var(--color-ink); }
.top .container { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-xs) var(--space-lg); padding-block: var(--space-sm); }
.wordmark { font-family: var(--font-display); font-weight: 700; font-synthesis: none; font-size: var(--text-lg); text-decoration: none; }
.sections { display: flex; gap: var(--space-md); overflow-x: auto; min-width: 0; flex: 1 1 24rem; }
.sections a { font-size: var(--text-sm); white-space: nowrap; }
.btn-mode { min-height: 44px; padding: 0 var(--space-md); border: var(--rule-frame) solid var(--color-ink); background: var(--color-ink); color: var(--color-paper); font: 700 var(--text-sm)/1 var(--font-body); cursor: pointer; transition: background-color var(--dur-micro) linear; }
.btn-mode:hover:not(:disabled) { background: var(--color-ink-2); }
.btn-mode:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-mode:active:not(:disabled) { transform: translateY(1px); }
.weeks { padding-block: var(--space-xl) 0; }
.weeks ul { display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-lg); margin: 0; padding: 0; list-style: none; }
.weeks li { min-height: 44px; display: flex; align-items: center; }
main section { padding-block: var(--space-xl) 0; }
#summary { padding-top: var(--space-lg); }
#summary h1 { margin-bottom: var(--space-sm); }
.kpis, .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 9rem), 1fr)); margin: 0; border-top: var(--rule-bar) solid var(--color-ink); }
.kpis div, .facts div { padding: var(--space-sm) var(--space-sm) var(--space-sm) 0; border-bottom: var(--rule-hair) solid var(--color-rule); }
dt { font-size: var(--text-sm); color: var(--color-muted); }
dd { margin: 0; }
.kpis dd, .facts dd { font-weight: 700; font-size: var(--text-2xl); line-height: 1.2; }
.kpis dd.regime { font-size: var(--text-lg); line-height: 1.6; }
.particulars { margin: 0; border-top: var(--rule-bar) solid var(--color-ink); }
.particulars div { display: grid; grid-template-columns: minmax(0, 9rem) minmax(0, 1fr); gap: var(--space-md); padding-block: var(--space-xs); border-bottom: var(--rule-hair) solid var(--color-rule); }
.particulars dt { font-weight: 700; color: var(--color-ink); }
.table-wrap { overflow-x: auto; border-top: var(--rule-bar) solid var(--color-ink); }
table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: var(--text-sm); }
th, td { padding: var(--space-xs) var(--space-sm); text-align: start; vertical-align: top; white-space: nowrap; border-top: var(--rule-hair) solid var(--color-rule); }
thead th { font-weight: 400; color: var(--color-muted); border-top: 0; }
tbody tr:first-child > * { border-top-color: var(--color-ink); }
tbody tr:last-child > * { border-bottom: var(--rule-hair) solid var(--color-rule); }
th:first-child, td:first-child { position: sticky; inset-inline-start: 0; z-index: 1; padding-inline-start: 0; background: var(--color-paper); }
th.num, td.num { text-align: end; font-variant-numeric: tabular-nums; }
td.note { white-space: normal; min-width: 14rem; }
.empty { padding-block: var(--space-sm); border-top: var(--rule-hair) solid var(--color-rule); color: var(--color-muted); }
[data-dir="up"] { color: var(--tw-up); }
[data-dir="down"] { color: var(--tw-down); }
[data-dir="flat"] { color: var(--tw-flat); }
.ladder { list-style: none; margin: 0; padding: 0; border-top: var(--rule-bar) solid var(--color-ink); }
.ladder li { display: grid; grid-template-columns: minmax(0, 22rem) minmax(0, 6rem) minmax(0, 1fr); gap: var(--space-md); align-items: center; padding-block: var(--space-xs); border-bottom: var(--rule-hair) solid var(--color-rule); }
.ladder .muted { font-size: var(--text-sm); }
.ladder .count { text-align: end; font-weight: 700; font-size: var(--text-lg); }
.ladder .track { display: block; min-width: 0; }
.ladder .bar { display: block; block-size: 14px; inline-size: max(2px, var(--w)); background: var(--color-ink); }
.ladder li.tier .bar { background: var(--color-accent); }
.ladder li.tier .count { color: var(--color-accent); }
footer { margin-top: var(--space-2xl); border-top: var(--rule-bar) solid var(--color-ink); padding-block: var(--space-md) var(--space-2xl); font-size: var(--text-sm); color: var(--color-muted); }
footer p + p { margin-top: var(--space-xs); }
@media (max-width: 60rem) { :root { --gutter: 24px; } }
@media (max-width: 40rem) {
  :root { --gutter: 16px; }
  .ladder li { grid-template-columns: minmax(0, 1fr) auto; }
  .ladder .track { grid-column: 1 / -1; }
  .particulars div { grid-template-columns: minmax(0, 1fr); gap: 0; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }
""".replace("DARK", DARK)

SCRIPT = """(function () {
  var root = document.documentElement;
  var btn = document.getElementById('mode-toggle');
  if (!btn) return;
  function cur() { return root.dataset.mode || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); }
  function label() { btn.textContent = cur() === 'dark' ? '切換淺色' : '切換深色'; btn.setAttribute('aria-pressed', cur() === 'dark' ? 'true' : 'false'); }
  btn.disabled = false;
  btn.addEventListener('click', function () {
    root.dataset.mode = cur() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('mode', root.dataset.mode); } catch (e) {}
    label();
  });
  label();
})();"""


def page_html(d, review, earlier):
    f = d["funnel"]
    week, asof = f["week"], f["asof"]
    y, w = week_parts(week)
    notes = review.get("notes") or {}
    gen = review.get("generation") or {}
    title = f"台股每週選股 {y} 第 {w} 週"
    links = "".join(f'<a href="#{s}">{label}</a>' for s, label in (
        ("tier-a", "Tier A"), ("shortlist", "入圍"), ("changes", "變化"), ("sectors", "產業"), ("funnel", "漏斗"),
        ("watch", "觀察軌"), ("forward", "成效"), ("method", "方法")))
    items = "".join(f'<li><a href="{esc(name)}">{esc(name[len("tw-screen-"):-len(".html")].replace("-w", "-W"))}</a></li>'
                    for name in earlier)
    weeks = f"<ul>{items}</ul>" if earlier else '<p class="empty">這是第一份週報，還沒有往期。</p>'
    body = "".join((sec_summary(d), sec_tier_a(d, notes), sec_shortlist(d, notes), sec_changes(d, review),
                    sec_sectors(d), sec_funnel(d), sec_watch(d), sec_forward(d), sec_method(d)))
    desc = (f"{asof} 收盤的台股每週選股：全市場 {fmt_int(f['counts'].get('L0'))} 檔，入圍 {fmt_int(f['counts'].get('L5'))} 檔，"
            f"Tier A {fmt_int(f['counts'].get('L6'))} 檔。")
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<script>try {{ var s = localStorage.getItem('mode'); if (s === 'dark' || s === 'light') document.documentElement.dataset.mode = s; }} catch (e) {{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<style>
{CSS}</style>
</head>
<body>
<header class="top">
  <div class="container">
    <a class="wordmark" href="../../index.html">台股選股週報</a>
    <nav class="sections" aria-label="本頁章節">{links}</nav>
    <button type="button" id="mode-toggle" class="btn-mode" aria-pressed="false" disabled>切換深色</button>
  </div>
</header>
<main class="container">
{body}
</main>
<nav class="container weeks" aria-label="往期週報">
  <h2>往期週報</h2>
  {weeks}
</nav>
<footer class="container">
  <p>資料來源：{SOURCES}。資料日 {esc(asof)}，方法版本 {esc(f.get('methodology_version') or '')}。</p>
  <p>生成模型：<span data-meta="model">{esc(str(gen.get('model') or ''))}</span>，推理強度 <span data-meta="effort">{esc(str(gen.get('effort') or ''))}</span>。</p>
  <p>{DISCLAIMER}</p>
  <p><a href="../../index.html">回到報告入口</a></p>
</footer>
<script>
{SCRIPT}
</script>
</body>
</html>
"""


# ----------------------------------------------------------------- portal

def summary_of(d, review):
    f = d["funnel"]
    return {"week": f["week"], "asof": f["asof"], "counts": f["counts"], "tier_a": d["shortlist"].get("tier_a", []),
            "regime": f.get("regime"), "generation": review.get("generation") or {}}


def card_html(s):
    y, w = week_parts(s["week"])
    c, codes, rel = s["counts"], s["tier_a"], page_rel(s["week"])
    gen = s.get("generation") or {}
    tier = f"Tier A {len(codes)} 檔：{'、'.join(codes)}。" if codes else "本週沒有 Tier A。"
    desc = (f"{s['asof']} 收盤，全市場 {fmt_int(c.get('L0'))} 檔普通股，完整漏斗 {fmt_int(c.get('L0_full'))} 檔，"
            f"入圍 {fmt_int(c.get('L5'))} 檔。{tier}大盤{regime_label(s.get('regime'))}。")
    tele = "\n".join(
        f'          <div class="telemetry-item{" telemetry-item--wide" if wide else ""}">{label}：'
        f'<span class="telemetry-val{" " + tone if tone else ""}">{esc(value)}</span></div>'
        for label, value, tone, wide in card_telemetry(s))
    badge = "artifact-badge--active" if codes else "artifact-badge--neutral"
    keywords = " ".join(["tw-equity-screener 選股 weekly screen taiwan equity funnel", s["week"], *codes])
    return f"""<article class="artifact-card" data-category="equity" data-keywords="{esc(keywords)}">
      <div>
        <div class="artifact-meta-top">
          <span class="artifact-category">equity screen</span>
          <span class="artifact-date">{esc(s['asof'])}</span>
        </div>
        <h2 class="artifact-heading">
          <a href="{rel}" class="artifact-title-link">台股每週選股 {y} 第 {w} 週</a>
        </h2>
        <p class="artifact-desc">
          {esc(desc)}
        </p>

        <div class="artifact-telemetry">
{tele}
          <div class="telemetry-item telemetry-item--wide">生成模型：<span class="telemetry-val" data-meta="model">{esc(str(gen.get('model') or ''))}</span> <span class="telemetry-val tone-muted" data-meta="effort">{esc(str(gen.get('effort') or ''))}</span></div>
        </div>
      </div>

      <div class="artifact-footer">
        <span class="artifact-badge {badge}">本週 Tier A：{len(codes)} 檔</span>
        <a href="{rel}" class="artifact-action" aria-label="閱讀 {y} 第 {w} 週台股選股週報">閱讀週報</a>
      </div>
    </article>"""


CARD_RE = re.compile(r'[ \t]*<article class="artifact-card"[^>]*data-keywords="tw-equity-screener[^"]*"[^>]*>.*?</article>\n?',
                     re.S)


def upsert_card(index_html, card):
    """Replace the screener card (dropping any duplicate), or insert it as the first card of the grid."""
    found = list(CARD_RE.finditer(index_html))
    if found:
        out, last = [], 0
        for i, m in enumerate(found):
            out.append(index_html[last:m.start()])
            if i == 0:
                out.append("    " + card + "\n")
            last = m.end()
        return "".join(out) + index_html[last:]
    m = re.search(r'<main class="artifacts-grid"[^>]*>\n?', index_html)
    if not m:
        raise ValueError('index.html has no <main class="artifacts-grid">')
    return index_html[:m.end()] + "    " + card + "\n" + index_html[m.end():]


def pages_base(readme):
    m = re.search(r"\[View Online\]\((https://[\w.-]+\.github\.io/[^/\s)]+/)", readme)
    if not m:
        raise ValueError("README.md has no GitHub Pages View Online link")
    return m.group(1)


def readme_row(week, base):
    y, w = week_parts(week)
    rel = page_rel(week)
    url = base + rel
    return (f"| **Equity Screen** | [台股每週選股 {y}-W{w:02d}]({url}) | [View Online]({url}) | "
            f"[`{rel}`](./{rel}) |")


def upsert_readme(readme, row):
    """Replace the Published Deliverables row holding reports/screens/, or insert row as the first data row."""
    lines = readme.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "## Published Deliverables"), None)
    sep = next((i for i in range(start, len(lines)) if lines[i].startswith("| :")), None) if start is not None else None
    if sep is None:
        raise ValueError("README.md has no Published Deliverables table")
    end = sep + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    hits = [i for i in range(sep + 1, end) if "reports/screens/" in lines[i]]
    if hits:
        lines[hits[0]] = row
        for i in reversed(hits[1:]):
            del lines[i]
    else:
        lines.insert(sep + 1, row)
    return "\n".join(lines)


def _rewrite(path, fn):
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    path.write_text(fn(raw.replace("\r\n", "\n")).replace("\n", nl), encoding="utf-8", newline="")


def load(folder):
    d = read_folder(folder)
    if d is None:
        raise FileNotFoundError(f"no week folder at {folder}")
    missing = [name for name in WEEK_FILES if Path(name).stem not in d]
    if missing:
        raise FileNotFoundError(f"{folder} lacks {', '.join(missing)}")
    return d, d.get("review") or {}


def render(folder, root):
    folder, root = Path(folder), Path(root)
    d, review = load(folder)
    week = d["funnel"]["week"]
    page = root / PAGE_DIR / page_name(week)
    page.parent.mkdir(parents=True, exist_ok=True)
    earlier = sorted((p.name for p in page.parent.glob("tw-screen-*.html") if p.name < page.name), reverse=True)
    page.write_text(page_html(d, review, earlier), encoding="utf-8", newline="")
    s = summary_of(d, review)
    _rewrite(root / "index.html", lambda t: upsert_card(t, card_html(s)))
    _rewrite(root / "README.md", lambda t: upsert_readme(t, readme_row(week, pages_base(t))))
    return page


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path, help="scripts/screens/{yyyy}-w{ww}")
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root holding index.html and README.md")
    args = ap.parse_args(argv)
    page = render(args.folder, args.root)
    print(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
