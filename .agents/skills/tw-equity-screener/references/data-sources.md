# Data Sources

Every endpoint the screen reads, and how it reads each one. `scripts/cache.py` fetches the exchange, OpenAPI, ISIN, and MOPS sources; FinMind goes through `tw-equity-report/scripts/finmind_client.py`. Field names are the sources' own labels.

## 0. Fetch rules

- Requests to `twse.com.tw`, `tpex.org.tw`, `mopsov.twse.com.tw`, and `isin.twse.com.tw` are spaced at least 3 s apart, sent with User-Agent `Mozilla/5.0 (compatible; tw-equity-screener)`, and time out after 60 s. A network error or HTTP 5xx is retried 3 times, after 10, 30, and 90 s.
- The raw cache is `raw/{source}/{key}.gz` under `TW_SCREENER_CACHE`, or under `~/.cache/tw-equity-screener` when that is unset. It is never committed.
- A response is cached only after it validates. A holiday, an unpublished date, or a block page fails validation, raises `NoDataError` (exit 3), and is never cached.
- A cached response is served without a request, except for the MOPS rows marked as refreshed.
- The ISIN and OpenAPI sources answer only the current state. They are cached under the run's `asof`, and only a live run fetches them; a past `asof` without them exits 4.

## 1. Exchange daily tables (by date)

All are GET requests answering UTF-8 JSON. In the URLs, `{ymd}` is `YYYYMMDD`, `{y}/{m}/{d}` is the Gregorian date, and `{roc}` is the ROC year (Gregorian − 1911).

| Source (cache key) | URL | Validation | Fields used |
|---|---|---|---|
| TWSE quotes (`twse_quotes/{date}`) | `https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json` | `stat` is `OK`, and `data` or a table has rows | Table `每日收盤行情`: 證券代號, 開盤價, 最高價, 最低價, 收盤價, 成交股數, 成交金額. The first table's 發行量加權股價指數 row: 收盤指數 (the TAIEX) |
| TPEx quotes (`tpex_quotes/{date}`) | `https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={y}/{m}/{d}&id=&response=json` | `stat` is `ok` in any case, and the first table has rows | Tables `上櫃股票行情` and `管理股票`: 代號, 開盤, 最高, 最低, 收盤, 成交股數, 成交金額(元), 發行股數 |
| TWSE institutional (`twse_t86/{date}`) | `https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json` | As TWSE quotes | 證券代號. Foreign = 外陸資買賣超股數(不含外資自營商) + 外資自營商買賣超股數; trust = 投信買賣超股數; dealer = 自營商買賣超股數 |
| TPEx institutional (`tpex_insti/{date}`) | `https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={y}/{m}/{d}&response=json` | As TPEx quotes | By position in the first table, since its field names repeat: cell 0 code, 10 foreign (dealers included), 13 trust, 22 dealer total, 23 three-institution total. A row whose cell 23 is not cells 10 + 13 + 22 stops the run as a layout change |
| TWSE foreign holding (`twse_qfiis/{date}`) | `https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={ymd}&selectType=ALLBUT0999&response=json` | As TWSE quotes | 證券代號, 發行股數, 全體外資及陸資持股比率 |
| TWSE valuation (`twse_per/{date}`) | `https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ymd}&selectType=ALL&response=json` | As TWSE quotes, and `date` equals `{ymd}` | 證券代號, 本益比, 股價淨值比, 殖利率(%) |
| TPEx valuation (`tpex_per/{date}`) | `https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json&d={roc}/{m}/{d}` | As TPEx quotes, and `date` equals `{ymd}` | The first table: 股票代號, 本益比, 股價淨值比, 殖利率(%) |

Quotes are fetched for the last 270 trading dates, the institutional and holding tables for the last 30, and valuation for `asof` only. A cell is a number once commas and spaces are stripped; `--`, `N/A`, and other text read as null.

## 2. OpenAPI snapshots (current state only)

GET requests answering UTF-8 JSON; a response validates when it is a JSON list. The cache key is `{name}/{asof}`. TWSE paths are under `https://openapi.twse.com.tw/v1/` and TPEx paths under `https://www.tpex.org.tw/openapi/v1/`.

| Name | Path | Fields used | Use |
|---|---|---|---|
| `TWT85U` | `exchangeReport/TWT85U` | Code | `altered_trading` |
| `TWTAWU` | `exchangeReport/TWTAWU` | Code, TradingHaltDate, TradingResumptionDate | `suspended` |
| `punish` | `announcement/punish` | Code, DispositionPeriod | `disposition` |
| `notice` | `announcement/notice` | Code | `attention` |
| `TWT48U_ALL` | `exchangeReport/TWT48U_ALL` | Code, Date, SubscriptionRatio | `cash_offering` |
| `applylistingLocal` | `company/applylistingLocal` | By position: 1 code, 2 name, 3 application date, 9 listing date, 11 price | Upcoming listings |
| `TWT88U` | `exchangeReport/TWT88U` | SecurCode, 1stTradingDate, 5thTradingDate, PriceUnderwritten | First five trading days |
| `suspendListing` | `company/suspendListingCsvAndHtml` | Code, DelistingDate | Delisting dates |
| `cmode` | `tpex_cmode` | SecuritiesCompanyCode, AlteredTrading, ManagedStock, SuspensionOfTrading, PeriodicTrading, MatchingFrequency | `altered_trading`, `managed`, `suspended`, `periodic_auction` |
| `disposal` | `tpex_disposal_information` | SecuritiesCompanyCode, DispositionPeriod | `disposition` |
| `warning` | `tpex_trading_warning_information` | SecuritiesCompanyCode | `attention` |
| `exright` | `tpex_exright_prepost` | SecuritiesCompanyCode, ExRrightsExDividendDate, SubscriptionRatioToNewSharesIssued | `cash_offering` |
| `applicants` | `tpex_esb_applicant_companies` | SecuritiesCompanyCode, CompanyName, Date, ListingDate, OfferingPrice | Upcoming listings |
| `ipo_no_limit` | `tpex_ipo_no_limit` | SecuritiesCompanyCode, StartDateForStabilizationOperation, EndDateForStabilizationOperation, UnderwritingPrice | First five trading days |
| `esb_quotes` | `tpex_esb_latest_statistics` | SecuritiesCompanyCode, Average, LatestPrice, TransactionVolume, ApplyingStatus | Emerging quotes |

Dates arrive as ROC (`1151120`, `115/11/20`) or Gregorian (`20261029`), and periods as `start～end` or `start~end`. A date that cannot be read leaves the status in force.

## 3. ISIN security master (current state only)

| Source (cache key) | URL | Encoding | Validation | Fields used |
|---|---|---|---|---|
| ISIN list (`isin{mode}/{asof}`) | `https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}`, with mode 2 for TWSE, 4 for TPEx, and 5 for Emerging | cp950 | The page has a `<table` | Cells: 0 有價證券代號及名稱 (the code, then the name after the first space), 1 ISIN, 2 上市日, 3 市場別, 4 產業別, 5 CFICode. A row counts when its ISIN matches `^[A-Z]{2}[A-Z0-9]{9}[0-9]$` and its CFICode starts with `ES` |

市場別 sets the market and board: 上市 is TWSE main, 上市臺灣創新板 is TWSE `tib`, 上櫃 is TPEx, and 興櫃 is Emerging. Any other value stops the run.

## 4. MOPS revenue and income (by month and season)

| Source (cache key) | Request | Encoding | Validation | Fields used | Refreshed |
|---|---|---|---|---|---|
| Monthly revenue (`rev_{board}_{kind}/{YYYY-MM}`) | GET `https://mopsov.twse.com.tw/nas/t21/{board}/t21sc03_{roc}_{month}_{kind}.html`: board `sii`, `otc`, or `rotc`; kind 0 or 1; the month not zero-padded | cp950 | 公司代號 appears once tags are stripped | Rows of 11 cells whose code matches `^[0-9A-Z]{4,6}$`: 0 code, 1 name (a trailing `*` stripped), 2 the month's revenue, 4 the same month a year earlier, 6 YoY %, 10 備註. The industry comes from the `產業別：` rows | Until the 25th of the next month |
| Quarterly income (`inc_{board}/{YYYY}-Q{s}`) | POST `https://mopsov.twse.com.tw/mops/web/ajax_t163sb04` with `encodeURIComponent=1`, `step=1`, `firstin=1`, `off=1`, `isQuery=Y`, `TYPEK={board}`, `year={roc}`, `season=01` to `04`: board `sii` or `otc` | UTF-8 | As revenue | Tables with a 公司代號 header. The general template, which has 營業收入 and 營業利益（損失）: 營業收入, 營業利益（損失）, 稅前淨利（淨損）, 本期淨利（淨損）, 淨利（淨損）歸屬於母公司業主, 基本每股盈餘（元）. Codes on any other template are kept by code only | Until 30 days after the season's deadline |

Revenue is in thousand NT$. Income is year to date, so standalone quarters are differenced. An income row whose cell count differs from its header stops the run.

## 5. FinMind (through `tw-equity-report`)

| Dataset | Request | Use | Cache |
|---|---|---|---|
| `TaiwanStockTradingDate` | `data_id` empty, from 450 days before the earlier of today and `asof` | The trading calendar | None |
| `TaiwanStockInfo` | `data_id` empty | Reconciliation against the ISIN master | None |
| The 9 Free datasets of `fetch.build` | One build per shortlisted stock, at most 40 | Deep metrics (methodology.md section 6) | `finmind/{asof}/{code}.json` under the raw cache root |

The token comes from `FINMIND_TOKEN` when it is set. A quota error exits 2; deep metrics already cached are kept, so a rerun resumes.

## 6. Quirks

| Quirk | Handling |
|---|---|
| **KY ISINs**: foreign issuers, such as Cayman companies, have non-`TW` ISINs (`KYG…`), and 3673 TPK-KY is `ESVTFR`. | Match the ISIN pattern and a CFICode starting with `ES`; never require a `TW` prefix or exactly `ESVUFR`. |
| **創新板 section**: the Taiwan Innovation Board stocks (31 on 2026-11-23) sit in their own section of `strMode=2`, with 市場別 上市臺灣創新板. Reading only the 股票 section, or only 上市, drops them. | Kept as TWSE board `tib` and flagged `tib`. |
| **MOPS `_0`/`_1` split**: TWSE and TPEx revenue comes in separate files for domestic (`_0`) and foreign (`_1`) issuers; Emerging has `_0` only. | Fetch all five files every month. |
| **T86 omissions**: T86 and the TPEx institutional table list only the stocks that institutions traded that day. | A missing row is zero flow, never a dropped stock. |
| **Full-width `Ｙ`**: `tpex_cmode` marks a mode with the full-width `Ｙ`, not `Y`. | Any non-blank value sets the tag. |
| **`notice` placeholder row**: on a day without notices, `announcement/notice` returns one row with a blank Code. | Blank codes are skipped. |
| **`TaiwanStockTradingDate` lists future dates**: it is the exchange calendar, not a record of trading. | `asof` resolves among the dates on or before today, stepping back at most 3 dates to the latest one with TWSE quotes. |
| **TPEx 管理股票 table**: managed stocks trade in their own table of the TPEx quotes, not in 上櫃股票行情. | Read both tables for quotes, and tag the second table's codes `managed`. |
| **`applylistingLocal` keys**: the keys are shifted by one column. | Read its rows by position. |
| **TPEx valuation columns**: the table gained a column (財報年/季) between 2024 and 2026, and its names carry trailing spaces. | Read fields by name and strip values. |
| **Valuation dates**: the valuation endpoints can answer with another day's table. | Require the response `date` to equal `asof`. |
| **MOPS code header**: MOPS prints the header as `公司<br>代號`. | Strip tags before matching it. |
| **MOPS restatements**: MOPS regenerates historical revenue files and may restate their comparison figures. | The cache keeps the copy fetched at the time; a month is refreshed only until the 25th of the next month. |
| **Reused codes and transfers**: codes are reused after a delisting, and a board transfer resets 上市日. | Securities are keyed `{code}@{listing_date}`. A code that changed market is one transfer event, and its price history counts across boards. |
| **No quote row**: a suspended or untraded stock has no row that day. | Its close is null (`excluded_no_quote` on `asof`), and its traded value counts as 0 in `adv20`. |
