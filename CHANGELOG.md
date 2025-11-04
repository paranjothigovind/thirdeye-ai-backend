# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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