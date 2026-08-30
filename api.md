# Unified IT API Contract

## Purpose

This document defines the HTTP contract for chat-based customer interactions on top of the LangGraph workflow in the Unified IT agent.

## Architecture Context

- State model: conversation state follows `AgentState` in `agent/state.py` with `messages`, `intent`, `extracted_params`, `missing_fields`, `tool_result`, `final_response`, `escalate`, and `session_summary`.
- Orchestration: the graph in `agent/graph.py` routes from `classify_intent` to `execute_tool`, `escalate`, and always finishes through `summarize`.
- Tool execution: data access happens through tools in `agent/tools.py`.

## Endpoint 1

### POST /api/chat/{conversation_id}/message

Send a guest message to the assistant and get a single assistant response for this turn.

### Path Params

- `conversation_id` (string, required): Stable identifier for one chat thread.

### Request Body Schema

```json
{
  "message": "string"
}
```

### Response Body Schema (200)

```json
{
  "conversation_id": "string",
  "intent": "inquiry|lead|escalate",
  "assistant_response": "string",
  "escalate": false,
  "tool_result": {},
  "state": {
    "extracted_params": {},
    "missing_fields": [],
    "final_response": "string"
  },
  "timestamp": "ISO-8601 string"
}
```

### Realistic Example

Request:

```json
{
  "message": "What is the difference between Web Hosting and a Cloud Server?"
}
```

Response:

```json
{
  "conversation_id": "conv-rt-0001",
  "intent": "inquiry",
  "assistant_response": "Web Hosting is a shared environment where multiple websites share the same server resources, making it cost-effective for smaller sites. A Cloud Server provides dedicated resources and greater scalability for growing businesses. Would you like to know the pricing for either?",
  "escalate": false,
  "tool_result": "Web Hosting provides shared resources on a single server, while a Cloud Server provides dedicated, scalable resources in a virtualized environment.",
  "state": {
    "extracted_params": {
      "query": "difference between Web Hosting and a Cloud Server"
    },
    "missing_fields": [],
    "final_response": "Web Hosting is a shared environment..."
  },
  "timestamp": "2026-07-14T16:20:00Z"
}
```

### Possible Error Responses

- `400 Bad Request`

```json
{
  "error": "INVALID_INPUT",
  "message": "message is required and must be a non-empty string"
}
```

- `503 Service Unavailable`

```json
{
  "error": "DEPENDENCY_FAILURE",
  "message": "Could not process message right now"
}
```

## Endpoint 2

### GET /api/chat/{conversation_id}/history

Return full conversation history for the given chat thread in chronological order.

### Path Params

- `conversation_id` (string, required): Stable identifier for one chat thread.

### Response Body Schema (200)

```json
{
  "conversation_id": "string",
  "messages": [
    {
      "role": "user|assistant|system",
      "content": "string",
      "timestamp": "ISO-8601 string"
    }
  ],
  "summary": {
    "total_messages": 0,
    "last_intent": "inquiry|lead|escalate|null",
    "escalate": false
  }
}
```

## HTTP Conventions

- `POST /message` is synchronous for one-turn processing.
- Client sends only one field in request body: `message`.
- `GET /history` is idempotent and read-only.
- Timestamps must be returned in UTC using ISO-8601.
