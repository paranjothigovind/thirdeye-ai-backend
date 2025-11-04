# 🧘 Third Eye Meditation AI Chatbot

An Azure-powered Retrieval-Augmented Generation (RAG) chatbot that provides grounded, compassionate guidance on Third Eye (Ajna) meditation. Built with Python, LangChain/LangGraph, Azure OpenAI, and Azure AI Search.

## ✨ Features

- **RAG-based answers** grounded in curated sources with inline citations
- **Angelitic RAG layering**: canonical teachings, safety/contraindications, practices, Q&A exemplars
- **Append-only ingestion** for PDFs with versioned upserts
- **Optional web scraping** when URLs are explicitly provided
- **Azure OpenAI** for chat generation and embeddings
- **Streaming responses** with collapsible citations
- **Safety guardrails** for responsible meditation guidance
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

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- Azure account with:
  - Azure OpenAI Service
  - Azure AI Search
  - Azure Blob Storage
  - Azure Key Vault (recommended)

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

### Chat
```bash
POST /api/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "How to practice Trataka safely?"}
  ],
  "stream": true
}
```

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
    "https://example.com/third-eye-guide",
    "https://example.com/trataka-practice"
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
AZURE_SEARCH_INDEX=third-eye-docs

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STRING=your-connection-string
AZURE_BLOB_CONTAINER=third-eye-pdfs

# Redis
REDIS_URL=redis://localhost:6379/0

# RAG Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
TOP_K_RESULTS=6
```

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=html
```

## 🚢 Deployment

### Azure Container Apps

1. **Build and push images**
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

2. **Deploy via GitHub Actions**
- Configure secrets in GitHub repository
- Push to main branch
- CI/CD pipeline will automatically deploy

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

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

[Specify your license here]

## 🙏 Acknowledgments

- Azure OpenAI and Azure AI Search
- LangChain/LangGraph ecosystem
- Community best practices for safe meditation guidance

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Contact: [your-email]

---

Made with 🧘 for the meditation community