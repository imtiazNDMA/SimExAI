# SimEx AI — Conversational Voice Architecture

**Status:** Phase 1 gate PASSED — Phase 2 cleared pending the build-vs-adopt decision (1.5)
**Author:** Engineering · **Date:** 2026-08-21 · **Last measured:** 2026-08-21
**Branch:** `feature/lmstudio-migration`

Companion to [`review.md`](./review.md) and [`todos.md`](./todos.md). This document covers **one
goal**: turning SimEx AI from a text chat app with voice bolted on into a full-duplex,
interruptible voice agent on a free/open, fully local stack.

**Legend:** `[S]` hours · `[M]` 1–3 days · `[L]` ~1 week+

---

## 1. Measured baseline

All numbers below were measured on the actual deployment box on 2026-08-21 via
`scripts/voice_latency_probe.py`, `scripts/stt_latency_probe.py`, and
`scripts/voice_e2e_probe.py`. **Nothing here is estimated.** Methodology notes are in §1.5,
because several measurements were wrong on the first attempt and the corrections changed the
conclusion each time.

### 1.1 Hardware and runtime

| Property | Value |
|---|---|
| GPU | NVIDIA RTX 6000 Ada Generation, 48 GB VRAM (~22 GB free with LM Studio resident) |
| LM Studio | GPU-resident (~24.7 GB with a 26B loaded), ~14–15% util during single-stream decode |
| `torch` in `.venv` | `2.12.1+cpu` — CUDA not available, so Kokoro runs on CPU |
| `faster-whisper` / `ctranslate2` | `1.2.1` / `4.8.1` — **GPU-capable independently of torch** (§1.7) |
| CUDA toolkit | 13.0 installed; ctranslate2 needs CUDA **12** libs — see §1.7 |
| Models available | `nemotron-3-nano`, `gemma-4-26b-a4b`, `qwen3.8-27b`, `glm-4.7-flash` |

### 1.2 The dominant finding: a 2-second transport tax

`GET /v1/models` is a static endpoint that performs no inference. It took **2.04s**.

| Base URL | `GET /models` median |
|---|---|
| `http://localhost:1234/v1` | **2.058s** |
| `http://127.0.0.1:1234/v1` | **0.010s** |

A 200× difference. This is the Windows IPv6 `::1` connect stall: `localhost` resolves to `::1`
first, stalls, then falls back to `127.0.0.1`. The penalty is paid **on every new TCP
connection**, and `ChatOpenAI` is not configured to reuse one.

`.env.example:15` ships `LMSTUDIO_BASE_URL=http://localhost:1234/v1`. **Every LLM call in SimEx
AI — chat, upload extraction, rewrite — currently pays ~2.05s of pure transport tax.** This also
explains the "reasoning models are slow" framing in `todos.md` Phase 0: a large part of what was
attributed to inference was TCP.

### 1.3 LLM latency, measured over `127.0.0.1`

Warm (2 discarded warmups), single model resident, median of 4+ runs:

| Model | 1st token | **1st visible token** | Total | Thinking |
|---|---|---|---|---|
| `nvidia/nemotron-3-nano` | 0.11s | **0.42s** | 0.46s | ~304 chars |
| `google/gemma-4-26b-a4b` (current) | 0.16s | **1.80s** | 1.84s | ~1103 chars |

Both models begin emitting within ~0.15s. The difference is entirely **thinking dead air** —
gemma spends ~1.64s producing reasoning tokens the user cannot hear. For voice, thinking time is
indistinguishable from silence.

Decode itself is fast: 40 tokens cost ~0.2s (≈5ms/token). **Inference was never the problem.**

### 1.4 Kokoro TTS, measured on CPU

| Input | Segments yielded | Time to 1st segment | Full synth | Audio length | RTF |
|---|---|---|---|---|---|
| 4 words | 1 | **0.32s** | 0.32s | 2.30s | 0.14 |
| 1 sentence | 1 | 0.42s | 0.42s | 4.47s | 0.09 |
| 3 sentences | 1 | 0.63s | 0.63s | 9.97s | 0.06 |
| long paragraph | 2 | 1.52s | 2.01s | 35.60s | 0.06 |

Two conclusions:

1. **Kokoro is fast enough, even on CPU** — *provided torch keeps its threads*. RTF 0.06–0.14
   means synthesis runs 7–16× faster than real time. Moving `torch` to CUDA is an optimization,
   not a prerequisite. But see §1.8: loading faster-whisper silently clamps torch to 4 threads
   and makes these numbers 3.5× worse.
2. **KPipeline does *not* chunk at sentence boundaries.** It yielded a single segment for
   everything up to ~10s of audio, only splitting at ~35s. An earlier assumption that we could
   simply consume its generator for streaming was **wrong** — we must chunk at the sentence
   level ourselves before calling it. This is a real work item, not a free win.

### 1.5 Methodology corrections

Recording these because they invalidate naive re-measurement:

- **LM Studio JIT-loads and evicts models.** Probing four models in a loop measured model
  *loading*, not inference (VRAM observed swinging 29.5 GB → 1.5 GB → 24.7 GB mid-run). Every
  measurement must discard warmups and hold one model resident.
- **`localhost` vs `127.0.0.1`** — see §1.2. Any probe using `localhost` overstates latency by
  ~2s per connection and hides the real distribution.
- **Kokoro's CPU speed depends on a torch setting another library mutates.** See §1.8 — any
  benchmark that loads faster-whisper first measures a 3.5× slower Kokoro.

### 1.6 Budget: today vs. measured

**Today** (gemma + `localhost`, whole-utterance TTS, nothing overlapped):

```
connect tax          2.05s
first visible token  1.80s   (incl. 1.64s thinking dead air)
finish generation    0.05s
full TTS synthesis   ~0.45s
─────────────────────────────
time to first audio  ≈ 4.35s     ← plus push-to-talk, no interruption possible
```

**Measured** — `scripts/voice_e2e_probe.py`, the real components chained end to end
(faster-whisper on GPU → LM Studio streaming over `127.0.0.1` → Kokoro first clause), 5 runs,
all stages warm:

Three independent invocations of the probe (5 runs each), reported as a range because
LM Studio's first-token latency varies run to run:

| Stage | Cumulative median | Cumulative p95 |
|---|---|---|
| 1. STT transcribe (11.8s of audio) | 0.077–0.078s | 0.077–0.078s |
| 2. + LLM first visible token | 0.494–0.695s | 0.642–0.710s |
| 3. + first clause complete | 0.495–0.710s | 0.643–0.710s |
| 4. + Kokoro first audio | **0.722–0.931s** | **0.860–0.934s** |

**Plan against the worst observed figure, ~0.93s, not the best.** Essentially all the spread is
stage 2 — LM Studio's time to first visible token ranged 0.42s to 0.62s across invocations. STT
and Kokoro were stable to within a millisecond.

Add the VAD endpointing threshold (~0.5s, tunable) plus browser transit and jitter buffer for
the figure a participant perceives: **≈1.4s worst case**. Commercial voice modes land around
0.8–1.5s, so this is competitive on hardware already in the building — but the margin is
thinner than the best-case number suggests.

**The Phase 1.2 gate passes** on every sample. The architecture in §3 stands as written; Phase 2
can start.

Two caveats. These are **server-side only** — they exclude network transit, jitter buffer depth,
and the endpointing threshold. And they are **single-session**; concurrency is unmeasured and
remains the open risk (Phase 6.1).

### 1.7 STT: measured, and the GPU is mandatory

`distil-small.en` and `small.en`, beam size 1, median of 5 warm runs
(`scripts/stt_latency_probe.py`):

| Model | Device | 3.1s audio | 11.8s | 25.2s | WER |
|---|---|---|---|---|---|
| `distil-small.en` | **CUDA** | **0.090s** | 0.135s | 0.226s | 0% / 0% / 14.8% |
| `small.en` | **CUDA** | **0.120s** | 0.218s | 0.408s | 0% / 0% / 13.1% |
| `distil-small.en` | CPU (int8) | 1.038s | 1.110s | 1.277s | — |
| `small.en` | CPU (int8) | 1.492s | 1.734s | 2.193s | — |

**CPU fails the 0.5s gate by 2–3×; GPU passes it by 5×.** GPU is a requirement, not an
optimization.

Three findings that change the plan:

1. **ctranslate2 brings its own CUDA runtime.** `get_cuda_device_count()` returns 1 and
   `float16` is supported despite `torch` being CPU-only. **Phase 1.4 was based on a false
   premise** — we do not need to touch the torch install to get GPU STT.
2. **But it links against CUDA 12, and this box has CUDA 13.** ctranslate2 bundles
   `cudnn64_9.dll` and *not* cuBLAS, so `nvidia-cublas-cu12` (553 MB) is required. Nothing else
   from the `nvidia-*-cu12` family is needed — `nvidia-cudnn-cu12` is redundant here.
3. **Windows will not find that DLL without help.** Python 3.8+ ignores `PATH` for extension
   DLLs, and a CUDA torch build would normally register the directory. With torch CPU-only,
   nothing does, and ctranslate2 fails with *"Library cublas64_12.dll is not found"* even once
   installed. `os.add_dll_directory()` alone is **not** sufficient — ctranslate2 resolves cuBLAS
   through its own `LoadLibrary` call, which searches `PATH`. Both are required; see
   `register_cuda_dlls()` in `scripts/stt_latency_probe.py`.

**Latency is ~93% fixed cost, not proportional to audio.** On CPU, 0.5s of audio costs 0.830s
and 11.8s costs 0.935s — 23× the audio for 13% more time. Whisper pads the mel spectrogram to a
30-second window regardless of content; encoding the *actual* 313 mel frames of a 3.1s clip
takes 0.060s against 0.967s for the padded transcribe. **Design consequence:** streaming partial
transcription would pay the full fixed price on every partial. Transcribe-once-at-endpoint
(Phase 2.6) is correct, and this is now measured rather than assumed.

**Silero VAD is effectively free** and ships bundled with faster-whisper via `onnxruntime` —
**0.044ms per 32ms frame**, 0.14% of the real-time budget. No separate dependency (Phase 1.3).

**WER caveat.** Those rates are against Kokoro-synthesized speech: clean, unaccented,
noise-free. **0% is a floor, not a forecast** — real Pakistani-English participant audio over a
headset will be worse. The 13–15% on the long clip is almost entirely number formatting
("zero six hundred hours" → "0,600 hours"), which matters for a disaster-response transcript.
`small.en` is both more accurate on the long clip and still only 0.120s for a typical turn;
prefer it as the default and treat `distil-small.en` as the speed option.

### 1.8 The integration bug worth knowing about

**ctranslate2 silently calls `torch.set_num_threads(4)` when a model loads.** On this box torch
defaults to 96 threads. Kokoro runs on CPU torch, so loading faster-whisper first makes TTS
**3.5× slower**:

| torch threads | Kokoro first-chunk |
|---|---|
| 96 (before ct2 loads) | 0.506s |
| **4 (after ct2 loads)** | **1.804s** |
| 16 (restored) | 0.699s |
| 32 (restored) | 0.530s |

This cost 1.7s per turn in the first end-to-end run — time-to-first-audio was **2.408s** before
the fix and **0.722s** after it, together with a shorter first chunk. Restoring
`torch.set_num_threads(32)` after loading the STT model is required in the voice service, and is
the kind of defect that would otherwise be misdiagnosed as "Kokoro is slow".

---

## 2. Why the current design cannot be evolved incrementally

| Layer | Current | Blocker |
|---|---|---|
| STT | Web Speech API (`app.js:927`) | Chrome-only; **streams mic audio to Google**; cannot run offline |
| Turn-taking | `continuous = false` + push-to-talk (`app.js:935`) | Mic is **closed while the AI speaks** |
| Transport | `POST /api/chat`, sync `def` (`app.py:735`) | Request/response; no partial results |
| LLM | `streaming=False` (`llm_engine.py:136`) | Whole reply generated before anything is spoken |
| TTS | One base64 WAV (`tts_engine.py`) | **Indivisible** — cannot interrupt audio that doesn't exist until complete |
| Playback | `new Audio(blobURL)` (`app.js:1069`) | Cannot be flushed cleanly mid-buffer |

Barge-in is not a missing feature; it is **excluded by the shape of the pipeline**. The voice
path needs replacing. The REST endpoints stay for the text UI.

The Web Speech API dependency deserves separate emphasis: for an on-prem NDMA deployment,
shipping participant microphone audio to Google is plausibly a compliance blocker, and — given
this box's intermittent connectivity (see the `en_core_web_sm` incident) — it cannot work
reliably offline regardless.

---

## 3. Target architecture

```
┌─ Browser ─────────────────────────────────────┐
│  AudioWorklet capture ──16kHz PCM frames──┐   │
│  Jitter-buffered playback ◀──PCM frames──┐│   │
│  (flushable on barge-in)                 ││   │
└──────────────────────────────────────────┼┼───┘
                                  WebSocket ││ /ws/voice
┌─ FastAPI ────────────────────────────────▼┴───┐
│  Silero VAD ──▶ endpointing + barge-in detect │
│       │                                        │
│       ▼                                        │
│  faster-whisper small.en (GPU, ct2 CUDA)       │
│       │                                        │
│       ▼                                        │
│  LLMEngine (streaming=True, 127.0.0.1)         │
│       │  token stream                          │
│       ▼                                        │
│  Sentence chunker ──▶ Kokoro ──▶ PCM frames    │
│                                                │
│  Cancellation bus: VAD ─▶ abort LLM + TTS      │
└────────────────────────────────────────────────┘
```

### 3.1 Component decisions

| Concern | Choice | Licence | Rationale |
|---|---|---|---|
| Transport | WebSocket `/ws/voice` | — | Duplex binary audio + JSON control; REST kept for text UI |
| VAD | **Silero VAD** (bundled with faster-whisper) | MIT | Measured 0.044ms per 32ms frame (§1.7); no separate dependency |
| STT | **faster-whisper** `small.en` on **GPU** | MIT | Measured 0.120s for a typical turn (§1.7); GPU is mandatory, CPU fails the gate |
| LLM | **LM Studio**, `nemotron-3-nano` for voice | — | Measured 0.42s to first visible token (§1.3) |
| TTS | **Kokoro-82M**, clause-chunked, CPU | Apache-2.0 | Measured RTF 0.06–0.14 (§1.4); needs the torch-thread fix (§1.8) |
| Capture/playback | `AudioWorklet` | — | `<audio>` + Blob cannot be flushed mid-utterance |

**Model routing, not model replacement.** `gemma-4-26b-a4b` stays for the text UI and upload
extraction, where its reasoning is an asset and latency is irrelevant. Only the *voice* path
routes to the nano model. Note from §1.5 that LM Studio evicts under VRAM pressure — running
both concurrently needs verification (Phase 0.4), and JIT eviction mid-exercise would be a
catastrophic latency spike.

### 3.2 Build vs. adopt

**Pipecat** and **LiveKit Agents** (both Apache-2.0) already implement the duplex loop, VAD
integration, barge-in, and jitter buffering — the parts that are fiddly and easy to get subtly
wrong — and both target local Whisper / local TTS / OpenAI-compatible LLM backends, which is
exactly this stack.

Recommendation: **timebox a spike (Phase 1.5) before committing.** Their Kokoro support should
be verified against current releases rather than assumed. Hand-rolling on raw WebSockets is
viable and gives full control, but most of the effort goes into re-implementing jitter buffering
and interruption edge cases.

---

## 4. Implementation phases

### Phase 0 — Latency quick wins `[S]` — do this first, independent of everything else

> These are strictly configuration and benefit the **existing text UI immediately**. Combined,
> they cut ~3.4s from every response. No architectural commitment required.

- [ ] **0.1** `[S]` `.env.example` + `.env`: `LMSTUDIO_BASE_URL` → `http://127.0.0.1:1234/v1`.
      Comment *why*, citing the 2.058s → 0.010s measurement, so nobody "tidies" it back.
- [ ] **0.2** `[S]` Give `ChatOpenAI` a persistent `httpx` client so connections are reused
      (§1.2 shows session reuse independently fixes the stall — belt and braces for any host
      that isn't a literal IP).
- [ ] **0.3** `[S]` `llm_engine.py:136` — `streaming=False` → `True`; add a `stream_response()`
      generator alongside `get_response()`. Do not change `get_response()` callers yet.
- [ ] **0.4** `[M]` Verify `nemotron-3-nano` + `gemma-4-26b-a4b` stay **co-resident** in 48 GB
      without eviction. Confirm via `nvidia-smi` under alternating load. If they evict, decide:
      smaller text model, or a second LM Studio instance on another port.
- [ ] **0.5** `[S]` Add `LMSTUDIO_VOICE_MODEL` env var + routing so the voice path selects its
      own model.
- [ ] **0.6** `[S]` Re-run `scripts/voice_latency_probe.py`; record the new baseline in this file.

**Exit criteria:** text-UI response latency drops by ≥3s; probe confirms `first_visible ≤ 0.5s`
on the voice model.

---

### Phase 1 — De-risking spikes `[M]` — mostly complete

> **GATE RESULT (2026-08-21): PASSED.** End-to-end time-to-first-audio is 0.72–0.93s median
> across three runs, server-side (§1.6). The §3 architecture stands; Phase 2 can start. Only the
> build-vs-adopt decision (1.5) remains blocking.

- [x] **1.1** `[S]` Installed `faster-whisper 1.2.1` (+ `ctranslate2 4.8.1`, `onnxruntime`).
      Silero VAD ships bundled — no separate package. **`nvidia-cublas-cu12` is also required**
      (§1.7). Both are declared as the `voice` extra in `pyproject.toml`: install with
      **`uv sync --extra voice`** — a bare `uv sync` *uninstalls* them (verified: "Would
      uninstall 8 packages").
- [ ] **1.1b** `[M]` **Vendor the weights** the way `en_core_web_sm` was — `distil-small.en`,
      `small.en`, Silero, and the 553 MB cuBLAS wheel. Not yet done; this box's connectivity is
      intermittent (the cuBLAS download took ~18 min and one `uv` attempt hung indefinitely),
      so redeploy currently depends on a network that has already failed once.
- [x] **1.2** `[M]` **STT latency measured** — §1.7. GPU passes the 0.5s gate by 5×; CPU fails
      it by 2–3×. GPU is now a hard requirement.
- [x] **1.3** `[S]` **Silero VAD measured** at 0.044ms per 32ms frame — negligible.
      *Still open:* tune the silence threshold against **real Pakistani-English speech**.
      500ms remains a starting point, not a validated value.
- [x] **1.4** `[S]` **Resolved, and the original premise was wrong.** ctranslate2 carries its own
      CUDA runtime, so torch stays CPU-only. The real work was `nvidia-cublas-cu12` plus Windows
      DLL registration (§1.7).
- [ ] **1.5** `[M]` **Build-vs-adopt spike.** Timeboxed Pipecat prototype: local Whisper + local
      Kokoro + LM Studio, barge-in working. Ship a decision, not a prototype.
      **This is now the only blocking unknown before Phase 2.**
- [ ] **1.6** `[S]` Re-measure §1.7 WER against **real participant audio**. Current rates come
      from synthetic speech and are optimistic by construction.

**Exit criteria:** a written go/no-go on framework adoption. Every other term in the §1.6 budget
is now filled in with a measured number.

---

### Phase 2 — Duplex transport `[L]`

- [ ] **2.1** `[M]` `/ws/voice` WebSocket endpoint (`async def`). Define the wire protocol:
      binary frames = PCM; JSON = control (`user_speech_start`, `transcript_partial`,
      `assistant_start`, `cancel`, `turn_end`).
- [ ] **2.2** `[M]` Session auth over WS. Reuse `SessionDep` / `X-Session-Id` semantics —
      WebSockets don't carry the header the same way; resolve via query param or first frame.
- [ ] **2.3** `[M]` Client `AudioWorklet` capture: mic → 16kHz mono PCM → framed upstream.
      Replace `initSTT()` (`app.js:926`) entirely.
- [ ] **2.4** `[M]` Client playback graph: **flushable** jitter-buffered queue. Retire
      `new Audio(blobURL)` for the voice path.
- [ ] **2.5** `[S]` `getUserMedia` with `echoCancellation`, `noiseSuppression`, `autoGainControl`.
- [ ] **2.6** `[M]` Server VAD loop → endpointing → transcription trigger.
- [ ] **2.7** `[S]` Connection lifecycle: reconnect, half-open detection, cleanup on drop.

**Exit criteria:** speak → transcribed → LLM → audio reply over one socket. **Interruption not
yet required.**

---

### Phase 3 — Streaming synthesis `[M]`

- [ ] **3.1** `[M]` Clause chunker over the LLM token stream. Emit on `. ! ? , ; :` past a
      ~10-character minimum so the *first* chunk is short. Validated in
      `scripts/voice_e2e_probe.py`: an 18-char minimum produced a 94-char first chunk (0.505s to
      synthesize); a 10-char minimum produced `"Understood."` (0.251s). **First chunk short,
      later chunks longer.**
- [ ] **3.2** `[M]` `tts_engine.stream_speech()` — generator yielding PCM per chunk. Keep
      `generate_speech()` intact for the REST endpoint.
- [ ] **3.3** `[S]` Kokoro synthesis off the event loop (worker thread / `run_in_executor`) so
      it cannot block the socket.
- [ ] **3.3b** `[S]` **Restore `torch.set_num_threads(32)` after loading the STT model** — see
      §1.8. Without it Kokoro is 3.5× slower and time-to-first-audio roughly triples. Add a
      regression assertion; this is silent and easy to reintroduce.
- [ ] **3.4** `[S]` Strip markdown before synthesis — `_clean_text_for_tts()` already does this;
      make it work incrementally on partial chunks without swallowing text across boundaries.
- [ ] **3.5** `[M]` Voice-specific prompt + `max_tokens`. The current moderator prompt targets a
      chat bubble; `LMSTUDIO_MAX_TOKENS=3000` produces essays. Voice turns are 1–3 sentences.
- [ ] **3.6** `[S]` Word timestamps over the socket so the existing highlighting (`app.js:1076`)
      survives, offset per chunk.

**Exit criteria:** first audio ≤1.5s after end of user speech, measured end-to-end.

---

### Phase 4 — Barge-in and turn-taking `[L]` — the hard part

- [ ] **4.1** `[M]` Keep the mic open **during** playback. This inverts the current design
      (`app.js:989` stops TTS before listening).
- [ ] **4.2** `[L]` Barge-in detection: VAD fires during assistant playback → `cancel`. Must
      distinguish real speech from echo and from backchannel ("mm-hm", "right") that should
      *not* interrupt. Expect this to need iteration against real users.
- [ ] **4.3** `[M]` Cancellation propagation: abort the LLM stream, stop Kokoro mid-chunk, flush
      the client queue. Every stage needs a cancellation token; a half-cancelled pipeline that
      resumes speaking is the worst failure mode here.
- [ ] **4.4** `[M]` Echo rejection. §"AEC" below — budget real time for this.
- [ ] **4.5** `[S]` Barge-in debounce so a cough doesn't derail a briefing.
- [ ] **4.6** `[M]` Turn-state machine: `idle → listening → thinking → speaking → interrupted`,
      with the illegal transitions actually enforced rather than implied.

**Exit criteria:** a participant can cut the moderator off mid-sentence and be understood, with
no self-interruption loop over headsets.

---

### Phase 5 — Conversation integrity `[M]`

> Interruption breaks an assumption the persistence layer currently makes.

- [ ] **5.1** `[M]` Persist **what the participant actually heard**, not what was generated.
      `app.py:765` saves the complete response; if the user cuts in after six words, the
      transcript must record six words. Otherwise the model believes it said things nobody
      heard — and for a training exercise the transcript is an **assessment artifact**.
- [ ] **5.2** `[S]` Schema: `interrupted` flag + `spoken_text` alongside `content`.
- [ ] **5.3** `[S]` Store the STT transcript verbatim, with confidence, for after-action review.
- [ ] **5.4** `[M]` Inject delivery (`app.py:748`) assumes a discrete turn. Re-check the
      semantics when a turn can be truncated.
- [ ] **5.5** `[S]` Text and voice must share one transcript — participants will switch mid-exercise.

---

### Phase 6 — Production hardening `[L]`

- [ ] **6.1** `[M]` Concurrency: how many simultaneous voice sessions? One Whisper + one Kokoro
      serving N wings needs a queue and a measured ceiling. **This is an exercise-wide risk** —
      SimEx runs multiple wings at once.
- [ ] **6.2** `[S]` Graceful degradation: STT/TTS failure falls back to text, following the
      pattern already established in `_get_pipeline()`.
- [ ] **6.3** `[S]` Per-stage latency metrics emitted per turn; keep the probe as a regression test.
- [ ] **6.4** `[M]` Controller observability: live transcript of every wing's voice session.
- [ ] **6.5** `[S]` Vendor **all** model weights (Whisper, Silero, Kokoro) — offline-first, per
      the `en_core_web_sm` precedent.
- [ ] **6.6** `[M]` Load test at expected wing count on the real box.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Acoustic echo** in a control room with open speakers | **High** | Browser AEC helps with headsets, poorly with open speakers. **Mandate headsets** — this is the most likely thing to break a live exercise |
| ~~STT latency exceeds budget~~ | **Closed** | Measured: 0.120s on GPU, gate passed by 5× (§1.7) |
| LM Studio evicts a model mid-exercise | High | Phase 0.4; consider separate instances per model |
| Concurrent wings saturate one GPU | **High** | Now the top *unmeasured* performance risk — every §1.6 number is single-session. Phase 6.1 before scheduling a real exercise |
| Barge-in false positives on backchannel | Medium | Phase 4.2/4.5; needs real-user iteration |
| Pakistani-English accent accuracy | **High** | Now the largest *unmeasured* quality risk. §1.7 WER comes from synthetic speech and is optimistic by construction. Test real participant audio (Phase 1.6); prefer `small.en` |
| Intermittent connectivity breaks setup | **High** | Demonstrated twice today: one `uv` install hung indefinitely, the 553 MB cuBLAS wheel took ~18 min. Vendor every weight and wheel (1.1b, 6.5) |
| Framework churn (Pipecat/LiveKit) | Low | Phase 1.5 decision gate |

---

## 6. Open decisions

1. **Framework or hand-rolled?** → Phase 1.5. Leaning Pipecat for a small team.
2. **Does voice replace the text UI, or sit beside it?** Determines how much of `app.js`
   survives. Recommendation: **beside** — controllers will want text, and it's the degradation path.
3. **Headsets or open speakers** in the exercise room? Materially changes Phase 4.4 difficulty.
4. **How many concurrent voice wings** must a single box support? Sizes Phase 6.1.
5. **Is `nemotron-3-nano` good enough as a moderator?** It's fast (§1.3) and the end-to-end
   replies are plausible ("Understood. Please confirm the required helicopter specifications…"),
   but the probes only tested **latency, not moderation quality**. Needs evaluation against
   `tests/test_moderator_prompt_quality.py` before committing the voice path to it. There is
   headroom to trade back: the §1.6 budget has ~0.6s of slack against the 1.5s commercial
   benchmark, enough for a larger voice model if quality demands it.

---

## 7. Recommended sequence

**Phase 0 this week** — it is pure configuration, needs no architectural buy-in, and makes the
existing product ~3.4s faster per turn. Nothing in it depends on the voice work landing.

**Phase 1 is now essentially complete and the gate passed** (§1.6): 0.72–0.93s time-to-first-audio,
server-side, across three independent runs. Two items remain — the build-vs-adopt decision (1.5), which is
the only blocker for Phase 2, and vendoring the weights (1.1b), which is a deployment risk rather
than a design one.

**Phase 2 is cleared to start** once 1.5 reports a decision. The design in §3 survived
measurement unchanged; what changed is that GPU STT is now mandatory rather than optional, and
two integration defects (§1.7 DLL registration, §1.8 torch threads) are known in advance instead
of being discovered during the build.
