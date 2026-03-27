"""FastAPI chat server for doc-digest.

Document-agnostic: reads document_data.json at startup.
Provides SSE streaming chat + follow-up question generation.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import create_chat_agent, create_followup_agent
from models import ChatMessage, ChatRequest, FollowUpRequest
from tools import set_document_data

logger = logging.getLogger("doc-digest.server")
logging.basicConfig(level=logging.INFO)

DOCUMENT_DATA_PATH = Path(__file__).parent / "document_data.json"


def _sse(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


async def _stream_agent(agent, prompt: str):
    """Iterate over agent.stream_async() and yield SSE events."""
    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event:
            text = event["data"]
            if text:
                yield _sse("text", {"content": str(text)})
        elif "current_tool_use" in event:
            tool_info = event["current_tool_use"]
            tool_name = tool_info.get("name", "")
            if tool_name:
                yield _sse("tool_call", {"tool": tool_name})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load document data at startup."""
    if not DOCUMENT_DATA_PATH.exists():
        raise RuntimeError(
            f"document_data.json not found at {DOCUMENT_DATA_PATH}. "
            "Run extract_document.py first."
        )
    data = json.loads(DOCUMENT_DATA_PATH.read_text(encoding="utf-8"))
    app.state.document_data = data
    app.state.sessions: dict[str, list[ChatMessage]] = {}
    set_document_data(data)

    title = data["metadata"]["title"]
    sections = len(data["sections"])
    logger.info("Loaded document: '%s' (%d sections)", title, sections)
    yield


app = FastAPI(title="Doc Digest Chat", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Health check endpoint."""
    meta = app.state.document_data["metadata"]
    return {
        "status": "ok",
        "document": meta["title"],
        "sections": len(app.state.document_data["sections"]),
    }


@app.get("/api/sections")
def get_sections():
    """Return section metadata for the ToC."""
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "level": s["level"],
            "word_count": s["word_count"],
        }
        for s in app.state.document_data["sections"]
    ]


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """SSE streaming chat endpoint."""
    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    history = app.state.sessions.get(session_id, [])

    # Build prompt with conversation history
    history_text = ""
    for msg in request.conversation_history[-10:]:  # Last 10 messages
        history_text += f"\n{msg.role}: {msg.content}"

    prompt = ""
    if history_text:
        prompt += f"Conversation so far:{history_text}\n\n"
    if request.section_id:
        prompt += f"[User is viewing section: {request.section_id}]\n"
    prompt += f"user: {request.message}"

    # Track in session
    history.append(ChatMessage(role="user", content=request.message))
    app.state.sessions[session_id] = history

    async def generate():
        try:
            agent = create_chat_agent(
                app.state.document_data, request.section_id
            )
            yield _sse("start", {"session_id": session_id})
            collected_text = []
            async for chunk in _stream_agent(agent, prompt):
                # Also collect text for history
                try:
                    parsed = json.loads(chunk.removeprefix("data: ").strip())
                    if parsed.get("type") == "text":
                        collected_text.append(parsed.get("content", ""))
                except (json.JSONDecodeError, AttributeError):
                    pass
                yield chunk
            # Save assistant response to history
            full_response = "".join(collected_text)
            history.append(
                ChatMessage(role="assistant", content=full_response)
            )
            app.state.sessions[session_id] = history
            yield _sse("done", {"session_id": session_id})
        except Exception as e:
            logger.exception("Chat stream error")
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/followups")
async def followups(request: FollowUpRequest):
    """Generate follow-up questions for a section."""
    # Verify section exists
    section = next(
        (
            s
            for s in app.state.document_data["sections"]
            if s["id"] == request.section_id
        ),
        None,
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    agent = create_followup_agent(
        app.state.document_data, request.section_id
    )
    result = agent(
        f"Generate 3 follow-up questions for the section: "
        f"'{section['title']}'"
    )

    # Try to parse JSON from the response
    response_text = str(result)
    try:
        # Find JSON array in response
        start = response_text.index("[")
        end = response_text.rindex("]") + 1
        questions = json.loads(response_text[start:end])
    except (ValueError, json.JSONDecodeError):
        questions = [
            f"What are the key takeaways from '{section['title']}'?",
            f"What evidence supports the claims in '{section['title']}'?",
            f"How does '{section['title']}' relate to the rest of the document?",
        ]

    return {"section_id": request.section_id, "questions": questions}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
