# SimEx AI — Implementation Backlog

Companion to [`review.md`](./review.md). Tasks are **dependency-ordered**, not severity-ordered — later phases assume earlier ones landed. IDs in parentheses map to review findings.

**Legend:** `[S]` hours · `[M]` 1–3 days · `[L]` ~1 week+

---

## Phase 0 — Enabling infrastructure ✅ COMPLETE

> **Verified against the live server (2026-08-20).** gemma-4-26b-a4b confirmed working for
> chat, **tool calling** (`finish_reason: tool_calls`, valid JSON args — Phase 5 is viable),
> and **vision** (exact OCR through LangChain's async path — the upload pipeline is safe).
>
> **Key discovery: it is a reasoning model.** It spends 100–1700 tokens on internal reasoning
> before emitting any visible answer, and `max_tokens` covers both. This makes P1-5 more severe
> than the review stated — the old `num_predict=700` would have returned *empty* chat responses,
> not just truncated extractions. Budgets are now 3000 (chat) / 16000 (extraction).
> Reasoning arrives in a separate `reasoning_content` field, not inline `<think>` tags,
> so responses come back clean — which reduces the urgency of task 6.3.

Migrate the LLM client first. Everything in Phases 3–5 depends on structured outputs, tool calling, and streaming, which the OpenAI-compatible API provides and `ChatOllama` does not.

- [x] **0.1** `[S]` Swap `langchain-ollama` → `langchain-openai`; point `ChatOpenAI` at LM Studio (`http://localhost:1234/v1`, model `google/gemma-4-26b-a4b`). Map `num_predict`→`max_tokens`, `client_kwargs.timeout`→`timeout`.
- [x] **0.2** `[S]` Rename `backend/ollama_engine.py` → `backend/llm_engine.py`, `OllamaEngine` → `LLMEngine`. Update `app.py:13,44`.
- [x] **0.3** `[S]` `OLLAMA_*` → `LMSTUDIO_*` env vars in `.env`, `.env.example`. Drop the hardcoded `172.18.1.132` default (P2-6). Invert `_normalize_base_url` to ensure a `/v1` suffix.
- [x] **0.4** `[S]` Rewrite `format_llm_error` for the failures that actually occur: connection refused (LM Studio down) and `model_not_found` (model not loaded).
- [x] **0.5** `[S]` `start.ps1` + `start.bat` one-command launcher: verify `uv`, check `.env`, `uv sync`, launch uvicorn, open browser when the port answers. Flags: `-Port`, `-NoSync`, `-NoBrowser`. Add a preflight probe of `/v1/models` so a down LM Studio fails loudly at startup rather than on the first chat.
- [x] **0.6** `[S]` Update `README.md` and the three `.agent/skills/*/SKILL.md` files that reference Ollama.

---

## Phase 1 — Sessions and persistence *(unblocks everything)*

**(P0-5, P0-2)** There is currently no concept of "an exercise run." Nothing else is fixable until there is.

- [ ] **1.1** `[M]` Add schema: `sessions` (id, scenario_id, wing_id, participant_label, current_phase_index, status, created_at), `messages` (id, session_id, role, content, phase_id, created_at, token_count), `inject_state` (session_id, inject_id, status, delivered_at, addressed_at), `assessments` (id, session_id, inject_id, rubric scores, evidence, gaps, created_at). Write a migration for the existing `data/simex.db`.
- [ ] **1.2** `[S]` Add the missing `injects.status` column — `_normalize_injects` sets it (`app.py:152`) and it is silently dropped today.
- [ ] **1.3** `[M]` Delete the module-level `scenario` / `responder` singletons (`app.py:43-44`). Load per-session exercise state keyed by a session id; make `ScenarioEngine` an instance owned by a session, never process-global.
- [ ] **1.4** `[S]` Thread a session id through every API route and the frontend (cookie or explicit header). Reject requests without one.
- [ ] **1.5** `[S]` Separate **controller** actions from **participant** actions. `phase/advance`, `phase/back`, `phase/reset`, and `scenario/upload` are controller-only; today any participant can reset everyone's exercise.
- [ ] **1.6** `[S]` `PRAGMA foreign_keys=ON` + WAL mode; indexes on `injects(scenario_id, phase_id)`, `messages(session_id)`; close connections properly (P2-3).

---

## Phase 2 — Conversation memory

**(P0-1)** The single largest quality jump available. Depends on Phase 1.

- [ ] **2.1** `[M]` Persist every turn to `messages` and load history into the prompt: `[system, ...history, user]` instead of today's two-message array (`llm_engine.py:138-142`).
- [ ] **2.2** `[M]` Context-window management: rolling window of recent turns + a running summary of older ones, budgeted against the model's context. Store the summary on the session so it is not recomputed per turn.
- [ ] **2.3** `[S]` Restore chat history on page load from the server (`GET /api/session/{id}/messages`) so refresh no longer destroys the transcript.
- [ ] **2.4** `[S]` Include the inject ledger in the prompt — what has been delivered and what the participant has already addressed — so the moderator stops re-raising resolved items.

---

## Phase 3 — Correctness fixes

Independent of each other; each is shippable alone. Do these while Phase 4 is being designed.

- [ ] **3.1** `[S]` **(P0-7)** Fix the f-string brace bug at `app.py:225`: `{{wing_ids}}` → `{wing_ids}`. One character each side. Verified: the model currently receives the literal string `{wing_ids}` and has never seen the canonical wing list.
- [ ] **3.2** `[S]` **(P0-7)** Set `normalize_wing_ids(..., keep_unknown=False)` for extraction output and log rejects, so hallucinated wing ids stop reaching SQLite and Pinecone.
- [ ] **3.3** `[S]` **(P0-6)** Replace `injects[:6]` (`llm_engine.py:193`) with mandate- and relevance-ranked selection: filter by the participant's wing via `required_wings`, then rank by severity and retrieval score, then apply a token budget rather than a magic count.
- [ ] **3.4** `[S]` **(P0-6/P0-3)** Make `required_wings` actually do something. It is written, stored, and embedded today but never used to filter anything — `get_injects_for_phase` (`scenario_engine.py:88`) filters on phase alone, so every wing sees every wing's injects.
- [ ] **3.5** `[S]` **(P1-3)** Make phase server-authoritative in `/api/chat`. Stop trusting `request.phase_id` (`app.py:448`); derive it from the session.
- [x] **3.6** `[S]` **(P1-5)** Give extraction its own sampling config: `temperature=0`, large `max_tokens`. *(Done in Phase 0: chat 3000 / extraction 16000 @ T=0. Budgets sized for reasoning overhead — see note below.)*
- [ ] **3.7** `[M]` **(P1-5)** Use LM Studio structured outputs (`response_format` with a JSON schema) for extraction. This should let most of `_clean_llm_json` and the `json_repair` fallback (`app.py:77-127`) be deleted — they exist to paper over 3.6.
- [ ] **3.8** `[S]` **(P1-2)** Wrap `_read_upload_as_context` in `run_in_threadpool`. It currently blocks the event loop through full PDF rasterization and Word COM automation, freezing every other participant's request.
- [ ] **3.9** `[M]` **(P1-4)** Cross-chunk coherence in extraction: pass prior-chunk scenario context forward, dedup injects semantically (not by renumbering ids, which hides the problem), and **fail the upload loudly** when chunks fail instead of reporting success.
- [ ] **3.10** `[S]` **(P2-4)** Return proper HTTP status codes on upload and TTS failure instead of 200-with-an-error-message.
- [ ] **3.11** `[S]` **(P2-5)** Fix namespace cleanup: `delete_scenario` is called with the *new* id (`app.py:352`) and is always a no-op. Delete the *previous* scenario's namespace, or add a retention job.

---

## Phase 4 — RAG rebuild

**(P0-3, P0-4, P1-6)** The heart of the ask. Depends on Phase 2 for query rewriting.

- [ ] **4.1** `[M]` **Index the actual source document.** Chunk and upsert `extracted_text` (currently discarded at `app.py:262`), not just the re-synthesized summary narrative. This is the root fix — today RAG runs over the model's own lossy summary.
- [ ] **4.2** `[M]` Parent–child chunking (~1500-char parents, ~400-char children; embed children, return parents) replacing the flat 500/50 splitter (`vector_store.py:22-26`). Carry `source_page` metadata through from the parser for citation.
- [ ] **4.3** `[M]` **Add a reranker.** Two-stage: retrieve top-30 → `pc.inference.rerank()` with `bge-reranker-v2-m3` → top-5. Highest-leverage single change in this phase.
- [ ] **4.4** `[S]` **Metadata filtering at query time.** Filter `phase_id <= current_phase` and by category. Metadata is already written (`vector_store.py:100-121`) and completely ignored at retrieval. **This closes a spoiler leak** — a D-90 participant can currently have D+90 content retrieved into their answer.
- [ ] **4.5** `[S]` Score threshold + dynamic `top_k`. When nothing clears the threshold, say so rather than padding the prompt with noise.
- [ ] **4.6** `[M]` **(P1-6)** History-aware query rewriting before retrieval, so follow-ups like "what about that bridge?" resolve to a real query. Requires 2.1.
- [ ] **4.7** `[S]` Retrieve for phase-advance briefings too — currently the highest-value moment for retrieval issues no query at all.
- [ ] **4.8** `[M]` Hybrid retrieval (dense + sparse/BM25) for exact-match recall on the quantitative data the extraction prompt works hard to preserve — river names, road km, population counts.
- [ ] **4.9** `[S]` Source citation: carry chunk provenance into the moderator's context so its claims are traceable to a document page.

---

## Phase 5 — The agent loop

**(P1-1, P0-2)** This is what makes it agentic. Depends on Phases 1, 2, 4.

- [ ] **5.1** `[L]` Define the moderator tool schema: `grade_response`, `deliver_inject`, `mark_inject_addressed`, `request_clarification`, `advance_phase` (controller-gated). See `review.md` §5.
- [ ] **5.2** `[L]` Implement the turn loop: rewrite → retrieve → rerank → moderator LLM with tools → execute tool calls → persist → respond. Bound iterations and handle tool-call failure explicitly.
- [ ] **5.3** `[M]` Rubric-based scoring against each wing's mandate (`mandate.py` already has the mandate data — `format_mandate_for_prompt` is the seam). Persist structured scores with supporting evidence quotes to `assessments`.
- [ ] **5.4** `[M]` Inject lifecycle driven by the agent: decide *when* to deliver based on conversation state and mandate relevance, instead of dumping a fixed slice into every prompt.
- [ ] **5.5** `[M]` **After-action report** — per-wing performance summary, mandate coverage, gaps, timeline of injects and responses. Exportable (PDF/Markdown). This is the deliverable that makes it a training product rather than a demo.
- [ ] **5.6** `[S]` Controller dashboard: live view of all wings' sessions, phase state, and outstanding injects.

---

## Phase 6 — Safety and guardrails

- [ ] **6.1** `[M]` **(P0-8)** Prompt-injection defense on ingested documents: delimit untrusted content explicitly, add instruction-hierarchy framing, and screen extracted text for injection patterns before it enters the prompt. **Highest-risk item in the review** — a malicious scenario PDF can currently make the invigilator hand out the answers.
- [ ] **6.2** `[M]` **(P1-8)** Output-side validation for the failures that matter: solution leakage, persona break, invented NDMA policy, scenario contradiction. Replace the eleven-regex profanity blocklist (`llm_engine.py:12-26`) with input classification that does not flag "damn."
- [ ] **6.3** `[S]` Harden `_strip_thinking` (`llm_engine.py:207`) — it only handles a closing `</think>` and leaks reasoning traces when the tag is malformed or unpaired.
- [ ] **6.4** `[S]` **(P2-1)** Real CORS origins; drop `allow_origins=["*"]` + `allow_credentials=True`, which is an invalid combination browsers reject for credentialed requests.
- [ ] **6.5** `[M]` Authentication and roles (controller vs participant). Currently anyone on the network can reset the exercise or upload a scenario.
- [ ] **6.6** `[S]` **(P2-2)** Upload size cap, MIME validation, and page limit. Given 3.8, a large PDF is an easy DoS today.
- [ ] **6.7** `[S]` Rate limiting on `/api/chat`, `/api/tts`, and `/api/scenario/upload`.

---

## Phase 7 — UX and streaming

- [ ] **7.1** `[M]` **(P1-9)** SSE streaming for chat responses. Largest perceived-quality win available. Sequence carefully — it interacts with the TTS word-highlighting feature.
- [ ] **7.2** `[S]` Reconcile TTS with streaming: either buffer to sentence boundaries and synthesize incrementally, or synthesize on completion.
- [ ] **7.3** `[S]` **(P2-7)** Real error handling in `frontend/app.js:58-70` — distinguish network / timeout / 5xx, add retry with backoff, stop collapsing every failure into `null`.
- [ ] **7.4** `[S]` Loading and progress states for upload — a 50-page PDF currently gives no feedback for a long time.
- [ ] **7.5** `[M]` Split `app.js` (1,127 lines) into ES modules; consider a light build step.

---

## Phase 8 — Testing and observability

Start this **during Phase 3**, not after Phase 7 — Phases 4 and 5 are unmeasurable without it.

- [x] **8.1a** `[S]` **(P1-10)** Restore the deleted tests and add pytest scaffolding. *(Done: recovered `tests/` from `main`; the 4 `test_document_parser.py` cases pass verbatim since `document_parser.py` never changed. `test_upload_vision_endpoint.py` rewritten for SQLite persistence, the async `ainvoke` path, and the D-90..D+90 phase scheme. pytest + pytest-asyncio added as a dev group. Mutation-checked: the suite fails when image attachment is broken.)*
- [ ] **8.1b** `[M]` **(P1-10)** Extend unit coverage to the untested pure logic: `mandate.normalize_wing_id`, `_parse_llm_json`, `_normalize_injects`, `ScenarioEngine` transitions, and the database layer. Add CI.
- [ ] **8.1c** `[S]` Declare `en_core_web_sm` in `pyproject.toml`. It is an **undeclared runtime dependency**: `uv sync` strips it, and Kokoro then re-downloads it over the network on the first TTS call. That is a silent failure in an air-gapped deployment.
- [ ] **8.2** `[M]` Golden-set extraction eval: fixture documents with known expected injects; measure precision/recall on extraction. This is what makes prompt changes safe.
- [ ] **8.3** `[M]` Retrieval eval: labeled query→chunk set, measure recall@k and MRR. Required to prove the Phase 4 reranker actually helps rather than assuming it.
- [ ] **8.4** `[M]` LLM-judge eval for moderator quality: does it withhold solutions, stay in persona, ask genuine follow-ups, use retrieved context?
- [ ] **8.5** `[S]` **(P1-7)** Replace `print()` with structured logging throughout. Stop swallowing exceptions silently — especially `app.py:45-49`, where a Pinecone outage disables RAG for the entire process lifetime with no signal.
- [ ] **8.6** `[S]` `/health` endpoint reporting LM Studio reachability, Pinecone reachability, DB status, and model loaded.
- [ ] **8.7** `[S]` Per-request tracing: latency, token counts, retrieval scores, tool calls. Needed to debug a nondeterministic system at all.

---

## Suggested first sprint

If you want the fastest path to a visibly better product:

1. **0.1–0.6** — LM Studio migration + launcher *(half a day)*
2. **3.1, 3.5, 3.6, 3.8** — four small high-impact correctness fixes *(half a day)*
3. **1.1–1.4** — sessions and persistence *(2–3 days)*
4. **2.1–2.3** — conversation memory *(2 days)*

That sequence alone converts the system from a stateless prompt proxy into something that remembers a conversation, which is the difference participants will feel most. **4.1, 4.3, and 4.4** follow immediately after and are the substance of the RAG improvement you asked about.
