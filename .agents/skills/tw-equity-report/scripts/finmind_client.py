"""Minimal FinMind REST client (standard library only).

Reads an optional token from the FINMIND_TOKEN environment variable. Never
returns substitute data: every failure raises.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.finmindtrade.com/api/v4/data"
PAUSE_S = 0.5


class QuotaError(RuntimeError):
    """FinMind refused the call because the hourly quota is used up."""


def fetch(dataset, data_id, start, end=None):
    """Return the rows of one dataset query, or raise."""
    params = {"dataset": dataset, "data_id": data_id, "start_date": start}
    if end:
        params["end_date"] = end
    req = urllib.request.Request(BASE_URL + "?" + urllib.parse.urlencode(params))
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (402, 429):
            raise QuotaError(
                f"FinMind hourly quota exhausted (HTTP {exc.code}). It resets within the hour; "
                "a higher FinMind tier raises the limit."
            ) from exc
        raise
    finally:
        time.sleep(PAUSE_S)
    if payload.get("status") not in (200, None):
        raise RuntimeError(f"{dataset} {data_id}: {payload.get('msg')}")
    return payload.get("data", [])
