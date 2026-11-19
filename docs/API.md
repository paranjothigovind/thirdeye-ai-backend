# Backend API Documentation

Base URL: `http://localhost:8000` (development). Interactive docs: `/api/docs` (Swagger UI), `/api/redoc`.

All routes are prefixed with `/api` (auth routes with `/api/auth`). Responses are JSON unless noted (SSE for streaming chat).

## Authentication

JWT Bearer tokens. Token lifetime: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`). Include `Authorization: Bearer <access_token>` on protected routes.

### POST /api/auth/signup
Create a new user account (also creates a FREE subscription).

Request body (JSON):
```json
{
  "email": "user@example.com",
  "username": "testuser",
  "password": "securepassword"
}
```
Response 200:
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "testuser",
  "is_active": true
}
```
Errors: 400 (email/username already registered).

### POST /api/auth/login
Authenticate and return access token. Note: JSON body (not form-encoded).

Request body (JSON):
```json
{
  "username": "testuser",
  "password": "securepassword"
}
```
Response 200:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```
Errors: 401 (invalid credentials).

### GET /api/auth/me
Get current authenticated user.

Headers: `Authorization: Bearer <token>`
Response 200:
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "testuser",
  "is_active": true
}
```

### GET /api/auth/subscriptions
Get current user's subscriptions.

Headers: `Authorization: Bearer <token>`
Response 200:
```json
[
  {
    "id": 1,
    "type": "free",
    "is_active": true,
    "start_date": "2026-...",
    "end_date": null
  }
]
```
Subscription types: `free`, `premium`, `enterprise`.

## Health

### GET /api/health
Liveness check. Response 200:
```json
{ "status": "healthy", "timestamp": "2026-...", "version": "1.0.0" }
```

### GET /api/ready
Readiness check. Response 200:
```json
{ "status": "ready", "timestamp": "2026-...", "version": "1.0.0" }
```

## Chat

### POST /api/chat
RAG chat with optional streaming (SSE).

Request body:
```json
{
  "messages": [
    { "role": "user", "content": "How to practice Trataka safely?" }
  ],
  "persona": null,
  "stream": true
}
```
- `messages`: list of `{role, content}` (role: user/assistant/system). The last
  `user` message is the question and the retrieval query. Earlier `user`/`assistant`
  messages are forwarded as conversation history (most recent
  `LLM_MAX_HISTORY_MESSAGES`, default 10). `system` messages from clients are ignored.
  A single `user` message works as before.
- `persona`: optional; "course"/"class" routes to course class agent; "post"/"support" routes to post-class support agent.
- `stream`: default true.
- Limits (configurable): at most `CHAT_MAX_MESSAGES` messages (40),
  `CHAT_MAX_MESSAGE_CHARS` per message (4,000) and `CHAT_MAX_TOTAL_CHARS` in total
  (24,000). Larger requests get **422**.

Optional header `X-Session-ID` (8–64 characters `A-Z a-z 0-9 _ -`): an anonymous
session identifier used only for per-session usage limits. Without it, limits
are per client IP. No login is required.

Usage limits return **429** with a `Retry-After` header and a user-readable
`detail`: per-IP requests per minute, per-session requests per hour, per-session
daily tokens, and the global daily token budget.

Streaming response (SSE, `text/event-stream`, header `X-Request-ID`):
```
: keep-alive

data: {"chunk": "...", "type": "content"}

data: {"citations": [{"title": "...", "reference": "..."}], "type": "citations"}

data: [DONE]
```
The full response is generated and passes the safety checks (including any
disclaimer) before the first `content` event is sent. Until then the server sends
SSE comment lines (`: keep-alive`), which clients must ignore. `[DONE]` is not
JSON; treat it as the completion marker.

`citations` ("Sources") lists the documents retrieved from the knowledge base and
supplied to the model: `title` from the document, `reference` = `page N`, the
URL, or `""`. It does not claim the model used each source. Answer text contains
no `[Source: ...]` tags.

On error, exactly one event is sent and no `content` events precede it:
`data: {"error": "<generic message>", "type": "error", "request_id": "uuid"}`.
Error text is generic; details are in server logs under the request ID.

If the question matches the emergency keywords, no model is called and usage
limits do not apply. With `stream: true` the emergency message is sent as normal
`content` events, then `citations: []` and `[DONE]`; with `stream: false` it is
the JSON body below.

Non-streaming (`stream: false`) response 200:
```json
{
  "response": "...",
  "citations": [{ "title": "...", "reference": "..." }],
  "request_id": "uuid"
}
```
Errors: 400 (no user message), 422 (validation or size limits), 429 (usage
limits), 500 (generic `detail` that includes the request ID).

### POST /api/chat/graph
LangGraph stateful chat with corrective loops.

Request body:
```json
{
  "messages": [{ "role": "user", "content": "..." }],
  "thread_id": null
}
```
Response 200:
```json
{
  "response": "...",
  "citations": [{ "title": "...", "reference": "..." }],
  "thread_id": "uuid",
  "retry_count": 0
}
```
`messages` is handled as in `/api/chat` (last user message = question, earlier
user/assistant turns = history), with the same size limits, emergency handling,
disclaimers, Sources and usage limits. `thread_id` is echoed back; the server keeps
no conversation state between requests. For session limits, `X-Session-ID` is
used, else `thread_id`, else the client IP.

Errors: 400 (no user message), 422, 429, 500 (generic `detail`).

## Ingestion

Max upload size: 25 MB (`MAX_UPLOAD_SIZE_MB`). Only PDF files accepted for file upload.

### POST /api/ingest
Multipart form-data. Provide either `file` (PDF) or `urls` (JSON string of URL list), plus optional `context`.

Fields:
- `file`: PDF file (multipart)
- `urls`: JSON string, e.g. `["https://example.com/page"]`
- `context`: optional string

Response 200:
```json
{
  "job_id": "uuid",
  "status": "queued",
  "message": "PDF ingestion job queued for file.pdf"
}
```
Errors: 400 (invalid file type/URLs/empty), 413 (too large), 500.

### POST /api/ingest/urls
JSON endpoint for URL ingestion.

Request body:
```json
{
  "urls": ["https://example.com/a", "https://example.com/b"],
  "context": "optional context"
}
```
Response 200: same as `/api/ingest`.

### GET /api/documents
List all unique ingested document IDs.

Response 200:
```json
{
  "count": 2,
  "doc_ids": ["doc1", "doc2"],
  "dummy_query": null,
  "text_results": null,
  "vector_results": null,
  "error": null
}
```

### GET /api/documents/{doc_id}/status
Check ingestion status of a document.

Response 200:
```json
{
  "ingested": true,
  "doc_id": "doc1",
  "version": 1,
  "title": "...",
  "source": "...",
  "timestamp": "...",
  "error": null
}
```

### DELETE /api/context/{context}
Delete all embeddings for a given context.

Response 200:
```json
{
  "status": "success",
  "context": "ctx",
  "deleted_count": 5,
  "error": null
}
```

### POST /api/clear
Clear all vector data and ingested PDFs.

Response 200:
```json
{
  "status": "success",
  "message": "All vector data and PDFs cleared successfully",
  "vector_result": { "...": "..." },
  "storage_result": { "...": "..." }
}
```

## Jobs

### GET /api/jobs/{job_id}
Poll Celery job status.

Response 200:
```json
{
  "job_id": "uuid",
  "status": "queued|processing|completed|failed|retrying|cancelled",
  "result": { "...": "..." },
  "error": null
}
```
`result` populated only when completed; `error` populated only when failed.

## Error Format
Errors return JSON:
```json
{ "detail": "message" }
```
with appropriate HTTP status codes (400, 401, 404, 413, 500).

## CORS
Configured via `CORS_ORIGINS` (defaults include localhost:3000/8000 and production frontends).

## Notes
- README mentions form-encoded login; actual endpoint accepts JSON.
- Streaming uses SSE; clients should parse `data:` lines.
