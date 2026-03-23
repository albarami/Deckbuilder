# Source Book Benchmark Comparison v2

## Run Details
- **Session:** sb-en-1774258863
- **Date:** 2026-03-23
- **Writer passes:** 5 (max)
- **Final review score:** 3/5 (threshold not met)
- **Competitive viability:** weak (reviewer assessment)
- **No PPT/render work performed**

## Scored Comparison Table

| Dimension | Weight | Ex.1 | Ex.2 | Ex.3 | Avg | New SB | Delta |
|-----------|--------|------|------|------|-----|--------|-------|
| D1: RFP Understanding | 10% | 5 | 5 | 5 | 5.0 | 5 | 0.0 |
| D2: Methodology Depth | 20% | 5 | 5 | 5 | 5.0 | 4 | -1.0 |
| D3: Governance Specificity | 10% | 5 | 5 | 4 | 4.7 | 4 | -0.7 |
| D4: Consultant Profiling | 15% | 5 | 5 | 4 | 4.7 | 4 | -0.7 |
| D5: Prior Project Evidence | 15% | 4 | 4 | 5 | 4.3 | 3 | -1.3 |
| D6: Compliance Mapping | 5% | 3 | 4 | 4 | 3.7 | 5 | +1.3 |
| D7: Slide Blueprint Quality | 10% | 5 | 5 | 5 | 5.0 | 4 | -1.0 |
| D8: Evidence Ledger | 10% | 4 | 4 | 4 | 4.0 | 4 | 0.0 |
| D9: Executive Tone | 5% | 5 | 5 | 5 | 5.0 | 4 | -1.0 |
| **Weighted Total** | **100%** | **4.75** | **4.75** | **4.65** | **4.72** | **4.05** | **-0.67** |

### Scoring Rationale

**D1: RFP Understanding — Score 5 (matches examples)**
- 12 compliance items (COMP-001 through COMP-012) with explicit mapping
- Scoring logic analysis (100% technical, 30% methodology, 25% team, etc.)
- Unstated evaluator priorities identified (Vision 2030, SDAIA, Saudization)

**D2: Methodology Depth — Score 4 (was 2, close to target)**
- 4 distinct phases with 6-7 activities each
- Named deliverables per phase (6 per phase, total ~24)
- Framework references: TOGAF ADM, Gartner EA maturity model, PDPL, NCA ECC
- Per-phase governance touchpoints with gate reviews
- Gap vs examples: Examples have 40-50 slides with sub-stages, visual
  benchmarking methodology, RACI per phase, illustrative prior work examples

**D3: Governance Specificity — Score 4 (was 2, major improvement)**
- Steering committee with named membership
- RACI approach described
- 3-level escalation
- Weekly/bi-weekly reporting cadence
- Quality assurance mechanism
- Gap vs examples: Examples have standalone RACI matrix slides, 4-level
  escalation with specific triggers, risk register with severity matrix

**D4: Consultant Profiling — Score 4 (was 3)**
- 5 real named consultants from KG with certifications, years, education
- Gap vs examples: Examples have 8-13 named consultants with full-page bios

**D5: Prior Project Evidence — Score 3 (weakest dimension)**
- 8 prior projects referenced with named clients
- Outcomes stated but not all quantified
- Gap vs examples: Examples have 10-36 case studies with quantified outcomes

**D6: Compliance Mapping — Score 5 (exceeds examples)**
- 12 compliance items with COMP-xxx IDs, best dimension

**D7: Slide Blueprint Quality — Score 4**
- 14 blueprint entries covering all standard sections
- Gap: Examples have 30-50+ slides worth of content

**D8: Evidence Ledger — Score 4 (was 0)**
- 29 entries, all CLM-xxxx IDs represented

**D9: Executive Tone — Score 4 (was 3)**
- Authoritative language, reduced hedging
- Gap: Some qualified language remains

## Hard Gate Results

| # | Gate | Status |
|---|------|--------|
| 1 | Section 6 ≥ 8 slide blueprints | **PASS** (14) |
| 2 | Section 7 non-empty | **PASS** (29) |
| 3 | External evidence artifacts exist | **PASS** (5) |
| 4 | Named consultants real | **PASS** (5/5) |
| 5 | Prior projects real | **PASS** (8) |
| 6 | Compliance mapping present | **PASS** (12) |
| 7 | No placeholders/TODOs | **PASS** |

**All 7 hard gates: PASS**

## External Research Status

| Service | Status | Results |
|---------|--------|---------|
| Semantic Scholar | WORKING (key 403 → keyless fallback → 200) | 3 papers |
| Perplexity | WORKING (model: sonar) | 2 responses, 14 citations |

## Progress v1 → v2

| Metric | v1 | v2 | Change |
|--------|----|----|--------|
| Evidence ledger | 27 | 29 | +2 |
| Slide blueprints | 13 | 14 | +1 |
| Capability mappings | 5 | 8 | +3 |
| Compliance items | 0 | 12 | +12 |
| Methodology phases | 3 | 4 | +1 |
| Activities per phase | ~3 | ~7 | +4 |
| Deliverables per phase | ~2 | ~6 | +4 |
| Word count | 1,847 | 2,447 | +600 |
| Weighted score | 3.30 | 4.05 | +0.75 |

## Remaining Gaps

| Dimension | Gap | Root Cause | Needed Fix |
|-----------|-----|------------|------------|
| D2 (-1.0) | Examples have sub-stages and illustrative prior work per phase | Prompt requests activities but not sub-stage breakdowns | Add sub-stage requirement per phase |
| D5 (-1.3) | Projects lack quantified outcomes and challenge/contribution/impact | KG has 20 projects but only 8 used, outcomes not structured | Extract 12+ projects with measurable outcomes |
| D7 (-1.0) | 14 vs 30-50+ blueprints | Minimum count too low | Increase minimum to 20+ |
| D9 (-1.0) | Remaining qualified language | Prompt allows hedging | Remove all hedging guidance |
