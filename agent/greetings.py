"""Greeting text/voice per language and the pre-rendered greeting audio cache.

The call greeting is fixed text, so instead of asking the live model to generate
it (several seconds while the caller hears ringing) we render it once with
``scripts/generate_greetings.py`` and play the stored audio the instant the call
connects, while the live session is still being set up.

``data/greetings.json`` format::

    {"English": {"text": "...", "voice": "Aoede", "audioB64": "<24 kHz PCM16 mono>", ...}, ...}

A cached entry is used only if it still matches the configured text and voice
and has a plausible duration; otherwise ``load_cached_greeting`` returns None
and the caller falls back to live generation (the previous behaviour).
"""
import base64
import json
import os
import threading
from typing import Dict, Optional

# Live API audio output format.
OUTPUT_SAMPLE_RATE = 24000
BYTES_PER_SECOND = OUTPUT_SAMPLE_RATE * 2  # 16-bit mono

# Sanity bounds for a stored greeting (guards against rambling / empty renders).
MIN_GREETING_SECONDS = 0.8
MAX_GREETING_SECONDS = 15.0

GREETINGS_PATH = os.environ.get(
    "GREETINGS_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "greetings.json"),
)

# Single source of truth for per-language voice settings and greeting text.
LANGUAGE_CONFIGS: Dict[str, Dict[str, str]] = {
    "Bengali": {
        "code": "bn-BD",
        "greeting": "ইউনিফাইড ক্লাউডে আপনাকে স্বাগতম। আমরা আপনাকে কীভাবে সাহায্য করতে পারি?",
        "voice": "Leda",
    },
    "English": {
        "code": "en-US",
        "greeting": "Hello! Thank you for calling Unified Cloud. How can I help you today?",
        "voice": "Aoede",
    },
    "Spanish": {
        "code": "es-ES",
        "greeting": "¡Hola! Gracias por llamar a Unified Cloud. ¿Cómo puedo ayudarle hoy?",
        "voice": "Aoede",
    },
    "Portuguese": {
        "code": "pt-PT",
        "greeting": "Olá! Obrigado por ligar para a Unified Cloud. Como posso ajudá-lo hoje?",
        "voice": "Aoede",
    },
}
DEFAULT_LANGUAGE = "Bengali"


def get_language_config(language: str) -> Dict[str, str]:
    return LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS[DEFAULT_LANGUAGE])


_lock = threading.Lock()
_file_cache = {"mtime": None, "path": None, "data": {}}


def _read_file() -> dict:
    """Parse greetings.json, re-reading only when the file changes."""
    path = GREETINGS_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    with _lock:
        if _file_cache["path"] == path and _file_cache["mtime"] == mtime:
            return _file_cache["data"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception as e:
            print(f"[greetings] could not read {path}: {e}")
            data = {}
        _file_cache.update(mtime=mtime, path=path, data=data)
        return data


def validate_entry(entry: object, config: Dict[str, str]) -> Optional[str]:
    """Return a base64 PCM string if ``entry`` is usable for ``config``, else None."""
    if not isinstance(entry, dict):
        return None
    if entry.get("text") != config["greeting"]:
        return None
    # Entries written by the generator also record the voice; reject a mismatch.
    if entry.get("voice") is not None and entry.get("voice") != config["voice"]:
        return None
    b64 = entry.get("audioB64")
    if not isinstance(b64, str) or not b64:
        return None
    try:
        nbytes = len(base64.b64decode(b64, validate=True))
    except Exception:
        return None
    if nbytes % 2:
        return None
    seconds = nbytes / BYTES_PER_SECOND
    if not (MIN_GREETING_SECONDS <= seconds <= MAX_GREETING_SECONDS):
        return None
    return b64


def load_cached_greeting(language: str) -> Optional[str]:
    """Base64 24 kHz PCM16 greeting for ``language`` if a valid cached render exists."""
    config = get_language_config(language)
    resolved = language if language in LANGUAGE_CONFIGS else DEFAULT_LANGUAGE
    entry = _read_file().get(resolved)
    return validate_entry(entry, config)
