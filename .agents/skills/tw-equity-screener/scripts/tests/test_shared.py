"""Unit tests for shared.py, the bridge to tw-equity-report's definitions (no network)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shared  # noqa: E402
from helpers import price_rows  # noqa: E402


class TrendGate(unittest.TestCase):
    def test_trend_gate_rising_passes(self):
        m, t = shared.trend_gate(price_rows([100 + i for i in range(80)]))
        self.assertTrue(t["checked"] and t["ok"])

    def test_trend_gate_falling_fails(self):
        m, t = shared.trend_gate(price_rows([200 - i for i in range(80)]))
        self.assertFalse(t["ok"])


if __name__ == "__main__":
    unittest.main()
