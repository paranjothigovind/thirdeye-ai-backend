# 🏗️ Architecture Documentation

## System Overview

The Third Eye Meditation AI Chatbot is a production-ready RAG (Retrieval-Augmented Generation) system built on Azure services, designed to provide safe, grounded meditation guidance.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│                    (Web UI / API Clients)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Chat    │  │ Ingest   │  │  Jobs    │  │  Health  │       │
│  │ Routes   │  │ Routes   │  │ Routes   │  │ Routes   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
┌───────────────────────────┐  ┌──────────────────────────┐
│     RAG Pipeline          │  │   Ingestion Pipeline     │
│  ┌─────────────────────┐  │  │  ┌────────────────────┐ │
│  │  Query Rewriting    │  │  │  │  PDF Processing    │ │
│  │  Retrieval          │  │  │  │  Web Scraping      │ │
│  │  Context Assembly   │  │  │  │  Chunking          │ │
│  │  Generation         │  │  │  │  Embedding         │ │
│  │  Citation Extract   │  │  │  │  Vectorization     │ │
│  │  Guardrails         │  │  │  └────────────────────┘ │
│  └─────────────────────┘  │  │                          │
└───────────┬───────────────┘  └────────────┬─────────────┘
            │                               │
            │                               ▼
            │                    ┌──────────────────────┐
            │                    │   Celery Workers     │
            │                    │  (Background Jobs)   │
            │                    └──────────┬───────────┘
            │                               │
            ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Azure Services Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Azure OpenAI │  │ Azure AI     │  │ Azure Blob   │         │
│  │ (Chat +      │  │ Search       │  │ Storage      │         │
│  │  Embeddings) │  │ (Vector DB)  │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐                           │
│  │ Key Vault    │  │ Redis        │                           │
│  │ (Secrets)    │  │ (Queue)      │                           │
│  └──────────────┘  └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. API Layer (`app/api/`)

**Purpose:** HTTP interface for all client interactions

**Components:**
- `routes_chat.py` - Chat endpoints with streaming support
- `routes_graph.py` - Advanced chat with LangGraph (stateful, corrective)
- `routes_ingest.py` - Content ingestion (PDF/URLs)
- `routes_jobs.py` - Background job status tracking
- `routes_health.py` - Health and readiness checks

**Key Features:**
- Streaming Server-Sent Events (SSE); responses are validated before any text is sent
- Request validation with Pydantic
- Error handling and logging
- CORS configuration

### 2. RAG Pipeline (`app/rag/`)

**Purpose:** Retrieval-Augmented Generation for grounded responses

**Components:**

#### a. Retriever (`retriever.py`)
- **Hybrid Search:** Combines semantic (vector) and keyword (BM25) search
- **Layer-based Retrieval:** Supports Angelitic RAG layers
- **Filtering:** Version control (is_latest), source type, sections

#### b. Chains (`chains.py`)
- **Simple RAG Chain:** Basic retrieval → generation flow
- **Angelitic RAG:** Multi-layer context assembly
  - Canonical teachings (highest priority)
  - Safety & contraindications (critical)
  - Practices & techniques
  - Q&A exemplars

#### c. Graph (`graph.py`)
- **LangGraph Implementation:** Stateful conversations with corrective loops
- **Nodes:**
  - Query rewriting for better retrieval
  - Retrieval with quality checks
  - Generation with response validation
  - Citation extraction
- **Conditional Edges:** Retry logic based on quality checks

#### d. Guardrails (`guardrails.py`)
- **Query Checks:** Medical advice detection, emergency keywords
- **Response Checks:** Citation presence, safety warnings
- **Disclaimers:** Automatic addition based on content
- **Emergency Handling:** Crisis response templates

#### e. Prompts (`prompts.py`)
- **System Prompt:** Defines AI persona and behavior
- **Query Rewrite:** Improves retrieval quality
- **Angelitic Template:** Structures multi-layer context
- **Guardrail Prompts:** Safety validation

### 3. Ingestion Pipeline (`app/ingestion/`)

**Purpose:** Process and vectorize content for RAG

**Components:**

#### a. PDF Pipeline (`pdf_pipeline.py`)
```
PDF Upload → Blob Storage → Parse (PyMuPDF) → Clean → 
Chunk → Embed → Upsert to Vector DB
```
- **Versioning:** Append-only with `is_latest` flag
- **Metadata:** Title, page, source, section, timestamp
- **Chunking:** 800-1200 tokens with 15-20% overlap

#### b. Web Pipeline (`web_pipeline.py`)
```
URLs → Robots.txt Check → Fetch HTML → Parse (BeautifulSoup) → 
Clean → Chunk → Embed → Upsert to Vector DB
```
- **Rate Limiting:** Configurable RPS (default: 2)
- **Compliance:** Respects robots.txt
- **Metadata:** URL, title, fetched_at, source

#### c. Workers (`workers.py`)
- **Celery Tasks:** Async processing of ingestion jobs
- **Job Tracking:** Status updates via Redis
- **Error Handling:** Retry logic with exponential backoff

#### d. Vector Store (`vectorstore.py`)
- **Index Management:** Auto-creates Azure AI Search index
- **Schema:** Optimized for hybrid search
- **Versioning:** Handles document updates

### 4. Models (`app/models/`)

**Purpose:** LLM generation providers and Azure OpenAI embeddings

Generation is behind a small provider abstraction, so the RAG layer never
imports a vendor SDK. Embeddings are **not** part of it: they always use Azure
OpenAI so the vectors stay compatible with the existing Azure AI Search index.

```
RAG chain / agents / LangGraph nodes
        │  self.llm.generate_response(messages, stream)
        ▼
LLMProvider (base.py) ──── generate() / stream() / aclose()
   ├── AzureOpenAIClient   (azure_openai.py, LangChain AzureChatOpenAI)
   └── AnthropicProvider   (anthropic_claude.py, official anthropic SDK)
        ▲
provider_factory.get_llm_provider()  ← LLM_PROVIDER setting
```

**Components:**

#### a. Provider contract (`base.py`)
- **Interface:** `generate()` (full text), `stream()` (real provider deltas), and
  `generate_response(messages, stream)` used by existing RAG code
- **Messages:** plain `{"role": "system" | "user" | "assistant", "content": str}` dicts;
  system messages are split out for providers that take them separately
- **Errors:** provider SDK exceptions are mapped to `LLMAuthenticationError`,
  `LLMRateLimitError`, `LLMTimeoutError`, `LLMServiceUnavailableError`,
  `LLMRefusalError` (all `LLMProviderError`); messages never contain credentials

#### b. Provider factory (`provider_factory.py`)
- Selects the provider from `LLM_PROVIDER` (`azure_openai` default, or `anthropic`)
- Creates it once per process and reuses it; `close_llm_provider()` runs on
  application shutdown (FastAPI lifespan) to close the async HTTP client

#### c. Anthropic Claude (`anthropic_claude.py`)
- `AsyncAnthropic` client; streaming via `messages.stream()` text deltas
- Retries (connection errors, 408/409/429/5xx with backoff and `retry-after`) and
  timeouts are the SDK's (`ANTHROPIC_MAX_RETRIES`, `ANTHROPIC_TIMEOUT`); a stream
  is retried only before its first event
- Checks `stop_reason`: `refusal` raises `LLMRefusalError` (partial text must be
  discarded); `max_tokens` with no answer text raises
- Sends `output_config.effort` (`ANTHROPIC_EFFORT`) and, by default, server-side
  refusal fallbacks (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`)
- **Refusal fallback:** a decline *before* any output is served by the fallback
  model (Anthropic chooses it per refusal category). A decline *after* partial
  output raises `LLMRefusalError`: the partial text is discarded and the client
  gets the standard error event. Non-streaming responses already omit declined text.
- Does not send `temperature`: current Claude models and API version `2026-10-21`
  (sent by SDK 2.x) reject sampling parameters
- **Model compatibility matrix** (`CLAUDE_MODEL_CAPABILITIES`): settings a model
  does not support are disabled at startup with a warning; unknown models are sent
  as configured with a warning.

  | Model | `effort` values | Refusal fallback |
  |---|---|---|
  | `claude-fable-5-2`, `claude-fable-5-1`, `claude-fable-5`, `claude-mythos-5-2`, `claude-mythos-5-1` | low–max | yes |
  | `claude-opus-5-5`, `claude-opus-5`, `claude-sonnet-5-5` | low–max | yes |
  | `claude-sonnet-5`, `claude-haiku-5-5`, `claude-opus-4-8`, `claude-opus-4-7` | low–max | no |
  | `claude-opus-4-6`, `claude-sonnet-4-6` | low, medium, high, max | no |
  | `claude-haiku-4-5` | not supported | no |

#### c2. LLM telemetry (`app/core/llm_telemetry.py`)
Every provider call logs one `llm_call` record (JSON field `llm`): provider,
requested and served model, input/output/cache tokens (`tokens_estimated` when
the provider reports none, e.g. Azure streaming), fallback used and fallback
model, stop reason, latency, provider request ID, status, and a hashed session
key. Records never contain prompts, answers or credentials. Token totals feed the
daily budgets below.

#### d. Azure OpenAI Client (`azure_openai.py`)
- **Streaming:** Async token-by-token generation
- **Retry Logic:** openai SDK retries inside `AzureChatOpenAI` (default 2)
- **Message Conversion:** Dict ↔ LangChain message formats
- Kept as a selectable provider; also exposed as the `azure_openai_client` global

#### e. Embeddings Client (`embeddings.py`)
- **Batch Processing:** Efficient embedding generation
- **Retry Logic:** Handles rate limits
- **Async Operations:** Non-blocking I/O

### 5. Core (`app/core/`)

**Purpose:** Cross-cutting concerns

**Components:**

#### a. Configuration (`config.py`)
- **Pydantic Settings:** Type-safe environment variables
- **Validation:** Ensures required configs present
- **Computed Properties:** Derived values (e.g., bytes from MB)

#### b. Logging (`logging.py`)
- **Structured JSON:** Machine-readable logs
- **Context:** Request IDs, job IDs, user IDs
- **Levels:** Appropriate log levels per component

#### c. Observability (`observability.py`)
- **Metrics:** Latency, cost, groundedness tracking
- **Tracing:** Operation-level instrumentation
- **Context Managers:** Easy tracing integration

## Data Flow

### Chat Request Flow

```
1. User sends message
   ↓
2. API validates request (message count and size limits → 422)
   ↓
3. Guardrails check query safety; an emergency gets the emergency response
   immediately (no model call, never rate-limited)
   ↓
3b. Usage limits: per-IP rate, per-session rate, per-session daily tokens,
    global daily token budget (→ 429 with Retry-After)
   ↓
4. RAG chain/graph invoked
   ↓
5. Query rewritten (if using graph)
   ↓
6. Retrieval from vector DB
   ├─ Canonical layer
   ├─ Safety layer
   ├─ Practices layer
   └─ Q&A layer
   ↓
7. Context assembled (wrapped in <retrieved_context> with [Source: ...] labels,
   plus the request's prior user/assistant turns)
   ↓
8. LLM provider generates response (streamed from the provider into a server buffer)
   ↓
9. Guardrails check the complete response; internal [Source: ...] tags removed;
   disclaimers applied
   ↓
10. Sources built from the retrieved documents supplied to the model
   ↓
11. Approved text sent to client (SSE `content` chunks, `citations`, `[DONE]`)
```

**Streaming and safety.** `/api/chat` with `stream: true` never sends model text
before step 9 finishes. While the response is prepared, the stream carries only
SSE comments (`: keep-alive`, every `SSE_KEEPALIVE_SECONDS`) so proxies keep the
connection open. If generation fails or the model refuses partway through, the
buffered text is discarded and the client receives one `error` event with a
generic message and the request ID. The SSE event format is unchanged, but the
first `content` event arrives once the full answer has been generated and
validated, not token by token. Emergency responses to streaming requests use the
same SSE events.

**Sources (citations).** The `citations` field lists the documents retrieved from
Azure AI Search and supplied to the model, built server-side from their metadata
(`title`, and `page N` or the URL as `reference`; empty when neither exists).
Retrieval does not prove which source the model relied on, so clients label them
"Sources". Model-written source names are never trusted: answers are stripped of
`[Source: ...]` tags, and the graph endpoint validates citations against the
retrieved documents.

**Emergency policy.** `EMERGENCY_POLICY_FILE` points to a region policy (see
`emergency_policy.example.json`). Contacts are shown only when the file records
who approved them and when; extra keywords (e.g. Tamil) are used only when the
file records a reviewer. Without an approved policy the response tells users to
contact local emergency services or someone they trust, with no phone numbers.
Emergency keyword matching is whole-word for English; reviewed policy keywords
use substring matching (needed for Tamil suffixes). The system prompt also tells
the model, in any language, not to give meditation guidance to someone in crisis.

**Usage limits.** `app/core/usage.py` counts requests and tokens in memory (one
process) or Redis (`USAGE_STORE=redis`, falls back to memory if Redis fails). The
client IP comes from the socket unless `TRUSTED_PROXY_HOPS` is set, in which case
only that many right-most `X-Forwarded-For` entries are trusted. Sessions are
identified by the optional `X-Session-ID` header (graph: `thread_id`), falling
back to the IP. IPs and session IDs are stored and logged only as keyed hashes.
The public chatbot needs no login; account-specific LMS endpoints require
authentication as before.

**Graph state retention.** The LangGraph checkpointer is keyed by a fresh
per-request ID and the checkpoint is deleted after each request, so no
conversation state stays in memory and a client-supplied `thread_id` (only echoed
back) cannot address another client's state.

**Conversation history.** Clients send the conversation in `messages`. The last
user message is the question (and the retrieval query); up to
`LLM_MAX_HISTORY_MESSAGES` earlier user/assistant turns are forwarded to the
model. Client `system` messages are dropped. History is never stored server-side
or shared between requests.

### Ingestion Flow

```
1. User uploads PDF or provides URLs
   ↓
2. API creates job and queues task
   ↓
3. Celery worker picks up task
   ↓
4. Content processed:
   - PDF: Parse → Clean → Chunk
   - Web: Fetch → Parse → Clean → Chunk
   ↓
5. Generate embeddings (batch)
   ↓
6. Upsert to vector DB with metadata
   ↓
7. Update job status
   ↓
8. Client polls for completion
```

## Deployment Architecture

### Azure Container Apps

```
┌─────────────────────────────────────────────────────────────┐
│                  Azure Container Apps Environment            │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   API Container  │  │ Worker Container │                │
│  │  (1-5 replicas)  │  │  (1-3 replicas)  │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                            │
│           └─────────┬───────────┘                            │
│                     │                                        │
│           ┌─────────▼─────────┐                             │
│           │  Redis Container  │                             │
│           │   (Internal)      │                             │
│           └───────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Azure Services                            │
│  • OpenAI  • AI Search  • Blob Storage  • Key Vault        │
└─────────────────────────────────────────────────────────────┘
```

### Scaling Strategy

**API Containers:**
- Min: 1 replica
- Max: 5 replicas
- Scale trigger: HTTP concurrency > 50

**Worker Containers:**
- Min: 1 replica
- Max: 3 replicas
- Scale trigger: Queue depth > 10

## Security Architecture

### Secrets Management

```
GitHub Secrets
    ↓
Azure Key Vault
    ↓
Container Apps Environment Variables
    ↓
Application Runtime
```

### Network Security

- **Ingress:** External (API), Internal (Redis, Worker)
- **Egress:** Controlled via NSG rules
- **TLS:** Enforced for all external traffic
- **Authentication:** Azure Managed Identity where possible

## Performance Considerations

### Caching Strategy

1. **Query Results:** Cache frequent queries (future)
2. **Embeddings:** Cache for duplicate content
3. **Static Assets:** CDN for UI files

### Optimization Techniques

1. **Batch Processing:** Embeddings generated in batches
2. **Async I/O:** Non-blocking operations throughout
3. **Connection Pooling:** Reuse HTTP connections
4. **Lazy Loading:** Load resources on demand

## Monitoring & Observability

### Metrics Tracked

- **Latency:** First token, total response time
- **Cost:** Token usage per request
- **Quality:** Groundedness, citation coverage
- **Errors:** Rate, types, patterns
- **Usage:** Requests per endpoint, user patterns

### Logging Strategy

- **Structured JSON:** All logs in JSON format
- **Context:** Request/job IDs for tracing
- **Levels:** DEBUG, INFO, WARNING, ERROR
- **Retention:** 30 days in Log Analytics

### Alerting

- **Health Checks:** Automated monitoring
- **Error Rates:** Threshold-based alerts
- **Latency:** P95/P99 tracking
- **Cost:** Budget alerts

## Disaster Recovery

### Backup Strategy

1. **Vector DB:** Regular index exports
2. **Blob Storage:** Soft delete + versioning enabled
3. **Configuration:** Infrastructure as Code (IaC)

### Recovery Procedures

1. **Index Rebuild:** From blob storage backups
2. **Container Restart:** Automated health checks
3. **Rollback:** Previous container image deployment

## Future Enhancements

### Planned Features

1. **Multi-tenancy:** User accounts and personalization
2. **Advanced Analytics:** User journey tracking
3. **A/B Testing:** Prompt and model experimentation
4. **Voice Interface:** Speech-to-text integration
5. **Mobile Apps:** Native iOS/Android clients

### Scalability Roadmap

1. **Read Replicas:** For vector DB
2. **CDN Integration:** Global content delivery
3. **Edge Computing:** Regional deployments
4. **Microservices:** Service decomposition

---

For implementation details, see the code documentation and inline comments.