"""Pydantic response models for LLM structured output via Instructor."""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator


class AgentResponse(BaseModel):
    thinking: str = Field(description="Brief reasoning about what to do next")
    action: str = Field(description="The game command to execute")
    new_objective: str = Field(default="", description="Optional new objective")

    @field_validator("new_objective", mode="before")
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

class Objective(BaseModel):
    text: str = Field(description="The objective description")
    location_id: int = Field(default=0, description="Location ID where this objective applies (0 if general)")
    location_name: str = Field(default="", description="Name of the location (empty if general)")

class ObjectiveDiscoveryResponse(BaseModel):
    objectives: list[Objective] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)

class ObjectiveCompletionResponse(BaseModel):
    completed_objectives: list[str] = Field(default_factory=list)
