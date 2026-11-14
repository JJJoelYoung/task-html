# Judgment Review — 2308 台達電 (2026-11-13)

Reviewer: Independent `research` subagent (`d2c4505b-0620-41d9-b630-4c95b756b111`) following `references/judgment-review.md` across all 9 checks.

## Findings & Disposition

1. **Check 8 & Check 1 — `moat[1].text`, `moat[1].basis`, `peers[2].basis`, `catalysts[2].basis` (Liquid cooling revenue share ~13% vs. verified >12%)**
   - **Finding**: `analysis_2308.json` cited liquid cooling share as `約 13%`, which only appeared in the refuted/period-disputed note of `research_2308.md` (line 38) rather than `## Facts`, whereas `research_2308.md` line 31 (`口袋學堂 2026-08-10`) verified `liquid cooling >12% vs. ~10% in 2025` and `Infrastructure order visibility extends through 2027`.
   - **Disposition**: **Fixed.** Updated `peers[2].basis`, `moat[1].text`, `moat[1].basis`, `catalysts[2].basis`, and `external_facts[6]` to cite the verified `>12%` (`逾 12%`) liquid cooling share and 2027 Infrastructure order visibility from `口袋學堂 2026-08-10` (`https://www.pocket.tw/school/articles/7760/`).

2. **Check 1 & Check 8 — `scenarios.Bull.basis` (Per-brokerage 2027E EPS breakdown)**
   - **Finding**: `scenarios.Bull.basis` listed individual brokerage 2027E EPS numbers (`凱基 66.29 元、富邦 64.56 元、國泰 62.28 元`), whereas `research_2308.md` line 32 only recorded the aggregate range `NT$62.28–NT$66.29`.
   - **Disposition**: **Fixed.** Updated `scenarios.Bull.basis` to cite the verified aggregate range `62.28 至 66.29 元` (midpoint `64.29 元`) from `口袋學堂 2026-08-10`.

3. **Check 8 & Check 1 — `external_facts[2]`, `risks[1].basis`, `risks[0].basis`, `peers[0].basis` (Source attribution alignment)**
   - **Finding**:
     1. Q3 2026 Power Electronics (`1,059.3 億元`) and Infrastructure (`658.8 億元`) figures were placed in `external_facts[2]` (`3Q26_Analyst%20Meeting.pdf`) instead of `external_facts[1]` (`BigGo 財經 / 台達電 2026Q3 法人說明會`), and 9M 2026 Mobility cumulative operating loss (`12.67 億元`) was cited in `risks[1].basis` without appearing in `external_facts[2]`.
     2. August 2026 revenue `月減 3.7%` in `risks[0].basis` was attributed to `工商時報 2026-09-19` instead of `data.revenue.last12`.
     3. `peers[0].basis` cited `工商時報 2026-10-07` alongside `口袋學堂 2026-08-10` for Lite-On (`2301`).
   - **Disposition**: **Fixed.** Moved Q3 2026 Power Electronics and Infrastructure segment figures into `external_facts[1]`, added 9M 2026 Mobility cumulative operating loss (`12.67 億元`) to `external_facts[2]`, cited `data.revenue.last12` for August `月減 3.7%` in `risks[0].basis`, and kept `口袋學堂 2026-08-10` as the sole external citation in `peers[0].basis`.

4. **Check 6 — `risks[3]` and `scenarios.Bear.assumptions` (Year-end intangible asset impairment alignment)**
   - **Finding**: `risks[3]` included year-end intangible asset / goodwill impairment review as an earnings risk, which was not explicitly mentioned in `scenarios.Bear.assumptions`.
   - **Disposition**: **Fixed.** Added year-end intangible asset and goodwill impairment review (`年底無形資產與商譽減損評估`) to `scenarios.Bear.assumptions` and `scenarios.Bear.basis`.

findings: 4 (4 fixed, 0 rejected)
