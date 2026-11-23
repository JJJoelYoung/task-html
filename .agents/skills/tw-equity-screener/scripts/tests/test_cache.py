"""Unit tests for cache.py with a scripted opener and a temporary cache root (no network)."""

import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import Fetcher, NoDataError, cache_root  # noqa: E402

URL = "https://example.test/table"
UA = "Mozilla/5.0 (compatible; tw-equity-screener)"


def has_table(text):
    return "<table" in text


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Plays scripted outcomes in order (the last one repeats): bytes to return, or an exception to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        out = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(out, BaseException):
            raise out
        return FakeResponse(out)


def http_error(code):
    return urllib.error.HTTPError(URL, code, "status", hdrs=None, fp=None)


class FetcherTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.sleeps = []

    def fetcher(self, opener, pause_s=0):
        return Fetcher(root=self.root, pause_s=pause_s, opener=opener, sleep=self.sleeps.append)

    def get(self, f, key="2026-11-20", **kw):
        return f.get("src", key, URL, encoding="utf-8", validate=has_table, **kw)

    def test_cache_hit_skips_network(self):
        opener = FakeOpener(b"<table>ok</table>")
        f = self.fetcher(opener)
        self.assertEqual(self.get(f), "<table>ok</table>")
        self.assertEqual(self.get(f), "<table>ok</table>")
        self.assertEqual(f.network_calls, 1)
        request, timeout = opener.requests[0]
        self.assertEqual((request.get_method(), timeout, request.get_header("User-agent")), ("GET", 60, UA))

    def test_no_data_not_cached(self):
        opener = FakeOpener(b"holiday: no table")
        f = self.fetcher(opener)
        with self.assertRaises(NoDataError):
            self.get(f)
        self.assertFalse(f.has("src", "2026-11-20"))
        with self.assertRaises(NoDataError):
            self.get(f)
        self.assertEqual(len(opener.requests), 2)

    def test_retry_backoff_then_success(self):
        down = urllib.error.URLError("down")
        f = self.fetcher(FakeOpener(down, down, b"<table>ok</table>"))
        self.assertEqual(self.get(f), "<table>ok</table>")
        self.assertEqual(self.sleeps, [10, 30])

    def test_retry_gives_up_after_three_waits(self):
        opener = FakeOpener(TimeoutError("slow"))
        f = self.fetcher(opener)
        with self.assertRaises(TimeoutError):
            self.get(f)
        self.assertEqual((self.sleeps, len(opener.requests)), ([10, 30, 90], 4))

    def test_http_404_not_retried(self):
        opener = FakeOpener(http_error(404))
        f = self.fetcher(opener)
        with self.assertRaises(urllib.error.HTTPError):
            self.get(f)
        self.assertEqual((len(opener.requests), self.sleeps), (1, []))

    def test_http_503_retried(self):
        f = self.fetcher(FakeOpener(http_error(503), b"<table>ok</table>"))
        self.assertEqual(self.get(f), "<table>ok</table>")
        self.assertEqual(self.sleeps, [10])

    def test_post_form_encoded(self):
        opener = FakeOpener(b"<table>ok</table>")
        self.get(self.fetcher(opener), form={"TYPEK": "sii", "season": "03"})
        request, _ = opener.requests[0]
        self.assertEqual((request.get_method(), request.data), ("POST", b"TYPEK=sii&season=03"))

    def test_refresh_bypasses_cache(self):
        opener = FakeOpener(b"<table>old</table>", b"<table>new</table>")
        f = self.fetcher(opener)
        self.get(f)
        self.assertEqual(self.get(f, refresh=True), "<table>new</table>")
        self.assertEqual(self.get(f), "<table>new</table>")
        self.assertEqual(f.network_calls, 2)

    def test_throttle_between_network_calls(self):
        f = self.fetcher(FakeOpener(b"<table>ok</table>"), pause_s=3)
        self.get(f, key="a")
        self.get(f, key="a")              # cache hit: no wait
        self.get(f, key="b")
        self.assertEqual(self.sleeps, [3])

    def test_cache_root_env_override(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"TW_SCREENER_CACHE": tmp}):
            self.assertEqual(cache_root(), Path(tmp))


if __name__ == "__main__":
    unittest.main()
