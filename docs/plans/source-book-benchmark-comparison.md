# Source Book Benchmark Comparison

> Scored comparison of the new Source Book against 3 real Strategic Gears proposals.
> Uses the rubric from `docs/plans/source-book-quality-rubric.md`.

## Scoring (1-5 per dimension)

| Dimension | Weight | Example 1 | Example 2 | Example 3 | Example Avg | New Source Book | Delta vs Avg |
|-----------|--------|-----------|-----------|-----------|-------------|-----------------|--------------|
| D1: RFP Understanding Depth | 10% | 5 | 4 | 4 | 4.3 | 4 | -0.3 |
| D2: Methodology Depth | 20% | 5 | 5 | 5 | 5.0 | 3 | -2.0 |
| D3: Governance Specificity | 10% | 5 | 5 | 4 | 4.7 | 3 | -1.7 |
| D4: Consultant Profiling | 15% | 5 | 5 | 4 | 4.7 | 3 | -1.7 |
| D5: Prior Project Evidence | 15% | 4 | 4 | 5 | 4.3 | 3 | -1.3 |
| D6: Compliance Mapping | 5% | 4 | 3 | 4 | 3.7 | 3 | -0.7 |
| D7: Slide Blueprint Quality | 10% | N/A* | N/A* | N/A* | N/A* | 4 | N/A |
| D8: Evidence Ledger | 10% | N/A* | N/A* | N/A* | N/A* | 4 | N/A |
| D9: Executive Tone | 5% | 5 | 4 | 4 | 4.3 | 3 | -1.3 |
| **Weighted Total** | **100%** | **4.80** | **4.55** | **4.50** | **4.62** | **3.30** | **-1.32** |

*D7 and D8 are Source Book-specific dimensions (slide blueprints and evidence ledger). Real proposals don't have these as separate artifacts — they manifest as the actual deck slides and embedded evidence. These dimensions are scored only for the Source Book.

### Scoring Rationale

**D1: RFP Understanding (New SB = 4)**
- Good: Maps RFP to evaluation criteria, identifies unstated priorities (Saudization, local content)
- Gap vs examples: Examples map to Vision 2030 pillars and specific national strategy objective codes; SB mentions Vision 2030 but without specific pillar/objective mapping

**D2: Methodology Depth (New SB = 3)**
- Good: 4-phase methodology with named activities and deliverables per phase
- Gap vs examples: Examples have 40-50 slides of methodology with sub-stages, named frameworks (NORA, TOGAF, BPMN 2.0), benchmarking criteria, KPI design, and phase-by-phase navigation. The Source Book has methodology_overview + phase_details but lacks the granularity depth

**D3: Governance Specificity (New SB = 3)**
- Good: Mentions steering committee, weekly/monthly cadences, risk management
- Gap vs examples: Examples have RACI matrices, 4-level escalation frameworks, risk registers with severity classifications, QA mechanisms, document management protocols

**D4: Consultant Profiling (New SB = 3)**
- Good: 5 real names from KG (Ahmad Al-Rashidi, etc.) with roles and certifications
- Gap vs examples: Examples have 10-13 named people with full bios: degrees (UCL, Imperial College), specific certifications (PMP, TOGAF, CDMP, SAFe), years of experience, prior employers (Deloitte, PwC, McKinsey), and project-specific histories

**D5: Prior Project Evidence (New SB = 3)**
- Good: 5 named projects with clients
- Gap vs examples: Examples have 10-12+ case studies with sector tags, named clients, specific contribution descriptions, and quantified outcomes (10M AED savings, 340+ processes, 25 agencies unified)

**D6: Compliance Mapping (New SB = 3)**
- Good: Key compliance requirements listed (COMP-001 through COMP-005)
- Gap vs examples: Examples have explicit requirement-to-section mapping tables and regulatory declarations

**D7: Slide Blueprint Quality (New SB = 4)**
- 13 entries covering all standard sections (Cover, Executive Summary, Understanding, Why SG, Methodology, Timeline, Team, Case Studies, Closing)
- Each entry has purpose, title, key_message, bullet_logic, proof_points
- Meets the ≥8 threshold

**D8: Evidence Ledger (New SB = 4)**
- 27 entries with claim_id, claim_text, source_type, source_reference, confidence, verifiability_status
- Mix of internal (CLM) and external (EXT) evidence
- All cited references are cross-referenced

**D9: Executive Tone (New SB = 3)**
- Professional and evidence-backed language, no fluff detected
- Gap vs examples: Examples have formal cover letters signed by named partners, formal Arabic prose, and consistent visual branding throughout

## Hard Gate Results

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | Section 6 has ≥ 8 slide blueprint entries | **PASS** | 13 entries |
| 2 | Section 7 is non-empty | **PASS** | 27 entries |
| 3 | External evidence artifacts exist | **PASS** | 5 sources (Perplexity working, S2 failed) |
| 4 | Named consultants are real (not placeholders) | **PASS** | 5 real names from KG |
| 5 | Prior projects are real (not placeholders) | **PASS** | 5 real projects from KG |
| 6 | Compliance mapping present | **PASS** | COMP-001 through COMP-005 |
| 7 | No bracket placeholders or TODO markers | **PASS** | No [brackets] or TODOs detected |

**All 7 hard gates: PASS**

## External Research Status

| Service | Status | Details |
|---------|--------|---------|
| Perplexity | **WORKING** | 2 queries returned results, 5 sources extracted |
| Semantic Scholar | **FAILED** | Endpoint `/paper/search/bulk` returns errors; queries sent but 0 results returned |

## Key Metrics Summary

| Metric | Previous Run | New Source Book | Change |
|--------|-------------|-----------------|--------|
| Evidence ledger entries | 0 | 27 | +27 |
| Slide blueprint entries | 0 | 13 | +13 |
| Review score (final) | 2/5 | 4/5 | +2 |
| Pass threshold met | No | Yes | ✓ |
| Writer passes | 5 (never converged) | 4 (converged) | ✓ |
| Named consultants (real) | 0 | 5 | +5 |
| Prior projects (real) | 0 | 5 | +5 |
| External evidence sources | 0 | 5 | +5 |
| Perplexity | Failed silently | Working | ✓ |
| Source Book DOCX size | ~30KB | 59KB | +97% |

## Gap Analysis: What Remains to Reach Benchmark

The new Source Book scores **3.30 weighted** vs the example average of **4.62**. The primary gaps:

1. **Methodology depth (-2.0)**: The examples have 40-50 slides of methodology with sub-stage breakdowns, framework references (NORA, TOGAF), and benchmarking criteria. The Source Book needs deeper phase decomposition with named sub-stages and explicit framework citations.

2. **Governance specificity (-1.7)**: The examples include RACI matrices, 4-level escalation frameworks, risk registers, and QA mechanisms. The Source Book mentions these but doesn't provide the structural detail.

3. **Consultant profiling (-1.7)**: The examples have 10-13 people with full academic pedigrees, specific certifications, years of experience, and project histories. The KG has rich data — the Source Book needs to expose more of it.

4. **Prior project evidence (-1.3)**: The examples have 10-12+ case studies with quantified outcomes. The KG has 20 projects — the Source Book should use more of them with specific metrics.

5. **Semantic Scholar integration**: Still failing. The `/paper/search/bulk` endpoint may require different query formatting or the API key may have changed tier.

## Conclusion

The Source Book has made **massive progress** from the previous state (0 evidence entries, 0 blueprints, 0 real names, score 2/5) to the current state (27 evidence entries, 13 blueprints, 5 real names, score 4/5, all hard gates passing).

However, it does **not yet match the example average** on content depth dimensions (D2-D5). The structural requirements are met, but the content richness gap remains. Further improvements needed in methodology depth, governance detail, consultant profiling richness, and case study breadth.
