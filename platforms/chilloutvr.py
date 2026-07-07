"""ChilloutVR controller: expressions over OSC.

CVR's built-in OSC support mirrors VRChat's avatar-parameter scheme
(/avatar/parameters/<name>), so expressions work the same way: FACES[name] as
an int to FACE_OSC_ADDRESS. CVR's OSC has no chatbox endpoint, so send_chat is
a no-op.
"""

import logging

from pythonosc import udp_client

from .base import PlatformController

logger = logging.getLogger(__name__)


class ChilloutVRController(PlatformController):
    id = "chilloutvr"
    display_name = "ChilloutVR"
    supports_chat = False
    setup_instructions = (
        "In ChilloutVR: enable OSC in the settings (Implementation -> OSC). The "
        "avatar needs a synced int parameter (default 'FaceOSC') whose values switch "
        "face animations, exactly like the VRChat setup. ChilloutVR's OSC has no "
        "chatbox, so replies are voice-only."
    )

    def __init__(self, *, host: str, port: int, face_address: str, faces: dict):
        self.faces = faces
        self.face_address = face_address
        self.client = udp_client.SimpleUDPClient(host, port)
        self._warned_chat = False

    async def send_expression(self, name: str) -> None:
        value = self.faces.get(name)
        if value is None:
            logger.warning(f"Expression '{name}' is not in FACES")
            return
        self.client.send_message(self.face_address, value)

    async def send_chat(self, text: str) -> None:
        if not self._warned_chat:
            logger.info("ChilloutVR has no OSC chatbox - chat mirroring is disabled.")
            self._warned_chat = True
