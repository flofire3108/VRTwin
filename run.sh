#!/usr/bin/env bash
# VRTwin one-click launcher for Linux and macOS.
# Creates a virtual environment on first run, installs dependencies, creates the
# virtual audio cables (Linux), then opens the control panel GUI.
# With arguments it runs the CLI instead (e.g. `./run.sh --text`).
set -u
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python was not found. Install Python 3.10-3.12:"
    echo "  Linux:  sudo apt install python3 python3-venv python3-tk  (or your distro's equivalent)"
    echo "  macOS:  brew install python python-tk  (or use the python.org installer)"
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    if ! python3 -m venv .venv; then
        echo "Could not create a virtual environment."
        echo "  Linux: sudo apt install python3-venv"
        exit 1
    fi
fi

# shellcheck disable=SC1091
. .venv/bin/activate

if [ ! -f .venv/.deps_installed ]; then
    echo "Installing dependencies (first run only, this can take a few minutes)..."
    if ! pip install -r requirements.txt; then
        echo
        echo "Dependency installation failed. See the error above."
        echo "PyAudio needs the PortAudio library to build:"
        echo "  Linux:  sudo apt install portaudio19-dev python3-dev  (or your distro's equivalent)"
        echo "  macOS:  brew install portaudio"
        echo "The GUI additionally needs Tk:"
        echo "  Linux:  sudo apt install python3-tk"
        echo "  macOS:  brew install python-tk  (python.org installers include it)"
        echo "Then delete the .venv folder and run this script again."
        exit 1
    fi
    echo ok > .venv/.deps_installed
fi

# Linux: make sure the two virtual audio cables exist (they disappear on
# reboot; recreating them at launch keeps this a one-click start).
#   VRTwin-Ears  = VRChat's sound -> the bot   (bot listens on its monitor)
#   VRTwin-Voice = the bot's voice -> VRChat   (VRChat's mic is its monitor)
if [ "$(uname -s)" = "Linux" ]; then
    if command -v pactl >/dev/null 2>&1; then
        sinks=$(pactl list short sinks 2>/dev/null || true)
        if ! printf '%s' "$sinks" | grep -q vrtwin_ears; then
            pactl load-module module-null-sink sink_name=vrtwin_ears \
                sink_properties=device.description=VRTwin-Ears >/dev/null \
                && echo "Created virtual audio cable: VRTwin-Ears"
        fi
        if ! printf '%s' "$sinks" | grep -q vrtwin_voice; then
            pactl load-module module-null-sink sink_name=vrtwin_voice \
                sink_properties=device.description=VRTwin-Voice >/dev/null \
                && echo "Created virtual audio cable: VRTwin-Voice"
        fi
    else
        echo "Note: pactl not found - skipping virtual audio cable setup."
        echo "The GUI and 'python main.py --text' still work without audio."
    fi
fi

# No arguments: open the control panel GUI. With arguments: run the CLI
# (e.g. `./run.sh --text` or `./run.sh --list-devices`).
if [ $# -eq 0 ]; then
    exec python gui.py
else
    exec python main.py "$@"
fi
