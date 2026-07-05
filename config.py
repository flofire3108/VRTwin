"""Configuration for the VRTwin AI avatar.

All values are loaded from a `.env` file next to this script (see `.env.example`).
Anything not set in `.env` falls back to the defaults below.
"""

import json
import os
from typing import Union

from dotenv import load_dotenv

load_dotenv()


def _get_device(name: str, default: str) -> Union[int, str]:
    """Audio devices can be given as an index (e.g. `7`) or a name substring
    (e.g. `CABLE-A`). AIAvatarKit accepts both."""
    value = os.getenv(name, default).strip()
    try:
        return int(value)
    except ValueError:
        return value


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- OpenRouter powers everything: brain (LLM), ears (STT) and voice (TTS) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")

# --- Voice (ears and mouth) via OpenRouter's audio APIs ---
STT_MODEL = os.getenv("STT_MODEL", "openai/gpt-4o-transcribe")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")
TTS_MODEL = os.getenv("TTS_MODEL", "google/gemini-3.1-flash-tts-preview")
TTS_VOICE = os.getenv("TTS_VOICE", "Kore")
# Gemini 3.1 Flash TTS outputs PCM at 24 kHz / 16-bit / mono.
TTS_SAMPLE_RATE = int(os.getenv("TTS_SAMPLE_RATE", "24000"))

# --- Audio devices (VB-CABLE virtual cables) ---
# INPUT_DEVICE  = where the bot LISTENS  (VRChat's speaker output -> CABLE-A)
# OUTPUT_DEVICE = where the bot SPEAKS   (CABLE-B -> VRChat's microphone)
INPUT_DEVICE = _get_device("INPUT_DEVICE", "CABLE-A")
OUTPUT_DEVICE = _get_device("OUTPUT_DEVICE", "CABLE-B")

# Voice activity detection: raise towards 0 (e.g. -40) if background noise
# triggers the bot, lower (e.g. -60) if it does not hear quiet players.
VAD_VOLUME_DB_THRESHOLD = float(os.getenv("VAD_VOLUME_DB_THRESHOLD", "-50"))

# --- VRChat OSC ---
OSC_HOST = os.getenv("OSC_HOST", "127.0.0.1")
OSC_PORT = int(os.getenv("OSC_PORT", "9000"))
FACE_OSC_ADDRESS = os.getenv("FACE_OSC_ADDRESS", "/avatar/parameters/FaceOSC")
CHATBOX_ENABLED = _get_bool("CHATBOX_ENABLED", True)

# Expression name -> value of the avatar's synced int parameter (FaceOSC).
# Must match the animations set up on the avatar in Unity.
# Override with FACES in .env as JSON, e.g. {"neutral": 0, "joy": 1}
FACES = json.loads(
    os.getenv(
        "FACES",
        '{"neutral": 0, "joy": 1, "angry": 2, "sorrow": 3, "fun": 4, "surprise": 5}',
    )
)

# --- Character ---
CHARACTER_NAME = os.getenv("CHARACTER_NAME", "Twin")

_DEFAULT_PERSONA = (
    f"You are {CHARACTER_NAME}, a friendly AI living inside VRChat as an avatar. "
    "You chat with the players standing around you. Your replies are spoken out "
    "loud through text-to-speech, so answer the way a person talks: casual, warm, "
    "and SHORT - one to three sentences. Never use markdown, lists, emoji, or "
    "stage directions. If you did not catch what someone said, just ask them to "
    "repeat it."
)
PERSONA = os.getenv("PERSONA", _DEFAULT_PERSONA)


def build_system_prompt() -> str:
    """Persona + AIAvatarKit face-tag instructions for the configured expressions."""
    face_names = [name for name in FACES.keys()]
    return (
        f"{PERSONA}\n\n"
        "## Facial expressions\n"
        "You can control your avatar's face. Insert a face tag at the beginning of "
        "a sentence to set your expression while saying it. Available faces: "
        f"{', '.join(face_names)}.\n"
        "Use the exact format [face:name]. Examples:\n"
        "[face:joy]Hey, welcome back! [face:fun]Wanna see something cool?\n"
        "[face:sorrow]Aw, that's rough...\n"
        "Only use the faces listed above. Use them naturally - not in every sentence."
    )


DEBUG = _get_bool("DEBUG", False)
