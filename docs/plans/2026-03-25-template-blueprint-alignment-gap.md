# Template-Blueprint Alignment Gap Analysis

## Scope and Inputs
- Template audited: `PROPOSAL_TEMPLATE/PROPOSAL_TEMPLATE EN.potx`
- Blueprint audited: `output/sb-en-1774372965/slide_blueprint_from_source_book.json`
- Audit type: **analysis only** (no prompt/code/filler/manifest changes)

---

## 1) Canonical Template Map (Every Slide)

| slide | section | layout | type | required? | repeatability | ownership | preview |
|---:|---|---|---|---|---|---|---|
| 1 | Proposal Shell | Proposal Cover | cover | required | fixed | hybrid |  |
| 2 | Introduction Message | Introduction Message | content | required | fixed | dynamic | Introduction Message |
| 3 | Table of Contents | ToC / Agenda | content | required | fixed | hybrid | Table of contents  /  Introduction and Our Understanding of the Project  /  04  /  Why Strategic Gears  /  09  /  Methodology  / |
| 4 | Section Divider: Introduction & Understanding | 01 | divider | required | fixed | hybrid | Introduction and Our Understanding of the Project |
| 5 | Understanding of Project | KSA | content | required | fixed | dynamic |  |
| 6 | Understanding of Project | Pillars of the Vision | content | required | fixed | dynamic |  |
| 7 | Understanding of Project | Vision Realization Programs Numbers | content | required | fixed | dynamic |  |
| 8 | Understanding of Project | Vision Realization Programs | content | required | fixed | dynamic |  |
| 9 | Section Divider: Why Strategic Gears | 02 | divider | required | fixed | hybrid | Why Strategic Gears |
| 10 | Why Strategic Gears (Evidence Case) | Services - Detailed Case | case-study | required | fixed | dynamic | Tadawul  /  Project: Understanding Investor Behaviors and Motivations  /  Contribution:  /  The research process was conducted in |
| 11 | Section Divider: Methodology | 03 | divider | required | fixed | hybrid | Methodology  /  Provision of Consulting Services for the Film Sector |
| 12 | Methodology | Methodology -3- Overview of Phases | content | required | fixed | dynamic | Provide progress reports for the initiative.  /  Support data analysis efforts to track and assess the performance of the Film Sec |
| 13 | Methodology | Methdology -3- Focused Phase | content | required | fixed | dynamic | Provide progress reports for the initiative.  /  Support data analysis efforts to track and assess the performance of the Film Sec |
| 14 | Methodology | Methodolgy - Detailed Phase | content | required | fixed | dynamic | Conduct an initial review and screening of incoming credit applications to ensure all required documents are provided.  /  Verify |
| 15 | Section Divider: Project Timeline & Outcome | 04 | divider | required | fixed | hybrid | Project Timeline & Outcome  /  Provision of Consulting Services for the Film Sector |
| 16 | Project Timeline & Outcomes | Heading only | table | required | fixed | dynamic | Project Phase Deliverables Table  /  N  /  Item  /  Deliverable Description  /  Unit  /  qty  /  Delivery Timeline  /  01  /  Film |
| 17 | Section Divider: Proposed Project Team | 05 | divider | required | fixed | hybrid | Proposed Project Team  /  Provision of Consulting Services for the Film Sector |
| 18 | Section Divider: Project Governance | 06 | divider | required | fixed | hybrid | Project Governance  /  Provision of Consulting Services for the Film Sector |
| 19 | Corporate House Section | Main Cover | shell | optional | fixed | house |  |
| 20 | Corporate House Section | Overview | shell | optional | fixed | house |  |
| 21 | Corporate House Section | What Drives Us | shell | optional | fixed | house |  |
| 22 | Corporate House Section | At a Glance | shell | optional | fixed | house |  |
| 23 | Corporate House Section | Why Strategic Gears | shell | optional | fixed | house |  |
| 24 | Deep Experience Sequence | Deep Experience 1/4 | content | optional | fixed | house |  |
| 25 | Deep Experience Sequence | Deep Experience 2/4 | content | optional | fixed | house |  |
| 26 | Deep Experience Sequence | Deep Experience 3/4 | content | optional | fixed | house |  |
| 27 | Deep Experience Sequence | Deep Experience 4/4 | content | optional | fixed | house |  |
| 28 | Corporate House Section | A House of Expertise | shell | optional | fixed | house |  |
| 29 | Corporate House Section | Vast Network | shell | optional | fixed | house |  |
| 30 | Corporate House Section | Purpose Beyond Business 1/2 | shell | optional | fixed | house |  |
| 31 | Corporate House Section | Purpose Beyond Business 2/2 | shell | optional | fixed | house |  |
| 32 | Corporate House Section | Our Services | shell | optional | fixed | house |  |
| 33 | Corporate House Section | Strategy | shell | optional | fixed | house |  |
| 34 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  The value of Taif flowers increased 15 times.  /  Setting up small and medium enterprises at the farming, har |
| 35 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Implementing the first session of the model to deduce the most accurate estimation of commercial concealment |
| 36 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Implementing the mechanisms of action on a national platform (comprehending all violations issued by the gove |
| 37 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing a unique school offer in the Saudi market that contributes to quickly making "Al-Rajhi" prominent |
| 38 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Dividing the target audience into 5 main segments, based on their investment behaviors.  /  Understanding the |
| 39 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Successfully designing a 15-year financial feasibility study and determining the payback period and rate of r |
| 40 | Services Case Pool A | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Estimating the numbers of expatriate workers in the Kingdom of Saudi Arabia. The estimated number was identic |
| 41 | Corporate House Section | Organizational Excellence | divider | optional | fixed | house |  |
| 42 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing State Gate Process to comply with Misk Charity projects.  /  Developing a checklist to make sure o |
| 43 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Clarifying the actions and roles of management personnel through the developed  operating model.  /  Contribu |
| 44 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Establishing a Situation Room to track private marketing project performance and to attract investments of mo |
| 45 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Working with Misk Project Management Office to establish and develop data files to track the general improvem |
| 46 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Studying Misk charity organizational structure.  /  Submitting the updated organizational structure based on |
| 47 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Items on the statement were clearly formulated to be easily implemented.  /  Developing a unified design for |
| 48 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Succeeding in complying the authority department requirements to come of with listing mechanisms and exceptio |
| 49 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing standards to measure the readiness of 188 government entities and submitting a detailed report of |
| 50 | Services Case Pool B | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Designing and implementing a training program that contributes to developing the specialized and general skil |
| 51 | Corporate House Section | Marketing | divider | optional | fixed | house |  |
| 52 | Services Case Pool C | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing a commercial name and visual identity that reflect the goals of city service providers classificat |
| 53 | Services Case Pool C | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Increase of awareness at the targeted category.  /  Increase of classification  applications and compliance r |
| 54 | Services Case Pool C | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing a detailed sales strategy at the level of each commercial product through (studying the current si |
| 55 | Services Case Pool C | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developing and approving the award's strategy by the steering committee and submitting a letter to the Royal |
| 56 | Services Case Pool C | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Updating the fee structures for the Center's services in accordance with best international practices.  /  De |
| 57 | Corporate House Section | Digital, Cloud, and AI | divider | optional | fixed | house |  |
| 58 | Services Case Pool D | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Formulating a clear 2-year roadmap with integrated quarterly plans to form the master plan for the portfolio |
| 59 | Services Case Pool D | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Automating “Tasfiah” journey and preparing the appropriate infrastructure.  /  Preparing a database of “Tasfi |
| 60 | Services Case Pool D | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  A comprehensive analysis of the state budget contributed to achieving savings by limiting potential statutory |
| 61 | Corporate House Section | People Advisory | divider | optional | fixed | house |  |
| 62 | Services Case Pool E | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  A clear framework and criteria to evaluate readiness across agencies.  /  Analytical reports summarizing gaps |
| 63 | Services Case Pool E | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Developed tailored training modules for all staff levels, from supervisors to managers.  /  Delivered practic |
| 64 | Corporate House Section | Deals Advisory | divider | optional | fixed | house |  |
| 65 | Services Case Pool F | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  We were commissioned by  /  Freshstream  /  to assess the business model and economic resilience of the targe |
| 66 | Services Case Pool F | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  TAG specializes in group travel for major touring artists and film globally.  /  Developed an independent mar |
| 67 | Services Case Pool F | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Following an approach to the client, we were commissioned to provide a sell-side CDD report that could articu |
| 68 | Corporate House Section | Research | divider | optional | fixed | house |  |
| 69 | Services Case Pool G | Services - Cases | case-study | optional | repeatable | house | Outcomes/ Impact  /  Market Research & Economic Studies  /  General Authority for Ports  /  Consultancy Services for Preparing the |
| 70 | Corporate House Section | Our Leadership | divider | optional | fixed | house |  |
| 71 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 20+ years of experience  /  HATTAN SAATY  /  CEO  /  NASSER ALQAHTANI  /  MANAGING PARTNER  /  Strategy  /  Marketing  /  Policy d |
| 72 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 21+ years of experience  /  NAGARAJ PADMANABHAN  /  SENIOR PARTNER  /  RICHARD PARKIN  /  PARTNER  /  Digital & cloud transformati |
| 73 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 13+ years of experience  /  LAITH ABDIN  /  PARTNER  /  AHMAD ABZAKH  /  ASSOCIATE PARTNER  /  Strategy development  /  Strategy e |
| 74 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 12+ years of experience  /  AHMAD AL OMARY  /  ASSOCIATE PARTNER  /  FARHAN KHAN  /  ASSOCIATE PARTNER  /  Business strategies  / |
| 75 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 17+ years of experience  /  HANNI EL SAYED  /  ASSOCIATE PARTNER  /  AHMED ESSAM  /  ASSOCIATE PARTNER  /  Digital transformation |
| 76 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 10+ years of experience  /  PABLO DELGADO  /  PRINCIPAL  /  BASHEER BASATA  /  DIRECTOR  /  Education strategy  /  Product develop |
| 77 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 10+ years of experience  /  ABDULAZIZ ALSHATHRI  /  DIRECTOR  /  SADEQ ALKAMEL  /  DIRECTOR  /  Strategy development and execution |
| 78 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 10+ years of experience  /  SEIF ABDELMAGUID  /  EGYPT COUNTRY MANAGER & DIRECTOR  /  Strategy development  /  Strategy implementa |
| 79 | Leadership Bio Pool | two team members | team-bio | optional | repeatable | house | 10+ years of experience  /  AMMAR MADANI  /  CHIEF HUMAN RESOURCES OFFICER  /  HASHIM ALSADAH  /  CHIEF OPERATING OFFICER  /  Huma |
| 80 | Corporate House Section | Know More Page | shell | optional | fixed | house |  |
| 81 | Corporate House Section | Contact | shell | required | fixed | house |  |

---

## 2) Template Section Map

| section_id | section_name | slide_numbers | layout_families | ownership | required/optional | repeatability |
|---|---|---|---|---|---|---|
| S01 | Proposal Shell | 1 | Proposal Cover | hybrid | required | fixed |
| S02 | Introduction Message | 2 | Introduction Message | dynamic | required | fixed |
| S03 | Table of Contents | 3 | ToC / Agenda | hybrid | required | fixed |
| S04 | Introduction and Understanding (Divider) | 4 | 01 | hybrid | required | fixed |
| S05 | Understanding of Project (Content Block) | 5-8 | KSA, Pillars of the Vision, Vision Realization Programs* | dynamic | required | fixed |
| S06 | Why Strategic Gears (Divider) | 9 | 02 | hybrid | required | fixed |
| S07 | Why Strategic Gears (Evidence Content) | 10 | Services - Detailed Case | dynamic | required | fixed |
| S08 | Methodology (Divider) | 11 | 03 | hybrid | required | fixed |
| S09 | Methodology (Content Block) | 12-14 | Methodology overview/focused/detailed | dynamic | required | fixed |
| S10 | Project Timeline and Outcome (Divider) | 15 | 04 | hybrid | required | fixed |
| S11 | Project Timeline and Outcomes (Table Content) | 16 | Heading only (deliverables table) | dynamic | required | fixed |
| S12 | Proposed Project Team (Divider) | 17 | 05 | hybrid | required | fixed |
| S13 | Project Governance (Divider) | 18 | 06 | hybrid | required | fixed |
| S14 | Corporate Main Shell Sequence | 19-23 | Main Cover, Overview, What Drives Us, At a Glance, Why Strategic Gears | house | optional | fixed |
| S15 | Deep Experience Sequence | 24-27 | Deep Experience 1/4 to 4/4 | house | optional | fixed |
| S16 | Corporate Capability Shell Sequence | 28-33 | A House of Expertise, Vast Network, Purpose Beyond Business 1/2, Purpose Beyond Business 2/2, Our Services, Strategy | house | optional | fixed |
| S17 | Organizational Excellence (Service Divider) | 41 | Organizational Excellence | house | optional | fixed |
| S18 | Organizational Excellence Case Pool | 42-50 | Services - Cases | house | optional | repeatable |
| S19 | Marketing (Service Divider) | 51 | Marketing | house | optional | fixed |
| S20 | Marketing Case Pool | 52-56 | Services - Cases | house | optional | repeatable |
| S21 | Digital, Cloud, and AI (Service Divider) | 57 | Digital, Cloud, and AI | house | optional | fixed |
| S22 | Digital, Cloud, and AI Case Pool | 58-60 | Services - Cases | house | optional | repeatable |
| S23 | People Advisory (Service Divider) | 61 | People Advisory | house | optional | fixed |
| S24 | People Advisory Case Pool | 62-63 | Services - Cases | house | optional | repeatable |
| S25 | Deals Advisory (Service Divider) | 64 | Deals Advisory | house | optional | fixed |
| S26 | Deals Advisory Case Pool | 65-67 | Services - Cases | house | optional | repeatable |
| S27 | Research (Service Divider) | 68 | Research | house | optional | fixed |
| S28 | Research Case Pool | 69 | Services - Cases | house | optional | repeatable |
| S29 | Our Leadership (Divider) | 70 | Our Leadership | house | optional | fixed |
| S30 | Leadership Bio Pool | 71-79 | two team members | house | optional | repeatable |
| S31 | Closing Shell Sequence | 80-81 | Know More Page, Contact | house | Know More optional, Contact required | fixed |

---

## 3) Ownership Classification

- **House-owned (do not freely generate):**
  - Corporate shell sections (`19-33`) and closing shells (`80-81`)
  - Service divider shells (`41`, `51`, `57`, `61`, `64`, `68`, `70`)
  - Services case pool slides (`34-40`, `42-50`, `52-56`, `58-60`, `62-63`, `65-67`, `69`)
  - Leadership/team-bio pool (`71-79`)
- **Dynamic (must be generated from Source Book):**
  - `2` (Introduction Message)
  - `5-8` (Understanding)
  - `10` (Why SG evidence case)
  - `12-14` (Methodology content)
  - `16` (Timeline/outcomes table content)
- **Hybrid (template shell + dynamic fill):**
  - Core dividers and section shells (`1`, `3`, `4`, `9`, `11`, `15`, `17`, `18`)

---

## 4) Current Blueprint Mapping Against Template

| bp_slide | bp_section | mapped_template_section | order_match | ownership_fit | audit_note |
|---:|---|---|---|---|---|
| 1 | Cover | Proposal Shell | yes | hybrid | Cover aligns to template slide 1 shell. |
| 2 | Table of Contents | Table of Contents | no | hybrid | TOC exists but template expects Introduction Message before TOC. |
| 3 | Executive Summary | Introduction & Understanding (closest) | no | dynamic | No dedicated Executive Summary layout in template; currently invented structure. |
| 4 | Understanding | Introduction & Understanding | yes | dynamic | Maps to slides 5-8 content family. |
| 5 | Understanding | Introduction & Understanding | yes | dynamic | Maps to slides 5-8 content family. |
| 6 | Understanding | Introduction & Understanding | yes | dynamic | Maps to slides 5-8 content family. |
| 7 | Why Strategic Gears | Why Strategic Gears | yes | dynamic | Maps to section divider + evidence case slide family (9-10). |
| 8 | Why Strategic Gears | Why Strategic Gears | yes | dynamic | Maps to section divider + evidence case slide family (9-10). |
| 9 | Why Strategic Gears | Why Strategic Gears | yes | dynamic | Maps to section divider + evidence case slide family (9-10). |
| 10 | Team | Proposed Project Team + Leadership Bio Pool | no | hybrid | Template uses divider at 17 + repeatable two-member bio pool (71-79), not profile-card layouts. |
| 11 | Team | Proposed Project Team + Leadership Bio Pool | no | hybrid | Template uses divider at 17 + repeatable two-member bio pool (71-79), not profile-card layouts. |
| 12 | Team | Proposed Project Team + Leadership Bio Pool | no | hybrid | Template uses divider at 17 + repeatable two-member bio pool (71-79), not profile-card layouts. |
| 13 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 14 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 15 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 16 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 17 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 18 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 19 | Methodology | Methodology | no | dynamic | Template has 3 methodology content layouts (12-14), blueprint expands to 7 generic slides. |
| 20 | Governance | Project Governance | no | dynamic | Template has governance divider (18) but no matching generated governance content family in current blueprint. |
| 21 | Governance | Project Governance | no | dynamic | Template has governance divider (18) but no matching generated governance content family in current blueprint. |
| 22 | Governance | Project Governance | no | dynamic | Template has governance divider (18) but no matching generated governance content family in current blueprint. |
| 23 | Timeline | Project Timeline & Outcomes | no | dynamic | Timeline section exists at 15-16 but appears after governance in blueprint. |
| 24 | Timeline | Project Timeline & Outcomes | no | dynamic | Timeline section exists at 15-16 but appears after governance in blueprint. |
| 25 | Case Studies | Services Case Pools (house-owned repeatable) | no | house | Blueprint generates free-form case-study slides rather than selecting from Services - Cases families. |
| 26 | Case Studies | Services Case Pools (house-owned repeatable) | no | house | Blueprint generates free-form case-study slides rather than selecting from Services - Cases families. |
| 27 | Case Studies | Services Case Pools (house-owned repeatable) | no | house | Blueprint generates free-form case-study slides rather than selecting from Services - Cases families. |
| 28 | Case Studies | Services Case Pools (house-owned repeatable) | no | house | Blueprint generates free-form case-study slides rather than selecting from Services - Cases families. |
| 29 | Case Studies | Services Case Pools (house-owned repeatable) | no | house | Blueprint generates free-form case-study slides rather than selecting from Services - Cases families. |
| 30 | Closing | Contact / closing shells | no | house | Template closing/contact is house-owned (80-81); blueprint invents dynamic closing slide. |

---

## 5) Structural Gaps and Severity

### Critical
- **Missing required dynamic section:** `Introduction Message` (`template slide 2`) is absent from blueprint.
- **Order violation:** blueprint sequence diverges from template canonical order immediately (`TOC` before `Introduction Message`, and custom sections not in template sequence).
- **House-owned sections generated freely:** `Case Studies` (`bp 25-29`) and `Closing` (`bp 30`) are generated as dynamic content instead of selecting/using house-owned pools/shells.
- **Section model drift:** blueprint introduces non-template standalone section `Executive Summary`, causing structural mismatch.

### High
- **Methodology over-generation:** blueprint allocates 7 generic methodology slides while template dynamic methodology family is `12-14` (3 slides).
- **Team model mismatch:** blueprint emits profile-card style team slides; template supports team via divider (`17`) plus house repeatable two-member bio pool (`71-79`).
- **Timeline position mismatch:** timeline appears after governance in blueprint, while template positions timeline before team/governance dividers (`15-16` then `17-18`).

### Medium
- **Governance representation ambiguity:** template has governance divider (`18`) but no obvious dedicated governance-content layout in core 1-18. Current blueprint creates 3 governance slides that do not map to explicit template layouts.
- **Case-study pool utilization quality:** template offers large case pools segmented by service families; blueprint uses a small free-form list without layout-family matching.
- **Team-bio pool utilization quality:** template provides 9 repeatable two-member bio slides; blueprint does not map to that pool.

---

## 6) Proposed Fixes for Next Implementation Phase

1. **Introduce canonical template section-order contract**
   - Build a reusable section-order map from template metadata.
   - Enforce strict blueprint ordering against this map.

2. **Split blueprint outputs into `dynamic_fill_plan` vs `house_pool_selection`**
   - `dynamic_fill_plan`: only for dynamic/hybrid slots.
   - `house_pool_selection`: references to house-owned case/team/contact shells by slide family and slot count.

3. **Replace free-form section taxonomy with template-native taxonomy**
   - Remove standalone `Executive Summary` unless explicitly mapped to an existing template layout.
   - Add explicit `Introduction Message` slot before TOC.

4. **Constrain dynamic slide counts per section to template-defined capacities**
   - Methodology capped to template family count.
   - Timeline mapped to `15-16` family order.
   - Team mapped to divider + selected bio-pool cards.

5. **Add ownership guardrails (hard fail)**
   - If generator attempts to author house-owned section content directly, fail validation.
   - Require selection references for case-study/team-bio pools, not generated prose-only entries.

6. **Add template-alignment validator before downstream rendering**
   - Validate:
     - section order exact match,
     - required sections present,
     - no house-owned free-generation,
     - pool coverage minimums (case-study and team-bio),
     - allowed layout families only.

7. **Define pool-coverage minimums (reusable, domain-agnostic)**
   - Case-study pool: require configurable minimum count and service-family diversity.
   - Team-bio pool: require configurable minimum number of selected bio cards.

---

## Audit Conclusion
- The current blueprint is **not template-accurate**.
- Primary failure mode is structural: it follows a generic consulting narrative, not the template’s canonical section and ownership model.
- Next phase should implement a **template-locked blueprint contract** with ownership-aware slotting and validation.

