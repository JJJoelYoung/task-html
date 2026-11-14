# Task HTML Portal Hallmark Console Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `index.html` (and Section 6 of `report-contract.md`) with Hallmark Floor gates and the `Console` (`graphite`) theme while preserving all existing JS portal behavior and `check_report.py` contract hooks.

**Architecture:** Convert `.hub-header` from a card container to a rule-delimited masthead directly on `--color-paper`, flatten `.artifact-telemetry` from a nested pill box into `1px solid var(--color-rule)` hairline rows inside `.artifact-card`, enforce Console's font/colour grammar (`--font-body` for labels/badges, `--font-outlier` with `tabular-nums slashed-zero` and `white-space: nowrap` for readings, `--color-cool` for category chips), and fix all `sloplint` Floor/Reflex/Craft issues without modifying JS logic or `check_report.py`.

**Tech Stack:** Standalone HTML5, OKLCH CSS custom properties, vanilla ES6 JS, Hallmark `sloplint.mjs` (Playwright render audit), Python `check_report.py` & `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-14-portal-hallmark-restyle-design.md`

## Global Constraints

- Preserve all `check_report.py` `check_portal()` hooks inside `<article class="artifact-card">`: `data-category="equity"`, `<span class="artifact-date">YYYY-MM-DD</span>`, `NT$ {target}`, signed upside `%`, Chinese `rating_zh` (`買進` / `中立` / `賣出`), `rr_card` (`不適用` or `x.xx : 1`), `aria-label=`, and valid relative links.
- Preserve all `sloplint --kept` DOM IDs and selectors recorded in `.hallmark/before.json`: `#artifactsContainer`, `#emptyNotice`, `#resultsCount`, `#searchClear`, `#searchInput`, `#searchKbd`, `#sortSelect`, `.artifact-card`, `.artifact-date`, `.artifact-heading`, `.artifact-telemetry`, `.filter-btn`, and all 6 hrefs.
- Keep `8299` and `2501` legacy financial metrics and descriptions untouched; remove only the `→` glyph in their link text for Gate 63 compliance.
- Maintain strict LF (`\n`) line endings in `index.html`, `report-contract.md`, and docs.

## Review Focus

1. **`375px` single-line telemetry values:** `3.32 : 1`, `315.3 億`, and `347.45 元` previously wrapped mid-value at `375px`. Verify `.telemetry-val` has `getClientRects().length === 1` for every card at `375px` via Playwright.
2. **Input/select edge contrast on `--color-paper` (`17%` L):** Removing the `.hub-header` `--color-paper-2` (`21%` L) container changes the surrounding surface of `.search-input` and `.sort-select`. Verify Gate 40 (`>= 3:1` edge contrast) passes under `sloplint --render`.
3. **Contract regex preservation under sentence-case ratings:** Changing `NEUTRAL / 中立` to `Neutral / 中立` must retain `中立` inside the card for `check_report.py`. Verify with `check_report.py` on `6834-20261112` and `2492-20261110`.
4. **`--kept` structural parity:** Restyling `.hub-header`, `.artifact-telemetry`, and action buttons must not drop any link, control ID, or script-queried selector. Verify with `sloplint --kept`.
5. **LF line ending preservation on Windows:** Verify `b"\r\n"` is absent from `index.html` and `report-contract.md` after edits.

---

### Task 1: Restyle `index.html` CSS Tokens, Masthead, Telemetry Hairlines, and Hallmark Compliance

**Files:**
- Modify: `index.html:12-428`

**Interfaces:**
- Consumes: Existing DOM classes `.hub-header`, `.hub-title`, `.hub-subtitle`, `.toolbar`, `.filter-btn`, `.search-input`, `.search-kbd`, `.search-clear`, `.sort-select`, `.artifact-card`, `.artifact-category`, `.artifact-heading`, `.artifact-telemetry`, `.telemetry-val`, `.artifact-badge`, `.artifact-action`, `.hub-footer`.
- Produces: Console-aligned styles passing Gates `10a`, `20`, `24b`, `26b`, `27`, `40`, `50`, `64`, `F7`, `F16`, and `375px` single-line telemetry rendering.

- [ ] **Step 1: Update Hallmark CSS stamp (`index.html:12-15`)**

  Update the stamp to reflect the actual architecture (`scope: app`, `redesign: restyle`), add `waive 49b` for multi-word stock titles wrapping at `320px–414px`, and state an honest pre-emit critique (naming what was cut — `.hub-header` box, telemetry nested card, and hover lift — rather than unverified `contrast: pass` / `fold: pass` assertions).

- [ ] **Step 2: Add global access, selection, scrollbar, heading wrap, and motion-reduction rules (`index.html:38-64`, end of `<style>`)**

  - Add `::selection` (`color-mix(in oklch, var(--color-accent) 25%, transparent)`), `caret-color: var(--color-accent)` on `input, select`, and `scrollbar-color: var(--color-rule-2) var(--color-paper)` on `:root` (`F16`, `console.md` Build hint).
  - Add `overflow-wrap: break-word; min-width: 0;` to `h1, h2, h3` (Gate 50).
  - Add `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }` (Gate 27).

- [ ] **Step 3: Restyle `.hub-header`, controls, spacing, and focus/active/disabled states (`index.html:72-252`)**

  - Replace `.hub-header` panel box (`background`, `border`, `border-radius`, `padding: var(--space-xl)`) with a rule-separated masthead directly on `--color-paper`: `padding-bottom: var(--space-lg); border-bottom: var(--rule-hair) solid var(--color-rule); margin-bottom: var(--space-lg);`. Remove the now-redundant `border-top`/`padding-top` on `.toolbar` if `.hub-subtitle` sits cleanly above `.toolbar`, or keep a single `1px` rule separator cleanly between title block and toolbar.
  - Set `.search-input` and `.sort-select` resting border to `var(--rule-hair) solid var(--color-muted)` (Gate 40 `>= 3:1` edge contrast).
  - Replace explicit `transition: all 0.15s ease` on `.filter-btn` with `transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;` (Gate 10a).
  - Replace `6px` horizontal padding on `.search-kbd` and `.search-clear` with `var(--space-xs)` / `var(--space-2xs)` (Gate 24b).
  - Add `:active` (`opacity: 0.85`) and `:disabled` (`opacity: 0.45; cursor: not-allowed;`) states for `.filter-btn`, `.search-clear`, `.sort-select`, and `.artifact-action` (Gate 26b).

- [ ] **Step 4: Restyle `.artifact-card`, `.artifact-telemetry`, `.artifact-category`, `.artifact-badge`, and `.artifact-action` (`index.html:254-391`)**

  - Remove `transform: translateY(-2px)` from `.artifact-card:hover` and transition only `border-color 0.15s ease` (Console § Motion, Gate 27).
  - Flatten `.artifact-telemetry`: remove `background`, `border`, `border-radius`, and horizontal padding; set `border-top: var(--rule-hair) solid var(--color-rule); border-bottom: var(--rule-hair) solid var(--color-rule); padding-block: var(--space-sm); margin-bottom: var(--space-md);` (eliminates nested box-in-box and `F7`).
  - Switch `.artifact-category` and `.artifact-badge` from `--font-outlier` to `--font-body` (`font-weight: 500`) per Console Do-nots (Gate 64); change `.artifact-category` color to `var(--color-cool)` (Console instrument grammar) with subtle border/no fill box overload (`F7`).
  - Update `.telemetry-val`: add `font-variant-numeric: tabular-nums slashed-zero; white-space: nowrap;` (fixes `375px` wrapping).
  - Update `.artifact-action`: replace `transition: all 0.15s ease` with `transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;` (Gate 10a).

- [ ] **Step 5: Verify CSS variables have zero unused tokens**

  Run:
  ```bash
  python -c "from pathlib import Path, re; t=Path('index.html').read_text(encoding='utf-8'); vs=re.findall(r'(--[a-z0-9-]+):', t); print([v for v in vs if len(re.findall(re.escape(v)+r'(?![a-z0-9-])', t))<=1])"
  ```
  Expected: `[]`

---

### Task 2: Update `index.html` Markup for Gate 63 & Gate 67, and Align `report-contract.md`

**Files:**
- Modify: `index.html:476-618`
- Modify: `.agents/skills/tw-equity-report/references/report-contract.md:59-70`

**Interfaces:**
- Consumes: Task 1 styles (`.artifact-category`, `.artifact-badge`, `.artifact-action`, `.telemetry-val`).
- Produces: Gate-63/67 compliant card markup in `index.html` and matching specification in `report-contract.md`.

- [ ] **Step 1: Update rating case and action link labels in `index.html:476-618`**

  - On `6834` and `2492`: change `NEUTRAL / 中立` to `Neutral / 中立` (Gate 67, retains `中立` for `check_report.py`), and change `閱讀報告 →` to `閱讀報告` (Gate 63).
  - On `2330`: change `CONVICTION BUY` to `Conviction Buy` (Gate 67), and change `閱讀報告 →` to `閱讀報告` (Gate 63).
  - On `8299` and `2501`: remove `<span>→</span>` from `閱讀完整報告` links (Gate 63), leaving all financial figures, descriptions, and telemetry items unchanged.

- [ ] **Step 2: Align `report-contract.md` Section 6 (`Portal entries`)**

  Update `.agents/skills/tw-equity-report/references/report-contract.md:59-70` to document sentence-case rating text (e.g., `Neutral / 中立`, `Buy / 買進`) and the verb-only action link label `閱讀報告` (no trailing `→` arrow).

- [ ] **Step 3: Run contract checks, unit tests, and LF line-ending check**

  Run:
  ```bash
  python .agents/skills/tw-equity-report/scripts/check_report.py scripts/equity/6834-20261112
  python .agents/skills/tw-equity-report/scripts/check_report.py scripts/equity/2492-20261110
  python -m unittest discover -s .agents/skills/tw-equity-report/scripts/tests
  python -c "from pathlib import Path; print('LF only:', all(b'\r\n' not in Path(p).read_bytes() for p in ('index.html', '.agents/skills/tw-equity-report/references/report-contract.md')))"
  ```
  Expected:
  - `178/178 checks passed for reports/equity/6834-ever-ohms-20261112.html` (exit `0`).
  - `2492-walsin-tech-20261110`: zero `portal:` or `links:` failures.
  - `Ran 47 tests ... OK`.
  - `LF only: True`.

---

### Task 3: Run Hallmark `sloplint` Verification, Playwright Single-Line/Interaction Tests, and Commit

**Files:**
- Verify: `index.html`, `.agents/skills/tw-equity-report/references/report-contract.md`

- [ ] **Step 1: Run `sloplint.mjs` under `--scope app --render --kept`**

  Run:
  ```bash
  node "$HOME/.agents/skills/nutlope/hallmark/scripts/sloplint.mjs" index.html --genre modern-minimal --scope app --render --kept
  ```
  Expected: `0 FAIL` and `0` unwaived `REFLEX` (`0 FAIL kept` / `0 WARN kept`). If any gate reports `FAIL` or unwaived `REFLEX`, fix it in `index.html` and re-run before continuing.

- [ ] **Step 2: Inspect generated screenshots and `.hallmark/compare.html`**

  Read the newly rendered `1440` and `375` screenshots from `.hallmark/` to confirm visual alignment with `Console` (no card-inside-card, readable input edges, unbroken `375px` numbers).

- [ ] **Step 3: Run Playwright interaction & bounding-box regression test**

  Run a Playwright Chromium script verifying:
  - Visible filter buttons (`全部成果 (All) (5)`, `個股報告 (Equity) (5)`), hidden empty tabs.
  - Sorting (`date-desc`, `upside-desc`, `code-asc`), `/` and `Esc` shortcuts, clear button, empty notice.
  - `scrollWidth <= innerWidth` at `1440px` and `375px`.
  - Every `.telemetry-val` element has `getClientRects().length === 1` at `375px` (no mid-value line breaks).
  - Zero console/page errors.

- [ ] **Step 4: Commit via `/conventional-commit`**

  Stage `index.html`, `.agents/skills/tw-equity-report/references/report-contract.md`, `docs/superpowers/specs/2026-11-14-portal-hallmark-restyle-design.md`, and `docs/superpowers/plans/2026-11-14-portal-hallmark-restyle.md` (no `.hallmark/` artifacts, as `.hallmark/` is gitignored), and execute a Conventional Commit following `/conventional-commit`.
