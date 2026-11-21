# 8-Step Taiwan Equity Strategy Model — Peer Review & Architecture Comparison

> **Review Scope:** Empirical peer review of an externally provided 8-step Taiwan equity prompt model evaluated against this repository's `tw-equity-report` framework using verified FinMind data for **2308 Delta Electronics (`2026-11-13`)**, **6834 Ever Ohms Technology (`2026-11-12`)**, and **2492 Walsin Technology (`2026-11-10` and `4Q25–3Q26` statements)**.

---

## 1. Executive Summary

The 8-step model has sharp market intuition. It directly addresses two of the most common analytical mistakes in retail and conventional fundamental valuation: **applying P/E multiples to single-quarter or non-operating EPS**, and **buying stocks that look statistically cheap while moving averages are still falling sharply**.

Executing the exact formulas in Python across three Taiwan equities makes two conclusions clear:
- **Three practical strengths worth adopting:** Its moving-average anti-knife-catching filter (`Step 8`) actually caught a real blind spot in our existing `tw-equity-report` decision engine on **2308 Delta Electronics**.
- **Five mathematical and structural flaws requiring fixes:** Systematic biases appear in the year-end revenue window, minority-interest and par-value assumptions, and computing reward-to-risk (`R:R`) from a single static EPS multiplied by a right-skewed `P80` target price—allowing overvalued or structurally distorted names to pass validation.

Accordingly, rather than adding a separate valuation system or second target-price set to `tw-equity-report`, we recommend distilling its repaired mechanisms into our existing modules. Sections below compare both architectures, break down the empirical numbers behind each strength and flaw, and provide a drop-in upgraded 8-step formula table.

---

## 2. Architecture Overview: 8-Step Model vs. `tw-equity-report`

| Dimension | This Repo (`tw-equity-report`) | Original 8-Step Model | Assessment |
|---|---|---|---|
| **Cyclical Stocks** | Mandatory `PER` / `PBR` cross-multiple check; switches to `PBR` on losses/troughs and requires `basis` for band deviations | Pre-filter warns on shipping, steel, panels, memory, petrochemicals, and passive components and **halts execution** | Right instinct, but halting outright blocks quantitative reference points across major active sectors |
| **EPS Forecast** | Forward 4-quarter `Bull`/`Base`/`Bear` EPS (analyst model combining guidance, monthly revenue, quarterly reports, reviewed by an independent subagent) | Mechanical formula: `(YTD + prior-year remaining months × (1 + 6M YoY median)) × (4Q simple avg OPM × 0.8) ÷ share capital` | Purely objective and strips non-operating items, but collapses into historical FY late in Q4 and ignores minority interests & OPM trends |
| **Valuation Bands** | 5-year daily `PER`/`PBR` percentiles (`P10`/`P25`/`P50`/`P75`/`P90`) + 3-peer comparison matrix | 5-year winsorized `PER` at `P80` (optimistic), `P50` (fair), `P20` (defensive) | Largely redundant; multiplying a single fixed EPS across all three multiples misses downside earnings contraction ("Davis double kill") |
| **Dilution Check** | Not previously enforced | `Step 5` explicitly requires checking unconverted CBs and announced cash capital increases (SPO / `現增`) | **8-step model is stronger**, closing a common dilution blind spot in small/mid-cap Taiwan electronics |
| **Reward-to-Risk (`R:R`)** | Strictly split: swing layer (multi-week technical zone & Fibonacci target) + hold layer `(Base − Close) ÷ (Close − Bear)` | Single formula `(Optimistic P80 − Close) ÷ (Close − Defensive P20)` with threshold `>= 2.5` | Right-skewed `P80` numerator can yield high `R:R` even when `Close` already exceeds `Fair P50` |
| **Trend Entry Filter** | `BUY` inside entry zone emitted `"可分批布局"` without checking `MA20`/`MA60` slope | `Step 8` dual gate: `R:R >= 2.5` **and** non-bearish alignment (reclaimed flat/rising `20MA` or `60MA` support), else watchlist (`左側觀察`) | **8-step model is stronger**, preventing premature knife-catching during steep MA downtrends |
| **Monthly Revenue Alert** | `dim6` `thesis_breakers` (2–3 free-form measurable conditions) | Explicitly calculates a dynamic next-month-10th fundamental stop-loss threshold | Anchoring to a concrete numerical next-month-10th trigger enforces tighter tracking discipline |

---

## 3. Three Practical Strengths

### Strength 1: Anti-Knife-Catching Moving-Average Filter (Caught a Real Blind Spot on `2308`)
On **2308 Delta Electronics (`asof 2026-11-13`)**, the closing price was `1,240.0` with moving averages at:
- `MA10 = 1,224.00`, `MA20 = 1,390.50` (**5-day slope `-160.25`**, single-day drop `-27.25`)
- `MA60 = 1,672.08` (**5-day slope `-49.50`**, single-day drop `-10.75`)

Our prior `derive.py` defined the pullback entry zone as `[min(MA10, MA20), max(MA10, MA20)] = [1,225, 1,390]` without verifying whether `MA20` and `MA60` had stopped falling. Because the fundamental rating was `BUY` (`買進`) and `1,240` sat inside that band, the engine directly emitted **`"可分批布局"` (accumulate in batches)**.

The 8-step model's `Step 8` rule—even if valuation `R:R` qualifies, an unstabilized trend (neither above flat/rising `20MA` nor supported by `60MA`) must downgrade to a left-side watchlist (**`"左側觀察"`**) rather than a market buy—directly closes that risk-control gap.

### Strength 2: Non-Operating-Stripped Mechanical Run-Rate Baseline
- **6-month monthly revenue YoY median** cleanly dampens Lunar New Year calendar shifts and one-off rush-order outliers (e.g., `6834`'s sharp MoM/YoY swings where a median is far more robust than an arithmetic mean).
- **Deriving core earnings from Operating Profit Margin (`OPM`)** is especially valuable in Taiwan equities—on **2492 Walsin Technology** during `3Q25–2Q26`, `TTM Net Income Attributable to Parent ÷ TTM Operating Income` reached **`1.465`**, showing reported EPS was heavily buoyed by dividends and FX gains. Isolating core `OPM` prevents capitalizing one-off non-operating income at recurring multiples.

### Strength 3: Convertible Bond (CB) / SPO Dilution & Next-Month-10th Revenue Discipline
- Small/mid-cap Taiwan electronics frequently encounter CB conversion overhang near conversion prices during rallies; `Step 5` forces upfront inspection of unconverted CBs and announced capital increases.
- Binding monitoring to a concrete numeric threshold for the next month's 10th revenue release turns the report from a static snapshot into an actionable monthly checklist.

---

## 4. Five Empirical Mathematical & Structural Flaws

The table below cross-checks both formulas on historical FinMind prices, monthly revenues, and financial statements (including `TAX`, `PreTaxIncome`, and `EquityAttributableToOwnersOfParent`):

### Empirical Comparison Table

| Metric / Ticker | 2308 Delta (`2026-11-13`) | 6834 Ever Ohms (`2026-11-12`) | 2492 Walsin Tech (`2026-11-10` / `4Q25–3Q26`) |
|---|---|---|---|
| **Industry (`FinMind`)** | `電子零組件業` | `電子零組件業` | `電子零組件業` |
| **Close / MA Trend** | `1,240.0` (`MA20`/`60` falling) | `101.0` (`MA20`/`60` falling) | `288.5` (`MA20` falling, `MA60` edging up) |
| **6M Revenue YoY Median** | `+39.30%` | `+101.25%` | `+43.75%` |
| **Last 4Q OPM (Spread)** | `16.35% ~ 17.83%` (`1.49 pp`) | `-0.64% ~ 16.42%` (`17.06 pp`) | `6.37% ~ 19.06%` (`12.70 pp`) |
| **TTM Effective Tax / Parent Ratio** | `22.89%` / **`89.46%`** | `17.18%` / `100.00%` | `23.25%` / **`85.43%`** |
| **Original Core Net Margin (`OPM avg × 0.8`)** | `13.48%` (overstated) | `7.36%` (sharply understated) | `9.99%` (`4Q25–3Q26`; prior `3Q25–2Q26` was `5.92%`) |
| **Upgraded Core Parent Net Margin** | **`11.61%`** | **`9.18%`** | **`7.66%`** |
| **Original Formula CY EPS (`d`)** | **`39.42`** | `2.10` (below TTM `3.02`) | `5.83` (prior 4Q) / `9.84` (latest 4Q) |
| **Upgraded CY / NTM Baseline EPS** | **`33.93`** / **`44.71`** | **`2.62`** / **`4.79`** | **`7.55`** / **`10.27`** |
| **TTM EPS / Analyst Base EPS** | `33.30` / `52.00` | `3.02` / `5.00` | `11.45` (latest 4Q) / `16.00` |
| **Original Targets (Def / Fair / Opt)** | `948.8` / `1,052.2` / `1,958.1` | `52.9` / `185.2` / `518.4` | `57.7` / `142.2` / `203.2` (prior 4Q) |
| **Original R:R (vs. `tw-equity` Hold R:R)** | **`2.47`** (vs. `1.30`) | `8.67` (vs. `0.14`) | `-0.37` (vs. `0.21`) |

> *Note:* The published `2492` snapshot (`2026-11-10`) loaded `3Q25–2Q26` filings (`TTM EPS 8.90`, parent ratio `82.1%`); the right column adds full `4Q25–3Q26` FinMind actuals for apples-to-apples comparison. On `2308`, 5-year weekly-sampled `P20`/`P50`/`P80` `PER` stand near `24.07x` / `26.69x` / `49.67x`.

### Flaw 1: Year-End Window Collapse — Oct–Dec Models Only Current FY, Not NTM
`Step 2` estimates current calendar-year (`CY`) revenue $a$. On **2308 Delta (`asof 2026-11-13`)**, a non-cyclical candidate ideal for the model:
- Jan–Oct cumulative revenue (`6,143.34B` in `NTD 100M` scale: `614.334B`) is already history, yielding `CY 2026` revenue of `759.525B` and minority-adjusted core `CY EPS` of **`33.93`**, barely above realized `TTM EPS` (`33.30`).
- Yet by November the market prices **next 12 months (`NTM` / `2027E`)**: rolling mechanical `NTM EPS` is **`44.71`**, while analyst `Base` is `52.00`.
- Although `Step 2` includes a text footnote advising checking next-year consensus after October, **`Steps 4–8` still substitute `a` and `d`**, causing systematic year-end undervaluation unless paired with rolling `NTM` revenue.

### Flaw 2: `OPM × 0.8` Ignores Minority Interests, 4Q Averaging Lags Turnarounds, and Share Formula Hardcodes NT$10 Par
1. **Minority-interest inflation in holding groups:** Delta holds ~63% of Delta Electronics Thailand (`DET`). Of `TTM` consolidated net income (`96.70B`), only `86.51B` belongs to owners of the parent (**`89.46%`** parent ratio), alongside a **`22.89%`** effective tax rate. True core parent margin is $16.83\% \times (1 - 22.89\%) \times 89.46\% = \mathbf{11.61\%}$, whereas `16.85% × 0.8 = 13.48%` overstates conversion by **+16%**, inflating `2026E` EPS to `39.42` vs. `33.93` (`2492` exhibits the same gap at **`82.1%–85.43%`**).
2. **4Q simple average OPM lags operating inflections:** On turnaround/high-growth `6834` (4Q OPMs `-0.64% → 8.50% → 12.53% → 16.42%`, 10M revenue YoY `+71.3%`), simple-average OPM (`9.20%`) puts `CY EPS` at `2.10`—even **below realized `TTM EPS` (`3.02`)**. Revenue-weighted `TTM OPM` (`11.08%`) paired with explicit volatility warnings is far cleaner.
3. **Hardcoded NT$10 par value:** $d = c \times 10 \div \text{Share Capital (NTD 100M)}$ assumes NT$10 par value and misfires by `2x–10x` on flexible-par Taiwan stocks (`NT$5`, `NT$2.5`, `NT$1`). Dividing by implied weighted shares ($\text{Parent Net Income} \div \text{EPS}$) avoids this completely.

### Flaw 3: Static EPS × Right-Skewed `P80` Creates "Overvalued Yet High `R:R`" Illusions
Observed directly on **2308 Delta**:
- Original targets: Defensive (`P20 ~24.07x`) = **`948.8`**, Fair (`P50 26.69x`) = **`1,052.2`**, Optimistic (`P80 ~49.67x`) = **`1,958.1`**.
- Although closing price **`1,240.0` already exceeded the model's own Fair Value (`1,052.2`) by `+17.8%`**, using right-skewed `P80` (`1,958.1`) in the numerator still yielded **`R:R = 2.47`** (just `0.03` shy of the `>= 2.5` buy trigger).
- Worse, bear regimes trigger **earnings contraction × multiple compression** (e.g., `6834` Bear cuts both EPS and multiple to `36.0`), which fixed-$d$ pricing understates; additionally, when $\text{Close} \le \text{Defensive Price}$, the denominator $(\text{Close} - \text{Defensive})$ turns zero or negative without explicit guardrails.

### Flaw 4: Ambiguous Winsorization and Coarse Industry Tagging
- **Undefined outlier rule:** `Step 6` ("exclude crash or bubble extremes, then take P80/P50/P20") invites conflicting interpretations—whether `P80`/`P20` itself trims extremes or secondary trimming alters them. In thin-profit years (`6834` 2024 median PER `1,152.5x`, 5Y `P50 = 88.31x`, `P90 = 491.67x`), ambiguous trimming swings targets violently (`185.2 / 518.4`).
- **Coarse FinMind taxonomy & costly halt rule:** In FinMind `TaiwanStockInfo.industry_category`, `6834` (resistors), `2492` (passive components), and `2308` (AI power/thermal) are **all classified identically under `電子零組件業`**, preventing reliable code-based cyclical detection, while halting on warning leaves active industries unvalued.

### Flaw 5: Timeframe Mismatch
`Step 8` derives long-term upside/downside from 5-year valuation bands while gating entries and stops on the 20-day moving average (`20MA`), causing horizon conflicts during short-term price spikes. Decoupling a multi-week **Swing layer** from a 12-month **Hold layer** resolves the conflict cleanly.

---

## 5. Upgraded 8-Step Formula Reference (Drop-In Replacement)

If the strategy author wishes to continue operating the standalone 8-step prompt, the table below provides drop-in replacements for each step without altering its overall workflow:

| Step | Original Rule / Formula | Empirical Flaw Found | Recommended Drop-In Upgrade |
|---|---|---|---|
| **Pre-Filter** | Warn on 6 cyclical industries and **halt execution** | 1. Cannot auto-detect via `industry_category` (`6834` = `2308`)<br>2. Non-cyclicals with thin-profit years (`P90 > 60x`) also distort<br>3. Halting drops all reference anchors | Replace halt with **3 automatic distortion checks**: (1) cyclical sector, (2) 5Y `PER P90 > 60x` or 4Q OPM spread `> 5 pp` or any quarter `OPM <= 0`, (3) `TTM OI <= 0`. Flag distortion and cross-check with **`PBR` bands + peer `PE`** instead of halting. |
| **Step 1–2**<br>Revenue Forecast | $a = \text{YTD} + \text{Prior Rem Months} \times (1 + \text{6M YoY Med})$ | Late-year `CY` revenue lags NTM pricing; post-Oct note disconnects from `Steps 4–8` | **Dual CY + NTM tracks:** compute both $a_{\text{CY}}$ and **rolling NTM revenue** $a_{\text{NTM}} = \text{TTM Rev} \times (1 + \text{6M YoY Med})$ for `Steps 4–7` after October. |
| **Step 3**<br>Core Net Margin | `4Q simple avg OPM × 0.8` | 1. Ignores minority interests (`2308`: `89.46%`) & actual tax<br>2. 4Q simple average lags inflections | Use **revenue-weighted TTM OPM × real conversion factors**:<br>$b = \frac{\text{TTM OI}}{\text{TTM Rev}} \times (1 - \text{Eff Tax}) \times \frac{\text{TTM Parent NI}}{\text{TTM Net Income}}$<br>(use actual 4Q `TAX / PreTaxIncome` when in `[0%, 40%]`, else `20%`; parent ratio in `(0%, 100%]`, else `100%`). |
| **Step 4–5**<br>Baseline EPS | $c = a \times b$<br>$d = c \times 10 \div \text{Share Capital}$ | Hardcodes NT$10 par value (fails on NT$5 / flexible par stocks) | $d = \frac{a \times b}{\text{Implied Weighted Shares}}$, deriving shares from latest normal quarter `Parent NI ÷ EPS` (`OrdinaryShare ÷ 10` fallback only), while retaining **unconverted CB / SPO dilution check (`> 5%` warning)**. |
| **Step 6–7**<br>Valuation & Targets | "Winsorized" 5Y `P80`/`P50`/`P20 × d` | 1. Undefined outlier trimming<br>2. Fixed `d × P20` understates Bear contraction | 1. Explicitly define **all valid days (`PER > 0`) over 5 years** for `P20`/`P50`/`P80` with no ad-hoc secondary trimming.<br>2. Apply a cyclical/contraction haircut on Bear EPS (e.g., `0.8 × d × P20` or peer-low intersection) to avoid understating downside. |
| **Step 8**<br>R:R & Trend Filter | $\frac{\text{Opt P80} - \text{Close}}{\text{Close} - \text{Def P20}} \ge 2.5$ + `20MA`/`60MA` filter | 1. Skewed `P80` passes `Close > Fair`<br>2. Zero/negative denominator when `Close <= Def`<br>3. Unquantified "flat/rising" rule | 1. Anchor Hold numerator to **Fair `P50 × d`** and require `Def < Close < Fair` before computing `R:R` (otherwise `"N/A"` / `不適用`).<br>2. Quantify trend filter: `alignment != "bearish"` **and** (`Close >= MA20 & 5d slope >= 0` or `Close >= MA60 & 5d slope >= 0`), else downgrade to `"左側觀察"` (`left_watch`). |

---

## 6. Integration Plan for `tw-equity-report`

For reasons outlined above, we decided **against adding a standalone `dim7` section**—simultaneously publishing two conflicting target-price and `R:R` engines would fragment action signals, and a cyclical halt rule would leave reports incomplete. Instead, we distilled the strategy's four proven upgrades into our existing architecture (`100%` FinMind Free-tier compatible):

1. **Upgrade `dim1` & Action Engine (`"左側觀察"` / `left_watch` Trend Filter):** Add `MA60` and 5-day slopes of `MA20` and `MA60` (`metrics.py`), gating every `BUY` state (including dead-cat bounces above the entry zone) when trend stabilization fails (`derive.py`).
2. **Upgrade `dim4` & `judgment-review.md` (Dual CY / NTM Core Run-Rate Baseline EPS):** Pull `"TAX"` and `"PreTaxIncome"` already included in Free-tier `TaiwanStockFinancialStatements`, surface `data-baseline="cy|ntm"` alongside scenario tables, flag high volatility, and require explicit operational/external justification whenever analyst `Base` EPS exceeds `NTM` baseline by `> +20%`.
3. **Upgrade `dim3` / `dim5` (Mandatory CB / SPO Dilution Verification):** Require Step 4 web/MOPS lookup of unconverted CBs and announced cash capital increases (`analysis["dilution"]`), rendered in `dim3` (`data-dilution`) even when zero dilution exists and mirrored to `dim5` risks if potential dilution exceeds `5%`.
4. **Upgrade `dim6` (Next-Month-10th Monthly Revenue Thesis Breaker):** Enforce via `check_report.py` and `judgment-review.md` that at least one `thesis_breakers` entry specifies `TaiwanStockMonthRevenue` with a concrete numeric threshold.

See the accompanying execution plan at [2026-11-21-tw-equity-report-upgrades.md](../superpowers/plans/2026-11-21-tw-equity-report-upgrades.md).
