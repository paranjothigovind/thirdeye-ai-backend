# 🚀 Deployment Guide

This guide covers deploying the Third Eye Meditation AI Chatbot to Azure and Vercel.

## Deployment Options

### Option 1: Full-Stack on Railway
Deploy both backend and frontend to Railway using Docker containers for easy scaling and management.

### Option 2: Full-Stack on Vercel
Deploy both backend and frontend to Vercel using serverless functions for the API and static hosting for the UI.

### Option 3: Full-Stack on Azure (Recommended for Production)
Deploy both backend and frontend to Azure Container Apps for a complete, managed solution.

This guide covers all options.

## Prerequisites

### For Railway Deployment
- Railway account (free tier available)
- Docker installed locally (for testing)
- GitHub account (for CI/CD)

### For Vercel Deployment
- Vercel account (free tier available)
- Node.js 20+ and npm installed
- GitHub account (for CI/CD)

### For Azure Deployment
- Azure CLI installed and configured
- Docker installed
- Azure subscription with appropriate permissions
- GitHub account (for CI/CD)

## 1. Provision Azure Resources

### Option A: Automated Setup (Recommended)

Run the setup script:

```bash
chmod +x scripts/setup_azure.sh
./scripts/setup_azure.sh
```

This will create:
- Resource Group
- Azure OpenAI Service (with GPT-4 and embeddings deployments)
- Azure AI Search
- Azure Blob Storage
- Azure Key Vault
- Azure Container Registry

### Option B: Manual Setup

Follow the Azure Portal instructions to create each service individually.

## 2. Configure Environment Variables

### Local Development

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Update `.env` with your Azure credentials from Key Vault:
```bash
# Get secrets from Key Vault
az keyvault secret show --vault-name third-eye-kv --name AZURE-OPENAI-KEY --query value -o tsv
az keyvault secret show --vault-name third-eye-kv --name AZURE-OPENAI-ENDPOINT --query value -o tsv
# ... etc
```

### GitHub Secrets (for CI/CD)

Configure the following secrets in your GitHub repository:

```
ACR_LOGIN_SERVER=<your-acr>.azurecr.io
ACR_USERNAME=<acr-username>
ACR_PASSWORD=<acr-password>
AZURE_CREDENTIALS=<service-principal-json>
AZURE_RESOURCE_GROUP=third-eye-rg
```

To create Azure credentials:
```bash
az ad sp create-for-rbac \
  --name "third-eye-github-actions" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/third-eye-rg \
  --sdk-auth
```

## 3. Build and Push Docker Images

### Manual Build

```bash
# Login to ACR
az acr login --name <your-acr-name>

# Build and push API image
docker build -t <your-acr>.azurecr.io/third-eye-chatbot:latest -f docker/Dockerfile .
docker push <your-acr>.azurecr.io/third-eye-chatbot:latest

# Build and push worker image
docker build -t <your-acr>.azurecr.io/third-eye-worker:latest -f docker/Dockerfile.worker .
docker push <your-acr>.azurecr.io/third-eye-worker:latest
```

### Automated via GitHub Actions

Push to `main` branch to trigger the CI/CD pipeline.

## 4. Deploy to Azure Container Apps

### Create Container Apps Environment

```bash
az containerapp env create \
  --name third-eye-env \
  --resource-group third-eye-rg \
  --location eastus
```

### Deploy API Container

```bash
az containerapp create \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image <your-acr>.azurecr.io/third-eye-chatbot:latest \
  --target-port 8000 \
  --ingress external \
  --registry-server <your-acr>.azurecr.io \
  --registry-username <acr-username> \
  --registry-password <acr-password> \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 5 \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_SEARCH_ENDPOINT=secretref:azure-search-endpoint \
    AZURE_SEARCH_KEY=secretref:azure-search-key \
    AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection \
    REDIS_URL=redis://third-eye-redis:6379/0
```

### Deploy Worker Container

```bash
az containerapp create \
  --name third-eye-worker \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image <your-acr>.azurecr.io/third-eye-worker:latest \
  --registry-server <your-acr>.azurecr.io \
  --registry-username <acr-username> \
  --registry-password <acr-password> \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_SEARCH_ENDPOINT=secretref:azure-search-endpoint \
    AZURE_SEARCH_KEY=secretref:azure-search-key \
    AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection \
    REDIS_URL=redis://third-eye-redis:6379/0
```

### Deploy Redis

```bash
az containerapp create \
  --name third-eye-redis \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image redis:7-alpine \
  --target-port 6379 \
  --ingress internal \
  --cpu 0.25 \
  --memory 0.5Gi
```

## 5. Configure Secrets

Store secrets in Azure Key Vault and reference them in Container Apps:

```bash
# Create secrets in Container Apps
az containerapp secret set \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --secrets \
    azure-openai-key=keyvaultref:<key-vault-url>/secrets/AZURE-OPENAI-KEY,identityref:<managed-identity-id> \
    azure-openai-endpoint=keyvaultref:<key-vault-url>/secrets/AZURE-OPENAI-ENDPOINT,identityref:<managed-identity-id>
```

## 6. Seed Knowledge Base

After deployment, seed the knowledge base:

```bash
# SSH into a container or run locally with production credentials
python scripts/seed_knowledge.py
```

## 7. Verify Deployment

Test the deployed API:

```bash
# Set API URL
export API_URL=https://third-eye-api.<region>.azurecontainerapps.io

# Run tests
bash scripts/test_api.sh
```

## 8. Configure Custom Domain (Optional)

```bash
az containerapp hostname add \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --hostname chat.yourdomain.com
```

## 9. Enable Monitoring

### Application Insights

```bash
az monitor app-insights component create \
  --app third-eye-insights \
  --location eastus \
  --resource-group third-eye-rg

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app third-eye-insights \
  --resource-group third-eye-rg \
  --query instrumentationKey -o tsv)

# Update container app with instrumentation key
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
```

### Log Analytics

Container Apps automatically sends logs to Log Analytics. View logs:

```bash
az containerapp logs show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --follow
```

## 10. Scaling Configuration

### Auto-scaling Rules

```bash
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --min-replicas 2 \
  --max-replicas 10 \
  --scale-rule-name http-rule \
  --scale-rule-type http \
  --scale-rule-http-concurrency 50
```

## 11. Backup and Disaster Recovery

### Backup Azure AI Search Index

```bash
# Export index definition
az search index show \
  --service-name third-eye-search \
  --name third-eye-docs \
  --resource-group third-eye-rg > index-backup.json
```

### Backup Blob Storage

Enable soft delete and versioning:

```bash
az storage account blob-service-properties update \
  --account-name <storage-account> \
  --enable-delete-retention true \
  --delete-retention-days 30 \
  --enable-versioning true
```

## 12. Cost Optimization

- Use Azure Reserved Instances for predictable workloads
- Enable auto-scaling to scale down during low traffic
- Use Azure Cost Management to monitor spending
- Consider Azure Spot Instances for worker containers

## Troubleshooting

### Check Container Logs

```bash
az containerapp logs show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --follow
```

### Check Container Status

```bash
az containerapp show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --query properties.runningStatus
```

### Restart Container

```bash
az containerapp revision restart \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --revision <revision-name>
```

## Security Best Practices

1. **Use Managed Identity** instead of connection strings where possible
2. **Enable Azure Key Vault** for all secrets
3. **Configure Network Security Groups** to restrict access
4. **Enable Azure DDoS Protection** for production
5. **Implement rate limiting** in the API
6. **Regular security updates** for base images
7. **Enable Azure Security Center** recommendations

## Maintenance

### Update Application

1. Build new Docker images with updated code
2. Push to ACR
3. Update Container Apps with new image:

```bash
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --image <your-acr>.azurecr.io/third-eye-chatbot:latest
```

### Database Maintenance

- Regularly review and clean up old document versions
- Monitor Azure AI Search index size and performance
- Optimize queries based on usage patterns

## Deploy Full-Stack to Railway

### Prerequisites

- Railway account (free tier available)
- Docker installed locally (for testing)
- GitHub account (for CI/CD)

### 1. Prepare the Application for Railway

Railway uses Docker containers for deployment. The application is already configured with Docker support.

#### Create Dockerfile (if not present)

Ensure you have a `Dockerfile` in the root directory:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build the frontend
RUN npm install && npm run build

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Create railway.json (Optional)

Create a `railway.json` file for Railway-specific configuration:

```json
{
  "build": {
    "builder": "dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

### 2. Set Up Environment Variables in Railway

#### Required Environment Variables

Set these in your Railway project settings:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
AZURE_SEARCH_INDEX=thirdeye-knowledge-index-v2
AZURE_BLOB_CONNECTION_STRING=your-connection-string
AZURE_BLOB_CONTAINER=third-eye-pdfs
REDIS_URL=redis://your-redis-url:6379/0
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=third-eye-chatbot
APP_ENV=production
CORS_ORIGINS=["https://your-railway-app.up.railway.app"]
MAX_UPLOAD_SIZE_MB=25
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
TOP_K_RESULTS=6
EMBEDDING_DIMENSIONS=3072
WEB_SCRAPING_RPS=2.0
```

### 3. Deploy to Railway

#### Option A: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Deploy
railway up
```

#### Option B: Using Railway Dashboard

1. Connect your GitHub repository to Railway
2. Railway will automatically detect the Dockerfile
3. Set all environment variables in Project Settings > Variables
4. Deploy by pushing to main branch or clicking Deploy

### 4. Add Database Service (Redis)

Railway makes it easy to add services:

1. In Railway dashboard, go to your project
2. Click "Add Service" > "Database" > "Redis"
3. Note the Redis URL and update your environment variables

### 5. Seed Knowledge Base

After deployment, seed the knowledge base:

```bash
# Use Railway's service shell or create a local script
python scripts/seed_knowledge.py
```

### 6. Verify Deployment

1. Visit your Railway URL (usually `https://your-project-name.up.railway.app`)
2. Test chat functionality
3. Test PDF upload and URL ingestion
4. Check Railway logs for any errors

### 7. Custom Domain (Optional)

In Railway dashboard:
- Go to Project Settings > Domains
- Add your custom domain
- Follow DNS configuration instructions

### Troubleshooting Railway Deployment

#### Build Errors
- Ensure Dockerfile is correct and all dependencies are listed
- Check Railway build logs for specific errors
- Verify Python version compatibility

#### Memory Issues
- Railway has memory limits; monitor usage in dashboard
- Consider upgrading plan for higher limits

#### Environment Variables
- Double-check all required environment variables are set
- Ensure Azure service endpoints are accessible

#### Static File Serving
- Railway serves static files from the built frontend
- Ensure `npm run build` completes successfully

---

## Deploy Full-Stack to Vercel

### Prerequisites

- Vercel account (free tier available)
- Node.js 20+ and npm installed locally (for testing)
- Azure OpenAI, Azure AI Search, and Azure Blob Storage accounts

### 1. Prepare the Application for Vercel

#### Update Configuration for Serverless

Vercel uses serverless functions for the API. Update `app/main.py` to work with Vercel's serverless environment:

```python
# Add this at the top of app/main.py
import os
from fastapi.middleware.wsgi import WSGIMiddleware

# For Vercel deployment, use WSGI
if os.getenv("VERCEL"):
    app = WSGIMiddleware(app)
```

#### Update Environment Variables

Create a `vercel.json` file in the root directory:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "functions": {
    "api/**/*.py": {
      "runtime": "python3.11"
    }
  },
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/api/$1"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

### 2. Set Up Environment Variables in Vercel

#### Required Environment Variables

Set these in your Vercel project settings:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
AZURE_SEARCH_INDEX=thirdeye-knowledge-index-v2
AZURE_BLOB_CONNECTION_STRING=your-connection-string
AZURE_BLOB_CONTAINER=third-eye-pdfs
REDIS_URL=redis://your-redis-url:6379/0
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=third-eye-chatbot
APP_ENV=production
CORS_ORIGINS=["https://your-vercel-app.vercel.app"]
MAX_UPLOAD_SIZE_MB=25
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
TOP_K_RESULTS=6
EMBEDDING_DIMENSIONS=3072
WEB_SCRAPING_RPS=2.0
```

### 3. Deploy to Vercel

#### Option A: Using Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod

# Set environment variables
vercel env add AZURE_OPENAI_ENDPOINT
vercel env add AZURE_OPENAI_API_KEY
# ... add all required environment variables
```

#### Option B: Using Vercel Dashboard

1. Connect your GitHub repository to Vercel
2. Vercel will automatically detect the `vercel.json` configuration
3. Set all environment variables in Project Settings > Environment Variables
4. Deploy by pushing to main branch or clicking Deploy

### 4. Configure Python Runtime

Create a `requirements.txt` file (if not already present) with Python dependencies:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-multipart>=0.0.6
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-community>=0.0.20
langgraph>=0.0.20
langsmith>=0.0.77
azure-search-documents>=11.4.0
azure-storage-blob>=12.19.0
azure-identity>=1.15.0
openai>=1.12.0
pymupdf>=1.23.0
celery>=5.3.0
redis>=5.0.0
beautifulsoup4>=4.12.0
requests>=2.31.0
python-dotenv>=1.0.0
tenacity>=8.2.0
tiktoken>=0.5.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0
```

### 5. Handle Static Files and API Routes

Vercel serves static files from the `dist` directory and routes API calls to serverless functions. The `vercel.json` configuration handles this routing.

### 6. Seed Knowledge Base

After deployment, seed the knowledge base:

```bash
# Use Vercel's function logs or create a local script
python scripts/seed_knowledge.py
```

### 7. Verify Deployment

1. Visit your Vercel URL
2. Test chat functionality
3. Test PDF upload and URL ingestion
4. Check Vercel function logs for any errors

### 8. Custom Domain (Optional)

In Vercel dashboard:
- Go to Project Settings > Domains
- Add your custom domain
- Follow DNS configuration instructions

### Troubleshooting Vercel Deployment

#### Function Timeout
- Vercel serverless functions have a 10-second timeout for free tier
- Consider upgrading to Pro plan for longer timeouts
- Optimize API responses for speed

#### Memory Limits
- Free tier has 1008 MB RAM limit
- Monitor memory usage in Vercel dashboard

#### Cold Starts
- Serverless functions may have cold start delays
- Consider keeping functions warm with cron jobs

#### Build Errors
- Ensure Python version is compatible (3.11 recommended)
- Check that all dependencies are in `requirements.txt`
- Verify `vercel.json` configuration

#### API Routing Issues
- Check `vercel.json` rewrites configuration
- Ensure API routes match the expected patterns

---

For more information, see:
- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure OpenAI Documentation](https://docs.microsoft.com/azure/cognitive-services/openai/)
- [Azure AI Search Documentation](https://docs.microsoft.com/azure/search/)
- [Vercel Documentation](https://vercel.com/docs)
