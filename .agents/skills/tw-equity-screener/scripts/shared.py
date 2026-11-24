"""The screener's only import bridge to tw-equity-report/scripts.

Every definition the two skills share (the trend filter, the 6-month median
revenue YoY, the shortlist deep metrics, the page-check helpers) is imported
from here, never re-implemented.
"""

import sys
from pathlib import Path

REPORT_SCRIPTS = Path(__file__).resolve().parents[2] / "tw-equity-report" / "scripts"
sys.path.insert(0, str(REPORT_SCRIPTS))

import check_report  # noqa: E402
import derive  # noqa: E402
import fetch  # noqa: E402
import finmind_client  # noqa: E402
import metrics as mt  # noqa: E402

fetch_build = fetch.build
finmind_fetch = finmind_client.fetch
QuotaError = finmind_client.QuotaError
NotPublishedError = fetch.NotPublishedError


def trend_gate(price_rows):
    """Return (price metrics, trend check) under tw-equity-report's trend filter."""
    m = mt.price_metrics(price_rows)[1]
    return m, derive.trend_check(m)
