# Methodology

Fixed definitions for every metric in the report. `scripts/metrics.py` (run by `scripts/fetch.py`) implements sections 1 to 5; `scripts/derive.py` implements sections 6 and 7 from the data and analysis files. Change a definition here and in the script together, with a unit test in `scripts/tests/`. Round prices to the stock's tick size, ratios to 2 decimals, and percentages to 1 decimal.

## 0. Common rules

- **Window (W20)**: the last 20 trading days up to and including `asof`. "近 1 個月" in the report means W20.
- **Lots**: 1 lot = 1,000 shares. `TaiwanStockPrice.Trading_Volume` and institutional `buy`/`sell` are in shares; convert to lots.
- **Daily average price**: `Trading_money / Trading_Volume`.
- **Point-in-time**: a quarterly statement is usable only after its statutory deadline (Q1 May 15, Q2 Aug 14, Q3 Nov 14, Q4 Mar 31 of the next year) unless the dataset already contains it. `TaiwanStockMonthRevenue` rows dated `YYYY-MM-01` hold the previous month's revenue.
- **Market**: take the latest-dated `TaiwanStockInfo` row as the current market. Apply the `finmind` skill's emerging-market rules when market is `emerging`.

## 1. Datasets

| Group | Dataset | Range |
|---|---|---|
| Price | `TaiwanStockPrice` | 120 trading days before `asof` |
| Institutional | `TaiwanStockInstitutionalInvestorsBuySell` | W20 |
| Foreign holding | `TaiwanStockShareholding` | W20 |
| Margin | `TaiwanStockMarginPurchaseShortSale` | W20 |
| Revenue | `TaiwanStockMonthRevenue` | 24 months |
| Financials | `TaiwanStockFinancialStatements`, `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement` | 8 quarters |
| Valuation | `TaiwanStockPER` | 5 years for the target; latest row for each peer |

Statement `type` names differ between industries; inspect the returned `type` values and record the ones used in `sources`.

## 2. Price and moving averages (W20)

- Close series, W20 high (max of `max`) and low (min of `min`) with dates.
- MA5, MA10, MA20: simple averages of `close`. Bias = `(close − MA20) / MA20`.
- **Squeeze (糾結)**: `(max(MA5, MA10, MA20) − min(...)) / close < 2%`.
- **Alignment**: bullish when MA5 > MA10 > MA20, bearish when MA5 < MA10 < MA20, otherwise mixed.
- **Volume**: `vol_avg20` = mean W20 volume in lots. Spike day: volume > 1.5 × `vol_avg20`. Dry-up day: volume < 0.6 × `vol_avg20`.
- **Float settling (浮額沉澱)**: signal is on when the W20 margin balance change is negative **and** W20 has at least 5 dry-up days. Report both inputs.

## 3. Institutional and margin (W20)

- Foreign = `Foreign_Investor` + `Foreign_Dealer_Self`. Investment trust = `Investment_Trust`. Dealers = `Dealer_self` + `Dealer_Hedging`. Net = `buy − sell`, in lots, daily and cumulative.
- Foreign holding ratio (`ForeignInvestmentSharesRatio`): first, last, high, low, and change in percentage points.
- Margin balance (`MarginPurchaseTodayBalance`) and short balance (`ShortSaleTodayBalance`): first, last, change, change %.
- **Short-to-margin ratio (券資比)** = short balance / margin balance. Levels: < 5% low, 5–20% medium, > 20% high (short-squeeze potential).
- **Institutional cost zone**: volume-weighted daily average price over the foreign net-buy days in W20, weighted by foreign net-buy lots; zone = that price ± 2%. If foreign has fewer than 3 net-buy days, use investment trust instead. If neither qualifies, record the zone as null and add a `gaps` entry.

## 4. Operations and financials

- **Revenue**: year-to-date sum through the latest reported month and its YoY against the same months of the prior year; the last 12 months' revenue with MoM and YoY each.
- **Last 4 quarters**: EPS, gross margin (gross profit / revenue), operating margin (operating income / revenue), TTM EPS (sum of the 4).
- **Days inventory (DSI)** = average of opening and closing inventory / quarterly cost of goods sold × 91.
- **Cash conversion** = TTM operating cash flow / TTM net income.
- **Earnings-quality focus by industry**: tech and electronics, inventory cycle and capex; construction, IFRS 15 recognition at delivery and contract liabilities; financials, book value and credit costs. Other industries: state the focus chosen and why.

## 5. Valuation bands and peers

- **Bands**: from 5 years of daily `PER` and `PBR` (drop PER ≤ 0), compute P10, P25, P50, P75, P90 by linear interpolation.
- **Current percentile** = share of days in the 5-year series with a value ≤ the current value.
- **Peer matrix**: latest `PER`, `PBR`, `dividend_yield` for the target and 3 peers, plus the peer median of each.

## 6. Scenarios, target price, and rating (generator)

- Horizon: 12 months.
- Target = forward EPS × PER multiple. Use BVPS × PBR multiple instead when TTM EPS ≤ 0 or the industry is financial or asset-heavy; state which.
- **Multiple anchoring**: Bear ≤ P25, Base between P25 and P75 (normally near P50), Bull ≤ P90. A multiple outside these bounds needs an explicit `basis`.
- Probabilities are whole percentages summing to 100. Probability-weighted target = Σ(probability × target).
- Upside = target / close − 1.
- **Rating** from Base upside: > +15% 買進 (BUY); −5% to +15% 中立 (NEUTRAL); < −5% 賣出 (SELL).

## 7. Trade setup (generator)

- **Pullback entry zone**: the overlap of [min(MA10, MA20), max(MA10, MA20)] and the institutional cost zone. If they do not overlap or the cost zone is null, use the MA10–MA20 band. Entry price = zone midpoint.
- **Breakout trigger**: the highest high of the last 60 trading days, valid only with volume > 1.5 × `vol_avg20`.
- **T1 (technical)**: the 60-day highest high when it is at least 3% above the entry price; otherwise entry price + 0.618 × (60-day high − 60-day low).
- **T2 (fundamental)**: the Base target.
- **Hard stop**: from the two candidates, the low of the highest-volume day in W20 and MA20 × 0.97, take the one closest to the entry price that is still below the zone's lower bound. If neither is below it, use the lower bound × 0.95.
- **Breakout stop**: breakout trigger × 0.95.
- **R:R (pullback)** = (T2 − entry price) / (entry price − hard stop). **R:R (breakout)** = (T2 − trigger) / (trigger − breakout stop). Mark R:R < 1.5 as 不具交易吸引力.
- **Thesis breakers**: 2–3 measurable conditions, each with a threshold and the dataset that would show it (e.g. monthly revenue YoY negative for 2 consecutive months).
