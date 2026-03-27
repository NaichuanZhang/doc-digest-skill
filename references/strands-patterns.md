# Strands SDK Patterns Reference

Quick reference for Strands SDK patterns used in the doc-digest chat server.
All patterns are taken from working production code.

## Agent Creation (from adsgency)

```python
import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

session = boto3.Session(profile_name="tokenmaster", region_name="us-west-2")
model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-6-20250514-v1:0", boto_session=session)

agent = Agent(
    model=model,
    tools=[tool_fn_1, tool_fn_2],
    system_prompt="Your system prompt here",
    callback_handler=None,  # None = no stdout printing
)
```

## Tool Definition

```python
from strands import tool

@tool
def my_tool(query: str, limit: int = 5) -> str:
    """Tool description shown to the model.

    Args:
        query: What to search for.
        limit: Max results to return.

    Returns:
        The search results as text.
    """
    return f"Results for {query}"
```

## SSE Streaming (from adsgency/backend/routers/stream.py)

```python
import json
from fastapi.responses import StreamingResponse

def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"

async def _stream_agent(agent: Agent, prompt: str):
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

# Usage in endpoint:
@app.post("/api/chat")
async def chat(request: ChatRequest):
    async def generate():
        agent = create_agent(...)
        async for chunk in _stream_agent(agent, prompt):
            yield chunk
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Module-Level State for Tools (from adsgency)

```python
_state = None

def set_state(data):
    global _state
    _state = data

@tool
def my_tool(query: str) -> str:
    """Uses module-level state."""
    return _state.get(query, "not found")
```

## Synchronous Agent Call (non-streaming)

```python
result = agent("Your prompt here")
response_text = str(result)
```
