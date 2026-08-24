"""Generate audio fixtures for the STT latency probe.

Uses Kokoro (already vendored and working) to synthesize SimEx-domain
utterances at ~3s / ~8s / ~15s, saved as 16kHz mono WAV -- the format the
voice pipeline will actually feed to Whisper.

IMPORTANT CAVEAT: synthetic TTS speech is clean, unaccented, and noise-free.
Latency measured against it is representative (transcription cost tracks audio
duration and model size), but ACCURACY is optimistic. Real Pakistani-English
participant audio over a headset in a noisy control room will be worse. Phase
1.2 accuracy numbers from these fixtures are a floor, not a forecast.

Run:  .venv/Scripts/python.exe scripts/make_stt_fixtures.py
"""
import os
import pathlib
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

OUT = pathlib.Path("scratch/stt_fixtures")

# Representative participant turns: domain vocabulary, place names, numbers --
# the things Whisper is most likely to get wrong.
UTTERANCES = {
    "short": (
        "We will coordinate with the relevant departments."
    ),
    "medium": (
        "The district administration has deployed four rescue teams to the "
        "affected union councils. We are requesting two additional helicopters "
        "for the aerial survey of the northern sector."
    ),
    "long": (
        "As of zero six hundred hours, the Provincial Disaster Management "
        "Authority reports that flood water has receded by approximately two "
        "feet in Nowshera district. However, the Kabul river remains above the "
        "danger mark at Warsak. We have relocated eleven thousand people to "
        "sixteen relief camps, and we are coordinating with the National "
        "Highway Authority to reopen the Peshawar to Islamabad motorway."
    ),
}


def main() -> None:
    from backend import tts_engine

    pipeline = tts_engine._get_pipeline()
    if pipeline is None:
        raise SystemExit(f"Kokoro unavailable: {tts_engine._init_error}")

    OUT.mkdir(parents=True, exist_ok=True)
    voice = os.getenv("KOKORO_VOICE", "af_heart")

    for name, text in UTTERANCES.items():
        segments = [
            r.audio
            for r in pipeline(text, voice=voice, speed=1.0)
            if r.audio is not None and len(r.audio) > 0
        ]
        audio = np.concatenate(segments)

        # Kokoro emits 24kHz; the voice pipeline standardizes on 16kHz mono,
        # so resample here rather than measuring a format we won't ship.
        ratio = 16000 / 24000
        idx = np.arange(int(len(audio) * ratio)) / ratio
        resampled = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)

        path = OUT / f"{name}.wav"
        sf.write(path, resampled, 16000, subtype="PCM_16")
        print(
            f"{name:<8} {len(resampled) / 16000:5.2f}s  {len(text):3d} chars  -> {path}"
        )
        (OUT / f"{name}.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
