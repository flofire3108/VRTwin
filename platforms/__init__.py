"""Platform controllers: one adapter per supported game/app.

The engine talks to a single PlatformController interface; create_controller()
builds the right one from config. Adding a platform = one new module here plus
a PLATFORM_IDS entry (the GUI dropdown and validation follow automatically).
"""

from .base import PlatformController
from .chilloutvr import ChilloutVRController
from .face_adapter import ControllerFaceController
from .resonite import ResoniteController
from .vrchat import VRChatController
from .vtubestudio import VTubeStudioController

CONTROLLER_CLASSES = {
    cls.id: cls
    for cls in (VRChatController, ChilloutVRController, ResoniteController, VTubeStudioController)
}
PLATFORM_IDS = list(CONTROLLER_CLASSES.keys())


def create_controller(cfg) -> PlatformController:
    """Builds the controller selected by cfg.PLATFORM from a config module."""
    platform_id = cfg.PLATFORM
    if platform_id not in CONTROLLER_CLASSES:
        raise SystemExit(f"Unknown PLATFORM '{platform_id}'. Choose one of: {', '.join(PLATFORM_IDS)}")

    if platform_id == "vrchat":
        return VRChatController(
            host=cfg.OSC_HOST, port=cfg.OSC_PORT, face_address=cfg.FACE_OSC_ADDRESS,
            faces=cfg.FACES, chatbox_max_length=cfg.CHATBOX_MAX_LENGTH,
        )
    if platform_id == "chilloutvr":
        return ChilloutVRController(
            host=cfg.OSC_HOST, port=cfg.OSC_PORT, face_address=cfg.FACE_OSC_ADDRESS,
            faces=cfg.FACES,
        )
    if platform_id == "resonite":
        return ResoniteController(
            host=cfg.OSC_HOST, port=cfg.OSC_PORT, face_address=cfg.FACE_OSC_ADDRESS,
            faces=cfg.FACES, chat_address=cfg.RESONITE_CHAT_ADDRESS,
        )
    return VTubeStudioController(ws_url=cfg.VTS_WS_URL, hotkeys=cfg.VTS_HOTKEYS)
