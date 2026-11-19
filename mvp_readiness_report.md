# MVP Readiness Report

Date: 2026-11-14. Production provider: Azure OpenAI only. **LIVE** = real Azure/Uvicorn run in this phase; **MOCKED** = automated tests.

## Verdict: READY FOR A SMALL PILOT once the manual steps below are done

Not production-hardened. Three items must be done first (section 3, marked **MUST**).

## 1. What changed in this phase (minimal)

| Change | File |
|---|---|
| `LLM_DAILY_TOKEN_BUDGET` default 0 (unlimited) → **1,000,000** tokens/UTC day (about 220–280 chats at ~3.5–4.5k tokens each) | `app/core/config.py`, `.env.example` |
| English emergency detection: added "don't want to live / be alive", "ending it all", "not worth living", "better off dead" | `app/rag/guardrails.py` |
| Regression tests (budget default, English phrasings, no false alarms, no Sources on emergency replies) | `tests/test_phase11.py` |
| This report | `mvp_readiness_report.md` |

Not touched: `.env`, Azure OpenAI/Search config, embeddings, retriever, auth, LMS, database, dependencies. No new architecture, tables, agents, or Redis.

## 2. Verification

| Check | Result | Type |
|---|---|---|
| Full test suite | **178 passed, 0 failed** (up from 165) | MOCKED |
| Uvicorn start (`app.main:app`, port 8765) | Started in ~6 s; `/api/health` and `/api/ready` returned 200; stopped cleanly | LIVE |
| English streaming question | 200, `text/event-stream`, `X-Request-ID`, 180 content events, Sources `Nettrikkan English.docx (1).pdf` pages 1 and 5, one `[DONE]` | LIVE |
| Tamil question (non-stream) | Tamil answer, Sources `Third_Eye_Meditation_RAG_TAMIL.pdf` pages 5 and 3, no `[Source:` tags | LIVE |
| Token tracking | Both calls logged real usage (3,504 and 4,190 tokens) | LIVE |
| English emergency over HTTP | SSE emergency message, empty Sources event, `[DONE]`, no model call, no phone numbers | LIVE |
| 422 / 429 limits | 422 for an oversized message; 429 (rate and budget) verified in Phase 1.2; budget logic re-tested | LIVE (Phase 1.2) + MOCKED |
| Emergency replies show no Sources (`/api/chat` JSON, SSE, `/api/chat/graph`) | Empty Sources; no retrieval or model call | MOCKED |
| `Event loop is closed` embedding error under real Uvicorn | Not seen in the Uvicorn log across the English and Tamil requests | LIVE |

Uvicorn log at startup shows only expected warnings: memory-only limits, no approved emergency contacts, no reviewed regional keywords.

## 3. Manual setup before the pilot

Set these as environment variables on the host (do not commit them; `.env` was not changed):

1. **MUST: `SECRET_KEY` and `JWT_SECRET_KEY`.** The local `.env` does not contain them, so the code falls back to the placeholder defaults (`your-secret-key-here`, `your-jwt-secret-key-here`). Anyone who knows the default can forge login tokens. Check the host's environment and set long random values. Also used to hash IPs for rate limits. Could not verify the host's settings.
2. **MUST: `TRUSTED_PROXY_HOPS`.** Currently 0. If the app sits behind a proxy (Render, Azure Container Apps), every visitor may appear as the proxy's IP and share one limit of 20 requests/minute. Find the real number of proxies and set it (typically 1). A wrong value lets clients spoof their IP.
3. **MUST: a smoke test on the deployed URL** (see section 5) with the production frontend.
4. `LLM_PROVIDER=azure_openai` (already the default; set it explicitly).
5. Optional: change `LLM_DAILY_TOKEN_BUDGET` to fit your Azure spend. Tokens are counted per process and reset at UTC midnight (about 05:30 IST); a restart also resets the counter.
6. When ready: an approved `EMERGENCY_POLICY_FILE` (copy `emergency_policy.example.json`, fill in contacts with `approved_by` and `approved_on`, keywords with `reviewed_by`).
7. Run a single instance (`USAGE_STORE=memory` is per process). The Dockerfile runs one Uvicorn worker, which matches.

## 4. Known limitations (not fixed, by design)

- **Tamil emergency detection does not exist.** No Tamil keywords are configured and none were invented. A Tamil message about suicide goes to the model like any question. In the live Phase 1.2 test the model replied in Tamil, advised contacting a trusted person or local emergency services, declined meditation guidance, and gave no phone numbers. That depends on the model following its prompt and is not guaranteed. Needs a native Tamil speaker to review keywords, plus approved contacts from the Netrikkan team.
- **Sources on a Tamil crisis reply.** Because that reply comes from the model, it still lists knowledge-base Sources. Emergency replies detected by keyword (English) never show Sources. Fixing the Tamil case needs reliable Tamil detection first.
- **English detection is phrase-based.** Ambiguous statements such as "I can't go on" or "I feel hopeless" are not detected (matching them would flag many harmless questions). Phrasing beyond the tested set may be missed.
- **Emergency message has no phone numbers** until approved contacts are configured.
- **Sources mean "retrieved and given to the model"**, not "used in the answer".
- **Higher token cost per chat** (~3.5–4.5k input tokens): the existing retriever returns the same documents for all four layers. Not changed (retrieval is out of scope).
- **Limits are per process.** Rate limits and the daily budget reset on restart and are not shared across instances.
- **Guardrail checks are keyword-based** and add disclaimers; they do not block unsafe text.

## 5. Not verified

- The deployed environment, its proxy hop count and its environment variables.
- The production frontend (`thirdeye-ai-frontend`) and the bundled web UI in a real browser; only its parser was tested.
- Login, LMS and subscription flows against the live host (their automated tests pass).
- Tamil answer quality by a Tamil reader (language and Sources checked only).
- Load or concurrency behavior; long-running stability.
- Real Redis (not used for the MVP).

## 6. Pilot smoke test (about 5 minutes, after deploy)

1. `GET /api/health` returns 200.
2. Ask an English and a Tamil question in the UI; check streaming completes, Sources appear, no `[Source:` text.
3. Type an English crisis sentence (for example "I don't want to live anymore"); check the emergency message appears with no Sources and no numbers.
4. Send 21 requests within a minute from one browser; the 21st should return 429 with a readable message.
5. Check logs for `llm_call` records and the startup warnings above.
