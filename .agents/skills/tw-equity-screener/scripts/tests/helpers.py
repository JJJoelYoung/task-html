"""Test helpers shared by the tw-equity-screener suite (no network)."""

import json
from datetime import date, timedelta
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture(name, encoding):
    """A fixture file's text, decoded with the source's own encoding."""
    return (FIXTURE_DIR / name).read_text(encoding=encoding)


def fx(name):
    """A JSON fixture, parsed."""
    return json.loads(fixture(name, "utf-8"))


def sec(code, listing_date, market, name="n", industry="i", board="main"):
    """A Security with placeholder ISIN and CFI values."""
    from universe import Security

    return Security(code=code, name=name, isin=f"TW000{code}", listing_date=listing_date, market=market,
                    board=board, industry=industry, cfi="ESVUFR")


def panel_with(code, closes, values=None, flows=None, start=date(2026, 1, 5)):
    """A Panel over weekday dates (from a Monday) holding one code. A None close leaves that date without a
    quote row; `values` overrides the traded value; `flows` holds that day's {foreign, trust, dealer} or None."""
    from factors import Panel

    dates, d = [], start
    while len(dates) < len(closes):
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += timedelta(days=1)
    days = {}
    for i, day in enumerate(dates):
        c, f = closes[i], (flows[i] if flows else None)
        quotes = {}
        if c is not None:
            v = values[i] if values and values[i] is not None else c * 1000
            quotes[code] = {"open": c, "high": c, "low": c, "close": c, "volume": 1000.0, "value": v,
                            "market": "twse"}
        days[day] = {"quotes": quotes, "taiex": 100.0, "managed": set(), "flows": {code: f} if f else None,
                     "holdings": None}
    return Panel(dates=dates, days=days)


def price_rows(closes, volumes=None, start=date(2026, 1, 5)):
    """FinMind-shaped daily price rows, the same shape as tw-equity-report's test helper."""
    rows = []
    for i, c in enumerate(closes):
        v = (volumes[i] if volumes else 10) * 1000
        rows.append({"date": (start + timedelta(days=i)).isoformat(), "open": c, "max": c + 1, "min": c - 1,
                     "close": c, "Trading_Volume": v, "Trading_money": v * c})
    return rows
