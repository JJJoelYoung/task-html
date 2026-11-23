"""TWSE and TPEx OpenAPI snapshots: trading statuses and the listing pipeline.

The OpenAPI answers only the current state, so a snapshot is cached under the
run's `asof` and a past `asof` can use only what an earlier run cached. Status
rules follow research section 5 (L1); an unreadable date never hides a status,
so a row whose date cannot be read counts as in force.
"""

import json
import re
from collections import defaultdict
from datetime import date, timedelta

from exchange import num

TWSE_API = "https://openapi.twse.com.tw/v1/"
TPEX_API = "https://www.tpex.org.tw/openapi/v1/"
OPENAPI = {
    "TWT48U_ALL": TWSE_API + "exchangeReport/TWT48U_ALL",
    "TWT85U": TWSE_API + "exchangeReport/TWT85U",
    "TWTAWU": TWSE_API + "exchangeReport/TWTAWU",
    "punish": TWSE_API + "announcement/punish",
    "notice": TWSE_API + "announcement/notice",
    "applylistingLocal": TWSE_API + "company/applylistingLocal",
    "TWT88U": TWSE_API + "exchangeReport/TWT88U",
    "suspendListing": TWSE_API + "company/suspendListingCsvAndHtml",
    "exright": TPEX_API + "tpex_exright_prepost",
    "cmode": TPEX_API + "tpex_cmode",
    "disposal": TPEX_API + "tpex_disposal_information",
    "warning": TPEX_API + "tpex_trading_warning_information",
    "applicants": TPEX_API + "tpex_esb_applicant_companies",
    "ipo_no_limit": TPEX_API + "tpex_ipo_no_limit",
    "esb_quotes": TPEX_API + "tpex_esb_latest_statistics",
}
EXCLUDE_TAGS = {"altered_trading", "managed", "suspended"}
FLAG_TAGS = {"disposition", "attention", "periodic_auction", "cash_offering"}
CMODE_TAGS = (("AlteredTrading", "altered_trading"), ("ManagedStock", "managed"),
              ("SuspensionOfTrading", "suspended"), ("PeriodicTrading", "periodic_auction"),
              ("MatchingFrequency", "periodic_auction"))
DATE_RE = re.compile(r"^(\d{2,4})[/-]?(\d{2})[/-]?(\d{2})$")
PIPELINE_DAYS = 365


class SnapshotMissing(RuntimeError):
    """A non-live run asked for a snapshot that no earlier run cached for its `asof`."""


def _json_list(text):
    try:
        return isinstance(json.loads(text), list)
    except ValueError:
        return False


def snapshot(fetcher, name, asof, live):
    """The `name` snapshot cached under `asof`; only a live run may fetch one."""
    if not live and not fetcher.has(name, asof):
        raise SnapshotMissing(f"no {name} snapshot cached for {asof}, and the OpenAPI serves only today")
    return json.loads(fetcher.get(name, asof, OPENAPI[name], encoding="utf-8", validate=_json_list))


def tw_date(s):
    """ROC ("1151120", "115/11/20") or Gregorian ("20261029") date as ISO; blank or unreadable gives None."""
    m = DATE_RE.match(str(s or "").strip())
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    try:
        return date(y + 1911 if y < 1911 else y, mo, d).isoformat()
    except ValueError:
        return None


def tw_range(s):
    """A "start～end" or "start~end" period as (start, end) ISO dates."""
    parts = re.split(r"[～~]", str(s or ""))
    return tw_date(parts[0]), tw_date(parts[-1])


def _code(v):
    return str(v or "").strip()


def _on_or_after(d, asof):
    return d is None or d >= asof


def parse_statuses(asof, p):
    """{code: tags} from the status snapshots in `p` (name to rows); sources absent from `p` are skipped."""
    tags = defaultdict(set)

    def tag(code, t):
        if _code(code):
            tags[_code(code)].add(t)

    for r in p.get("TWT85U", []):
        tag(r["Code"], "altered_trading")
    for r in p.get("TWTAWU", []):
        halt, resume = tw_date(r["TradingHaltDate"]), tw_date(r["TradingResumptionDate"])
        if (halt is None or halt <= asof) and (resume is None or resume > asof):
            tag(r["Code"], "suspended")
    for name, field in (("punish", "Code"), ("disposal", "SecuritiesCompanyCode")):
        for r in p.get(name, []):
            if _on_or_after(tw_range(r["DispositionPeriod"])[1], asof):
                tag(r[field], "disposition")
    for r in p.get("notice", []):          # the "no notices" placeholder row has a blank Code
        tag(r["Code"], "attention")
    for r in p.get("warning", []):
        tag(r["SecuritiesCompanyCode"], "attention")
    for r in p.get("cmode", []):
        for field, t in CMODE_TAGS:
            if str(r.get(field) or "").strip():
                tag(r["SecuritiesCompanyCode"], t)
    for r in p.get("TWT48U_ALL", []):
        if (num(r["SubscriptionRatio"]) or 0) > 0 and _on_or_after(tw_date(r["Date"]), asof):
            tag(r["Code"], "cash_offering")
    for r in p.get("exright", []):
        if ((num(r["SubscriptionRatioToNewSharesIssued"]) or 0) > 0
                and _on_or_after(tw_date(r["ExRrightsExDividendDate"]), asof)):
            tag(r["SecuritiesCompanyCode"], "cash_offering")
    return dict(tags)


def parse_pipeline(asof, p):
    """Upcoming listings, first-five-day lists, Emerging quotes, and delisting dates."""
    since = (date.fromisoformat(asof) - timedelta(days=PIPELINE_DAYS)).isoformat()
    applied = []
    for r in p.get("applylistingLocal", []):
        v = list(r.values())            # keys are shifted by one column, so read by position
        applied.append({"code": _code(v[1]), "name": _code(v[2]), "market": "twse", "applied": tw_date(v[3]),
                        "listing_date": tw_date(v[9]), "price": num(v[11])})
    for r in p.get("applicants", []):
        applied.append({"code": _code(r["SecuritiesCompanyCode"]), "name": _code(r["CompanyName"]),
                        "market": "tpex", "applied": tw_date(r["Date"]), "listing_date": tw_date(r["ListingDate"]),
                        "price": num(r["OfferingPrice"])})
    upcoming = [a for a in applied if a["applied"] is not None and a["applied"] >= since
                and (a["listing_date"] is None or a["listing_date"] >= asof)]

    first_five = {}
    for r in p.get("TWT88U", []):
        first_five.setdefault(_code(r["SecurCode"]), {"first": tw_date(r["1stTradingDate"]),
                                                      "fifth": tw_date(r["5thTradingDate"]),
                                                      "price": num(r["PriceUnderwritten"])})
    for r in p.get("ipo_no_limit", []):
        first_five.setdefault(_code(r["SecuritiesCompanyCode"]),
                              {"first": tw_date(r["StartDateForStabilizationOperation"]),
                               "fifth": tw_date(r["EndDateForStabilizationOperation"]),
                               "price": num(r["UnderwritingPrice"])})

    emerging = {_code(r["SecuritiesCompanyCode"]): {"avg": num(r["Average"]), "last": num(r["LatestPrice"]),
                                                    "volume": num(r["TransactionVolume"]),
                                                    "applying_status": _code(r["ApplyingStatus"])}
                for r in p.get("esb_quotes", [])}

    delisted = {}
    for r in p.get("suspendListing", []):
        code, d = _code(r["Code"]), tw_date(r["DelistingDate"])
        if d and d > delisted.get(code, ""):
            delisted[code] = d
    return {"upcoming": upcoming, "first_five": first_five, "emerging": emerging, "delisted": delisted}
