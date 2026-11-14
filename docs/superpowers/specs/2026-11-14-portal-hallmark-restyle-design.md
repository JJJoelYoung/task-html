# Task HTML Portal — Hallmark Console Restyle Design

**Date:** 2026-11-14
**Status:** Approved
**Scope:** Small change (`index.html` CSS/semantic markup restyle + `.agents/skills/tw-equity-report/references/report-contract.md` Section 6 alignment)

## 1. Intent & Why

Bring `index.html` into full alignment with Hallmark Floor gates and the `Console` theme (`graphite` colourway) without disturbing the portal's existing interactive features (dynamic category counts, sorting, live search with `/` and `Esc`, card telemetry) or breaking `.agents/skills/tw-equity-report/scripts/check_report.py`.

## 2. Goals, Non-Goals & Anti-Goals

- **Goals:**
  - Achieve `0 FAIL` on Hallmark Floor gates (`10a`, `27`, `40`, `50`, `63`, `67`, `20`).
  - Resolve Console theme mismatches: remove card hover lift (`translateY`), eliminate nested box-inside-box telemetry (`4`, `F7`), switch non-numeric labels/badges from monospace back to body/display face (`64`), apply `tabular-nums slashed-zero` and `white-space: nowrap` to readings (fixing `375px` mid-value wrapping), and restore Console's Amber (operator/target/primary action) vs. Cool Blue (instrument/category) grammar.
  - Keep `check_report.py` (178/178 on `6834`) and `2330/test_equity_report.py` passing without altering verification scripts.
- **Non-Goals:**
  - Changing JavaScript filtering, sorting, or search behavior.
  - Rewriting legacy card metrics or descriptions on `8299` and `2501` (beyond removing the `→` character on the link text for Gate 63).
  - Switching to a multi-column table/audit-trail layout (`full redesign`).
- **Anti-Goals:**
  - Introducing shadows, glows, gradients, or light-mode palettes.
  - Breaking `check_report.py` string/tag hooks (`<article class="artifact-card">`, `data-category="equity"`, `<span class="artifact-date">`, `NT$ ...`, signed upside %, `rating_zh`, `rr_card`, `aria-label=`).

## 3. Constraints

- `check_report.py` `check_portal()` inspects static HTML regexes inside `<article class="artifact-card">`; all checked hooks must remain intact.
- `index.html` and `report-contract.md` must preserve LF-only line endings.
- Under `375px` mobile width, `3.32 : 1` and CJK figure+unit strings inside `.telemetry-val` must stay unbroken on one line.

## 4. Approaches Considered

1. **Approach A — `polish`:** Fix Floor/Reflex rules in place while keeping `.hub-header` box and `.artifact-telemetry` nested pill box. Smallest diff, but retains nested container boxes (`F7`) and misses Console's hairline-driven aesthetic.
2. **Approach B — `restyle` (Selected):** Keep the 3-column card grid, JS behavior, and `check_report.py` compatibility while converting `.hub-header` to an edge-aligned rule-separated masthead, converting `.artifact-telemetry` to hairline-divided rows on `--color-paper-2`, fixing all Floor/Reflex/Craft issues, and syncing `report-contract.md`. Best visual authenticity without contract churn.
3. **Approach C — `full redesign`:** Replace the card grid with a two-pane Console audit trail table. Rejected because it breaks `check_report.py` and reduces readability for 5 prose-rich equity summaries.

## 5. Design Specification

### 5.1 Layout & Container Hierarchy

```text
+-----------------------------------------------------------------------+
| Task HTML Deliverables Hub                                            |
| Subtitle on --color-paper (no outer card border/radius)               |
| --------------------------------------------------------------------- |
| [全部成果 (All) (5)] [個股報告 (Equity) (5)]   [搜尋... /] [最新日期 v] |
+-----------------------------------------------------------------------+
                                                          顯示 5 / 5 筆
+---------------------+  +---------------------+  +---------------------+
| equity research  dt |  | equity research  dt |  | equity research  dt |
| Title               |  | Title               |  | Title               |
| Summary prose       |  | Summary prose       |  | Summary prose       |
| ------------------- |  | ------------------- |  | ------------------- |
| 收盤價    目標價     |  | 收盤價    目標價     |  | 收盤價    目標價     |
| 潛在上漲  風險報酬比 |  | 潛在上漲  風險報酬比 |  | 潛在上漲  風險報酬比 |
| 投資評等             |  | 投資評等             |  | 投資評等             |
| ------------------- |  | ------------------- |  | ------------------- |
| [動作：...] [閱讀報告]|  | [動作：...] [閱讀報告]|  | [動作：...] [閱讀報告]|
+---------------------+  +---------------------+  +---------------------+
```

### 5.2 Specific Changes

- **Masthead (`.hub-header`)**: Remove card background, border, and border-radius; use `border-bottom: var(--rule-hair) solid var(--color-rule)` and vertical padding directly on `--color-paper`.
- **Card Telemetry (`.artifact-telemetry`)**: Remove `--color-paper-3` fill, outer border, and pill radius; replace with `border-top` and `border-bottom` in `1px solid var(--color-rule)` so readings sit directly on `--color-paper-2`.
- **Typography & Numbers**:
  - `h1, h2, h3`: add `overflow-wrap: break-word; min-width: 0;` (Gate 50).
  - `.artifact-category`, `.artifact-badge`, `.results-count`: use `var(--font-body)` (`font-weight: 500` on badges/tags, `font-variant-numeric: tabular-nums` on `.results-count`) instead of monospace (Gate 64 / Console Do-not).
  - `.telemetry-val`: keep `--font-outlier`, add `font-variant-numeric: tabular-nums slashed-zero; white-space: nowrap;` to fix `375px` wrapping.
  - Rating text (`6834`, `2492`, `2330`): sentence case (`Neutral / 中立`, `Conviction Buy`) to satisfy Gate 67 (`<=15px` uppercase rule) while preserving `check_report.py`'s `中立` substring match.
- **Colour & Controls**:
  - `.artifact-category`: `color: var(--color-cool)` on subtle rule/cool border (instrument tag), reserving `--color-accent` for primary filter control and target/upside highlights.
  - `.search-input`, `.sort-select`: `border: var(--rule-hair) solid var(--color-muted)` (or contrast-verified `>=3:1` edge against surface, Gate 40) + `caret-color: var(--color-accent)` (`F16`).
  - Action links: remove `→` suffix (`閱讀報告` / `閱讀完整報告`, Gate 63).
  - Spacing & States: replace `6px` padding on `.search-kbd` / `.search-clear` with `var(--space-2xs)` / `var(--space-xs)` (`24b`); add `:active` and `:disabled` styles (`26b`); add `::selection` and `scrollbar-color` (`F16`).
- **Motion & Hallmark Stamp**:
  - Remove `transform: translateY(-2px)` on `.artifact-card:hover` (Console § Motion); list explicit `transition` properties (`color, background-color, border-color`, Gate 10a); add `@media (prefers-reduced-motion: reduce)` block (Gate 27).
  - Update CSS stamp accurately (`scope: app`, `redesign: restyle`, `waive 49b` for multi-line card title links at `320px–414px`, honest `pre-emit critique`).
- **Docs Alignment**: Update `.agents/skills/tw-equity-report/references/report-contract.md` Section 6 to match sentence-case rating examples (`Neutral / 中立`, `Buy / 買進`) and verb-only action link (`閱讀報告`).

## 6. Verification Criteria

- `node .../sloplint.mjs index.html --genre modern-minimal --scope app --render --kept` reports `0 FAIL` and `0` unwaived `REFLEX`.
- `python .agents/skills/tw-equity-report/scripts/check_report.py scripts/equity/6834-20261112` exits `0` (`178/178` passed).
- Playwright check confirms `0` console/page errors, working filter/sort/search/shortcuts, and zero horizontal overflow + unbroken telemetry numbers at `375px` and `1440px`.
