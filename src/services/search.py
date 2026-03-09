"""Local search stub — replaces Azure AI Search for local development.

Reads files from a local docs directory and returns them as search results
matching the format expected by the Retrieval Ranker agent.

Production equivalent: Azure AI Search with pre-indexed SharePoint content.
"""

from pathlib import Path

from src.models.retrieval import SearchQuery


async def local_search(
    queries: list[SearchQuery],
    docs_path: str = "./test_docs",
) -> list[dict]:
    """Search local documents and return results for the Retrieval Ranker.

    For each file in docs_path, returns a search result dict with:
      - doc_id: filename-based ID (DOC-001, DOC-002, ...)
      - title: filename without extension
      - excerpt: first 500 chars of file content
      - metadata: {filename, path, size_bytes}
      - search_score: 0.8 (static for local dev)

    In production, this is replaced by Azure AI Search vector + keyword
    hybrid search with real relevance scores.
    """
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        return []

    results: list[dict] = []
    doc_counter = 0

    for filepath in sorted(docs_dir.iterdir()):
        if not filepath.is_file():
            continue
        # Skip hidden files and non-document extensions
        if filepath.name.startswith("."):
            continue

        doc_counter += 1
        doc_id = f"DOC-{doc_counter:03d}"

        # Read content (text files only for local dev)
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            content = ""

        excerpt = content[:500] if content else ""

        results.append({
            "doc_id": doc_id,
            "title": filepath.stem,
            "excerpt": excerpt,
            "metadata": {
                "filename": filepath.name,
                "path": str(filepath),
                "size_bytes": filepath.stat().st_size if filepath.exists() else 0,
            },
            "search_score": 0.8,
        })

    return results


async def load_documents(
    approved_ids: list[str],
    docs_path: str = "./test_docs",
) -> list[dict]:
    """Load full document content for approved source IDs.

    Used by the Analysis pipeline node to provide document content
    to the Analysis Agent. In production, this reads from SharePoint
    via Graph API.

    Returns list of dicts with: doc_id, title, content_text, metadata.
    """
    # First, get all available docs with their IDs
    all_results = await local_search([], docs_path)

    # Filter to approved IDs only
    approved = [r for r in all_results if r["doc_id"] in approved_ids]

    documents: list[dict] = []
    for result in approved:
        # Read full content (not just excerpt)
        filepath = Path(result["metadata"]["path"])
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            content = result["excerpt"]

        documents.append({
            "doc_id": result["doc_id"],
            "title": result["title"],
            "content_text": content,
            "metadata": result["metadata"],
        })

    return documents
