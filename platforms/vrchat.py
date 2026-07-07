"""VRChat controller: expressions and chatbox over OSC.

Expressions: sends FACES[name] as an int to the avatar's synced parameter
(FACE_OSC_ADDRESS, default /avatar/parameters/FaceOSC). Chat: VRChat's chatbox
via /chatbox/input. Requires OSC enabled in VRChat's Action Menu.
"""

import logging

from pythonosc import udp_client

from .base import PlatformController

logger = logging.getLogger(__name__)


class VRChatController(PlatformController):
    id = "vrchat"
    display_name = "VRChat"
    supports_chat = True
    setup_instructions = (
        "In VRChat (on the bot account): open the Action Menu (hold R on desktop) -> "
        "Options -> OSC -> Enable. The avatar needs a synced int parameter (default "
        "'FaceOSC') whose values switch face animations - see the README. Replies "
        "also appear in the chatbox."
    )

    def __init__(self, *, host: str, port: int, face_address: str, faces: dict,
                 chatbox_max_length: int = 144):
        self.faces = faces
        self.face_address = face_address
        self.chatbox_max_length = chatbox_max_length
        self.client = udp_client.SimpleUDPClient(host, port)

    async def send_expression(self, name: str) -> None:
        value = self.faces.get(name)
        if value is None:
            logger.warning(f"Expression '{name}' is not in FACES")
            return
        self.client.send_message(self.face_address, value)

    async def send_chat(self, text: str) -> None:
        # /chatbox/input: [text, send immediately, no notification sound]
        self.client.send_message("/chatbox/input", [text[: self.chatbox_max_length], True, False])
