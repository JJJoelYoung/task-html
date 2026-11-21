"""Unit tests for research_context.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_context as rc  # noqa: E402


def _full_sample_data() -> dict:
    return {
        "code": "2330",
        "asof": "2026-11-20",
        "gaps": ["Sample minor gap note"],
        "price": {
            "metrics": {
                "close": 2000.0,
                "ma20": 2276.0,
                "ma60": 2394.25,
                "ma20_slope_5d": -72.25,
                "ma60_slope_5d": -20.92,
                "alignment": "bearish",
            }
        },
        "valuation": {
            "PER": {"current": 20.36, "current_percentile": 38.0},
            "PBR": {"current": 7.41, "current_percentile": 71.9},
            "dividend_yield": 1.1,
        },
        "peers": {
            "rows": [
                {"code": "2330", "PER": 20.36, "PBR": 7.41},
                {"code": "2303", "PER": 11.86, "PBR": 2.14},
                {"code": "5347", "PER": 19.87, "PBR": 3.01},
                {"code": "6770", "PER": 8.91, "PBR": 1.55},
            ],
            "median": {"PER": 11.86, "PBR": 2.14},
        },
        "revenue": {
            "latest_period": "2026-10",
            "ytd": 4485617293000,
            "ytd_yoy_pct": 43.3,
            "last12": [
                {"period": "2026-10", "revenue": 586890319000, "mom_pct": 14.7, "yoy_pct": 59.7},
            ],
        },
        "financials": {
            "latest_quarter": "2026-09-30",
            "ttm_eps": 98.27,
            "bvps_latest": 269.85,
            "implied_shares": 25928114917,
            "cash_conversion": {"ratio": 1.23},
            "core_baseline": {
                "applicable": True,
                "cy_eps": 103.18,
                "ntm_eps": 148.33,
                "yoy6_median_pct": 54.0,
                "high_volatility": True,
                "volatility_reasons": ["opm_spread_gt_5pp", "yoy_gt_50pct"],
            },
            "quarters": [
                {"quarter": "2025-12-31", "eps": 18.0, "gross_margin_pct": 59.0, "operating_margin_pct": 49.0, "dsi_days": 78.0},
                {"quarter": "2026-03-31", "eps": 23.0, "gross_margin_pct": 62.0, "operating_margin_pct": 52.0, "dsi_days": 75.0},
                {"quarter": "2026-06-30", "eps": 27.84, "gross_margin_pct": 65.0, "operating_margin_pct": 56.0, "dsi_days": 74.0},
                {"quarter": "2026-09-30", "eps": 29.43, "gross_margin_pct": 66.4, "operating_margin_pct": 58.7, "dsi_days": 73.7},
            ],
        },
    }


class ResearchContextTests(unittest.TestCase):
    def test_build_context_markdown_complete_and_bounded(self) -> None:
        md = rc.build_context_markdown(_full_sample_data(), max_chars=2200)
        self.assertLessEqual(len(md), 2200)
        self.assertIn("2330", md)
        self.assertIn("TTM EPS=98.27", md)
        self.assertIn("YoY=+59.7%", md)
        self.assertIn("CY EPS=103.18", md)
        self.assertIn("NTM EPS=148.33", md)
        self.assertIn("PER=20.36x", md)
        self.assertIn("2303,5347,6770", md)
        self.assertIn("Sample minor gap note", md)

        # Strict tight cap guarantees hard compliance even under huge gaps list
        huge = _full_sample_data()
        huge["gaps"] = [f"Long gap description number {i} explaining missing fields" for i in range(40)]
        tight = rc.build_context_markdown(huge, max_chars=750)
        self.assertLessEqual(len(tight), 750)
        self.assertIn("TTM EPS=98.27", tight)

    def test_handles_nulls_and_inapplicable_baseline(self) -> None:
        sparse = {
            "code": "9999",
            "asof": "2026-11-20",
            "gaps": [],
            "price": {"metrics": {"close": 50.0, "ma20": 48.0, "ma60": None, "ma20_slope_5d": None, "ma60_slope_5d": None}},
            "valuation": {"PER": {}, "PBR": {}, "dividend_yield": None},
            "peers": {"rows": [], "median": {}},
            "revenue": {"latest_period": None, "ytd": None, "ytd_yoy_pct": None, "last12": []},
            "financials": {
                "latest_quarter": None,
                "ttm_eps": None,
                "bvps_latest": None,
                "implied_shares": None,
                "cash_conversion": None,
                "core_baseline": {"applicable": False, "reason": "negative_ttm_operating_income"},
                "quarters": [],
            },
        }
        md = rc.build_context_markdown(sparse)
        self.assertLessEqual(len(md), 2200)
        self.assertIn("applicable=False (negative_ttm_operating_income)", md)
        self.assertIn("TTM EPS=n/a", md)
        self.assertIn("Data Gaps**: None", md)

    def test_cli_accepts_work_dir_and_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            work = tmp / "2330-20261120"
            work.mkdir()
            data_path = work / "data_2330.json"
            data_path.write_text(json.dumps(_full_sample_data(), ensure_ascii=False), encoding="utf-8")

            out1 = tmp / "scratch" / "ctx_dir.md"
            self.assertEqual(rc.main([str(work), "--out", str(out1)]), 0)
            self.assertTrue(out1.is_file())
            txt1 = out1.read_text(encoding="utf-8")
            self.assertLessEqual(len(txt1), 2200)
            self.assertIn("NT$586.89B", txt1)

            out2 = tmp / "scratch" / "ctx_file.md"
            self.assertEqual(rc.main([str(data_path), "--out", str(out2)]), 0)
            self.assertEqual(out2.read_text(encoding="utf-8"), txt1)


if __name__ == "__main__":
    unittest.main()
