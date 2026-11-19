# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 1.1 — Safety, grounding and production readiness

#### Added
- Usage limits for `/api/chat` and `/api/chat/graph`: per-IP rate, per-session rate (`X-Session-ID`), per-session daily tokens, global daily token budget (HTTP 429 with `Retry-After`); in-memory or Redis store
- Request size limits: message count, characters per message, total characters (HTTP 422)
- Proxy-aware client IP (`TRUSTED_PROXY_HOPS`; `X-Forwarded-For` ignored by default)
- Structured `llm_call` telemetry: tokens (incl. cache), requested/served model, fallback use, latency, stop reason, provider request ID; no content or keys
- Configurable region emergency policy (`EMERGENCY_POLICY_FILE`, `emergency_policy.example.json`); contacts and extra (e.g. Tamil) keywords used only when approved/reviewed
- SSE keep-alive comments while a response is buffered (`SSE_KEEPALIVE_SECONDS`)
- Claude model compatibility matrix with startup warnings; startup warnings for unsafe public configuration
- Bundled web UI: buffered SSE parser (`sse-parser.js`) with `[DONE]` handling, Sources rendering, 429/422 messages, anonymous session header
- Regression tests for all of the above, including Node.js tests of the UI parser against fragmented server streams

#### Changed
- `citations` are built server-side from the retrieved documents ("Sources") and validated against them; model-written source tags are stripped from answers
- Emergency responses to `stream: true` requests use the SSE event contract; `/api/chat/graph` now applies emergency checks and disclaimers
- Emergency message no longer lists US numbers (911, 988, 741741); it gives generic guidance until approved regional contacts are configured
- Medical and emergency keyword matching is whole-word ("harmony", "unconditional" no longer match)
- User content and context are escaped inside the prompt's XML-like delimiters
- Graph no longer retries for a missing in-text citation when documents were retrieved
- Graph checkpoints are per request and deleted afterwards; `thread_id` is only echoed
- Provider error messages no longer include provider error text

#### Fixed
- A Claude refusal after partial output with server-side fallback no longer delivers the declined partial text joined to the fallback continuation
- Removed the prompt instruction that generated a fabricated "[Source: Nettrikkan Module]" citation
- Graph query rewriting no longer logs the user's query
- `extract_citations` regex no longer merges adjacent tags
- Bundled UI no longer throws on `[DONE]`, now renders Sources, and handles events split across network reads

### Phase 1 — Claude integration

### Added
- Anthropic Claude as an LLM generation provider (`LLM_PROVIDER=anthropic`) using the official `anthropic` SDK (async client, real streaming)
- LLM provider abstraction (`app/models/base.py`, `provider_factory.py`); Azure OpenAI remains available and is the default
- Settings: `LLM_PROVIDER`, `LLM_MAX_HISTORY_MESSAGES`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`, `ANTHROPIC_TIMEOUT`, `ANTHROPIC_MAX_RETRIES`, `ANTHROPIC_EFFORT`, `ANTHROPIC_REFUSAL_FALLBACK`
- Conversation history: earlier user/assistant messages in a chat request are forwarded to the model (per request only)
- Retrieved context is sent to the model inside `<retrieved_context>` tags with grounding rules (answer only from sources, never invent citations, say when the knowledge base lacks information)
- `.env.example`
- Mocked provider, RAG and SSE tests (no network or API key needed)

### Changed
- `/api/chat` streaming buffers and validates the complete response before sending any `content` event (same SSE format; first chunk arrives after generation completes)
- Medical disclaimer is also added when the response itself is flagged by `check_response`
- Error responses no longer include internal exception text (SSE `error` event and HTTP 500 `detail` are generic and carry the request ID)
- Settings validation errors no longer echo configuration values

### Fixed
- Streaming clients now receive the medical disclaimer (it was previously appended only after streaming had finished)
- `/api/chat/graph` returns 400 instead of 500 when no user message is present
- Removed `tenacity` retry decorators on the Azure async generators, which never retried; retries are done by the provider SDKs

### Previously added
- Initial release of Third Eye Meditation AI Chatbot
- RAG-based chat system with Azure OpenAI integration
- Angelitic RAG layering (canonical, safety, practices, Q&A)
- PDF ingestion pipeline with versioning
- Web scraping pipeline with robots.txt compliance
- Hybrid retrieval with Azure AI Search
- Safety guardrails and disclaimers
- Streaming chat responses with citations
- Background job processing with Celery
- LangGraph implementation for stateful conversations
- Comprehensive test suite
- Docker containerization
- GitHub Actions CI/CD pipeline
- Azure deployment scripts and documentation
- Beautiful web UI with real-time streaming
- Sample knowledge base seeding script

### Security
- Azure Key Vault integration for secrets management
- Non-root Docker containers
- Environment variable validation
- Input sanitization and validation

## [1.0.0] - 2024-01-XX

### Initial Release
- Core RAG functionality
- Azure integration (OpenAI, AI Search, Blob Storage)
- Safety-first meditation guidance
- Production-ready deployment configuration

---

## Version History

### Version 1.0.0 - Initial Release
**Release Date:** TBD

**Highlights:**
- Complete RAG pipeline for meditation guidance
- Azure-native architecture
- Safety guardrails and ethical AI practices
- Production-ready with CI/CD

**Known Issues:**
- None at initial release

**Upgrade Notes:**
- First release, no upgrade path needed

---

For detailed commit history, see the [commit log](https://github.com/your-org/thirdeye-ai-backend/commits/main).