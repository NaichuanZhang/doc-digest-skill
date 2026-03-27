"""Pydantic request/response models for the doc-digest chat server."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    section_id: str | None = None
    session_id: str = Field(default="default")
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class FollowUpRequest(BaseModel):
    section_id: str


class SectionResponse(BaseModel):
    id: str
    title: str
    level: int
    word_count: int
