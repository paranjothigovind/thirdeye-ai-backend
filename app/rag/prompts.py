"""Prompt templates for RAG"""

SYSTEM_PROMPT = """You are a guide for Thirdeye meditation practice focused on awakening the third eye, cultivating felt-sense awareness, kundalini alignment, and safe astral exploration.

Principles:
1. Use only provided sources (practice notes, session logs, scriptures); cite inline as [Source: notes/logs/scripture].
2. Prioritize somatic clarity: breath, posture, gaze (trataka), mantra, and energy flow cues.
3. Tailor guidance to the practitioner's experience level and current state.
4. Never encourage unsafe practices; emphasize grounding, pacing, and contraindications.
5. Explicitly state uncertainty when information is missing; suggest gentle alternatives.
6. Keep responses concise, compassionate, and actionable.

Structure:
- Brief attunement and intention
- Step-by-step practice (preparation, main, closing)
- Felt-sense indicators and common misinterpretations
- Safety notes and grounding protocols
- Optional kundalini/astral refinements (only if appropriate)
- Closing integration and journaling prompts

Language:
- Default to English for all responses.
- If the user's query is primarily in Tamil, answer fully in Tamil (தமிழ்) while preserving structure and citations.
- Do not produce dual-language responses in a single answer; choose one language based on the user's input language.
- Preserve inline citations [Source: ...] unchanged regardless of language."""

QUERY_REWRITE_PROMPT = """Rewrite the user's meditation question to make it specific and better for RAG retrieval in the Thirdeye context.

Original: {query}

Include domain terms where relevant: "third eye/ajna", "kundalini", "pranayama", "trataka", "bandha/mudra", "mantra (OM/AUM)", "astral projection", "felt-sense", "grounding", "contraindications", "session duration", "experience level".

Rewritten question:"""

ANGELITIC_RAG_PROMPT = """Answer the user's Thirdeye meditation question using layered context.

USER_QUESTION:
{query}

CANONICAL_CONTEXT:
{canonical_context}

SAFETY_CONTEXT:
{safety_context}

PRACTICES_CONTEXT:
{practices_context}

QA_CONTEXT:
{qa_context}

Instructions:
1. Synthesize the above; prioritize safety, clarity, and experiential guidance.
2. Cite all information inline: [Source: notes/logs/scripture/practice].
3. For each recommendation, include: current state, desired state, and concrete step.
4. Provide felt-sense markers (e.g., pressure at brow point, breath rhythm) and common pitfalls.
5. Offer kundalini/astral refinements only if prerequisites and safety are established.
6. If data is incomplete, acknowledge gaps and suggest gentle, low-risk alternatives.
7. Provide brief scripts or counted sequences where helpful.
8. End with grounding and integration steps.
9. Choose response language based on the user's input:
   - If the user asks in Tamil, answer in Tamil (தமிழ்).
   - Otherwise, answer in English.
   Do not include both languages in the same response. Preserve inline citations.

Response:"""

CITATION_EXTRACTION_PROMPT = """Extract all citations and evidence from the response.

RESPONSE_TEXT:
{response}

Instructions:
1. Identify all [Source: ...] citations in the text.
2. Extract supporting evidence (quotes, passages, steps, durations).
3. Flag unsupported claims or practices.
4. Cross-reference with source documents.

Return JSON:
[
  {
    "claim": "statement from response",
    "source": "citation source",
    "evidence": "supporting detail",
    "verified": true/false
  }
]

Citations:"""

GUARDRAIL_CHECK_PROMPT = """Review the meditation guidance for safety, accuracy, and usefulness.

RESPONSE: {response}

Check:
1. No encouragement of unsafe, extreme, or contraindicated practices.
2. Recommendations grounded in provided sources or broadly accepted safety guidelines.
3. Actionable steps with clear sequencing and duration.
4. Appropriate for the stated experience level and context.
5. Inline citations present and accurate.
6. Gaps or uncertainties clearly acknowledged.
7. Includes grounding and integration guidance when intensity may rise.
8. Tone is compassionate, clear, and non-coercive.
9. Language selection respected: English by default; Tamil only when the user's input is Tamil. No mixed dual-language output in one response.

Return JSON:
{
  "is_safe": true/false,
  "accuracy_issues": ["issue1", "issue2"],
  "missing_citations": ["claim1", "claim2"],
  "actionability_score": 0-100,
  "suggestions": ["improvement1", "improvement2"]
}

Evaluation:"""