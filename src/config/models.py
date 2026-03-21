"""Model name to API config mapping for all DeckForge agents."""

from src.config.settings import get_settings


def _build_model_map() -> dict[str, str]:
    """Build MODEL_MAP from current settings."""
    settings = get_settings()
    return {
        "context_agent": settings.openai_model_gpt54,
        "retrieval_planner": settings.openai_model_gpt54,
        "retrieval_ranker": settings.openai_model_gpt54,
        "analysis_agent": settings.anthropic_model_opus,
        "research_agent": settings.anthropic_model_opus,
        "structure_agent": settings.openai_model_gpt54,
        "content_agent": settings.openai_model_gpt54,
        "qa_agent": settings.openai_model_gpt54,
        "conversation_manager": settings.anthropic_model_sonnet,
        "indexing_classifier": settings.openai_model_gpt54,
        "submission_transform_agent": settings.anthropic_model_opus,
        "assembly_plan_agent": settings.anthropic_model_opus,
        "external_research_agent": settings.anthropic_model_sonnet,
    }


MODEL_MAP: dict[str, str] = _build_model_map()
