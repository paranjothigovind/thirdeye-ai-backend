# 🚀 Azure Deployment Guide

This guide covers deploying the Third Eye Meditation AI Chatbot to Microsoft Azure using various deployment options.

## 📋 Table of Contents

1. [Deployment Options](#deployment-options)
2. [Prerequisites](#prerequisites)
3. [Azure Resource Provisioning](#azure-resource-provisioning)
4. [Deployment Methods](#deployment-methods)
   - [Azure Container Apps (Recommended)](#option-1-azure-container-apps-recommended)
   - [Azure App Service](#option-2-azure-app-service)
   - [Azure Kubernetes Service (AKS)](#option-3-azure-kubernetes-service-aks)
5. [Configuration](#configuration)
6. [Monitoring & Observability](#monitoring--observability)
7. [Security Best Practices](#security-best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Deployment Options

### Option 1: Azure Container Apps (Recommended)
**Best for:** Production workloads with auto-scaling, microservices architecture, and serverless container deployment.

**Pros:**
- Fully managed container orchestration
- Built-in auto-scaling (0 to N replicas)
- Integrated with Azure services
- Pay-per-use pricing model
- Easy CI/CD integration

### Option 2: Azure App Service
**Best for:** Simple web applications, quick deployments, and teams familiar with PaaS.

**Pros:**
- Easy deployment with Docker support
- Built-in CI/CD
- Integrated monitoring
- Managed SSL certificates
- Good for monolithic applications

### Option 3: Azure Kubernetes Service (AKS)
**Best for:** Complex microservices, advanced orchestration needs, multi-cloud strategies.

**Pros:**
- Full Kubernetes control
- Advanced networking and security
- Multi-region deployments
- Hybrid cloud support

---

## Prerequisites

### Required Tools
- **Azure CLI** (v2.50+): [Install Guide](https://docs.microsoft.com/cli/azure/install-azure-cli)
- **Docker** (v24+): [Install Guide](https://docs.docker.com/get-docker/)
- **Git**: For version control and CI/CD
- **Python 3.11+**: For local testing

### Azure Subscription Requirements
- Active Azure subscription with appropriate permissions
- Resource creation permissions (Contributor role or higher)
- Ability to create service principals for CI/CD

### Azure Services Needed
- **Azure OpenAI Service** (GPT-4 and text-embedding-ada-002)
- **Azure AI Search** (Standard tier or higher)
- **Azure Blob Storage** (General Purpose v2)
- **Azure Container Registry** (Basic tier or higher)
- **Azure Key Vault** (Standard tier)
- **Azure Monitor** / **Application Insights** (for observability)

---

## Azure Resource Provisioning

### Option A: Automated Setup (Recommended)

Use the provided setup script to create all required Azure resources:

```bash
# Make the script executable
chmod +x scripts/setup_azure.sh

# Run the setup script
./scripts/setup_azure.sh
```

The script will create:
- Resource Group (`third-eye-rg`)
- Azure OpenAI Service with deployments:
  - GPT-4 (chat completion)
  - text-embedding-ada-002 (embeddings)
- Azure AI Search instance
- Azure Blob Storage account
- Azure Container Registry
- Azure Key Vault
- Application Insights

### Option B: Manual Setup via Azure Portal

1. **Create Resource Group**
   ```bash
   az group create \
     --name third-eye-rg \
     --location eastus
   ```

2. **Create Azure OpenAI Service**
   ```bash
   az cognitiveservices account create \
     --name third-eye-openai \
     --resource-group third-eye-rg \
     --kind OpenAI \
     --sku S0 \
     --location eastus
   
   # Deploy GPT-4 model
   az cognitiveservices account deployment create \
     --name third-eye-openai \
     --resource-group third-eye-rg \
     --deployment-name gpt-4 \
     --model-name gpt-4 \
     --model-version "0613" \
     --model-format OpenAI \
     --sku-capacity 10 \
     --sku-name "Standard"
   
   # Deploy embeddings model
   az cognitiveservices account deployment create \
     --name third-eye-openai \
     --resource-group third-eye-rg \
     --deployment-name text-embedding-ada-002 \
     --model-name text-embedding-ada-002 \
     --model-version "2" \
     --model-format OpenAI \
     --sku-capacity 10 \
     --sku-name "Standard"
   ```

3. **Create Azure AI Search**
   ```bash
   az search service create \
     --name third-eye-search \
     --resource-group third-eye-rg \
     --sku standard \
     --location eastus
   ```

4. **Create Azure Blob Storage**
   ```bash
   az storage account create \
     --name thirdeyestorage \
     --resource-group third-eye-rg \
     --location eastus \
     --sku Standard_LRS
   
   # Create container
   az storage container create \
     --name third-eye-pdfs \
     --account-name thirdeyestorage
   ```

5. **Create Azure Container Registry**
   ```bash
   az acr create \
     --name thirdeyeacr \
     --resource-group third-eye-rg \
     --sku Basic \
     --location eastus \
     --admin-enabled true
   ```

6. **Create Azure Key Vault**
   ```bash
   az keyvault create \
     --name third-eye-kv \
     --resource-group third-eye-rg \
     --location eastus
   ```

7. **Create Application Insights**
   ```bash
   az monitor app-insights component create \
     --app third-eye-insights \
     --location eastus \
     --resource-group third-eye-rg \
     --application-type web
   ```

---

## Configuration

### 1. Store Secrets in Azure Key Vault

```bash
# Get Azure OpenAI credentials
OPENAI_KEY=$(az cognitiveservices account keys list \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --query key1 -o tsv)

OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --query properties.endpoint -o tsv)

# Get Azure Search credentials
SEARCH_KEY=$(az search admin-key show \
  --service-name third-eye-search \
  --resource-group third-eye-rg \
  --query primaryKey -o tsv)

SEARCH_ENDPOINT="https://third-eye-search.search.windows.net"

# Get Blob Storage connection string
BLOB_CONNECTION=$(az storage account show-connection-string \
  --name thirdeyestorage \
  --resource-group third-eye-rg \
  --query connectionString -o tsv)

# Store secrets in Key Vault
az keyvault secret set --vault-name third-eye-kv --name AZURE-OPENAI-KEY --value "$OPENAI_KEY"
az keyvault secret set --vault-name third-eye-kv --name AZURE-OPENAI-ENDPOINT --value "$OPENAI_ENDPOINT"
az keyvault secret set --vault-name third-eye-kv --name AZURE-SEARCH-KEY --value "$SEARCH_KEY"
az keyvault secret set --vault-name third-eye-kv --name AZURE-SEARCH-ENDPOINT --value "$SEARCH_ENDPOINT"
az keyvault secret set --vault-name third-eye-kv --name AZURE-BLOB-CONNECTION-STRING --value "$BLOB_CONNECTION"
```

### 2. Configure GitHub Secrets for CI/CD

Create the following secrets in your GitHub repository (Settings > Secrets and variables > Actions):

```bash
# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name thirdeyeacr --resource-group third-eye-rg --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name thirdeyeacr --resource-group third-eye-rg --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name thirdeyeacr --resource-group third-eye-rg --query passwords[0].value -o tsv)

# Create service principal for GitHub Actions
AZURE_CREDENTIALS=$(az ad sp create-for-rbac \
  --name "third-eye-github-actions" \
  --role contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/third-eye-rg \
  --sdk-auth)

echo "Add these secrets to GitHub:"
echo "ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER"
echo "ACR_USERNAME=$ACR_USERNAME"
echo "ACR_PASSWORD=$ACR_PASSWORD"
echo "AZURE_CREDENTIALS=$AZURE_CREDENTIALS"
echo "AZURE_RESOURCE_GROUP=third-eye-rg"
```

---

## Deployment Methods

## Option 1: Azure Container Apps (Recommended)

Azure Container Apps provides a fully managed serverless container platform with built-in auto-scaling and microservices support.

### Step 1: Create Container Apps Environment

```bash
az containerapp env create \
  --name third-eye-env \
  --resource-group third-eye-rg \
  --location eastus
```

### Step 2: Build and Push Docker Images

```bash
# Login to Azure Container Registry
az acr login --name thirdeyeacr

# Build and push API image
docker build -t thirdeyeacr.azurecr.io/third-eye-chatbot:latest -f docker/Dockerfile .
docker push thirdeyeacr.azurecr.io/third-eye-chatbot:latest

# Build and push worker image
docker build -t thirdeyeacr.azurecr.io/third-eye-worker:latest -f docker/Dockerfile.worker .
docker push thirdeyeacr.azurecr.io/third-eye-worker:latest
```

### Step 3: Deploy Redis Container

```bash
az containerapp create \
  --name third-eye-redis \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image redis:7-alpine \
  --target-port 6379 \
  --ingress internal \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 1 \
  --max-replicas 1
```

### Step 4: Deploy API Container

```bash
# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name thirdeyeacr --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name thirdeyeacr --query passwords[0].value -o tsv)

# Create managed identity for Key Vault access
IDENTITY_ID=$(az identity create \
  --name third-eye-identity \
  --resource-group third-eye-rg \
  --query id -o tsv)

IDENTITY_CLIENT_ID=$(az identity show \
  --ids $IDENTITY_ID \
  --query clientId -o tsv)

# Grant Key Vault access to managed identity
az keyvault set-policy \
  --name third-eye-kv \
  --object-id $(az identity show --ids $IDENTITY_ID --query principalId -o tsv) \
  --secret-permissions get list

# Deploy API container
az containerapp create \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image thirdeyeacr.azurecr.io/third-eye-chatbot:latest \
  --target-port 8000 \
  --ingress external \
  --registry-server thirdeyeacr.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 5 \
  --user-assigned $IDENTITY_ID \
  --secrets \
    azure-openai-key=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-OPENAI-KEY,identityref:$IDENTITY_ID \
    azure-openai-endpoint=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-OPENAI-ENDPOINT,identityref:$IDENTITY_ID \
    azure-search-key=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-SEARCH-KEY,identityref:$IDENTITY_ID \
    azure-search-endpoint=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-SEARCH-ENDPOINT,identityref:$IDENTITY_ID \
    azure-blob-connection=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-BLOB-CONNECTION-STRING,identityref:$IDENTITY_ID \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_API_VERSION=2024-02-15-preview \
    AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4 \
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002 \
    AZURE_SEARCH_ENDPOINT=secretref:azure-search-endpoint \
    AZURE_SEARCH_KEY=secretref:azure-search-key \
    AZURE_SEARCH_INDEX=third-eye-docs \
    AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection \
    AZURE_BLOB_CONTAINER=third-eye-pdfs \
    REDIS_URL=redis://third-eye-redis:6379/0 \
    APP_ENV=production \
    CHUNK_SIZE=1000 \
    CHUNK_OVERLAP=150 \
    TOP_K_RESULTS=6
```

### Step 5: Deploy Worker Container

```bash
az containerapp create \
  --name third-eye-worker \
  --resource-group third-eye-rg \
  --environment third-eye-env \
  --image thirdeyeacr.azurecr.io/third-eye-worker:latest \
  --registry-server thirdeyeacr.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --user-assigned $IDENTITY_ID \
  --secrets \
    azure-openai-key=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-OPENAI-KEY,identityref:$IDENTITY_ID \
    azure-openai-endpoint=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-OPENAI-ENDPOINT,identityref:$IDENTITY_ID \
    azure-search-key=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-SEARCH-KEY,identityref:$IDENTITY_ID \
    azure-search-endpoint=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-SEARCH-ENDPOINT,identityref:$IDENTITY_ID \
    azure-blob-connection=keyvaultref:https://third-eye-kv.vault.azure.net/secrets/AZURE-BLOB-CONNECTION-STRING,identityref:$IDENTITY_ID \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_API_VERSION=2024-02-15-preview \
    AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4 \
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002 \
    AZURE_SEARCH_ENDPOINT=secretref:azure-search-endpoint \
    AZURE_SEARCH_KEY=secretref:azure-search-key \
    AZURE_SEARCH_INDEX=third-eye-docs \
    AZURE_BLOB_CONNECTION_STRING=secretref:azure-blob-connection \
    AZURE_BLOB_CONTAINER=third-eye-pdfs \
    REDIS_URL=redis://third-eye-redis:6379/0
```

### Step 6: Configure Auto-Scaling

```bash
# Configure HTTP-based auto-scaling for API
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --min-replicas 2 \
  --max-replicas 10 \
  --scale-rule-name http-rule \
  --scale-rule-type http \
  --scale-rule-http-concurrency 50

# Configure CPU-based auto-scaling for worker
az containerapp update \
  --name third-eye-worker \
  --resource-group third-eye-rg \
  --min-replicas 1 \
  --max-replicas 5 \
  --scale-rule-name cpu-rule \
  --scale-rule-type cpu \
  --scale-rule-metadata type=Utilization value=70
```

### Step 7: Get Application URL

```bash
API_URL=$(az containerapp show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

echo "Application URL: https://$API_URL"
```

---

## Option 2: Azure App Service

Azure App Service provides a simple PaaS solution for web applications with built-in CI/CD.

### Step 1: Create App Service Plan

```bash
az appservice plan create \
  --name third-eye-plan \
  --resource-group third-eye-rg \
  --is-linux \
  --sku P1V2
```

### Step 2: Create Web App

```bash
az webapp create \
  --name third-eye-chatbot \
  --resource-group third-eye-rg \
  --plan third-eye-plan \
  --deployment-container-image-name thirdeyeacr.azurecr.io/third-eye-chatbot:latest
```

### Step 3: Configure Container Registry

```bash
az webapp config container set \
  --name third-eye-chatbot \
  --resource-group third-eye-rg \
  --docker-custom-image-name thirdeyeacr.azurecr.io/third-eye-chatbot:latest \
  --docker-registry-server-url https://thirdeyeacr.azurecr.io \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD
```

### Step 4: Configure App Settings

```bash
# Get secrets from Key Vault
OPENAI_KEY=$(az keyvault secret show --vault-name third-eye-kv --name AZURE-OPENAI-KEY --query value -o tsv)
OPENAI_ENDPOINT=$(az keyvault secret show --vault-name third-eye-kv --name AZURE-OPENAI-ENDPOINT --query value -o tsv)
SEARCH_KEY=$(az keyvault secret show --vault-name third-eye-kv --name AZURE-SEARCH-KEY --query value -o tsv)
SEARCH_ENDPOINT=$(az keyvault secret show --vault-name third-eye-kv --name AZURE-SEARCH-ENDPOINT --query value -o tsv)
BLOB_CONNECTION=$(az keyvault secret show --vault-name third-eye-kv --name AZURE-BLOB-CONNECTION-STRING --query value -o tsv)

# Configure app settings
az webapp config appsettings set \
  --name third-eye-chatbot \
  --resource-group third-eye-rg \
  --settings \
    AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT" \
    AZURE_OPENAI_API_KEY="$OPENAI_KEY" \
    AZURE_OPENAI_API_VERSION=2024-02-15-preview \
    AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4 \
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002 \
    AZURE_SEARCH_ENDPOINT="$SEARCH_ENDPOINT" \
    AZURE_SEARCH_KEY="$SEARCH_KEY" \
    AZURE_SEARCH_INDEX=third-eye-docs \
    AZURE_BLOB_CONNECTION_STRING="$BLOB_CONNECTION" \
    AZURE_BLOB_CONTAINER=third-eye-pdfs \
    APP_ENV=production
```

### Step 5: Enable Continuous Deployment

```bash
az webapp deployment container config \
  --name third-eye-chatbot \
  --resource-group third-eye-rg \
  --enable-cd true
```

---

## Option 3: Azure Kubernetes Service (AKS)

For advanced orchestration and multi-region deployments.

### Step 1: Create AKS Cluster

```bash
az aks create \
  --name third-eye-aks \
  --resource-group third-eye-rg \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --enable-managed-identity \
  --attach-acr thirdeyeacr \
  --generate-ssh-keys
```

### Step 2: Get Credentials

```bash
az aks get-credentials \
  --name third-eye-aks \
  --resource-group third-eye-rg
```

### Step 3: Create Kubernetes Manifests

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: third-eye-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: third-eye-api
  template:
    metadata:
      labels:
        app: third-eye-api
    spec:
      containers:
      - name: api
        image: thirdeyeacr.azurecr.io/third-eye-chatbot:latest
        ports:
        - containerPort: 8000
        env:
        - name: AZURE_OPENAI_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: azure-secrets
              key: openai-endpoint
        # Add other environment variables
---
apiVersion: v1
kind: Service
metadata:
  name: third-eye-api-service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: third-eye-api
```

### Step 4: Deploy to AKS

```bash
kubectl apply -f k8s/deployment.yaml
```

---

## Monitoring & Observability

### Application Insights Integration

```bash
# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app third-eye-insights \
  --resource-group third-eye-rg \
  --query instrumentationKey -o tsv)

# Update container app with Application Insights
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
```

### View Logs

```bash
# Container Apps logs
az containerapp logs show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --follow

# App Service logs
az webapp log tail \
  --name third-eye-chatbot \
  --resource-group third-eye-rg
```

### Metrics and Alerts

```bash
# Create CPU alert
az monitor metrics alert create \
  --name high-cpu-alert \
  --resource-group third-eye-rg \
  --scopes $(az containerapp show --name third-eye-api --resource-group third-eye-rg --query id -o tsv) \
  --condition "avg Percentage CPU > 80" \
  --description "Alert when CPU exceeds 80%"
```

---

## Security Best Practices

### 1. Use Managed Identities

Always use Azure Managed Identities instead of connection strings where possible:

```bash
# Assign managed identity to container app
az containerapp identity assign \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --user-assigned $IDENTITY_ID
```

### 2. Network Security

```bash
# Restrict access to specific IP ranges
az containerapp ingress access-restriction set \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --rule-name allow-office \
  --ip-address 203.0.113.0/24 \
  --action Allow
```

### 3. Enable Azure DDoS Protection

```bash
az network ddos-protection create \
  --name third-eye-ddos \
  --resource-group third-eye-rg \
  --location eastus
```

### 4. Regular Security Updates

- Enable automatic OS patching for AKS nodes
- Regularly update base Docker images
- Scan images for vulnerabilities using Azure Defender

### 5. Implement Rate Limiting

Add rate limiting in your FastAPI application or use Azure API Management.

---

## Seed Knowledge Base

After deployment, seed the knowledge base with initial documents:

```bash
# Option 1: Run locally with production credentials
python scripts/seed_knowledge.py

# Option 2: Execute in container
az containerapp exec \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --command "python scripts/seed_knowledge.py"
```

---

## Custom Domain Configuration

### Add Custom Domain

```bash
# For Container Apps
az containerapp hostname add \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --hostname chat.yourdomain.com

# For App Service
az webapp config hostname add \
  --webapp-name third-eye-chatbot \
  --resource-group third-eye-rg \
  --hostname chat.yourdomain.com
```

### Configure SSL Certificate

```bash
# Create managed certificate (free)
az containerapp ssl upload \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --hostname chat.yourdomain.com \
  --certificate-type Managed
```

---

## Backup and Disaster Recovery

### 1. Backup Azure AI Search Index

```bash
# Export index definition
az search index show \
  --service-name third-eye-search \
  --name third-eye-docs \
  --resource-group third-eye-rg > backups/index-$(date +%Y%m%d).json
```

### 2. Enable Blob Storage Versioning

```bash
az storage account blob-service-properties update \
  --account-name thirdeyestorage \
  --enable-delete-retention true \
  --delete-retention-days 30 \
  --enable-versioning true
```

### 3. Geo-Redundant Storage

```bash
az storage account update \
  --name thirdeyestorage \
  --resource-group third-eye-rg \
  --sku Standard_GRS
```

---

## Cost Optimization

### 1. Use Azure Reserved Instances

Purchase reserved instances for predictable workloads (up to 72% savings).

### 2. Auto-Scaling Configuration

```bash
# Scale down during off-hours
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --min-replicas 0 \
  --max-replicas 10
```

### 3. Monitor Costs

```bash
# Set up budget alerts
az consumption budget create \
  --budget-name third-eye-budget \
  --amount 500 \
  --time-grain Monthly \
  --start-date $(date +%Y-%m-01) \
  --end-date $(date -d "+1 year" +%Y-%m-01)
```

### 4. Use Spot Instances for Workers

For non-critical worker containers, consider using Azure Spot instances.

---

## Troubleshooting

### Check Container Status

```bash
# Container Apps
az containerapp show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --query properties.runningStatus

# App Service
az webapp show \
  --name third-eye-chatbot \
  --resource-group third-eye-rg \
  --query state
```

### View Container Logs

```bash
# Real-time logs
az containerapp logs show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --follow

# Historical logs
az monitor log-analytics query \
  --workspace $(az containerapp env show --name third-eye-env --resource-group third-eye-rg --query properties.appLogsConfiguration.logAnalyticsConfiguration.customerId -o tsv) \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'third-eye-api' | order by TimeGenerated desc | take 100"
```

### Restart Container

```bash
# Container Apps - restart revision
az containerapp revision restart \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --revision $(az containerapp revision list --name third-eye-api --resource-group third-eye-rg --query "[0].name" -o tsv)

# App Service - restart
az webapp restart \
  --name third-eye-chatbot \
  --resource-group third-eye-rg
```

### Common Issues

#### Issue: Container fails to start
**Solution:** Check environment variables and secrets are correctly configured.

```bash
az containerapp show \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --query properties.template.containers[0].env
```

#### Issue: High latency
**Solution:** Check if auto-scaling is configured and increase min replicas.

```bash
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --min-replicas 3
```

#### Issue: Out of memory errors
**Solution:** Increase memory allocation.

```bash
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --memory 4.0Gi
```

---

## CI/CD with GitHub Actions

Create `.github/workflows/azure-deploy.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  AZURE_RESOURCE_GROUP: third-eye-rg
  CONTAINER_APP_NAME: third-eye-api
  ACR_NAME: thirdeyeacr

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Build and push to ACR
        run: |
          az acr login --name ${{ env.ACR_NAME }}
          docker build -t ${{ env.ACR_NAME }}.azurecr.io/third-eye-chatbot:${{ github.sha }} -f docker/Dockerfile .
          docker push ${{ env.ACR_NAME }}.azurecr.io/third-eye-chatbot:${{ github.sha }}
      
      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name ${{ env.CONTAINER_APP_NAME }} \
            --resource-group ${{ env.AZURE_RESOURCE_GROUP }} \
            --image ${{ env.ACR_NAME }}.azurecr.io/third-eye-chatbot:${{ github.sha }}
```

---

## Maintenance

### Update Application

```bash
# Build new image
docker build -t thirdeyeacr.azurecr.io/third-eye-chatbot:v2.0 -f docker/Dockerfile .
docker push thirdeyeacr.azurecr.io/third-eye-chatbot:v2.0

# Update container app
az containerapp update \
  --name third-eye-api \
  --resource-group third-eye-rg \
  --image thirdeyeacr.azurecr.io/third-eye-chatbot:v2.0
```

### Database Maintenance

- Regularly review and optimize Azure AI Search index
- Monitor index size and query performance
- Clean up old document versions in Blob Storage

---

## Additional Resources

- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [Azure Kubernetes Service Documentation](https://docs.microsoft.com/azure/aks/)
- [Azure OpenAI Documentation](https://docs.microsoft.com/azure/cognitive-services/openai/)
- [Azure AI Search Documentation](https://docs.microsoft.com/azure/search/)
- [Azure Key Vault Documentation](https://docs.microsoft.com/azure/key-vault/)

---

## Support

For issues and questions:
- Open an issue on GitHub
- Check Azure service health status
- Review Application Insights for errors
- Contact Azure support for infrastructure issues

---

**Last Updated:** 2025
**Version:** 2.0