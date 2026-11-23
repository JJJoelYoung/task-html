# Taiwan Equity Screener: Research Synthesis and Design Proposal

> **Scope:** How to design a weekly, multi-stage stock-screening funnel for TWSE (上市) and TPEx (上櫃) common stocks, with a separate watch track for Emerging Stock Board (興櫃) and newly listed stocks, whose shortlist feeds `tw-equity-report`. Target style, chosen by the user: growth × reasonable valuation × trend and institutional-flow confirmation, ranking the stocks most likely to earn "BUY with an actionable entry" from `tw-equity-report`.
>
> **As of:** 2026-11-23. Market data snapshots are from trading date 2026-11-20.

---

## 1. Executive Summary

1. **Use one integrated composite score.** Do not take the union of several single-factor screens. AQR's long-only backtest found that one combined value-plus-momentum score beat a mix of separate single-style portfolios: 3.6% versus 2.5% annual excess return, with the information ratio rising from 0.6 to 0.9. The advantage is contested: a later peer-reviewed test found no robust edge for either approach, and AQR's claim about where the extra alpha came from failed verification (F7). The composite is still the simpler design, and MSCI builds its multi-factor score the same way. Standardize the way MSCI does: winsorize, z-score within each sector, average.
2. **Taiwan's edge is monthly revenue, not raw price momentum.** Monthly revenue surprises predict later earnings surprises and returns. They add information beyond analyst forecasts, and prices drift toward them until the quarterly report. Plain past-winner momentum has repeatedly failed in Taiwan; it works only when a stock stays a winner (persistence) and the market regime does not flip. So price trend should be an entry gate (`tw-equity-report`'s MA20/MA60 filter) plus a small persistence score, not a heavily weighted factor.
3. **Universe completeness takes a reconciliation protocol, not a single list.** This was tested live. The official ISIN lists hold 2,362 equity securities: TWSE 1,088 (1,057 in 股票 plus 31 in a separate 創新板 section), TPEx 898, and Emerging 376. Three silent-omission traps were found and reproduced:
   - Filtering by a `TW` ISIN prefix drops every KY issuer: 91 on TWSE, 30 on TPEx, and 6 on Emerging.
   - Reading only the 股票 section drops the 31 創新板 stocks.
   - Reading only MOPS's domestic revenue file drops the 92 TWSE and 30 TPEx foreign issuers.
4. **Free data covers the full-market layers.** TWSE and TPEx publish free full-market tables. Some can be queried by date: daily quotes, institutional flows (T86 back to 2012-05-02), foreign holdings, PER/PBR and margin balances for both boards, MOPS monthly revenue by month, and MOPS quarterly income statements by season. Others, the OpenAPI snapshots, return only the latest table. FinMind's Free tier (600 requests per hour, one stock per request) is needed only for the final shortlist of at most 40 stocks, reusing `tw-equity-report`'s `fetch.py` at about 9 requests per stock.
5. **Weekly history must be point-in-time and auditable.** Archive raw snapshots with their fetch date, and key each security on code plus listing date, because codes are reused. Every security in the master must appear exactly once in each week's score table, with a final status. Add hysteresis buffers so the weekly list does not churn.
6. **Validate by forward-tracking, not by backtest alone.** Track each weekly list as a paper portfolio over 4, 13, 26, and 52 weeks. Require a t-statistic above 3 before adopting a new factor, and log every variant tried. The primary success metric is the **BUY conversion rate**: the share of Tier A names that `tw-equity-report` rates 買進 with an active entry.
7. **Keep deep research off the weekly critical path.** This research run planned 107 agents; the 46 that finished used about 5.9M subagent tokens before the usage limit stopped it. Finishing its verification and synthesis took another 49 agents and about 2.9M tokens. The weekly screen should run on scripts, and deep research is an opt-in switch that is off by default (decision D5). Finalists still get deep research through `tw-equity-report`, which runs it in Step 4.

---

## 2. Method and Evidence Status

- **Deep-research workflow** (run `wf_5abdd4ae-e0b`, 2026-11-22). It ran 5 search angles, fetched 25 sources, and extracted 124 claims with verbatim quotes. The 5-hour usage limit stopped the run during verification, after 5 claims had passed 3-0 adversarial verification. The synthesis step never ran, so this document was first synthesized in session.
- **In-session verification** (2026-11-22/23). Eight key academic and practitioner sources were spot-checked: each page was fetched and the quoted phrases were confirmed present. Every data-source claim used in the design was tested with live calls.
- **Verification completed** (run `wf_e58b5eef-8dd`, 2026-11-23). The remaining 16 literature claims of the first run got the same 3-vote check with the same prompts, then its synthesis step ran. Of all 21 literature claims, 18 passed 3-0, 2 passed 2-1, and 1 was refuted 1-2. Its 4 ISIN-structure claims were skipped because section 3.3 reproduced them live. Section 3 tags reflect these votes.

Evidence tags used below:

| Tag | Meaning |
|---|---|
| **[V3]** | Passed 3-0 independent adversarial verification in the workflow. |
| **[V2]** | Passed 2-1: it survives, but one verifier's objection is recorded next to it. |
| **[SP]** | Spot-checked in session: the source page was fetched and the quoted phrase found. Paywalled papers were checked at abstract level only. |
| **[LIVE]** | Reproduced by live calls to the endpoint on 2026-11-22/23. |
| **[EX]** | Extracted by a fetch agent with a verbatim quote, but not independently re-verified. |
| **[J]** | Design judgment: a tunable default, not a research finding. |

---

## 3. Findings

### 3.1 Funnel architecture and factor combination (industry practice)

| # | Finding | Evidence |
|---|---|---|
| F1 | Factor indexes screen for investability before scoring. MSCI uses an existing parent index as the eligible universe "to provide an opportunity set with sufficient liquidity and capacity." A stock needs at least 7 months of price to receive a momentum score. | [V3] MSCI Momentum 2025-07 |
| F2 | Entries and exits are asymmetric. IPOs added to the parent index wait for the next scheduled review; parent-index deletions apply immediately. | [V3]/[EX] MSCI Quality 2025-05, DMF 2022-05 |
| F3 | Standardization recipe: rank, winsorize raw values at the 5th and 95th percentiles, z-score with the universe mean and standard deviation, flip the sign for lower-is-better variables, then average with equal weights. | [V3] MSCI Quality 2025-05 |
| F4 | Sector-neutral variant: re-standardize the composite within each sector and winsorize at ±3. | [V3] MSCI Quality 2025-05 |
| F5 | The MSCI multi-factor (DMF) index scores Value and Quality relative to sector, and scores Momentum and Size on plain winsorized z-scores. Value = 0.33 × book-to-price + 0.67 × earnings yield. Its composite gives the four factors equal weights (0.25 each) and is built from stock-level scores, not by blending single-factor indexes. DMF's momentum input comes from the proprietary Barra model and cannot be rebuilt from free data. | [V3] MSCI DMF 2022-05 |
| F6 | Standard momentum signal: 6-month and 12-month returns that skip the latest month, risk-adjusted by 3 years of weekly volatility, z-scored, and averaged 50/50. | [V3] MSCI Momentum 2025-07 |
| F7 | One integrated score beats mixing single-style portfolios: 3.6% versus 2.5% excess return per year, and an information ratio of 0.9 versus 0.6 (1993–2015, MSCI World-like universe, net of costs). Limits: AQR authors, value and momentum only, mean-variance optimized portfolios rather than a top-N cut, and a smaller benefit at low tracking error. Leippold & Rüegg (EFM 2018) used more robust tests and found no reliable edge for either approach. **Refuted 1-2:** that the gain comes from stocks decent on both styles (3.2% alpha, t = 3.1) rather than stocks extreme on one (1.4%, t ≈ 1). The paper never tests that difference, so do not use it to justify rejecting single-factor standouts. | [V3] main result; refuted sub-claim. AQR 2017 |
| F8 | The AQR backtests spent 80% of the active risk budget within industries and 20% across industries. This is a template for partial sector neutrality. | [EX] AQR 2017 |
| F9 | Turnover control with rank buffers. MSCI Quality targets 300 names: it adds ranks 1–240 first and keeps existing members ranked up to 360. MSCI Momentum targets 500 names: it adds the top 250 and keeps members ranked up to 750. | [EX] MSCI |
| F10 | A buy/hold spread (buy when a stock enters the top 10%, sell when it leaves the top 20%) was the single most effective cost-reduction rule tested. It cut turnover by 41% and transaction costs by 42%. | [SP] phrase; [EX] numbers. Novy-Marx & Velikov 2016 |
| F11 | Base rates for screens: only 18 of AAII's 55 tracked screens beat the S&P 500 over 5 years, and 14 over 10 years. The best 2025 screen, a GARP/PEG screen, averaged only 2 passing stocks. AAII treats screening as "just the starting point," which supports a qualitative-review stage. Objection on record: both windows fall in a decade led by US mega-caps, and many AAII screens beat the index since 1998. | [V2] base rate; [EX] the rest. AAII 2026-01 |
| F12 | Factor decay: across 97 predictors, returns were 26% lower out of sample and 58% lower after publication. About 45% of the in-sample premium survives. | [EX] CFA Digest of McLean & Pontiff |

### 3.2 Taiwan-specific evidence

| # | Finding | Evidence |
|---|---|---|
| T1 | Monthly revenue surprises significantly predict future earnings surprises, beyond analyst forecasts. Prices drift with them until the quarterly announcement, and do not react to them at the announcement itself, so the signal is consumed by then. Analysts revise forecasts after each monthly release. | [V3] abstract. RQFA 58(1), 2022 |
| T2 | Unexpected monthly revenue (MSURGE) predicts earnings growth and returns. MSURGE, QSURGE, and QSUE are correlated, but each independently explains returns. Institutions (三大法人) increase holdings before positive MSURGE announcements. A strategy combining them out of sample performed well. | [V3] abstract (paywalled; no formula or effect size). Airiti 2022 |
| T3 | Taiwan is "a remarkable exception to the momentum phenomenon." Winner and loser portfolios turn over heavily, which weakens momentum. A **persistency-based** long-short strategy (buy stocks that stay winners, short stocks that stay losers) earns significant intermediate-term profits, including in other markets. Objection on record: the authors' 2018 paper defines a persistent winner as one that stays in the winner group for at least one more month **after** formation, which is known only in hindsight, and finds that over 40% of winners leave the group the next month. A count of past weeks in the top group, as in 4.3, is an untested backward-looking proxy. | [V3] failure and turnover; [V2] persistency profits. PBFJ 78, 2023; EFM 24(5), 2018 |
| T4 | Momentum earns significant profits when the market stays in the same state and reverses at state transitions. The profit is concentrated in high-attention stocks. | [V3] abstract. Lin, Ko, Feng & Yang, PBFJ 38, 2016 |
| T5 | Counterpoint: in a TWSE-only study (data 1975–2003), April-to-August momentum was **not** significantly different between up and down markets. Industry explains about 40% of momentum; the 1987–1997 subperiod was insignificant. Evidence on a market-regime gate is therefore mixed. | [SP] title; [EX] numbers. IJFR 7(2), 2016 |
| T6 | Industry momentum comes from close product-market peers. Coarse industry momentum loses significance among larger firms. Taiwan's official categories are coarse; `電子零組件業` lumps resistors, passives, and AI power together. | [EX] JFQA 2018 (US); [LIVE] repo 8-step review |
| T7 | Taiwan listed and OTC companies must publish the prior month's revenue by the 10th of each month. | [SP] Airiti 2022 abstract |

**Implications [J]:** Weight revenue growth, acceleration, and surprise most heavily. Refresh them after each 10th-of-month release and treat them as stale after the matching quarterly report. Use price trend as a gate, and add a small persistence score instead of a 12-1 momentum rank. The persistence score extrapolates T3 (see its objection), so validation reviews it first. Make the market regime a caution flag, not a block.

### 3.3 Universe completeness (reproduced live)

| # | Finding | Evidence |
|---|---|---|
| U1 | The authoritative master is the ISIN service (`isin.twse.com.tw/isin/C_public.jsp?strMode=2/4/5`). It lists 上市日, 市場別, official 產業別, and CFICode for every security. On 2026-11-23 it held 2,362 equities: TWSE 1,088, TPEx 898, and Emerging 376. | [LIVE] |
| U2 | **創新板 trap:** the 31 Taiwan Innovation Board stocks sit in their own section, with 市場別 `上市臺灣創新板`. Reading only 股票, or only `市場別 == 上市`, drops them. | [LIVE] |
| U3 | **KY ISIN trap:** Cayman and other foreign issuers have non-`TW` ISINs (for example `KYG...`): 91 on TWSE, 30 on TPEx, and 6 on Emerging. Use `CFICode` starting with `ES`, not `ESVUFR` exactly, because 3673 TPK-KY is `ESVTFR`. | [LIVE] |
| U4 | **Mixed security types:** STOCK_DAY_ALL (1,393 rows), T86, and TPEx dailyQuotes (13,807 rows) include ETFs, warrants, preferred shares, ETNs, and DRs. Code patterns fail: legacy ETFs such as 0050–0061 have 4 digits, and 91xx codes are DRs. Join on the ISIN equity set instead. | [LIVE]/[EX] |
| U5 | **T86 omits idle names:** it lists only stocks that institutions traded that day (1,360 rows versus 1,393 quotes). A missing row means zero institutional flow; the stock must not be dropped from the universe. | [EX] |
| U6 | **Codes are reused:** 2432 and 2301 were delisted and later reassigned to different companies. Key securities on code plus listing date. | [EX] |
| U7 | **Transfers look like delistings:** TWSE's delisting list includes 6423, which moved to TPEx on the same day. Match exits against the other boards before treating them as exits. 上市日 resets on transfer (8908 欣雄: 2026-10-16 on TWSE after trading on TPEx since 1997). | [EX] |
| U8 | FinMind `TaiwanStockInfo` covered 2,361 of the 2,362. The only miss was 6623, which registered on Emerging that day. It also carries stale rows (ETFs, delisted codes). Four active codes had stale dates (1808, 4804, 8084, 8291), matching suspended stocks with no quote row. | [LIVE] |
| U9 | Listing pipeline sources: TWSE `applylistingLocal` and TPEx `tpex_esb_applicant_companies`; Emerging `ApplyingStatus`; first-five-day lists `TWT88U` and `tpex_ipo_no_limit`. **TWSE `applylistingLocal` keys are shifted by one column**, so parse it by position. | [LIVE] |
| U10 | Delistings are rare (2–5 per year recently on TWSE), and the list picked up a 2026-11-18 exit within 5 days. | [EX] |
| U11 | Survivorship: keep delisted and full-cash-delivery stocks in historical snapshots, as the Taiwan momentum study did. | [EX] |

### 3.4 Free data feasibility and publication lags

| Need | TWSE (上市) | TPEx (上櫃) | Emerging (興櫃) | By date? | Status |
|---|---|---|---|---|---|
| Security master | ISIN `strMode=2` | ISIN `strMode=4` | ISIN `strMode=5` | Snapshot | [LIVE] |
| Company master (listing date, industry, shares) | OpenAPI `t187ap03_L` | `mopsfin_t187ap03_O` | `mopsfin_t187ap03_R` | Snapshot | [LIVE] |
| Daily quotes | `rwd/zh/afterTrading/MI_INDEX?date=&type=ALLBUT0999` | `www/zh-tw/afterTrading/dailyQuotes?date=` | `tpex_esb_latest_statistics` | TWSE, TPEx yes; Emerging no | [LIVE] |
| Institutional flows | `rwd/zh/fund/T86?date=&selectType=ALLBUT0999` (from 2012-05-02) | `www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=` | — | Yes | [LIVE] |
| Foreign holding | `rwd/zh/fund/MI_QFIIS?date=` | `tpex_3insti_qfii` | — | TWSE yes | [LIVE] |
| PER / PBR / yield | `rwd/zh/afterTrading/BWIBBU_d?date=&selectType=ALL` | `web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json&d={roc}/{m}/{d}` | — | Yes (2024-11-20 and 2026-11-20 tested) | [LIVE] |
| Monthly revenue | MOPS `nas/t21/sii/t21sc03_{roc}_{m}_{0,1}.html` | `.../otc/...` | `.../rotc/..._0.html` | Yes (by month) | [LIVE] |
| Quarterly income | MOPS `ajax_t163sb04` POST (`TYPEK=sii`, year, season) | `TYPEK=otc` | `TYPEK=rotc` | Yes (by season) | [LIVE] sii |
| Margin balances | `rwd/zh/marginTrading/MI_MARGN?date=&selectType=ALL` | `web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={roc}/{m}/{d}` | — | Yes (2024-11-20 tested) | [LIVE] |
| Cash offerings (ex-rights schedule) | OpenAPI `TWT48U_ALL` | `tpex_exright_prepost` | — | Snapshot of upcoming ex-dates only | [LIVE] |
| Index history | `MI_INDEX` (TAIEX) | `web/stock/iNdex_info/inxh/Inx_result.php?l=zh-tw&o=json&d={roc}/{m}` (by month); OpenAPI `tpex_index` (current month) | — | Yes | [LIVE] |
| Cash flow, convertible bonds | Not in OpenAPI | Not in OpenAPI | — | — | [EX] → FinMind / MOPS for the shortlist |
| Status lists | `TWT85U`, `TWTAWU`, `announcement/punish`, `announcement/notice` | `tpex_cmode`, `tpex_disposal_information`, `tpex_trading_warning_information` | `tpex_esb_disposal_information` | Snapshot | [LIVE] |

Caveats for the exchange tables [LIVE]:

- The TPEx PER table gained a column (`財報年/季`) between 2024 and 2026, and its company names carry trailing spaces. Parse fields by name and strip values.
- The cash-offering tables list only upcoming ex-rights dates, and mostly dividends. A subscription ratio above 0 marks a rights offering to existing shareholders. The price field can be text (`尚未公告`, `註4`) until it is announced. On 2026-11-23, TWSE listed 27 rows (5 with a subscription) and TPEx 65 rows (2 with a subscription).

The MOPS revenue and income files are full-market in one request, but they come with these caveats:

- MOPS revenue files are split into domestic (`_0`) and foreign (`_1`) issuers. October 2026: TWSE 997 + 92, TPEx 868 + 30, Emerging 367. [LIVE]
- Each revenue file has industry subtotal (合計) rows, usable for sector revenue breadth, and a 備註 column, usable for flagging one-offs. [EX]
- Historical files are regenerated (a file for April 2024 was stamped 2026-11-17) and may carry restated comparison figures. Archive your own copy at fetch time for point-in-time use. [EX]
- Quarterly figures are year-to-date cumulative. Difference consecutive quarters to get standalone quarters. [EX]
- Financial-sector templates have no revenue or operating-income columns. [EX]

Publication lags, for point-in-time rules [EX, MOPS]:

| Data | Deadline |
|---|---|
| Monthly revenue | By the 10th of the following month |
| General industry | Q1 May 15, Q2 Aug 14, Q3 Nov 14, annual Mar 31 |
| Financial holding companies | Q1 May 30, Q2 Aug 31, Q3 Nov 29 |
| Banks, insurers, securities firms | Q2 Aug 31 |
| Emerging (semi-annual) | Q2 Aug 14, annual Apr 30; Q1 and Q3 only from listing applicants |

On 2026-11-22 only 3 of 13 financial holding companies had filed Q3. A single calendar cutoff is therefore wrong for financials.

Operational notes:

- **Rate limits [J]:** TWSE and TPEx do not document limits in the sources reviewed. Throttle to at least 3 seconds between requests, retry with backoff, and cache every response.
- **Bot blocking [EX]:** the TPEx/TWSE industry value-chain platform (`ic.tpex.org.tw`) returned HTTP 403 to automated fetchers. It has 47 chains with upstream, midstream, and downstream segments, but no API, and its terms forbid redistribution.

### 3.5 Weekly operation and validation

| # | Finding | Evidence |
|---|---|---|
| W1 | AAII validates screens by forward-tracking hypothetical portfolios. Each is equal-weighted, rebuilt every period, and excludes costs and dividends; AAII notes this overstates returns, most for high-turnover screens. | [V3] AAII |
| W2 | Use a single hold-out sample only with at least 1,000 observations, which is about 20 years of weekly data. Any search over configurations overfits to some degree, so record every configuration tried. The Probability of Backtest Overfitting (PBO), computed by combinatorially symmetric cross-validation (CSCV), estimates the damage; reject a configuration when PBO > 0.05. | [EX] Bailey et al., J. Comp. Finance 2017 |
| W3 | A newly proposed factor needs a t-ratio above 3.0, not 2.0. | [SP] Harvey, Liu & Zhu, RFS 2016 |
| W4 | Strategies with less than 50% one-sided monthly turnover mostly survive trading costs; few above that do. | [EX] Novy-Marx & Velikov, RFS 2016 |

---

## 4. Proposed Design: `tw-equity-screener`

### 4.1 Principles

1. **One definition per metric across both skills.** The trend filter, the 6-month median revenue YoY, core baseline EPS, and the valuation bands are imported from `tw-equity-report/scripts/metrics.py`, never re-implemented.
2. **Nothing is dropped silently.** Each week, every master security ends in exactly one terminal status with a reason.
3. **Scripts compute, the LLM reviews.** Every number comes from a script, as in `tw-equity-report`.
4. **Point in time.** A datum is used only after its publication date, and history is keyed on `(code, listing_date)`.
5. **Narrow top-down, with an exception lane.** Sector gating narrows the field, but an exceptional stock in a weak sector can still pass.

### 4.2 Funnel

Indicative counts come from the 2026-11-20 snapshot. That was a heavy-volume crash day, so the liquidity counts are high.

| Layer | Rule (default) | Data | Evidence | Count |
|---|---|---|---|---|
| **L0 Universe** | ISIN equities (CFI `ES*`), all boards and both TWSE sections, reconciled against FinMind `TaiwanStockInfo` and the quote tables. Key is `(code, listing_date)`. Weekly events: new, exit, transfer, rename, code reuse. | ISIN, FinMind, quotes | U1–U8 | 2,362 |
| **L0 Track split** | Full funnel: TWSE + TPEx with at least 120 trading days of price history, counted across boards. Watch track: all Emerging stocks plus younger stocks. | Archive | F1, F2 [V3]; 120 days [J] | ~1,980 / ~380 |
| **L1 Investability** | Exclude altered trading or full-cash delivery (`TWT85U`, `tpex_cmode`), managed stocks, and suspended stocks. Require a 20-day median traded value of at least NT$30M and a close of at least NT$10. Flag 處置 and 注意 stocks as not actionable this week. | Status lists, daily quotes | F1; thresholds [J] | ~700–800 |
| **L2 Red flags** | Exclude TTM operating income ≤ 0. Route 金融保險業 out of the revenue factors (v1: exclude). Flag revenue rows with a 備註 note and YoY above 100% as possible one-offs. Flag `cash_offering` when `TWT48U_ALL` or `tpex_exright_prepost` lists a subscription ratio above 0 with an ex-date on or after `asof`; it is a flag, not an exclusion. Convertible bonds stay a `tw-equity-report` Step 4 check (see Known Gaps). | MOPS t163sb04, t21sc03; ex-rights tables | 3.4 caveats; rules [J] | ~550–650 |
| **L3 Sector gate** | Sector score = mean z of four inputs: revenue breadth (% of members with 3-month revenue YoY > 0), industry subtotal 3-month YoY, 13-week equal-weight relative return, and trend breadth (% passing the trend filter). The bottom-third sectors are unfavoured: their stocks pass only through the exception lane (top 5% market-wide composite). | MOPS 合計 rows, archive | T5, T6; gate [J] | ~400–500 |
| **L4 Composite** | See 4.3. Hard floor: any factor-group z below −1 excludes the stock. | All of the above | F3–F8; floor [J] (F7's refuted sub-claim does not support it) | ranked |
| **L4 Trend gate** | `tw-equity-report` trend filter: alignment not bearish, and either (close ≥ MA20 with 5-day slope ≥ 0) or (close ≥ MA60 with 5-day slope ≥ 0). | Archive | Shared code | split |
| **L5 Shortlist** | Actionable: among stocks passing the trend gate, those ranked ≤ 20, plus last week's actionable names still ranked ≤ 40 (hysteresis), capped at the 30 best ranks. Left-side watch (左側觀察): the top 10 that fail only the trend gate. | Scores | F9, F10 | ≤ 40 |
| **L5 Deep metrics** | FinMind, per stock, via `fetch.py`: 5-year PER/PBR band percentile, NTM core baseline EPS, cash conversion, institutional cost zone. **BUY proxy** = NTM core baseline EPS × own 5-year PER P50 ÷ close − 1. | FinMind Free | ~9 requests/stock | ≤ 360 requests |
| **L6 Tiering** | **Tier A:** BUY proxy > +15%, trend gate passes, no red flag (next step: `/tw-equity-report <code>`). **Tier B:** the rest of the shortlist. | Shortlist | [J] mirrors the report's BUY rule | 3–5 / rest |

### 4.3 Composite score

| Group | Weight [J] | Inputs (computed full-market from free data) |
|---|---|---|
| Growth | 35% | `rev_yoy_med6` (same definition as the report); `rev_accel` = mean YoY of the last 3 months − mean YoY of the last 12 months; `rev_surge` = (d_t − mean of the prior 12 values of d) ÷ their population standard deviation, where d_t = R_t − R_{t−12} (a SURGE-style choice, since T2's exact formula is paywalled; it needs 25 months of revenue); TTM operating margin minus its level 4 quarters ago |
| Valuation | 25% | 0.67 × earnings yield (1/PER, PER > 0) + 0.33 × book yield (1/PBR), sector-relative (F5 weights) |
| Quality | 15% | TTM operating margin; 4-quarter operating-margin spread (lower is better); ROE = TTM EPS ÷ BVPS |
| Flow | 15% | 20-day (foreign + investment trust) net buy ÷ shares outstanding; investment-trust net-buy days in the 20-day window |
| Persistence | 10% | Weeks out of the last 13 in which the stock ranked in the top third by 6-month return skipping the last month. A backward-looking proxy for T3's persistence, which T3 does not test [J] |

Combination [V3 for the recipe, J for the weights]:

1. For each variable, winsorize at the 5th and 95th percentiles of the eligible universe.
2. Z-score within industry, then winsorize at ±3.
3. Group score = mean of the available member z-scores.
4. Composite = 0.8 × Σ(weight × group z) + 0.2 × sector score (F8).
5. A stock is scored only if at least 70% of the weight is available; weights are re-normalized over the available groups. Otherwise it is not ranked, with reason `insufficient_data`.
6. Revenue inputs are refreshed after the 10th of each month. A stock whose latest revenue month is older than the market's latest month (a late filer) gets null revenue inputs. Quarterly figures are used only after their statutory deadline. Under that rule the latest revenue month always belongs to a quarter not yet reported, so v1 needs no T1 staleness rule.

### 4.4 Watch track (Emerging and new listings)

- **Members:** all Emerging stocks; full-funnel stocks with fewer than 120 trading days of history; listing applicants (`applylistingLocal`, `tpex_esb_applicant_companies`).
- **Metrics:** monthly revenue YoY (MOPS `rotc`, `t187ap05_R`); Emerging daily average price and volume; listing progress; first-five-day stabilization window. Financials are semi-annual for most Emerging stocks.
- **Output:** three tables:
  - upcoming listings;
  - recently listed stocks (age and history status);
  - Emerging stocks with `rev_yoy_med6 ≥ 20%` and 3 consecutive positive YoY months [J].
- **Graduation:** a stock enters the full funnel at the first weekly run after it reaches 120 trading days of history. This is a deferred entry, as MSCI defers IPOs to the next review (F2). Transfers keep their prior-board price history.

### 4.5 Market regime flag

- **Inputs:** the TAIEX close (`MI_INDEX` row `發行量加權股價指數`) versus its MA60, the MA60 slope, and the sign of the 12-month (250 trading days) return.
- **Flag:** `regime_transition` when, within the last 4 weeks, the TAIEX crossed its MA60 or its 12-month return changed sign.
- **Effect:** it annotates the shortlist with a caution and does not block it, because the evidence is mixed (T4 versus T5). 2026-11-20 was a −6.3% day for the Formosa index; only 16 stocks rose.

### 4.6 Data architecture and request budget

**First-run backfill:**

| Source | Coverage | Requests |
|---|---|---|
| Quotes (TWSE `MI_INDEX`, TPEx `dailyQuotes`) | 270 trading days: MA60 with slope, 6-1 momentum at each of the last 13 week-ends, and the TAIEX 12-month return over the last 4 weeks | ≈ 540 |
| Flows (T86, `MI_QFIIS`, TPEx institutional) | 30 trading days (W20) | ≈ 90 |
| Monthly revenue: 25 months × 5 files | 25 months | 125 |
| Quarterly income: 9 seasons × 3 boards | 8 standalone quarters | 27 |

At a 3-second throttle this takes roughly 40 minutes, once.

**Weekly run:**

| Source | Requests |
|---|---|
| 5 days × 5 daily tables | ≈ 25 |
| PER/PBR for `asof` (both boards) | 2 |
| ISIN lists | 3 |
| Status and snapshot tables | ≈ 15 |
| Monthly revenue (in the week after the 10th) | 5 |
| Quarterly income (after deadlines) | 3 |
| FinMind (shortlist, trading calendar, stock list) | ≤ 360 + 2 |

This stays well inside the Free tier.

**Storage [J]:**

- **Raw cache** (not committed): `~/.cache/tw-equity-screener/raw/{source}/{date}.json.gz`. Snapshot-only endpoints are archived as fetched, which makes them point in time; date-addressable ones can be rebuilt.
- **Committed weekly output:** `scripts/screens/{yyyy}-w{ww}/` (the weekly page is `reports/screens/tw-screen-{yyyy}-w{ww}.html`), containing:

  | File | Contents |
  |---|---|
  | `universe.csv` | Every master security with track, status, and reason |
  | `events.json` | Universe events |
  | `funnel.json` | Count per layer |
  | `scores.csv` | Every scored stock: factor z-scores, group scores, composite, rank, gate results |
  | `shortlist.json` | Shortlist with deep metrics and tier |
  | `watch.json` | Watch-track tables |
  | `diff.json` | Week-over-week changes |

- **Forward tracking:** `scripts/screens/forward.csv`.
- Every file carries `asof`, `week`, and `methodology_version`.

### 4.7 Week-over-week diff

- **Universe:** new listings, exits (transfer-checked), transfers, renames, reused codes, and status changes (處置, 注意, full-cash delivery, suspension).
- **Shortlist:** names that entered (with the gate they newly passed), names that exited (with the reason: rank > 40, trend gate failed, red flag, or delisted), rank deltas, streak (consecutive weeks on the list), and composite and group-score deltas.
- **Report link:** if `reports/equity/{code}-*.html` exists, show its latest rating and action. This builds a BUY conversion record.
- **Invariant (unit-tested):** the master count equals the sum of terminal statuses, and the week-over-week master delta equals new minus exits.

### 4.8 Validation loop

- **Forward tracking (W1):** treat the Tier A and actionable lists as equal-weight paper portfolios. Report 4, 13, 26, and 52-week price returns versus the TAIEX and the equal-weight L1 universe (both from the archive): hit rate, median excess return, and weekly turnover.
- **Primary metric:** the BUY conversion rate (Tier A → `tw-equity-report` 買進 with an active entry). This directly measures the target style.
- **Change control:** bump `methodology_version` on every rule change and log it with the reason, so no variant is left unrecorded (W2).
- **Adoption bar:** a new factor or threshold needs a point-in-time backtest t-statistic above 3 (W3). When several variants are compared, also check PBO.
- **Expected decay:** about half of a published premium (F12). Judge results against the base rate that most screens fail to beat their benchmark (F11), remembering that this rate comes from one decade led by US mega-caps.
- **First factor to review:** the persistence group (4.3), because it extrapolates T3. If its forward contribution is not positive after 26 weeks, propose removing it [J].

### 4.9 Integration with `tw-equity-report`

- **Shared code:** one bridge module adds `.agents/skills/tw-equity-report/scripts` to `sys.path`, exactly as the report's generators do. The screener imports `metrics.price_metrics` with `derive.trend_check` (trend filter), `metrics.revenue` with a new `metrics.yoy6_median` helper split out of `metrics.core_baseline`, and `fetch.build` for the shortlist deep metrics (bands, core baseline, cash conversion, cost zone).
- **Handoff:** each Tier A row carries the command `/tw-equity-report <code>` and the BUY proxy inputs, so the report's judgment review can compare the analyst Base case with the mechanical proxy.
- **Shared rule:** the 6-month median of revenue YoY and the trend filter stay defined in one place, `references/methodology.md`; the screener's methodology cites them rather than copying them.

### 4.10 Skill shape and weekly workflow

- **Location:** `.agents/skills/tw-equity-screener/`, containing `SKILL.md`, `references/methodology.md`, `references/data-sources.md`, `scripts/` (universe, market fetch, factors, screen, diff, render), and `scripts/tests/`. Add a Claude Code stub at `.claude/skills/tw-equity-screener/SKILL.md`.
- **Invocation:** `/tw-equity-screener [--asof YYYY-MM-DD] [--backfill] [--deep-research off|sector|finalists]`, user-invoked only, like `tw-equity-report`.

Weekly steps:

| Step | Action |
|---|---|
| 0 | Resolve `asof` (last trading day on or before today) and the ISO week. Recommended run day: Saturday, after Friday's flows are published. |
| 1 | Universe and events (L0) |
| 2 | Incremental fetch, with backfill on the first run |
| 3 | L1–L4 scripts, with tests |
| 4 | Shortlist deep metrics (FinMind) |
| 5 | One LLM review pass over the shortlist: universe events and 備註 notes, written to `review.json`. No web search. |
| 6 | Write the history and diff, and render the weekly page |
| 7 | Commit (and push if published) |
| 8 | Report back: funnel counts, events, entries and exits, Tier A, and suggested `/tw-equity-report` runs |

**Deep research is a switch, off by default** (decision D5). The user turns it on per run:

| Argument | Effect |
|---|---|
| `--deep-research off` (default) | No deep research. Finalists get it only when the user runs `tw-equity-report`, whose Step 4 runs it. |
| `--deep-research sector` | One deep-research run on the cycle of the top 3 sectors, saved as `sector_research.md` in the week folder. |
| `--deep-research finalists` | One deep-research run per Tier A name (at most 3), saved as `research_{code}.md` in the week folder. It uses `tw-equity-report`'s Step 4 query, so a report run in the same session can reuse it. |

---

## 5. Decisions

| # | Decision | Status (2026-11-23) |
|---|---|---|
| D1 | Publish the weekly screen to GitHub Pages | **Decided: publish.** One portal card, replaced weekly; each weekly page links to earlier weeks. |
| D2 | Liquidity floor (20-day median traded value) | Default NT$30M, tunable in `methodology.md`. |
| D3 | Financials (金融保險業) | **Decided: exclude in v1**, with status `excluded_financial`. A PBR/ROE sub-screen may come later. |
| D4 | Innovation Board (創新板) | Default: include, flagged `tib`. |
| D5 | Deep research | **Decided: a per-run switch, `--deep-research off\|sector\|finalists`, default `off`.** |
| D6 | Shortlist size and Tier A size | Default: actionable enters at rank ≤ 20, stays while ≤ 40, capped at 30; 10 left-side watch; Tier A is 3–5 in practice. |
| D7 | Research refresh | The user may re-run the full research at a lower effort before implementation. Plan Task 0 reconciles any new findings into this document first. |

## 6. Known Gaps

- IPO lock-up (閉鎖期) release schedules and honeymoon returns were not covered by verified sources. In v1 the watch track flags listing age only; read lock-up terms from the prospectus or MOPS.
- Full-market PER/PBR history is date-addressable (3.4), but v1 reads only the `asof` date. A full-market 5-year PER band would take about 2,500 requests, so the band stays a FinMind shortlist metric.
- No free full-market cash-flow or convertible-bond source was verified. Cash conversion is checked at the shortlist stage (FinMind), and convertible-bond dilution in `tw-equity-report` Step 4.
- The Taiwan revenue-surprise papers were read at abstract level: no formulas or effect sizes. The factor definitions and thresholds above are judgment.
- AQR, MSCI, Novy-Marx & Velikov, and Harvey et al. are mostly US or developed-market evidence.
- The cash-offering flag sees only rights offerings with an upcoming ex-rights date. Offerings without existing-shareholder subscription, and those already past their ex-date, are not flagged; `tw-equity-report` Step 4 still checks dilution.
- TPEx index history is available (3.4) but unused in v1. Benchmarks use the TAIEX and the equal-weight universe; a TPEx-only benchmark for OTC stocks can come later.
- v1 uses quarterly figures only after their statutory deadline, so it ignores early filers whose report has already moved the price.

## 7. Revision Log

- **2026-11-23, planning pass** (live checks of field layouts, before any implementation):
  - Dropped the `TWT48U_ALL` cash-offering flag from L2; it is the TWSE-only ex-rights schedule.
  - Dropped the company masters (`t187ap03_*`) from L0 reconciliation; ISIN, the quote tables, and `MI_QFIIS` already carry listing dates and shares.
  - Raised the quote backfill from 220 to 270 trading days for the TAIEX 12-month return, and moved the regime flag and benchmarks to the TAIEX plus the equal-weight universe.
  - Made the L5 hysteresis exact (enter ≤ 20, stay ≤ 40, cap 30) and raised the FinMind budget to ≤ 360 requests.
  - Replaced the `rev_surge` zeroing rule with a late-filer rule (see 4.3, rule 6).
  - Named the shared functions (`derive.trend_check`, new `metrics.yoy6_median`, `fetch.build`).
  - Recorded decisions D1, D3, D5, and D7.
- **2026-11-23, research refresh** (plan Task 0; run `wf_e58b5eef-8dd` and live checks):
  - Retagged section 3 from the completed verification and added the [V2] tag. F7's "decent on both styles" sub-claim was refuted 1-2 and removed from the executive summary; the peer-reviewed counter-evidence on integrated scoring is now cited.
  - Kept the L4 hard floor and the 10% persistence weight, both now tagged [J]. Validation reviews the persistence group first.
  - Switched PER/PBR from the OpenAPI snapshots to the date-addressable `BWIBBU_d` and TPEx `pera_result.php`, so every input is keyed by date.
  - Restored a cash-offering flag in L2, now for both boards (`TWT48U_ALL` and `tpex_exright_prepost`). It flags only and is not a red flag for Tier A.
  - Rewrote the Known Gaps on PER/margin history, TPEx cash offerings, and TPEx index history, which live checks closed.

## 8. Sources

- MSCI Quality Indexes Methodology (2025-05): https://www.msci.com/indexes/documents/methodology/2_MSCI_Quality_Indexes_Methodology_20250520.pdf
- MSCI Momentum Indexes Methodology (2025-07): https://www.msci.com/indexes/documents/methodology/2_MSCI_Momentum_Indexes_Methodology_20250725.pdf
- MSCI Diversified Multiple-Factor Indexes Methodology (2022-05): https://www.msci.com/eqb/methodology/meth_docs/2_MSCI_Diversified_Multi-Factor_Indexes_Methodology_20220524.pdf
- AQR, "Long-Only Style Investing: Don't Just Mix, Integrate" (2017): https://www.aqr.com/Insights/Research/White-Papers/Long-Only-Style-Investing
- Leippold & Rüegg, "The Mixed vs the Integrated Approach to Style Investing: Much Ado About Nothing?" (EFM 24(5), 2018): https://ideas.repec.org/a/bla/eufman/v24y2018i5p829-855.html
- AAII, 2025 review of AAII stock screens (2026-01): https://www.aaii.com/journal/article/398718-2025-review-of-aaii-stock-screens-wangers-zebras-break-from-the-herd
- CFA Institute Digest, "Does Academic Research Destroy Stock Return Predictability?" (2016): https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary
- Novy-Marx & Velikov, "A Taxonomy of Anomalies and their Trading Costs" (NBER w20721; RFS 2016): https://www.nber.org/papers/w20721
- Harvey, Liu & Zhu, "...and the Cross-Section of Expected Returns" (NBER w20592; RFS 2016): https://www.nber.org/papers/w20592
- Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (J. Computational Finance 2017): https://escholarship.org/uc/item/4w1110bb
- "Text-Based Industry Momentum" (JFQA 2018): https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/textbased-industry-momentum/6E04891A7AD30C24C21CBDE37EC06BF4
- "The information value of interim accounting disclosures: evidence from mandatory monthly revenue reports" (RQFA 58(1), 2022): https://ideas.repec.org/a/kap/rqfnac/v58y2022i1d10.1007_s11156-021-00994-1.html
- "Unexpected Monthly Revenue in the Taiwan Stock Market: A Comprehensive Analysis" (2022): https://www.airitilibrary.com/Article/Detail/P20171012001-202212-202212200009-202212200009-503-545
- Lin, Ko, Feng & Yang, "Market dynamics and momentum in the Taiwan stock market" (PBFJ 38, 2016): https://econpapers.repec.org/RePEc:eee:pacfin:v:38:y:2016:i:c:p:59-75
- "Revisiting the momentum effect in Taiwan: The role of persistency" (PBFJ 78, 2023): https://ideas.repec.org/a/eee/pacfin/v78y2023ics0927538x23000094.html
- Chen, Chou & Hsieh, "Persistency of the momentum effect" (EFM 24(5), 2018): https://econpapers.repec.org/RePEc:bla:eufman:v:24:y:2018:i:5:p:856-892
- "The Role of Industry Effect and Market States in Taiwanese Momentum" (IJFR 7(2), 2016): https://ideas.repec.org/a/jfr/ijfr11/v7y2016i2p183-188.html
- TWSE OpenAPI: https://openapi.twse.com.tw/ · TPEx OpenAPI: https://www.tpex.org.tw/openapi/
- ISIN lists: https://isin.twse.com.tw/isin/C_public.jsp?strMode=2 (also 4, 5)
- MOPS monthly revenue: https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_115_10_0.html (pattern) · MOPS quarterly income: https://mopsov.twse.com.tw/mops/web/ajax_t163sb04
- TPEx/TWSE industry value-chain platform: https://ic.tpex.org.tw/
