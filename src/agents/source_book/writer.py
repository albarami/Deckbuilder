"""Source Book Writer agent — split-call architecture for deep content.

Consumes reference_index, external_evidence_pack, proposal_strategy, and
rfp_context to produce a structured SourceBook with 7 sections.

Split-call architecture:
  Stage 1a: Sections 1-2 (RFP Interpretation + Client Problem Framing)
  Stage 1b: Section 3 (Why Strategic Gears — team, projects, capabilities)
  Stage 1c: Section 4 (External Evidence curation)
  Stage 1d: Section 5 (Proposed Solution — methodology, governance, timeline)
  Stage 2a: Section 6 (Slide blueprints)
  Stage 2b: Section 7 (Evidence ledger)

Each stage gets its own LLM call with full token budget so the model
can produce deep prose content without JSON overhead from other sections
competing for tokens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from src.config.models import MODEL_MAP
from src.models.source_book import (
    ClientProblemFraming,
    EvidenceLedger,
    EvidenceLedgerEntry,
    ProposedSolution,
    RFPInterpretation,
    SourceBook,
    SourceBookSection1,
    SourceBookSection2,
    SourceBookSection3,
    SourceBookSection4,
    SourceBookSection5,
    SourceBookSection6,
    SourceBookSection7,
    SourceBookSections12,
    _Section1Classification,
    _Section1Prose,
    _Section2Validated,
    _Section5Governance,
    _Section5Methodology,
)
from src.models.state import DeckForgeState
from src.services.llm import call_llm

from .prompts import (
    STAGE1A_CLASSIFICATION_PROMPT,
    STAGE1A_SECTION1_PROMPT,
    STAGE1B_SECTION2_PROMPT,
    STAGE1B_SECTION3_PROMPT,
    STAGE1C_SECTION4_PROMPT,
    STAGE1D_SECTION5_PROMPT,
    STAGE1E_GOVERNANCE_PROMPT,
    STAGE1E_METHODOLOGY_PROMPT,
    STAGE2A_BLUEPRINTS_PROMPT,
    STAGE2B_EVIDENCE_LEDGER_PROMPT,
    WRITER_SYSTEM_PROMPT,
)

# Legacy alias used by tests
SYSTEM_PROMPT = WRITER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Patterns for citation references in source book text
_CLM_PATTERN = re.compile(r"CLM-\d{4}")
_EXT_PATTERN = re.compile(r"EXT-\d{3}")

# Banned hedge words/phrases for executive tone enforcement
_HEDGE_PATTERNS = [
    "illustrative",
    "pending",
    "preliminary",
    "indicative",
    "subject to",
    "may require",
    "could be",
    "would need",
    "to be determined",
    "further analysis",
    "TBD",
    "to be confirmed",
    "validation required",
    "could potentially",
    "may be adjusted",
]


def _build_evidence_ledger_from_citations(source_book: SourceBook) -> EvidenceLedger:
    """Scan sections 1-6 for CLM-xxxx / EXT-xxx citations and build a ledger."""
    sections_data = {
        "rfp_interpretation": source_book.rfp_interpretation.model_dump(mode="json"),
        "client_problem_framing": source_book.client_problem_framing.model_dump(mode="json"),
        "why_strategic_gears": source_book.why_strategic_gears.model_dump(mode="json"),
        "external_evidence": source_book.external_evidence.model_dump(mode="json"),
        "proposed_solution": source_book.proposed_solution.model_dump(mode="json"),
        "slide_blueprints": [bp.model_dump(mode="json") for bp in source_book.slide_blueprints],
    }
    text_blob = json.dumps(sections_data, ensure_ascii=False, default=str)

    clm_ids = sorted(set(_CLM_PATTERN.findall(text_blob)))
    ext_ids = sorted(set(_EXT_PATTERN.findall(text_blob)))

    entries: list[EvidenceLedgerEntry] = []
    for cid in clm_ids:
        entries.append(
            EvidenceLedgerEntry(
                claim_id=cid,
                claim_text=f"Auto-extracted citation {cid}",
                source_type="internal",
                source_reference=cid,
                confidence=0.5,
                verifiability_status="unverified",
            )
        )
    for eid in ext_ids:
        entries.append(
            EvidenceLedgerEntry(
                claim_id=eid,
                claim_text=f"Auto-extracted citation {eid}",
                source_type="external",
                source_reference=eid,
                confidence=0.5,
                verifiability_status="unverified",
            )
        )

    logger.info(
        "Built evidence ledger from citations: %d CLM + %d EXT = %d entries",
        len(clm_ids),
        len(ext_ids),
        len(entries),
    )
    return EvidenceLedger(entries=entries)


def _scan_for_hedges(source_book: SourceBook) -> list[str]:
    """Scan all text fields for banned hedge phrases."""
    text_blob = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )
    matches: list[str] = []
    for phrase in _HEDGE_PATTERNS:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text_blob, re.IGNORECASE):
            matches.append(phrase)
    return matches


def _strip_dangling_ext_citations(
    source_book: SourceBook,
    state: DeckForgeState,
) -> SourceBook:
    """Remove EXT-xxx citations that don't exist in the external evidence pack."""
    valid_ext_ids: set[str] = set()
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                valid_ext_ids.add(sid)

    text_blob = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )
    all_ext_ids = set(_EXT_PATTERN.findall(text_blob))
    dangling = all_ext_ids - valid_ext_ids

    if not dangling:
        logger.info("EXT citation check: all %d EXT IDs are valid", len(all_ext_ids))
        return source_book

    logger.warning(
        "EXT citation check: stripping %d dangling IDs: %s (valid: %s)",
        len(dangling),
        sorted(dangling),
        sorted(valid_ext_ids),
    )

    dangling_pattern = re.compile(
        r"\s*\[?(" + "|".join(re.escape(d) for d in dangling) + r")\]?\s*"
    )

    def _clean_str(val: str) -> str:
        return dangling_pattern.sub(" ", val).strip()

    def _clean_list(items: list[str]) -> list[str]:
        return [_clean_str(s) for s in items if _clean_str(s)]

    for bp in source_book.slide_blueprints:
        if bp.proof_points:
            bp.proof_points = [p for p in bp.proof_points if p not in dangling]
        if bp.must_have_evidence:
            bp.must_have_evidence = [m for m in bp.must_have_evidence if m not in dangling]
        if bp.bullet_logic:
            bp.bullet_logic = _clean_list(bp.bullet_logic)

    if source_book.evidence_ledger.entries:
        original_count = len(source_book.evidence_ledger.entries)
        source_book.evidence_ledger.entries = [
            e for e in source_book.evidence_ledger.entries
            if e.claim_id not in dangling
        ]
        removed = original_count - len(source_book.evidence_ledger.entries)
        if removed:
            logger.info("Removed %d dangling EXT entries from evidence ledger", removed)

    return source_book


def _engine1_guard(
    source_book: SourceBook,
    state: DeckForgeState,
) -> SourceBook:
    """Engine 1 / Engine 2 guard — validate firm-specific data against KG.

    After the Writer produces content, this guard checks every consultant
    name and project against the actual knowledge graph. Anything the LLM
    fabricated (not in KG) is stripped and replaced with honest placeholders.

    Rules:
    - Consultant names must exist in KG people list → recommended_candidate
    - Consultant names NOT in KG → cleared, set to open_role_profile
    - No consultant is ever confirmed_candidate (Engine 2 not integrated)
    - Projects must exist in KG projects list → kept with clear sourcing
    - Projects NOT in KG → stripped, evidence_gap added
    - Evidence ledger: internal entries without real KG/ref backing → gap
    """
    wsg = source_book.why_strategic_gears

    # Build KG name and project lookup sets
    kg_names: set[str] = set()
    kg_project_names: set[str] = set()
    if state.knowledge_graph:
        for p in state.knowledge_graph.people:
            if p.person_type == "internal_team" and p.name:
                kg_names.add(p.name.strip().lower())
        for pr in state.knowledge_graph.projects:
            if pr.project_name:
                kg_project_names.add(pr.project_name.strip().lower())

    # ── Guard: Consultants ────────────────────────────────
    fabricated_names: list[str] = []
    for nc in wsg.named_consultants:
        # Never allow confirmed_candidate — Engine 2 not integrated
        if nc.staffing_status == "confirmed_candidate":
            nc.staffing_status = "recommended_candidate"
            nc.source_of_recommendation = (
                "indexed from data test folder — not authoritative company backend"
            )
            logger.info(
                "Engine 1 guard: downgraded '%s' from confirmed → recommended",
                nc.name,
            )

        # Check if name exists in KG
        if nc.name and nc.name.strip():
            name_lower = nc.name.strip().lower()
            if kg_names and name_lower in kg_names:
                # Name is real — keep as recommended_candidate
                nc.staffing_status = "recommended_candidate"
                if "indexed from" not in (nc.source_of_recommendation or ""):
                    nc.source_of_recommendation = (
                        "indexed from data test folder — "
                        "not authoritative company backend"
                    )
            elif not kg_names:
                # KG has 0 people — all names are fabricated
                fabricated_names.append(nc.name)
                nc.name = ""
                nc.staffing_status = "open_role_profile"
                nc.source_of_recommendation = "open_role_requirement"
                nc.confidence = "low"
            else:
                # KG has people but this name is NOT in it — fabricated
                fabricated_names.append(nc.name)
                nc.name = ""
                nc.staffing_status = "open_role_profile"
                nc.source_of_recommendation = "open_role_requirement"
                nc.confidence = "low"

    if fabricated_names:
        logger.warning(
            "Engine 1 guard: stripped %d fabricated consultant names: %s "
            "(KG has %d real people)",
            len(fabricated_names),
            fabricated_names,
            len(kg_names),
        )

    # ── Guard: Project-evidence leakage (B6) ────────────────
    # Build current RFP identifiers to detect self-referential project evidence
    current_rfp_identifiers: set[str] = set()
    if state.rfp_context:
        for field_name in ("rfp_name", "issuing_entity"):
            val = getattr(state.rfp_context, field_name, None)
            if val:
                en = getattr(val, "en", "") or ""
                ar = getattr(val, "ar", "") or ""
                for text in (en, ar):
                    if text:
                        tokens = {t.lower().strip() for t in text.split() if len(t) > 3}
                        current_rfp_identifiers.update(tokens)
        # Add scope keywords (first 3 words of each scope item)
        for si in (state.rfp_context.scope_items or [])[:5]:
            desc = si.description
            en = getattr(desc, "en", "") or ""
            if en:
                tokens = {t.lower().strip() for t in en.split()[:3] if len(t) > 3}
                current_rfp_identifiers.update(tokens)

    def _rfp_token_overlap(project_name: str) -> float:
        """Compute token overlap ratio between project name and current RFP."""
        if not current_rfp_identifiers or not project_name:
            return 0.0
        proj_tokens = {t.lower().strip() for t in project_name.split() if len(t) > 3}
        if not proj_tokens:
            return 0.0
        overlap = proj_tokens & current_rfp_identifiers
        return len(overlap) / len(proj_tokens)

    # ── Guard: Projects ───────────────────────────────────
    real_projects = []
    fabricated_projects: list[str] = []
    leakage_stripped: list[str] = []
    for pe in wsg.project_experience:
        proj_lower = pe.project_name.strip().lower() if pe.project_name else ""
        # B6: Check for current-RFP leakage (project that IS the current opportunity)
        overlap = _rfp_token_overlap(pe.project_name or "")
        if overlap > 0.6:
            leakage_stripped.append(pe.project_name or "(unnamed)")
            logger.warning(
                "Engine 1 guard: stripped leaked project '%s' "
                "(%.0f%% token overlap with current RFP)",
                pe.project_name, overlap * 100,
            )
            continue
        if kg_project_names and proj_lower in kg_project_names:
            real_projects.append(pe)
        elif not kg_project_names:
            # KG has 0 projects — all are fabricated
            fabricated_projects.append(pe.project_name)
        else:
            # KG has projects but this one is NOT in it
            fabricated_projects.append(pe.project_name)

    if fabricated_projects:
        logger.warning(
            "Engine 1 guard: stripped %d fabricated projects (KG has %d real): %s",
            len(fabricated_projects),
            len(kg_project_names),
            fabricated_projects[:5],
        )
    if leakage_stripped:
        logger.warning(
            "Engine 1 guard: stripped %d leaked projects (current RFP self-references): %s",
            len(leakage_stripped),
            leakage_stripped[:5],
        )
    wsg.project_experience = real_projects

    # ── Guard: Evidence Ledger ────────────────────────────
    # Build set of valid internal references from KG and reference_index
    valid_internal_refs: set[str] = set()
    if state.reference_index:
        for c in state.reference_index.claims:
            if c.claim_id:
                valid_internal_refs.add(c.claim_id)
    # KG project IDs as valid references
    if state.knowledge_graph:
        for pr in state.knowledge_graph.projects:
            if pr.project_id:
                valid_internal_refs.add(pr.project_id)

    gap_count = 0
    for entry in source_book.evidence_ledger.entries:
        if entry.source_type == "internal" and entry.verifiability_status == "verified":
            # Check if the referenced source actually exists
            has_valid_ref = any(
                ref in entry.source_reference or ref in entry.claim_id
                for ref in valid_internal_refs
            ) if valid_internal_refs else False
            if not has_valid_ref:
                entry.verifiability_status = "gap"
                entry.verification_note = (
                    "Engine 1 guard: no matching reference found in KG or "
                    "reference_index. Must be populated from company backend."
                )
                gap_count += 1

    if gap_count:
        logger.warning(
            "Engine 1 guard: changed %d evidence entries from 'verified' to 'gap' "
            "(no matching KG/reference data)",
            gap_count,
        )

    # NOTE: Blueprint overclaim scanning was REMOVED from _engine1_guard
    # because it runs before Stage 2a generates blueprints (empty list).
    # Use _engine1_blueprint_overclaim_scan() AFTER Stage 2a instead.
    # _engine1_blueprint_overclaim_scan() handles this AFTER Stage 2a.

    if False:  # DISABLED — overclaim scan moved to _engine1_blueprint_overclaim_scan()
        # Regex pattern matching semantic certainty claims in Arabic and English.
        # Covers: 100%, "all requirements met", "proven", "complete compliance",
        # and Arabic equivalents including يستوفي جميع, كل متطلب, مُثبتة, etc.
        import re as _re
        _OVERCLAIM_RE = _re.compile(
            # Arabic certainty patterns — broad semantic coverage
            r"100%|بنسبة\s*100|"
            r"يستوفي\s+جميع|يستوفون\s+جميع|تستوفي\s+جميع|"  # meets all (m/f/pl)
            r"كل\s+متطلب|جميع\s+متطلبات|جميع\s+المتطلبات|"  # every/all requirements
            r"مُثبتة|مثبتة|مُثبت|مثبت|"  # proven (m/f)
            r"مُغطّى|مغطى|مغطاة|"  # covered (m/f)
            r"امتثال\s+كامل|امتثال\s+100|مطابقة\s+كاملة|مطابقة\s*100|"
            r"تطابق\s+تام|استيفاء\s+كامل|"
            r"فريق\s+مؤهل\s+بالكامل|فريق\s+متكامل\s+يلبي|"
            r"خبرة\s+مثبتة|خبرة\s+موثقة|سجل\s+حافل|"
            r"تحقق\s+كامل|توافق\s+كامل|التزام\s+كامل|"  # complete compliance/conformity
            r"بدون\s+استثناء|دون\s+استثناء|"  # without exception
            # English certainty patterns
            r"fully meets|fully meet|complete compliance|all requirements satisfied|"
            r"proven track record|proven capability|proven expertise|"
            r"fully qualified team|fully staffed|"
            r"100% match|100% compliance|100% coverage",
            _re.IGNORECASE,
        )

        # Targeted replacements for common Arabic phrases
        _AR_REPLACEMENTS = [
            (r"يستوفي\s+جميع", "مُصمَّم لاستيفاء"),
            (r"يستوفون\s+جميع", "مُصمَّمون لاستيفاء"),
            (r"كل\s+متطلب\s+مُغطّى", "كل متطلب محدَّد"),
            (r"كل\s+متطلب\s+مغطى", "كل متطلب محدَّد"),
            (r"مُثبتة", "مطلوبة"),
            (r"مثبتة", "مطلوبة"),
            (r"جميع\s+متطلبات", "متطلبات"),
            (r"جميع\s+المتطلبات", "المتطلبات"),
            (r"امتثال\s+كامل", "امتثال مُصمَّم"),
            (r"مطابقة\s+كاملة", "مطابقة مُصمَّمة"),
        ]

        def _soften_text(text: str) -> str:
            """Apply targeted Arabic replacements, then fallback regex."""
            result = text
            for pattern, replacement in _AR_REPLACEMENTS:
                result = _re.sub(pattern, replacement, result)
            # Fallback: replace any remaining 100% or certainty
            result = _re.sub(r"100%|بنسبة\s*100", "مُصمَّم لتلبية المتطلبات", result)
            return result

        overclaim_count = 0
        for bp in source_book.slide_blueprints:
            # Scan title, key_message, and bullet_logic — ALL entries
            fields = [
                ("title", bp.title),
                ("key_message", bp.key_message),
            ] + [
                (f"bullet_{j}", b) for j, b in enumerate(bp.bullet_logic or [])
            ]
            for field_name, text in fields:
                if not text:
                    continue
                if _OVERCLAIM_RE.search(text):
                    replaced = _soften_text(text)
                    if replaced != text:
                        if field_name == "title":
                            bp.title = replaced
                        elif field_name == "key_message":
                            bp.key_message = replaced
                        elif field_name.startswith("bullet_"):
                            idx = int(field_name.split("_")[1])
                            bp.bullet_logic[idx] = replaced
                        overclaim_count += 1
                        logger.info(
                            "Engine 1 guard: softened overclaim in slide %d %s",
                            bp.slide_number, field_name,
                        )

        if overclaim_count:
            logger.warning(
                "Engine 1 guard: replaced %d certainty overclaims in blueprints "
                "(team=%s, projects=%d)",
                overclaim_count,
                "present" if has_real_team else "absent",
                len(real_projects),
            )

        # Layer 2: SEMANTIC check on team/capability sections (S07, S12, S13, S14)
        # Even after regex cleanup, append Engine 2 conditional language if missing
        _TEAM_SECTIONS = {"S07", "S12", "S13", "S14"}
        # Sections that make claims about SG capability, team, or proof
        _PROOF_SECTION_KEYWORDS = [
            "فريق", "team", "capability", "قدرات", "تطابق", "match",
            "compliance", "امتثال", "خبرة", "experience",
            "why sg", "لماذا", "sg", "strategic gears", "ستراتيجيك",
            "مطابقة", "مؤهل", "qualified",
        ]
        _ENGINE2_AR_SUFFIX = " — يتطلب تأكيد التعيينات من المحرك الثاني"
        _ENGINE2_EN_SUFFIX = " — requires staffing confirmation from Engine 2"
        _PROJECT_AR_SUFFIX = " — يتطلب إثبات من سجل المشاريع"

        # Project-claim keywords (broader than just "track record")
        _PROJECT_CLAIM_KW = [
            "خبرة مباشرة", "سجل حافل", "مشاريع سابقة", "نفّذت", "نفذت",
            "أنجزت", "مشروع مع", "مشروعاً مع", "delivered", "executed",
            "track record", "proven delivery", "prior project",
            "الوحيدة التي", "the only",  # uniqueness claims
        ]

        semantic_fixes = 0
        logger.info(
            "Engine 1 guard Layer 2: scanning %d blueprints (team=%s, projects=%s)",
            len(source_book.slide_blueprints), has_real_team, has_real_projects,
        )
        for bp in source_book.slide_blueprints:
            combined = f"{bp.section} {bp.title} {bp.purpose}".lower()
            is_proof_section = any(kw in combined for kw in _PROOF_SECTION_KEYWORDS)
            if not is_proof_section:
                continue

            km = bp.key_message or ""
            if not km:
                continue

            logger.info(
                "Engine 1 guard Layer 2: matched slide %d '%s' (section=%s)",
                bp.slide_number, bp.title[:40], bp.section[:20] if bp.section else "?",
            )

            is_arabic = any(c > "\u0600" for c in km)
            already_conditional = "المحرك الثاني" in km or "Engine 2" in km

            # STEP 1: REWRITE base text certainty phrases → conditional
            # This fixes the BASE claim, not just appends a suffix
            if not has_real_team:
                import re as _re2
                _BASE_REWRITES = [
                    # "documented experience" → "required experience"
                    (r"خبرة\s+عملية\s+موثقة", "خبرة عملية مطلوبة"),
                    (r"خبرة\s+موثقة", "خبرة مطلوبة"),
                    # "direct experience" → "required direct experience"
                    # Match with optional Arabic waw prefix (وخبرة)
                    (r"و?خبرة\s+مباشرة", "خبرة مباشرة مطلوبة"),
                    # "qualifications matching" → "qualifications designed to match"
                    (r"مؤهلات\s+تتطابق\s+مع", "مؤهلات مُصمَّمة لتتطابق مع"),
                    (r"تتطابق\s+مع\s+متطلبات", "مُصمَّمة لتتطابق مع متطلبات"),
                    # "specialists" → "required specialists" in team context
                    (r"متخصصين\s+بمؤهلات", "متخصصين مطلوبين بمؤهلات"),
                    # "proven" → "required"
                    (r"مُثبت[ةه]?", "مطلوب[ة]"),
                    # English equivalents
                    (r"proven\s+experience", "required experience"),
                    (r"direct\s+experience", "required direct experience"),
                    (r"documented\s+experience", "experience to be confirmed"),
                ]
                original_km = km
                for pattern, replacement in _BASE_REWRITES:
                    km = _re2.sub(pattern, replacement, km)
                if km != original_km:
                    bp.key_message = km
                    semantic_fixes += 1
                    logger.info(
                        "Engine 1 guard: rewrote base text in slide %d",
                        bp.slide_number,
                    )

            # STEP 2: Append Engine 2 suffix if not already conditional
            if not has_real_team and "المحرك الثاني" not in km and "Engine 2" not in km:
                suffix = _ENGINE2_AR_SUFFIX if is_arabic else _ENGINE2_EN_SUFFIX
                bp.key_message = km + suffix
                semantic_fixes += 1
                logger.info(
                    "Engine 1 guard: appended Engine 2 team condition to slide %d",
                    bp.slide_number,
                )
                km = bp.key_message

            # STEP 3: Project proof claims
            if not has_real_projects and "سجل المشاريع" not in km:
                if any(kw in km for kw in _PROJECT_CLAIM_KW):
                    bp.key_message = km + _PROJECT_AR_SUFFIX
                    semantic_fixes += 1
                    logger.info(
                        "Engine 1 guard: appended project proof condition to slide %d",
                        bp.slide_number,
                    )

        if semantic_fixes:
            logger.warning(
                "Engine 1 guard: added %d Engine 2 conditional suffixes to team/proof sections",
                semantic_fixes,
            )

    logger.info(
        "Engine 1 guard complete: %d real consultants, %d open roles, "
        "%d real projects, %d fabricated stripped",
        sum(1 for nc in wsg.named_consultants if nc.name and nc.name.strip()),
        sum(1 for nc in wsg.named_consultants if nc.staffing_status == "open_role_profile"),
        len(real_projects),
        len(fabricated_names) + len(fabricated_projects),
    )

    return source_book


def _engine1_blueprint_overclaim_scan(
    source_book: SourceBook,
    state: DeckForgeState,
) -> SourceBook:
    """Scan blueprints for semantic overclaims AFTER Stage 2a generates them.

    When KG data is absent (no real team, few projects), replace certainty
    language in ALL blueprint entries with conditional framing.
    """
    import re as _re

    # Determine data availability
    kg_people_count = 0
    kg_project_count = 0
    if state.knowledge_graph:
        kg_people_count = sum(
            1 for p in state.knowledge_graph.people
            if p.person_type == "internal_team"
        )
        kg_project_count = len(state.knowledge_graph.projects)

    has_real_team = kg_people_count > 0
    has_real_projects = kg_project_count >= 3

    if has_real_team and has_real_projects:
        return source_book  # No overclaim risk

    # Arabic semantic certainty patterns
    _OVERCLAIM_RE = _re.compile(
        r"100%|بنسبة\s*100|"
        r"يستوفي\s+جميع|يستوفون\s+جميع|يستوفي\s+كل|"
        r"كل\s+متطلب|جميع\s+متطلبات|جميع\s+المتطلبات|"
        r"مُثبتة|مثبتة|مُغطّى|مغطى|موثقة|و?خبرة\s+مباشرة|"
        r"امتثال\s+كامل|مطابقة\s+كاملة|تطابق\s+تام|استيفاء\s+كامل|"
        r"فريق\s+مؤهل\s+بالكامل|خبرة\s+مثبتة|سجل\s+حافل|"
        r"fully meets|complete compliance|proven track record|"
        r"fully qualified|100% match|100% compliance",
        _re.IGNORECASE,
    )

    _AR_REPLACEMENTS = [
        (r"يستوفي\s+جميع", "مُصمَّم لاستيفاء"),
        (r"يستوفي\s+كل", "مُصمَّم لاستيفاء كل"),
        (r"يستوفون\s+جميع", "مُصمَّمون لاستيفاء"),
        (r"كل\s+متطلب\s+مُغطّى", "كل متطلب محدَّد"),
        (r"كل\s+متطلب\s+مغطى", "كل متطلب محدَّد"),
        (r"مُثبتة", "مطلوبة"),
        (r"مثبتة", "مطلوبة"),
        (r"مُغطّى", "محدَّد"),
        (r"مغطى", "محدَّد"),
        (r"جميع\s+متطلبات", "متطلبات"),
        (r"جميع\s+المتطلبات", "المتطلبات"),
        # "documented" and "direct" — must be conditional when proof absent
        (r"موثقة", "مطلوبة"),
        (r"و?خبرة\s+مباشرة", "خبرة مطلوبة"),
        (r"امتثال\s+كامل", "امتثال مُصمَّم"),
        (r"مطابقة\s+كاملة", "مطابقة مُصمَّمة"),
    ]

    def _soften(text: str) -> str:
        result = text
        for pattern, replacement in _AR_REPLACEMENTS:
            result = _re.sub(pattern, replacement, result)
        result = _re.sub(r"100%|بنسبة\s*100", "مُصمَّم لتلبية المتطلبات", result)
        return result

    overclaim_count = 0
    for bp in source_book.slide_blueprints:
        fields = [
            ("title", bp.title),
            ("key_message", bp.key_message),
        ] + [
            (f"bullet_{j}", b) for j, b in enumerate(bp.bullet_logic or [])
        ]
        for field_name, text in fields:
            if not text:
                continue
            if _OVERCLAIM_RE.search(text):
                replaced = _soften(text)
                if replaced != text:
                    if field_name == "title":
                        bp.title = replaced
                    elif field_name == "key_message":
                        bp.key_message = replaced
                    elif field_name.startswith("bullet_"):
                        idx = int(field_name.split("_")[1])
                        bp.bullet_logic[idx] = replaced
                    overclaim_count += 1
                    logger.info(
                        "Blueprint overclaim scan: softened slide %d %s",
                        bp.slide_number, field_name,
                    )

    # ── FINAL PASS: targeted S07/S12/S13/S14 sweep ──────────
    # The LLM generates different phrasings every run. The regex above
    # catches known patterns. This final pass catches ANY remaining
    # كامل/جميع/استيفاء in team/capability sections specifically.
    _TEAM_SECTIONS = {"S07", "S12", "S13", "S14"}
    _FINAL_PATTERNS = [
        (_re.compile(r"كامل"), "مُستهدَف"),  # complete → targeted
        (_re.compile(r"استيفاء\s+كامل"), "تصميم يستهدف استيفاء"),
        (_re.compile(r"كل\s+متطلب"), "كل متطلب مُحدَّد"),
        (_re.compile(r"جميع\s+المتطلبات"), "المتطلبات المُحدَّدة"),
        (_re.compile(r"جميع\s+متطلبات"), "متطلبات"),
    ]

    # Map legacy slide sections to contract section IDs for matching
    _TEAM_KEYWORDS = ["team", "فريق", "why sg", "لماذا", "capability", "قدرات", "compliance", "امتثال"]

    final_fixes = 0
    for bp in source_book.slide_blueprints:
        combined = f"{bp.section} {bp.title} {bp.purpose}".lower()
        is_team_section = any(kw in combined for kw in _TEAM_KEYWORDS)
        if not is_team_section:
            continue

        for field_name, text in [("title", bp.title), ("key_message", bp.key_message)]:
            if not text:
                continue
            fixed = text
            for pat, repl in _FINAL_PATTERNS:
                if pat.search(fixed):
                    fixed = pat.sub(repl, fixed)
            if fixed != text:
                if field_name == "title":
                    bp.title = fixed
                else:
                    bp.key_message = fixed
                final_fixes += 1
                logger.info(
                    "Blueprint FINAL pass: softened slide %d %s: '%s' → '%s'",
                    bp.slide_number, field_name, text[:50], fixed[:50],
                )

    # ── Layer 3: Append Engine 2 conditional suffixes to team/proof sections ──
    _ENGINE2_AR = " — يتطلب تأكيد التعيينات من المحرك الثاني"
    _PROJECT_AR = " — يتطلب إثبات من سجل المشاريع"
    _PROJECT_KW = [
        "خبرة مباشرة", "سجل حافل", "مشاريع سابقة", "نفّذت", "نفذت",
        "أنجزت", "مشروع مع", "مشروعاً مع", "الوحيدة التي",
    ]
    suffix_count = 0
    for bp in source_book.slide_blueprints:
        combined = f"{bp.section} {bp.title} {bp.purpose}".lower()
        is_team = any(kw in combined for kw in _TEAM_KEYWORDS)
        if not is_team:
            continue
        km = bp.key_message or ""
        if not km:
            continue
        if "المحرك الثاني" in km or "Engine 2" in km:
            continue  # already has conditional
        if not has_real_team:
            bp.key_message = km + _ENGINE2_AR
            suffix_count += 1
            km = bp.key_message
        if not has_real_projects and any(kw in km for kw in _PROJECT_KW):
            bp.key_message = km + _PROJECT_AR
            suffix_count += 1

    total = overclaim_count + final_fixes + suffix_count
    if total:
        logger.warning(
            "Blueprint overclaim scan: %d fixes (%d regex + %d final + %d E2 suffix) "
            "(team=%d, projects=%d)",
            total, overclaim_count, final_fixes, suffix_count,
            kg_people_count, kg_project_count,
        )
    else:
        logger.info("Blueprint overclaim scan: 0 overclaims found")

    return source_book


async def _rewrite_hedges(
    source_book: SourceBook,
    hedges_found: list[str],
) -> SourceBook:
    """Make one LLM call to rewrite sentences containing banned hedges."""
    hedge_list = ", ".join(f'"{h}"' for h in hedges_found)

    system = (
        "You are an executive writing editor. The Source Book below "
        "contains hedging language that must be removed. Rewrite every "
        "sentence containing a banned word with direct, confident statements. "
        f"Remove ALL instances of: {hedge_list}. "
        "Do NOT change any other content. Output the full corrected SourceBook JSON."
    )

    user_msg = json.dumps(
        source_book.model_dump(mode="json"),
        ensure_ascii=False,
        default=str,
    )

    model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))

    try:
        async with asyncio.timeout(120):
            result = await call_llm(
                model=model,
                system_prompt=system,
                user_message=user_msg,
                response_model=SourceBook,
                max_tokens=32000,
                temperature=0.0,
            )
        cleaned = result.parsed
        cleaned.pass_number = source_book.pass_number
        if not cleaned.slide_blueprints and source_book.slide_blueprints:
            cleaned.slide_blueprints = source_book.slide_blueprints
        if not cleaned.evidence_ledger.entries and source_book.evidence_ledger.entries:
            cleaned.evidence_ledger = source_book.evidence_ledger
        logger.info("Hedge rewrite complete — removed %d hedge patterns", len(hedges_found))
        return cleaned, result
    except Exception as e:
        logger.warning("Hedge rewrite failed: %s — keeping original", e)
        return source_book, None


def _build_shared_context(
    state: DeckForgeState,
    reviewer_feedback: str = "",
) -> dict:
    """Build the shared context dict that all stage calls can draw from."""
    rfp_dump = None
    if state.rfp_context:
        rfp_dump = state.rfp_context.model_dump(mode="json")

    ref_index_dump = None
    if state.reference_index:
        ri = state.reference_index
        ref_index_dump = {
            "total_claims": len(ri.claims),
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "claim_text": c.claim_text,
                    "source_doc_id": c.source_doc_id,
                    "evidence_span": c.evidence_span,
                    "confidence": c.confidence,
                    "category": c.category,
                }
                for c in ri.claims[:150]
            ],
            "case_studies": [cs.model_dump(mode="json") for cs in ri.case_studies[:30]],
            "team_profiles": [tp.model_dump(mode="json") for tp in ri.team_profiles[:40]],
            "compliance_evidence": [ce.model_dump(mode="json") for ce in ri.compliance_evidence[:30]],
            "frameworks": [fw.model_dump(mode="json") for fw in ri.frameworks[:15]],
            "gaps": [g.model_dump(mode="json") for g in ri.gaps[:30]],
        }

    ext_evidence_dump = None
    if state.external_evidence_pack:
        ext_evidence_dump = state.external_evidence_pack.model_dump(mode="json")

    strategy_dump = None
    if state.proposal_strategy:
        strategy_dump = state.proposal_strategy.model_dump(mode="json")

    kg_dump = None
    if state.knowledge_graph:
        kg = state.knowledge_graph
        internal_people = [
            p for p in kg.people if p.person_type == "internal_team"
        ]
        kg_dump = {
            # Explicit counts so the LLM knows exactly what data exists
            "_DATA_BOUNDARY": {
                "internal_team_count": len(internal_people),
                "project_count": len(kg.projects),
                "client_count": len(kg.clients),
                "WARNING": (
                    f"You have EXACTLY {len(internal_people)} named team members "
                    f"and {len(kg.projects)} projects in the knowledge graph. "
                    "Do NOT invent additional names or projects beyond this data. "
                    "Use open_role_profile for team roles without KG matches."
                ),
            },
            "people": [
                {
                    "person_id": p.person_id,
                    "name": p.name,
                    "current_role": p.current_role,
                    "company": p.company,
                    "years_experience": p.years_experience,
                    "certifications": p.certifications,
                    "domain_expertise": p.domain_expertise,
                    "projects": p.projects,
                }
                for p in internal_people
            ],
            "projects": [
                {
                    "project_id": pr.project_id,
                    "project_name": pr.project_name,
                    "client": pr.client,
                    "sector": pr.sector,
                    "domain_tags": pr.domain_tags,
                    "outcomes": pr.outcomes,
                    "methodologies": pr.methodologies,
                }
                for pr in kg.projects[:30]
            ],
            "clients": [
                {
                    "client_id": c.client_id,
                    "name": c.name,
                    "client_type": c.client_type,
                    "sector": c.sector,
                }
                for c in kg.clients[:20]
            ],
        }

    # Timeline and team constraints from RFP
    rfp_timeline_dump = None
    rfp_team_requirements_dump = None
    mandatory_constraints: list[str] = []
    if state.rfp_context:
        if state.rfp_context.project_timeline:
            rfp_timeline_dump = state.rfp_context.project_timeline.model_dump(mode="json")
        if state.rfp_context.team_requirements:
            rfp_team_requirements_dump = [
                tr.model_dump(mode="json") for tr in state.rfp_context.team_requirements
            ]

    if rfp_timeline_dump:
        dur = rfp_timeline_dump.get("total_duration", "")
        months = rfp_timeline_dump.get("total_duration_months")
        if dur or months:
            mandatory_constraints.append(
                f"MANDATORY TIMELINE: The RFP states the project duration is "
                f"{dur or str(months) + ' months'}. Use this EXACT duration."
            )
        sched = rfp_timeline_dump.get("deliverable_schedule", [])
        if sched:
            milestones = "; ".join(
                f"{s.get('milestone', '?')} due {s.get('due_date', '?')}" for s in sched
            )
            mandatory_constraints.append(f"MANDATORY MILESTONES: {milestones}")

    if rfp_team_requirements_dump:
        roles = []
        for req in rfp_team_requirements_dump:
            rt = req.get("role_title", {})
            title = rt.get("en") or rt.get("ar") or str(rt)
            edu = req.get("education", "")
            certs = req.get("certifications", [])
            yrs = req.get("min_years_experience")
            parts = [title]
            if edu:
                parts.append(edu)
            if certs:
                parts.append(", ".join(certs))
            if yrs:
                parts.append(f"{yrs}+ years")
            roles.append(" / ".join(parts))
        if roles:
            mandatory_constraints.append(
                "MANDATORY TEAM ROLES (from RFP): "
                + " | ".join(roles)
                + ". Map each RFP role to a proposed consultant."
            )

    available_ext_ids: list[str] = []
    if state.external_evidence_pack:
        for src in getattr(state.external_evidence_pack, "sources", []):
            sid = getattr(src, "source_id", "")
            if sid:
                available_ext_ids.append(sid)

    # B3: Extract mandatory phase structure from deliverable_schedule
    mandatory_phase_structure = None
    if state.rfp_context and state.rfp_context.project_timeline:
        pt = state.rfp_context.project_timeline
        if pt.deliverable_schedule:
            phase_parts = []
            for ds in pt.deliverable_schedule:
                desc = ds.description
                en = getattr(desc, "en", "") or ""
                ar = getattr(desc, "ar", "") or ""
                text = en or ar or ds.deliverable_id
                if text:
                    due = ds.due_at or "unspecified"
                    phase_parts.append(f"- {text} (due: {due})")
            if phase_parts:
                mandatory_phase_structure = "\n".join(phase_parts)

    # B1: Pre-format evaluation model summary from structured evaluation_criteria
    evaluation_model_summary = None
    if state.rfp_context and state.rfp_context.evaluation_criteria:
        ec = state.rfp_context.evaluation_criteria
        parts = []
        if ec.award_mechanism and ec.award_mechanism != "unknown":
            parts.append(f"Award mechanism: {ec.award_mechanism}")
        if ec.technical and ec.technical.weight_pct is not None:
            parts.append(f"Technical weight: {ec.technical.weight_pct}%")
        if ec.financial and ec.financial.weight_pct is not None:
            parts.append(f"Financial weight: {ec.financial.weight_pct}%")
        threshold = ec.technical_passing_threshold or ec.passing_score
        if threshold is not None:
            parts.append(f"Technical passing threshold: {threshold}%")
        if parts:
            evaluation_model_summary = " | ".join(parts)

    # B4: Pre-format scope deliverables summary for problem framing grounding
    scope_deliverables_summary = None
    if state.rfp_context:
        deliv_parts = []
        if state.rfp_context.deliverables:
            for d in state.rfp_context.deliverables[:15]:
                desc = d.description
                en = getattr(desc, "en", "") or ""
                ar = getattr(desc, "ar", "") or ""
                text = en or ar
                if text:
                    mand = " [MANDATORY]" if d.mandatory else ""
                    deliv_parts.append(f"- {d.id}: {text}{mand}")
        if state.rfp_context.scope_items:
            for si in state.rfp_context.scope_items[:10]:
                desc = si.description
                en = getattr(desc, "en", "") or ""
                ar = getattr(desc, "ar", "") or ""
                text = en or ar
                if text:
                    deliv_parts.append(f"- {si.id}: {text}")
        if deliv_parts:
            scope_deliverables_summary = "\n".join(deliv_parts)

    # ── Hard Requirements Summary (conformance architecture) ──────
    # Build compact summary from extracted hard requirements.
    # Filtered to validation_scope == "source_book" only.
    hard_requirements_summary = None
    if state.rfp_context and state.rfp_context.hard_requirements:
        from src.models.conformance import (
            HardRequirementsSummary,
            HardRequirementSummaryItem,
        )

        source_book_reqs = [
            hr for hr in state.rfp_context.hard_requirements
            if hr.validation_scope == "source_book"
        ]
        items = [
            HardRequirementSummaryItem(
                id=hr.requirement_id,
                obligation=f"{hr.subject} {hr.operator} {hr.value_text} ({hr.unit})",
                severity=hr.severity,
                phase=hr.phase,
            )
            for hr in source_book_reqs
        ]
        hard_requirements_summary = HardRequirementsSummary(
            requirements=items,
            total_count=len(items),
            critical_count=sum(1 for hr in source_book_reqs if hr.severity == "critical"),
        ).model_dump(mode="json")

    return {
        "mandatory_constraints": mandatory_constraints or None,
        "available_ext_ids": available_ext_ids or None,
        "evaluation_model_summary": evaluation_model_summary,
        "scope_deliverables_summary": scope_deliverables_summary,
        "mandatory_phase_structure": mandatory_phase_structure,
        "hard_requirements_summary": hard_requirements_summary,
        "rfp_context": rfp_dump,
        "rfp_project_timeline": rfp_timeline_dump,
        "rfp_team_requirements": rfp_team_requirements_dump,
        "reference_index": ref_index_dump,
        "knowledge_graph": kg_dump,
        "external_evidence_pack": ext_evidence_dump,
        "proposal_strategy": strategy_dump,
        "reviewer_feedback": reviewer_feedback or None,
        "output_language": state.output_language,
        "sector": state.sector,
        "geography": state.geography,
    }


def _build_stage_payload(
    shared_ctx: dict,
    previous_section_data: dict | None = None,
    keep_keys: list[str] | None = None,
    drop_keys: list[str] | None = None,
) -> str:
    """Build a JSON payload for a stage call with context filtering.

    Args:
        shared_ctx: Full shared context from _build_shared_context.
        previous_section_data: Previous section output for rewrite passes.
        keep_keys: If provided, ONLY include these keys from shared_ctx.
        drop_keys: If provided, DROP these keys from shared_ctx.

    This ensures each stage receives only the context it needs, keeping
    the input payload small enough that max_tokens isn't consumed by input.

    On rewrite passes (previous_section_data present), the rfp_context is
    condensed to essential fields only — the LLM already has the reviewer
    feedback and previous output telling it what to fix, so the full RFP
    dump is redundant and wastes token budget needed for output quality.
    """
    # INVARIANT: hard_requirements_summary is NEVER dropped from context.
    # This ensures the writer always sees the full obligation list.
    if drop_keys and "hard_requirements_summary" in drop_keys:
        drop_keys = [k for k in drop_keys if k != "hard_requirements_summary"]
    if keep_keys and "hard_requirements_summary" not in keep_keys:
        keep_keys = [*keep_keys, "hard_requirements_summary"]

    if keep_keys:
        payload = {k: shared_ctx[k] for k in keep_keys if k in shared_ctx}
    elif drop_keys:
        payload = {k: v for k, v in shared_ctx.items() if k not in drop_keys}
    else:
        payload = dict(shared_ctx)

    if previous_section_data:
        payload["previous_section_content"] = previous_section_data

        # Condense rfp_context on rewrite passes to preserve output token budget.
        # Keep: rfp_name, mandate, scope_items, deliverables, compliance,
        #        evaluation_criteria, key_dates, team_requirements.
        # Drop: verbose nested sub-objects that were already digested in pass 1.
        if "rfp_context" in payload and payload["rfp_context"] is not None:
            full_ctx = payload["rfp_context"]
            if isinstance(full_ctx, dict):
                payload["rfp_context"] = {
                    k: full_ctx[k]
                    for k in [
                        "rfp_name", "issuing_entity", "mandate",
                        "scope_items", "deliverables",
                        "compliance_requirements", "evaluation_criteria",
                        "key_dates", "team_requirements",
                        "project_timeline", "procurement_platform",
                    ]
                    if k in full_ctx
                }

    return json.dumps(payload, ensure_ascii=False, default=str)


def _dump_sections_15(source_book: SourceBook) -> str:
    """Serialize Sections 1-5 as JSON context for Stage 2a/2b."""
    return json.dumps(
        {
            "client_name": source_book.client_name,
            "rfp_name": source_book.rfp_name,
            "language": source_book.language,
            "rfp_interpretation": source_book.rfp_interpretation.model_dump(mode="json"),
            "client_problem_framing": source_book.client_problem_framing.model_dump(mode="json"),
            "why_strategic_gears": source_book.why_strategic_gears.model_dump(mode="json"),
            "external_evidence": source_book.external_evidence.model_dump(mode="json"),
            "proposed_solution": source_book.proposed_solution.model_dump(mode="json"),
        },
        ensure_ascii=False,
        default=str,
    )


async def _generate_section_1(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
):
    """Stage 1a: Section 1 (RFP Interpretation) + metadata.

    Split into TWO LLM calls so each gets a focused schema and full token budget:
      Call 1 (_Section1Prose): 7 fields — forensic prose analysis
      Call 2 (_Section1Classification): 6 fields — structured evidence rows

    The LLM consistently fills simple types (str, list[str]) but skips complex
    nested Pydantic models when both are in the same schema. Splitting forces
    each call to produce quality content for its subset of fields.

    Returns: (SourceBookSection1, LLMResponse_prose, LLMResponse_classification)
    Caller must accumulate BOTH LLM responses for session accounting.
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "rfp_interpretation": previous_book.rfp_interpretation.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        drop_keys=["knowledge_graph", "external_evidence_pack"],
    )
    logger.info("Stage 1a (Section 1 — RFP Interpretation): input chars=%d", len(payload))

    # ── Call 1: Prose interpretation ──────────────────────────────
    prose_result = await call_llm(
        model=model,
        system_prompt=STAGE1A_SECTION1_PROMPT,
        user_message=payload,
        response_model=_Section1Prose,
        max_tokens=16000,
        temperature=0.1,
    )
    prose = prose_result.parsed
    logger.info(
        "Stage 1a-prose complete: scope_words=%d, compliance_items=%d, assumptions=%d, ambiguities=%d",
        len(prose.objective_and_scope.split()),
        len(prose.key_compliance_requirements),
        len(prose.assumptions),
        len(prose.ambiguities),
    )

    # ── Call 2: Structured classification ─────────────────────────
    # On rewrite: build a compact payload with condensed rfp_context +
    # previous classification output (for improvement) + reviewer feedback.
    # On first pass: use the same payload as prose (full rfp_context is fine
    # since there's no previous content inflating the input).
    if previous_book:
        # Rewrite: condensed rfp_context + previous classification for improvement
        rfp_ctx = shared_ctx.get("rfp_context")
        condensed_rfp = None
        if rfp_ctx and isinstance(rfp_ctx, dict):
            condensed_rfp = {
                k: rfp_ctx[k]
                for k in [
                    "rfp_name", "issuing_entity", "mandate",
                    "scope_items", "deliverables",
                    "compliance_requirements", "evaluation_criteria",
                    "key_dates", "team_requirements",
                    "project_timeline", "procurement_platform",
                ]
                if k in rfp_ctx
            }

        prev_classification = {
            "explicit_requirements": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.explicit_requirements],
            "inferred_requirements": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.inferred_requirements],
            "external_support": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.external_support],
            "compliance_rows": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.compliance_rows],
            "delivery_control_rows": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.delivery_control_rows],
            "evaluation_hypotheses": [r.model_dump(mode="json") for r in previous_book.rfp_interpretation.evaluation_hypotheses],
        }

        classification_payload = json.dumps({
            "rfp_context": condensed_rfp,
            "previous_classification": prev_classification,
            "requirement_density": shared_ctx.get("requirement_density", "medium"),
            "reviewer_feedback": shared_ctx.get("reviewer_feedback"),
            "output_language": shared_ctx.get("output_language"),
            "sector": shared_ctx.get("sector"),
            "geography": shared_ctx.get("geography"),
        }, ensure_ascii=False, default=str)
    else:
        # First pass: same payload as prose (no previous content bloat)
        classification_payload = _build_stage_payload(
            shared_ctx, None,
            drop_keys=["knowledge_graph", "external_evidence_pack"],
        )

    classification_result = await call_llm(
        model=model,
        system_prompt=STAGE1A_CLASSIFICATION_PROMPT,
        user_message=classification_payload,
        response_model=_Section1Classification,
        max_tokens=16000,
        temperature=0.1,
    )
    classification = classification_result.parsed
    logger.info(
        "Stage 1a-classification complete: explicit=%d, inferred=%d, compliance_rows=%d, delivery_rows=%d, eval_hypotheses=%d",
        len(classification.explicit_requirements),
        len(classification.inferred_requirements),
        len(classification.compliance_rows),
        len(classification.delivery_control_rows),
        len(classification.evaluation_hypotheses),
    )

    # ── Assemble RFPInterpretation from both calls ────────────────
    rfp_interp = RFPInterpretation(
        objective_and_scope=prose.objective_and_scope,
        constraints_and_compliance=prose.constraints_and_compliance,
        unstated_evaluator_priorities=prose.unstated_evaluator_priorities,
        probable_scoring_logic=prose.probable_scoring_logic,
        key_compliance_requirements=prose.key_compliance_requirements,
        assumptions=prose.assumptions,
        ambiguities=prose.ambiguities,
        explicit_requirements=classification.explicit_requirements,
        inferred_requirements=classification.inferred_requirements,
        external_support=classification.external_support,
        compliance_rows=classification.compliance_rows,
        delivery_control_rows=classification.delivery_control_rows,
        evaluation_hypotheses=classification.evaluation_hypotheses,
    )

    logger.info(
        "Stage 1a complete: compliance_items=%d, scope_words=%d",
        len(rfp_interp.key_compliance_requirements),
        len(rfp_interp.objective_and_scope.split()),
    )

    # Assemble the wrapper with metadata from state context
    rfp_ctx = shared_ctx.get("rfp_context") or {}
    rfp_name = rfp_ctx.get("rfp_name", {})
    s1 = SourceBookSection1(
        client_name=rfp_ctx.get("issuing_entity", {}).get("en", "") if isinstance(rfp_ctx.get("issuing_entity"), dict) else str(rfp_ctx.get("issuing_entity", "")),
        rfp_name=rfp_name.get("en", "") if isinstance(rfp_name, dict) else str(rfp_name),
        language=str(shared_ctx.get("output_language", "en")),
        generation_date=__import__("datetime").date.today().isoformat(),
        rfp_interpretation=rfp_interp,
        requirement_density=shared_ctx.get("requirement_density", "medium"),
    )
    return s1, prose_result, classification_result


async def _generate_section_2(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
):
    """Stage 1b: Section 2 (Client Problem Framing).

    Calls the LLM with ClientProblemFraming directly (not SourceBookSection2
    wrapper) so the model focuses 100% of output tokens on the 4 prose fields.
    The wrapper is assembled on the Python side.

    Drops: knowledge_graph, external_evidence_pack, reference_index (not needed
    for problem framing — this section is about the client's situation).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "client_problem_framing": previous_book.client_problem_framing.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        keep_keys=[
            "rfp_context", "proposal_strategy", "mandatory_constraints",
            "reviewer_feedback", "output_language", "sector", "geography",
        ],
    )
    logger.info("Stage 1b (Section 2 — Problem Framing): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1B_SECTION2_PROMPT,
        user_message=payload,
        response_model=_Section2Validated,
        max_tokens=16000,
        temperature=0.1,
    )

    validated = result.parsed
    cpf = ClientProblemFraming(
        current_state_challenge=validated.current_state_challenge,
        why_it_matters_now=validated.why_it_matters_now,
        transformation_logic=validated.transformation_logic,
        risk_if_unchanged=validated.risk_if_unchanged,
    )
    s2 = SourceBookSection2(client_problem_framing=cpf)
    total_words = sum(
        len(getattr(cpf, f, "").split())
        for f in ["current_state_challenge", "why_it_matters_now",
                   "transformation_logic", "risk_if_unchanged"]
    )
    logger.info(
        "Stage 1b complete: problem_framing_words=%d",
        total_words,
    )
    return s2, result


async def _generate_section_3(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection3:
    """Stage 1b: Section 3 (Why Strategic Gears).

    Needs: knowledge_graph (team, projects), reference_index, mandatory_constraints
    (for team roles), rfp_team_requirements, proposal_strategy, available_ext_ids.
    Drops: full rfp_context (too large), external_evidence_pack (not needed here).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "why_strategic_gears": previous_book.why_strategic_gears.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        keep_keys=[
            "knowledge_graph", "reference_index", "mandatory_constraints",
            "rfp_team_requirements", "proposal_strategy", "available_ext_ids",
            "reviewer_feedback", "output_language", "sector", "geography",
        ],
    )
    logger.info("Stage 1b (Section 3): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1B_SECTION3_PROMPT,
        user_message=payload,
        response_model=SourceBookSection3,
        max_tokens=24000,
        temperature=0.1,
    )

    s3 = result.parsed
    logger.info(
        "Stage 1b complete: consultants=%d, projects=%d, capabilities=%d",
        len(s3.why_strategic_gears.named_consultants),
        len(s3.why_strategic_gears.project_experience),
        len(s3.why_strategic_gears.capability_mapping),
    )
    return s3, result


async def _generate_section_4(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection4:
    """Stage 1c: Section 4 (External Evidence).

    Needs: external_evidence_pack, available_ext_ids, proposal_strategy.
    Drops: rfp_context, knowledge_graph, reference_index (not needed for evidence curation).
    """
    prev_data = None
    if previous_book:
        prev_data = {
            "external_evidence": previous_book.external_evidence.model_dump(mode="json"),
        }
    payload = _build_stage_payload(
        shared_ctx, prev_data,
        keep_keys=[
            "external_evidence_pack", "available_ext_ids", "proposal_strategy",
            "reviewer_feedback", "output_language",
        ],
    )
    logger.info("Stage 1c (Section 4): input chars=%d", len(payload))

    result = await call_llm(
        model=model,
        system_prompt=STAGE1C_SECTION4_PROMPT,
        user_message=payload,
        response_model=SourceBookSection4,
        max_tokens=16000,
        temperature=0.1,
    )

    s4 = result.parsed
    logger.info(
        "Stage 1c complete: evidence_entries=%d",
        len(s4.external_evidence.entries),
    )
    return s4, result


def _build_section5_payload(shared_ctx: dict, prev_fields: dict | None = None) -> str:
    """Build the RFP-rich payload for Section 5 calls.

    Keeps ALL fields needed for elite methodology (scope, deliverables,
    evaluation criteria, compliance, team requirements, timeline, mandate)
    but drops raw document text and KG data that don't inform methodology.
    """
    rfp_for_methodology = None
    if shared_ctx.get("rfp_context"):
        rfp = shared_ctx["rfp_context"]
        rfp_for_methodology = {
            "rfp_name": rfp.get("rfp_name", ""),
            "issuing_entity": rfp.get("issuing_entity", ""),
            "mandate": rfp.get("mandate", ""),
            "scope_items": rfp.get("scope_items", []),
            "deliverables": rfp.get("deliverables", []),
            "evaluation_criteria": rfp.get("evaluation_criteria"),
            "compliance_requirements": rfp.get("compliance_requirements", []),
            "team_requirements": rfp.get("team_requirements", []),
            "project_timeline": rfp.get("project_timeline"),
        }

    compact_ref_index = None
    ref_index = shared_ctx.get("reference_index")
    if ref_index:
        compact_ref_index = {
            "total_claims": ref_index.get("total_claims", 0),
            "claim_ids_available": [
                c.get("claim_id", "") for c in ref_index.get("claims", [])
            ],
            "frameworks": ref_index.get("frameworks", []),
        }

    payload_dict = {
        "mandatory_constraints": shared_ctx.get("mandatory_constraints"),
        "rfp_project_timeline": shared_ctx.get("rfp_project_timeline"),
        "rfp_team_requirements": shared_ctx.get("rfp_team_requirements"),
        "rfp_context": rfp_for_methodology,
        "proposal_strategy": shared_ctx.get("proposal_strategy"),
        "reference_index_summary": compact_ref_index,
        "available_ext_ids": shared_ctx.get("available_ext_ids"),
        "reviewer_feedback": shared_ctx.get("reviewer_feedback"),
        "output_language": shared_ctx.get("output_language"),
        "sector": shared_ctx.get("sector"),
        "geography": shared_ctx.get("geography"),
    }
    if prev_fields:
        payload_dict["previous_section_content"] = prev_fields

    return json.dumps(payload_dict, ensure_ascii=False, default=str)


async def _generate_section_5(
    shared_ctx: dict,
    model: str,
    previous_book: SourceBook | None = None,
) -> SourceBookSection5:
    """Stage 1e: Section 5 (Proposed Solution — highest weight).

    Split into two calls so each gets the full 32K token budget:
    - Call 1: methodology_overview + phase_details
    - Call 2: governance_framework + timeline_logic + value_case_and_differentiation

    Results are deterministically merged into a single ProposedSolution.
    If either call fails, the entire stage fails (no partial results).
    """
    # Previous data for rewrite passes — split by ownership
    # Condense phase_details to skeleton (names + durations) to avoid
    # inflating the rewrite payload beyond the output token budget.
    prev_methodology = None
    prev_governance = None
    if previous_book:
        ps = previous_book.proposed_solution
        condensed_phases = [
            {
                "phase_name": p.phase_name,
                "duration": getattr(p, "duration", ""),
                "activities_count": len(getattr(p, "activities", [])),
                "deliverables_count": len(getattr(p, "deliverables", [])),
            }
            for p in ps.phase_details
        ]
        prev_methodology = {
            "methodology_overview": ps.methodology_overview[:2000],
            "phase_skeleton": condensed_phases,
            "original_phase_count": len(ps.phase_details),
        }
        prev_governance = {
            "governance_framework": ps.governance_framework,
            "timeline_logic": ps.timeline_logic,
            "value_case_and_differentiation": ps.value_case_and_differentiation,
        }

    # ── Call 1: Methodology + Phases ──────────────────────
    payload_1 = _build_section5_payload(shared_ctx, prev_methodology)
    logger.info("Stage 1e-i (Section 5 methodology): input chars=%d", len(payload_1))

    result_1 = await call_llm(
        model=model,
        system_prompt=STAGE1E_METHODOLOGY_PROMPT,
        user_message=payload_1,
        response_model=_Section5Methodology,
        max_tokens=32000,
        temperature=0.1,
    )
    meth = result_1.parsed
    logger.info(
        "Stage 1e-i complete: methodology_words=%d, phases=%d",
        len(meth.methodology_overview.split()),
        len(meth.phase_details),
    )

    # ── Call 2: Governance + Timeline + Value Case ────────
    payload_2 = _build_section5_payload(shared_ctx, prev_governance)
    logger.info("Stage 1e-ii (Section 5 governance): input chars=%d", len(payload_2))

    result_2 = await call_llm(
        model=model,
        system_prompt=STAGE1E_GOVERNANCE_PROMPT,
        user_message=payload_2,
        response_model=_Section5Governance,
        max_tokens=32000,
        temperature=0.1,
    )
    gov = result_2.parsed
    logger.info(
        "Stage 1e-ii complete: governance_len=%d, timeline_len=%d, value_len=%d",
        len(gov.governance_framework),
        len(gov.timeline_logic),
        len(gov.value_case_and_differentiation),
    )

    # ── Deterministic merge into ProposedSolution ─────────
    merged = ProposedSolution(
        methodology_overview=meth.methodology_overview,
        phase_details=meth.phase_details,
        governance_framework=gov.governance_framework,
        timeline_logic=gov.timeline_logic,
        value_case_and_differentiation=gov.value_case_and_differentiation,
    )

    logger.info(
        "Stage 1e merge complete: phases=%d, governance_len=%d, methodology_len=%d",
        len(merged.phase_details),
        len(merged.governance_framework),
        len(merged.methodology_overview),
    )

    return SourceBookSection5(proposed_solution=merged), result_1, result_2


async def _generate_blueprints(
    source_book: SourceBook,
    model: str,
    state: DeckForgeState | None = None,
) -> SourceBookSection6:
    """Stage 2a: Dedicated LLM call for slide blueprints only.

    Injects claim discipline rules based on KG data availability.
    """
    context = _dump_sections_15(source_book)

    # Inject claim discipline into context based on proof state
    claim_discipline = ""
    if state:
        kg = state.knowledge_graph
        kg_people = 0
        kg_projects = 0
        if kg:
            kg_people = len([p for p in kg.people if p.person_type == "internal_team"])
            kg_projects = len(kg.projects)

        if kg_people == 0 or kg_projects <= 1:
            claim_discipline = """

*** CLAIM DISCIPLINE — MANDATORY FOR THIS RUN ***

The knowledge graph has {people} named team members and {projects} projects.
You MUST follow these rules for team and capability slides:

FOR TEAM SLIDES (S07, S12, S13, S14):
- ALLOWED: "تصميم فريق مقترح", "هيكل فريق يطابق متطلبات الأدوار المستهدفة",
  "ملفات أدوار مفتوحة لحين تأكيد التعيينات", "تغطية منهجية قوية"
- FORBIDDEN: "يستوفي كل عضو جميع الشروط", "خبرة مباشرة موثقة",
  "مطابقة 100%", "استيفاء كامل", "فريق مؤكد", "قدرات مثبتة بالكامل"

FOR CAPABILITY SLIDES (S07):
- ALLOWED: "قدرات مطلوبة ومدعومة بأطر مرجعية دولية",
  "تصميم مقترح يستند إلى أطر دولية وخبرة قابلة للاستكمال"
- FORBIDDEN: "كل متطلب مغطى بقدرة مثبتة", "خبرة مباشرة" without Engine 2 proof

Use conditional language: "مُصمَّم لاستيفاء", "مطلوبة", "مُستهدَف"
instead of: "يستوفي", "موثقة", "مثبتة", "كامل"
""".format(people=kg_people, projects=kg_projects)

    full_context = context + claim_discipline
    logger.info("Stage 2a (blueprints): input chars=%d (discipline=%d chars)",
                len(full_context), len(claim_discipline))

    result = await call_llm(
        model=model,
        system_prompt=STAGE2A_BLUEPRINTS_PROMPT,
        user_message=full_context,
        response_model=SourceBookSection6,
        max_tokens=48000,
        temperature=0.1,
    )

    section6 = result.parsed
    logger.info("Stage 2a produced: %d blueprints", len(section6.slide_blueprints))
    return section6, result


async def _generate_evidence_ledger(
    source_book: SourceBook,
    model: str,
) -> SourceBookSection7:
    """Stage 2b: Dedicated LLM call for evidence ledger only."""
    context = json.dumps(
        {
            "sections_1_5": json.loads(_dump_sections_15(source_book)),
            "slide_blueprints": [
                bp.model_dump(mode="json") for bp in source_book.slide_blueprints
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    logger.info("Stage 2b (evidence ledger): input chars=%d", len(context))

    result = await call_llm(
        model=model,
        system_prompt=STAGE2B_EVIDENCE_LEDGER_PROMPT,
        user_message=context,
        response_model=SourceBookSection7,
        max_tokens=16000,
        temperature=0.1,
    )

    section7 = result.parsed
    logger.info(
        "Stage 2b produced: %d evidence entries",
        len(section7.evidence_ledger.entries),
    )
    return section7, result


async def run(
    state: DeckForgeState,
    reviewer_feedback: str = "",
    pack_context: dict | None = None,
) -> dict:
    """Run the Source Book Writer agent (seven-stage split-call architecture).

    Stage 1a: Section 1 (RFP Interpretation)
    Stage 1b: Section 2 (Client Problem Framing)
    Stage 1c: Section 3 (Why Strategic Gears)
    Stage 1d: Section 4 (External Evidence)
    Stage 1e: Section 5 (Proposed Solution / Methodology)
    Stage 2a: Section 6 (Slide blueprints)
    Stage 2b: Section 7 (Evidence ledger)

    Each stage gets its own LLM call and dedicated token budget.
    pack_context: merged context packs from routing (if available).
    """
    model = MODEL_MAP.get("source_book_writer", MODEL_MAP.get("analysis_agent"))

    # Track fallback usage per pass
    fallback_events: list[str] = []

    # Determine pass number
    current_pass = 1
    if state.source_book:
        current_pass = state.source_book.pass_number + 1

    shared_ctx = _build_shared_context(state, reviewer_feedback=reviewer_feedback)

    # ── Pre-generation: requirement density detection ──────
    from .requirement_detector import detect_requirement_density
    density_analysis = detect_requirement_density(state)
    shared_ctx["requirement_density"] = density_analysis.density
    shared_ctx["density_signals"] = density_analysis.signals
    shared_ctx["should_generate_compliance_matrix"] = density_analysis.should_generate_compliance_matrix
    shared_ctx["should_generate_delivery_matrix"] = density_analysis.should_generate_delivery_matrix
    shared_ctx["should_generate_ambiguity_table"] = density_analysis.should_generate_ambiguity_table
    logger.info(
        "Requirement density: %s (prescriptive=%d, deliverables=%d, eval=%d)",
        density_analysis.density,
        density_analysis.prescriptive_count,
        density_analysis.deliverable_count,
        density_analysis.evaluation_count,
    )

    # Inject pack context into shared context if available
    if pack_context:
        shared_ctx["pack_context"] = pack_context
        logger.info(
            "Writer received pack context: %d packs, %d search queries",
            len(pack_context.get("active_packs", [])),
            len(pack_context.get("recommended_search_queries", [])),
        )
    previous_book = state.source_book if state.source_book and current_pass > 1 else None

    logger.info(
        "Source Book Writer: pass=%d, has_ref_index=%s, has_strategy=%s, rewrite=%s",
        current_pass,
        state.reference_index is not None,
        state.proposal_strategy is not None,
        bool(reviewer_feedback),
    )

    try:
        from src.services.session_accounting import update_session_from_llm
        accumulated_session = state.session.model_copy(deep=True)

        # ── Stage 1a: Section 1 (RFP Interpretation) ──────────
        # Split into 2 calls: prose + classification. Both return LLM responses.
        s1, s1_prose_llm, s1_class_llm = await _generate_section_1(shared_ctx, model, previous_book)
        accumulated_session = update_session_from_llm(accumulated_session, s1_prose_llm)
        accumulated_session = update_session_from_llm(accumulated_session, s1_class_llm)

        # ── Stage 1b: Section 2 (Client Problem Framing) ──────
        s2, s2_llm = await _generate_section_2(shared_ctx, model, previous_book)
        accumulated_session = update_session_from_llm(accumulated_session, s2_llm)

        # ── Stage 1c: Section 3 (Why Strategic Gears) ─────────
        s3, s3_llm = await _generate_section_3(shared_ctx, model, previous_book)
        accumulated_session = update_session_from_llm(accumulated_session, s3_llm)

        # ── Stage 1d: Section 4 (External Evidence) ───────────
        s4, s4_llm = await _generate_section_4(shared_ctx, model, previous_book)
        accumulated_session = update_session_from_llm(accumulated_session, s4_llm)

        # ── Stage 1e: Section 5 (Proposed Solution) ───────────
        s5, s5_llm_1, s5_llm_2 = await _generate_section_5(shared_ctx, model, previous_book)
        accumulated_session = update_session_from_llm(accumulated_session, s5_llm_1)
        accumulated_session = update_session_from_llm(accumulated_session, s5_llm_2)

        # ── Assemble SourceBook from split-call outputs ────────
        source_book = SourceBook(
            client_name=s1.client_name,
            rfp_name=s1.rfp_name,
            language=s1.language,
            generation_date=s1.generation_date,
            rfp_interpretation=s1.rfp_interpretation,
            client_problem_framing=s2.client_problem_framing,
            why_strategic_gears=s3.why_strategic_gears,
            external_evidence=s4.external_evidence,
            proposed_solution=s5.proposed_solution,
            pass_number=current_pass,
            requirement_density=getattr(s1, "requirement_density", density_analysis.density),
        )

        # Deduplicate projects by case-insensitive name
        if source_book.why_strategic_gears.project_experience:
            seen: dict[str, bool] = {}
            unique_projects = []
            for proj in source_book.why_strategic_gears.project_experience:
                key = proj.project_name.strip().lower()
                if key not in seen:
                    seen[key] = True
                    unique_projects.append(proj)
            if len(unique_projects) < len(source_book.why_strategic_gears.project_experience):
                logger.info(
                    "Deduped projects: %d → %d",
                    len(source_book.why_strategic_gears.project_experience),
                    len(unique_projects),
                )
            source_book.why_strategic_gears.project_experience = unique_projects

        logger.info(
            "Stage 1 complete: pass=%d, capabilities=%d, consultants=%d, projects=%d",
            current_pass,
            len(source_book.why_strategic_gears.capability_mapping),
            len(source_book.why_strategic_gears.named_consultants),
            len(source_book.why_strategic_gears.project_experience),
        )

        # ── Engine 1 / Engine 2 Guard ─────────────────────────
        # Validate consultant names and projects against actual KG data.
        # Strip anything the LLM fabricated that doesn't exist in the KG.
        source_book = _engine1_guard(source_book, state)

        # ── Stage 2a: Section 6 (blueprints) ──────────────────
        section6, s6_llm = await _generate_blueprints(source_book, model, state=state)
        accumulated_session = update_session_from_llm(accumulated_session, s6_llm)
        source_book.slide_blueprints = section6.slide_blueprints

        if not source_book.slide_blueprints:
            logger.error(
                "Stage 2a produced 0 blueprints on pass %d — this is a hard failure. "
                "Check max_tokens and input payload size.",
                current_pass,
            )

        # ── Post-blueprint overclaim scan ─────────────────────
        # Must run AFTER Stage 2a so the newly generated blueprints
        # are scanned for certainty language about team/proof.
        source_book = _engine1_blueprint_overclaim_scan(source_book, state)

        # ── Stage 2b: Section 7 (evidence ledger) ─────────────
        section7, s7_llm = await _generate_evidence_ledger(source_book, model)
        accumulated_session = update_session_from_llm(accumulated_session, s7_llm)
        source_book.evidence_ledger = section7.evidence_ledger

        if not source_book.evidence_ledger.entries:
            logger.warning(
                "Stage 2b produced 0 evidence entries on pass %d — "
                "evidence extractor will run post-loop to populate.",
                current_pass,
            )

        # ── EXT citation coherence check ─────────────────────
        source_book = _strip_dangling_ext_citations(source_book, state)

        # ── Hedge scanner ──────────────────────────────────────
        hedges = _scan_for_hedges(source_book)
        if hedges:
            logger.warning("Hedge scanner found %d banned phrases: %s", len(hedges), ", ".join(hedges))
            source_book, hedge_llm = await _rewrite_hedges(source_book, hedges)
            if hedge_llm:
                accumulated_session = update_session_from_llm(accumulated_session, hedge_llm)
            remaining = _scan_for_hedges(source_book)
            if remaining:
                logger.warning("Hedge rewrite: %d phrases remain — second pass", len(remaining))
                source_book, hedge_llm_2 = await _rewrite_hedges(source_book, remaining)
                if hedge_llm_2:
                    accumulated_session = update_session_from_llm(accumulated_session, hedge_llm_2)
        else:
            logger.info("Hedge scanner: zero banned phrases found")

        # ── Assertion classification enforcement ──────────────
        from .assertion_classifier import enforce_classification
        classification_report = enforce_classification(source_book)
        logger.info(
            "Assertion classifier: claims=%d, fixed=%d, absolutes=%d, "
            "benchmark_gov=%d, inference_render=%d",
            classification_report.total_claims_checked,
            classification_report.misclassified_fixed,
            classification_report.absolutes_softened,
            classification_report.benchmark_governance_fixes,
            classification_report.inference_rendering_fixes,
        )

        # ── Cross-section coherence validation ────────────────
        from .coherence_validator import validate_coherence
        coherence_result = validate_coherence(source_book)
        if coherence_result.issues:
            logger.warning(
                "Coherence validator: %d issues found: %s",
                len(coherence_result.issues),
                "; ".join(coherence_result.issues[:5]),
            )
        if coherence_result.absolutes_found:
            logger.warning(
                "Coherence validator: %d unsupported absolutes remain: %s",
                len(coherence_result.absolutes_found),
                "; ".join(coherence_result.absolutes_found[:3]),
            )

        logger.info(
            "Source Book written: pass=%d, blueprints=%d, evidence=%d, capabilities=%d",
            current_pass,
            len(source_book.slide_blueprints),
            len(source_book.evidence_ledger.entries),
            len(source_book.why_strategic_gears.capability_mapping),
        )

        return {
            "source_book": source_book,
            "session": accumulated_session,
            "fallback_events": fallback_events,
        }

    except Exception as e:
        logger.error("Source Book Writer failed: %s", e)
        from src.models.state import ErrorInfo

        preserved_book = state.source_book if state.source_book else SourceBook(
            rfp_interpretation=RFPInterpretation(
                objective_and_scope="Source Book generation failed.",
            ),
        )

        return {
            "source_book": preserved_book,
            "errors": state.errors + [
                ErrorInfo(
                    agent="source_book_writer",
                    error_type="LLMError",
                    message=str(e),
                ),
            ],
            "last_error": ErrorInfo(
                agent="source_book_writer",
                error_type="LLMError",
                message=str(e),
            ),
        }


# ── Legacy compatibility ──────────────────────────────────────
# Keep _build_user_message available for any code that imports it
def _build_user_message(state: DeckForgeState, reviewer_feedback: str = "") -> str:
    """Build user message (legacy — used by tests)."""
    ctx = _build_shared_context(state, reviewer_feedback)
    return json.dumps(ctx, ensure_ascii=False, default=str)
