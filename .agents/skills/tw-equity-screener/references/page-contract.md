# Weekly Page Contract

The weekly screen page, its portal entries, and what `check_screen.py` enforces. `render.py` is the only writer; every number on the page comes from the week folder and `review.json`.

## 1. Files

| Output | Path (repo root) | Writer |
| --- | --- | --- |
| Weekly page | `reports/screens/tw-screen-{yyyy}-w{ww}.html` | `render.py` |
| Portal card | `index.html`, inside `<main class="artifacts-grid">` | `render.py` (`upsert_card`) |
| README row | `README.md`, `Published Deliverables` table | `render.py` (`upsert_readme`) |

`render.py <week-folder> [--root .]` reads `scripts/screens/{week}/` and fails when any of the seven week files is missing. A re-run of the same week replaces the page, the one screener card, and the one README row; duplicate screener cards or rows collapse to one. `index.html` and `README.md` keep their line endings.

## 2. Theme (fixed for every week)

Hallmark run, app scope, Floor gates. Dealt with `theme.mjs deal --genre editorial` (seed `weekly-taiwan-equity-screener-9445·ce12e4cc·2026-11-24·r0`) and picked **Broadside**, deal 1 of 3, colourway `bill`. Rejected: Manifesto (a dark poster whose red accent would read as "up") and Vellum (blackletter heads over numeric tables).

- Why: the page is numbers and tables. Broadside's buff stock, ink rules at one point or five, and the narrow Archivo Narrow make it read as a printed weekly market sheet, and the narrow face fits the most columns at 375 px.
- Faces: Bevan for the page title, section heads, and wordmark, set over the bold system Traditional Chinese faces (`font-synthesis: none` keeps Bevan from a faux bold while the Chinese face uses its real bold). Archivo Narrow 400 and 700 for everything read, with tabular figures. Six Caps is dropped: it has no Chinese glyphs, and the app scale keeps heads too small for it. Two weights only, 400 and 700.
- Colour: the theme's one vermilion doubles as `--tw-up`, and `--tw-down` adds a green. The page has no other colour, so colour always means direction. Taiwan colours override the theme's "never a second colour" rule: the user's requirement wins over the theme.
- Dark mode: Broadside's `inked` colourway, under `prefers-color-scheme: dark` and `:root[data-mode="dark"]`, switched by `#mode-toggle` and kept in `localStorage.mode`. The toggle stays disabled until its script runs.
- Tables: the stock column (code, then name) comes first and is pinned while the rest scrolls inside the table's own labelled region. Row rules are top borders, so the pinned column keeps them. Every table has a one-line empty note.
- Signature: the funnel ladder, from the whole market down to Tier A, as ruled rows with ink bars.
- Sweep: `sloplint --genre editorial --scope app --render` ends at 0 FAIL and 0 WARN, with F25 (columns off-screen at 375 px) answered by the pinned column.
- Every week reuses this theme. Never deal a new one per week.

## 3. Sections and hooks

Section ids, in order: `summary`, `tier-a`, `shortlist`, `changes`, `sectors`, `funnel`, `watch`, `forward`, `method`. The header holds the wordmark (a link to the portal), the section links, and the mode toggle. A closing `nav` (`aria-label="往期週報"`) after `main` links the pages of earlier weeks only, newest first, with an empty note on the first week.

| Hook | Where | Value |
| --- | --- | --- |
| `data-kpi="asof"` | summary | `funnel.json` `asof` |
| `data-kpi="universe"` / `ranked` / `shortlist` / `tier_a` | summary | `counts.L0` / `L4` / `L5` / `L6`, thousands-separated |
| `data-kpi="regime"` | summary | `regime_label(funnel.regime)`: 站上季線 or 跌破季線, plus （轉折） on a transition, or 資料不足 |
| `data-layer="{layer}"` | funnel | the count of each of L0, L0_full, L0_watch, L1–L6 |
| `data-code="{code}"` | tier-a | one row per `tier_a` code, holding `<code>/tw-equity-report {code}</code>` |
| `data-dir="up\|down\|flat"` | any signed figure | `derive.sign_dir` of BUY proxy, rank delta, sector score, revenue YoY, relative return, and excess return |
| `data-meta="model"` / `effort` | footer, card | `review.json` `generation` |

The footer carries the data sources, `asof`, `methodology_version`, the model and effort, the disclaimer `本頁僅供研究參考，不構成任何投資建議。`, and a link back to the portal.

## 4. Week folder fields the page reads

| File | Fields |
| --- | --- |
| `funnel.json` | `counts` {L0, L0_full, L0_watch, L1–L6}; `statuses` {status: n}; `sectors` {industry: n, rev_breadth, rev_yoy3, rel_ret13, trend_breadth, score, unfavoured}; `regime`; `params`; `forward` {`stats`: `forward_stats` rows, `buy_conversion`} |
| `funnel.json` `params` | `score.PARAMS` plus `shortlist` {enter, stay, cap, left_n, tier_a_proxy}. The method text, the layer notes, and the leads print their numbers from here. |
| `shortlist.json` | `actionable`, `left_watch`: rows {code, name, industry, rank, rank_trend, composite, groups {growth, valuation, quality, flow, persistence}, flags, deep, buy_proxy, tier, command}; `tier_a`: codes |
| `diff.json` | `entered`, `exited`, `rank_delta`, `streak`, `composite_delta`, `reports` |
| `events.json` | `new`, `exits`, `code_reuse` (keys); `transfers`, `renames`; `status_changes`; `reconciliation` |
| `watch.json` | `upcoming`, `recent`, `emerging` (the `watch_tables` rows) |
| `universe.csv` | code, name, status |
| `review.json` | `generation` {model, effort}; `notes` {code: one line}; `events_zh` (one paragraph) |

## 5. Portal entries

- Card: `article.artifact-card`, `data-category="equity"`, `data-keywords` starting `tw-equity-screener 選股 weekly screen`; category `equity screen`; date `asof`; title `台股每週選股 {yyyy} 第 {w} 週` linking to the page; a three-sentence description with the funnel counts, the Tier A codes, and the regime; telemetry `全市場`, `完整漏斗`, `入圍`, `Tier A`, then wide `市場狀態` and wide `生成模型`; badge `本週 Tier A：{n} 檔` (`--active` when n > 0); action `閱讀週報` with an `aria-label`.
- README row: `| **Equity Screen** | [台股每週選股 {yyyy}-W{ww}]({url}) | [View Online]({url}) | [`reports/screens/tw-screen-{week}.html`](./reports/screens/tw-screen-{week}.html) |`, where `{url}` is `pages_base(README)` plus the page path. It replaces the previous week's row, or becomes the table's first row.

## 6. Checks (`check_screen.py <week-folder> [--root .]`)

Prints a `FAIL` line per failed check, then a `PASS` or `FAIL` summary; exits 1 on any failure.

1. The folder is `scripts/screens/{week}/` under the root; all seven week files exist and agree on `asof`, `week`, and `methodology_version`; the week is the folder name and the ISO week of `asof`; `review.json` has a non-empty `generation.model` and `generation.effort`.
2. `history.check_invariants` returns no errors, with the previous week's universe size read from the previous week folder. The counts tie out: `L0` equals the `universe.csv` rows; `statuses` equals the tally of the `universe.csv` status column; `L0 = L0_full + L0_watch`; `L0_watch` equals `watch_track`; `L0_full ≥ L1 ≥ … ≥ L6`; `L5` equals the shortlist rows and the two shortlist statuses; `L4` equals `ranked` plus `L5`; `L6` equals the Tier A codes, which are all actionable.
3. The page has every section id and the earlier-weeks nav; KPI and funnel hooks equal `funnel.json` (read from `<body>`, so a CSS selector never stands in for a hook); one Tier A row per code with its command; `--tw-up`, `--tw-down`, and `--tw-flat` declared in `:root` and in both dark blocks and used by a rule, with up red and down green (oklch, chroma ≥ 0.10); every `data-dir` is up, down, or flat and matches the sign of any non-zero figure; the viewport meta, `overflow-x: clip` on `html, body`, and a footer with the disclaimer, the sources, `asof`, `methodology_version`, and the generation meta; every in-page anchor has its id.
4. `index.html` has exactly one screener card, linking this week's page, dated `asof`, with telemetry, badge, and generation meta equal to the week folder; `README.md` has exactly one `reports/screens/` row, pointing to this week.
5. Every relative `href` and `src` in the page, the card, and the README row resolves.
