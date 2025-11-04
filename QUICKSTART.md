# ⚡ Quick Start Guide

Get the Third Eye Meditation AI Chatbot running in 5 minutes!

## Prerequisites

- Python 3.11+
- Docker (optional, for Redis)
- Azure account (for production deployment)

## Option 1: Local Development (Fastest)

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd thirdeye-ai-backend

# Run setup script
chmod +x scripts/local_dev.sh
./scripts/local_dev.sh
```

### 2. Configure Environment

Edit `.env` file with your Azure credentials:

```bash
# Minimum required variables
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002

AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-key

AZURE_BLOB_CONNECTION_STRING=your-connection-string

REDIS_URL=redis://localhost:6379/0
```

### 3. Start Services

```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start API
make dev

# Terminal 3: Start Worker
make worker
```

### 4. Seed Knowledge Base

```bash
make seed
```

### 5. Test It!

Open http://localhost:8000 in your browser and start chatting!

Or test via API:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the Third Eye chakra?"}],
    "stream": false
  }'
```

## Option 2: Docker Compose (Recommended)

### 1. Setup

```bash
# Clone repository
git clone <repository-url>
cd thirdeye-ai-backend

# Copy environment file
cp .env.example .env
# Edit .env with your Azure credentials
```

### 2. Start Everything

```bash
docker-compose up -d
```

### 3. Seed Knowledge Base

```bash
docker-compose exec api python scripts/seed_knowledge.py
```

### 4. Access

- UI: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

## Option 3: Azure Deployment

### 1. Provision Resources

```bash
chmod +x scripts/setup_azure.sh
./scripts/setup_azure.sh
```

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repository:
- `ACR_LOGIN_SERVER`
- `ACR_USERNAME`
- `ACR_PASSWORD`
- `AZURE_CREDENTIALS`
- `AZURE_RESOURCE_GROUP`

### 3. Deploy

```bash
git push origin main
```

GitHub Actions will automatically build and deploy!

## Common Commands

```bash
# Development
make dev          # Start API server
make worker       # Start Celery worker
make test         # Run tests
make lint         # Check code quality
make format       # Format code

# Docker
make docker-up    # Start all containers
make docker-down  # Stop all containers
make docker-logs  # View logs

# Utilities
make seed         # Seed knowledge base
make test-api     # Test API endpoints
make clean        # Clean up generated files
```

## Testing the Chatbot

### Via Web UI

1. Open http://localhost:8000
2. Type a question like "How do I practice Trataka?"
3. See streaming response with citations!

### Via API

```bash
# Simple chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the benefits of Third Eye meditation?"}
    ],
    "stream": false
  }'

# Upload PDF
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@meditation-guide.pdf"

# Ingest URLs
curl -X POST http://localhost:8000/api/ingest/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/meditation-article"]
  }'

# Check job status
curl http://localhost:8000/api/jobs/{job_id}
```

## Sample Questions to Try

1. "What is the Third Eye chakra?"
2. "How do I practice Trataka safely?"
3. "What are the contraindications for Third Eye meditation?"
4. "Can meditation help with anxiety?"
5. "How long should I meditate as a beginner?"

## Troubleshooting

### Redis Connection Error

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine
```

### Azure OpenAI Rate Limits

- Check your deployment quotas in Azure Portal
- Increase TPM (tokens per minute) if needed
- Add retry logic (already implemented)

### Vector Store Index Not Found

```bash
# The index is auto-created on first run
# If issues persist, check Azure AI Search service status
```

### Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

## Next Steps

1. **Customize Content:** Add your own meditation guides
2. **Adjust Prompts:** Modify `app/rag/prompts.py` for different tone
3. **Add Features:** See CONTRIBUTING.md for ideas
4. **Deploy to Production:** Follow DEPLOYMENT.md

## Getting Help

- 📖 Read the full [README.md](README.md)
- 🏗️ Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- 🚀 See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup
- 🐛 Report issues on GitHub
- 💬 Join discussions for questions

## What's Next?

- [ ] Customize the knowledge base with your content
- [ ] Adjust safety guardrails for your use case
- [ ] Set up monitoring and alerts
- [ ] Configure custom domain
- [ ] Add user authentication (if needed)
- [ ] Implement feedback collection

---

Happy meditating! 🧘‍♀️✨