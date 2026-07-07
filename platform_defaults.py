"""Per-OS defaults shared by config.py, settings_schema.py and gui.py.

Side-effect free on purpose: settings_schema/gui must not import config.py
(config's load_dotenv() would leak `.env` values into the GUI's environment,
which the avatar subprocess inherits), so the platform-dependent defaults
live here where both sides can import them.

The "two virtual audio cables" differ per OS:
  Windows: VB-CABLE A+B          -> devices named CABLE-A / CABLE-B
  macOS:   BlackHole 2ch + 16ch  -> two independent loopback devices
  Linux:   PulseAudio/PipeWire null sinks. PortAudio only exposes one "pulse"
           device, so the actual sinks are picked with the PULSE_SOURCE /
           PULSE_SINK environment variables (run.sh creates the sinks).
"""

import sys

_DEFAULTS = {
    "win32": {
        "input_device": "CABLE-A",
        "output_device": "CABLE-B",
        "pulse_source": "",
        "pulse_sink": "",
        "input_device_help": (
            "The recording device that carries VRChat's sound to the bot - normally "
            "'CABLE-A Output'. A device index number also works."
        ),
        "output_device_help": (
            "The playback device that carries the bot's voice to VRChat's microphone - "
            "normally 'CABLE-B Input'. A device index number also works."
        ),
        "mono_font": "Consolas",
    },
    "darwin": {
        "input_device": "BlackHole 2ch",
        "output_device": "BlackHole 16ch",
        "pulse_source": "",
        "pulse_sink": "",
        "input_device_help": (
            "The device that carries the game's sound to the bot - normally "
            "'BlackHole 2ch'. A device index number also works."
        ),
        "output_device_help": (
            "The device that carries the bot's voice to the game's microphone - "
            "normally 'BlackHole 16ch'. A device index number also works."
        ),
        "mono_font": "Menlo",
    },
    "linux": {
        # PortAudio sees PulseAudio/PipeWire as a single "pulse" device; the
        # concrete virtual devices are selected via PULSE_SOURCE / PULSE_SINK.
        "input_device": "pulse",
        "output_device": "pulse",
        "pulse_source": "vrtwin_ears.monitor",
        "pulse_sink": "vrtwin_voice",
        "input_device_help": (
            "Keep 'pulse' and pick the concrete source with 'Pulse source' under "
            "Advanced (run.sh creates the VRTwin-Ears cable). A device index number also works."
        ),
        "output_device_help": (
            "Keep 'pulse' and pick the concrete sink with 'Pulse sink' under "
            "Advanced (run.sh creates the VRTwin-Voice cable). A device index number also works."
        ),
        "mono_font": "monospace",
    },
}


def defaults_for(platform: str) -> dict:
    """Defaults for a sys.platform value; unknown platforms behave like Linux."""
    return _DEFAULTS.get("win32" if platform.startswith("win") else platform, _DEFAULTS["linux"])


_current = defaults_for(sys.platform)

# Hearing mode: Windows can tap an output device directly (WASAPI loopback via
# PyAudioWPatch) so no input cable is needed; other OSes record from a device
# (Linux uses pulse monitor sources, macOS uses BlackHole).
DEFAULT_INPUT_MODE = "loopback" if sys.platform.startswith("win") else "device"

DEFAULT_INPUT_DEVICE = _current["input_device"]
DEFAULT_OUTPUT_DEVICE = _current["output_device"]
DEFAULT_PULSE_SOURCE = _current["pulse_source"]
DEFAULT_PULSE_SINK = _current["pulse_sink"]
INPUT_DEVICE_HELP = _current["input_device_help"]
OUTPUT_DEVICE_HELP = _current["output_device_help"]
MONO_FONT = _current["mono_font"]
