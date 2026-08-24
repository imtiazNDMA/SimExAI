"""Kokoro TTS engine — generates speech audio with word-level timestamps.

Uses the native kokoro KPipeline for high-quality TTS with precise
word-level alignment timestamps for synchronized highlighting.
"""
import base64
import io
import os
import re
import warnings
from typing import Optional

# Lazy-loaded globals
_pipeline = None
_available = None
_init_error = None


def _is_available() -> bool:
    """Check if Kokoro TTS dependencies are installed."""
    global _available
    if _available is not None:
        return _available
    try:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
        _available = True
    except ImportError:
        _available = False
        print("Warning: Kokoro TTS not available. Install with: pip install kokoro soundfile")
    return _available


def _get_pipeline():
    """Lazy-initialize the Kokoro pipeline on first use.

    Returns None if initialization fails. Kokoro pulls in spaCy and model
    weights on first use, and those can fail at request time on an offline or
    throttled network — spacy.cli.download calls sys.exit(), which raises
    SystemExit rather than a normal exception. Failures are cached in
    _init_error so every later request degrades to silent no-audio instead of
    retrying a slow download and returning a 500.
    """
    global _pipeline, _init_error
    if _pipeline is not None:
        return _pipeline
    if _init_error is not None:
        return None
    lang = os.getenv("KOKORO_LANG", "a")  # 'a' = American English
    repo_id = os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")
    try:
        from kokoro import KPipeline
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="dropout option adds dropout after all but last recurrent layer.*",
                category=UserWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message="`torch.nn.utils.weight_norm` is deprecated.*",
                category=FutureWarning,
            )
            _pipeline = KPipeline(lang_code=lang, repo_id=repo_id)
    except (Exception, SystemExit) as e:
        _init_error = (
            f"Kokoro TTS initialization failed ({type(e).__name__}: {e}). "
            "Check that the spaCy model en_core_web_sm is installed and that "
            "the Kokoro weights are present in the local Hugging Face cache."
        )
        print(f"Warning: {_init_error}")
        return None
    print(f"Kokoro TTS initialized (lang={lang}, repo={repo_id})")
    return _pipeline


def _clean_text_for_tts(text: str) -> str:
    """Strip markdown formatting and special chars that confuse TTS."""
    # Remove bold/italic markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^[\s]*[-•]\s*', '', text, flags=re.MULTILINE)
    # Remove numbered lists like "1. " or "1) "
    text = re.sub(r'^[\s]*\d+[.)]\s*', '', text, flags=re.MULTILINE)
    # Collapse multiple newlines
    text = re.sub(r'\n{2,}', '. ', text)
    text = text.replace('\n', ' ')
    # Collapse whitespace
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def generate_speech(
    text: str,
    voice: Optional[str] = None,
    speed: float = 1.0,
) -> dict:
    """Generate speech audio and word timestamps from text.

    Returns:
        {
            "audio": "base64-encoded WAV string",
            "timestamps": [{"word": "Hello", "start": 0.0, "end": 0.32}, ...]
        }
    """
    if not _is_available():
        return {"audio": "", "timestamps": [], "error": "Kokoro TTS not installed"}

    import soundfile as sf
    import numpy as np

    pipeline = _get_pipeline()
    if pipeline is None:
        return {"audio": "", "timestamps": [], "error": _init_error}

    voice = voice or os.getenv("KOKORO_VOICE", "af_heart")

    cleaned = _clean_text_for_tts(text)
    if not cleaned:
        return {"audio": "", "timestamps": []}

    # Generate audio in chunks (Kokoro yields segments for long text)
    all_audio = []
    all_timestamps = []
    time_offset = 0.0
    sample_rate = 24000

    try:
        for result in pipeline(cleaned, voice=voice, speed=speed):
            if result.audio is not None and len(result.audio) > 0:
                all_audio.append(result.audio)

                # Extract word-level timestamps (native Kokoro alignment)
                if hasattr(result, 'tokens') and result.tokens:
                    for token in result.tokens:
                        word = getattr(token, 'text', '').strip()
                        if not word:
                            continue
                        start = getattr(token, 'start_ts', 0.0) + time_offset
                        end = getattr(token, 'end_ts', 0.0) + time_offset
                        all_timestamps.append({
                            "word": word,
                            "start": round(start, 3),
                            "end": round(end, 3),
                        })

                # Update offset for next chunk
                time_offset += len(result.audio) / sample_rate

    except Exception as e:
        print(f"TTS generation error: {e}")
        return {"audio": "", "timestamps": [], "error": str(e)}

    if not all_audio:
        return {"audio": "", "timestamps": []}

    # Concatenate all audio chunks
    combined = np.concatenate(all_audio)

    # Encode as WAV base64
    buf = io.BytesIO()
    sf.write(buf, combined, sample_rate, format='WAV', subtype='PCM_16')
    buf.seek(0)
    audio_b64 = base64.b64encode(buf.read()).decode('ascii')

    return {
        "audio": audio_b64,
        "timestamps": all_timestamps,
    }
