"""Conversation Manager action models — discriminated union by action type."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from .common import DeckForgeBaseModel
from .enums import ActionScope, ActionType, Language


class RewriteSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.REWRITE_SLIDE] = ActionType.REWRITE_SLIDE
    target: str  # S-NNN
    scope: Literal[ActionScope.SLIDE_ONLY, ActionScope.REQUIRES_REPORT_UPDATE]
    instruction: str = ""


class AddSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.ADD_SLIDE] = ActionType.ADD_SLIDE
    after: str | None = None  # S-NNN or None for beginning
    topic: str
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


class RemoveSlideAction(DeckForgeBaseModel):
    type: Literal[ActionType.REMOVE_SLIDE] = ActionType.REMOVE_SLIDE
    target: str  # S-NNN
    requires_confirmation: bool = True


class SlideMove(DeckForgeBaseModel):
    """Matches prompt contract: {"from": "S-004", "to": "S-005"}."""
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")  # S-NNN
    to: str  # S-NNN


class ReorderSlidesAction(DeckForgeBaseModel):
    type: Literal[ActionType.REORDER_SLIDES] = ActionType.REORDER_SLIDES
    moves: list[SlideMove]


class AdditionalRetrievalAction(DeckForgeBaseModel):
    type: Literal[ActionType.ADDITIONAL_RETRIEVAL] = ActionType.ADDITIONAL_RETRIEVAL
    query: str
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


class ShowSourcesAction(DeckForgeBaseModel):
    type: Literal[ActionType.SHOW_SOURCES] = ActionType.SHOW_SOURCES
    target: str  # S-NNN


class ChangeLanguageAction(DeckForgeBaseModel):
    type: Literal[ActionType.CHANGE_LANGUAGE] = ActionType.CHANGE_LANGUAGE
    language: Literal[Language.EN, Language.AR, Language.BILINGUAL]
    scope: Literal[ActionScope.FULL_RERENDER] = ActionScope.FULL_RERENDER


class ExportAction(DeckForgeBaseModel):
    type: Literal[ActionType.EXPORT] = ActionType.EXPORT
    format: Literal["pptx", "docx", "both"] = "pptx"
    scope: Literal[ActionScope.SYSTEM_EXPORT] = ActionScope.SYSTEM_EXPORT


class FillGapAction(DeckForgeBaseModel):
    type: Literal[ActionType.FILL_GAP] = ActionType.FILL_GAP
    gap_id: str  # GAP-NNN
    scope: Literal[ActionScope.AWAITING_USER_INPUT] = ActionScope.AWAITING_USER_INPUT


class WaiveGapAction(DeckForgeBaseModel):
    type: Literal[ActionType.WAIVE_GAP] = ActionType.WAIVE_GAP
    gap_id: str  # GAP-NNN
    requires_confirmation: bool = True


class UpdateReportAction(DeckForgeBaseModel):
    type: Literal[ActionType.UPDATE_REPORT] = ActionType.UPDATE_REPORT
    section: str | None = None
    scope: Literal[ActionScope.REQUIRES_REPORT_UPDATE] = ActionScope.REQUIRES_REPORT_UPDATE


# Discriminated union — Pydantic resolves by the `type` field
ConversationAction = Annotated[
    RewriteSlideAction
    | AddSlideAction
    | RemoveSlideAction
    | ReorderSlidesAction
    | AdditionalRetrievalAction
    | ShowSourcesAction
    | ChangeLanguageAction
    | ExportAction
    | FillGapAction
    | WaiveGapAction
    | UpdateReportAction,
    Field(discriminator="type"),
]


class ConversationResponse(DeckForgeBaseModel):
    """Complete output of the Conversation Manager."""
    response_to_user: str
    action: ConversationAction
