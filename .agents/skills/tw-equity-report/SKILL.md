---
name: tw-equity-report
description: Produce a personal investment-decision HTML report for one Taiwan-listed stock, given its ticker or Chinese name, combining fundamental research with a chip and technical trade plan from FinMind data and Hallmark visual design, then register it in index.html and README.md, test, commit, and push. User-invoked only.
argument-hint: "<stock code or name>"
disable-model-invocation: true
---

# Taiwan Equity 360 Report

Build one standalone, responsive HTML report that helps the user decide what to do with a single Taiwan stock now: a current action, a swing trade plan, and a 12-month hold case, backed by fundamental research. Every number comes from FinMind data computed by a script; every judgment is labeled as judgment. The report is published, so it never holds the user's own positions, cost basis, or capital.

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
- Run `git status --porcelain -- index.html README.md`. If either file already has changes, stop and ask the user to commit or stash them first, since Step 8 stages both files whole.

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

### Step 4: Research and judgments

**Research (`research_{code}.md`).** External facts (results FinMind has not yet published, guidance, pricing, capacity, industry cycle) come only from this file in the work folder.

- If it already exists, or this session holds research on the stock (for example a `/deep-research` result the user ran first), use that, writing it into the file.
- Otherwise run the `deep-research` workflow (in Claude Code, the `Workflow` tool with `name: "deep-research"`), which verifies each claim with independent agents. Pass as `args`: `{name} ({code}), last 6 months: latest results and guidance (法說會), monthly revenue commentary, pricing and capacity, the industry cycle, and major customer or product news.` Keep only claims it reports as verified.
- Without that workflow, run about 5 web searches over the same topics instead. Read the page behind every fact you keep; a search snippet alone is not a source.
- Record each fact as one line: the claim, source name, publication date, and URL. Add a short list of what was searched but not found, refuted, or where sources conflict. State at the top of the file which method gathered it.

**Judgments (`analysis_{code}.json`).** Write the inputs that need analyst judgment, each with a `basis` field naming the data it rests on:

- Peer list with reasons.
- Bull / Base / Bear scenarios: forward EPS (or BVPS), multiple, probability, and assumptions, under the anchoring rules in methodology.md.
- Moat, catalysts, risks, and thesis breakers, in the formats from report-contract.md.
- Earnings-quality commentary for the industry.

- `external_facts`: each external fact the report uses, as `{text, source, date, url}`, with the URL from `research_{code}.md`.

Content that FinMind cannot supply (moat, catalysts, overseas comparisons) either says `分析師判斷` or rests on an external fact; a `basis` that rests on one includes its URL.

**Judgment review (`judgment_review_{code}.md`).** Before Step 5, have a fresh-context subagent review the judgments, so they are checked by a reader who did not write them. Give it only the paths of `data_{code}.json`, `research_{code}.md`, `analysis_{code}.json`, and [references/judgment-review.md](references/judgment-review.md), and tell it to follow that file. For each finding, fix the analysis or record why it does not hold. Write the findings and their disposition to `judgment_review_{code}.md` in the work folder. If subagents are unavailable, do the review yourself from that file after rereading the three inputs, and say so in Step 9.

### Step 5: Generate the report (`generate_report.py`)

Load `hallmark`. report-contract.md fixes the page structure, so run only these Hallmark steps:

- **Floor**: all of it.
- **Ask**: answered here, so skip it. Material: only the figures in `data_{code}.json` and `analysis_{code}.json`; no photos, logos, or quotes. Audience: the user, deciding what to do with the stock. Use: read the current action first, then the trade plan and the thesis behind it. Tone: Hallmark's choice; state it in one line.
- **Shape**: Stat-Led or Long Document (hero figure: the current action and its condition, with rating and Base target); skip the draw, since sections `dim1`–`dim6` are fixed.
- **Deal**: from the repo root, `node <hallmark-skill-dir>/scripts/theme.mjs deal --genre <genre> --prompt "<code> <name> equity research" --log .hallmark/log.json`, so consecutive reports get different themes. Load only the picked theme's file, and follow `references/data-viz.md` for every chart.
- **Picks block**: once, short: theme, tone, signature, sections.
- **Build**: `theme.mjs scaffold <slug> --dealt "<n>/3, seed <seed>" --dir scripts/equity/{code}-{YYYYMMDD}/.hallmark`, then copy the contents of `tokens.css` and `base.css` into the generator's CSS (that folder is gitignored, so the generator must not read it); fill the stamp.
- **Log**: after Step 7 passes, add the entry with `theme.mjs log --entry '<json>' --log .hallmark/log.json`.

The hero review, comps, photos, and the material ask do not apply; the finish review runs in Step 7.

Then write `generate_report.py` in the work folder. It reads `data_{code}.json` and `analysis_{code}.json` with `derive.load_work()`, takes target prices, upside, implied cross multiples, rating, current action, both trade layers, and R:R from `derive.derive()`, and formats them with `fmt_price`, `fmt_pct`, `fmt_mult`, and `fmt_rr`. Import `derive` by adding `.agents/skills/tw-equity-report/scripts` (resolved from the repo root) to `sys.path`. The generator owns layout and charts only; every number comes from the two JSON files or `derive`. Meet every requirement in report-contract.md, including the markup hooks in its section 2.

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

Then capture review screenshots (the first screen and `dim1`–`dim6`, at 1440 and 375 px, light and dark) into the work folder's `.hallmark/shots/`:

```
python .agents/skills/tw-equity-report/scripts/shots.py scripts/equity/{code}-{YYYYMMDD}
```

Exit code 4 means Playwright is missing: skip the review below, say so in Step 9, and give the install line the script prints.

Run Hallmark's finish review in a fresh-context subagent, as its `gates.md` section 6 describes, passing the sloplint renders and these screenshots. Add to its brief: in both themes, every chart's lines, bars, and labels are visible and none overlap; at 375 px no section clips content. Act on its first word, fix, recapture, and re-run `check_report.py`.

### Step 8: Commit and push

1. Stage only this run's files: the report, the work folder (without `__pycache__`), `index.html`, and `README.md`. Leave any other working-tree change unstaged.
2. Commit with the `conventional-commit` skill, e.g. `feat(equity): add 2330 tsmc research report`.
3. Push the current branch with `git push origin HEAD`. If the push is rejected, stop and report; never force-push.

### Step 9: Report back

Give the user: the report path, current action and its condition, rating, close, Base target and upside, the three R:R values, as-of date, any `gaps`, the research method, the judgment-review findings fixed and rejected, the finish-review outcome (or why it was skipped), the commit hash, and the push result.
