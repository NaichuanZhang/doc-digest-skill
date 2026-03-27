"""Strands agent configuration for doc-digest chat server.

Creates agents with document context injected into the system prompt.
Uses tokenmaster AWS profile by default (matching adsgency pattern).
"""

from __future__ import annotations

import os
import logging

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

from tools import search_document, get_section, fact_check

logger = logging.getLogger("doc-digest.agent")

AWS_PROFILE = os.getenv("AWS_PROFILE", "tokenmaster")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6-20250514-v1:0"
)


def _create_model() -> BedrockModel:
    """Create BedrockModel with tokenmaster profile."""
    session_kwargs: dict = {"region_name": AWS_REGION}
    if AWS_PROFILE:
        session_kwargs["profile_name"] = AWS_PROFILE
        logger.debug("Using AWS profile: %s", AWS_PROFILE)

    session = boto3.Session(**session_kwargs)
    return BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        boto_session=session,
    )


def _build_chat_prompt(
    document_data: dict, section_id: str | None = None
) -> str:
    """Build system prompt with document context."""
    meta = document_data["metadata"]
    sections = document_data["sections"]

    prompt = (
        f"You are a knowledgeable assistant for the document: "
        f"'{meta['title']}'.\n"
    )
    if meta.get("author"):
        prompt += f"Author: {meta['author']}. "
    prompt += f"The document has {len(sections)} sections.\n\n"

    prompt += (
        "Your role:\n"
        "- Answer questions about this document accurately\n"
        "- Cite specific sections when referencing content\n"
        "- Help the user understand complex parts\n"
        "- When fact-checking, compare claims against the document content\n"
        "- Generate insightful follow-up questions\n\n"
    )

    # If focused on a specific section, prepend it
    if section_id:
        section = next(
            (s for s in sections if s["id"] == section_id), None
        )
        if section:
            prompt += (
                f"The user is currently focused on this section:\n"
                f"## {section['title']}\n{section['content']}\n\n"
                f"---\n\n"
            )

    # Include full text (truncated for context window)
    full_text = document_data.get("full_text", "")
    max_chars = 50000
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n\n[... truncated ...]"

    prompt += f"Full document content:\n{full_text}"
    return prompt


def _build_followup_prompt(
    document_data: dict, section_id: str
) -> str:
    """Build system prompt for follow-up question generation."""
    section = next(
        (s for s in document_data["sections"] if s["id"] == section_id),
        None,
    )
    if not section:
        return "Generate general questions about this document."

    return (
        "You are a critical analyst reviewing a document section. "
        "Generate exactly 3 insightful follow-up questions that would help "
        "a reader better understand this section. Focus on:\n"
        "- Assumptions that should be challenged\n"
        "- Evidence that should be verified\n"
        "- Implications that deserve deeper analysis\n\n"
        "Return ONLY a JSON array of 3 strings, no other text.\n"
        f'Example: ["Question 1?", "Question 2?", "Question 3?"]\n\n'
        f"Section: {section['title']}\n\n{section['content']}"
    )


def create_chat_agent(
    document_data: dict, section_id: str | None = None
) -> Agent:
    """Create an agent for document Q&A chat."""
    return Agent(
        model=_create_model(),
        tools=[search_document, get_section, fact_check],
        system_prompt=_build_chat_prompt(document_data, section_id),
        callback_handler=None,
    )


def create_followup_agent(
    document_data: dict, section_id: str
) -> Agent:
    """Create an agent for generating follow-up questions."""
    return Agent(
        model=_create_model(),
        tools=[get_section],
        system_prompt=_build_followup_prompt(document_data, section_id),
        callback_handler=None,
    )
