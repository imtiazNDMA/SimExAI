"""STT latency probe -- ARCHITECTURE.md Phase 1.2 gate.

Measures faster-whisper transcription latency against the fixtures produced by
make_stt_fixtures.py. The number that matters for the voice architecture is
p95 transcription time for a typical participant turn (~3-12s of audio).

GATE: if p95 for a typical turn exceeds 0.5s, the segment-at-once design in
ARCHITECTURE.md Phase 2 must be revisited in favour of streaming/partial
transcription.

Reports latency, real-time factor, and a rough word-error rate against the
reference text. See make_stt_fixtures.py for why the WER here is optimistic.

Run:  .venv/Scripts/python.exe scripts/stt_latency_probe.py [model] [device]
"""
import os
import pathlib
import re
import statistics
import sys
import time

FIXTURES = pathlib.Path("scratch/stt_fixtures")
RUNS = 5


def register_cuda_dlls() -> None:
    """Make pip-installed CUDA libraries findable on Windows.

    Python 3.8+ ignores PATH when resolving extension-module DLLs. A CUDA
    torch build normally calls os.add_dll_directory() for these, but this
    project runs torch CPU-only (ctranslate2 brings its own CUDA runtime), so
    nothing registers them and ctranslate2 fails with
    "Library cublas64_12.dll is not found or cannot be loaded".
    """
    if not hasattr(os, "add_dll_directory"):
        return  # not Windows
    site = pathlib.Path(__file__).resolve().parent.parent / ".venv/Lib/site-packages"
    found = []
    for pattern in ("nvidia/*/bin", "nvidia/*/lib"):
        for path in site.glob(pattern):
            if path.is_dir():
                os.add_dll_directory(str(path))
                found.append(str(path))
    # add_dll_directory alone is not enough: ctranslate2.dll resolves cuBLAS
    # with its own LoadLibrary call, which searches PATH rather than the
    # directories registered for Python's extension loader.
    if found:
        os.environ["PATH"] = os.pathsep.join(found) + os.pathsep + os.environ["PATH"]


def normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation -- WER should not punish comma placement."""
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    """Levenshtein distance over words / reference length."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(
                prev[j - 1] if r == h else 1 + min(prev[j - 1], prev[j], cur[j - 1])
            )
        prev = cur
    return prev[-1] / len(ref)


def main() -> None:
    register_cuda_dlls()
    from faster_whisper import WhisperModel

    model_name = sys.argv[1] if len(sys.argv) > 1 else "distil-small.en"
    device = sys.argv[2] if len(sys.argv) > 2 else "auto"
    compute = "float16" if device == "cuda" else "int8"

    print(f"=== faster-whisper: {model_name} on {device} ({compute}) ===")
    started = time.perf_counter()
    model = WhisperModel(model_name, device=device, compute_type=compute)
    print(f"model load: {time.perf_counter() - started:.2f}s\n")

    cases = sorted(FIXTURES.glob("*.wav"))
    if not cases:
        raise SystemExit(
            f"No fixtures in {FIXTURES}. Run scripts/make_stt_fixtures.py first."
        )

    print(f"{'fixture':<10}{'audio':>7}{'median':>9}{'p95':>8}{'RTF':>7}{'WER':>7}")
    print("-" * 48)

    import soundfile as sf

    for wav in cases:
        reference = wav.with_suffix(".txt").read_text(encoding="utf-8")
        audio_secs = sf.info(wav).duration

        # Warm up: first call initializes CUDA/BLAS workspaces.
        segments, _ = model.transcribe(str(wav), beam_size=1, language="en")
        text = " ".join(s.text for s in segments)

        times = []
        for _ in range(RUNS):
            t0 = time.perf_counter()
            segments, _ = model.transcribe(str(wav), beam_size=1, language="en")
            text = " ".join(s.text for s in segments)  # generator: must drain
            times.append(time.perf_counter() - t0)

        med = statistics.median(times)
        p95 = sorted(times)[max(0, int(len(times) * 0.95) - 1)]
        print(
            f"{wav.stem:<10}{audio_secs:6.2f}s{med:8.3f}s{p95:7.3f}s"
            f"{med / audio_secs:7.3f}{wer(reference, text):6.1%}"
        )
        print(f"    -> {text.strip()[:110]}")


if __name__ == "__main__":
    main()
