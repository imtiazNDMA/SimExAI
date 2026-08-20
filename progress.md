# SimEx AI — Session Handoff

**Last updated:** 2026-08-20
**Branch:** `feature/lmstudio-migration` → PR [#2](https://github.com/imtiazNDMA/SimExAI/pull/2) (targets `RAG`, not `main`)
**Status:** Phase 1 + 2 complete and verified (16 tests passing, browser-verified transcript restore).

This file is the entry point for a new session in any tool (Claude Code, opencode, etc.).
It records **what is true now** and **what is not obvious from the code**. It deliberately
does not restate content that already lives elsewhere:

| For | Read |
|---|---|
| Why the architecture is the way it is | [`review.md`](./review.md) — 25 findings, 8 P0 / 10 P1 / 7 P2 |
| What to do next, in dependency order | [`todos.md`](./todos.md) — 9 phases |
| What changed and why | `git log RAG..HEAD` — the commit bodies carry the reasoning |
| Repo conventions for agents | [`CLAUDE.md`](./CLAUDE.md), [`docs/agents/`](./docs/agents/) |

---

## 1. The one-paragraph situation

SimEx AI is an AI-moderated disaster simulation exercise chatbot for NDMA Pakistan. A
controller uploads a scenario document; participants representing NDMA wings chat with an
AI "Lead Moderator" that is supposed to challenge and evaluate them. **It currently does
not evaluate anyone** — the system is a stateless prompt proxy with one retrieval call
attached: no conversation memory, no scoring, no agent loop, and a RAG pipeline that
indexes the model's own summary rather than the uploaded document. `review.md` documents
this in detail. The work in flight is turning it into an actual agentic product, phase by
phase.

---

## 2. Progress by phase

| Phase | Done | Notes |
|---|---|---|
| 0 — Enabling infrastructure | **6/6 ✅** | Ollama → LM Studio, launcher |
| 1 — Sessions and persistence | **6/6 ✅** | Schema + full route wiring; first session = controller |
| 2 — Conversation memory | **4/4 ✅** | History persisted + windowed, transcript restore, inject ledger |
| 3 — Correctness fixes | 4/11 | 3.1, 3.5, 3.6, 3.8 done |
| 4 — RAG rebuild | 0/9 | The reranker work |
| 5 — The agent loop | 0/6 | Tool calling verified as viable |
| 6 — Safety and guardrails | 0/7 | |
| 7 — UX and streaming | 0/5 | Upload UX done ahead of schedule |
| 8 — Testing and observability | 1/9 | 8.1a done |

### What actually shipped

**LLM provider migrated** (`e4828a3`). `langchain-ollama` → `langchain-openai` against LM
Studio's OpenAI-compatible API. `backend/ollama_engine.py` → `backend/llm_engine.py`,
`OllamaEngine` → `LLMEngine`. `OLLAMA_*` env vars → `LMSTUDIO_*`.

**One-command launcher** (`179ffb5`, `e3fce67`). `start.bat` → `start.ps1`. Preflight:
`uv` present, `.env` present (bootstraps from `.env.example` and stops), `uv sync`, LLM
server reachable, port free. Then uvicorn, then opens the browser once it answers.
Default port **9897**.

**Tests restored** (`0e40bda`). See §4 — they had been deleted by accident.

**Session schema** (`78bc41a`). New tables `exercises`, `sessions`, `messages`,
`inject_state`, `assessments`; the missing `injects.status` column; `get_connection` now
closes; `PRAGMA foreign_keys=ON`; WAL; indexes. **Additive and currently inert** — no
route reads or writes any of it yet.

**Session wiring — Phase 1.3–1.5 complete.** Module-level `scenario`/`responder`
singletons (`app.py:47-48` in the old layout) are gone. Every route now resolves a
per-request `SessionContext` (session → exercise → fresh `ScenarioEngine` +
`LLMEngine`) from `X-Session-Id`. `POST /api/session` bootstraps a browser
localStorage UUID: the first active session on an exercise claims `role='controller'`;
later sessions are participants. Controller-only actions (`upload`, `advance`, `back`,
`reset`) return `403` for participants. The shared timeline now lives on `exercises`
and is mutated with bounded, persistent SQL transitions (`change_exercise_phase`,
`reset_exercise_phase`). Upload jobs carry their originating `session_id`/`exercise_id`
and are visible only to the owner. Chat phase is server-authoritative — clients no
longer submit `phase_id` (also closes 3.5), and the extraction prompt's `{{wing_ids}}`
brace bug is fixed (3.1). Participants are bound to their first wing; controllers may
switch wings to facilitate. The frontend polls `/api/phases` every 5s (and on tab
focus) so participant timelines follow controller advances without reload.

**Upload progress overlay** (`27df5ab`). `POST /api/scenario/upload` now returns `202` with
a `job_id`; `GET /api/scenario/upload/{job_id}` reports real stage and chunk progress.
Full-screen overlay replaces the old `alert()`. Word `.doc` rejection and no-Word
text-only fallback.

**Test scaffolding.** `tests/conftest.py` redirects `SIMEX_DB_PATH` before app import so
tests never touch `data/simex.db`. 12 tests pass, including the full route-header matrix,
first-controller/participant bootstrap, shared-phase persistence, participant wing
binding, upload-job ownership, and server-authoritative chat phase.

**Conversation memory — Phase 2 complete.** Every turn is persisted to `messages`
(now carrying `wing_id` via schema migration) and the chat route loads the wing's history
and passes it into `get_response` as `[system, ...history, user]`. History windowing:
the last 12 turns verbatim plus a deterministic condensed block for older turns
(200 chars/turn; a real LLM summarizer is deferred — see §8). `GET /api/session/messages`
restores the transcript on page load; browser-verified that a message survives a reload
without a duplicate greeting (the greeting itself now renders as a user bubble so the live
view matches the restored one). The inject ledger is built per chat — injects for the
current phase are marked `delivered`, ones whose title appears in the user message marked
`addressed`, and the formatted ledger is injected into the prompt so resolved items stop
being re-raised. 16 tests pass, including 4 HTTP-contract tests covering persistence,
windowing, transcript restore, and the ledger. The Phase 1 `FakeResponder` and the
`RecordingLLM` fake both exercise the real route seam.

---

## 3. Immediate next step

**Phase 3 (correctness fixes)** — Phase 2 is done. 3.2, 3.3, 3.4, 3.7, 3.9, 3.10, 3.11
remain. **3.4** (`required_wings` filtering) pairs naturally with **3.3** (mandate-ranked
inject selection) and both sharpen what Phase 5.4 needs. Do these while Phase 4 (RAG
rebuild) is being designed; Phase 8.1b (unit coverage of `ScenarioEngine`, DB layer) can
ride along.

### Design decisions already made (do not re-litigate)

- **The phase lives on `exercises`, not `sessions`.** A SimEx is a shared timeline: all ten
  wings sit at D-90 together and only the Controller advances it. `todos.md` 1.1 originally
  said otherwise; the schema supersedes it.
- **First active session on an exercise claims `role='controller'`.** No credentials — real
  auth is task 6.5, which can layer onto the same `role` column.
- **PR #2 targets `RAG`, not `main`**, matching the existing PR #1.

---

## 4. Non-obvious things that will bite you

These cost real time to discover. None are visible from reading the code.

**The model is a reasoning model.** `google/gemma-4-26b-a4b` spends **100–1700 tokens on
internal reasoning** before emitting any visible answer, and `max_tokens` covers both. A
budget set too low returns an **empty** response, not a short one — measured directly:
`max_tokens=10` yields `content: ''` with `finish_reason: length`. Budgets are now 3000
(chat) / 16000 (extraction @ `temperature=0`). Reasoning arrives in a separate
`reasoning_content` field, not inline `<think>` tags, so output is clean.

**Verified capabilities** (probed against the live server, so Phase 5 is not a gamble):
tool calling works (`finish_reason: tool_calls`, valid JSON args); vision works (exact OCR
through LangChain's async path with the same `image_url` shape the upload pipeline builds).

**`backend/app.py:28` calls `init_db()` at import time.** Importing `backend.app` in a test
migrates the **real** `data/simex.db`. `tests/conftest.py` now sets `SIMEX_DB_PATH` to a
temp database before the app is imported, so tests never touch the real one. The
`SIMEX_DB_PATH` override applies to `database.DB_PATH` — the env var replaces the whole
path, not just the filename.

**Every API route now requires `X-Session-Id`.** `POST /api/session` is the only
create-if-unknown endpoint; every other route returns `400` without a header and `404`
for an unknown session. The frontend stores a UUID in `localStorage`
(`simexai-session-id`); a fresh browser profile or cleared storage creates a new
participant session. Two tabs in the same browser share one session and one role.

**Sessions are never auto-expired.** `last_seen_at` is written but not yet read; a dead
controller browser keeps the role until its session row is marked `status='inactive'`
manually (the frontend then rotates its UUID after a `409`). Real auth (6.5) supersedes
this. The `SessionContext`/`LLMEngine` are rebuilt per request, so a restart or a
controller phase change is always seen by the next request — no per-session cache to
invalidate.

**Tests were deleted by accident, not by choice.** Commit `c198a2e` ("fix: ensure perfectly
synchronized TTS highlighting") removed 243 lines of test coverage as collateral. Restored
from `main` in `0e40bda`.

**`en_core_web_sm` is an undeclared runtime dependency.** `uv sync` strips it; Kokoro TTS
then silently re-downloads it over the network on the first TTS call. Works here, fails in
an air-gapped deployment. Logged as `todos.md` 8.1c.

**Each LLM chat turn takes ~10s** (reasoning overhead on this model). Browser tests must
wait for the **typing indicator to appear and disappear** rather than counting reply
bubbles — the typing indicator is itself a `.message.system` bubble, so bubble counts
can look correct while a reply is still generating (and before it is persisted). Reloading
mid-generation drops the in-flight assistant turn from the restored transcript.

**History windowing is deterministic, not a real summary.** 2.2 stores no per-session
summary yet: older turns are condensed into one system block at 200 chars/turn on every
chat. Cheap and stable, but it does not meet the "stored running summary" intent — the
checklist carries an explicit follow-up.

**The greeting now renders as a user bubble.** `sendGreeting` was persisting its user
message server-side without showing it in the live transcript, so a reload made one extra
bubble appear. It now calls `addMessage(wingId, 'user', ...)` to match the restored view.

**`--reload` orphans workers.** Force-killing uvicorn leaves a `multiprocessing-fork` child
holding the port, and the socket table still names the dead parent. Kill children first,
then sweep by command line. Ctrl+C is fine.

**Silent failures are real, not theoretical** (review P1-7). A Pinecone cleanup printed
"deleted namespace" while actually failing on DNS, because the exception was swallowed.
When verifying anything that touches Pinecone, surface the exception rather than trusting
the log line.

**Network in this environment drops intermittently.** `git push` and Pinecone calls have
both failed with `Could not resolve host` and succeeded on retry. Retry once before
diagnosing.

**`.agents/` (plural) is a broken skills install** — 53 of 67 `.md` files are 3-byte
BOM-only stubs, and it carries a `settings.local.json` with paths from unrelated projects.
It is gitignored. Do not source anything from it. The real repo skills are in `.agent/`
(singular).

---

## 5. Running it

```bash
start.bat                 # preflight + uvicorn + browser, port 9897
start.bat -Port 8080      # different port
start.bat -NoSync         # skip uv sync, fast restart
start.bat -NoBrowser      # no browser

.venv/Scripts/python.exe -m pytest tests/ -q     # 16 tests, ~4s
```

**Prerequisites:** LM Studio running with an OpenAI-compatible server at
`http://localhost:1234/v1` and `google/gemma-4-26b-a4b` loaded. `.env` needs
`PINECONE_API_KEY` (RAG silently disables without it — review P1-7).

Config lives in `.env`; the shape is documented in `.env.example`. **Never commit `.env`
or `.env.bak*`** — they hold live keys and are gitignored.

---

## 6. Verification standard

Every change so far has been checked against the running system, not asserted from the
diff. Keep that bar:

- The migration was verified with a real chat call, a real multimodal call, and a full
  `POST /api/chat` round trip — not an import check.
- The schema migration was tested against a **copy** of the real database first.
- The restored test was **mutation-checked**: breaking image attachment makes it fail
  (`[0,0] != [1,1]`), proving it detects the regression it claims to cover.
- The upload overlay was driven in a real browser in both themes. The first pass hardcoded
  three dark-only colors and looked broken in light mode — screenshots caught it.

Testing against the live server writes into the **real** `data/simex.db` and Pinecone.
Clean up after yourself; the user's own scenario ("Cyclone Neer 2025 Simulation",
18 injects) must survive.

---

## 7. Suggested skills for the next session

Tool-agnostic — use the nearest equivalent if your harness names them differently.

| When | Skill |
|---|---|
| Before any Phase 1–5 implementation | `brainstorming` — these are architectural, not bounded |
| Writing Phase 1/2 code | `test-driven-development` — the safety net now exists; use it |
| Executing `todos.md` phases | `executing-plans` |
| Any bug or unexpected behaviour | `systematic-debugging` |
| Before claiming anything works | `verification-before-completion` — see §6 |
| Frontend/UI work | `frontend-design` — match the existing tokens in `frontend/style.css` |
| Before merging | `requesting-code-review`, `finishing-a-development-branch` |

---

## 8. Open questions for the user

1. **Merge PR #1?** It adds a competing pure-batch `start.bat` and will conflict with this
   branch. A note was left on it; closing is the user's call.
2. **Session expiry / controller handoff.** Sessions are never auto-expired, so a dead
   controller keeps the role until its row is manually marked `inactive`. Worth a policy:
   stale `last_seen_at` threshold, explicit "end session" action, or defer to real auth
   (6.5).
3. **Reset semantics changed.** `POST /api/phase/reset` now resets the timeline to D-90
   while preserving the uploaded scenario (previously it also cleared the scenario).
   The confirm dialog text was updated to match.
4. **2.2 summary is deterministic, not stored.** Older turns are condensed at 200
   chars/turn per chat; no per-session LLM summary is persisted yet. Worth a follow-up
   before Phase 4's query-rewrite task (4.6) leans on it.
