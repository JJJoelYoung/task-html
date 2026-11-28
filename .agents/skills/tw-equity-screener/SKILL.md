---
name: tw-equity-screener
description: Run the weekly Taiwan equity screen. Scan every TWSE and TPEx common stock through a growth × valuation × trend funnel built on free full-market data, keep a week-by-week history and diff, publish the weekly page, register it in index.html and README.md, commit, and push. Hands Tier A names to tw-equity-report. User-invoked only.
argument-hint: "[--asof YYYY-MM-DD] [--backfill] [--deep-research off|sector|finalists]"
disable-model-invocation: true
---

# Taiwan Equity Weekly Screen

Screen the whole Taiwan market once a week and publish the result. Every TWSE and TPEx stock goes through the L0–L6 funnel (universe, investability, red flags, sector gate, composite, shortlist, tiers); Emerging stocks and young listings go to a watch track. Each run writes a committed week folder that the next week diffs against, and its Tier A names are the candidates for `/tw-equity-report`. Scripts compute every number; you review them and write only short notes. The page is public, so it never holds the user's positions, cost basis, or capital.

## Required companions

- `finmind`: quota limits and dataset rules for the FinMind calls (trading calendar, stock list, shortlist deep metrics). Load before Step 1.
- `conventional-commit`: the `generation` metadata in Step 2 and the commit in Step 6.
- `hallmark`: only its linter, in Step 5. The page theme is fixed; never deal a new one.
- `deep-research`: only when `--deep-research` is `sector` or `finalists` (Step 3).

Read these when the task needs them:

- [references/methodology.md](references/methodology.md): every rule and parameter, `methodology_version`, the adoption bar, and the changelog.
- [references/data-sources.md](references/data-sources.md): each endpoint's URL, encoding, validation, fields, cache key, and quirks.
- [references/page-contract.md](references/page-contract.md): the weekly page, the portal card, the README row, and what `check_screen.py` checks.
- [references/known-issues.md](references/known-issues.md): open defects and deferred fixes, with deadlines. Read it before changing a script.

## Language

- The page, the card, the README row, the `review.json` text, and the report back: Traditional Chinese.
- Scripts, comments, JSON keys, docs, and commit messages: English.

## Arguments

| Argument | Default | Effect |
|---|---|---|
| `--asof YYYY-MM-DD` | The latest published trading day | Replays a past date. The ISIN lists and snapshots serve only today, so a past date works only if a live run cached them (exit 4 otherwise). |
| `--backfill` | Off | Lets the run fetch more than 30 uncached trading dates. The first run needs it: about 770 requests, at least 40 minutes. |
| `--deep-research off\|sector\|finalists` | `off` | Step 3. Handled by you, never passed to a script. |

## Workflow

### Step 0: Prepare

1. Parse the arguments. For any other `--deep-research` value, stop and ask.
2. Saturday is the recommended run day, after Friday's flows are published. On another day, `asof` still resolves to the latest published trading day.
3. Run `git status --porcelain -- index.html README.md`. If either file has changes, stop and ask the user to commit or stash them, since Step 6 stages both whole.
4. Load `finmind` and `conventional-commit`.

### Step 1: Run the screen

From the repo root, passing `--asof` and `--backfill` when given:

```
python .agents/skills/tw-equity-screener/scripts/run.py [--asof YYYY-MM-DD] [--backfill]
```

- It fetches through a throttled raw cache outside the repo (`~/.cache/tw-equity-screener`, or `TW_SCREENER_CACHE`), reads the FinMind token from `FINMIND_TOKEN` when set, and writes the week folder `scripts/screens/{week}/` (`{week}` is `{yyyy}-w{ww}`) and `scripts/screens/forward.csv`. It prints `asof`, the week folder, and the funnel counts.
- A normal week takes a few minutes, a backfill 40 or more. Run it in the background where the platform allows, and wait for it to exit. Never start a second run while one is running.
- A rerun replaces the whole week folder, `review.json` and research files included. Move research files aside first and put them back after, then redo Step 2.

On a non-zero exit:

| Exit | Action |
|---|---|
| 1 | An invariant failed (the output names it), or a script raised an error such as a changed table layout. The week folder was not written. Report the message and stop. |
| 2 | The FinMind quota is exhausted. Tell the user it resets within the hour; a rerun then resumes from the cache. |
| 3 | A source has not published `asof` yet. Rerun later; on Saturday every Friday table is out. An earlier `--asof` works only for a date a live run cached. |
| 4 | No ISIN list or snapshot is cached for that date. Rerun without `--asof`, or with a date a live run covered. |
| 5 | Show the printed backfill estimate, and ask before rerunning with `--backfill`. |

On any other error, stop and report it.

### Step 2: Review (`review.json`)

Review the week by reading only, with no web search. Read `events.json` and `shortlist.json` in the week folder; each shortlist row's `revenue_note` holds the latest month's 備註 note, or null. Then write `review.json` in the week folder:

- `generation`: `{"model", "effort"}`, resolved with the `conventional-commit` skill's `scripts/get_agent_metadata.py`, as `tw-equity-report` Step 4 does. If the script is missing or reports `missing` fields, ask the user.
- `notes`: `{code: one line}` for every shortlisted code, in Traditional Chinese: the group that carries its rank, and any flag or 備註 note worth knowing.
- `events_zh`: one Traditional Chinese paragraph on the universe events, status changes, and reconciliation.

If a number looks wrong, stop and report it. Never edit the computed files.

### Step 3: Deep research (on request only)

Skip this step when `--deep-research` is `off`. Otherwise, first tell the user that each run is long and token-heavy (the design research used about 5.9M tokens across 46 agents). Then run the `deep-research` workflow as `tw-equity-report` Step 4 does, keeping only verified claims, in that step's research-file format:

- `sector`: one run on the cycle of the top 3 industries by `score` in `funnel.json` `sectors`, among those with at least `params.small_industry_n` members. Save it as `sector_research.md` in the week folder.
- `finalists`: one run per Tier A name, at most 3 by composite, with `tw-equity-report` Step 4's query. Save each as `research_{code}.md` in the week folder, where a later `tw-equity-report` run can reuse it.

### Step 4: Render

```
python .agents/skills/tw-equity-screener/scripts/render.py scripts/screens/{week}
```

It writes `reports/screens/tw-screen-{week}.html` and replaces the screener card in `index.html` and its row in `README.md`.

### Step 5: Check

```
python .agents/skills/tw-equity-screener/scripts/check_screen.py scripts/screens/{week}
```

Fix every `FAIL` at its cause and re-run until it exits 0: fix `review.json` in place; fix a `render.py` bug with a test, in its own commit before Step 6. Never edit the page by hand. A failed count or invariant means a computed number is wrong: stop and report it.

Then, if `node` is available, run `node <hallmark-skill-dir>/scripts/sloplint.mjs reports/screens/tw-screen-{week}.html --genre editorial --scope app --render`, and fix every `FAIL` the same way. If `node` is missing, skip the linter and say so in Step 7.

### Step 6: Commit and push

1. Stage only the week folder, `scripts/screens/forward.csv`, the page, `index.html`, and `README.md`. Leave every other change unstaged.
2. Commit with the `conventional-commit` skill: `feat(screener): add {yyyy}-w{ww} weekly screen`.
3. Push with `git push origin HEAD`. Invoking this skill authorizes the push, scheduled runs included, so never ask first. Run it as a separate command, exactly as written, so a permission allow rule for that command matches it. If the push is rejected, stop and report; never force-push.

### Step 7: Report back

In Traditional Chinese, give the user:

- the funnel counts and the universe events;
- the entries and exits;
- Tier A, with each BUY proxy and its `/tw-equity-report <code>` command;
- the regime flag, and any gaps: the shortlisted names' `deep.gaps`, the `reconciliation` lists, `funnel.json` `closed_dates`, and the `insufficient_data` count;
- any research files, and the linter outcome or why it was skipped;
- the commit hash and the push result.

## Rules

- Change a rule or parameter only after the user approves: edit the script and its tests, bump `METHODOLOGY_VERSION` in `scripts/history.py`, and add a changelog line to methodology.md. A new factor or threshold must also clear the adoption bar there.
- The tests run offline from the repo root: `python -m unittest discover -s .agents/skills/tw-equity-screener/scripts/tests`.
- Never commit the raw cache.

## Post-Execution Consistency Check

After completing all actions, verify coherence before finalizing (no optimization or feature suggestions):

1. **Unexpected Errors**: No unhandled tool/command errors, skipped required steps, or unrecovered failures occurred (expected graceful fallbacks are normal).
2. **Internal Conflicts**: No instructions, flags, paths, or constraints across frontmatter, `SKILL.md`, `references/`, `scripts/`, or companion files contradicted one another.

If both hold, omit any check output. If either fails, report the exact discrepancy and affected step without modifying skill files.
