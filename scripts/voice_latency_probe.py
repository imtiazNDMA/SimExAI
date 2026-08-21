"""Voice-path latency probe.

The existing .tmp_latency_probe.py measures whole-call latency, which is the
right metric for the text UI. For a duplex voice agent the metric that decides
the architecture is different:

  * LLM  -> time to FIRST token, and for reasoning models how much of that is
            invisible "thinking" dead air.
  * TTS  -> time to the FIRST audio segment, not the whole utterance, plus the
            real-time factor (synthesis seconds per audio second).

Run:  .venv/Scripts/python.exe scripts/voice_latency_probe.py
"""
import os
import statistics
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")
API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")

# Representative moderator turn: short system prompt, short user turn.
SYSTEM = (
    "You are a disaster-management exercise moderator. Reply in at most two "
    "short spoken sentences. Never use bullet points or markdown."
)
USER = "We will coordinate with the relevant departments."


def probe_llm(model: str, max_tokens: int, timeout: int = 240) -> dict | None:
    """Stream one completion, timing first token and first visible token."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "temperature": 0.45,
        "max_tokens": max_tokens,
        "stream": True,
    }
    started = time.perf_counter()
    first_chunk = None
    first_visible = None
    visible = []
    reasoning_chars = 0
    in_think = False

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {API_KEY}"},
            stream=True,
            timeout=timeout,
        )
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw or not raw.startswith(b"data: "):
                continue
            payload = raw[6:]
            if payload == b"[DONE]":
                break
            import json as _json

            delta = _json.loads(payload)["choices"][0].get("delta", {})
            # LM Studio exposes reasoning either as a separate field or inline.
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            content = delta.get("content")

            if first_chunk is None and (reasoning or content):
                first_chunk = time.perf_counter() - started
            if reasoning:
                reasoning_chars += len(reasoning)
            if content:
                if "<think>" in content:
                    in_think = True
                if in_think:
                    reasoning_chars += len(content)
                    if "</think>" in content:
                        in_think = False
                    continue
                if first_visible is None:
                    first_visible = time.perf_counter() - started
                visible.append(content)
    except Exception as exc:  # noqa: BLE001 - probe, report and move on
        print(f"  !! {model}: {type(exc).__name__}: {exc}")
        return None

    total = time.perf_counter() - started
    text = "".join(visible).strip()
    return {
        "model": model,
        "first_chunk": first_chunk,
        "first_visible": first_visible,
        "total": total,
        "reasoning_chars": reasoning_chars,
        "chars": len(text),
        "text": text,
    }


def probe_tts() -> None:
    """Time Kokoro cold init, first segment, and full synthesis."""
    import numpy as np

    from backend import tts_engine

    print("\n=== KOKORO TTS ===")
    started = time.perf_counter()
    pipeline = tts_engine._get_pipeline()
    print(f"cold init                 : {time.perf_counter() - started:6.2f}s")
    if pipeline is None:
        print(f"  !! init failed: {tts_engine._init_error}")
        return

    sentence = "Forest fire risk remains elevated across the northern districts."
    voice = os.getenv("KOKORO_VOICE", "af_heart")

    # Warm call so we measure steady state, not first-call graph setup.
    list(pipeline(sentence, voice=voice, speed=1.0))

    for label, text in [
        ("one sentence", sentence),
        (
            "three sentences",
            sentence
            + " District officers should confirm evacuation routes. "
            "Report back within the hour.",
        ),
    ]:
        started = time.perf_counter()
        first_seg = None
        audio = []
        for result in pipeline(text, voice=voice, speed=1.0):
            if result.audio is None or len(result.audio) == 0:
                continue
            if first_seg is None:
                first_seg = time.perf_counter() - started
            audio.append(result.audio)
        total = time.perf_counter() - started
        secs = len(np.concatenate(audio)) / 24000 if audio else 0.0
        print(
            f"{label:<26}: first_segment {first_seg:5.2f}s | "
            f"full {total:5.2f}s | audio {secs:5.2f}s | RTF {total / secs:4.2f}"
        )


def main() -> None:
    import torch

    print("=== ENVIRONMENT ===")
    print(f"torch {torch.__version__} | cuda_available={torch.cuda.is_available()}")
    print(f"base_url {BASE_URL}")
    if "localhost" in BASE_URL:
        print(
            "  !! WARNING: 'localhost' costs ~2.05s per new TCP connection on\n"
            "     Windows (IPv6 ::1 stall). Every number below is inflated by\n"
            "     that much. Use http://127.0.0.1:1234/v1 -- see ARCHITECTURE.md 1.2."
        )

    models = requests.get(
        f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15
    ).json()
    chat_models = [
        m["id"] for m in models["data"] if "embed" not in m["id"].lower()
    ]

    print("\n=== LLM (streaming, warmup discarded, median of 3) ===")
    print(f"{'model':<34} {'1st tok':>8} {'1st vis':>8} {'total':>7} {'think':>7}")
    print("-" * 68)
    for model in chat_models:
        # LM Studio JIT-loads models on first request and evicts under VRAM
        # pressure, so the first call measures model load, not inference.
        # Discard it.
        probe_llm(model, max_tokens=3000)
        runs = []
        for _ in range(3):
            r = probe_llm(model, max_tokens=3000)
            if r:
                runs.append(r)
        if not runs:
            continue
        fv = statistics.median(
            [r["first_visible"] for r in runs if r["first_visible"] is not None]
            or [float("nan")]
        )
        fc = statistics.median([r["first_chunk"] for r in runs])
        tot = statistics.median([r["total"] for r in runs])
        think = statistics.median([r["reasoning_chars"] for r in runs])
        print(f"{model:<34} {fc:7.2f}s {fv:7.2f}s {tot:6.2f}s {think:6.0f}c")
        print(f"    -> {runs[-1]['text'][:150]}")

    probe_tts()


if __name__ == "__main__":
    main()
