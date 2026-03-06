"""ID generators following Appendix C patterns. IDs are immutable once assigned."""

from threading import Lock

_counters: dict[str, int] = {}
_lock = Lock()


def _next_id(prefix: str, width: int) -> str:
    """Generate the next sequential ID for a given prefix."""
    with _lock:
        current = _counters.get(prefix, 0) + 1
        _counters[prefix] = current
        return f"{prefix}-{str(current).zfill(width)}"


def next_claim_id() -> str:
    """CLM-NNNN — unique per Reference Index."""
    return _next_id("CLM", 4)


def next_gap_id() -> str:
    """GAP-NNN — unique per Reference Index."""
    return _next_id("GAP", 3)


def next_doc_id() -> str:
    """DOC-NNN — unique per SharePoint index."""
    return _next_id("DOC", 3)


def next_slide_id() -> str:
    """S-NNN — unique per deck session."""
    return _next_id("S", 3)


def next_scope_id() -> str:
    """SCOPE-NNN — unique per RFP object."""
    return _next_id("SCOPE", 3)


def next_deliverable_id() -> str:
    """DEL-NNN — unique per RFP object."""
    return _next_id("DEL", 3)


def next_compliance_id() -> str:
    """COMP-NNN — unique per RFP object."""
    return _next_id("COMP", 3)


def next_waiver_id() -> str:
    """WVR-NNN — unique per deck session."""
    return _next_id("WVR", 3)


def next_section_id() -> str:
    """SEC-NN — unique per Research Report."""
    return _next_id("SEC", 2)


def reset_counters() -> None:
    """Reset all counters — call at session start."""
    with _lock:
        _counters.clear()
