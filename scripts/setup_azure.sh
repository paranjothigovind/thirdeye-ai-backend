#!/bin/bash
# Setup Azure resources for Third Eye Chatbot

set -e

# Configuration
RESOURCE_GROUP="third-eye-rg"
LOCATION="eastus2"
OPENAI_NAME="third-eye-openai"
SEARCH_NAME="third-eye-search"
STORAGE_NAME="thirdeyestorage$(date +%s)"
KEYVAULT_NAME="third-eye-kv"
ACR_NAME="thirdeyeacr"

echo "🚀 Setting up Azure resources for Third Eye Chatbot..."

# Create resource group
echo "📦 Creating resource group..."
az group create \
  --name third-eye-rg \
  --location $LOCATION

# Create Azure OpenAI
echo "🤖 Creating Azure OpenAI service..."
az cognitiveservices account create \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --location $LOCATION \
  --kind OpenAI \
  --sku S0

# Deploy models
echo "📊 Deploying GPT-4o model..."
az cognitiveservices account deployment create \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-11-20" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10

echo "📊 Deploying embeddings model..."
az cognitiveservices account deployment create \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --deployment-name text-embedding-3-large \
  --model-name text-embedding-3-large \
  --model-version "1" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10

# Create Azure AI Search
echo "🔍 Creating Azure AI Search service..."
az search service create \
  --name third-eye-search \
  --resource-group third-eye-rg \
  --location eastus2 \
  --sku Standard

# Create Storage Account
echo "💾 Creating Storage Account..."
az storage account create \
  --name "thirdeyestoragedev" \
  --resource-group third-eye-rg \
  --location eastus2 \
  --sku Standard_LRS

# Create blob container
echo "📦 Creating blob container..."
az storage container create \
  --name third-eye-pdfs \
  --account-name hirdeyestoragedev

# Create Key Vault
echo "🔐 Creating Key Vault..."
az keyvault create \
  --name third-eye-kv \
  --resource-group third-eye-rg \
  --location eastus2

# Create Azure Container Registry
echo "🐳 Creating Azure Container Registry..."
az acr create \
  --name thirdeyeacr \
  --resource-group third-eye-rg \
  --location eastus2 \
  --sku Standard \
  --admin-enabled true

# Get credentials and store in Key Vault
echo "🔑 Storing credentials in Key Vault..."

OPENAI_KEY=$(az cognitiveservices account keys list \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --query "key1" -o tsv)

OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --name third-eye-openai \
  --resource-group third-eye-rg \
  --query "properties.endpoint" -o tsv)

SEARCH_KEY=$(az search admin-key show \
  --service-name third-eye-search \
  --resource-group third-eye-rg \
  --query "primaryKey" -o tsv)

SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"

STORAGE_CONNECTION=$(az storage account show-connection-string \
  --name thirdeyestoragedev \
  --resource-group third-eye-rg \
  --query "connectionString" -o tsv)

# Store in Key Vault
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AZURE-OPENAI-KEY" --value "$OPENAI_KEY"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AZURE-OPENAI-ENDPOINT" --value "$OPENAI_ENDPOINT"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AZURE-SEARCH-KEY" --value "$SEARCH_KEY"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AZURE-SEARCH-ENDPOINT" --value "$SEARCH_ENDPOINT"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AZURE-BLOB-CONNECTION-STRING" --value "$STORAGE_CONNECTION"

echo "✅ Azure resources created successfully!"
echo ""
echo "📝 Resource Details:"
echo "  Resource Group: third-eye-rg"
echo "  OpenAI Service: third-eye-openai"
echo "  Search Service: third-eye-search"
echo "  Storage Account: thirdeyestoragedev"
echo "  Key Vault: $KEYVAULT_NAME"
echo "  Container Registry: $ACR_NAME"
echo ""
echo "🔐 Credentials stored in Key Vault: $KEYVAULT_NAME"
echo ""
echo "📋 Next steps:"
echo "  1. Update .env file with these values"
echo "  2. Configure GitHub secrets for CI/CD"
echo "  3. Deploy the application"