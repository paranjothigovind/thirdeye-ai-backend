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
- Streaming Server-Sent Events (SSE) for real-time responses
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

**Purpose:** Azure OpenAI integration

**Components:**

#### a. Azure OpenAI Client (`azure_openai.py`)
- **Streaming:** Async token-by-token generation
- **Retry Logic:** Exponential backoff for transient failures
- **Message Conversion:** Dict ↔ LangChain message formats

#### b. Embeddings Client (`embeddings.py`)
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
2. API validates request
   ↓
3. Guardrails check query safety
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
7. Context assembled
   ↓
8. LLM generates response
   ↓
9. Guardrails check response
   ↓
10. Citations extracted
   ↓
11. Stream to client
```

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