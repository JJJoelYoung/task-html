"""Date-addressable TWSE and TPEx daily tables, valuation, and `asof` resolution.

Every table goes through `cache.Fetcher`, keyed by its ISO date. A response
counts only when it carries rows: the exchanges answer a holiday or an
unpublished date with a no-data status or an empty table, and caching either
would poison that date (Review Focus 2). Valuation tables must also be dated
the requested day, because those endpoints can answer with another day.
"""

import json

from cache import NoDataError

TWSE_QUOTES = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json"
TWSE_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json"
TWSE_QFIIS = "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={ymd}&selectType=ALLBUT0999&response=json"
TPEX_QUOTES = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={y}/{m}/{d}&id=&response=json"
TPEX_INSTI = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={y}/{m}/{d}&response=json"
TWSE_PER = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ymd}&selectType=ALL&response=json"
TPEX_PER = ("https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php"
            "?l=zh-tw&o=json&d={ry}/{m}/{d}")

TAIEX_NAME = "發行量加權股價指數"
ASOF_STEP_BACKS = 3
QUOTE_KEYS = ("open", "high", "low", "close", "volume", "value")
TWSE_QUOTE_SPEC = tuple(zip(QUOTE_KEYS, ("開盤價", "最高價", "最低價", "收盤價", "成交股數", "成交金額")))
TPEX_QUOTE_SPEC = tuple(zip(QUOTE_KEYS, ("開盤", "最高", "最低", "收盤", "成交股數", "成交金額(元)"))) + (
    ("shares", "發行股數"),)
QFIIS_SPEC = (("shares", "發行股數"), ("foreign_pct", "全體外資及陸資持股比率"))
VALUATION_SPEC = (("per", "本益比"), ("pbr", "股價淨值比"), ("yield", "殖利率(%)"))
T86_FIELDS = ("外陸資買賣超股數(不含外資自營商)", "外資自營商買賣超股數", "投信買賣超股數", "自營商買賣超股數")
INSTI_CELLS = (10, 13, 22, 23)   # foreign incl. dealers, trust, dealer total, three-institution total


def num(s):
    """A float from an exchange cell. Commas and spaces are stripped; "", "-", "--", "---", "N/A", and any
    other non-numeric text give None; numbers pass through."""
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def url_for(template, day):
    """Fill a URL template for an ISO date: {ymd}, {y}/{m}/{d}, or the ROC year {ry}."""
    y, m, d = day.split("-")
    return template.format(ymd=y + m + d, y=y, m=m, d=d, ry=int(y) - 1911)


def _load(text):
    try:
        j = json.loads(text)
    except ValueError:
        return None
    return j if isinstance(j, dict) else None


def twse_ok(text):
    """TWSE answered OK with at least one row (top-level `data` or a table's `data`)."""
    j = _load(text)
    if j is None or j.get("stat") != "OK":
        return False
    return bool(j.get("data")) or any(isinstance(t, dict) and t.get("data") for t in j.get("tables") or [])


def tpex_ok(text):
    """TPEx answered ok with rows in its first table."""
    j = _load(text)
    if j is None or str(j.get("stat", "")).lower() != "ok":
        return False
    tables = j.get("tables")
    return isinstance(tables, list) and bool(tables) and isinstance(tables[0], dict) and bool(tables[0].get("data"))


def _dated(ok, ymd):
    return lambda text: ok(text) and _load(text).get("date") == ymd


def _fetch(fetcher, source, template, day, validate):
    return json.loads(fetcher.get(source, day, url_for(template, day), encoding="utf-8", validate=validate))


def _table(j, title_part):
    for t in j.get("tables") or []:
        if isinstance(t, dict) and title_part in (t.get("title") or ""):
            return t
    raise ValueError(f"no table titled {title_part!r}")


def _columns(fields, names):
    """The index of each named field (names compared stripped); a missing name raises ValueError."""
    stripped = [str(f).strip() for f in fields]
    missing = [n for n in names if n not in stripped]
    if missing:
        raise ValueError(f"fields {missing} not in {stripped}")
    return {n: stripped.index(n) for n in names}


def _by_code(fields, data, code_field, spec):
    """{code: {key: num(cell)}} for spec pairs (key, field name)."""
    col = _columns(fields, [code_field] + [name for _, name in spec])
    return {str(row[col[code_field]]).strip(): {key: num(row[col[name]]) for key, name in spec} for row in data}


def parse_twse_quotes(j):
    t = _table(j, "每日收盤行情")
    return _by_code(t["fields"], t["data"], "證券代號", TWSE_QUOTE_SPEC)


def parse_taiex(j):
    t = j["tables"][0]
    col = _columns(t["fields"], ["指數", "收盤指數"])
    for row in t["data"]:
        if str(row[col["指數"]]).strip() == TAIEX_NAME:
            return num(row[col["收盤指數"]])
    raise ValueError(f"no {TAIEX_NAME} row in {t.get('title')!r}")


def parse_tpex_quotes(j):
    """Quotes from 上櫃股票行情 plus 管理股票, whose stocks trade outside the main table, and the managed codes."""
    t = _table(j, "上櫃股票行情")
    managed = _table(j, "管理股票")
    quotes = _by_code(t["fields"], t["data"], "代號", TPEX_QUOTE_SPEC)
    if managed["data"]:
        quotes.update(_by_code(managed["fields"], managed["data"], "代號", TPEX_QUOTE_SPEC))
    code = _columns(managed["fields"], ["代號"])["代號"]
    return quotes, {str(row[code]).strip() for row in managed["data"]}


def parse_t86(j):
    col = _columns(j["fields"], ("證券代號",) + T86_FIELDS)
    out = {}
    for row in j["data"]:
        foreign, dealer_self, trust, dealer = (num(row[col[name]]) for name in T86_FIELDS)
        out[str(row[col["證券代號"]]).strip()] = {"foreign": foreign + dealer_self, "trust": trust, "dealer": dealer}
    return out


def parse_tpex_insti(j):
    """By position, since the field names repeat. The three-institution total guards the layout."""
    out = {}
    for row in j["tables"][0]["data"]:
        code = str(row[0]).strip()
        foreign, trust, dealer, total = (num(row[i]) for i in INSTI_CELLS)
        if total != foreign + trust + dealer:
            raise ValueError(f"TPEx insti layout changed: {code} total {row[23]!r} is not cells 10 + 13 + 22")
        out[code] = {"foreign": foreign, "trust": trust, "dealer": dealer}
    return out


def parse_qfiis(j):
    return _by_code(j["fields"], j["data"], "證券代號", QFIIS_SPEC)


def parse_valuation(twse_j, tpex_j):
    out = _by_code(twse_j["fields"], twse_j["data"], "證券代號", VALUATION_SPEC)
    t = tpex_j["tables"][0]
    out.update(_by_code(t["fields"], t["data"], "股票代號", VALUATION_SPEC))
    return out


def fetch_day(fetcher, date, with_flows):
    """Quotes for both boards, TAIEX, and managed stocks; flows and holdings only when `with_flows`."""
    twse = _fetch(fetcher, "twse_quotes", TWSE_QUOTES, date, twse_ok)
    tpex_quotes, managed = parse_tpex_quotes(_fetch(fetcher, "tpex_quotes", TPEX_QUOTES, date, tpex_ok))
    quotes = {code: dict(q, market="twse") for code, q in parse_twse_quotes(twse).items()}
    quotes.update({code: dict(q, market="tpex") for code, q in tpex_quotes.items()})
    day = {"quotes": quotes, "taiex": parse_taiex(twse), "managed": managed, "flows": None, "holdings": None}
    if with_flows:
        flows = parse_t86(_fetch(fetcher, "twse_t86", TWSE_T86, date, twse_ok))
        flows.update(parse_tpex_insti(_fetch(fetcher, "tpex_insti", TPEX_INSTI, date, tpex_ok)))
        day["flows"] = flows
        day["holdings"] = parse_qfiis(_fetch(fetcher, "twse_qfiis", TWSE_QFIIS, date, twse_ok))
    return day


def fetch_valuation(fetcher, date):
    """PER, PBR, and yield for both boards, from tables dated exactly `date`."""
    ymd = date.replace("-", "")
    twse = _fetch(fetcher, "twse_per", TWSE_PER, date, _dated(twse_ok, ymd))
    tpex = _fetch(fetcher, "tpex_per", TPEX_PER, date, _dated(tpex_ok, ymd))
    return parse_valuation(twse, tpex)


def resolve_asof(fetcher, today, trading_dates):
    """The latest trading date on or before `today` whose TWSE quotes validate, stepping back at most 3 dates."""
    candidates = sorted((d for d in trading_dates if d <= today), reverse=True)[:ASOF_STEP_BACKS + 1]
    for i, day in enumerate(candidates):
        try:
            _fetch(fetcher, "twse_quotes", TWSE_QUOTES, day, twse_ok)
            return day
        except NoDataError:
            if i == len(candidates) - 1:
                raise
    raise NoDataError(f"no trading date on or before {today}")
