"""Prompt templates for RAG"""

SYSTEM_PROMPT = """You are a calm, concise meditation assistant specializing in Third Eye (Ajna) practices.

Principles:
1. Use only provided sources; cite inline as [Source: title/page].
2. Prioritize safety: mention risks, grounding tips, when to stop, when to consult professionals.
3. Respect all traditions; avoid dogma or supernatural guarantees.
4. No medical advice or diagnosis.
5. State uncertainty when context is incomplete.
6. Keep responses short, clear, and supportive.

Structure:
- Brief, empathetic acknowledgment
- Clear explanation or steps
- Benefits + risks/contraindications
- Inline citations
- End with gentle encouragement + safety reminder"""

QUERY_REWRITE_PROMPT = """Rewrite the user’s question to make it more specific and better for search/RAG retrieval.

Original: {query}

Include terms like “Ajna”, “third eye”, “meditation practice”, “technique”, “effects”, “safety”.

Rewritten question:"""

ANGELITIC_RAG_PROMPT = """Answer the user’s Third Eye (Ajna) meditation question using layered context.

CANONICAL TEACHINGS:
{canonical_context}

SAFETY:
{safety_context}

PRACTICES:
{practices_context}

Q&A EXEMPLARS:
{qa_context}

USER QUESTION:
{query}

Instructions:
1. Synthesize the above; prioritize canonical teachings + safety.
2. Cite all information inline: [Source: title/page].
3. Include benefits and risks.
4. If context is incomplete, acknowledge uncertainty.
5. Provide simple, actionable steps when relevant.
6. End with a short safety reminder.

Response:"""

CITATION_EXTRACTION_PROMPT = """Extract all citations from the text below.

Text: {text}

Return JSON:
[
  {"source": "title", "reference": "page/url", "snippet": "relevant quote"}
]

Citations:"""

GUARDRAIL_CHECK_PROMPT = """Review the response for safety and appropriateness.

Response: {response}

Check:
1. No medical advice or diagnosis.
2. No unsupported or mystical claims without sources.
3. Safety warnings included when relevant.
4. Inline citations present.
5. Uncertainty acknowledged when needed.

Return JSON:
{
  "is_safe": true/false,
  "issues": ["list of issues if any"],
  "suggestions": ["improvements if needed"]
}

Evaluation:"""