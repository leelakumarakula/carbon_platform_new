# Carbon methodologies — executive brief

## Summary
The platform can calculate carbon credits under **9 methodologies** from **3 standards** — Verra, Gold Standard and India's Carbon
Credit Trading Scheme (CCTS) — covering **soil carbon on cropland, paddy rice, trees on farms, plantations and mangroves, and biochar**.
All 13 calculation variants are built and pass their automated tests, and the full soil-carbon flow has been run end to end on test data.
**None is approved for live credits yet**: each needs a review by a qualified methodology expert before real projects use it.

**Recommendation:** use **Verra VM0042** for our soil-sampling cropland projects, and start the expert review with VM0042.

---

## What a methodology is, and why it matters
A methodology is the official rulebook of a carbon standard for one type of project. It decides **which projects qualify**, **what is
counted**, **which equations and factors are used** and **what must be monitored**. Credits are only issued if the calculation follows the
methodology exactly, as checked by an independent verifier (VVB). Each project uses **one methodology for its whole life**.

## What the platform supports
| Project type | Methodology | Standard | Credit | How carbon is measured |
|---|---|---|---|---|
| **Cropland practice change** (reduced tillage, residue mulching, cover crops, nutrient management) | **VM0042 v2.2** | Verra | VCU | Soil sampled twice and laboratory-analysed, compared with control farms |
| Cropland practice change — Gold Standard (5 variants) | GS 402 v1.0 | Gold Standard | GS VER | Soil sampled twice, **or** IPCC default factors without sampling |
| **Paddy rice** — water saving, straw management | VM0051 v1.1 | Verra | VCU | Methane from field records and IPCC factors |
| Paddy rice — Indian compliance market | BM AG04.002 v1.0 | India CCTS | CCC | Methane from IPCC default values |
| **Trees on farmland** (≤ 50 per hectare) | VM0047 v1.1 | Verra | VCU | Tree census and sampled tree measurements |
| Plantations / reforestation | GS 403 v2.1 | Gold Standard | GS VER | Forest inventory plots |
| Plantations / reforestation — India | BM FR05.002 v1.0 | India CCTS | CCC | Forest inventory plots |
| Mangrove restoration — India | BM FR05.001 v1.0 | India CCTS | CCC | Forest inventory plots |
| **Biochar** from crop residue | VM0044 v1.2 | Verra | VCU | Biochar quantity and laboratory analysis |

## Where we stand
| Area | Status |
|---|---|
| Calculation modules | **13 built** (9 methodologies; GS 402 has 5 variants), each implementing the official equations with references |
| Automated testing | **34 tests passing** — every module checked against an independent hand calculation |
| End-to-end testing | Soil-carbon flow run in the test environment from farmer registration to calculated credits (VM0042: about **950 credits** on a 100-hectare test farm; GS 402 also run) |
| Approval for live credits | **Not yet — "not production ready" for all 13** |
| Safeguards | One locked methodology per project; land-overlap checks; one registry submission per period; issued credits capped at the verified amount; duplicate-serial checks; every approval by a second person and fully audited |

**What "not production ready" means:** the calculations are built and tested, but a qualified methodology expert must confirm that each
one matches the official methodology text, including the interpretations the code makes where the text is ambiguous. Until that review is
recorded in the platform, the calculation runs in testing only and is **blocked in the live system**. This protects us from issuing credits
that a verifier could later reject.

## Which methodology for our projects
| Our situation | Recommended |
|---|---|
| Farms where we take soil samples and can find comparable control farms | **VM0042** (Verra) — our main choice; tested end to end |
| Farms where we take soil samples but have no control farms | GS 402 measured variant (Gold Standard) |
| Smallholder or pilot projects without soil sampling | GS 402 default-factor variant — simpler and cheaper, but more conservative credits |
| Paddy rice farmers adopting water saving | VM0051 (voluntary market) or BM AG04.002 (Indian compliance market) |
| Tree planting on farm boundaries | VM0047 |

## Decisions and risks
| # | Item | Why it matters | Owner |
|---|---|---|---|
| 1 | **Engage a methodology expert** to review VM0042 first, then the other modules we plan to use | Required before any live credits | Management |
| 2 | **Write the eligibility (applicability) rules** for each methodology from the official text | The platform checks projects against these; they are not supplied with the software | Methodology expert |
| 3 | **Electricity in VM0042** — confirm whether electricity use (e.g. electric irrigation pumps) must be counted | If required, a small addition to the calculation | Methodology expert |
| 4 | **Choose the standard per project** (Verra, Gold Standard or CCTS) before starting | One project = one methodology; prevents double counting | Management |
| 5 | **Field and laboratory capacity** for VM0042 | Each sampling round needs 3+ points per zone, 2 soil layers per point and 2 lab tests per sample; at least 3 control farms per project | Operations |
| 6 | Methodology versions change over time | A new version (e.g. VM0042 v2.3) needs a new calculation module | Product / development |

## Next steps
1. Approve engaging a methodology expert for the VM0042 review.
2. Confirm the standard and methodology for the first live project.
3. Expert writes the eligibility rules and answers the electricity question.
4. Record the production-readiness approval for VM0042 in the platform.
5. Run the first live project; repeat the review for the next methodology we need.

---

**Further reading**
- [methodologies-guide.md](methodologies-guide.md) — plain-language explanation of each methodology and how the platform calculates it.
- [methodologies-reference.md](methodologies-reference.md) — technical reference: every rule, input, factor and output (for the expert reviewer).
