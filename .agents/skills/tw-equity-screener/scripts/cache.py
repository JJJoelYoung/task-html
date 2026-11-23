"""Throttled HTTP fetcher with a gzip raw cache outside the repository.

Every exchange and MOPS request goes through `Fetcher.get`, which serves the
cache first, spaces live requests, retries transient failures, and caches a
response only after it validates. A "no data" answer (holiday, unpublished
date, block page) raises `NoDataError` and is never cached.
"""

import gzip
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (compatible; tw-equity-screener)"
RETRY_WAITS_S = (10, 30, 90)
TIMEOUT_S = 60


def cache_root():
    """The raw cache directory: `TW_SCREENER_CACHE` when set, else ~/.cache/tw-equity-screener."""
    env = os.environ.get("TW_SCREENER_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "tw-equity-screener"


class NoDataError(RuntimeError):
    """The source answered without the expected table: a holiday, an unpublished date, or a block page."""


class Fetcher:
    def __init__(self, root=None, pause_s=3.0, opener=urllib.request.urlopen, sleep=time.sleep):
        self.root = Path(root) if root is not None else cache_root()
        self.pause_s = pause_s
        self.opener = opener
        self.sleep = sleep
        self.network_calls = 0
        self._fetched = False

    def _path(self, source, key):
        return self.root / "raw" / source / f"{key}.gz"

    def has(self, source, key):
        return self._path(source, key).exists()

    def get(self, source, key, url, *, encoding, validate, form=None, refresh=False):
        path = self._path(source, key)
        if not refresh and path.exists():
            return gzip.decompress(path.read_bytes()).decode("utf-8")
        if self._fetched:
            self.sleep(self.pause_s)
        self._fetched = True
        text = self._request(url, form).decode(encoding)
        if not validate(text):
            raise NoDataError(f"{source}/{key}: no expected table in {url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(gzip.compress(text.encode("utf-8")))
        os.replace(tmp, path)
        return text

    def _request(self, url, form):
        data = urllib.parse.urlencode(form).encode("ascii") if form else None
        request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        for attempt in range(len(RETRY_WAITS_S) + 1):
            self.network_calls += 1
            try:
                with self.opener(request, timeout=TIMEOUT_S) as response:
                    return response.read()
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == len(RETRY_WAITS_S):
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == len(RETRY_WAITS_S):
                    raise
            self.sleep(RETRY_WAITS_S[attempt])
