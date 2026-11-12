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

### Step 2: Fetch and compute (`data_{code}.json`)

The bundled [scripts/](scripts/) implement methodology.md: `fetch.py` fetches and computes sections 1 to 5, and `derive.py` computes sections 6 and 7. From the repo root, run:

```
python .agents/skills/tw-equity-report/scripts/fetch.py {code} --asof {asof} --out scripts/equity/{code}-{YYYYMMDD}/
```

It writes `data_{code}.json` with `asof`, `tool_version`, `sources`, and `gaps`, reading the token from `FINMIND_TOKEN`. Inspect the JSON before going on.

- Exit code 2 means the FinMind hourly quota is exhausted: stop and tell the user it resets within the hour, and a higher FinMind tier raises it.
- Exit code 3 means FinMind has not yet published a chip dataset for `asof`: stop and tell the user to rerun later that evening, or offer the previous trading day as `--asof`.
- On any other error, stop and report it.
- Every number comes from the script. Missing data appears only as a script-recorded `gap`, disclosed in the report; never fill it with estimates, and never type market data into code or JSON.
- To change a metric, edit the shared script and its tests, then run `python -m unittest discover -s .agents/skills/tw-equity-report/scripts/tests`. A change applies to every later report, so confirm it with the user first.
- The scripts use only Free-tier datasets, so the report builds on any FinMind account. Before adding a dataset above Free (for example `TaiwanStockHoldingSharesPer`, Backer), check the account tier with the `setup-finmind-mcp` skill's `smoke` command; its hourly limit maps to the tier (600 Free, 1,600 Backer, 6,000 Sponsor). If the API refuses a dataset for tier, record a gap instead of failing.

### Step 3: Choose peers

Pick 3 Taiwan-listed companies that compete directly with the target's main business. Exclude customers, suppliers, and companies related only through the supply chain. Write a one-line reason for each into the analysis file (Step 4). Re-run `fetch.py` with the same `--asof` and `--peers <code>,<code>,<code>` so the peer matrix comes from data.

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

Then write `generate_report.py` in the work folder. It reads `data_{code}.json` and `analysis_{code}.json` with `derive.load_work()`, takes target prices, upside, rating, trade setup, and R:R from `derive.derive()`, and formats them with `fmt_price`, `fmt_pct`, and `fmt_rr`. Import `derive` by adding `.agents/skills/tw-equity-report/scripts` (resolved from the repo root) to `sys.path`. The generator owns layout and charts only; every number comes from the two JSON files or `derive`. Meet every requirement in report-contract.md, including the markup hooks in its section 2.

### Step 6: Register the report

- `index.html`: add one card inside `<main class="artifacts-grid">`, using the existing `artifact-card` structure. If a card already links to the same report path, replace it instead of adding another.
- `README.md`: add one row to the `Published Deliverables` table, or replace the row with the same local path. Keep the README's existing style.

### Step 7: Check

From the repo root, run:

```
python .agents/skills/tw-equity-report/scripts/check_report.py scripts/equity/{code}-{YYYYMMDD}
```

It checks the report against report-contract.md section 7. Fix the cause of every `FAIL` in the generator, the analysis file, or the portal entries, and re-run until it exits 0.

Then, if `node` is available, run Hallmark's linter from the hallmark skill directory: `node <hallmark-skill-dir>/scripts/sloplint.mjs <report> --render`. Fix every `FAIL`, and fix or waive every `REFLEX`. If `node` is missing, skip the linter and say so in Step 9.

### Step 8: Commit and push

1. Stage only this run's files: the report, the work folder (without `__pycache__`), `index.html`, and `README.md`. Leave any other working-tree change unstaged.
2. Commit with the `conventional-commit` skill, e.g. `feat(equity): add 2330 tsmc research report`.
3. Push the current branch with `git push origin HEAD`. If the push is rejected, stop and report; never force-push.

### Step 9: Report back

Give the user: the report path, rating, close, Base target and upside, R:R, as-of date, any `gaps`, the commit hash, and the push result.
