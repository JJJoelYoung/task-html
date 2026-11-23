# Taiwan Equity Screener Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `.agents/skills/tw-equity-screener/`, a user-invoked weekly skill that runs every TWSE and TPEx common stock through the L0–L6 funnel, keeps a week-by-week history with diffs, publishes one weekly page, and hands its Tier A names to `tw-equity-report`.

**Architecture:** Standard-library Python scripts fetch free full-market tables into a raw cache outside the repo: the ISIN master, TWSE/TPEx daily tables and OpenAPI snapshots, and MOPS revenue and income. They compute factors with definitions shared from `tw-equity-report/scripts` through one bridge module, and each run writes a committed week folder, `scripts/screens/{yyyy}-w{ww}/`. FinMind is called only for the trading calendar, the stock list, and the shortlist (`fetch.build`). A renderer turns the week folder into `reports/screens/tw-screen-{yyyy}-w{ww}.html`, one portal card, and one README row. `check_screen.py` validates all of them.

**Tech Stack:** Python 3.12 standard library (`urllib`, `json`, `csv`, `gzip`, `re`, `statistics`, `unittest`); FinMind v4 Free tier through `tw-equity-report/scripts/finmind_client.py`; Markdown skill files.

**Spec:** [docs/research/2026-11-23-tw-equity-screener-research.md](../../research/2026-11-23-tw-equity-screener-research.md), section 4 (design) and section 5 (decisions). Section 3 holds the evidence, and section 7 logs the design changes. Every exact value in this plan comes from that document or from the live field checks recorded in it.

## Global Constraints

- Python standard library only; no new packages.
- Pass `encoding="utf-8"` to every text-file read and write and to every text-mode `subprocess.run`. Decode ISIN pages and MOPS revenue pages as `cp950`, and MOPS `ajax_t163sb04` responses as UTF-8.
- Free data only: FinMind Free datasets (`TaiwanStockTradingDate`, `TaiwanStockInfo`, and the 9 datasets `fetch.build` uses). No Backer or Sponsor datasets.
- Requests to `twse.com.tw`, `tpex.org.tw`, `mopsov.twse.com.tw`, and `isin.twse.com.tw`: at least 3 s apart. On a network error or HTTP 5xx, retry 3 times after 10, 30, and 90 s. Send User-Agent `Mozilla/5.0 (compatible; tw-equity-screener)`.
- Raw cache: `Path.home() / ".cache" / "tw-equity-screener"`, or the `TW_SCREENER_CACHE` environment variable when set. Never commit it, and never write an absolute path into a committed file.
- One definition per metric, imported only through `scripts/shared.py`:
  - the trend filter is `derive.trend_check(metrics.price_metrics(rows)[1])`;
  - the 6-month median revenue YoY is `metrics.yoy6_median(metrics.revenue(rows, gaps))`;
  - shortlist deep metrics come from `fetch.build(code, [], asof)`.
- Every master security ends each week in exactly one terminal status (Task 8 `STATUSES`). A missing input is null, never zero. The one exception: a stock absent from T86 or the TPEx institutional table had zero institutional flow that day (research U5).
- Point in time: a quarterly season is used only on or after its deadline. For general industry the deadlines are Q1 May 15, Q2 Aug 14, Q3 Nov 14, and Q4 Mar 31 of the next year. Snapshot tables for a past `asof` come only from the archive.
- Securities are keyed `{code}@{listing_date}` (`Security.key`). Per-stock data inside a week is keyed by `code`, which is unique at any one time.
- Language: the page, card, and README row are Traditional Chinese. Code, comments, JSON keys, CSV headers, docs, and commit messages are English (`english-doc-guard`).
- Public output never holds the user's positions, cost basis, or capital. The page footer carries `本頁僅供研究參考，不構成任何投資建議。`.
- Taiwan colours: up is red and down is green, through `--tw-up`, `--tw-down`, `--tw-flat`, and `data-dir="up|down|flat"`, by the rules in `tw-equity-report/references/report-contract.md` section 2.
- `methodology_version` starts at `1.0`. Every rule change bumps it and adds a changelog line to `references/methodology.md`.
- From the repo root, `python -m unittest discover -s .agents/skills/tw-equity-screener/scripts/tests` runs offline. `python -m unittest discover -s .agents/skills/tw-equity-report/scripts/tests` keeps passing.
- `run.py` exit codes:

  | Code | Meaning |
  |---|---|
  | 1 | Invariant failure |
  | 2 | FinMind quota exhausted |
  | 3 | A table for `asof` is not published yet |
  | 4 | A snapshot for a past `asof` is missing from the archive |
  | 5 | The backfill guard stopped the run |

- Commit through the `conventional-commit` skill, and create the skill files with `portable-skill-creator`.

## Review Focus

1. **Board transfers.** A stock that moved between boards, such as TPEx to TWSE with a new listing date, keeps its full price history and appears as one `transfer` event, not as an exit plus a new listing. Tests: Task 3 `test_transfer_is_one_event`; Task 7 `test_history_days_spans_board_transfer`.
2. **Unpublished dates.** A holiday, or a run before the exchange publishes `asof`, must not poison the cache. A "no data" answer raises and is never cached, and the resolver steps back to the last published trading day. Tests: Task 2 `test_no_data_not_cached`; Task 4 `test_resolve_asof_steps_back_when_unpublished`.
3. **Thin industries.** An industry with fewer than 5 eligible stocks must not produce extreme z-scores or be gated as unfavoured; TPEx 電器電纜 has 1 stock. Tests: Task 8 `test_small_industry_uses_market_z` and `test_small_industry_never_unfavoured`.
4. **Same-week re-runs.** Re-running the same week overwrites its folder without duplicating the portal card, the README row, or forward-tracking rows. Tests: Task 11 `test_forward_rows_idempotent`; Task 12 `test_card_replaced_not_duplicated`.
5. **Partial data.** A late monthly-revenue filer, or a non-financial company on a non-general income template (1409 新纖), is never dropped silently. It gets null inputs, and `insufficient_data` only when less than 70% of the weight remains. Tests: Task 7 `test_late_filer_revenue_inputs_null`; Task 8 `test_non_general_template_not_financial_is_insufficient`.

---

## File Structure

Paths are under `.agents/skills/tw-equity-screener/` unless the table marks them as repo-root paths.

| Path | Responsibility |
|---|---|
| `SKILL.md` | Weekly workflow, arguments, deep-research switch |
| `agents/openai.yaml` | `policy: allow_implicit_invocation: false` |
| `references/methodology.md` | Rules, parameters, `methodology_version`, changelog |
| `references/data-sources.md` | Endpoint contracts: URL, encoding, validation, fields, quirks |
| `references/page-contract.md` | Weekly page, card, README row, and what `check_screen.py` checks |
| `scripts/shared.py` | The only import bridge to `tw-equity-report/scripts` |
| `scripts/cache.py` | Throttled fetch, retries, gzip raw cache |
| `scripts/universe.py` | ISIN master, universe events, reconciliation |
| `scripts/exchange.py` | Date-addressable TWSE/TPEx tables (quotes, flows, holdings, valuation), `asof` resolution |
| `scripts/snapshots.py` | OpenAPI snapshots: status lists, cash-offering flags, listing pipeline |
| `scripts/mops.py` | Monthly revenue and quarterly income |
| `scripts/factors.py` | Panel helpers and per-stock raw variables |
| `scripts/score.py` | Track split, L1–L4 statuses, standardization, composite, sector gate |
| `scripts/shortlist.py` | L5 hysteresis, FinMind deep metrics, BUY proxy, L6 tiers |
| `scripts/watch.py` | Watch-track tables and the market regime flag |
| `scripts/history.py` | Week folder I/O, diff, invariants, forward tracking, BUY conversion |
| `scripts/render.py` | Weekly page, portal card, README row |
| `scripts/check_screen.py` | Contract checks; exit 1 on any failure |
| `scripts/run.py` | Orchestrates steps 0–6 |
| `scripts/tests/` | `test_<module>.py`, `helpers.py`, `make_fixtures.py`, `fixtures/` |
| `.claude/skills/tw-equity-screener/SKILL.md` (repo root) | Generated Claude Code stub |
| `scripts/screens/{yyyy}-w{ww}/` (repo root) | Committed week folder |
| `scripts/screens/forward.csv` (repo root) | Forward-tracking record |
| `reports/screens/tw-screen-{yyyy}-w{ww}.html` (repo root) | Published weekly page |

Also modified:

- `.agents/skills/tw-equity-report/scripts/metrics.py` and its `tests/test_metrics.py` (Task 1).
- `index.html` and `README.md` (every run).

All test commands run from the repo root. `SCREENER_TESTS` below stands for `python -m unittest discover -s .agents/skills/tw-equity-screener/scripts/tests`.

---

### Task 0: Reconcile a research refresh and commit the docs

**Files:**
- Modify: `docs/research/2026-11-23-tw-equity-screener-research.md`
- Modify: this plan

- [ ] **Step 1:** Ask the user whether a refreshed research report exists and where it is. If there is none, go to Step 4.
- [ ] **Step 2:** List every finding in the new report that is new, contradicts section 3, or changes one of its numbers. Record evidence-only changes in section 3. For each change that alters a rule or parameter in section 4, do three things:
  - edit sections 4–5;
  - add a line to the section 7 Revision Log;
  - update the affected task's test values in this plan.
- [ ] **Step 3:** Show the user the diff of sections 4–5, and wait for approval before Task 1.
- [ ] **Step 4:** Commit the research note and this plan: `docs(research): add tw equity screener research and plan`.

### Task 1: Shared-definition bridge

**Files:**
- Modify: `.agents/skills/tw-equity-report/scripts/metrics.py` (`core_baseline`, where `yoys6` and `med_yoy` are built)
- Test: `.agents/skills/tw-equity-report/scripts/tests/test_metrics.py`
- Create: `scripts/shared.py`, `scripts/tests/helpers.py`, `scripts/tests/test_shared.py`, `agents/openai.yaml`

**Interfaces:**
- Produces `metrics.yoy6_median(rev: dict) -> float | None`: `percentile(sorted(<non-null yoy_pct in rev["last12"][-6:]>), 50)`, or `None` when there are none. `core_baseline` calls it, and its output does not change.
- `shared.py` inserts `Path(__file__).resolve().parents[2] / "tw-equity-report" / "scripts"` at the front of `sys.path`, then exposes:
  - `mt`: the `metrics` module.
  - `derive`: the `derive` module.
  - `fetch_build`: `fetch.build`.
  - `finmind_fetch`: `finmind_client.fetch`.
  - `QuotaError`, `NotPublishedError`.
  - `trend_gate(price_rows: list[dict]) -> tuple[dict, dict]`, which returns `(m, derive.trend_check(m))` with `m = mt.price_metrics(price_rows)[1]`.
- Produces `tests/helpers.py` with `price_rows(closes, volumes=None, start=date(2026, 1, 5))`, the same row shape as `tw-equity-report`'s `test_metrics.py` helper. Later tasks add their helpers here.

- [ ] **Step 1: Write the failing tests**

```python
# tw-equity-report/scripts/tests/test_metrics.py
def test_yoy6_median_last_six(self):
    rev = {"last12": [{"yoy_pct": v} for v in [5, 1, 2, 3, 4, 9, 10, 20, None, 40, 50, 60]]}
    self.assertEqual(mt.yoy6_median(rev), 40.0)          # last six: 10, 20, None, 40, 50, 60

def test_yoy6_median_none(self):
    self.assertIsNone(mt.yoy6_median({"last12": [{"yoy_pct": None}] * 6}))

# tw-equity-screener/scripts/tests/test_shared.py
def test_trend_gate_rising_passes(self):
    m, t = shared.trend_gate(price_rows([100 + i for i in range(80)]))
    self.assertTrue(t["checked"] and t["ok"])

def test_trend_gate_falling_fails(self):
    m, t = shared.trend_gate(price_rows([200 - i for i in range(80)]))
    self.assertFalse(t["ok"])
```

- [ ] **Step 2:** Run both suites. Expect `AttributeError: ... 'yoy6_median'` and `ModuleNotFoundError: No module named 'shared'`.
- [ ] **Step 3:** Implement `yoy6_median` and call it from `core_baseline`. Write `shared.py`, `helpers.py`, and `agents/openai.yaml`.
- [ ] **Step 4:** Run both suites. Expect PASS, including the existing `core_baseline` tests.
- [ ] **Step 5:** Commit: `feat(screener): add shared-definition bridge`.

### Task 2: Throttled fetcher and raw cache (`cache.py`)

**Files:** Create `scripts/cache.py`, `scripts/tests/test_cache.py`.

**Interfaces:**
- `cache_root() -> Path`.
- `class NoDataError(RuntimeError)`: the source answered without the expected table, because of a holiday, a date not yet published, or a block page.
- `class Fetcher(root: Path | None = None, pause_s: float = 3.0, opener=urllib.request.urlopen, sleep=time.sleep)`:
  - `get(source: str, key: str, url: str, *, encoding: str, validate: Callable[[str], bool], form: dict | None = None, refresh: bool = False) -> str`:
    1. Unless `refresh` is set, serve `{root}/raw/{source}/{key}.gz` when it exists.
    2. Otherwise send the request: a POST of the URL-encoded `form` when given, else a GET, through `opener(request, timeout=60)`. Decode the response with `encoding`.
    3. If `validate(text)` is false, raise `NoDataError` and write nothing.
    4. Otherwise write the gzip atomically (temporary file, then `os.replace`) and return the text.
  - Retries: on `URLError`, `TimeoutError`, or HTTP ≥ 500, sleep 10, 30, then 90 s between attempts, then re-raise. HTTP 4xx raises at once.
  - Throttle: sleep `pause_s` before every network call except the first. Cache hits do not sleep.
  - `has(source: str, key: str) -> bool`; `network_calls: int`.

- [ ] **Step 1: Write the failing tests** (fake opener; `pause_s=0`; temporary cache root)

```python
def test_cache_hit_skips_network(self):        # two gets, same key → network_calls == 1
def test_no_data_not_cached(self):             # validate False → NoDataError; has() is False; the next get calls the opener again
def test_retry_backoff_then_success(self):     # URLError twice, then text → returns text; sleep calls == [10, 30]
def test_http_404_not_retried(self):           # HTTPError 404 → raises after exactly 1 opener call
def test_post_form_encoded(self):              # form {"TYPEK": "sii", "season": "03"} → request.data == b"TYPEK=sii&season=03"
def test_cache_root_env_override(self):        # TW_SCREENER_CACHE=<tmp> → cache_root() == Path(<tmp>)
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'cache'`.
- [ ] **Step 3:** Implement `cache.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add throttled fetcher and raw cache`.

### Task 3: Universe master, events, and reconciliation (`universe.py`)

**Files:** Create `scripts/universe.py`, `scripts/tests/test_universe.py`, `scripts/tests/make_fixtures.py`, and `scripts/tests/fixtures/isin_{2,4,5}.html`.

**Interfaces:**
- `@dataclass(frozen=True) class Security`:
  - Fields: `code`, `name`, `isin`, `listing_date` (ISO date), `market` (`"twse" | "tpex" | "emerging"`), `board` (`"main" | "tib"`), `industry`, `cfi`.
  - Property `key`: `f"{code}@{listing_date}"`.
- `ISIN_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"` for modes `2, 4, 5`. Encoding `cp950`; validate: `"<table" in text`; source `isin{mode}`; key `asof`.
- `parse_isin(html: str) -> list[Security]`. It reads table cells with tags stripped and U+3000 replaced by a space, and keeps rows of at least 6 cells where cell 1 matches `^[A-Z]{2}[A-Z0-9]{9}[0-9]$` and cell 5 starts with `ES`:
  - Cell 0 splits on its first space into code and name.
  - Cell 2 is the listing date, as `YYYY/MM/DD`.
  - Cell 3 is the market: `上市 → (twse, main)`, `上市臺灣創新板 → (twse, tib)`, `上櫃 → (tpex, main)`, `興櫃 → (emerging, main)`. Any other value raises `ValueError` naming it.
  - Cell 4 is the industry.
- `load_master(fetcher, asof: str) -> list[Security]`.
- `events(prev: list[Security] | None, cur: list[Security], delisted: dict[str, str] | None = None) -> dict` with these keys:
  - `new`, `exits`: lists of keys.
  - `transfers`: `[{"code", "from", "to"}]`. A code present in both weeks under a different market is one transfer, and it is left out of `new` and `exits`.
  - `renames`: `[{"key", "from", "to"}]`.
  - `code_reuse`: keys of new securities whose code appears in `delisted` with a delisting date before the new listing date. Those keys also stay in `new`.

  With `prev=None`, every list is empty.
- `reconcile(master: list[Security], quoted: set[str], finmind_info: list[dict]) -> dict`. Informational only. Keys:
  - `not_in_finmind`: master codes missing from FinMind.
  - `not_quoted`: TWSE/TPEx master codes without a valid close on `asof`.
  - `finmind_stale`: codes whose latest FinMind row date differs from the modal date.
- `tests/make_fixtures.py` is run by hand, never by the tests. It fetches the live sources and writes trimmed copies into `fixtures/`:
  - Each payload keeps its structure: HTML section rows, JSON keys, table headers.
  - Rows are limited to `FIXTURE_CODES = ["1101", "1303", "1409", "2330", "2801", "3481", "3673", "0050", "00400A", "00625K", "00411A", "6488", "1260"]`, plus the first data row after each ISIN section header and the TAIEX row of `MI_INDEX` `tables[0]`.
  - Date-addressable fixtures are for 2026-11-20; the TPEx institutional fixture is for 2026-11-19. ISIN fixtures are from the capture day. Later tasks add their fixtures to this script.
- `tests/helpers.py` adds `fixture(name, encoding) -> str`, `fx(name) -> dict` (JSON), and `sec(code, listing_date, market, name="n", industry="i", board="main")`.

- [ ] **Step 1:** Write `make_fixtures.py`, run it, and inspect the trimmed files.
- [ ] **Step 2: Write the failing tests**

```python
def test_parse_isin_equities_and_traps(self):
    s = {x.code: x for x in parse_isin(fixture("isin_2.html", "cp950"))}
    self.assertEqual((s["2330"].key, s["2330"].industry), ("2330@1994-09-05", "半導體業"))
    self.assertNotIn("0050", s)                                                    # ETF: CFI not ES*
    self.assertTrue(s["3673"].cfi.startswith("ES") and not s["3673"].isin.startswith("TW"))  # KY issuer
    self.assertTrue(any(x.board == "tib" for x in s.values()))                     # 創新板 section kept

def test_unknown_market_raises(self):          # cell 3 "上市X" → ValueError containing "上市X"

def test_transfer_is_one_event(self):           # Review Focus 1
    ev = events([sec("8908", "1997-03-01", "tpex")], [sec("8908", "2026-10-16", "twse")])
    self.assertEqual(ev["transfers"], [{"code": "8908", "from": "tpex", "to": "twse"}])
    self.assertEqual((ev["new"], ev["exits"]), ([], []))

def test_rename_and_code_reuse(self):           # same key, new name → renames; new "2432" with delisted {"2432": "2010-05-01"} → code_reuse
def test_reconcile_lists(self):                 # one code missing from FinMind, one unquoted, one stale → each listed once
```

- [ ] **Step 3:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'universe'`.
- [ ] **Step 4:** Implement `universe.py`.
- [ ] **Step 5:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 6:** Commit: `feat(screener): add universe master and events`.

### Task 4: Exchange daily tables and `asof` (`exchange.py`)

**Files:** Create `scripts/exchange.py` and `scripts/tests/test_exchange.py`. Add the `twse_mi_index_20261120`, `twse_t86_20261120`, `twse_qfiis_20261120`, `tpex_quotes_20261120`, and `tpex_insti_20261119` JSON fixtures to `make_fixtures.py`.

**Interfaces:**
- URL constants. Cache key: ISO date.

  ```python
  TWSE_QUOTES = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json"
  TWSE_T86    = "https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json"
  TWSE_QFIIS  = "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={ymd}&selectType=ALLBUT0999&response=json"
  TPEX_QUOTES = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={y}/{m}/{d}&id=&response=json"
  TPEX_INSTI  = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={y}/{m}/{d}&response=json"
  TWSE_PER    = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ymd}&selectType=ALL&response=json"
  TPEX_PER    = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json&d={ry}/{m}/{d}"
  ```

  `{ry}` is the ROC year (year − 1911); `{m}` and `{d}` are zero-padded.
- Validation: TWSE needs `stat == "OK"`. TPEx needs `stat.lower() == "ok"` and a non-empty `tables[0]["data"]`. For `TWSE_PER` and `TPEX_PER`, the response `date` must also equal the requested `YYYYMMDD`, so a table for another day is never cached under `asof`.
- `num(s) -> float | None`: strips commas and spaces. `""`, `"-"`, `"--"`, `"---"`, and `"N/A"` give `None`; numbers pass through.
- Parsers. Fields are matched by name unless noted.

  | Function | Source table and fields | Output |
  |---|---|---|
  | `parse_twse_quotes(j) -> dict[str, dict]` | Table whose title contains `每日收盤行情`: `證券代號`, `開盤價`, `最高價`, `最低價`, `收盤價`, `成交股數`, `成交金額` | `{"open", "high", "low", "close", "volume", "value"}` |
  | `parse_taiex(j) -> float` | `tables[0]`, row `發行量加權股價指數`, column `收盤指數` | Index close |
  | `parse_tpex_quotes(j) -> tuple[dict[str, dict], set[str]]` | Table `上櫃股票行情`: `代號`, `開盤`, `最高`, `最低`, `收盤`, `成交股數`, `成交金額(元)`, `發行股數` | Same keys plus `shares`; second value: codes in table `管理股票` |
  | `parse_t86(j) -> dict[str, dict]` | `外陸資買賣超股數(不含外資自營商)`, `外資自營商買賣超股數`, `投信買賣超股數`, `自營商買賣超股數` | `foreign` (first two summed), `trust`, `dealer` |
  | `parse_tpex_insti(j) -> dict[str, dict]` | **By position**, since field names repeat: cell 10, cell 13, cell 22 | `foreign`, `trust`, `dealer`. Raises `ValueError` naming the code when cell 23 ≠ cell 10 + cell 13 + cell 22 |
  | `parse_qfiis(j) -> dict[str, dict]` | `發行股數`, `全體外資及陸資持股比率` | `{"shares", "foreign_pct"}` |
  | `parse_valuation(twse_j, tpex_j) -> dict[str, dict]` | TWSE top-level `fields`/`data`: `證券代號`, `本益比`, `股價淨值比`, `殖利率(%)`. TPEx `tables[0]`: `股票代號`, `本益比`, `股價淨值比`, `殖利率(%)`. Strip every value; TPEx pads names with spaces, and its table gained a `財報年/季` column in 2026 | `{"per", "pbr", "yield"}`; a non-numeric value gives `None` |

- `fetch_day(fetcher, date: str, with_flows: bool) -> dict` returns:
  - `quotes`: `{code: {..., "market"}}` for both boards.
  - `taiex`: float.
  - `managed`: `set[str]`.
  - `flows`, `holdings`: dicts when `with_flows`, else `None`.
- `fetch_valuation(fetcher, date: str) -> dict[str, dict]`: `parse_valuation` over `TWSE_PER` and `TPEX_PER` for `date`, cache key the ISO date. The run calls it for `asof` only (2 requests).
- `resolve_asof(fetcher, today: str, trading_dates: list[str]) -> str`: the latest trading date on or before `today` whose TWSE quotes validate. On `NoDataError`, it steps back one trading date, at most 3 times, then re-raises.

- [ ] **Step 1:** Add the fixtures to `make_fixtures.py` and run it.
- [ ] **Step 2: Write the failing tests**

```python
def test_twse_quotes(self):
    q = parse_twse_quotes(fx("twse_mi_index_20261120.json"))
    self.assertEqual((q["00400A"]["close"], q["00400A"]["value"]), (9.80, 640498037))
    self.assertIsNone(q["00625K"]["close"])                                   # no trade: "--"

def test_taiex(self):
    self.assertEqual(parse_taiex(fx("twse_mi_index_20261120.json")), 36033.29)

def test_t86_foreign_includes_dealer_self(self):
    f = parse_t86(fx("twse_t86_20261120.json"))["3481"]
    self.assertEqual((f["foreign"], f["trust"], f["dealer"]), (46944616, -450532, 2854959))

def test_tpex_insti_positional(self):
    f = parse_tpex_insti(fx("tpex_insti_20261119.json"))["00411A"]
    self.assertEqual((f["foreign"], f["trust"], f["dealer"]), (1155000, 0, 4303539))

def test_tpex_insti_layout_guard(self):         # set cell 23 to "1" → ValueError mentioning "00411A"

def test_tpex_quotes_shares_and_managed(self):
    q, managed = parse_tpex_quotes(fx("tpex_quotes_20261120.json"))
    self.assertEqual((q["00411A"]["close"], q["00411A"]["shares"], managed), (8.19, 481076000, set()))

def test_qfiis(self):
    h = parse_qfiis(fx("twse_qfiis_20261120.json"))["00400A"]
    self.assertEqual((h["shares"], h["foreign_pct"]), (2458640000, 0.54))

def test_valuation_both_boards(self):
    twse = {"stat": "OK", "date": "20261120",
            "fields": ["證券代號", "證券名稱", "收盤價", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"],
            "data": [["1101", "台泥", "22.00", "4.55", 114, "-", "0.78", "115/3"]]}
    tpex = {"stat": "ok", "date": "20261120", "tables": [{
            "fields": ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"],
            "data": [["6488", "環球晶          ", "24.86", "7.70000000", 114, "1.74", "1.60", "115Q3"]]}]}
    self.assertEqual(parse_valuation(twse, tpex), {"1101": {"per": None, "pbr": 0.78, "yield": 4.55},
                                                   "6488": {"per": 24.86, "pbr": 1.60, "yield": 1.74}})

def test_valuation_other_date_rejected(self):   # Review Focus 2: fake TPEx answer dated 20261119 for 2026-11-20 → NoDataError; nothing cached

def test_resolve_asof_steps_back_when_unpublished(self):   # Review Focus 2: fake fetcher raises NoDataError for 2026-11-23
    self.assertEqual(resolve_asof(f, "2026-11-23", ["2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24"]), "2026-11-20")
```

- [ ] **Step 3:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'exchange'`.
- [ ] **Step 4:** Implement `exchange.py`.
- [ ] **Step 5:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 6:** Commit: `feat(screener): add exchange daily tables`.

### Task 5: OpenAPI snapshots (`snapshots.py`)

**Files:** Create `scripts/snapshots.py`, `scripts/tests/test_snapshots.py`.

**Interfaces:**
- `OPENAPI: dict[str, str]`, mapping a name to its URL.
  - TWSE, under `https://openapi.twse.com.tw/v1/`:

    | Name | Path |
    |---|---|
    | `TWT48U_ALL` | `exchangeReport/TWT48U_ALL` |
    | `TWT85U` | `exchangeReport/TWT85U` |
    | `TWTAWU` | `exchangeReport/TWTAWU` |
    | `punish` | `announcement/punish` |
    | `notice` | `announcement/notice` |
    | `applylistingLocal` | `company/applylistingLocal` |
    | `TWT88U` | `exchangeReport/TWT88U` |
    | `suspendListing` | `company/suspendListingCsvAndHtml` |

  - TPEx, under `https://www.tpex.org.tw/openapi/v1/`:

    | Name | Path |
    |---|---|
    | `exright` | `tpex_exright_prepost` |
    | `cmode` | `tpex_cmode` |
    | `disposal` | `tpex_disposal_information` |
    | `warning` | `tpex_trading_warning_information` |
    | `applicants` | `tpex_esb_applicant_companies` |
    | `ipo_no_limit` | `tpex_ipo_no_limit` |
    | `esb_quotes` | `tpex_esb_latest_statistics` |

  Responses are UTF-8 JSON lists. Validate: the text parses as a JSON list; an empty list is valid.
- `class SnapshotMissing(RuntimeError)`.
- `snapshot(fetcher, name: str, asof: str, live: bool) -> list[dict]`: cache key `asof`. When `live` is false and the entry is not cached, raise `SnapshotMissing`.
- `tw_date(s: str) -> str | None`: `"1151120"` and `"115/11/20"` are ROC dates (year + 1911); `"20261029"` is Gregorian; all become ISO dates, and blank gives `None`. `tw_range(s) -> tuple[str, str]` splits on `～` or `~`.
- `EXCLUDE_TAGS = {"altered_trading", "managed", "suspended"}`; `FLAG_TAGS = {"disposition", "attention", "periodic_auction", "cash_offering"}`.
- `parse_statuses(asof: str, p: dict[str, list]) -> dict[str, set[str]]`. A field counts as set when `str(v).strip()` is non-empty; TPEx marks fields with a full-width `Ｙ`.

  | Source | Rule | Tag |
  |---|---|---|
  | `TWT85U` | Every row | `altered_trading` |
  | `TWTAWU` | `TradingHaltDate ≤ asof`, and `TradingResumptionDate` blank or `> asof` | `suspended` |
  | `punish`, `disposal` | End of `DispositionPeriod ≥ asof` | `disposition` |
  | `notice` | Rows with a non-blank `Code` | `attention` |
  | `warning` | Every row | `attention` |
  | `cmode` | `AlteredTrading` set | `altered_trading` |
  | `cmode` | `ManagedStock` set | `managed` |
  | `cmode` | `SuspensionOfTrading` set | `suspended` |
  | `cmode` | `PeriodicTrading` or `MatchingFrequency` set | `periodic_auction` |
  | `TWT48U_ALL` | `SubscriptionRatio` > 0 and `Date` ≥ asof | `cash_offering` |
  | `exright` | `SubscriptionRatioToNewSharesIssued` > 0 and `ExRrightsExDividendDate` ≥ asof | `cash_offering` |

  The ratio is read as a number (blank gives 0). The price fields are not read: they can be text such as `尚未公告` or `註4`.

- `parse_pipeline(asof: str, p: dict[str, list]) -> dict` returns:
  - `upcoming`: `[{"code", "name", "market", "applied", "listing_date", "price"}]` for stocks that applied within the last 365 days and whose listing date is blank or on or after `asof`.
    - TWSE `applylistingLocal` is read **by position**, because its keys are shifted by one column. With `v = list(row.values())`: `v[1]` code, `v[2]` name, `v[3]` application date, `v[9]` listing date, `v[11]` underwriting price.
    - TPEx `applicants` uses `SecuritiesCompanyCode`, `CompanyName`, `Date` (Gregorian), `ListingDate`, and `OfferingPrice`.
  - `first_five`: `{code: {"first", "fifth", "price"}}`, from `TWT88U` (deduplicated on `SecurCode`; `1stTradingDate`, `5thTradingDate`, `PriceUnderwritten`) and from `ipo_no_limit` (`StartDateForStabilizationOperation`, `EndDateForStabilizationOperation`, `UnderwritingPrice`).
  - `emerging`: `{code: {"avg", "last", "volume", "applying_status"}}` from `esb_quotes` (`Average`, `LatestPrice`, `TransactionVolume`, `ApplyingStatus`).
  - `delisted`: `{code: date}` from `suspendListing` (`DelistingDate`).

- [ ] **Step 1: Write the failing tests**

```python
def test_tw_dates(self):
    self.assertEqual([tw_date(x) for x in ("1151120", "115/11/18", "20261029", "")],
                     ["2026-11-20", "2026-11-18", "2026-10-29", None])
    self.assertEqual(tw_range("115/11/23～115/11/27"), ("2026-11-23", "2026-11-27"))
    self.assertEqual(tw_range("1151120~1151126"), ("2026-11-20", "2026-11-26"))

def test_halt_applies_only_while_halted(self):
    p = {"TWTAWU": [{"Code": "2314", "TradingHaltDate": "1151110", "TradingResumptionDate": "1151111"}]}
    self.assertIn("suspended", parse_statuses("2026-11-10", p)["2314"])
    self.assertNotIn("2314", parse_statuses("2026-11-20", p))

def test_cmode_fullwidth_flags(self):
    row = {"SecuritiesCompanyCode": "2067", "AlteredTrading": "Ｙ", "PeriodicTrading": "", "ManagedStock": "",
           "MatchingFrequency": "", "SuspensionOfTrading": ""}
    self.assertEqual(parse_statuses("2026-11-20", {"cmode": [row]})["2067"], {"altered_trading"})

def test_notice_placeholder_ignored(self):
    self.assertEqual(parse_statuses("2026-11-20", {"notice": [{"Number": "0", "Code": "", "Name": ""}]}), {})

def test_applylisting_by_position(self):
    keys = ["Code", "Company", "ApplicationDate", "Chairman", "AmountofCapital ", "CommitteeDate", "ApprovedDate",
            "AgreementDate", "ListingDate", "ApprovedListingDate", "Underwriter", "UnderwritingPrice", "Note"]
    row = dict(zip(keys, ["12", "7867", "特力屋", "1150429", "x", "960000", "1150609", "1150721", "1150730",
                          "1151030", "x", "44.06", ""]))
    up = parse_pipeline("2026-10-20", {"applylistingLocal": [row]})["upcoming"]
    self.assertEqual((up[0]["code"], up[0]["listing_date"], up[0]["price"]), ("7867", "2026-10-30", 44.06))
    self.assertEqual(parse_pipeline("2026-11-20", {"applylistingLocal": [row]})["upcoming"], [])

def test_snapshot_missing_for_past_asof(self):     # empty cache, live=False → SnapshotMissing

def test_cash_offering_both_boards(self):
    p = {"TWT48U_ALL": [{"Date": "1151127", "Code": "3706", "SubscriptionRatio": "0.08219551", "SubscriptionPricePerShare": "52.0000"},
                        {"Date": "1151202", "Code": "00406A", "SubscriptionRatio": "", "SubscriptionPricePerShare": ""},
                        {"Date": "1151110", "Code": "2345", "SubscriptionRatio": "0.01782156", "SubscriptionPricePerShare": "尚未公告"}],
         "exright": [{"ExRrightsExDividendDate": "1151203", "SecuritiesCompanyCode": "6160",
                      "SubscriptionRatioToNewSharesIssued": "0.16060945", "SubscriptionPricePerShare": "註4"},
                     {"ExRrightsExDividendDate": "1151203", "SecuritiesCompanyCode": "5483",
                      "SubscriptionRatioToNewSharesIssued": "0.00000000", "SubscriptionPricePerShare": "0.00"}]}
    self.assertEqual(parse_statuses("2026-11-20", p), {"3706": {"cash_offering"}, "6160": {"cash_offering"}})
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'snapshots'`.
- [ ] **Step 3:** Implement `snapshots.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add openapi snapshot parsers`.

### Task 6: MOPS revenue and income (`mops.py`)

**Files:** Create `scripts/mops.py` and `scripts/tests/test_mops.py`. Add two fixtures to `make_fixtures.py`: `mops_sii_115_10_0.html` (`cp950`; the header rows and the 水泥工業 and 塑膠工業 blocks) and `mops_t163sb04_sii_115_03.html` (UTF-8; the header rows plus 1101, 2801, and 1409).

**Interfaces:**
- Revenue source:
  - `REVENUE_URL = "https://mopsov.twse.com.tw/nas/t21/{board}/t21sc03_{roc}_{month}_{kind}.html"`.
  - `REVENUE_FILES = [("sii", 0), ("sii", 1), ("otc", 0), ("otc", 1), ("rotc", 0)]`.
  - Encoding `cp950`; validate: `"公司代號" in text`; source `rev_{board}_{kind}`; key `YYYY-MM`.
- Income source:
  - `INCOME_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"`, sent as a POST with form `{"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y", "TYPEK": board, "year": str(roc_year), "season": f"{season:02d}"}`.
  - Encoding UTF-8; validate: `"公司代號" in text`; source `inc_{board}`; key `YYYY-Q{s}`.
- `parse_revenue(html: str) -> list[dict]` returns `{"code", "name", "industry", "revenue", "revenue_last_year", "yoy_pct", "note"}` rows:
  - Data rows have 11 cells and a cell 0 matching `^[0-9A-Z]{4,6}$`. The fields are cells 0, 1, 2, 4, 6, and 10.
  - `industry` comes from the latest `產業別：X` cell above the row.
  - Revenue is in thousand NT$ (`單位：千元`).
  - A trailing `*` on the name is stripped. A note of `-` or blank gives `None`. `合計` rows are skipped.
- `revenue_rows(months: dict[tuple[int, int], list[dict]]) -> dict[str, list[dict]]`: per code, FinMind-shaped rows `{"revenue_year", "revenue_month", "revenue"}`, oldest first.
- `deadline(year: int, season: int) -> str`: `(y, 1)` is `y-05-15`, `(y, 2)` is `y-08-14`, `(y, 3)` is `y-11-14`, and `(y, 4)` is `(y+1)-03-31`.
- `due_seasons(asof: str, n: int = 9) -> list[tuple[int, int]]`: the `n` latest seasons whose deadline is on or before `asof`, oldest first.
- `parse_income(html: str) -> tuple[dict[str, dict], set[str]]`:
  - The general template is a table whose header row contains both `營業收入` and `營業利益（損失）`, with full-width parentheses.
  - From those tables, it maps by header name `營業收入`, `營業利益（損失）`, `稅前淨利（淨損）`, `本期淨利（淨損）`, `淨利（淨損）歸屬於母公司業主`, and `基本每股盈餘（元）` to `{"revenue", "op_income", "pretax", "net_income", "net_parent", "eps"}`. A value of `--` gives `None`.
  - The second return value holds the codes found in every other template: bank, securities, financial holding, insurance, and other.
- `standalone(ytd: dict[tuple[int, int], dict[str, dict]]) -> dict[str, list[dict]]`: Q1 equals YTD Q1, and Qs equals YTD(s) − YTD(s−1) of the same year, for every numeric field. A quarter appears only when both inputs exist. Each row carries `year` and `season`, and the rows are oldest first.
- Refresh rules:
  - The latest due season is fetched with `refresh=True` on every run until 30 days after its deadline, to pick up late filers.
  - The latest revenue month is refreshed until the 25th of the following month.

- [ ] **Step 1:** Add the fixtures to `make_fixtures.py` and run it.
- [ ] **Step 2: Write the failing tests**

```python
def test_parse_revenue(self):
    rows = {r["code"]: r for r in parse_revenue(fixture("mops_sii_115_10_0.html", "cp950"))}
    r = rows["1101"]
    self.assertEqual((r["revenue"], r["revenue_last_year"], r["yoy_pct"], r["industry"], r["note"]),
                     (16357176, 13882248, 17.82, "水泥工業", None))
    self.assertIsNotNone(rows["1303"]["note"])
    self.assertNotIn("合計", rows)

def test_parse_income_templates(self):
    gen, other = parse_income(fixture("mops_t163sb04_sii_115_03.html", "utf-8"))
    self.assertEqual((gen["1101"]["revenue"], gen["1101"]["op_income"], gen["1101"]["eps"]), (112522875, 9571599, 0.63))
    self.assertTrue({"2801", "1409"} <= other)
    self.assertNotIn("1409", gen)

def test_standalone_differencing(self):          # inc(revenue, op_income, eps) builds a YTD row
    ytd = {(2026, 1): {"X": inc(100, 10, 1.0)}, (2026, 2): {"X": inc(250, 30, 2.5)}, (2026, 3): {"X": inc(400, 45, 4.0)}}
    out = standalone(ytd)["X"]
    self.assertEqual([q["revenue"] for q in out], [100, 150, 150])
    self.assertEqual([q["op_income"] for q in out], [10, 20, 15])

def test_standalone_skips_undifferenceable(self):    # only (2026, 1) and (2026, 3) → Q1 only

def test_due_seasons(self):
    s = due_seasons("2026-11-23")
    self.assertEqual((s[0], s[-1], len(s)), ((2024, 3), (2026, 3), 9))
    self.assertEqual(due_seasons("2026-11-13")[-1], (2026, 2))
```

- [ ] **Step 3:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'mops'`.
- [ ] **Step 4:** Implement `mops.py`.
- [ ] **Step 5:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 6:** Commit: `feat(screener): add mops revenue and income parsers`.

### Task 7: Factors (`factors.py`)

**Files:** Create `scripts/factors.py`, `scripts/tests/test_factors.py`; add `panel_with(code, closes, values=None, flows=None)` to `tests/helpers.py`.

**Interfaces:**
- Consumes `fetch_day` and `fetch_valuation` output (Task 4), `revenue_rows` and `standalone` (Task 6), and `shared.mt` (Task 1).
- `@dataclass class Panel`:
  - `dates: list[str]` (ascending).
  - `days: dict[str, dict]`: date to `fetch_day` output.
  - Method `close(code, i) -> float | None`.
- `price_rows(panel, code, n: int = 120) -> list[dict]`: FinMind-shaped rows (`date`, `open`, `max`, `min`, `close`, `Trading_Volume`, `Trading_money`) over the last `n` panel dates on which the code has a close.
- `history_days(panel, code, max_gap: int = 60) -> int`: the number of dates with a close in the trailing run. The run breaks at the first gap of more than `max_gap` consecutive panel dates without a close.
- `adv20(panel, code) -> float`: the median traded value over the last 20 panel dates. A date without a row or a trade counts as 0.
- `week_ends(panel, n: int = 13) -> list[int]`: the index of the last panel date in each of the last `n` ISO weeks, the `asof` week included.
- `momentum_6_1(panel, code, i) -> float | None`: `close(i − 21) / close(i − 126) − 1`.
- `persistence(panel, codes: list[str]) -> dict[str, int | None]`. For each code: in how many of the 13 week-ends its momentum ranked in the top third (rank ≤ ceil(n / 3) among the codes with momentum that week). `None` when the code lacks momentum at any of them. Run it on the full-track codes; the result becomes each stock's `persist13`.
- `stock_factors(code, panel, rev: list[dict], latest_row: dict | None, quarters: list[dict], val: dict | None, shares: float | None, market_month: tuple[int, int]) -> dict`:
  - Returns the raw variables in the table below, plus `close`, `adv20`, `ttm_op_income`, `latest_month`, `rev3`, and `rev3_ly` (revenue sums over the last 3 months and the same months a year earlier).
  - Units are percent or percentage points. Any missing input gives `None`.
  - `latest_row` is the stock's `parse_revenue` row for its latest month.

  | Variable | Definition |
  |---|---|
  | `rev_yoy_med6` | `mt.yoy6_median(mt.revenue(rev, []))` |
  | `rev_accel` | Mean of the last 3 `yoy_pct` − mean of the last 12 (needs all 12) |
  | `rev_surge` | `d_t = R_t − R_{t−12}`; `(d_t − mean(d_{t−12..t−1})) / pstdev(d_{t−12..t−1})`. Needs 25 months; `None` when the pstdev is 0 |
  | `opm_delta_4q` | Operating margin over the last 4 quarters − the same over quarters 5–8 back (8 consecutive quarters) |
  | `earnings_yield`, `book_yield` | `100 / PER` when PER > 0; `100 / PBR` when PBR > 0 |
  | `opm_ttm` | Σ op_income ÷ Σ revenue × 100, over the last 4 consecutive quarters |
  | `opm_spread_4q` | max − min of the last 4 quarterly operating margins |
  | `roe_ttm` | TTM EPS ÷ (close ÷ PBR) × 100 |
  | `flow20_pct` | Σ (foreign + trust) over the last 20 dates ÷ shares × 100; a missing day counts as 0 |
  | `trust_days20` | Days in the last 20 with trust > 0 |
  | `rev_yoy3` | `rev3 ÷ rev3_ly × 100 − 100` |
  | `ret13w` | close ÷ close 65 dates earlier × 100 − 100 |
  | `one_off` | The latest month has a note and `yoy_pct > 100` |

- Late filer: when `latest_month < market_month`, every revenue-based variable is `None`: `rev_yoy_med6`, `rev_accel`, `rev_surge`, `rev_yoy3`, `rev3`, and `rev3_ly`.

- [ ] **Step 1: Write the failing tests** (`assertAlmostEqual` for floats)

```python
def test_history_days_spans_board_transfer(self):        # Review Focus 1: one code, quotes on TPEx, then TWSE
    self.assertEqual(history_days(panel_with("8908", [10.0] * 300), "8908"), 300)

def test_history_days_breaks_at_long_gap(self):
    self.assertEqual(history_days(panel_with("X", [10.0] * 100 + [None] * 100 + [10.0] * 100), "X"), 100)

def test_history_days_keeps_short_suspension(self):
    self.assertEqual(history_days(panel_with("X", [10.0] * 135 + [None] * 30 + [10.0] * 135), "X"), 270)

def test_adv20_missing_days_are_zero(self):              # 10 days at 50e6, 10 days absent → 25e6

def test_rev_surge(self):
    R = [100] * 12 + [100, 102] * 6 + [110]              # d over months 13–24 alternates 0, 2; d_25 = 10
    self.assertAlmostEqual(factors_for(rev=R)["rev_surge"], 9.0)

def test_quality_valuation_flow(self):
    # 8 quarters: revenue 100 each, op_income [5, 5, 5, 5, 8, 10, 12, 10], eps of the last 4 [1.0, 1.2, 1.5, 1.3]
    # close 100, PER 20, PBR 2; foreign + trust = 1,000 shares on each of 20 days; shares 2,000,000; trust > 0 every day
    f = factors_for(...)
    self.assertEqual((f["opm_ttm"], f["opm_delta_4q"], f["opm_spread_4q"]), (10.0, 5.0, 4.0))
    self.assertEqual((f["roe_ttm"], f["earnings_yield"], f["book_yield"]), (10.0, 5.0, 50.0))
    self.assertEqual((f["flow20_pct"], f["trust_days20"]), (1.0, 20))

def test_persistence_counts_top_third(self):             # 3 codes, fixed ranks over 200 dates → 13 and 0; one without early prices → None

def test_late_filer_revenue_inputs_null(self):           # Review Focus 5: latest month 2026-09, market month 2026-10
    f = factors_for(latest=(2026, 9), market=(2026, 10))
    self.assertEqual([f[k] for k in ("rev_yoy_med6", "rev_accel", "rev_surge", "rev_yoy3")], [None] * 4)

def test_one_off_flag(self):                             # note "x" with yoy 150 → True; yoy 50 → False
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'factors'`.
- [ ] **Step 3:** Implement `factors.py`. Define the `factors_for` test helper in `test_factors.py`; it fills the defaults.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add factor computations`.

### Task 8: Funnel and composite (`score.py`)

**Files:** Create `scripts/score.py`, `scripts/tests/test_score.py`.

**Interfaces:**
- `PARAMS`:

  ```python
  PARAMS = {
      "min_history": 120, "adv20_min": 30_000_000, "close_min": 10.0, "winsor": (5, 95), "z_clip": 3.0,
      "small_industry_n": 5, "floor_z": -1.0, "availability_min": 0.70,
      "group_weights": {"growth": 0.35, "valuation": 0.25, "quality": 0.15, "flow": 0.15, "persistence": 0.10},
      "mix": (0.8, 0.2), "unfavoured_fraction": 1 / 3, "exception_top_pct": 5.0,
  }
  ```

- `GROUPS` lists `(variable, member weight, sign)` per group:

  ```python
  GROUPS = {
      "growth": [("rev_yoy_med6", 1, 1), ("rev_accel", 1, 1), ("rev_surge", 1, 1), ("opm_delta_4q", 1, 1)],
      "valuation": [("earnings_yield", 0.67, 1), ("book_yield", 0.33, 1)],
      "quality": [("opm_ttm", 1, 1), ("opm_spread_4q", 1, -1), ("roe_ttm", 1, 1)],
      "flow": [("flow20_pct", 1, 1), ("trust_days20", 1, 1)],
      "persistence": [("persist13", 1, 1)],
  }
  ```

  A group score is the member-weighted mean of the available member z-scores.
- `FINANCIAL_INDUSTRIES = {"金融保險業"}`, the label on all three boards.
- `STATUSES`, in evaluation order: `watch_track`, `excluded_status`, `excluded_no_quote`, `excluded_liquidity`, `excluded_price`, `excluded_financial`, `excluded_loss`, `insufficient_data`, `excluded_sector`, `excluded_floor`, `ranked`, `shortlist_actionable`, `shortlist_left_watch`. Task 9 sets the last two.
- `track(s: Security, history_days: int, params=PARAMS) -> str`: `"full"` for TWSE/TPEx stocks with at least `min_history` days, else `"watch"`.
- `winsorize(values: dict[str, float], lo: float, hi: float) -> dict[str, float]`, with bounds from `mt.percentile`.
- `zscores(values: dict[str, float], industry: dict[str, str], min_n: int, clip: float) -> dict[str, float]`:
  - z-score within the industry, with the population standard deviation; a standard deviation of 0 gives 0.0.
  - An industry with fewer than `min_n` values uses the market-wide z-score instead.
  - Results are clipped at ±`clip`.
- `sector_scores(eligible: list[str], industry: dict[str, str], factors: dict[str, dict], trend_ok: dict[str, bool], min_n: int) -> dict[str, dict]` returns per industry `{"n", "rev_breadth", "rev_yoy3", "rel_ret13", "trend_breadth", "score", "unfavoured"}`:
  - `rev_breadth`: the % of members with `rev_yoy3 > 0`.
  - `rev_yoy3`: Σ `rev3` ÷ Σ `rev3_ly` × 100 − 100.
  - `rel_ret13`: the members' mean `ret13w` − the eligible mean.
  - `trend_breadth`: the % of members passing the trend gate.
  - `score`: the mean of the four inputs' z-scores across industries with `n ≥ min_n`. Industries with `n < min_n` get `score 0.0` and are never unfavoured.
  - `unfavoured`: true for the lowest `floor(count × unfavoured_fraction)` qualifying industries.
- `composite(groups: dict[str, float | None], sector: float, params=PARAMS) -> tuple[float | None, float]`. Availability is the sum of the weights of the non-null groups. The result is `(None, availability)` when availability < `availability_min`, else `(mix[0] × Σ(w × g) / availability + mix[1] × sector, availability)`.
- `run_funnel(master, tracks: dict[str, str], tags: dict[str, set[str]], factors: dict[str, dict], trend_ok: dict[str, bool], non_general: set[str], params=PARAMS) -> tuple[dict[str, dict], dict]`:
  - Returns rows keyed by `Security.key`, each with `status`, `reason`, `flags`, `z_<var>`, `g_<group>`, `sector_score`, `availability`, `composite`, `rank`, `rank_trend` (rank inside the trend-pass or trend-fail list), and `trend_ok`.
  - Also returns the funnel counts: `L0`, `L0_full`, `L0_watch`, `L1`, `L2`, `L3`, `L4`, plus `statuses` and `sectors`.
  - Evaluation order:

    | Stage | Rule | Status |
    |---|---|---|
    | Track | Watch track | `watch_track` |
    | L1 | Any `EXCLUDE_TAGS` tag | `excluded_status` |
    | L1 | No close | `excluded_no_quote` |
    | L1 | `adv20 < 30,000,000` | `excluded_liquidity` |
    | L1 | Close < 10 | `excluded_price` |
    | L2 | Industry `金融保險業` | `excluded_financial` |
    | L2 | Any other code in `non_general` | `insufficient_data`, reason `non_general_template` |
    | L2 | `ttm_op_income ≤ 0` | `excluded_loss` |
    | Score | Over the L2 survivors: winsorize each variable market-wide, z-score within industry, group scores, composite. Availability < 0.70 | `insufficient_data` |
    | L3 | Unfavoured industry and composite outside the top 5% of scored stocks | `excluded_sector` |
    | L3 | Unfavoured industry and composite inside the top 5% | Passes, flagged `exception_lane` |
    | L4 | Any group z < −1 | `excluded_floor` |
    | L4 | All others, by composite descending | `ranked` |

  - Flags carried on every row: tags in `FLAG_TAGS`, `one_off_revenue`, `tib`, and `exception_lane`.

- [ ] **Step 1: Write the failing tests**

```python
def test_track_split(self):                     # emerging → watch; tpex with 119 days → watch; 120 → full

def test_winsorize_bounds(self):
    w = winsorize({str(i): float(i) for i in range(1, 101)}, 5, 95)
    self.assertAlmostEqual(w["1"], 5.95); self.assertAlmostEqual(w["100"], 95.05); self.assertEqual(w["50"], 50.0)

def test_industry_z_and_clip(self):             # one industry [1..6] → z("6") ≈ 1.4639; 19 zeros plus one 100 → that z clips to 3.0
def test_small_industry_uses_market_z(self):    # Review Focus 3: 2-member industry → its z equals the market-wide z
def test_small_industry_never_unfavoured(self): # Review Focus 3: 4-member industry worst on every input → score 0.0, not unfavoured

def test_composite_renormalizes(self):
    c, a = composite({"growth": 1.0, "valuation": 0.0, "quality": 0.0, "flow": None, "persistence": None}, 1.0, PARAMS)
    self.assertAlmostEqual(a, 0.75); self.assertAlmostEqual(c, 0.8 * 0.35 / 0.75 + 0.2)

def test_availability_below_70_is_insufficient(self):   # growth and valuation only → (None, 0.60)
def test_floor_excludes_group_below_minus_one(self):   # g_quality −1.2 → excluded_floor; −0.9 → ranked
def test_exception_lane(self):                  # top-5% stock in an unfavoured industry → ranked with exception_lane; the next → excluded_sector
def test_terminal_status_exactly_once(self):    # synthetic master of 40 covering every branch → one status per key; sum(statuses) == 40
def test_financial_excluded(self):              # industry 金融保險業 → excluded_financial, even with full factor data
def test_non_general_template_not_financial_is_insufficient(self):   # Review Focus 5: 1409 in non_general → insufficient_data, non_general_template
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'score'`.
- [ ] **Step 3:** Implement `score.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add funnel and composite scoring`.

### Task 9: Shortlist and tiers (`shortlist.py`)

**Files:** Create `scripts/shortlist.py`, `scripts/tests/test_shortlist.py`.

**Interfaces:**
- `select(ranked: list[dict], prev_actionable: set[str], enter: int = 20, stay: int = 40, cap: int = 30, left_n: int = 10) -> tuple[list[str], list[str]]`. Each `ranked` row carries `code`, `trend_ok`, and `rank_trend`.
  - Actionable: trend-pass codes with `rank_trend ≤ enter`, plus codes in `prev_actionable` with `rank_trend ≤ stay`, ordered by rank and cut at `cap`.
  - Left-side watch: the `left_n` best trend-fail codes.
- `deep_metrics(code: str, asof: str, cache_dir: Path, build=shared.fetch_build) -> dict`:
  - Reads `{cache_dir}/finmind/{asof}/{code}.json` when it exists. Otherwise it calls `build(code, [], asof)` and writes the result there, so a rerun after an exhausted quota resumes where it stopped.
  - Returns the fields below, taken from the `fetch.build` output:

    | Field | Source in the `fetch.build` output |
    |---|---|
    | `close` | `price.metrics.close` |
    | `per_p50` | `valuation.PER.p50` |
    | `per_pct` | `valuation.PER.current_percentile` |
    | `pbr_pct` | `valuation.PBR.current_percentile` |
    | `ntm_eps`, `cb_applicable`, `cb_high_vol` | `financials.core_baseline.ntm_eps`, `.applicable`, `.high_volatility` |
    | `cash_conversion` | `financials.cash_conversion` |
    | `cost_zone` | `institutional.cost_zone` |
    | `gaps` | `gaps` |

  - `QuotaError` and `NotPublishedError` propagate to the caller.
- `buy_proxy(dm: dict) -> float | None`: `(ntm_eps × per_p50 ÷ close − 1) × 100`. `None` unless `cb_applicable` is true and all three inputs are positive.
- `RED_FLAGS = {"disposition", "attention", "periodic_auction", "one_off_revenue"}`.
- `tier(list_name: str, trend_ok: bool, flags: set[str], proxy: float | None) -> str`: `"A"` when `list_name == "actionable"`, `trend_ok` is true, no flag is in `RED_FLAGS`, and `proxy > 15.0`. Otherwise `"B"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_incumbent_stays_within_40(self):       # prev {"B"}: B at rank 35 kept; new C at rank 25 not kept; B at rank 41 dropped
def test_cap_30_keeps_best_ranks(self):         # 20 entrants plus 15 incumbents at ranks 21–35 → ranks 1–30
def test_left_watch_top_10(self):               # 15 trend-fail codes → the 10 best by rank_trend

def test_buy_proxy(self):
    self.assertAlmostEqual(buy_proxy({"cb_applicable": True, "ntm_eps": 10, "per_p50": 15, "close": 120}), 25.0)

def test_buy_proxy_none_when_not_applicable(self):   # cb_applicable False → None; ntm_eps −1 → None

def test_tier_rules(self):
    self.assertEqual(tier("actionable", True, set(), 16.0), "A")
    self.assertEqual(tier("actionable", True, set(), 15.0), "B")
    self.assertEqual(tier("actionable", True, {"attention"}, 30.0), "B")
    self.assertEqual(tier("left_watch", False, set(), 30.0), "B")

def test_deep_metrics_cached(self):             # fake build called once over two calls; the cache file exists
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'shortlist'`.
- [ ] **Step 3:** Implement `shortlist.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add shortlist hysteresis and tiers`.

### Task 10: Watch track and regime (`watch.py`)

**Files:** Create `scripts/watch.py`, `scripts/tests/test_watch.py`.

**Interfaces:**
- `watch_tables(master: list[Security], tracks: dict[str, str], history: dict[str, int], pipeline: dict, emerging_rev: dict[str, list[dict]], asof: str) -> dict` returns three tables:
  - `upcoming`: `pipeline["upcoming"]`, sorted by listing date, then application date.
  - `recent`: watch-track TWSE/TPEx stocks with `code`, `name`, `market`, `listing_date`, `history_days`, `days_to_full = 120 − history_days`, and `first_five` (from `pipeline["first_five"]`).
  - `emerging`: Emerging stocks whose `mt.yoy6_median(mt.revenue(rows, [])) ≥ 20.0` and whose last 3 `yoy_pct` are all > 0, with `avg`, `last`, `volume`, and `applying_status` from `pipeline["emerging"]`.
- `regime(taiex: list[tuple[str, float]]) -> dict`:
  - Returns `close`, `ma60`, `ma60_slope_5d`, `ret12m` (against the close 250 dates back), `above_ma60` (`close > ma60`), `transition`, and `reasons`.
  - `transition` is true when `above_ma60`, or `ret12m > 0`, changed within the last 20 dates. `reasons` lists `ma60_cross` and `ret12m_sign` for whichever changed.
  - With fewer than 270 closes, `transition` is `None` and `reasons` is `["insufficient_history"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_regime_transition_on_cross(self):      # 270 closes of 100, then 10 rising to 110 → transition True; "ma60_cross" in reasons
def test_regime_quiet(self):                    # 280 steadily rising closes → transition False
def test_regime_insufficient_history(self):     # 200 closes → transition None
def test_emerging_standout_rule(self):          # last 6 yoy [25, 30, 20, 22, 24, 26] → listed; last 3 [22, -1, 26] → not listed
def test_recent_days_to_full(self):             # history 80 → days_to_full 40
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'watch'`.
- [ ] **Step 3:** Implement `watch.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add watch track and regime flag`.

### Task 11: History, diff, invariants, forward tracking (`history.py`)

**Files:** Create `scripts/history.py`, `scripts/tests/test_history.py`.

**Interfaces:**
- `week_id(asof: str) -> str`: ISO year and week as `f"{y}-w{w:02d}"`.
- `write_week(root: Path, week: str, files: dict[str, object]) -> Path`:
  - Writes `scripts/screens/{week}/` under `root`, replacing every file.
  - JSON uses `ensure_ascii=False, indent=1`, and CSV has a header row.
  - Every JSON file has top-level `asof`, `week`, and `methodology_version`, and every CSV row starts with those three columns.
- Week folder files:

  | File | Contents |
  |---|---|
  | `universe.csv` | `asof, week, methodology_version, key, code, name, market, board, industry, listing_date, track, history_days, status, reason, flags` (flags joined with `;`) |
  | `scores.csv` | `asof, week, methodology_version, key, code, industry, z_<var>…, g_<group>…, sector_score, availability, composite, rank, rank_trend, trend_ok, list` |
  | `events.json` | Task 3 `events`, plus `status_changes` (`[{"code", "added", "removed"}]`, by tag) and `reconciliation` |
  | `funnel.json` | `counts`, `statuses`, `sectors`, `regime`, `params`, `forward` (`forward_stats` rows and `buy_conversion`) |
  | `shortlist.json` | `actionable` and `left_watch` rows (`code`, `name`, `industry`, `rank`, `rank_trend`, `composite`, `groups`, `flags`, `deep`, `buy_proxy`, `tier`, `command` = `"/tw-equity-report {code}"`), and `tier_a` (codes) |
  | `watch.json` | The Task 10 tables |
  | `diff.json` | The `diff` output below |

- `previous_week(root: Path, week: str) -> str | None`: the greatest folder name below `week` that matches `^\d{4}-w\d{2}$`.
- `diff(prev: dict | None, cur: dict, reports: dict[str, dict]) -> dict`. `prev` and `cur` each hold a week's `shortlist.json` and its `scores.csv` rows. The result has:
  - `entered`: `[{"code", "list", "rank"}]`.
  - `exited`: `[{"code", "list", "reason"}]`, where the reason is `rank_out`, `trend_failed`, the stock's new status, or `delisted`.
  - `rank_delta`: `{code: prev rank − cur rank}`.
  - `streak`: `{code: weeks}`.
  - `composite_delta`.
  - `reports`: the latest report for each shortlisted code.
- `report_index(repo_root: Path) -> dict[str, dict]`: for each code, the newest `reports/equity/{code}-*-{YYYYMMDD}.html` by that suffix, with `path`, `date` (from the suffix), and `rating` and `action` read from the `data-kpi="rating"` and `data-kpi="action"` elements (`None` when absent). Files without a date suffix, such as `2501-cathay-real-estate.html`, are skipped.
- `status_changes(prev_tags: dict[str, set[str]] | None, cur_tags: dict[str, set[str]]) -> list[dict]`: `[{"code", "added", "removed"}]` for each code whose tag set changed, sorted by code. With `prev_tags=None`, it returns an empty list. The previous tags are read from the previous `universe.csv` `flags` and `reason` columns.
- `check_invariants(master_n: int, statuses: dict[str, int], prev_master_n: int | None, events: dict) -> list[str]` returns one message per broken invariant:
  - `sum(statuses) != master_n`;
  - `prev_master_n` is set and `master_n − prev_master_n != len(new) − len(exits)`.
- `append_forward(path: Path, week: str, asof: str, rows: list[dict]) -> None`: columns `week, asof, list, code, close`. It rewrites the file without that week's earlier rows, then appends the new rows.
- `forward_stats(rows: list[dict], close_at, taiex_at, universe_ret) -> list[dict]`. The callables are `close_at(code, date)`, `taiex_at(date)`, and `universe_ret(week, end_date)`, the equal-weight return of that week's L1 stocks. For each list (`tier_a`, `actionable`) and each horizon of 4, 13, 26, and 52 weeks that has fully elapsed, it reports:
  - `weeks`;
  - `hit_rate`: the % of names beating the TAIEX;
  - `median_excess_taiex`, `median_excess_ew`;
  - `turnover`: the mean weekly share of names replaced.
- `buy_conversion(rows: list[dict], reports: dict[str, dict]) -> dict` returns `{"eligible", "converted", "rate"}`. Eligible names are Tier A names with a report dated on or after their week's `asof`. Converted names are those rated `買進` with an action other than `左側觀察`. This is the primary metric (research 4.8).

- [ ] **Step 1: Write the failing tests**

```python
def test_week_id(self):
    self.assertEqual((week_id("2026-11-20"), week_id("2027-01-01")), ("2026-w47", "2026-w53"))

def test_write_week_overwrites(self):           # write twice with different funnel counts → funnel.json holds the second
def test_previous_week(self):                   # folders 2026-w45, 2026-w46, 2026-w48, and "notes" → previous of 2026-w48 is 2026-w46
def test_status_changes(self):                  # prev {"A": {"attention"}}, cur {"A": {"disposition"}, "B": set()} → [{"code": "A", "added": ["disposition"], "removed": ["attention"]}]

def test_invariants(self):
    self.assertEqual(check_invariants(10, {"ranked": 6, "watch_track": 4}, 9, {"new": ["a"], "exits": []}), [])
    self.assertEqual(len(check_invariants(10, {"ranked": 6}, 9, {"new": [], "exits": []})), 2)

def test_diff_entries_exits_streak(self):       # prev A (rank 3, streak 2), B; cur A rank 1, C rank 2, B trend failed → C entered; B exited "trend_failed"; A delta +2, streak 3
def test_report_index_newest(self):             # 2330-tsmc-20261109.html and 2330-tsmc-20261120.html → the 20261120 file, date 2026-11-20, its data-kpi rating; an undated file is skipped
def test_forward_rows_idempotent(self):         # Review Focus 4: append the same week twice → its rows appear once
def test_forward_stats_hit_rate(self):          # 2 names at +10% and −5%, TAIEX at 0% over 4 weeks → hit_rate 50.0, median_excess_taiex 2.5
def test_buy_conversion_rate(self):             # 4 eligible: 2 rated 買進 and actionable, 1 買進 with 左側觀察, 1 中立 → rate 50.0
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'history'`.
- [ ] **Step 3:** Implement `history.py`.
- [ ] **Step 4:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 5:** Commit: `feat(screener): add weekly history and diff`.

### Task 12: Weekly page, portal entries, and checks (`render.py`, `check_screen.py`)

**Files:** Create `scripts/render.py`, `scripts/check_screen.py`, `references/page-contract.md`, `scripts/tests/test_render.py`, `scripts/tests/test_check_screen.py`.

**Interfaces:**
- `render.py <week-folder> [--root .]` writes `reports/screens/tw-screen-{week}.html` and updates `index.html` and `README.md`. Every number comes from the week folder, and from `review.json` when it exists.
- Page requirements:
  - Traditional Chinese, with inline CSS and JS.
  - Light and dark themes, with an `id="mode-toggle"` toggle.
  - Works at 375 px with `overflow-x: clip`; wide tables scroll inside their own container.
  - Sections: `summary`, `tier-a`, `shortlist`, `changes`, `sectors`, `funnel`, `watch`, `forward`, `method`, plus a `nav` that links to earlier weeks' pages. `forward` shows `funnel.json` `forward`: the BUY conversion rate first, then hit rate and median excess return per horizon.
- Page hooks:
  - KPIs: `data-kpi="asof|universe|ranked|shortlist|tier_a|regime"`.
  - Funnel rows: `data-layer="L0|L0_full|L0_watch|L1|L2|L3|L4|L5|L6"`, with their counts.
  - Tier A rows: `data-code="{code}"`, each containing `<code>/tw-equity-report {code}</code>`.
  - Signed figures (rank delta, BUY proxy, composite delta, returns): `data-dir` from `derive.sign_dir`.
  - `<footer>`: data sources, `asof`, `methodology_version`, `data-meta="model"` and `data-meta="effort"` (from `review.json` `generation`), and the disclaimer.
- Template design: design the template once with the `hallmark` skill (Floor gates). Use one fixed theme for every week, with no weekly deal, and record the theme pick in `references/page-contract.md`.
- `card_html(s: dict) -> str`: the `artifact-card` structure from `tw-equity-report/references/report-contract.md` section 6, with:
  - `data-category="equity"`, and `data-keywords` starting with `tw-equity-screener 選股 weekly screen`;
  - `artifact-category` `equity screen` and `artifact-date` = `asof`;
  - title `台股每週選股 {yyyy} 第 {ww} 週`, linking to the page;
  - a 2–3 sentence description with the funnel counts and the Tier A codes;
  - telemetry rows `全市場`, `完整漏斗`, `入圍`, and `Tier A`, then a wide `市場狀態` row and a wide `生成模型` row;
  - footer badge `本週 Tier A：{n} 檔` (`artifact-badge--active` when n > 0, else `artifact-badge--neutral`) and action link `閱讀週報` with an `aria-label`.
- `upsert_card(index_html: str, card: str) -> str`: replaces the card whose `data-keywords` starts with `tw-equity-screener`, or inserts the card as the first child of `<main class="artifacts-grid">`.
- `pages_base(readme: str) -> str`: the first `https://{user}.github.io/{repo}/` prefix among the README's `View Online` links.
- `upsert_readme(readme: str, row: str) -> str`: replaces the `Published Deliverables` row whose local path contains `reports/screens/`, or inserts the row as the first data row. Row format:

  ```markdown
  | **Equity Screen** | [台股每週選股 {yyyy}-W{ww}]({url}) | [View Online]({url}) | [`reports/screens/tw-screen-{week}.html`](./reports/screens/tw-screen-{week}.html) |
  ```

- `check_screen.py <week-folder> [--root .]` prints `PASS`/`FAIL` lines and exits 1 on any failure. It checks:
  1. All 7 week files exist and agree on `asof`, `week`, and `methodology_version`. `review.json` exists with a non-empty `generation.model` and `generation.effort`.
  2. `history.check_invariants` returns no errors.
  3. The page has:
     - every section id;
     - KPI and funnel hooks equal to `funnel.json`;
     - one Tier A row per `tier_a` code, with its command;
     - `--tw-up`, `--tw-down`, and `--tw-flat` in `:root` and again in the dark block;
     - every `data-dir` matching the sign of its figure;
     - the viewport meta, `overflow-x: clip`, and the disclaimer.
  4. `index.html` has exactly one screener card, linking this week's page, with telemetry equal to `funnel.json`. `README.md` has exactly one row with `reports/screens/`, pointing to this week.
  5. Every relative `href` and `src` in the page, the card, and the row resolves.

- [ ] **Step 1:** Design the page template with `hallmark`, and write `references/page-contract.md`.
- [ ] **Step 2: Write the failing tests**

```python
def test_card_replaced_not_duplicated(self):    # Review Focus 4: upsert twice into an index with 2 equity cards → 1 screener card, 3 cards total
def test_card_inserted_first_when_absent(self): # index without a screener card → the new card is the first artifact-card
def test_readme_row_replaced(self):             # an existing reports/screens/ row for 2026-w46 → replaced by 2026-w47; row count unchanged

def test_pages_base(self):
    self.assertEqual(pages_base("[View Online](https://user.github.io/repo/reports/x.html)"), "https://user.github.io/repo/")

def test_check_passes_on_rendered_week(self):   # synthetic week folder in a temporary repo → render → check exits 0
def test_check_fails_on_kpi_mismatch(self):     # change the data-kpi="universe" text → exit 1, and the message names the hook
def test_check_fails_on_wrong_dir(self):        # flip one data-dir → exit 1
```

- [ ] **Step 3:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'render'`.
- [ ] **Step 4:** Implement `render.py` and `check_screen.py`.
- [ ] **Step 5:** Run `SCREENER_TESTS`. Expect PASS.
- [ ] **Step 6:** Commit: `feat(screener): add weekly page and portal entries`.

### Task 13: Orchestrator and skill files

**Files:** Create `scripts/run.py`, `scripts/tests/test_run.py`, `SKILL.md`, `references/methodology.md`, and `references/data-sources.md`. Generate `.claude/skills/tw-equity-screener/SKILL.md`.

**Interfaces:**
- `main(argv: list[str] | None = None, *, fetcher: Fetcher | None = None, finmind=shared.finmind_fetch) -> int`, behind the CLI `run.py [--asof YYYY-MM-DD] [--backfill] [--root .]`. It prints the week folder and the funnel counts.

  | Step | Action |
  |---|---|
  | 0 | Fetch `TaiwanStockTradingDate` starting 450 calendar days before today (it also lists future dates), run `resolve_asof`, then `week_id`. `live` is true when `--asof` is absent or equals the resolved date. |
  | 1 | Run `load_master`, fetch `TaiwanStockInfo`, load the snapshots, and run `fetch_valuation(asof)`; a `NoDataError` from it exits 3. Then compute `events` against the previous week's universe, and `reconcile`. |
  | 2 | Fetch the daily tables for the last 270 trading dates, with flows only for the last 30. If more than 30 dates are uncached and `--backfill` is absent, print the request count and the minutes at 3 s each, and exit 5. |
  | 3 | Revenue: 25 months up to `latest_month(asof)`. Income: `due_seasons(asof)`. |
  | 4 | Compute `stock_factors` for every full-track code, `persistence`, and the trend gate (`shared.trend_gate` on `price_rows`). Merge into the tags `managed` from `parse_tpex_quotes` and `one_off_revenue` from the factors. Run `run_funnel`. |
  | 5 | Run `select`, `deep_metrics`, `buy_proxy`, `tier`, `watch_tables`, and `regime`. |
  | 6 | Run `status_changes`, `diff`, and `check_invariants`; an invariant failure exits 1 before anything is written. Then `write_week` and `append_forward`, and store `forward_stats` and `buy_conversion` in `funnel.json` under `forward`. |

- `latest_month(asof: str) -> tuple[int, int]`: the previous month when `asof` falls on or after the 11th, else the month before that.
- `SKILL.md` frontmatter:

  ```yaml
  name: tw-equity-screener
  description: Run the weekly Taiwan equity screen. Scan every TWSE and TPEx common stock through a growth × valuation × trend funnel built on free full-market data, keep a week-by-week history and diff, publish the weekly page, register it in index.html and README.md, commit, and push. Hands Tier A names to tw-equity-report. User-invoked only.
  argument-hint: "[--asof YYYY-MM-DD] [--backfill] [--deep-research off|sector|finalists]"
  disable-model-invocation: true
  ```

- `SKILL.md` steps:
  0. Parse the arguments; `--deep-research` defaults to `off`. Saturday is the recommended run day, after Friday's flows are published. If `git status --porcelain -- index.html README.md` is not empty, stop and ask the user to commit or stash. Load `finmind` and `conventional-commit`.
  1. From the repo root, run `python .agents/skills/tw-equity-screener/scripts/run.py` with the arguments. On a non-zero exit:

     | Exit | Action |
     |---|---|
     | 2 | Quota exhausted. Rerun within the hour; cached work is kept. |
     | 3 | Not published yet. Rerun later, or pass the previous trading day. |
     | 4 | No archived snapshot for that date. |
     | 5 | Show the backfill estimate, and ask before rerunning with `--backfill`. |

  2. Review, by the LLM and without web search:
     - Read `events.json`, `shortlist.json`, and the shortlisted names' latest 備註 notes.
     - Write `review.json` with `generation` (`{model, effort}`, resolved by the `conventional-commit` skill's metadata script as in `tw-equity-report` Step 4), `notes` (`{code: one-line note in Traditional Chinese}`), and `events_zh`.
     - If a number looks wrong, stop and report it. Never edit the computed files.
  3. Deep research, only when the argument asks for it. Before starting, tell the user that each run is long and token-heavy: the design research used about 5.9M tokens across 46 agents.
     - `sector`: one `deep-research` run on the cycle of the top 3 industries by sector score, saved as `sector_research.md`.
     - `finalists`: one run per Tier A name, at most 3 by composite, using `tw-equity-report` Step 4's query. Each is saved as `research_{code}.md`, which `tw-equity-report` can reuse.
  4. Run `python .agents/skills/tw-equity-screener/scripts/render.py scripts/screens/{week}`.
  5. Run `python .agents/skills/tw-equity-screener/scripts/check_screen.py scripts/screens/{week}`; fix every failure and re-run until it exits 0. If `node` is available, run Hallmark's `sloplint.mjs` on the page.
  6. Stage only the week folder, `scripts/screens/forward.csv`, the page, `index.html`, and `README.md`. Commit as `feat(screener): add {yyyy}-w{ww} weekly screen`, and push with `git push origin HEAD`; never force-push.
  7. Report back in Traditional Chinese:
     - the funnel counts and the universe events;
     - entries and exits;
     - Tier A with the BUY proxy and the `/tw-equity-report <code>` commands;
     - the regime flag and any gaps;
     - the commit hash and the push result.
- `references/methodology.md`:
  - Every rule and parameter from Tasks 7–10, under `methodology_version: 1.0`, with a changelog.
  - The adoption bar for new factors: a point-in-time t-statistic above 3, and the probability of backtest overfitting (PBO) when several variants are compared.
  - For the trend filter and the 6-month YoY median, cite `tw-equity-report/references/methodology.md` sections 2 and 4 instead of copying them.
- `references/data-sources.md`:
  - One row per endpoint from Tasks 3–6 and FinMind: URL, method, encoding, validation, fields used (positions for `applylistingLocal` and TPEx institutional), and cache key.
  - Quirks: KY ISINs, the 創新板 section, the MOPS `_0`/`_1` split, T86 omissions, the full-width `Ｙ`, the `notice` placeholder row, and `TaiwanStockTradingDate` listing future dates.
- Stub and audit: follow the `portable-skill-creator` skill.
  1. From the repo root, run that skill's `scripts/sync_project_skills.py .`, then the same command with `--check`.
  2. Run that skill's `scripts/audit_skill.py` on `.agents/skills/tw-equity-screener`.

- [ ] **Step 1: Write the failing tests**

```python
def test_backfill_guard_exits_5_with_estimate(self):   # fake fetcher with an empty cache → exit 5; output names the request count

def test_latest_month(self):
    self.assertEqual([latest_month(d) for d in ("2026-11-11", "2026-11-10", "2026-01-05")],
                     [(2026, 10), (2026, 9), (2025, 11)])
```

- [ ] **Step 2:** Run `SCREENER_TESTS`. Expect `ModuleNotFoundError: No module named 'run'`.
- [ ] **Step 3:** Implement `run.py`. Write `SKILL.md` and the references with `portable-skill-creator` and `english-doc-guard`, then generate the stub and run the audit.
- [ ] **Step 4:** Run both suites, the `sync_project_skills.py . --check` command, and the audit. Expect every one to pass.
- [ ] **Step 5:** Commit: `feat(screener): add orchestrator and skill files`.

### Task 14: First live run

- [ ] **Step 1:** Run both test suites. Expect PASS.
- [ ] **Step 2:** Run `run.py --backfill`. The first run takes about 40 minutes; handle exits 2–5 as `SKILL.md` Step 1 describes.
- [ ] **Step 3:** Verify against the raw sources:
  - The master count equals the ISIN equity totals.
  - Three random `scores.csv` rows, one each for growth, quality, and flow, recompute by hand from the cached tables.
  - One Tier A BUY proxy recomputes from its cached FinMind file.
  - The universe events are plausible.
- [ ] **Step 4:** Run `SKILL.md` Steps 2, 4, and 5 (review, render, check). Inspect the page at 375 and 1440 px in both themes. Because this run adds a README row, also follow the `portable-readme-creator` skill's audit.
- [ ] **Step 5:** Show the user the page, the funnel counts, and Tier A, and wait for approval.
- [ ] **Step 6:** After approval, run `SKILL.md` Step 6 (commit and push).
