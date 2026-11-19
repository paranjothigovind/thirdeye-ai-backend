# 🧘 Nettrikkan AI Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about **Nettrikkan** (Inner Awareness), including *Meyunarvu* (true inner awareness), strictly from the teaching material you ingest. It answers in English or Tamil, only from retrieved sources, and does not start a practice unless the user asks for one. Built with Python, FastAPI, LangChain/LangGraph, Azure AI Search, and either Anthropic Claude or Azure OpenAI for answer generation.

> This repository was previously named after "Third Eye (Ajna) meditation". The system now follows the Nettrikkan framework: natural breath only, no mantras or visualization, witnessing rather than effort. Some resource names (the `thirdeye-ai-backend` repo, the `thirdeye-*` index and `third-eye-*` container defaults) keep the old name for compatibility.

## ✨ Features

- **RAG-based answers** grounded in curated sources with inline citations
- **Angelitic RAG layering**: canonical teachings, safety/contraindications, practices, Q&A exemplars
- **Append-only ingestion** for PDFs with versioned upserts
- **Optional web scraping** when URLs are explicitly provided
- **Choice of generation model**: Anthropic Claude or Azure OpenAI (`LLM_PROVIDER`); embeddings always use Azure OpenAI
- **Streaming responses** with collapsible citations
- **Tamil and English**: replies in Tamil when the question is in Tamil, using the Nettrikkan terms
- **Query rewriting** to Nettrikkan terminology (e.g. "third eye" → "Nettrikkan", "focus" → "Thaarana") for better retrieval
- **Safety guardrails** for responsible guidance and emergency situations
- **Azure-native deployment** with CI/CD

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│ Azure OpenAI │────▶│   Azure AI  │
│     API     │     │   (Chat +    │     │   Search    │
└─────────────┘     │  Embeddings) │     │  (Vector)   │
       │            └──────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Celery    │────▶│ Azure Blob   │
│   Workers   │     │   Storage    │
└─────────────┘     └──────────────┘
```

### Answer pipeline: corrective RAG with LangGraph

`POST /api/chat/graph` runs a LangGraph state machine (`app/rag/graph.py`). It
retrieves, checks its own work, and retries before answering:

```
rewrite_query → retrieve → check_retrieval ─┬─ weak (<2 documents) → rewrite_query   (retry)
                                            └─ ok → generate → check_response ─┬─ fails check → retrieve   (retry)
                                                                               └─ ok → add_citations → END
```

- **rewrite_query** rewrites the question into Nettrikkan terminology (e.g. "third eye" → "Nettrikkan").
- **retrieve** runs hybrid search on Azure AI Search (BM25 keyword + vector).
- **check_retrieval** loops back to `rewrite_query` when fewer than 2 documents come back.
- **generate** answers only from the retrieved excerpts, using the configured LLM provider.
- **check_response** applies the guardrails (medical advice, missing sources when nothing was retrieved) and loops back to `retrieve` if the answer fails.
- **add_citations** attaches the sources server-side from the retrieved documents.

Both loops share one retry budget (`max_retries = 2`), so a request cannot loop forever.
The streaming `POST /api/chat` endpoint uses the simpler chain in `app/rag/chains.py`.
Checkpoints are kept in memory (`MemorySaver`), see "What I'd do next" below.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- Azure account with:
  - Azure OpenAI Service (embeddings always; chat too if `LLM_PROVIDER=azure_openai`)
  - Azure AI Search
  - Azure Blob Storage
  - Azure Key Vault (recommended)
- An Anthropic API key, only if `LLM_PROVIDER=anthropic` (see below)

### Local Development

1. **Clone the repository**
```bash
git clone <repository-url>
cd thirdeye-ai-backend
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Azure credentials
# Also set SECRET_KEY and JWT_SECRET_KEY (required, no defaults; see Configuration)
```

5. **Start Redis (for Celery)**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

6. **Run the API**
```bash
uvicorn app.main:app --reload
```

7. **Run the worker (in another terminal)**
```bash
celery -A app.ingestion.workers worker --loglevel=INFO
```

8. **Access the UI**
```
http://localhost:8000
```

### Docker Compose

```bash
# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📡 API Endpoints

### Authentication

#### User Registration
```bash
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "testuser",
  "password": "securepassword"
}
```

#### User Login
```bash
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=testuser&password=securepassword
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Get Current User (Authenticated)
```bash
GET /api/auth/me
Authorization: Bearer <access_token>
```

#### Get User Subscriptions (Authenticated)
```bash
GET /api/auth/subscriptions
Authorization: Bearer <access_token>
```

### Chat
```bash
POST /api/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What is Meyunarvu?"}
  ],
  "stream": true
}
```

The last `user` message is the question. Earlier `user`/`assistant` messages are
optional conversation history; `system` messages from clients are ignored.
Streamed text is sent only after the full response has passed the safety checks
(the stream carries `: keep-alive` comments meanwhile). `citations` lists the
retrieved documents supplied to the model ("Sources"). An optional `X-Session-ID`
header identifies an anonymous session for usage limits; over-limit requests get
HTTP 429, oversized requests HTTP 422.

### Ingest PDF
```bash
POST /api/ingest
Content-Type: multipart/form-data

file: <pdf-file>
```

### Ingest URLs
```bash
POST /api/ingest/urls
Content-Type: application/json

{
  "urls": [
    "https://example.com/nettrikkan-introduction",
    "https://example.com/nettrikkan-faq"
  ]
}
```

### Job Status
```bash
GET /api/jobs/{job_id}
```

### Health Check
```bash
GET /api/health
GET /api/ready
```

## 🔧 Configuration

Key environment variables:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
AZURE_SEARCH_INDEX=thirdeye-knowledge-index-v2

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STRING=your-connection-string
AZURE_BLOB_CONTAINER=third-eye-pdfs

# Authentication - REQUIRED, no defaults. The app refuses to start without them.
# Use two different random values (32+ characters), e.g.:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=
JWT_SECRET_KEY=

# Database (local SQLite file by default; never commit it)
DATABASE_URL=sqlite:///./thirdeye.db

# Redis
REDIS_URL=redis://localhost:6379/0

# RAG Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
TOP_K_RESULTS=6
```

See [.env.example](.env.example) for the full list.

### 🤖 LLM provider: Claude or Azure OpenAI

Answer generation goes through one provider, chosen with `LLM_PROVIDER`:

| `LLM_PROVIDER` | Generates answers with | Extra settings needed |
|---|---|---|
| `azure_openai` (default) | Azure OpenAI chat deployment | `AZURE_OPENAI_CHAT_*` |
| `anthropic` | Anthropic Claude | `ANTHROPIC_API_KEY` |

To use Claude, add to `.env` and restart the API:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...        # from https://console.anthropic.com
# Optional (defaults shown)
ANTHROPIC_MODEL=claude-opus-5-5
ANTHROPIC_MAX_TOKENS=16000
ANTHROPIC_TIMEOUT=120               # seconds per attempt
ANTHROPIC_MAX_RETRIES=2             # SDK retries for 408/409/429/5xx/connection errors
ANTHROPIC_EFFORT=medium             # low|medium|high|xhigh|max; empty = model default
ANTHROPIC_REFUSAL_FALLBACK=true     # server-side fallback model if Claude declines (beta)
LLM_MAX_HISTORY_MESSAGES=10         # prior turns from the request sent to the model
```

To switch back, set `LLM_PROVIDER=azure_openai` (or remove it) and restart.
The API refuses to start if `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` is empty.

What stays on Azure whichever provider you pick: **Azure OpenAI embeddings**
(`AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`), **Azure AI Search** (index, vectors and
hybrid retrieval), **Azure Blob Storage**, plus Redis/Celery for ingestion. The
Azure chat settings are still required by configuration even when Claude is selected.
Switching providers does not touch embeddings, the index schema or its vectors.

> **Billing:** Claude API usage is billed per token to your Anthropic Console
> account (pay-as-you-go API credits). It is separate from a Claude Pro or Max
> subscription on claude.ai, which does not include API access.

How it fits together: [ARCHITECTURE.md → Models](ARCHITECTURE.md#4-models-appmodels).

### 🚦 Before enabling Claude publicly

The chatbot stays open without login, so set limits first (all in [.env.example](.env.example)):

- `LLM_DAILY_TOKEN_BUDGET`: total tokens per UTC day (0 = unlimited; the app warns at startup)
- `RATE_LIMIT_IP_PER_MINUTE`, `RATE_LIMIT_SESSION_PER_HOUR`, `SESSION_DAILY_TOKEN_LIMIT`
- `CHAT_MAX_MESSAGES`, `CHAT_MAX_MESSAGE_CHARS`, `CHAT_MAX_TOTAL_CHARS`
- `TRUSTED_PROXY_HOPS`: number of reverse proxies that append to `X-Forwarded-For`
  (keep `0` unless you know the count; a wrong value lets clients spoof their IP)
- `USAGE_STORE=redis` when running more than one instance

Each LLM call logs one `llm_call` JSON record with tokens, models, fallback use,
latency and request IDs (never prompts, answers or keys).

### 🚨 Emergency policy

Emergency replies tell users to contact local emergency services or a trusted
person, without phone numbers, until an approved policy is configured:
copy [emergency_policy.example.json](emergency_policy.example.json), add only
contact details verified from official sources and approved by the Netrikkan team
(with `approved_by` / `approved_on`), and set `EMERGENCY_POLICY_FILE`. Tamil
emergency keywords go in the same file and are used only once a native Tamil
speaker is recorded in `keywords.reviewed_by`.

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=html
```

The Claude integration tests (`tests/test_llm_providers.py`,
`tests/test_chat_integration.py`) run the real Anthropic SDK against an in-process
mock HTTP transport. They make no network calls, need no `ANTHROPIC_API_KEY` and
use no API credits. The test suite still reads the Azure settings from `.env`
when importing the app. `tests/test_frontend_sse.py` tests the bundled web UI's
stream parser with Node.js (skipped if `node` is not installed); run it alone with
`node --test "tests/frontend/*.test.mjs"`.

## 🚢 Deployment

The application is designed to be deployed on Microsoft Azure. See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment instructions.

### Quick Deploy to Azure Container Apps

1. **Provision Azure Resources**
```bash
# Run automated setup script
chmod +x scripts/setup_azure.sh
./scripts/setup_azure.sh
```

2. **Build and Push Docker Images**
```bash
# Login to Azure Container Registry
az acr login --name <your-acr-name>

# Build and push API
docker build -t <your-acr>.azurecr.io/third-eye-chatbot:latest -f docker/Dockerfile .
docker push <your-acr>.azurecr.io/third-eye-chatbot:latest

# Build and push worker
docker build -t <your-acr>.azurecr.io/third-eye-worker:latest -f docker/Dockerfile.worker .
docker push <your-acr>.azurecr.io/third-eye-worker:latest
```

3. **Deploy Containers**
```bash
# Deploy using Azure CLI (see DEPLOYMENT.md for full commands)
az containerapp create --name third-eye-api ...
az containerapp create --name third-eye-worker ...
```

4. **Automated Deployment via GitHub Actions**
- Configure Azure credentials in GitHub repository secrets
- Push to main branch
- CI/CD pipeline will automatically build and deploy

### Deployment Options

- **Azure Container Apps** (Recommended) - Fully managed serverless containers with auto-scaling
- **Azure App Service** - Simple PaaS deployment with Docker support
- **Azure Kubernetes Service (AKS)** - Advanced orchestration for complex deployments

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions on each deployment method.

## 📊 Observability

- **Structured logging**: JSON logs with request IDs
- **LangSmith tracing**: Enable with `LANGCHAIN_TRACING_V2=true`
- **Metrics**: Track latency, cost, groundedness
- **Health checks**: `/api/health` and `/api/ready`

## 🛡️ Safety & Ethics

- ⚠️ No medical advice or diagnosis
- 🙏 Respects spiritual diversity
- 📚 All responses cite sources
- 🚨 Emergency detection and appropriate responses
- ✅ Safety warnings for practices

## 📚 Documentation

- [API Documentation](http://localhost:8000/api/docs) (Swagger UI)
- [ReDoc](http://localhost:8000/api/redoc)

## 🔭 What I'd do next

- **Evals:** build a small golden set of English and Tamil questions with expected
  sources, and measure retrieval hit rate and groundedness, so prompt and retriever
  changes can be compared instead of judged by eye.
- **Persistent checkpointer:** the graph uses LangGraph's in-memory `MemorySaver`, so
  conversation state is lost on restart and not shared between instances. Swap it for a
  Redis or Postgres checkpointer before running more than one replica.
- **More tests for the graph itself:** cover each node and both retry loops
  (weak retrieval, failed response check, retry budget exhausted) with a stubbed
  retriever and LLM; today most coverage is at the API and provider level.
- **One chat path:** `/api/chat` (streaming, simple chain) and `/api/chat/graph`
  (corrective graph) answer differently. Move streaming onto the graph, or retire one.
- **Real data store:** replace the local SQLite database with Postgres (Alembic
  migrations are already in place) and keep database files out of the repository.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

See [LICENSE](LICENSE).

## 🙏 Acknowledgments

- Azure OpenAI and Azure AI Search
- LangChain/LangGraph ecosystem
- The Nettrikkan team and teachers whose material grounds the answers

## 📞 Support

For issues and questions:
- Open an issue on GitHub

---

Made with 🧘 for the meditation community