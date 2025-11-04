#!/bin/bash
# Setup Azure resources for Third Eye Chatbot

set -e

# Configuration
RESOURCE_GROUP="third-eye-rg"
LOCATION="eastus"
OPENAI_NAME="third-eye-openai"
SEARCH_NAME="third-eye-search"
STORAGE_NAME="thirdeyestorage$(date +%s)"
KEYVAULT_NAME="third-eye-kv"
ACR_NAME="thirdeyeacr"

echo "🚀 Setting up Azure resources for Third Eye Chatbot..."

# Create resource group
echo "📦 Creating resource group..."
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Create Azure OpenAI
echo "🤖 Creating Azure OpenAI service..."
az cognitiveservices account create \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --kind OpenAI \
  --sku S0

# Deploy models
echo "📊 Deploying GPT-4 model..."
az cognitiveservices account deployment create \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --deployment-name gpt-4 \
  --model-name gpt-4 \
  --model-version "0613" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"

echo "📊 Deploying embeddings model..."
az cognitiveservices account deployment create \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --deployment-name text-embedding-ada-002 \
  --model-name text-embedding-ada-002 \
  --model-version "2" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"

# Create Azure AI Search
echo "🔍 Creating Azure AI Search service..."
az search service create \
  --name $SEARCH_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard

# Create Storage Account
echo "💾 Creating Storage Account..."
az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# Create blob container
echo "📦 Creating blob container..."
az storage container create \
  --name third-eye-pdfs \
  --account-name $STORAGE_NAME

# Create Key Vault
echo "🔐 Creating Key Vault..."
az keyvault create \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Create Azure Container Registry
echo "🐳 Creating Azure Container Registry..."
az acr create \
  --name $ACR_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard \
  --admin-enabled true

# Get credentials and store in Key Vault
echo "🔑 Storing credentials in Key Vault..."

OPENAI_KEY=$(az cognitiveservices account keys list \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "key1" -o tsv)

OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "properties.endpoint" -o tsv)

SEARCH_KEY=$(az search admin-key show \
  --service-name $SEARCH_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "primaryKey" -o tsv)

SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"

STORAGE_CONNECTION=$(az storage account show-connection-string \
  --name $STORAGE_NAME \
  --resource-group $RESOURCE_GROUP \
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
echo "  Resource Group: $RESOURCE_GROUP"
echo "  OpenAI Service: $OPENAI_NAME"
echo "  Search Service: $SEARCH_NAME"
echo "  Storage Account: $STORAGE_NAME"
echo "  Key Vault: $KEYVAULT_NAME"
echo "  Container Registry: $ACR_NAME"
echo ""
echo "🔐 Credentials stored in Key Vault: $KEYVAULT_NAME"
echo ""
echo "📋 Next steps:"
echo "  1. Update .env file with these values"
echo "  2. Configure GitHub secrets for CI/CD"
echo "  3. Deploy the application"