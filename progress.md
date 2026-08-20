# SimEx AI — Session Handoff

**Last updated:** 2026-08-20
**Branch:** `feature/lmstudio-migration` → PR [#2](https://github.com/imtiazNDMA/SimExAI/pull/2) (targets `RAG`, not `main`)
**Status:** 10 commits, pushed, 5 tests passing, nothing merged yet.

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
| 1 — Sessions and persistence | **3/6** | Schema landed; **app.py not yet wired** |
| 2 — Conversation memory | 0/4 | Blocked on Phase 1 |
| 3 — Correctness fixes | 2/11 | 3.6, 3.8 done |
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

**Upload progress overlay** (`27df5ab`). `POST /api/scenario/upload` now returns `202` with
a `job_id`; `GET /api/scenario/upload/{job_id}` reports real stage and chunk progress.
Full-screen overlay replaces the old `alert()`. Word `.doc` rejection and no-Word
text-only fallback.

---

## 3. Immediate next step

**Phase 1, tasks 1.3–1.5** — wire `backend/app.py` to the session schema. This is what
actually closes P0-5 (global mutable state); the tables alone change nothing.

1. **1.3** Delete the module-level singletons at `backend/app.py:47-48`
   (`scenario = ScenarioEngine()`, `responder = LLMEngine(scenario)`). Resolve per-session
   state instead.
2. **1.4** Thread a session id through every route and the frontend. Agreed approach:
   `localStorage` on the client, sent as an `X-Session-Id` header, created on first load.
3. **1.5** Gate controller-only actions: `phase/advance`, `phase/back`, `phase/reset`,
   `scenario/upload`. Today any participant can reset everyone's exercise.

Then **Phase 2** (conversation memory) — the single largest quality jump available, and
unblocked the moment sessions exist.

### Design decisions already made (do not re-litigate)

- **The phase lives on `exercises`, not `sessions`.** A SimEx is a shared timeline: all ten
  wings sit at D-90 together and only the Controller advances it. `todos.md` 1.1 originally
  said otherwise; the schema supersedes it.
- **First session on an exercise claims `role='controller'`.** No credentials — real auth
  is task 6.5, which can layer onto the same `role` column.
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
migrates the **real** `data/simex.db`. It is empty and the migration is additive, so no harm
so far — but `tests/conftest.py` should redirect `database.DB_PATH` before import. Not yet
written.

**Tests were deleted by accident, not by choice.** Commit `c198a2e` ("fix: ensure perfectly
synchronized TTS highlighting") removed 243 lines of test coverage as collateral. Restored
from `main` in `0e40bda`.

**`en_core_web_sm` is an undeclared runtime dependency.** `uv sync` strips it; Kokoro TTS
then silently re-downloads it over the network on the first TTS call. Works here, fails in
an air-gapped deployment. Logged as `todos.md` 8.1c.

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

.venv/Scripts/python.exe -m pytest tests/ -q     # 5 tests, ~5s
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
2. **`docs/test cases/`** is untracked and not mine — leave, commit, or ignore?
3. **Phase 1 wiring changes the API contract** (session id required on every route). The
   frontend must change with it — worth confirming before starting 1.4.
