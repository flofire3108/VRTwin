"""Waiver / disclosure handling for VRTwin.

The EULA text lives in EULA.md. Acceptance is recorded per machine in
waiver_accepted.json (gitignored) with the accepted version, so a future EULA
revision re-triggers the click-through.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).parent
EULA_PATH = APP_DIR / "EULA.md"
ACCEPTANCE_PATH = APP_DIR / "waiver_accepted.json"

WAIVER_VERSION = 1

# Shown persistently in the GUI banner and at CLI startup (1.2 in-app disclosure).
NOTICE_TEXT = (
    "VRTwin is intended for private / friends-only use. Running it in public "
    "instances may violate the host platform's Terms of Service and Community "
    "Guidelines (VRChat explicitly restricts bots)."
)

WAIVER_PROMPT = (
    "VRTwin is licensed for personal, non-commercial use only. You assume all "
    "risk of account action taken by any host platform (VRChat, ChilloutVR, "
    "Resonite, VTube Studio, ...) as a result of running an automated avatar."
)


def eula_text() -> str:
    try:
        return EULA_PATH.read_text(encoding="utf-8")
    except OSError:
        return WAIVER_PROMPT  # fallback if EULA.md is missing


def is_waiver_accepted() -> bool:
    try:
        state = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        return int(state.get("version", 0)) >= WAIVER_VERSION
    except (OSError, ValueError):
        return False


def record_waiver_acceptance() -> None:
    ACCEPTANCE_PATH.write_text(
        json.dumps(
            {"version": WAIVER_VERSION, "accepted_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )


def require_waiver_cli() -> None:
    """Gate for CLI entrypoints: prompt interactively, refuse non-interactively."""
    if is_waiver_accepted():
        return
    if not sys.stdin.isatty():
        raise SystemExit(
            "The VRTwin license agreement has not been accepted on this machine. "
            "Run the GUI (python gui.py) or run this command in a terminal to accept it."
        )
    print("=" * 72)
    print(WAIVER_PROMPT)
    print()
    print(NOTICE_TEXT)
    print()
    print(f"Full terms: {EULA_PATH}")
    print("=" * 72)
    answer = input("Do you accept these terms? [yes/no] ").strip().lower()
    if answer not in ("y", "yes"):
        raise SystemExit("License not accepted.")
    record_waiver_acceptance()
