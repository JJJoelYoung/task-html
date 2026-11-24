# Methodology

`methodology_version`: 1.0

The rules and parameters of the weekly screen. The scripts implement them, and each week's `funnel.json` `params` records the values that week used. Change a rule here and in its script together, with a unit test, under section 10. [J] marks a value set by judgment rather than evidence, as the research document's sections 4 and 5 tag it; each is a candidate for review under the adoption bar.

## 0. Common rules

- **Universe**: every equity (CFICode `ES*`) in the ISIN lists of TWSE (both sections), TPEx, and the Emerging board. A security is keyed `{code}@{listing_date}`; data inside one week is keyed by `code`, which is unique at any one time.
- **One status each**: every master security ends each week in exactly one terminal status (section 3), with a reason where the status has one.
- **Missing is null**: a missing input is null, never zero. There are two exceptions. A stock absent from T86 or the TPEx institutional table had no institutional flow that day. `adv20` counts a date without a trade as 0.
- **Point in time**:
  - A quarterly season is used only on or after its deadline: Q1 May 15, Q2 Aug 14, Q3 Nov 14, and Q4 Mar 31 of the next year. The run reads the 9 latest due seasons.
  - The market's latest revenue month is the previous month from the 11th on, and the month before that until then. The run reads the 25 months up to it.
  - The ISIN lists and snapshot tables for a past `asof` come only from the cache of a live run on that date.
- **Windows**: 270 trading dates of daily tables, with flows and holdings for the latest 30.
- **Units**: percent or percentage points, except `rev_surge` (a z-score) and counts. Revenue and income are in thousand NT$.
- **Shared definitions**, imported through `scripts/shared.py` and never restated here:
  - the trend filter: [`tw-equity-report` methodology](../../tw-equity-report/references/methodology.md) section 2, run on the last 120 dates with a close;
  - the 6-month median revenue YoY (`rev_yoy_med6`): the same file, section 4 (core baseline);
  - the shortlist deep metrics: `fetch.build`, the same file, sections 1 to 5.

## 1. Price history

| Helper | Definition |
|---|---|
| `history_days` | Dates with a close in the trailing run, counted across boards, so a board transfer keeps its history. The run breaks at the first gap of more than 60 consecutive dates without a close. |
| `adv20` | Median traded value over the last 20 dates; a date without a row or a trade counts as 0. |
| `price_rows` | The last 120 dates with a close, in FinMind's row shape, for the trend filter. |
| `week_ends` | The last date of each of the last 13 ISO weeks, the `asof` week included. |
| `momentum_6_1` | close(i − 21) ÷ close(i − 126) − 1. |

## 2. Raw variables

| Variable | Definition | Needs |
|---|---|---|
| `rev_yoy_med6` | The shared definition (section 0) | |
| `rev_accel` | Mean of the last 3 monthly YoY − mean of the last 12 | 12 consecutive months |
| `rev_surge` | d_t = R_t − R_{t−12}; (d_t − mean(d_{t−12..t−1})) ÷ pstdev(d_{t−12..t−1}); null when that pstdev is 0 | 25 consecutive months |
| `rev3`, `rev3_ly`, `rev_yoy3` | Revenue over the last 3 months; over the same months a year earlier; `rev3 ÷ rev3_ly × 100 − 100` | |
| `opm_ttm` | Σ operating income ÷ Σ revenue × 100 | 4 consecutive quarters |
| `opm_delta_4q` | `opm_ttm` of the last 4 quarters − the same over quarters 5 to 8 back | 8 consecutive quarters |
| `opm_spread_4q` | max − min of the last 4 quarterly operating margins | 4 consecutive quarters |
| `roe_ttm` | TTM EPS ÷ (close ÷ PBR) × 100 | 4 consecutive quarters; PBR > 0 |
| `ttm_op_income` | Σ operating income over the last 4 quarters (the L2 loss test) | 4 consecutive quarters |
| `earnings_yield`, `book_yield` | 100 ÷ PER when PER > 0; 100 ÷ PBR when PBR > 0 | The `asof` valuation tables |
| `flow20_pct` | Σ (foreign + investment trust) net shares over the last 20 dates ÷ shares outstanding × 100 | Shares outstanding |
| `trust_days20` | Dates in the last 20 with investment-trust net buying above 0 | |
| `ret13w` | close ÷ close 65 dates earlier × 100 − 100 | |
| `persist13` [J] | Of the 13 week-ends, how many put the stock's `momentum_6_1` in the top third: rank ≤ ceil(n ÷ 3) among the full-track stocks with momentum that week | Momentum at all 13 week-ends |
| `one_off` | The latest month has a 備註 note and a YoY above 100% | |

- **Quarters**: income is filed year to date. Q1 is used as filed; a later quarter is YTD(s) − YTD(s − 1) of the same year.
- **Foreign and trust flows**: foreign is foreign investors plus foreign dealers; trust is investment trusts.
- **Shares outstanding**: TWSE 發行股數 from `MI_QFIIS`; TPEx 發行股數 from the quotes.
- **Late filer**: when a stock's latest revenue month is before the market's latest month, every revenue variable (`rev_yoy_med6`, `rev_accel`, `rev_surge`, `rev3`, `rev3_ly`, `rev_yoy3`) is null.
- **Non-general template**: a code that filed on any template other than the general one in the 9 seasons, and is not on the general template in the latest season, is non-general (section 3).

## 3. Funnel (L0 to L5)

Track: `full` for TWSE and TPEx stocks with `history_days` ≥ 120 [J]; every other security, Emerging included, is `watch` (section 8). A young stock enters the full funnel at the first weekly run after it reaches 120 days.

Statuses are evaluated in this order, and the first match is final:

| Layer | Rule | Status (reason) |
|---|---|---|
| Track | Watch track | `watch_track` |
| L1 | Any exclusion tag (below) | `excluded_status` (the tags) |
| L1 | No close on `asof` | `excluded_no_quote` |
| L1 | `adv20` below NT$30,000,000 [J] | `excluded_liquidity` |
| L1 | Close below NT$10 [J] | `excluded_price` |
| L2 | Industry 金融保險業 (excluded in v1) | `excluded_financial` |
| L2 | Non-general template (section 2) | `insufficient_data` (`non_general_template`) |
| L2 | `ttm_op_income` known and ≤ 0 | `excluded_loss` |
| Score | Availability below 0.70 (section 4) | `insufficient_data` (`availability`) |
| L3 | Unfavoured industry, outside the exception lane (section 5) | `excluded_sector` (the industry) |
| L4 | Any group score below −1 [J] | `excluded_floor` (the groups) |
| L4 | Every other scored stock | `ranked` |
| L5 | Shortlisted (section 6) | `shortlist_actionable`, `shortlist_left_watch` |

Status tags, from the snapshots and the quotes:

| Tag | Kind | Source |
|---|---|---|
| `altered_trading` | Exclusion | TWSE `TWT85U`; TPEx `tpex_cmode` AlteredTrading |
| `managed` | Exclusion | TPEx `tpex_cmode` ManagedStock; the TPEx quotes' 管理股票 table |
| `suspended` | Exclusion | TWSE `TWTAWU`, halted on or before `asof` and not resumed by then; TPEx `tpex_cmode` SuspensionOfTrading |
| `disposition` (處置) | Red flag | TWSE `punish`, TPEx `tpex_disposal_information`, while the period ends on or after `asof` |
| `attention` (注意) | Red flag | TWSE `notice`, TPEx `tpex_trading_warning_information` |
| `periodic_auction` | Red flag | TPEx `tpex_cmode` PeriodicTrading or MatchingFrequency |
| `one_off_revenue` | Red flag | `one_off` (section 2) |
| `cash_offering` | Flag | TWSE `TWT48U_ALL`, TPEx `tpex_exright_prepost`: a subscription ratio above 0 and an ex-date on or after `asof` |
| `tib` | Flag | The Taiwan Innovation Board, which v1 includes |
| `exception_lane` | Flag | Passed L3 through the exception lane |

A status row whose date cannot be read counts as in force. Red flags block Tier A (section 7); the other flags only annotate.

## 4. Composite (L4)

Over the stocks that pass L2:

1. Winsorize each variable market-wide at its 5th and 95th percentiles (linear interpolation).
2. Z-score it within its ISIN industry (the label TWSE and TPEx share), with the population standard deviation; a standard deviation of 0 gives 0. An industry with fewer than 5 values uses the market-wide z-score. Clip at ±3.
3. Group score: the member-weighted mean of the available member z-scores, each times its sign.
4. Availability: the sum of the weights of the groups that have a score. Below 0.70, the stock is `insufficient_data`.
5. Composite = 0.8 × Σ (weight × group score) ÷ availability + 0.2 × sector score (section 5).

| Group | Weight [J] | Members (member weight, sign) |
|---|---|---|
| Growth | 0.35 | `rev_yoy_med6` (1, +), `rev_accel` (1, +), `rev_surge` (1, +), `opm_delta_4q` (1, +) |
| Valuation | 0.25 | `earnings_yield` (0.67, +), `book_yield` (0.33, +) |
| Quality | 0.15 | `opm_ttm` (1, +), `opm_spread_4q` (1, −), `roe_ttm` (1, +) |
| Flow | 0.15 | `flow20_pct` (1, +), `trust_days20` (1, +) |
| Persistence | 0.10 | `persist13` (1, +) |

## 5. Sector gate (L3)

Per industry, over its members that pass L2:

| Input | Definition |
|---|---|
| `rev_breadth` | The % of members with `rev_yoy3` above 0, among those with a value |
| `rev_yoy3` | Σ `rev3` ÷ Σ `rev3_ly` × 100 − 100, over the members with both |
| `rel_ret13` | The members' mean `ret13w` − the mean over every stock that passes L2 |
| `trend_breadth` | The % of members passing the trend filter |

- The sector score is the mean of the four inputs' z-scores across the industries with at least 5 members (population standard deviation; a null input is skipped). An industry with fewer than 5 members scores 0 and is never unfavoured.
- The lowest floor(count ÷ 3) of those industries by score are unfavoured [J]; ties break by industry name.
- **Exception lane**: a stock in an unfavoured industry passes when its composite ranks within the top ceil(5% × scored stocks) market-wide [J], flagged `exception_lane`. The rest are `excluded_sector`.

## 6. Ranking and shortlist (L4 and L5)

- `ranked` stocks are ordered by composite, ties by code; `rank` counts from 1. `rank_trend` counts separately among the stocks that pass the trend filter and among those that fail it.
- **Actionable**: trend-pass stocks with `rank_trend` ≤ 20, plus last week's actionable stocks still at `rank_trend` ≤ 40 (hysteresis), in `rank_trend` order, cut at 30 [J].
- **Left-side watch (左側觀察)**: the 10 best trend-fail stocks by `rank_trend` [J].
- **Deep metrics**: `fetch.build(code, [], asof)` for every shortlisted stock, cached whole at `finmind/{asof}/{code}.json` under the raw cache root. The row keeps the close, PER P50 and current percentile, PBR current percentile, NTM core baseline EPS with its `applicable` and `high_volatility` flags, cash conversion, the institutional cost zone, and gaps.
- **Revenue note**: `revenue_note` holds the latest revenue month and its 備註 note, when it has one, for the weekly review.

## 7. BUY proxy and tiers (L6)

- **BUY proxy** = (NTM core baseline EPS × own 5-year PER P50 ÷ close − 1) × 100. It is null unless the core baseline is applicable and all three inputs are positive.
- **Tier A**: actionable, passes the trend filter, has no red flag, and has a BUY proxy above 15.0 [J], mirroring `tw-equity-report`'s BUY rule. **Tier B**: every other shortlisted stock.

## 8. Watch track and regime

- **Upcoming listings**: TWSE `applylistingLocal` and TPEx `tpex_esb_applicant_companies` rows applied within the last 365 days whose listing date is on or after `asof`, or not set; sorted by listing date (unset last), then application date.
- **Recent listings**: watch-track TWSE and TPEx stocks, with `history_days`, `days_to_full` = 120 − `history_days`, and the first-five-day window from `TWT88U` or `tpex_ipo_no_limit`.
- **Emerging standouts**: Emerging stocks with `rev_yoy_med6` ≥ 20.0 and each of the last 3 monthly YoY above 0 [J], shown with their Emerging quote (average, last, volume, applying status).
- **Regime flag**, on the TAIEX close from the TWSE quotes:
  - It reports the close, MA60, the MA60 change over 5 dates, and `ret12m`, the return against the close 250 dates back. `above_ma60` is close > MA60.
  - `transition` is true when `above_ma60`, or the sign of `ret12m`, changed within the last 20 dates; `reasons` names `ma60_cross` or `ret12m_sign`.
  - With fewer than 270 closes, `transition` is null and `reasons` is `insufficient_history`.
  - The flag annotates the page and never blocks the shortlist.

## 9. Week over week and forward tracking

- **Universe events**: new listings, exits, transfers, renames, and reused codes. A code that changed market is one transfer, not an exit plus a listing. Status changes are tag changes against the previous week's `universe.csv`.
- **Invariants**: the statuses sum to the master count, and the master count moved by new listings minus exits. A failure exits 1 before anything is written.
- **Diff**: entries; exits with a reason (`rank_out`, `trend_failed`, the new status, or `delisted`); rank and composite deltas; streaks; and each shortlisted code's latest `tw-equity-report`.
- **Forward tracking**: `forward.csv` records each week's Tier A and actionable lists with their `asof` closes. For each list and each fully elapsed horizon of 4, 13, 26, and 52 weeks, `forward_stats` reports:
  - `weeks` (cohorts) and `names` (name observations, pooled);
  - `hit_rate`, the % of observations beating the TAIEX;
  - `median_excess_taiex`, and `median_excess_ew` against the equal-weight L1 universe of the cohort's week;
  - `turnover`, the mean weekly share of names replaced.
- **Forward pricing**: a close missing on the horizon date falls back to the latest earlier close. A cohort whose TAIEX close at either end lies outside the 270-date panel is skipped, so the 52-week row covers only cohorts inside it. Returns exclude costs and dividends.
- **BUY conversion**, the primary metric: among the Tier A names with a `tw-equity-report` dated on or after their week's `asof`, the share rated 買進 with an action other than 左側觀察.

## 10. Change control and adoption bar

- Every rule change bumps `methodology_version` (`METHODOLOGY_VERSION` in `scripts/history.py`, stamped on every week file) and adds a changelog line with its reason. Record every variant tried, adopted or not, since an unrecorded search overfits.
- A new factor or threshold is adopted only when a point-in-time backtest gives it a t-statistic above 3 (Harvey, Liu and Zhu, 2016). When several variants are compared, also estimate the probability of backtest overfitting (PBO) by combinatorially symmetric cross-validation, and reject a variant whose PBO is above 0.05 (Bailey et al., 2017).
- Expect about half of a published premium to survive. Judge the results against the base rate that most screens fail to beat their benchmark.
- Review the persistence group first. If its forward contribution is not positive after 26 weeks, propose removing it.

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-24 | First version, from the research document of 2026-11-23 (sections 4 and 5). |
