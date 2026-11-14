# Judgment Review

Brief for the fresh-context subagent that reviews `analysis_{code}.json` before the report is generated. You did not write the analysis; your job is to find where it is wrong, unsupported, or inconsistent with the data. Read-only: change no file.

## Inputs

- `data_{code}.json`: FinMind data and computed metrics, the only source of market and financial numbers.
- `research_{code}.md`: external facts, each with source, date, and URL.
- `analysis_{code}.json`: the judgments under review. Each item has a `basis`.
- [methodology.md](methodology.md) sections 6 and 7: the valuation and trade-setup rules.

## Checks

Apply every check to every item it covers.

1. **Cited numbers.** Every number in a `basis`, assumption, or comment appears in the data or research file with the same value, period, and unit. A number found in neither is a finding.
2. **Forward EPS (or BVPS).** For each scenario, compute the growth it implies over TTM EPS (or the latest BVPS) and compare it with the last 4 quarters, the latest quarter annualized, gross and operating margin trends, and monthly revenue YoY. A Base that needs a turn the data does not yet show must name the external fact that supports it.
3. **Multiples.** Bear ≤ P25, Base within P25–P75, Bull ≤ P90 of the method's band, or a `basis` that cites the percentile and justifies it. Compute each target's implied cross multiple (PER method: target / BVPS; PBR method: target / TTM EPS); a Base above that band's P90 or a Bull above 1.5 × P90 needs a `basis` naming the metric.
4. **Probabilities.** Whole numbers summing to 100, and consistent with the evidence: a Bull more likely than Base needs a reason.
5. **Peers.** Each of the 3 competes directly with the target's main business, not as a customer, supplier, or supply-chain neighbour.
6. **Catalysts and risks.** Each has an expected timing, a direction of impact, and an indicator that can be observed in data or a dated announcement. Each risk that would move the Bear case is reflected in the Bear assumptions.
7. **Thesis breakers.** Each has a numeric threshold and names the dataset that would show it.
8. **External facts.** Every fact used appears in `research_{code}.md` with the same claim and URL, and none rests on a claim the research file lists as refuted or conflicting without saying so.
9. **Earnings quality.** The commentary addresses the industry focus in methodology section 4, using the data file's DSI and cash conversion.

## Output

Return a Markdown list, most consequential first. Each finding gives: the check number, the item (for example `scenarios.Base.eps`), what is wrong with the evidence from the files, and the fix. End with one line: `findings: <n>` and, if there are none, `no findings` after confirming all 9 checks ran on every item.
