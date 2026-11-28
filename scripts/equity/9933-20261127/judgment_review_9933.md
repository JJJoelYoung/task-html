# Judgment review: 9933 CTCI Corporation

A fresh-context subagent reviewed `analysis_9933.json` on 2026-11-28. It was given only `data_9933.json`, `research_9933.md`, `analysis_9933.json`, and `references/judgment-review.md`, and it re-ran every number in Python against the data file. It returned 14 findings. Each is listed below with its disposition.

| # | Check | Item | Finding | Disposition |
|---|---|---|---|---|
| 1 | 2, 1, 9 | `scenarios[*].assumptions`, `earnings_quality.text` | All three cases used the TTM tax rate of 23.49%, which includes 4Q25's one-off 11.19%; the 1-9M26 rate is 27.49%. The text also claimed the 6.33 core baseline excluded that low tax rate, which it does not. | **Fixed.** All cases now use 27.5%, and `valuation_method_basis` says why. EPS falls: Bull 7.70 to 7.34, Base 6.13 to 5.80, Bear 4.22 to 3.82 (with #2 and #3). The earnings-quality text now says the baseline removes only non-operating income and is about 6.0 at 27.5%. |
| 2 | 1, 2 | `scenarios[2].assumptions` | "Revenue stays at TTM, about 900億" was 3.6% above TTM (868.97億). | **Fixed.** Bear revenue is now 869億. |
| 3 | 6 | `scenarios[2]` vs `risks[2]`, `risks[3]` | The Bear target left out both one-off risks, although Base discounted its multiple for them. A repeat BKRF impairment would run through opex, as it did in 1Q25 (opex 36.27億). | **Fixed for BKRF; litigation left out on purpose.** The Bear case now deducts a further 10% BKRF impairment (19.6億, 1.78 per diluted share before tax): 3.82 × 10 = 38.2, less 1.78 = 36.4, which is 9.5x. The two lawsuits stay out of all cases, because their outcome and CTCI's share of the Taipower claim are not disclosed; `risks[3]` says so and gives the maximum per-share hit (7.7). |
| 4 | 5, 8, 3 | `peers`, `valuation_method_basis` | 欣陸 and 中工 overlap with CTCI's plant EPC only thinly, and none of the three peers had a sourced line in the research. The peer PBR median was never addressed. | **Fixed.** Peers are now the fab-facility contractors 亞翔 (6139), 漢唐 (2404) and 帆宣 (6196), sourced to uanalyze 2026-09-06 (backlogs) and 2026-01-27 (亞翔 in Singapore, the Micron phase 2 role). `fetch.py` was re-run with the new peers: the peer median PER is 12.47x and PBR 5.82x. The basis now says that no listed peer runs power-plant EPC, so the peers cover only the high-tech part. It also says the peer PBR is not comparable, because the implied ROE is 25% to 62% for these asset-light firms, so the PBR check uses CTCI's own band. |
| 5 | 8 | `catalysts[2].basis` | It cited udn May ("通霄二期 entering construction") against uanalyze November ("still in design"). | **Fixed.** The catalyst now states both and goes with the newer account; `external_facts` flags the conflict, and the research file lists it as explained. |
| 6 | 8 | `moat[0].text` | "另有" implied that 通霄二期 was outside the 2025 total; 1,547億 is the consortium value; the backlog mix was undated. | **Fixed.** "另有" is removed, the consortium caveat is added ("中鼎份額未揭露"), and the mix is dated end-June 2026. |
| 7 | 3, 1 | `scenarios[1].basis` | The PBR ÷ ROE cross-check mixed undiluted PBR with diluted ROE. | **Fixed.** Both Bull and Base now give undiluted and diluted PBR (diluted BVPS 29.24). Base is 2.08x diluted, below the 2.20x P90; 2.08x ÷ 19.8% matches 10.5x. Bull is 3.14x diluted, below the 3.30x limit (1.5 × P90). |
| 8 | 7, 6 | `thesis_breakers[2]`, `risks[2..3].indicator` | No impairment or litigation-loss line exists in the dataset. | **Fixed.** The indicator is now a computable proxy: quarterly opex (gross profit − operating income) above 26億, or non-operating income below −20億. |
| 9 | 8 | `risks[0].basis` | "Escalation shifts risk rather than lifting margin" was not in the research. | **Fixed.** It is labelled 分析師判斷. |
| 10 | 6 | `risks[3].timing` | "判決時點未知" is not an expected timing. | **Fixed.** It now reads "每季財報附註；下一次為 2026 年報（2027-03-31 前）". |
| 11 | 7 | `thesis_breakers[0]`, foreign-holding levels | The condition ("below the 3Q monthly average", 72.8億) and threshold (70億) disagreed; the foreign-holding risk (25%) and breaker (24%) disagreed. | **Fixed.** The condition now says "跌破 70 億元". The foreign-holding risk and breaker are removed, because `check_report.py` allows at most 5 risks and 3 breakers; dim2 still covers the flows. |
| 12 | 1, 8 | `catalysts[4]`, `scenarios[0]`, `peers[2]` | Three citations did not match their sources. | **Fixed.** The 4,503.5億 backlog is now cited to CTEE, and the 13.40% margin to `data.financials.quarters`. The 亞翔 clause went with the peer change. |
| 13 | 8 | several | Research caveats were dropped: the 49% period, the undated Middle East 13% share, and the single-source diluted EPS. | **Fixed.** "期間未標示" and "單一來源" are added where these figures appear. The 49% period is resolved in the research file: all three sources that state it give 1-3Q26, as the verifiers confirmed. |
| 14 | 6 | `catalysts[3].indicator` | The dividend catalyst had no threshold. | **Fixed.** It now requires a 2026 cash dividend above 0.95 元, the prior year's dividend implied by the 1.76% yield at 54.1. |

The reviewer confirmed every other number against the files: TTM EPS, shares and dilution, ROE, TTM opex and non-operating income, band percentiles and yearly medians, probabilities (20/55/25), the cash-flow and DSI figures, the revenue, margin and flow figures in catalysts and risks, the per-share hits, `has_cb`/`has_spo`, and every external fact against the research file.

Net effect of the fixes:

| Item | Before | After |
|---|---|---|
| Bull target | 96.3 | 91.8 |
| Base target | 64.4 (+19.0%) | 60.9 (+12.6%) |
| Bear target | 42.2 | 36.3 |
| Probability-weighted target | 65.2 | 60.9 |
| Rating | 買進 | 中立 |
| Action | 可分批布局 | 觀望 (fair buy price 53.0, close 54.1) |
| Hold R:R | 0.87 | 0.38 |

The pullback and breakout R:R come from price levels, so they stay at 4.48 and 4.27. The Base multiple stayed at 10.5x. It was set before the review and was not raised to keep the 買進 rating, even though the new peer median (12.47x) is higher.
