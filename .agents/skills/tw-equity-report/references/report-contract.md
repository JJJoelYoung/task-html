# Report Contract

What every report must contain and how the run is checked. The reader is the owner deciding what to do with the stock, so the page leads with the current action. Visual design is free (via the `hallmark` skill); the content and structure below are not.

## 1. Files per run

| Path | Content |
|---|---|
| `reports/equity/{code}-{slug}-{YYYYMMDD}.html` | The report, a single self-contained file |
| `scripts/equity/{code}-{YYYYMMDD}/data_{code}.json` | Fetched data and computed metrics, written by `scripts/fetch.py` |
| `scripts/equity/{code}-{YYYYMMDD}/research_{code}.md` | External facts, one per line: claim, source, date, URL |
| `scripts/equity/{code}-{YYYYMMDD}/analysis_{code}.json` | Analyst judgments with `basis` fields; `external_facts` as `{text, source, date, url}` |
| `scripts/equity/{code}-{YYYYMMDD}/generate_report.py` | HTML generator (layout and charts; numbers from `scripts/derive.py`) |

Fetching, metrics, derived values, and checks live once in the skill's `scripts/`; a run never copies them into its work folder.

## 2. Page requirements

- One HTML file with inline CSS, JS, and SVG charts. External scripts or fonts only from well-known CDNs, with pinned versions; the page must still read correctly if they fail.
- Light and dark themes (follow `prefers-color-scheme`, plus a toggle).
- Works at 375 px width with no horizontal page scroll; wide tables scroll inside their own container.
- Chart hover shows exact values.
- Header shows company, code, market, industry, and `asof`.

**Markup hooks** that `check_report.py` reads. Prices, signed percentages, multiples, and R:R use `derive.fmt_price`, `fmt_pct`, `fmt_mult`, and `fmt_rr`.

- KPI values: an element whose own text is the value, marked `data-kpi="action|close|rating|target|upside|rr|asof"`.
- R:R values: `data-rr="pullback"`, `data-rr="breakout"`, and `data-rr="hold"`, same form.
- Implied cross multiples: `data-implied="Bull|Base|Bear"`, same form, formatted with `derive.fmt_mult`.
- dim6 chart levels: `data-line="entry|t1|t2|sl" data-value="<number>"`.
- Theme toggle: `id="mode-toggle"`. Chart hover values: `data-tip` attributes.
- Every chart or table sits in a `<figure>` whose `<figcaption>` names FinMind and the date range.

## 3. KPI cards (top of page)

Current action (`derive` `action_zh`) with its condition line (`action_note`) first and most prominent, then close, rating, Base target, Base upside %, pullback R:R (`不適用` when the setup is inactive), and `asof`.

## 4. Sections

Each section is a `<section>` with the given `id`.

| id | Title | Must include |
|---|---|---|
| `dim1` | 價量與均線 | K-line or close chart over 60+ days with MA5/10/20 and volume bars; W20 high/low; alignment and squeeze verdict; spike and dry-up days; float-settling signal |
| `dim2` | 籌碼結構 | Daily and cumulative net flows of the 3 institutional groups; foreign holding ratio trend; margin and short balances; short-to-margin ratio and level; institutional cost zone |
| `dim3` | 營運與財務 | Monthly revenue chart with YoY; YTD revenue and YoY; 4-quarter EPS, gross and operating margin; DSI; cash conversion; industry earnings-quality commentary |
| `dim4` | 估值與目標價 | 5-year PER and PBR bands with current percentile; peer matrix with peer reasons; Bull/Base/Bear table (EPS or BVPS, multiple, target, upside, implied cross multiple with its band position, probability, assumptions); probability-weighted target; rating |
| `dim5` | 催化劑與風險 | Moat; 3–5 catalysts and 3–5 risks, each with expected timing, direction of impact, and an observable indicator |
| `dim6` | 交易部位與風控 | Swing layer: pullback zone and breakout trigger with their conditions, T1, swing T2, hard stop and breakout stop, both R:R values. Hold layer: fair buy price, Base and Bear targets, hold R:R. An inactive setup shows `不適用` with its reason from `derive.SETUP_STATUS_ZH`. Thesis breakers; the K-line chart with horizontal Entry, T1, T2, and SL lines |

## 5. Data labeling

- Every chart and table states its date range and source dataset.
- Judgment content is marked `分析師判斷`; each external fact shows its source and date and links to its URL.
- `gaps` from the data file are listed in a visible note. Null values (including null days in a chart series) are shown as missing, never as zero.
- Footer: data source (FinMind), `asof`, generation date, and the disclaimer `本報告僅供研究參考，不構成任何投資建議。`

## 6. Portal entries

**index.html card** (inside `<main class="artifacts-grid">`), copying the structure of the existing cards:

- `<article class="artifact-card" data-category="equity" data-keywords="...">`. Keywords: code, Chinese name, English name and slug, industry, and the report's main themes.
- `artifact-category` = `equity research`; `artifact-date` = `asof` (`YYYY-MM-DD`).
- Title link to the report; a 2–3 sentence description using numbers from the data file.
- `artifact-telemetry` items: 目標價, 潛在上漲 (or 潛在下跌), 投資評等, 風險報酬比 (`x.xx : 1`, or `不適用`).
- Footer badge and a `閱讀報告 →` action link with an `aria-label`.

**README.md row** in `Published Deliverables`: category, linked title, `View Online` link (GitHub Pages URL), local path. Follow the existing rows.

## 7. Check list (`scripts/check_report.py`)

`check_report.py <work-folder>` exits 1 on any failure. It checks:

1. **Data**: `data_{code}.json` has `asof`, `sources`, and every metric group in methodology.md sections 2–5 (null allowed only when listed in `gaps`); the peer matrix holds the target and 3 peers.
2. **Research**: `research_{code}.md` exists; every `external_facts` item has source, date, and URL, and is linked in the report; every URL in the analysis file is listed in the research file.
3. **Analysis**: Bull/Base/Bear probabilities sum to 100; each scenario, peer, catalyst, and risk has a non-empty `basis`; 3 peers, 3–5 catalysts, 3–5 risks, 2–3 thesis breakers; a multiple outside its anchoring band cites a percentile in its `basis`; a scenario whose implied cross multiple is flagged (`needs_basis`) names that metric in its `basis`.
4. **Calculations**: target prices, upside, weighted target, entry, stops, T1, T2, trigger, fair buy price, and the three R:R values recomputed by `derive.py` appear in the HTML; each `data-implied` hook equals its derived value; each inactive setup shows its reason.
5. **Structure**: sections `dim1`–`dim6`; KPI hooks (including the action) equal the derived values and the action's condition line is shown; Entry, T1, T2, and SL lines in the dim6 chart; disclaimer, `asof`, `分析師判斷`, every gap, captions, themes, viewport, `overflow-x: clip`, and hover values.
6. **Portal**: exactly one `index.html` card and one README row point to the report; the card's telemetry matches the derived values.
7. **Links**: every relative `href`/`src` in the report, the card, and the README row resolves to an existing file.
