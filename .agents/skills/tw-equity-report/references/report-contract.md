# Report Contract

What every report must contain and how the run is checked. Visual design is free (via the `hallmark` skill); the content and structure below are not.

## 1. Files per run

| Path | Content |
|---|---|
| `reports/equity/{code}-{slug}-{YYYYMMDD}.html` | The report, a single self-contained file |
| `scripts/equity/{code}-{YYYYMMDD}/fetch_finmind_{code}.py` | Fetch and compute script |
| `scripts/equity/{code}-{YYYYMMDD}/data_{code}.json` | Fetched data and computed metrics |
| `scripts/equity/{code}-{YYYYMMDD}/analysis_{code}.json` | Analyst judgments with `basis` fields |
| `scripts/equity/{code}-{YYYYMMDD}/generate_report.py` | HTML generator |
| `scripts/equity/{code}-{YYYYMMDD}/test_equity_report.py` | Test script |

## 2. Page requirements

- One HTML file with inline CSS, JS, and SVG charts. External scripts or fonts only from well-known CDNs, with pinned versions; the page must still read correctly if they fail.
- Light and dark themes (follow `prefers-color-scheme`, plus a toggle).
- Works at 375 px width with no horizontal page scroll; wide tables scroll inside their own container.
- Chart hover shows exact values.
- Header shows company, code, market, industry, and `asof`.

## 3. KPI cards (top of page)

Close, rating, Base target, Base upside %, pullback R:R, and `asof`.

## 4. Sections

Each section is a `<section>` with the given `id`.

| id | Title | Must include |
|---|---|---|
| `dim1` | 價量與均線 | K-line or close chart over 60+ days with MA5/10/20 and volume bars; W20 high/low; alignment and squeeze verdict; spike and dry-up days; float-settling signal |
| `dim2` | 籌碼結構 | Daily and cumulative net flows of the 3 institutional groups; foreign holding ratio trend; margin and short balances; short-to-margin ratio and level; institutional cost zone |
| `dim3` | 營運與財務 | Monthly revenue chart with YoY; YTD revenue and YoY; 4-quarter EPS, gross and operating margin; DSI; cash conversion; industry earnings-quality commentary |
| `dim4` | 估值與目標價 | 5-year PER and PBR bands with current percentile; peer matrix with peer reasons; Bull/Base/Bear table (EPS or BVPS, multiple, target, upside, probability, assumptions); probability-weighted target; rating |
| `dim5` | 催化劑與風險 | Moat; 3–5 catalysts and 3–5 risks, each with expected timing, direction of impact, and an observable indicator |
| `dim6` | 交易部位與風控 | Pullback zone and breakout trigger with their conditions; T1, T2; hard stop and breakout stop; thesis breakers; both R:R values; the K-line chart with horizontal Entry, T1, T2, and SL lines |

## 5. Data labeling

- Every chart and table states its date range and source dataset.
- Judgment content is marked `分析師判斷`; external facts cite source and date.
- `gaps` from the data file are listed in a visible note.
- Footer: data source (FinMind), `asof`, generation date, and the disclaimer `本報告僅供研究參考，不構成任何投資建議。`

## 6. Portal entries

**index.html card** (inside `<main class="artifacts-grid">`), copying the structure of the existing cards:

- `<article class="artifact-card" data-category="equity" data-keywords="...">`. Keywords: code, Chinese name, English name and slug, industry, and the report's main themes.
- `artifact-category` = `equity research`; `artifact-date` = `asof` (`YYYY-MM-DD`).
- Title link to the report; a 2–3 sentence description using numbers from the data file.
- `artifact-telemetry` items: 目標價, 潛在上漲 (or 潛在下跌), 投資評等, 風險報酬比.
- Footer badge and a `閱讀報告 →` action link with an `aria-label`.

**README.md row** in `Published Deliverables`: category, linked title, `View Online` link (GitHub Pages URL), local path. Follow the existing rows.

## 7. Test checklist (`test_equity_report.py`)

The test script uses only the standard library and must check:

1. **Data**: `data_{code}.json` has `asof`, `sources`, and every metric group in methodology.md sections 2–5 (null allowed only when listed in `gaps`).
2. **Analysis**: scenario probabilities sum to 100; each scenario, peer, catalyst, and risk has a non-empty `basis`; multiples outside the anchoring bounds have a justification.
3. **Calculations**: recompute target prices, upside, rating, entry, stops, and both R:R values from the JSON files and compare with the values shown in the HTML.
4. **Structure**: sections `dim1`–`dim6` exist; the KPI card values equal the JSON-derived values; Entry, T1, T2, and SL lines exist in the dim6 chart; the disclaimer and `asof` appear.
5. **Portal**: exactly one `index.html` card and one README row point to the report path; the card's telemetry values match the report.
6. **Links**: every relative `href`/`src` in the report, the new card, and the new README row resolves to an existing file.
