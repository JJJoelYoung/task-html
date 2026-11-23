"""Test helpers shared by the tw-equity-screener suite (no network)."""

from datetime import date, timedelta


def price_rows(closes, volumes=None, start=date(2026, 1, 5)):
    """FinMind-shaped daily price rows, the same shape as tw-equity-report's test helper."""
    rows = []
    for i, c in enumerate(closes):
        v = (volumes[i] if volumes else 10) * 1000
        rows.append({"date": (start + timedelta(days=i)).isoformat(), "open": c, "max": c + 1, "min": c - 1,
                     "close": c, "Trading_Volume": v, "Trading_money": v * c})
    return rows
