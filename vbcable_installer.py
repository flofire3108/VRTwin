"""VB-CABLE detection and guided install (Windows).

VB-Audio's licensing covers individual users installing the driver themselves;
redistributing their binaries inside another product requires a separate
agreement. So nothing of VB-Audio ships with VRTwin - instead, this module
downloads the OFFICIAL installer from vb-audio.com on the user's machine and
launches it elevated, which gives the same one-click experience without
redistribution.

Only the single free VB-CABLE is auto-installed (the A+B cables are paid
donationware). With loopback hearing, one cable is all VRTwin needs: the
bot speaks into "CABLE Input" and the game uses "CABLE Output" as its mic.
"""

import logging
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Official VB-Audio download (never bundled). Overridable if the pack number changes.
VBCABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"
SETUP_EXE = "VBCABLE_Setup_x64.exe"


def cable_present() -> bool:
    """True if any VB-Audio cable device is visible to the audio system."""
    try:
        import pyaudio

        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                name = p.get_device_info_by_index(i).get("name", "")
                if "CABLE" in name.upper() or "VB-AUDIO" in name.upper():
                    return True
            return False
        finally:
            p.terminate()
    except Exception:
        return False


def download_and_run_installer(log=logger.info) -> bool:
    """Download the official VB-CABLE zip and launch its installer elevated.

    Returns True when the installer was launched (the driver is only active
    after the user finishes the wizard AND reboots). Windows only.
    """
    if not sys.platform.startswith("win"):
        log("VB-CABLE auto-install is Windows-only. Linux: use ./run.sh; macOS: install BlackHole.")
        return False

    workdir = Path(tempfile.mkdtemp(prefix="vbcable_"))
    zip_path = workdir / "vbcable.zip"
    log(f"Downloading the official VB-CABLE installer from {VBCABLE_URL} ...")
    urllib.request.urlretrieve(VBCABLE_URL, zip_path)

    log("Extracting...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(workdir)

    setup = workdir / SETUP_EXE
    if not setup.exists():
        # fall back to any setup exe in the pack (name could change)
        candidates = list(workdir.glob("VBCABLE_Setup*.exe"))
        if not candidates:
            log("Installer executable not found in the downloaded pack.")
            return False
        setup = candidates[0]

    log("Launching the VB-CABLE installer (Windows will ask for administrator rights)...")
    import ctypes

    # ShellExecuteW with "runas" = run elevated; returns >32 on success
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(setup), None,
                                                 str(workdir), 1)
    if result <= 32:
        log(f"Could not launch the installer (code {result}).")
        return False

    log("In the installer window: click 'Install Driver', then REBOOT your PC. "
        "After the reboot, VRTwin will find the CABLE devices.")
    return True
