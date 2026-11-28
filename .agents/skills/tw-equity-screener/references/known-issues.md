# Known Issues

Open defects and gaps in `tw-equity-screener`, kept here so they can be scheduled and fixed. The final code review of 2026-11-25 (commits `ab378ab..fbca79a`) found them. Its blocking findings I1, I2, I3, and I5 were fixed in `2b1fbb5`. Everything below is still open.

**Using this file:**
- Each entry names the function, not a line number, because line numbers drift.
- "Changes output: yes" means the fix changes scores, lists, or statistics. Such a fix needs the user's approval, a `METHODOLOGY_VERSION` bump in `scripts/history.py`, and a changelog line in [methodology.md](methodology.md) (SKILL.md, Rules).
- When an issue is fixed, delete its entry and give the commit in the changelog or the commit message. When a new one is found, add it with the next free number.

## Deadlines

| ID | Due | Why |
| --- | --- | --- |
| I4 | before about 2027-11 (week 52) | Forward stats turn into a rolling window of about 56 weeks. |
| D1 | before about 2027-05 (week 26) | The persistence-group review in methodology section 10 needs a way to measure it. |
| M12 | before relying on BUY conversion (about week 4) | It double-counts names and rewrites past conversions. |
| M5 | during the first live run | Memory use is close to 2 GB. |

## Index

| ID | Area | Summary | Priority | Changes output |
| --- | --- | --- | --- | --- |
| I4 | forward stats | Only cohorts inside the 270-date panel are priced. | deadline | yes |
| D1 | validation | There is no measure of each group's forward contribution. | deadline | no (new tool) |
| M1 | data integrity | Only the PER tables are date-checked. | cheap polish | no |
| M2 | universe events | Emerging-to-listed moves (most IPOs) count as transfers. | cheap polish | yes |
| M3 | portal | Rendering an older week points the portal and README back to it. | cheap polish | no |
| M4 | history | A rerun deletes review.json and the research files. | cheap polish | no |
| M5 | memory | The price panel holds about 1.8 GB. | watch | no |
| M6 | factors | Price factors use unadjusted closes. | methodology | yes |
| M7 | watch track | Long-suspended old stocks show as new listings. | normal | yes |
| M8 | network | Connection resets during `read()` are not retried. | cheap polish | no |
| M9 | MOPS | A failed refresh exits 3 even when a cached copy exists. | normal | no |
| M10 | imports | The report scripts can shadow screener modules. | low | no |
| M11 | page | The Tier A row omits the BUY proxy inputs. | normal | no |
| M12 | forward stats | `buy_conversion` double-counts and rewrites the past. | deadline | yes |
| M13 | page | The L2 note omits two of its rules. | low | no |
| M14 | run timing | A Friday-afternoon run keeps exiting 3. | normal | no |
| M15 | point in time | The MOPS refresh keys on asof, so later data leaks into past weeks. | normal | yes |
| M16 | history | A skipped week does not reset streaks. | low | yes |
| M17 | page | The page omits composite delta and each code's latest report. | cheap polish | no |
| M18 | tests | No end-to-end test covers a board transfer between two weeks. | normal | no |
| M19 | cache | Nothing ever prunes the raw cache, so it grows about 5-8 MB a week. | normal | no |
| M20 | MOPS | A throttle page during a cold backfill exits 3 as "not published". | normal | no |

## Deferred with a deadline

### I4. Forward stats only price cohorts inside the panel

- **Where:** `scripts/run.py` builds the forward prices through `PanelLookup`. `scripts/history.py` `forward_stats` uses them.
- **Effect:** a cohort whose TAIEX close at either end falls outside the 270-date panel is skipped. Every horizon becomes a rolling window of about 56 weeks, and the 52-week row holds only 2 or 3 cohorts. Nothing differs before about week 52 (2027-11). Methodology section 9 states the limit, and the page shows each row's cohort count.
- **Fix:** price closes outside the panel from the exchanges' past daily tables, through the cache. `forward.csv` already keeps every entry close, so no data is lost.

### D1. No per-group forward contribution measure

- **Where:** nothing exists yet. Methodology section 10 says to review the persistence group after 26 weeks.
- **Effect:** when that review falls due (about 2027-05), there will be no tool to run it.
- **Fix:** add a script that measures each group's contribution to forward excess return, for example by the rank IC of each `g_<group>` column in `scores.csv` against forward returns. Report it with the forward stats.

## Minor issues

### M1. Only the PER tables are date-checked

- **Where:** `scripts/exchange.py` `fetch_day`. Only the PER tables pass through `_dated`.
- **Effect:** if MI_INDEX, T86, MI_QFIIS, or a TPEx quotes or institutional table answers for a different day, it is cached under the requested date. Every later run then reuses the wrong data.
- **Fix:** check the top-level date of every daily payload with `_dated` before caching it.

### M2. Emerging-to-listed moves count as transfers

- **Where:** `scripts/universe.py` `events`, and `scripts/render.py` `sec_changes`.
- **Effect:** almost every Taiwan IPO lists by moving from the Emerging board (興櫃) to TWSE or TPEx. So 新上市櫃 counts mostly new Emerging registrations, and the real IPOs appear under 轉板. The page shows only counts, with no names.
- **Fix:** treat Emerging → TWSE or TPEx as a listing event, and show the names. Update the transfer definition in methodology section 9.

### M3. Rendering an older week repoints the portal

- **Where:** `scripts/render.py` `main`, through `upsert_card` and `upsert_readme`.
- **Effect:** re-rendering or backfilling an older week points the `index.html` card and the README row at that week instead of the newest one.
- **Fix:** update the card and the README row only when the folder is the newest week under `scripts/screens/`.

### M4. A rerun deletes review.json and the research files

- **Where:** `scripts/history.py` `write_week`, which replaces the whole week folder. SKILL.md tells the user to move these files aside first.
- **Effect:** `review.json`, `sector_research.md`, and `research_{code}.md` are lost. The research files are the most token-expensive output of the workflow.
- **Fix:** copy the files that `run.py` does not compute from the old folder into the staging folder before the swap. Then drop the warning from SKILL.md.

### M5. The price panel uses about 1.8 GB of memory

- **Where:** `scripts/exchange.py` `fetch_day`, and `scripts/run.py` Step 2, which keeps every day.
- **Effect:** each day keeps about 15,200 quote rows, warrants included. The probe measured about 6.8 MB a day, or about 1.8 GB over 270 dates. A machine short on memory may fail the backfill.
- **Fix:** keep only master codes and the TAIEX in each day. Do this if the first live run nears 2 GB.

### M6. Price factors use unadjusted closes

- **Where:** `scripts/factors.py` `momentum_6_1`, `persistence`, and the `ret13w` calculation in `stock_factors`.
- **Effect:** a capital reduction (減資) or a rights issue fakes a return of tens of percent, up or down. Ex-dividend days bias these returns against high-yield names.
- **Fix:** keep the quote's 漲跌價差 cell, since close minus change gives the day's reference price, and chain an adjustment factor from it. A cheaper option is to flag names with an ex-rights event in the window.

### M7. Long-suspended old stocks show as new listings

- **Where:** `scripts/watch.py` `watch_tables` (the `recent` table), and `scripts/render.py` `sec_watch`.
- **Effect:** `recent` holds every TWSE or TPEx stock that is not on the full track. So an old stock with a long trading gap shows under 新上市櫃 with `days_to_full` 120.
- **Fix:** filter `recent` by listing date, and show suspended stocks separately or not at all.

### M8. Connection resets during read() are not retried

- **Where:** `scripts/cache.py` `Fetcher.get` and `Fetcher._request`.
- **Effect:** retries cover only HTTP 5xx, `URLError`, and `TimeoutError`. A `ConnectionResetError` or `http.client.IncompleteRead` while reading the body ends a backfill with a traceback, and a `UnicodeDecodeError` does not become a `NoDataError`. A rerun resumes from the cache.
- **Fix:** add both read errors to the retried set, and turn a decode failure into a `NoDataError`.

### M9. A failed MOPS refresh exits 3 despite a cached copy

- **Where:** `scripts/mops.py` `fetch_revenue` and `fetch_income`.
- **Effect:** when a refresh fails validation, for example on a MOPS throttle page, the whole run exits 3 even though an older cached copy of the page exists.
- **Fix:** fall back to the cached copy and record a gap in the week's output.

### M10. The report scripts can shadow screener modules

- **Where:** `scripts/shared.py`, which runs `sys.path.insert(0, REPORT_SCRIPTS)`.
- **Effect:** none today. A future module in `tw-equity-report/scripts/` with the same name as a screener module would silently replace it.
- **Fix:** load the report modules with `importlib` under their own names instead of changing `sys.path`.

### M11. The Tier A row omits the BUY proxy inputs

- **Where:** `scripts/render.py` `sec_tier_a`.
- **Effect:** the page shows the BUY proxy but not its inputs: NTM EPS, the 5-year PER P50, and the close. The reader cannot check the number before spending a `/tw-equity-report` run, and the spec 4.9 handoff asks for them.
- **Fix:** add the three columns from the `shortlist.json` deep metrics.

### M12. buy_conversion double-counts and rewrites the past

- **Where:** `scripts/history.py` `buy_conversion`.
- **Effect:** it counts (week, code) rows and uses only the newest report for each code. A name that stays in Tier A for five weeks counts five times. A later 中立 report also rewrites the earlier conversions. This skews the primary validation metric.
- **Fix:** count distinct codes per cohort, and match each one to the first report dated on or after its Tier A week's asof.

### M13. The L2 note omits two of its rules

- **Where:** `scripts/render.py`, the L2 row of the funnel ladder labels.
- **Effect:** the note says only 排除金融保險、營業虧損. It leaves out the non-general-template rule and the `no_income` rule, so exclusions such as 1409 go unexplained on the page.
- **Fix:** add both rules to the L2 note, and update [page-contract.md](page-contract.md) if it quotes the text.

### M14. A Friday-afternoon run keeps exiting 3

- **Where:** `scripts/exchange.py` `resolve_asof`, which checks only MI_INDEX.
- **Effect:** a run on Friday afternoon resolves asof to that Friday, then exits 3 until T86, MI_QFIIS, and the PER tables are out.
- **Fix:** have `resolve_asof` require every daily table, or state a safe run time in SKILL.md (Saturday works today).

### M15. Later data leaks into past weeks

- **Where:** the refresh rule in `scripts/mops.py` `fetch_revenue` and `fetch_income`, and the ISIN and snapshot caching in `scripts/run.py`.
- **Effect:** there are two leaks.
  - The refresh rule keys on asof, not today. Rerunning an old asof fetches today's MOPS pages, so companies that filed later leak into a past week.
  - A weekday-morning live run caches today's ISIN lists and snapshots under the previous trading day's key.
- **Fix:** key the refresh rule on the fetch date, and keep the fetch date with each cached page. Cache the ISIN lists and snapshots under the date they were fetched, and read the newest copy fetched on or before the run's cutoff.

### M16. A skipped week does not reset streaks

- **Where:** `scripts/history.py` `previous_week` and `diff`.
- **Effect:** streaks and rank deltas compare against the latest existing folder. After a skipped week, a name continues its streak as if it had appeared in the missing week.
- **Fix:** reset streaks when the previous folder is not the immediately preceding ISO week, or count the gap as a break.

### M17. The page omits composite delta and each code's latest report

- **Where:** `scripts/render.py` `sec_shortlist` and `sec_changes`. `diff.json` already has `composite_delta` and `reports`.
- **Effect:** the plan's page hooks name composite delta as a signed figure, and spec 4.7 says to show each shortlisted code's latest rating and action. Without them, the reader cannot see which Tier A names already have a recent report.
- **Fix:** render both, and add them to [page-contract.md](page-contract.md) and `check_screen.py`.

### M18. No test covers a board transfer between two weeks

- **Where:** `scripts/tests/test_run.py`.
- **Effect:** the transfer path through `universe.events`, `status_changes`, and the invariants is tested only in unit tests. A regression in how `run.py` joins them would go unnoticed.
- **Fix:** add an end-to-end test where one code moves from TPEx to TWSE between two runs. Assert one transfer, no exit or listing, and passing invariants. If M2 lands first, add an Emerging-to-listed case as well.

### M19. Nothing ever prunes the raw cache

- **Where:** `scripts/cache.py` `Fetcher`, and `scripts/shortlist.py` `deep_metrics`. Neither deletes old entries. The cache lives at `TW_SCREENER_CACHE`, or `~/.cache/tw-equity-screener` by default.
- **Effect:** the cache grows without limit. The estimates below come from the sizes of live sample files:
  - the first backfill writes about 100-150 MB of exchange daily tables;
  - each later week adds about 2-3 MB of daily tables, about 1 MB of ISIN lists and OpenAPI snapshots, and up to 4 MB of FinMind deep metrics (up to 40 names at about 100 KB each).
  - That is about 5-8 MB a week, or 300-400 MB a year.
  - Daily tables older than the 270-date panel are never read again. ISIN lists, snapshots, and deep metrics are read again only to rerun their week.
  - MOPS pages are keyed by month or quarter, and a refresh overwrites them, so they stay bounded.
- **Fix:** add a prune step that runs after a successful run.
  - Keep the daily tables inside the 270-date window, and keep the TAIEX close of every date, which the I4 fix needs.
  - Keep the ISIN lists, snapshots, and `finmind/{asof}/` folders for the latest N weeks. Deleting them makes a rerun of that week exit 4, so choose N, and print what was pruned.
  - Set N after the first live run shows real sizes.

### M20. A MOPS throttle page during a backfill exits 3 as "not published"

- **Where:** `scripts/cache.py` `Fetcher.get`, which raises `NoDataError` when a page fails validation, and `scripts/run.py` `main`, which reports every `NoDataError` as exit 3.
- **Effect:** the first live backfill (2026-11-28) exited 3 on `rev_sii_0/2026-09` after about 115 MOPS requests, although that month had been out since October. A manual fetch of the same URL moments later returned the full table. MOPS had served a throttle page, and nothing backs off and retries it. A rerun resumes from the cache.
- **Fix:** for MOPS months and seasons whose publication date has passed, treat a failed validation as a throttle: wait and retry with backoff, and if it still fails, exit with a message that names throttling, not "not published".
