"""Pydantic response models for LLM structured output via Instructor."""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class AgentResponse(BaseModel):
    thinking: str = Field(description="Brief reasoning about what to do next")
    action: str = Field(description="The game command to execute")
    next_steps: str = Field(default="", description="Your plan for the next 2-3 turns, if pursuing a multi-turn goal")
    new_objective: str = Field(default="", description="Optional new objective")
    nav_target: str = Field(
        default="",
        description=(
            "Optional. A location name or ID you want to head toward over multiple turns. "
            "On the next turn, you'll see a computed route from your current position. "
            "Leave empty if you don't have a nav destination."
        ),
    )

    @field_validator("new_objective", "next_steps", "nav_target", mode="before")
    @classmethod
    def coerce_none(cls, v: object) -> str:
        return v if v is not None else ""

class CriticResponse(BaseModel):
    score: float = Field(ge=-1.0, le=1.0, description="Action quality score")
    justification: str = Field(description="Why this score was given")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in evaluation")

class ExtractorResponse(BaseModel):
    exits: list[str] = Field(default_factory=list, description="Available exit directions")
    in_combat: bool = Field(default=False, description="Whether combat is active")
    is_room_description: bool = Field(default=False, description="Whether text is a room description")

class MemorySynthesisResponse(BaseModel):
    should_remember: bool = Field(description="Whether to remember this")
    reasoning: str = Field(description="Why or why not")
    category: str = Field(default="NOTE", description="SUCCESS|FAILURE|DISCOVERY|DANGER|NOTE")
    memory_title: str = Field(default="", description="3-6 word title")
    memory_text: str = Field(default="", description="1-2 sentence insight")
    persistence: str = Field(default="ephemeral", description="core|permanent|ephemeral")
    status: str = Field(default="ACTIVE", description="ACTIVE|TENTATIVE")
    supersedes_titles: list[str] = Field(
        default_factory=list,
        description="Exact titles of existing memories this replaces. Copy titles verbatim from the existing memories list."
    )

class ConsolidationAction(BaseModel):
    action: Literal["keep", "drop", "merge", "supersede"] = Field(description="keep|drop|merge|supersede")
    memory_title: str = Field(description="Exact title of existing memory being acted on")
    merge_with: str = Field(default="", description="Title of the other memory (for 'merge' and 'supersede')")
    new_text: str = Field(default="", description="Rewritten text (for 'merge' only)")
    new_title: str = Field(default="", description="Title for merged memory (for 'merge' only)")
    reason: str = Field(description="Why this action was chosen")

class ConsolidationResponse(BaseModel):
    actions: list[ConsolidationAction]

class LocationSummaryResponse(BaseModel):
    summary: str = Field(description="One-line location summary (max 100 chars)")

class Objective(BaseModel):
    text: str = Field(description="The objective description")
    location_id: int = Field(default=0, description="Location ID where this objective applies (0 if general)")
    location_name: str = Field(default="", description="Name of the location (empty if general)")

class ObjectiveDiscoveryResponse(BaseModel):
    objectives: list[Objective] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)

class ObjectiveCompletionResponse(BaseModel):
    completed_objectives: list[str] = Field(default_factory=list)

class GroundingJudgment(BaseModel):
    item: str = Field(description="Title of memory or text of objective being validated")
    grounded: bool = Field(description="Whether the claim is supported by recent game output")
    reason: str = Field(description="Explanation for the judgment (logged, not shown to agent)")

class GroundingValidationResponse(BaseModel):
    judgments: list[GroundingJudgment] = Field(description="One judgment per candidate")
