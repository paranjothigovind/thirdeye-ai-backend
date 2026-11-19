# Phase 1.2 — Azure Live Verification Report

Date: 2026-11-14. Provider: `LLM_PROVIDER=azure_openai`. Claude was not used.
Legend: **LIVE** = real Azure calls made in this phase. **MOCKED** = automated tests with fakes.

## 1. Tests

| Suite | Result | Type |
|---|---|---|
| Full pytest suite (baseline, before changes) | 163 passed, 0 failed | MOCKED |
| Full pytest suite (after fixes) | **165 passed, 0 failed** (resource/runtime warnings as errors) | MOCKED |
| Node SSE parser tests | 7/7 (also run inside pytest) | MOCKED |

Live checks were run with throwaway scripts outside the repo; they are not part of the suite.

## 2. Azure OpenAI — LIVE

- Config: provider `azure_openai`, chat deployment `paranj-gpt-5.2`, API version `2024-12-01-preview`, endpoint and keys present (not printed).
- `generate` and `stream`: **PASS**. Azure reports real token usage for both (not estimated); served model `gpt-chat-latest`, stop reason `stop`.
- Via the real FastAPI app, English and Tamil, streaming and non-streaming: all returned 200 with a grounded answer.

## 3. Azure AI Search — LIVE

- Hybrid retrieval returned 4 documents for an English question (`Nettrikkan English.docx (1).pdf`, pages 1/8/3/5) and 4 for a Tamil question (`Third_Eye_Meditation_RAG_TAMIL.pdf`, pages 5/3/1/2). Index `thirdeye-knowledge-index-v2`, 3072 dimensions, unchanged.
- English question → English answer; Tamil question → Tamil answer.

## 4. Sources — LIVE

- In every live chat request (EN/TA × stream/non-stream) the returned Sources were a subset of the documents actually retrieved for that request, built from `title` and `page N`. No `[Source: …]` tags appeared in any answer.

## 5. Tokens and budget — LIVE

- Token usage is captured per call (input, output, total, served model, stop reason, latency).
- Daily budget: with `LLM_DAILY_TOKEN_BUDGET=50` set in-process, the first request succeeded and its recorded tokens equalled the counter exactly; the next request on `/api/chat` and on `/api/chat/graph` returned **429** with a `Retry-After` until UTC midnight.
- Per-IP limit: first request 200, second **429** with no model call made.

## 6. Safety and streaming — LIVE

- SSE: `text/event-stream`, content events, then `citations`, then exactly one `[DONE]`. A `: keep-alive` comment was observed on a slow request.
- Oversized request (too long, too many messages): **422**, no model call.
- English emergency (`stream:true`): SSE emergency message, no model call, no digits or phone numbers.
- **Tamil emergency: not detected by keywords** (no reviewed Tamil keywords are configured). A live Tamil suicidal-ideation message went to the model; the system-prompt backstop made it reply in Tamil, advise contacting a trusted person or local emergency services, decline to give meditation guidance, and include no phone numbers. This relies on model behaviour and is not a guarantee. The reply still carried Sources from the knowledge base.

## 7. Defects found and fixed

1. **Azure `max_tokens` rejected (HTTP 400)** — `gpt-5.2` requires `max_completion_tokens`. Production RAG never passed it, but the provider's `max_tokens` argument always failed. Fixed in `AzureOpenAIClient._model_with`; verified live for `generate` and `stream`.
2. **Azure cached tokens double counted** — Azure reports cached tokens as a subset of input tokens; they were being added again to the total, inflating usage and consuming the daily budget early (observed: 6694 reported vs 3494 real). Fixed; cached count now logged separately as `cached_input_tokens`. Verified live (3616 = 3612 + 4).

Regression tests added for both. Anthropic accounting is unchanged (it reports cache tokens separately).

## 8. Files changed (Phase 1.2)

- `app/models/azure_openai.py`
- `tests/test_phase11.py` (two tests appended)
- `phase12_live_verification_report.md` (this file)

Not touched: `.env`, embeddings, vector dimensions, index schema, retriever, ingestion, auth, LMS, database, dependencies.

## 9. Remaining blockers / limitations

- **Tamil emergency detection** needs native-reviewed keywords and approved contacts in `EMERGENCY_POLICY_FILE` from the Netrikkan team. Not added here by design.
- `LLM_DAILY_TOKEN_BUDGET` is 0 (unlimited) and `TRUSTED_PROXY_HOPS` is 0 in the current environment. Set both for production; check the real proxy hop count first, or all visitors behind a proxy share one IP limit.
- Each default-path chat sends about 3.3k–4k input tokens because the existing retriever returns the same documents for all four layers (`retrieve_by_layer` ignores the layer). Retrieval is out of scope, but this raises Azure cost.
- Live checks used the Python app in-process. Not tested: the deployed host and proxy, the production frontend, the bundled UI in a browser, real Redis (`USAGE_STORE=redis`), and multiple instances.
- Tamil retrieval quality was checked only by document titles/pages and answer language, not by a Tamil reader.
- A Tamil crisis reply still attaches knowledge-base Sources.
- The `Event loop is closed` embedding error appears only when requests are run in separate event loops (a test-harness artifact); not seen under a single loop. Not verified under real uvicorn.

## 10. Production readiness: **NOT READY**

Core Azure generation, retrieval, Sources, tokens, limits and SSE work live. Blocking before launch: (1) set a daily token budget and the correct proxy hop count; (2) Netrikkan-approved emergency contacts and reviewed Tamil emergency keywords; (3) a smoke test on the deployed environment with the production frontend.
