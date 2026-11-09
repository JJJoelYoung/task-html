---
name: tw-equity-report
description: Produce an institutional-grade 360-degree equity research HTML report for one Taiwan-listed stock, given its ticker or Chinese name, using FinMind data and Hallmark visual design, then register it in index.html and README.md, test, commit, and push. User-invoked only.
argument-hint: "<stock code or name>"
disable-model-invocation: true
---

# Taiwan Equity 360 Report

Build one standalone, responsive HTML research report for a single Taiwan stock, written from the standpoint of a top-tier foreign brokerage analyst. Every number comes from FinMind data computed by a script; every judgment is labeled as judgment.

## Required companions

Load these skills before the steps that use them:

- `finmind`: dataset names, column units, point-in-time rules, and quota limits. Load before Step 1.
- `hallmark`: visual design of the report page. Load before Step 5. The design is free each run; do not copy an earlier report's layout.

Read both references before writing any script:

- [references/methodology.md](references/methodology.md): fixed definitions, formulas, and thresholds for every metric. Never substitute your own.
- [references/report-contract.md](references/report-contract.md): required report content, file layout, portal entries, and test checklist.

## Language

- Report body, card text, and README row: Traditional Chinese (company names may add English).
- Scripts, code comments, JSON keys, and commit messages: English.

## Workflow

### Step 0: Resolve the argument

The argument is a 4-digit code or a company name.

1. No argument: ask the user for one and stop.
2. Call the finmind MCP tool `get_stock_info` with the argument.
   - Code with no match: report it and stop.
   - Name with several matches: list the candidates (code, name, market, industry) and ask the user to pick.
3. Record `code`, Chinese name, market (`twse`/`tpex`/`emerging`, latest row), and `industry_category`.
4. Choose `slug`, the lowercase hyphenated English short name. If `reports/equity/` already has a report for this code, reuse its slug. Otherwise use the common English name (`tsmc`, `cathay-real-estate`).

### Step 1: Fix the as-of date and paths

- `asof` = latest trading date present in `TaiwanStockPrice` for the code. `YYYYMMDD` = `asof` without dashes.
- Report: `reports/equity/{code}-{slug}-{YYYYMMDD}.html`.
- Work folder: `scripts/equity/{code}-{YYYYMMDD}/`.
- If either already exists, overwrite it without asking.

### Step 2: Fetch and compute (`fetch_finmind_{code}.py`)

Write a Python script in the work folder that:

- Uses only the standard library (`urllib.request`, `json`, `statistics`) against `https://api.finmindtrade.com/api/v4/data`.
- Reads an optional token from the `FINMIND_TOKEN` environment variable and sends it as `Authorization: Bearer <token>`. Never write a token into any file.
- Sleeps about 0.5 s between calls. On HTTP 402/429, stop and tell the user the quota is exhausted and that setting `FINMIND_TOKEN` raises it.
- Fetches the datasets listed in methodology.md for the target, plus the latest `TaiwanStockPER` row for each code passed in `--peers` (comma-separated; empty on the first run).
- Computes every metric in methodology.md and writes `data_{code}.json` with `asof`, a `sources` map (metric group to dataset and date range), and a `gaps` list for missing data.

Run it and inspect the JSON before going on. Missing data is recorded in `gaps` and disclosed in the report; never fill it with estimates.

### Step 3: Choose peers

Pick 3 Taiwan-listed companies that compete directly with the target's main business. Exclude customers, suppliers, and companies related only through the supply chain. Write a one-line reason for each into the analysis file (Step 4). Re-run the fetch script with `--peers <code>,<code>,<code>` so the peer matrix comes from data.

### Step 4: Write judgments (`analysis_{code}.json`)

Write the inputs that need analyst judgment, each with a `basis` field naming the data it rests on:

- Peer list with reasons.
- Bull / Base / Bear scenarios: forward EPS (or BVPS), multiple, probability, and assumptions, under the anchoring rules in methodology.md.
- Moat, catalysts, risks, and thesis breakers, in the formats from report-contract.md.
- Earnings-quality commentary for the industry.

Content that FinMind cannot supply (moat, catalysts, overseas comparisons) must say `分析師判斷` or cite an external source with its date.

### Step 5: Generate the report (`generate_report.py`)

Load `hallmark` and give it these answers so it does not stop to ask:

- Material: only the figures in `data_{code}.json` and `analysis_{code}.json`; no photos, logos, or quotes.
- Audience: investors and analysts reading Taiwan equity research.
- Use: understand the thesis and act on the trade setup.
- Tone: Hallmark's choice; state it in one line.

Prefer the Stat-Led or Long Document shape (hero figure: rating and Base target), and follow Hallmark's `references/data-viz.md` for every chart.

Then write a script that reads `data_{code}.json` and `analysis_{code}.json`, computes the derived values that methodology.md assigns to the generator (target prices, upside, rating, trade setup, R:R), and writes the HTML. No number may be typed directly into the HTML template. Meet every requirement in report-contract.md.

### Step 6: Register the report

- `index.html`: add one card inside `<main class="artifacts-grid">`, using the existing `artifact-card` structure. If a card already links to the same report path, replace it instead of adding another.
- `README.md`: add one row to the `Published Deliverables` table, or replace the row with the same local path. Keep the README's existing style.

### Step 7: Test (`test_equity_report.py`)

Write and run a standard-library test script that covers the checklist in report-contract.md. Fix the cause of every failure and re-run until all tests pass. Do not proceed with any failure.

Then, if `node` is available, run Hallmark's linter from the hallmark skill directory: `node <hallmark-skill-dir>/scripts/sloplint.mjs <report> --render`. Fix every `FAIL`, and fix or waive every `REFLEX`. If `node` is missing, skip the linter and say so in Step 9.

### Step 8: Commit and push

1. Stage only this run's files: the report, the work folder (without `__pycache__`), `index.html`, and `README.md`. Leave any other working-tree change unstaged.
2. Commit with the `conventional-commit` skill, e.g. `feat(equity): add 2330 tsmc research report`.
3. Push the current branch with `git push origin HEAD`. If the push is rejected, stop and report; never force-push.

### Step 9: Report back

Give the user: the report path, rating, close, Base target and upside, R:R, as-of date, any `gaps`, the commit hash, and the push result.
