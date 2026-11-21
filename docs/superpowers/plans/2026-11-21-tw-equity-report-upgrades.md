# Taiwan Equity Report Skill Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the four high-value risk-control and sanity-check enhancements distilled from the 8-step Taiwan equity strategy peer review into `.agents/skills/tw-equity-report/` without introducing paid FinMind dependencies or a conflicting second valuation engine (`dim7`), and publish the sanitized English peer-review research note under `docs/research/` as their empirical design rationale.

**Architecture:** Keep the existing six-section (`dim1`–`dim6`) dual-horizon design (swing technical layer + 12-month scenario hold layer) intact, while upgrading:
1. **Trend Filter & `"左側觀察"` (`left_watch`) Action (`metrics.py`, `derive.py`)**: Add `MA60`, `ma20_slope_5d`, and `ma60_slope_5d` using the existing 120-day `TaiwanStockPrice` series, and gate every `BUY` action (including `close > z_hi` dead-cat bounces) so falling-MA setups downgrade to `"left_watch"` with `pullback_status = "downtrend"`.
2. **Dual CY / NTM Core Run-Rate Baseline EPS (`metrics.py`, `fetch.py`, `check_report.py`, `judgment-review.md`)**: Pull `"TAX"` and `"PreTaxIncome"` (already present in Free-tier `TaiwanStockFinancialStatements`), compute revenue-weighted TTM OPM × `(1 - effective_tax_rate)` × `parent_ratio` ÷ `implied_weighted_shares` across both Calendar-Year (CY) and Rolling Next-12-Month (NTM) revenues, flag high volatility, surface `data-baseline="cy|ntm"` in `dim4`, and enforce a `> +20%` Base-vs-NTM justification check in `judgment-review.md`.
3. **Structured CB / SPO Dilution Check (`SKILL.md`, `report-contract.md`, `check_report.py`, `judgment-review.md`)**: Keep `fetch.py` 100% Free-tier; require Step 4 web/MOPS verification of unconverted CBs and announced cash capital increases (`analysis["dilution"]`), rendered in `dim3` (`data-dilution`) with `> 5%` dilution mirrored to `dim5` risks.
4. **Monthly Revenue Thesis Breaker Enforcement (`SKILL.md`, `report-contract.md`, `check_report.py`, `judgment-review.md`)**: Enforce via `check_report.py` and `judgment-review.md` that at least one `thesis_breakers` item monitors `TaiwanStockMonthRevenue` with a concrete numeric threshold for the next 10th-of-month release.

**Tech Stack:** Python 3.12 stdlib (`unittest`, `json`, `re`, `html`, `pathlib`), FinMind v4 Free-tier REST datasets, Markdown skill specifications.

**Research Reference:** [2026-11-21-tw-equity-8step-strategy-review.md](../../research/2026-11-21-tw-equity-8step-strategy-review.md) (created in Task 0)

---

## Global Constraints

- **100% FinMind Free-tier compatible**: Do NOT add Backer/Sponsor datasets (e.g., `TaiwanStockConvertibleBondDailyOverview`). All new financial fields (`TAX`, `PreTaxIncome`) come from existing `TaiwanStockFinancialStatements` calls; `MA60` and 5-day slopes come from the existing 120-day `TaiwanStockPrice` query.
- **Backward compatibility for legacy reports**: Do NOT modify or regenerate existing published HTML reports (`6834`, `2308`, `2492`, `2330`, `8299`, `2501`). `derive.py` MUST gracefully degrade when given legacy `data_*.json` or minimal unit-test dicts lacking `ma60`, `ma20_slope_5d`, `ma60_slope_5d`, or `alignment`.
- **No NT$10 par-value hardcoding in baseline shares**: Use `net_income_parent / eps` from the latest normal quarter (`|EPS| >= 0.2`), falling back to TTM `net_income_parent / ttm_eps`, and only then to `OrdinaryShare / 10`.
- **Single source of truth & encoding**: Pass `encoding="utf-8"` on all file I/O; keep `.claude/skills/tw-equity-report/SKILL.md` unchanged unless frontmatter changes (none planned); never embed machine-specific absolute paths in committed files.
- **English-only repo docs & zero leaks**: Commit only the sanitized English research note under `docs/research/` (`english-doc-guard`), never commit the third-party source prompt file, and keep zero local machine paths or downloaded filenames in both the committed research note and the external Traditional Chinese peer-review copy.

## Review Focus

1. **Anti-knife-catching flip on `2308`**: With `MA20 = 1,390.50` (5d slope `-160.25`) and `MA60 = 1,672.08` (5d slope `-49.50`), `derive.derive()` must downgrade `2308` (`asof 2026-11-13`) from `"accumulate"` to `"left_watch"` (`"左側觀察"`), `pullback_status = "downtrend"`, `rr_pullback = None`.
2. **Strict dead-cat bounce guard (`close > z_hi`)**: Even when `close` exceeds `zone_high`, failing `trend_check(m)` must emit `"left_watch"` and `"downtrend"` rather than `"wait_pullback"`.
3. **Flexible par-value & minority-interest accuracy**: Verify `core_baseline()` yields exact `CY = 33.93 / NTM = 44.71` (`high_volatility = False`) on `2308` (`parent_ratio = 89.46%`, `eff_tax = 22.89%`) and `CY = 2.62 / NTM = 4.79` (`high_volatility = True`) on `6834`, plus unit-tested NT$5 par-value shares (`2x` shares vs. `OrdinaryShare / 10`).
4. **Fallback guards on anomalous quarters**: Test `PreTaxIncome <= 0`, tax rates outside `[0%, 40%]`, `IncomeAfterTaxes <= 0`, parent ratios outside `(0%, 100%]`, non-consecutive quarters, and `TTM OperatingIncome <= 0`.
5. **Validator completeness (`check_report.py`)**: Confirm missing `dilution`, missing numeric `TaiwanStockMonthRevenue` breaker, or missing/mismatched `data-dilution` / `data-baseline` hooks (including `"不適用"` under PBR valuation) trigger clear `FAIL` messages.

---

### Task 0: Publish Sanitized English Strategy Review Note & Clean External Copy

**Files:**
- Create: `docs/research/2026-11-21-tw-equity-8step-strategy-review.md`
- Sanitize (external, outside git): the user's local Traditional Chinese peer-review copy

- [x] **Step 1: Author English research note at `docs/research/2026-11-21-tw-equity-8step-strategy-review.md`**
  - Translate and structure all 6 sections (Executive Summary, Architecture Comparison Matrix, 3 Strengths, Empirical Table & 5 Mathematical/Structural Flaws across `2308`, `6834`, `2492`, Drop-in Upgraded 8-Step Formula Table, and 4-Module Integration Summary) strictly in English (`english-doc-guard`), preserving quoted Traditional Chinese UI labels (e.g., `"左側觀察"`) with English explanations.
  - Reference the external strategy generically ("an externally provided 8-step Taiwan equity prompt model") with zero local paths, zero downloaded filenames, and zero verbatim reproduction of the original prompt.

- [x] **Step 2: Sanitize line 3 of the external Traditional Chinese peer-review copy**
  - Replace the local file link/path and downloaded filename on line 3 with a generic anonymous description so the local file is safe to share with the strategy provider while remaining outside git.

- [x] **Step 3: Security & path check**
  - Run `gitleaks dir` on `docs/research/2026-11-21-tw-equity-8step-strategy-review.md` and confirm zero absolute paths (`[A-Za-z]:\\`) in the file.

---

### Task 1: Extend Price Slopes, Financial Fields, and Core Baseline in `metrics.py` & `fetch.py`

**Files:**
- Modify: `.agents/skills/tw-equity-report/scripts/metrics.py`
- Modify: `.agents/skills/tw-equity-report/scripts/fetch.py`

**Interfaces:**
- `metrics.price_metrics(rows)` -> adds `ma60` to `series[]` and `ma60`, `ma20_slope_5d`, `ma60_slope_5d` to `metrics`.
- `metrics.financials(inc, bal, cf, asof, gaps)` -> adds `pretax_income`, `tax` per quarter and `implied_shares`, `shares_source` to returned dict.
- `metrics.core_baseline(rev, fin)` -> returns CY & NTM core run-rate baseline EPS dict with fallback & volatility flags.
- `fetch.build(code, peers, asof_pin=None)` -> attaches `fin["core_baseline"] = mt.core_baseline(rev, fin)`.

- [x] **Step 1: Extend `STATEMENT_TYPES` and `price_metrics` in `metrics.py`**
  - Add `"TAX"` and `"PreTaxIncome"` to `STATEMENT_TYPES`.
  - In `price_metrics(rows)`, append `"ma60": r2(ma(60, i))` to each `series` dict.
  - Add helper for 5-day MA change (`last[key] - series[-6][key]` when `len(series) >= 6` and both endpoints are non-null, else `None`), and populate `ma60`, `ma20_slope_5d`, and `ma60_slope_5d` in the returned `metrics` dict.

- [x] **Step 2: Extend `financials()` with tax, pretax income, and `implied_shares`**
  - In `quarters` loop, store `"pretax_income": d.get("PreTaxIncome")` and `"tax": d.get("TAX")`.
  - Compute `implied_shares` & `shares_source` using a helper `_implied_shares(last4, consecutive, ttm_eps, share_cap)`:
    1. Walk `reversed(last4)`: first quarter with `eps` and `net_income_parent` non-null, `abs(eps) >= 0.2`, and `eps * net_income_parent > 0` -> `(net_income_parent / eps, "implied_latest_q")`.
    2. Else if `consecutive` and `ttm_eps is not None` and `abs(ttm_eps) >= 0.2` and all `last4` have `net_income_parent` with `sum(nip) * ttm_eps > 0` -> `(sum(nip) / ttm_eps, "implied_ttm")`.
    3. Else if `share_cap` -> `(share_cap / 10, "ordinary_share_par10")`.
    4. Else `(None, None)`.
  - Include `"implied_shares": round(imp_shares) if imp_shares else None` and `"shares_source": shares_src` in `financials()` return dict.

- [x] **Step 3: Implement `core_baseline(rev, fin)` in `metrics.py` and wire into `fetch.py`**
  - Extract `last4 = fin.get("quarters", [])[-4:]`.
  - Guard checks (return `{"applicable": False, "reason": ...}` with null numeric fields):
    - `len(last4) < 4` or non-consecutive quarters (`next_quarter`) -> `"non_consecutive_quarters"`.
    - Missing `operating_income` / `revenue` or `ttm_rev <= 0` or `ttm_oi <= 0` -> `"nonpositive_operating_income"`.
    - Missing/nonpositive `shares` (`fin.get("implied_shares") or fin.get("shares_outstanding")`) -> `"missing_shares"`.
    - Empty `yoys6 = sorted(r["yoy_pct"] for r in rev["last12"][-6:] if r.get("yoy_pct") is not None)` -> `"missing_yoy"`.
  - Compute:
    - `med_yoy = percentile(yoys6, 50)`, `ttm_opm = ttm_oi / ttm_rev`.
    - `eff_tax, tax_src`: if all 4 quarters have `tax` and `pretax_income` non-null and `sum(pretax_income) > 0` and `0 <= sum(tax) / sum(pretax_income) <= 0.40`, use `(sum(tax) / sum(pretax_income), "ttm_actual")`; else `(0.20, "default_20pct")`.
    - `parent_ratio, parent_src`: if all 4 quarters have `net_income_parent` and `net_income` non-null and `sum(net_income) > 0` and `0 < sum(net_income_parent) / sum(net_income) <= 1.0`, use `(sum(net_income_parent) / sum(net_income), "ttm_actual")`; else `(1.0, "default_100pct")`.
    - `core_margin = ttm_opm * (1 - eff_tax) * parent_ratio`.
    - `cy_rev`: parse `ly, lm` from `rev["latest_period"]`; sum prior-year remaining months `lm+1..12` from `rev["series24"]`; if all remaining months exist (or `lm == 12`), `cy_rev = rev["ytd"] + rem_rev * (1 + med_yoy / 100)`, else `None`. Set `cy_late_year = lm >= 10`.
    - `ntm_rev`: `sum(r["revenue"] for r in rev["last12"]) * (1 + med_yoy / 100)`.
    - Volatility reasons: `"opm_spread_gt_5pp"` (`max(opms) - min(opms) > 5.0`), `"negative_quarter_opm"` (`any(o <= 0 for o in opms)`), `"yoy_gt_50pct"` (`abs(med_yoy) > 50.0`). `high_volatility = bool(vol_reasons)`.
  - In `fetch.py`, inside `build()`, compute `fin["core_baseline"] = mt.core_baseline(rev, fin)`.

---

### Task 2: Add Trend Filter, `"left_watch"` Action, and Baseline Deviation in `derive.py`

**Files:**
- Modify: `.agents/skills/tw-equity-report/scripts/derive.py`

**Interfaces:**
- `SETUP_STATUS_ZH["downtrend"] = "均線呈空頭下彎，趨勢尚未止跌，拉回策略暫不成立"`
- `ACTION_ZH["left_watch"] = "左側觀察"`
- `trend_check(m) -> {"checked": bool, "ok": bool, "reason": str | None}`
- `fmt_eps(v) -> str` (`"不適用"` when `None`, else `f"{v:.2f}"`)
- `derive(d, a)` returns extra keys: `trend_ok`, `trend_reason`, `baseline_deviation_pct`

- [x] **Step 1: Add status/action constants, `trend_check(m)`, and `fmt_eps(v)`**
  - Implement `trend_check(m)`:
    - If `"ma20_slope_5d"` not in `m` and `"alignment"` not in `m`: return `{"checked": False, "ok": True, "reason": None}` (legacy graceful degradation).
    - If `m.get("alignment") == "bearish"`: return `{"checked": True, "ok": False, "reason": "bearish_alignment"}`.
    - If `m.get("ma20_slope_5d") is None` and `m.get("ma60_slope_5d") is None`: return `{"checked": False, "ok": True, "reason": None}`.
    - Compute `ma20_ok = (m.get("ma20") is not None and m.get("ma20_slope_5d") is not None and m["close"] >= m["ma20"] and m["ma20_slope_5d"] >= 0)` and `ma60_ok = (m.get("ma60") is not None and m.get("ma60_slope_5d") is not None and m["close"] >= m["ma60"] and m["ma60_slope_5d"] >= 0)`.
    - Return `{"checked": True, "ok": ma20_ok or ma60_ok, "reason": None if (ma20_ok or ma60_ok) else "below_falling_ma"}`.

- [x] **Step 2: Integrate `trend_check(m)` and `baseline_deviation_pct` into `derive(d, a)`**
  - Pullback status precedence:
    `not tr["ok"]` -> `"downtrend"`, else `close < z_lo` -> `"below_zone"`, else `t2 <= entry` -> `"target_below_entry"`, else `"active"`.
  - Action precedence (strict Q2 + Q6 consistency):
    `SELL` -> `"avoid"`; `NEUTRAL` -> `"watch"`; `BUY` and `not tr["ok"]` -> `"left_watch"` (`note = f"估值達買進但均線趨勢未止跌，等站上走平翻揚的 {ma_ref}"`); else `wait_reclaim` / `accumulate` / `wait_pullback`.
  - Compute `baseline_deviation_pct`: when `a.get("valuation_method") != "PBR"`, read `cb = (d.get("financials") or {}).get("core_baseline") or {}`; if `cb.get("applicable") and cb.get("ntm_eps") and cb["ntm_eps"] > 0`, return `round((base["eps"] / cb["ntm_eps"] - 1) * 100, 1)`, else `None`.

---

### Task 3: Extend Contract Checks in `check_report.py`

**Files:**
- Modify: `.agents/skills/tw-equity-report/scripts/check_report.py`

- [x] **Step 1: Update `check_data(c, d)`**
  - Add `"ma60"` and `"ma20_slope_5d"` to required non-null `price.metrics` keys; if `len(d["price"]["series"]) >= 65`, require `m.get("ma60_slope_5d") is not None`.
  - Check `isinstance((d.get("financials") or {}).get("core_baseline"), dict)` and `isinstance(cb.get("applicable"), bool)`.

- [x] **Step 2: Update `check_analysis(c, d, a, x)`**
  - Validate `dilution` is a dict containing boolean `has_cb`, boolean `has_spo`, non-empty `summary`, and non-empty `basis`.
  - Validate `thesis_breakers` contains at least one item where `"TaiwanStockMonthRevenue"` appears in `dataset` and `re.search(r"\d", str(item.get("threshold", "")))` matches.

- [x] **Step 3: Update `check_structure(c, page, d, x)` (plus `a` parameter passed from `main`)**
  - Pass `a` into `check_structure(c, page, d, a, x)` (keeping a default or updating all call sites cleanly).
  - Verify `<section id="dim3"` contains `data-dilution` with non-empty text (`text_of(dim3, "data-dilution", ...)` or regex matching `data-dilution(?:="[^"]*")?[^>]*>([^<]+)<`).
  - Verify `<section id="dim4"` contains `data-baseline="cy"` and `data-baseline="ntm"`. When `a.get("valuation_method") == "PBR"` or not `cb.get("applicable")`, both must equal `"不適用"`; otherwise they must equal `dv.fmt_eps(cb.get("cy_eps"))` and `dv.fmt_eps(cb.get("ntm_eps"))`.

---

### Task 4: Update Reference Docs & `SKILL.md`

**Files:**
- Modify: `.agents/skills/tw-equity-report/references/methodology.md`
- Modify: `.agents/skills/tw-equity-report/references/report-contract.md`
- Modify: `.agents/skills/tw-equity-report/references/judgment-review.md`
- Modify: `.agents/skills/tw-equity-report/SKILL.md`

- [x] **Step 1: Update `methodology.md`**
  - Section 2: document `MA60`, `ma20_slope_5d`, `ma60_slope_5d`, and the trend-filter condition (`alignment != "bearish"` and (`close >= MA20 & ma20_slope_5d >= 0` or `close >= MA60 & ma60_slope_5d >= 0`)).
  - Section 4: document `TAX`, `PreTaxIncome`, `implied_shares`, and the dual CY/NTM `core_baseline` formula + fallback guards + `high_volatility` flags.
  - Section 7 & 8: document pullback `downtrend` reason, `"左側觀察"` (`left_watch`) row in Current Action table, and the mandatory numeric `TaiwanStockMonthRevenue` thesis breaker.

- [x] **Step 2: Update `report-contract.md`**
  - Section 2: document `data-baseline="cy|ntm"` (`derive.fmt_eps`) and `data-dilution`.
  - Section 4: update `dim1` (`MA60` + 5-day slopes), `dim3` (structured `dilution` block), `dim4` (Core Run-Rate Baseline strip), `dim6` (next-month-10th numeric revenue breaker).
  - Section 7: summarize new checks in `check_report.py`.

- [x] **Step 3: Update `judgment-review.md`**
  - Check 2: add comparison of `Base` EPS against `data.financials.core_baseline.ntm_eps`; deviation `> +20%` requires explicit operational/external evidence in `basis`.
  - Check 7: verify at least one thesis breaker uses `TaiwanStockMonthRevenue` with a concrete numeric next-month threshold.
  - Check 10 (New): verify `analysis.dilution` (`has_cb`, `has_spo`, `summary`, `basis`) against `research_{code}.md` and verify `> 5%` dilution is mirrored in `risks`. Update closing instruction to confirm `all 10 checks ran on every item`.

- [x] **Step 4: Update `SKILL.md`**
  - Step 4 Research query: add `unconverted convertible bonds (CB) or announced cash capital increases (現增)`.
  - Step 4 Judgments: specify `dilution` object and the numeric monthly-revenue thesis breaker rule.
  - Step 5 Generator: mention `derive.fmt_eps`, `data-baseline`, and `data-dilution`.

---

### Task 5: Expand Unit Tests in `scripts/tests/`

**Files:**
- Modify: `.agents/skills/tw-equity-report/scripts/tests/test_metrics.py`
- Modify: `.agents/skills/tw-equity-report/scripts/tests/test_derive.py`
- Modify: `.agents/skills/tw-equity-report/scripts/tests/test_check.py`

- [x] **Step 1: Add tests in `test_metrics.py`**
  - `ma60`, `ma20_slope_5d`, `ma60_slope_5d` (both 60-bar `ma60_slope_5d=None` and 70-bar rising/falling series).
  - `core_baseline`: minority interest + custom tax + NT$5 par value (`implied_latest_q`), anomalous tax fallback (`default_20pct`), non-positive operating income (`applicable=False`), non-consecutive quarters (`applicable=False`), all 3 `high_volatility` triggers.

- [x] **Step 2: Add `TrendFilter` and baseline deviation tests in `test_derive.py`**
  - `2308`-like downtrend inside zone -> `action="left_watch"`, `pullback_status="downtrend"`, `rr_pullback=None`.
  - Dead-cat bounce (`close > z_hi` with falling MAs) -> `action="left_watch"`, `pullback_status="downtrend"`, `rr_pullback=None`.
  - Pullback below rising MA20 supported by rising MA60 (`alignment="mixed"`) -> `action="accumulate"`, `pullback_status="active"`.
  - Bearish alignment even when `close >= MA60` -> `action="left_watch"`.
  - Legacy fixture without `ma60`/`ma20_slope_5d`/`alignment` -> backward-compatible pass.
  - `baseline_deviation_pct` (PER vs. PBR) and `fmt_eps`.

- [x] **Step 3: Add validator tests in `test_check.py`**
  - `check_data` requiring `ma60`, `ma20_slope_5d`, `core_baseline`.
  - `check_analysis` enforcing `dilution` dict and numeric `TaiwanStockMonthRevenue` breaker.
  - `check_structure` validating `data-dilution` and `data-baseline="cy|ntm"` (both PER numeric values and PBR `"不適用"`).

---

### Task 6: Post-Implementation Verification

- [x] Run full unit test suite:
  ```pwsh
  python -m unittest discover -s .agents/skills/tw-equity-report/scripts/tests -v
  ```
- [x] Run read-only smoke verification against `scripts/equity/2308-20261113/data_2308.json` and `scripts/equity/6834-20261112/data_6834.json` confirming:
  1. Legacy `derive(d, a)` succeeds without errors (graceful degradation).
  2. When `ma60` and 5-day slopes are computed from `data_2308.json`'s 120-day series, `2308` flips from `"accumulate"` to `"left_watch"` (`"左側觀察"`).
  3. `core_baseline` computes expected values on `2308` (`CY 33.93 / NTM 44.71`) and `6834` (`CY 2.62 / NTM 4.79`).
- [x] Run `gitleaks dir` (`--redact --no-banner`) on `docs/research/2026-11-21-tw-equity-8step-strategy-review.md`, confirm zero absolute paths across `docs/research/`, `docs/superpowers/plans/`, and `.agents/skills/tw-equity-report/`, verify `git status --short` shows only expected files, and confirm existing published reports were not touched.
