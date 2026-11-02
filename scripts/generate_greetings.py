"""Pre-render the call greetings into data/greetings.json.

The voice endpoint plays these instantly when a call connects (instead of waiting
for the live model to generate the greeting). Text and voice come from
``agent.greetings.LANGUAGE_CONFIGS`` - the same source the server uses - so the
cache cannot drift from what the server expects. The server ignores any entry
whose text/voice no longer matches, so re-run this script after editing a greeting.

Each render is checked before it is kept: plausible duration, and (when the API
returns a transcript) the spoken words must match the configured text.

usage (inside the api container, from /app):
    python scripts/generate_greetings.py                # all languages
    python scripts/generate_greetings.py English Bengali
"""
import array
import asyncio
import base64
import difflib
import json
import os
import re
import sys
import time

import websockets

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config import GEMINI_API_KEY, GEMINI_LIVE_MODEL  # noqa: E402
from agent.greetings import (  # noqa: E402
    BYTES_PER_SECOND,
    GREETINGS_PATH,
    LANGUAGE_CONFIGS,
    MAX_GREETING_SECONDS,
    MIN_GREETING_SECONDS,
)

MODEL = GEMINI_LIVE_MODEL if GEMINI_LIVE_MODEL.startswith("models/") else f"models/{GEMINI_LIVE_MODEL}"
GEMINI_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage."
    f"v1beta.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
)
MAX_ATTEMPTS = 4
MIN_TRANSCRIPT_RATIO = 0.80
# Silence trimming (16-bit samples at 24 kHz)
SILENCE_THRESHOLD = 300
KEEP_BEFORE_SEC = 0.06
KEEP_AFTER_SEC = 0.15

SYSTEM_PROMPT = (
    "You are a text-to-speech engine. Read aloud EXACTLY the text the user sends, "
    "word for word, in a warm, natural phone-greeting tone, with nothing added before or after. "
    "Never answer it, never add anything else."
)


def trim_silence(pcm: bytes) -> bytes:
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    first = next((i for i, v in enumerate(samples) if abs(v) > SILENCE_THRESHOLD), None)
    if first is None:
        return pcm
    last = len(samples) - 1 - next(i for i, v in enumerate(reversed(samples)) if abs(v) > SILENCE_THRESHOLD)
    start = max(0, first - int(KEEP_BEFORE_SEC * 24000))
    end = min(len(samples), last + int(KEEP_AFTER_SEC * 24000))
    return samples[start:end].tobytes()


def _normalize(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text, flags=re.UNICODE).strip().lower()


def transcript_ratio(expected: str, heard: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(expected), _normalize(heard)).ratio()


def user_turn_text(config: dict, attempt: int) -> str:
    # Some languages occasionally stop after a couple of words when the bare text is sent;
    # alternate with an explicit instruction wrapper on even attempts.
    if attempt % 2 == 1:
        return config["greeting"]
    return f'Read this aloud exactly, word for word, in full: "{config["greeting"]}"'


async def render_once(config: dict, attempt: int = 1) -> tuple:
    """Return (pcm_bytes, transcript_or_empty)."""
    chunks, heard = [], []
    async with websockets.connect(GEMINI_WS_URL) as ws:
        await ws.send(json.dumps({
            "setup": {
                "model": MODEL,
                "generationConfig": {
                    "temperature": 0,
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config["voice"]}},
                        "languageCode": config["code"],
                    },
                },
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "outputAudioTranscription": {},
            }
        }))
        await ws.recv()
        await ws.send(json.dumps({
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text": user_turn_text(config, attempt)}]}],
                "turnComplete": True,
            }
        }))
        while True:
            data = json.loads(await asyncio.wait_for(ws.recv(), 60))
            sc = data.get("serverContent", {})
            for part in sc.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    chunks.append(base64.b64decode(part["inlineData"]["data"]))
            t = sc.get("outputTranscription", {}).get("text")
            if t:
                heard.append(t)
            if sc.get("turnComplete"):
                break
    return b"".join(chunks), "".join(heard)


async def render_language(name: str, config: dict):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            pcm, heard = await render_once(config, attempt)
        except Exception as e:
            print(f"[{name}] attempt {attempt}: error {type(e).__name__}: {e}")
            continue
        pcm = trim_silence(pcm)
        seconds = len(pcm) / BYTES_PER_SECOND
        ratio = transcript_ratio(config["greeting"], heard) if heard.strip() else None
        print(f"[{name}] attempt {attempt}: {seconds:.2f}s, transcript match="
              f"{'n/a' if ratio is None else f'{ratio:.2f}'}  heard={heard.strip()[:90]!r}")
        if not (MIN_GREETING_SECONDS <= seconds <= MAX_GREETING_SECONDS):
            print(f"[{name}]   rejected: duration outside {MIN_GREETING_SECONDS}-{MAX_GREETING_SECONDS}s")
            continue
        if ratio is not None and ratio < MIN_TRANSCRIPT_RATIO:
            print(f"[{name}]   rejected: transcript does not match the greeting text")
            continue
        return {
            "text": config["greeting"],
            "voice": config["voice"],
            "model": MODEL,
            "sampleRate": 24000,
            "durationSec": round(seconds, 2),
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "audioB64": base64.b64encode(pcm).decode("ascii"),
        }
    return None


async def main(languages):
    # Keep entries for languages we are not regenerating (only if they are still valid JSON).
    existing = {}
    if os.path.exists(GREETINGS_PATH):
        try:
            with open(GREETINGS_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    targets = languages or list(LANGUAGE_CONFIGS)
    unknown = [l for l in targets if l not in LANGUAGE_CONFIGS]
    if unknown:
        sys.exit(f"Unknown language(s): {unknown}. Known: {list(LANGUAGE_CONFIGS)}")

    failed = []
    for name in targets:
        entry = await render_language(name, LANGUAGE_CONFIGS[name])
        if entry:
            existing[name] = entry
        else:
            failed.append(name)
            existing.pop(name, None)  # never keep a stale/bad render; the server falls back to live

    # Drop stale entries for languages that no longer exist.
    existing = {k: v for k, v in existing.items() if k in LANGUAGE_CONFIGS}

    tmp = GREETINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp, GREETINGS_PATH)
    print(f"\nWrote {GREETINGS_PATH}: " + ", ".join(
        f"{k} ({v.get('durationSec', '?')}s)" for k, v in existing.items()))
    if failed:
        print(f"FAILED to render: {failed} (the server will fall back to live greeting for these)")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
