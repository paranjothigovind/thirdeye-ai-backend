# Contributing to Third Eye Meditation AI Chatbot

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Respect spiritual and cultural diversity
- Prioritize user safety and well-being

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/thirdeye-ai-backend.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Set up development environment (see README.md)

## Development Workflow

### 1. Code Style

We follow PEP 8 style guidelines with some modifications:

```bash
# Format code
make format

# Check linting
make lint
```

Key conventions:
- Use type hints for all function parameters and return values
- Maximum line length: 127 characters
- Use docstrings for all public functions and classes
- Prefer async/await for I/O operations

### 2. Testing

All new features must include tests:

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

Test guidelines:
- Write unit tests for individual functions
- Write integration tests for API endpoints
- Mock external services (Azure OpenAI, Azure Search)
- Aim for >80% code coverage

### 3. Documentation

- Update README.md for user-facing changes
- Update docstrings for code changes
- Add examples for new features
- Update API documentation if endpoints change

### 4. Commit Messages

Follow conventional commits:

```
feat: add new meditation technique endpoint
fix: resolve citation extraction bug
docs: update deployment guide
test: add tests for guardrails
refactor: simplify retrieval logic
```

## Areas for Contribution

### High Priority

1. **Additional Meditation Techniques**
   - Add more traditional practices
   - Include safety guidelines
   - Provide step-by-step instructions

2. **Improved Guardrails**
   - Enhance safety checks
   - Better emergency detection
   - More nuanced disclaimer logic

3. **Evaluation Framework**
   - Groundedness metrics
   - Citation accuracy
   - Response quality assessment

4. **Multi-language Support**
   - Internationalization
   - Translation of core content
   - Language-specific prompts

### Medium Priority

1. **Advanced RAG Features**
   - Query expansion
   - Re-ranking algorithms
   - Hybrid search optimization

2. **User Feedback Loop**
   - Thumbs up/down on responses
   - Report inappropriate content
   - Suggest improvements

3. **Performance Optimization**
   - Caching strategies
   - Batch processing
   - Query optimization

### Nice to Have

1. **Voice Interface**
   - Speech-to-text integration
   - Text-to-speech for guided meditations

2. **Progress Tracking**
   - User meditation history
   - Practice recommendations
   - Personalized guidance

3. **Community Features**
   - Share practices
   - Discussion forums
   - Teacher verification

## Pull Request Process

1. **Before Submitting**
   - Ensure all tests pass
   - Update documentation
   - Add tests for new features
   - Run linting and formatting

2. **PR Description**
   - Clearly describe the changes
   - Reference related issues
   - Include screenshots for UI changes
   - List any breaking changes

3. **Review Process**
   - Address reviewer feedback
   - Keep PRs focused and small
   - Be responsive to comments
   - Update PR based on feedback

4. **Merging**
   - Squash commits if needed
   - Ensure CI/CD passes
   - Get approval from maintainers

## Adding New Content

### Adding Meditation Practices

1. Create content following this structure:
```python
{
    "content": "Detailed practice instructions...",
    "title": "Practice Name",
    "source": "pdf",
    "page": 1,
    "section": "practices"
}
```

2. Include:
   - Clear step-by-step instructions
   - Duration guidelines
   - Benefits
   - Safety precautions
   - Contraindications

3. Submit via PR with:
   - Source citations
   - Expert review (if possible)
   - Safety verification

### Adding Safety Information

Safety content is critical. Please:
- Cite reputable sources
- Include medical disclaimers
- List contraindications
- Provide emergency guidance
- Get expert review before merging

## Prompt Engineering

When modifying prompts:

1. **Test Thoroughly**
   - Test with various queries
   - Check citation accuracy
   - Verify safety responses
   - Test edge cases

2. **Version Control**
   - Keep old prompts commented
   - Document changes
   - Include reasoning

3. **Evaluation**
   - Use LangSmith for tracing
   - Compare with baseline
   - Get user feedback

## Security

- Never commit secrets or API keys
- Use environment variables
- Follow Azure security best practices
- Report security issues privately

## Questions?

- Open an issue for bugs
- Start a discussion for features
- Contact maintainers for sensitive topics

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for helping make meditation guidance more accessible and safe! 🙏