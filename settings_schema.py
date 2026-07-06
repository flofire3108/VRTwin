"""Schema of every VRTwin setting: defaults, types, and human explanations.

This is the single source of truth the GUI (gui.py) renders from. Each entry
mirrors one option in config.py (same env key, same default) — a consistency
test guards that. Values are stored in `.env`; anything left at its default is
removed from `.env` so config.py's defaults apply.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import dotenv_values, set_key, unset_key

import platform_defaults

ENV_PATH = Path(__file__).parent / ".env"

# Widget kinds understood by the GUI:
#   text, secret, bool, int, float, float_optional (empty = auto),
#   slider (min/max/step), choice (editable dropdown), multiline, json,
#   device_in, device_out (audio device dropdowns)


@dataclass(frozen=True)
class Setting:
    key: str
    default: str
    kind: str
    label: str
    help: str
    section: str
    min: float = 0.0
    max: float = 1.0
    step: float = 1.0
    unit: str = ""
    choices: List[str] = field(default_factory=list)
    placeholder: str = ""


SECTIONS = ["Keys & Models", "Hearing & Voice", "Audio Devices", "VRChat", "Character", "Advanced"]

GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

SETTINGS: List[Setting] = [
    # --- Keys & Models ---
    Setting("OPENROUTER_API_KEY", "", "secret", "OpenRouter API key",
            "The one key that powers everything (brain, ears, voice). Get it at openrouter.ai/settings/keys.",
            "Keys & Models", placeholder="sk-or-..."),
    Setting("OPENROUTER_MODEL", "anthropic/claude-sonnet-5", "text", "Brain model (LLM)",
            "The model that thinks up the replies. Any OpenRouter chat model id works.",
            "Keys & Models"),
    Setting("OPENROUTER_REASONING_ENABLED", "false", "bool", "Let the brain reason before replying",
            "ON = smarter but slower and more expensive replies. OFF is best for real-time voice chat.",
            "Keys & Models"),
    Setting("OPENROUTER_TEMPERATURE", "", "float_optional", "Reply randomness (temperature)",
            "Empty = the model's own default. 0 = predictable, around 1.0-1.5 = more varied and creative.",
            "Keys & Models", placeholder="auto"),
    Setting("STT_MODEL", "openai/gpt-4o-transcribe", "text", "Ears model (speech-to-text)",
            "The OpenRouter model that converts player speech into text.",
            "Keys & Models"),
    Setting("TTS_MODEL", "google/gemini-3.1-flash-tts-preview", "text", "Voice model (text-to-speech)",
            "The OpenRouter model that speaks the replies out loud.",
            "Keys & Models"),
    Setting("TTS_VOICE", "Kore", "choice", "Voice",
            "Which voice the avatar speaks with. Gemini prebuilt voices; type any other name your TTS model supports.",
            "Keys & Models", choices=GEMINI_VOICES),
    Setting("TTS_STYLE", "", "text", "Voice style",
            "Overall speaking style, e.g. 'warm and friendly' or 'energetic and upbeat'. Leave empty for neutral.",
            "Keys & Models", placeholder="(neutral)"),
    Setting("TTS_PACE", "", "text", "Voice pace",
            "Speaking pace, e.g. 'slow and deliberate' or 'brisk energetic'. Leave empty for natural pace.",
            "Keys & Models", placeholder="(natural)"),
    Setting("TTS_ACCENT", "", "text", "Voice accent",
            "Regional accent, e.g. 'American English' or 'British English from London'. Leave empty for model default.",
            "Keys & Models", placeholder="(model default)"),
    Setting("STT_LANGUAGE", "en", "text", "Spoken language",
            "Language hint for speech recognition, e.g. en, nl, ja. Improves accuracy.",
            "Keys & Models"),

    # --- Hearing & Voice ---
    Setting("VAD_VOLUME_DB_THRESHOLD", "-50", "slider", "Microphone sensitivity",
            "How loud a sound must be before the bot listens. Drag right (towards -20) to ignore background noise, left (towards -90) to hear quiet players.",
            "Hearing & Voice", min=-90, max=-20, step=1, unit="dB"),
    Setting("VAD_SILENCE_DURATION_THRESHOLD", "0.5", "slider", "End-of-sentence pause",
            "How many seconds of silence mean the player finished talking. Longer = fewer interruptions, slower replies.",
            "Hearing & Voice", min=0.1, max=2.0, step=0.1, unit="s"),
    Setting("CANCEL_ECHO", "true", "bool", "Ignore own voice (echo cancel)",
            "Stops the bot from hearing and answering itself while it is speaking. Keep ON.",
            "Hearing & Voice"),
    Setting("AUDIO_SAMPLE_RATE", "16000", "int", "Capture sample rate",
            "Sample rate (Hz) used to record audio for voice detection and speech-to-text. 16000 is standard.",
            "Hearing & Voice"),
    Setting("TTS_SAMPLE_RATE", "24000", "int", "Voice sample rate",
            "Sample rate (Hz) of the TTS audio. Gemini 3.1 Flash outputs 24000; only change for a different TTS model.",
            "Hearing & Voice"),
    Setting("STT_MIN_DATA_LENGTH", "4096", "int", "Minimum utterance size",
            "Audio snippets shorter than this (bytes) are skipped as too short to transcribe. Raise to ignore coughs and clicks.",
            "Hearing & Voice"),
    Setting("STT_TIMEOUT", "10.0", "float", "Hearing timeout",
            "Seconds to wait for the speech-to-text service before giving up on an utterance.",
            "Hearing & Voice"),
    Setting("TTS_TIMEOUT", "30.0", "float", "Voice timeout",
            "Seconds to wait for the text-to-speech service before giving up on a reply.",
            "Hearing & Voice"),
    Setting("TTS_CACHE_DIR", "", "text", "Voice cache folder",
            "Folder to cache spoken lines so repeated replies are not re-synthesized. Empty = caching off.",
            "Hearing & Voice", placeholder="(disabled)"),

    # --- Audio Devices (defaults depend on the OS, see platform_defaults.py) ---
    Setting("INPUT_DEVICE", platform_defaults.DEFAULT_INPUT_DEVICE, "device_in",
            "Bot's ears (input device)",
            platform_defaults.INPUT_DEVICE_HELP,
            "Audio Devices"),
    Setting("OUTPUT_DEVICE", platform_defaults.DEFAULT_OUTPUT_DEVICE, "device_out",
            "Bot's mouth (output device)",
            platform_defaults.OUTPUT_DEVICE_HELP,
            "Audio Devices"),

    # --- VRChat ---
    Setting("OSC_HOST", "127.0.0.1", "text", "VRChat address (OSC host)",
            "Where VRChat is running. Keep 127.0.0.1 when VRChat runs on this PC.",
            "VRChat"),
    Setting("OSC_PORT", "9000", "int", "VRChat OSC port",
            "VRChat listens for OSC messages on this port. 9000 is VRChat's default.",
            "VRChat"),
    Setting("FACE_OSC_ADDRESS", "/avatar/parameters/FaceOSC", "text", "Expression parameter address",
            "The avatar's synced int parameter that switches face animations. Must match your avatar's animator setup.",
            "VRChat"),
    Setting("FACES", '{"neutral": 0, "joy": 1, "angry": 2, "sorrow": 3, "fun": 4, "surprise": 5}',
            "json", "Expressions (name -> value)",
            "JSON mapping of expression names to the parameter values your avatar's animator expects. The AI is told exactly these names.",
            "VRChat"),
    Setting("FACE_NEUTRAL_KEY", "neutral", "text", "Resting expression",
            "Which expression (from the list above) the avatar returns to after emoting.",
            "VRChat"),
    Setting("CHATBOX_ENABLED", "true", "bool", "Show replies in chatbox",
            "Also displays every spoken reply as a VRChat chatbox bubble so players can read it.",
            "VRChat"),
    Setting("CHATBOX_MAX_LENGTH", "144", "int", "Chatbox character limit",
            "Replies are trimmed to this many characters for the chatbox. VRChat's limit is 144.",
            "VRChat"),

    # --- Character ---
    Setting("CHARACTER_NAME", "Twin", "text", "Character name",
            "The AI's name - used in its default personality and in the console log.",
            "Character"),
    Setting("PERSONA", "", "multiline", "Personality",
            "Describe who the AI is and how it talks. Empty = a friendly default persona based on the character name. Expression instructions are added automatically.",
            "Character", placeholder="(auto: friendly VRChat persona)"),

    # --- Advanced ---
    Setting("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1", "text", "OpenRouter base URL",
            "API endpoint for all OpenRouter calls. Only change for a proxy or compatible gateway.",
            "Advanced"),
    Setting("HTTP_MAX_CONNECTIONS", "100", "int", "Max HTTP connections",
            "Connection pool size shared by the hearing and voice clients.",
            "Advanced"),
    Setting("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20", "int", "Max keep-alive connections",
            "How many idle HTTP connections are kept open for reuse.",
            "Advanced"),
    Setting("DB_CONNECTION_STR", "aiavatar.db", "text", "Conversation history file",
            "SQLite file storing the conversation memory. Give each bot instance its own file.",
            "Advanced"),
    Setting("HISTORY_MAX_MESSAGES", "30", "int", "Memory length (messages)",
            "How many past messages the brain sees each reply. Lower = cheaper, faster and less likely to mix up different players; higher = longer memory.",
            "Advanced"),
    Setting("HISTORY_TIMEOUT_SECONDS", "3600", "int", "Memory time limit",
            "Forget conversation history older than this many seconds. 0 = never forget by time.",
            "Advanced", unit="s"),
    Setting("LLM_MAX_TOKENS", "200", "int", "Max reply length (tokens)",
            "Hard cap on how long a spoken reply can be. Keeps replies short, fast and cheap.",
            "Advanced"),
    Setting("LLM_OPTION_SPLIT_THRESHOLD", "24", "int", "Start-speaking chunk size",
            "The reply is spoken in chunks; a chunk is flushed to the voice early once it passes this many characters at a natural pause. Lower = starts talking sooner in smaller pieces.",
            "Advanced"),
    Setting("VOICE_RECORDER_ENABLED", "false", "bool", "Record heard voices",
            "Saves every recognized utterance as a WAV file - useful to debug what the bot hears.",
            "Advanced"),
    Setting("VOICE_RECORDER_DIR", "recorded_voices", "text", "Voice recordings folder",
            "Where the recorded WAV files go when the recorder is on.",
            "Advanced"),
    Setting("PULSE_SOURCE", platform_defaults.DEFAULT_PULSE_SOURCE, "text", "Pulse source (Linux)",
            "Linux only: which PulseAudio/PipeWire source the 'pulse' input device uses. run.sh creates 'vrtwin_ears.monitor'. Empty = system default microphone.",
            "Advanced", placeholder="(system default)"),
    Setting("PULSE_SINK", platform_defaults.DEFAULT_PULSE_SINK, "text", "Pulse sink (Linux)",
            "Linux only: which PulseAudio/PipeWire sink the 'pulse' output device uses. run.sh creates 'vrtwin_voice'. Empty = system default speakers.",
            "Advanced", placeholder="(system default)"),
    Setting("DEBUG", "false", "bool", "Debug logging",
            "Verbose logs for every pipeline step. Turn on when troubleshooting.",
            "Advanced"),
]

_BY_KEY = {s.key: s for s in SETTINGS}

_TRUE_VALUES = ("1", "true", "yes", "on")


def _canonical(setting: Setting, value: str) -> str:
    value = ("" if value is None else str(value)).strip()
    if setting.kind == "bool":
        return "true" if value.lower() in _TRUE_VALUES else "false"
    return value


def load_values() -> dict:
    """Current value of every setting: `.env` where set, defaults elsewhere."""
    env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return {
        s.key: _canonical(s, env[s.key]) if env.get(s.key) is not None else s.default
        for s in SETTINGS
    }


def validate(setting: Setting, value: str) -> Optional[str]:
    """Returns an error message, or None when the value is acceptable."""
    value = value.strip()
    if setting.kind == "int" or (setting.kind == "slider" and setting.step >= 1):
        try:
            int(float(value))
        except ValueError:
            return f"{setting.label}: enter a whole number."
    elif setting.kind in ("float", "slider"):
        try:
            float(value)
        except ValueError:
            return f"{setting.label}: enter a number."
    elif setting.kind == "float_optional" and value:
        try:
            float(value)
        except ValueError:
            return f"{setting.label}: enter a number or leave empty for auto."
    elif setting.kind == "json":
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict) or not parsed or not all(
                isinstance(k, str) and isinstance(v, int) for k, v in parsed.items()
            ):
                raise ValueError
        except ValueError:
            return f'{setting.label}: must be JSON like {{"neutral": 0, "joy": 1}}.'
    return None


def validate_all(values: dict) -> List[str]:
    errors = [validate(_BY_KEY[k], v) for k, v in values.items() if k in _BY_KEY]
    errors = [e for e in errors if e]
    # Cross-field: the resting expression must exist in the faces map
    try:
        faces = json.loads(values.get("FACES", "") or "{}")
        neutral = (values.get("FACE_NEUTRAL_KEY") or "").strip()
        if isinstance(faces, dict) and faces and neutral and neutral not in faces:
            errors.append(f"Resting expression: '{neutral}' is not one of the expressions above.")
    except ValueError:
        pass  # already reported by the FACES validator
    return errors


def save_values(values: dict) -> None:
    """Persist to `.env`: only values that differ from the defaults are written;
    values equal to their default are removed so config.py's defaults apply."""
    ENV_PATH.touch(exist_ok=True)
    existing = dotenv_values(ENV_PATH)
    for s in SETTINGS:
        if s.key not in values:
            continue
        value = _canonical(s, values[s.key])
        if value == s.default:
            if s.key in existing:
                unset_key(str(ENV_PATH), s.key)
        else:
            set_key(str(ENV_PATH), s.key, value)
