"""End-to-end voice-turn probe -- validates the ARCHITECTURE.md 1.6 budget.

Chains the real components in the order the live pipeline will run them:

    VAD -> faster-whisper -> LM Studio (streaming) -> Kokoro (first chunk)

and reports time-to-first-audio: the interval between the participant falling
silent and the first sample of the moderator's reply being ready to play.

This measures the SERVER pipeline only. It excludes network transit to the
browser, jitter-buffer depth, and the VAD silence threshold that decides when
the turn ended (~500ms, tunable) -- add those for the figure a user perceives.

Run:  .venv/Scripts/python.exe scripts/voice_e2e_probe.py
"""
import json
import os
import pathlib
import statistics
import sys
import time

import requests
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.stt_latency_probe import register_cuda_dlls  # noqa: E402

# 127.0.0.1, never localhost -- see ARCHITECTURE.md 1.2 (2.05s IPv6 stall).
BASE_URL = "http://127.0.0.1:1234/v1"
VOICE_MODEL = os.getenv("LMSTUDIO_VOICE_MODEL", "nvidia/nemotron-3-nano")
STT_MODEL = os.getenv("STT_MODEL", "distil-small.en")
FIXTURE = pathlib.Path("scratch/stt_fixtures/medium.wav")
RUNS = 5

SYSTEM = (
    "You are a disaster-management exercise moderator. Reply in at most two "
    "short spoken sentences. Never use bullet points or markdown."
)

# Emit the first TTS chunk at the first clause boundary rather than waiting for
# a full sentence -- ARCHITECTURE.md 1.4 measured 0.32s to synthesize 4 words
# against 0.63s for three sentences, so a short first chunk starts audio sooner.
CLAUSE_ENDS = (".", "!", "?", ",", ";", ":")
MIN_CHUNK_CHARS = 10


def first_chunk_boundary(buffer: str) -> int:
    """Return index just past the first usable clause break, or -1."""
    buffer = buffer.lstrip()
    if len(buffer) < MIN_CHUNK_CHARS:
        return -1
    for i, ch in enumerate(buffer):
        if i + 1 >= MIN_CHUNK_CHARS and ch in CLAUSE_ENDS:
            return i + 1
    return -1


def main() -> None:
    register_cuda_dlls()
    from faster_whisper import WhisperModel

    from backend import tts_engine

    print("=== loading components ===")
    import torch

    threads_before = torch.get_num_threads()
    stt = WhisperModel(STT_MODEL, device="cuda", compute_type="float16")
    # ctranslate2 clamps torch to 4 threads when it loads. Kokoro runs on CPU
    # torch, so leaving the clamp in place makes TTS ~3.5x slower (measured
    # 0.51s -> 1.80s). Restore a sane count -- see ARCHITECTURE.md 1.8.
    torch.set_num_threads(min(32, threads_before))
    print(f"torch threads: {threads_before} -> clamped by ct2 -> "
          f"{torch.get_num_threads()}")
    tts = tts_engine._get_pipeline()
    if tts is None:
        raise SystemExit(f"Kokoro unavailable: {tts_engine._init_error}")
    voice = os.getenv("KOKORO_VOICE", "af_heart")
    session = requests.Session()  # reuse the connection, as the server will

    audio, sr = sf.read(FIXTURE, dtype="float32")
    print(f"fixture: {FIXTURE.name} ({len(audio) / sr:.2f}s)")
    print(f"stt={STT_MODEL} (cuda) llm={VOICE_MODEL} tts=kokoro (cpu)\n")

    # Warm every stage: model load, CUDA workspaces, LM Studio JIT, Kokoro graph.
    list(stt.transcribe(audio, beam_size=1, language="en")[0])
    session.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": VOICE_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 20,
        },
        timeout=120,
    )
    list(tts("warm up the graph", voice=voice, speed=1.0))

    rows = []
    for _ in range(RUNS):
        t0 = time.perf_counter()

        segments, _ = stt.transcribe(audio, beam_size=1, language="en")
        transcript = " ".join(s.text for s in segments).strip()
        t_stt = time.perf_counter() - t0

        resp = session.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": VOICE_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                "temperature": 0.45,
                "max_tokens": 200,
                "stream": True,
            },
            stream=True,
            timeout=120,
        )

        buffer = ""
        chunk = None
        t_first_tok = None
        for raw in resp.iter_lines():
            if not raw or not raw.startswith(b"data: "):
                continue
            payload = raw[6:]
            if payload == b"[DONE]":
                break
            delta = json.loads(payload)["choices"][0].get("delta", {})
            content = delta.get("content")
            if not content:
                continue  # reasoning tokens: inaudible, still dead air
            if t_first_tok is None:
                t_first_tok = time.perf_counter() - t0
            buffer += content
            cut = first_chunk_boundary(buffer)
            if cut > 0:
                chunk = buffer.lstrip()[:cut]
                break
        resp.close()
        if chunk is None:
            chunk = buffer
        t_chunk = time.perf_counter() - t0

        for result in tts(chunk, voice=voice, speed=1.0):
            if result.audio is not None and len(result.audio) > 0:
                break
        t_audio = time.perf_counter() - t0

        rows.append((t_stt, t_first_tok, t_chunk, t_audio, transcript, chunk))

    med = lambda i: statistics.median([r[i] for r in rows])  # noqa: E731
    p95 = lambda i: sorted(r[i] for r in rows)[max(0, int(RUNS * 0.95) - 1)]  # noqa: E731

    print(f"{'stage':<34}{'median':>9}{'p95':>9}")
    print("-" * 52)
    print(f"{'1. STT transcribe':<34}{med(0):8.3f}s{p95(0):8.3f}s")
    print(f"{'2. + LLM first visible token':<34}{med(1):8.3f}s{p95(1):8.3f}s")
    print(f"{'3. + first clause complete':<34}{med(2):8.3f}s{p95(2):8.3f}s")
    print(f"{'4. + Kokoro first audio':<34}{med(3):8.3f}s{p95(3):8.3f}s")
    print("-" * 52)
    print(f"{'TIME TO FIRST AUDIO (server)':<34}{med(3):8.3f}s{p95(3):8.3f}s")
    print(f"\ntranscript: {rows[-1][4][:90]}")
    print(f"first chunk spoken: {rows[-1][5]!r}")


if __name__ == "__main__":
    main()
