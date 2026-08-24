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

## Phase 1 — Sessions and persistence ✅ COMPLETE

**(P0-5, P0-2)** There is now a concept of "an exercise run" and every request is resolved
against one.

> **Verified (2026-08-20).** Route-wired and browser-tested: first active session claims
> controller, participants get `403` on controller actions, the shared timeline persists
> on `exercises` and participant UIs follow controller advances within 5s without reload.
> Chat phase is server-authoritative (3.5) and the extraction prompt brace bug is fixed
> (3.1). 12 tests pass against an isolated `SIMEX_DB_PATH`; external AI/Pinecone services
> are stubbed.

- [x] **1.1** `[M]` Add schema: `sessions` (id, scenario_id, wing_id, participant_label, current_phase_index, status, created_at), `messages` (id, session_id, role, content, phase_id, created_at, token_count), `inject_state` (session_id, inject_id, status, delivered_at, addressed_at), `assessments` (id, session_id, inject_id, rubric scores, evidence, gaps, created_at). Write a migration for the existing `data/simex.db`.
- [x] **1.2** `[S]` Add the missing `injects.status` column — `_normalize_injects` sets it (`app.py:152`) and it is silently dropped today.
- [x] **1.3** `[M]` Delete the module-level `scenario` / `responder` singletons (`app.py:43-44`). Load per-session exercise state keyed by a session id; make `ScenarioEngine` an instance owned by a session, never process-global.
- [x] **1.4** `[S]` Thread a session id through every API route and the frontend (cookie or explicit header). Reject requests without one.
- [x] **1.5** `[S]` Separate **controller** actions from **participant** actions. `phase/advance`, `phase/back`, `phase/reset`, and `scenario/upload` are controller-only; today any participant can reset everyone's exercise.
- [x] **1.6** `[S]` `PRAGMA foreign_keys=ON` + WAL mode; indexes on `injects(scenario_id, phase_id)`, `messages(session_id)`; close connections properly (P2-3).

---

## Phase 2 — Conversation memory ✅ COMPLETE

**(P0-1)** The single largest quality jump available. Depends on Phase 1.

> **Verified (2026-08-20).** Every turn is persisted to `messages` (with `wing_id`) and the
> chat route loads the wing's history and passes it into `get_response` as
> `[system, ...history, user]`. History windowing: the last 12 turns verbatim, older turns
> condensed into one deterministic system block (200 chars/turn) — a real LLM summarizer
> is deferred, stored summaries are not yet recomputed per turn. `GET /api/session/messages`
> restores the transcript on page load (verified in-browser: a message survives reload and no
> duplicate greeting fires). The inject ledger (delivered + addressed) is built per chat and
> injected into the prompt, with `inject_state` rows updated server-side. 16 tests pass.

- [x] **2.1** `[M]` Persist every turn to `messages` and load history into the prompt: `[system, ...history, user]` instead of today's two-message array (`llm_engine.py:138-142`).
- [x] **2.2** `[M]` Context-window management: rolling window of recent turns + a running summary of older ones, budgeted against the model's context. Store the summary on the session so it is not recomputed per turn. *(Deterministic condensation in place; stored LLM summary deferred to a follow-up.)*
- [x] **2.3** `[S]` Restore chat history on page load from the server (`GET /api/session/messages`) so refresh no longer destroys the transcript.
- [x] **2.4** `[S]` Include the inject ledger in the prompt — what has been delivered and what the participant has already addressed — so the moderator stops re-raising resolved items. *(Delivery + addressed marking live; full agent-driven delivery is Phase 5.4.)*

---

## Phase 2A — Chat history controls ✅ COMPLETE

Provide an explicit way to start a clean conversation without resetting the exercise or deleting
assessment evidence. Clearing chat is scoped to the current session and selected wing by default.

> **Verified (2026-08-24).** The active-wing clear action is server-authoritative, idempotent, and
> isolated by session/wing. Explicit message kinds preserve assessment artifacts; a persisted clear
> marker prevents automatic greetings from recreating deleted history after reload; history-version
> checks discard LLM responses racing with deletion. API and real Chromium tests cover preservation,
> authorization, cross-session isolation, reload, failure, keyboard focus, and retained assessment
> result messages. Full suite: 43 passed.

- [x] **2A.1** `[S]` Define clear-history semantics: delete only ordinary transcript messages for
  `(session_id, wing_id)`; preserve the scenario, shared phase, inject lifecycle, other wings,
  assessment questions/answers/scores, and final preparedness remarks. After clearing, the next
  ordinary chat turn starts with no prior conversational memory.
- [x] **2A.2** `[S]` Add a transactional database method and authenticated
  `DELETE /api/session/messages/{wing_id}` endpoint. Normalize and authorize the wing, return the
  deleted count, make repeated requests idempotent, and prevent participants from clearing another
  wing or session. Do not accept an arbitrary `session_id` from the client.
- [x] **2A.3** `[S]` Add a **Clear chat** action for the active wing with a confirmation dialog that
  names the wing and states what will be preserved. Disable it when no wing/history is selected,
  clear only that wing's local message state after server success, stop active TTS/typing indicators,
  and show a recoverable error without hiding messages if deletion fails.
- [x] **2A.4** `[S]` Keep assessment records canonical and separately rendered. Clearing ordinary
  chat during an active or completed five-question assessment must not decrement `N/5`, recreate a
  question, remove score cards, or permit a sixth answer.
- [x] **2A.5** `[S]` Add API and browser tests for wing isolation, authorization, idempotent repeated
  clear, reload after clear, clearing during an active assessment, completed-result preservation,
  request failure, and keyboard-accessible confirmation/focus restoration.

**Exit criteria:** after clearing one wing and reloading, that wing's ordinary transcript remains
empty and no longer enters the moderator prompt, while every other wing and all exercise/assessment
state remain unchanged.

---

## Phase 3 — Correctness fixes

Independent of each other; each is shippable alone. Do these while Phase 4 is being designed.

- [x] **3.1** `[S]` **(P0-7)** Fix the f-string brace bug at `app.py:225`: `{{wing_ids}}` → `{wing_ids}`. One character each side. Verified: the model currently receives the literal string `{wing_ids}` and has never seen the canonical wing list.
- [x] **3.2** `[S]` **(P0-7)** Set `normalize_wing_ids(..., keep_unknown=False)` for extraction output and log rejects, so hallucinated wing ids stop reaching SQLite and Pinecone. *(Unknown ids are dropped with an inject-specific warning before persistence/indexing.)*
- [x] **3.3** `[S]` **(P0-6)** Replace `injects[:6]` (`llm_engine.py:193`) with mandate- and relevance-ranked selection: filter by the participant's wing via `required_wings`, then rank by severity and retrieval score, then apply a token budget rather than a magic count. *(Severity first, Pinecone hit score as tie-breaker, approximate 1,200-token budget.)*
- [x] **3.4** `[S]` **(P0-6/P0-3)** Make `required_wings` actually do something. It is written, stored, and embedded today but never used to filter anything — `get_injects_for_phase` (`scenario_engine.py:88`) filters on phase alone, so every wing sees every wing's injects. *(Prompt, ledger, phase responses, and `/api/injects` are wing-aware; untargeted legacy injects remain global.)*
- [x] **3.5** `[S]` **(P1-3)** Make phase server-authoritative in `/api/chat`. Stop trusting `request.phase_id` (`app.py:448`); derive it from the session.
- [x] **3.6** `[S]` **(P1-5)** Give extraction its own sampling config: `temperature=0`, large `max_tokens`. *(Done in Phase 0: chat 3000 / extraction 16000 @ T=0. Budgets sized for reasoning overhead — see note below.)*
- [ ] **3.7** `[M]` **(P1-5)** Use LM Studio structured outputs (`response_format` with a JSON schema) for extraction. This should let most of `_clean_llm_json` and the `json_repair` fallback (`app.py:77-127`) be deleted — they exist to paper over 3.6.
- [x] **3.8** `[S]` **(P1-2)** Wrap document parsing in `run_in_threadpool`. *(Done in 27df5ab — was a hard prerequisite for upload progress polling, which the frozen loop would otherwise have blocked. Pinecone indexing moved off the loop too.)*
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

## Feature track 5A-5I — Five-question wing preparedness assessment

**Goal:** For every wing in an exercise run, SimExAI asks exactly five scored questions,
judges each submitted answer from **0 to 10**, and publishes a final score and evidence-based
preparedness remarks after question five. This is the detailed delivery plan for **5.3** and the
per-wing scoring portion of **5.5**. It can ship before the complete tool-calling loop in 5.1-5.4;
it depends on completed Phases 1-2 and a proven structured-output path for the judge.

### Proposed MVP contract (confirm in 5A)

- The assessment subject is one wing team in one exercise attempt. The current result is unique by
  `(exercise_id, wing_id, attempt_no)`, with at most one active attempt for that exercise and wing.
  Any authorized session acting for that wing may continue the same assessment; retain the
  submitting `session_id` on every answer for auditability.
- Each wing receives five questions **per exercise run**, not five per timeline phase. Store the
  phase in which each question was asked, but phase changes do not reset or duplicate progress.
- Questions cover five fixed command-level lenses in order: **risk picture**, **priorities and
  decisions**, **operational readiness**, **coordination and ownership**, and **contingency and
  adaptation**. The LLM may adapt wording to the wing, scenario, current phase, and injects, but
  may not change the lens or reveal future injects.
- Each answer receives one integer score in the inclusive range `0..10`, concise strengths,
  material gaps, evidence grounded in the submitted answer, and short improvement feedback.
- Judge each answer immediately but withhold scores and coaching feedback until all five answers are
  complete, so early feedback cannot train later answers. Return only submission confirmation and
  the next question during the active assessment.
- The backend computes the final score as the arithmetic mean of five validated answer scores,
  rounded to one decimal. The LLM never performs or overrides score arithmetic.
- Preparedness bands are deterministic: `0.0-2.9 Critical gaps`, `3.0-4.9 Limited`,
  `5.0-6.9 Developing`, `7.0-8.9 Prepared`, and `9.0-10.0 Highly prepared`.
- Final remarks summarize demonstrated strengths, recurring gaps, and the highest-priority
  improvement, using only the five persisted judgments. A result is not final while any judgment
  is missing or invalid.
- Assessment progress is server-authoritative. Greetings, general chat, phase notices, retries,
  and assistant prose never increment the question counter.
- MVP assessment grounding is deliberately limited to the persisted scenario summary, current and
  prior phase metadata, current/prior wing-relevant injects, and the wing mandate snapshot. Do not
  use unconstrained source-document RAG until spoiler-safe metadata filtering in 4.4 is complete.
- The existing `/api/phase/reset` remains a timeline rewind and preserves results. Starting a new
  scenario/attempt creates a new exercise run; destructive assessment reset is a separate,
  controller-only action with explicit confirmation.

### Phase 5A — Product rules and evaluation specification

- [ ] **5A.1** `[S]` Record the MVP contract above in an ADR: assessment ownership, exactly-five
  invariant, five question lenses, phase interaction, score formula, rounding, preparedness bands,
  visibility of per-answer scores, finalization rules, and reset/new-attempt semantics.
- [ ] **5A.2** `[M]` Write the versioned scoring rubric. Define observable anchors for `0`, `2`,
  `5`, `8`, and `10`; require scenario relevance, mandate alignment, prioritization, feasibility,
  ownership/coordination, and adaptation only when the current question lens calls for them.
- [ ] **5A.3** `[S]` Define evidence rules: the judge must cite or closely reference claims from
  the participant answer, must distinguish absent evidence from an incorrect claim, and must not
  award points for facts supplied only by the moderator.
- [ ] **5A.4** `[S]` Decide controller policy for phase advance while wings are incomplete. MVP
  recommendation: allow advance with a visible incomplete-wing warning; do not silently finalize
  or restart assessments.
- [ ] **5A.5** `[S]` Define the post-completion interaction: assessment input becomes read-only for
  scoring, while ordinary unscored chat remains available only through an explicit mode/action so
  a sixth message cannot be mistaken for a sixth answer.
- [ ] **5A.6** `[S]` Confirm the canonical wing count from `data/Mandate/mandate.json` (currently
  nine) and correct stale product copy before using the count in completion dashboards or reports.
- [ ] **5A.7** `[M]` Define and implement the assessment permission matrix before exposing routes:
  participants can start/read/answer only their bound wing; controllers can read all summaries and
  invoke retry/reset/export. Remove the current automatic promotion of every session to controller
  for this workflow, coordinating the general authentication work with 6.5.
- [ ] **5A.8** `[S]` Confirm that one exercise has one team per canonical wing. If multiple teams may
  represent the same wing, introduce an explicit `team_id` now rather than overloading session or
  adding it after results exist.
- [ ] **5A.9** `[S]` Set user-facing service targets from a live LM Studio baseline: maximum answer
  length, submission-to-acceptance latency, p95 judgment/next-question latency, concurrent wing
  capacity, and timeout/retry limits. Use these targets to choose synchronous `200` versus persisted
  asynchronous `202` behavior in 5E.9.

**Exit criteria:** rubric and lifecycle decisions are reviewable without reading prompt code;
two evaluators independently place a sample answer within one point using the rubric anchors.

### Phase 5B — Domain model, schema, and migration

- [ ] **5B.1** `[M]` Add `wing_assessments`: `id`, `exercise_id`, `wing_id`, `attempt_no`, `status`,
  `questions_required` (fixed at 5), `current_ordinal`, `answered_count`, `lock_version`,
  `final_score`, `preparedness_band`, `final_remarks`, `rubric_version`, `judge_model`, timestamps,
  `UNIQUE(exercise_id, wing_id, attempt_no)`, and a partial unique index permitting only one active
  attempt per exercise/wing. Reset archives the old attempt and increments `attempt_no`.
- [ ] **5B.2** `[M]` Add `assessment_questions`: `id`, `wing_assessment_id`, `ordinal` constrained
  to `1..5`, `phase_id`, `lens`, `question_text`, immutable evaluation-context JSON/hash, status,
  timestamps, and `UNIQUE(wing_assessment_id, ordinal)`. The context snapshot contains the exact
  mandate, scenario/phase evidence, relevant inject ids/text, rubric, prompt, schema, and model
  versions used at question time; do not model multiple injects as one nullable `inject_id`.
- [ ] **5B.3** `[M]` Add canonical `assessment_answers`: question id, submitting session id,
  immutable answer text/hash, persisted idempotency key, status, timestamps, and
  `UNIQUE(question_id)` plus a scoped unique idempotency constraint. Add `answer_judgments`: answer
  id, integer score with `CHECK(score BETWEEN 0 AND 10)`, strengths/gaps/evidence JSON, feedback,
  judge/schema versions, status, timestamps, and `UNIQUE(answer_id)`. Confirm the legacy
  `assessments` table has no rows before removal; migrate or retain it as legacy if real data exists.
- [ ] **5B.4** `[S]` Extend `messages` with an explicit `kind` and optional `question_id` so
  `participant_answer`, `moderator_question`, `score_feedback`, `general_chat`, `orientation`, and
  `phase_notice` cannot be confused. Backfill existing rows as `general_chat`. Assessment tables and
  APIs are canonical for shared question/answer/result cards; never reconstruct them by merging
  session-owned transcripts or duplicate them as ordinary chat rows.
- [ ] **5B.5** `[M]` Add database repository methods for create/load/list assessment, reserve an
  ordinal, persist a generated question, claim an answer for scoring, persist a judgment, finalize,
  and controller reset. Use transactions and uniqueness constraints rather than process-local locks.
- [ ] **5B.6** `[M]` Make answer submission idempotent with a client request id and assessment
  `lock_version`/current-question check. Persist the request id and terminal response reference so
  replay survives restart. Two concurrent submissions for question five must produce one judgment,
  one final result, and a deterministic `409`/idempotent replay for the loser.
- [ ] **5B.7** `[S]` Add indexes for `(exercise_id, wing_id)`, assessment status, question ordinal,
  answer/judgment lookup, and idempotency key. Assessment evidence is immutable audit data: define
  `ON DELETE RESTRICT/SET NULL` behavior so session deletion, message cleanup, or scenario replacement
  cannot cascade-delete completed results or submitting-session provenance.
- [ ] **5B.8** `[M]` Specify state ownership and legal compare-and-set transitions in the repository:
  assessment owns ordinal/count/finalization; question owns generation/answer state; answer owns
  submission/scoring state. Define who can retry each failure and prove `answered_count` increments
  only when a valid judgment commits, including score-success/next-question-generation-failure.
- [ ] **5B.9** `[M]` Fix scenario upload lifecycle before assessment routes ship: create a new
  exercise run and archive the old one instead of repointing an exercise containing transcripts or
  scores to a new scenario.

**Exit criteria:** migration works on a copy of the current SQLite database; repository tests prove
five-ordinal uniqueness, score constraints, wing isolation, idempotency, and concurrent fifth-answer
safety without calling an LLM.

### Phase 5C — Typed API and structured AI contracts

- [ ] **5C.1** `[S]` Add Pydantic contracts in `backend/models.py` for assessment summary,
  question, answer submission, per-answer judgment, progress, final result, and structured errors.
  Stable IDs come from the server and are never accepted from model output.
- [ ] **5C.2** `[M]` Create a dedicated deterministic judge client (`temperature=0`) separate from
  conversational moderation and upload extraction. Configure independent timeout, token budget,
  model name, and retry policy through `LMSTUDIO_JUDGE_*` environment variables.
- [ ] **5C.3** `[M]` Prove LM Studio JSON-schema structured output with the deployed model. Bind a
  schema containing `score`, `strengths`, `gaps`, `evidence`, and `feedback`; reject extra fields,
  fractional/out-of-range scores, empty evidence, and malformed payloads.
- [ ] **5C.4** `[S]` Allow one bounded repair/retry for syntactically invalid judge output. If it
  remains invalid or times out, persist `scoring_failed`, return a retryable error, and do not
  increment progress or fabricate/clamp a score.
- [ ] **5C.5** `[M]` Version and snapshot all evaluation inputs: rubric version, wing mandate,
  question lens, scenario/phase evidence, active inject context, judge model, and prompt version.
  Historical scores must remain explainable after prompts or mandate data change.
- [ ] **5C.6** `[S]` Treat uploaded scenario text as untrusted evidence inside both question and
  judge prompts. Delimit it, restate instruction hierarchy, and prohibit document instructions from
  altering the rubric, score range, output schema, or question count (coordinate with 6.1).
- [ ] **5C.7** `[M]` Define a separate structured question-generation contract containing the fixed
  ordinal/lens, question text, and references into the immutable evaluation context. Validate its
  timeout/retry/fallback behavior independently from judging.
- [ ] **5C.8** `[M]` Define a structured final-remarks contract: band-consistent summary, strengths,
  recurring gaps, and priority improvement with judgment references. Retry once on invalid output;
  on failure, persist a deterministic template assembled from stored judgments rather than blocking
  or changing the final numeric result.

**Exit criteria:** a live integration probe returns schema-valid questions, judgments, and final
remarks for representative good, partial, irrelevant, explicit-refusal, and prompt-injection
answers; blank/whitespace input is rejected before judging, and model failures are explicit/retryable.

### Phase 5D — Question generation and grading engine

- [ ] **5D.1** `[M]` Add `backend/assessment_engine.py` as the single deep module that owns the
  five-lens blueprint, prompt construction, judgment validation, score aggregation, preparedness
  band mapping, and final-remarks generation. Keep HTTP and SQLite details outside this module.
- [ ] **5D.2** `[M]` Build one question at a time from the fixed ordinal/lens plus current wing
  mandate, scenario, authoritative phase, current relevant injects, and prior assessed answers.
  Require one concise command-level question, no answer leakage, no future injects, and no repeated
  semantic lens.
- [ ] **5D.3** `[S]` Validate generated questions before persistence: exactly one question, correct
  lens, wing relevance, supported scenario facts, no specialist-method quiz unless required by the
  current inject, and no near-duplicate of prior questions. Retry once, then use a reviewed
  deterministic lens-specific fallback question.
- [ ] **5D.4** `[M]` Build the judge prompt around the exact persisted question and participant
  answer. Include only evidence available when the question was asked; do not grade against future
  phases, later participant messages, assistant suggestions, or hidden chain-of-thought.
- [ ] **5D.5** `[M]` Generate concise score feedback after each valid judgment without exposing the
  full rubric or a model reasoning trace. Feedback must explain the score through observed strength
  and one highest-value gap rather than prescribe a complete answer; store it immediately but do not
  reveal it until the assessment is complete.
- [ ] **5D.6** `[S]` Compute final score and band in Python after five valid judgments. Generate final
  remarks from normalized stored strengths/gaps/evidence, validate that remarks agree with the
  deterministic score/band, and persist once.
- [ ] **5D.7** `[M]` Build a small adversarial fixture set: polished but vague answers, long answers
  with one correct point, irrelevant technical detail, copied moderator text, contradictions,
  explicit refusal, whitespace-only validation, Urdu/English code-switching, and prompt injection.

**Exit criteria:** deterministic unit tests prove ordinal-to-lens coverage, no sixth question, score
math/bands, evidence isolation, finalization only after five judgments, and stable failure handling.

### Phase 5E — Server-authoritative workflow and endpoints

- [ ] **5E.1** `[M]` Add idempotent `POST /api/assessments/{wing_id}/start`. Resolve the active
  exercise and canonical wing, create/load its assessment, generate question one only when absent,
  and return current progress. Selecting a wing may safely call this endpoint repeatedly.
- [ ] **5E.2** `[M]` Add `GET /api/assessments` for all-wing summaries and
  `GET /api/assessments/{wing_id}` for complete restoration: status, answered count, current
  question, prior answer scores/feedback, average-so-far, and final result.
- [ ] **5E.3** `[L]` Add `POST /api/assessments/{wing_id}/answers`. Validate the stable question id,
  current ordinal/version, non-empty answer, exercise/wing ownership, and idempotency key; persist
  the answer, judge it, and generate the next question or final result. Before question five, return
  acceptance/progress and the next question without disclosing score or feedback.
- [ ] **5E.4** `[M]` Use explicit state transitions:
  `not_started -> generating_question -> awaiting_answer -> scoring -> awaiting_answer|finalizing -> complete`,
  with `generation_failed`/`scoring_failed` retry states. Never hold a SQLite transaction open
  during an LLM network call; reserve state transactionally before the call and complete it with a
  compare-and-set afterward.
- [ ] **5E.5** `[S]` Reject a sixth scored answer with a typed conflict while preserving ordinary
  unscored chat. Do not infer completion from `?` characters or transcript adjacency.
- [ ] **5E.6** `[M]` Add controller-only retry and reset endpoints. Retry reuses the same question
  and answer; reset archives the previous immutable attempt, creates the next attempt number, and
  records the actor/reason. `/api/phase/reset` must not call this path.
- [ ] **5E.7** `[S]` Enforce the 5A.7 permission matrix on every assessment route before frontend
  integration. Return `403` without revealing whether another wing has started or completed.
- [ ] **5E.8** `[S]` Add optional controller phase-advance warnings listing incomplete wings, based
  on persisted assessment summaries. Enforcement, if later required, belongs in the backend route.
- [ ] **5E.9** `[M]` Add bounded judge/question-generation concurrency and backpressure for the
  shared LM Studio instance. Prefer `202 Accepted` plus pollable persisted states when end-to-end
  scoring exceeds the agreed synchronous latency budget; define timeout/cancellation/recovery and
  load-test all canonical wings submitting concurrently.

**Exit criteria:** API tests can start, answer, reload, switch sessions, finish, and restore every
wing; duplicate/stale/concurrent requests cannot create extra questions, scores, or final remarks.

### Phase 5F — Frontend assessment experience

- [ ] **5F.1** `[M]` Add `assessmentByWing` state loaded from `GET /api/assessments` during startup.
  Store per-wing status, current question, scores, version, request token, submitting/error state,
  and final result; never use local storage or count chat bubbles for progress.
- [ ] **5F.2** `[S]` Render an accessible `0/5` through `5/5` progress badge on every wing and
  `Question N of 5` in the active-wing header. Use text and semantics, not color alone.
- [ ] **5F.3** `[M]` Render distinct assessment question, submitted answer, score feedback, and final
  preparedness cards in the chat stream from assessment APIs, not transcript inference. Keep score
  feedback hidden during questions 1-5; after completion, reveal per-answer scores/feedback and a
  final card with `N.N/10`, band, demonstrated strengths, recurring gaps, and priority improvement.
- [ ] **5F.4** `[M]` Route the input to the dedicated answer endpoint only while an assessment is
  `awaiting_answer`. Disable duplicate submission while scoring, preserve text on recoverable failure,
  and announce progress/errors through `role=status`/`role=alert`.
- [ ] **5F.5** `[S]` Make requests wing-scoped. Switching wings while generation/scoring is pending
  must not move a typing indicator, score, TTS playback, or error into the newly selected wing; use
  per-wing request versions like the existing inject request guard.
- [ ] **5F.6** `[S]` Stop sending synthetic `"hello"` and phase notices as participant answers.
  Start assessment through its explicit endpoint and label any retained chat control messages with
  their message kind.
- [ ] **5F.7** `[S]` Add clear complete and retry states. After completion, lock scored submission,
  preserve review/TTS access, and expose ordinary chat only as an explicit unscored action.
- [ ] **5F.8** `[M]` Harden responsive and accessible behavior: native wing buttons, input label tied
  to the current question, keyboard-only flow, focus restoration, numeric score text, long-remarks
  wrapping, `prefers-reduced-motion`, and layouts at 320/375/768/1440px.

**Exit criteria:** a participant can complete and revisit all five questions using keyboard only;
reload and rapid wing switching preserve the correct progress, cards, focus, and request ownership.

### Phase 5G — Controller overview and reporting

- [ ] **5G.1** `[M]` Extend the controller view with all-wing progress: not started/in progress/
  failed/complete, answered count, average-so-far, final score, and preparedness band.
- [ ] **5G.2** `[S]` Show incomplete/failed wings before phase advance and scenario replacement,
  with links that open the relevant wing assessment; warnings must not expose one wing's answer text
  to unauthorized participant sessions once roles are enforced.
- [ ] **5G.3** `[M]` Feed completed assessment records into the after-action report planned in 5.5:
  score table, rubric version, five answer judgments, evidence, recurring gaps, and final remarks.
- [ ] **5G.4** `[S]` Export machine-readable JSON first; add Markdown/PDF only after the persisted
  report contract is stable. Include exercise/scenario ids and generation timestamp.

**Exit criteria:** controller totals reconcile exactly with persisted completed assessments and a
reloaded/exported report shows the same scores, bands, and remarks as each wing view.

### Phase 5H — Quality evaluation, security, and observability

- [ ] **5H.1** `[L]` Create a reviewed golden set of wing/question/answer examples with acceptable
  score ranges and expected gaps. Measure exact schema validity, mean absolute score deviation,
  band agreement, evidence grounding, and repeated-run variance before changing prompts/models.
  MVP release gate: at least 90 adjudicated examples (at least 10 per current wing, covering low/
  medium/high anchors), >=99% schema validity, mean absolute error <=1.0, >=85% band agreement,
  >=95% grounded evidence, and <=1-point spread across three runs for >=90% of examples.
- [ ] **5H.2** `[M]` Run fairness/calibration review across all canonical wings. Ensure verbose or
  technical answers are not rewarded merely for length and specialized wings are judged against
  their own mandate and question lens rather than a generic operations template.
- [ ] **5H.3** `[M]` Add prompt-injection and data-boundary tests for malicious answers and uploaded
  scenarios. Participant text cannot change the rubric, request a score, forge JSON, reveal future
  injects, or cause cross-wing evidence leakage.
- [ ] **5H.4** `[S]` Emit structured events for question generation, scoring attempt, schema failure,
  retry, finalization, reset, and export. Record latency, model/prompt/rubric version, token usage,
  score, and error category without logging hidden reasoning or unnecessary participant PII.
- [ ] **5H.5** `[S]` Add metrics/alerts for judge availability, invalid-output rate, p50/p95 scoring
  latency, retry rate, duplicate conflicts, completion rate, and score distribution by wing.
- [ ] **5H.6** `[S]` Enforce authorization and rate limits on start/answer/retry/reset/result routes;
  regression-test the 5A.7 permission matrix and coordinate broader authentication/rate-limit work
  with 6.5 and 6.7 before deployment beyond the trusted LAN.

**Exit criteria:** the candidate judge meets the 5H.1 calibration/grounding thresholds, adversarial
cases cannot alter workflow state, and operators can distinguish model failure from participant or
network failure using traces and metrics.

### Phase 5I — End-to-end verification and rollout

- [ ] **5I.1** `[M]` Add backend workflow tests covering start, all five ordinals, valid `0` and
  `10`, invalid score output, judge timeout/retry, sixth-answer rejection, wing/session isolation,
  reload, phase changes, final arithmetic/bands, reset semantics, and new-scenario isolation.
- [ ] **5I.2** `[M]` Add concurrency tests for duplicate start, duplicate answer, simultaneous fifth
  answers, retry racing with reload, and two sessions representing the same wing.
- [ ] **5I.3** `[M]` Add Playwright end-to-end coverage for completion, reload after question two,
  wing switch while scoring, recoverable API failure, final-result restoration, keyboard navigation,
  screen-reader status text, and mobile layouts.
- [ ] **5I.4** `[S]` Add a feature flag with three modes: `off`, `evaluation`, and `on`.
  `evaluation` runs the real five-question workflow in test/facilitator sessions but withholds all
  AI scores from participants and stores records in normal versioned attempts; it never tries to
  infer five rubric lenses from arbitrary legacy chat.
- [ ] **5I.5** `[M]` Run evaluation mode on facilitator-reviewed attempts, compare AI and human
  scores against the 5H.1 gates, tune rubric anchors rather than ad hoc score offsets, and obtain
  product/domain sign-off.
- [ ] **5I.6** `[S]` Roll out to one exercise first with database backup and rollback instructions.
  Rollback disables new assessment starts but preserves completed records and exports.
- [ ] **5I.7** `[S]` Update `README.md`, `.env.example`, operator runbook, API documentation, and
  facilitator guidance explaining that the score supports training discussion and is not an
  authoritative personnel-performance decision.

**Definition of done:** every wing can complete exactly five persisted, scenario-grounded questions;
every answer has one validated `0..10` judgment with evidence; the fifth judgment deterministically
produces a restorable final score, band, and remarks; no greeting, phase notice, retry, reload,
concurrent request, or general chat can create a sixth scored answer or contaminate another wing.

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
