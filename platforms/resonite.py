"""Resonite controller: generic OSC for in-world receivers.

Resonite has no fixed avatar-parameter schema like VRChat - instead, users
build OSC receivers in-world (ProtoFlux OSC nodes). This controller therefore
sends plain OSC values you can wire up however you like:
  expressions: FACES[name] (int) to FACE_OSC_ADDRESS
  chat:        the reply text (string) to RESONITE_CHAT_ADDRESS (optional)
"""

import logging

from pythonosc import udp_client

from .base import PlatformController

logger = logging.getLogger(__name__)


class ResoniteController(PlatformController):
    id = "resonite"
    display_name = "Resonite"
    supports_chat = True  # optional, via RESONITE_CHAT_ADDRESS
    setup_instructions = (
        "In Resonite: build an OSC receiver on your avatar (ProtoFlux OSC nodes) "
        "listening on the OSC port. Expressions arrive as an int on the expression "
        "address (default /avatar/parameters/FaceOSC); if you set a chat address "
        "below, each reply is also sent there as a string for a subtitle/nameplate."
    )

    def __init__(self, *, host: str, port: int, face_address: str, faces: dict,
                 chat_address: str = ""):
        self.faces = faces
        self.face_address = face_address
        self.chat_address = chat_address.strip()
        self.client = udp_client.SimpleUDPClient(host, port)

    async def send_expression(self, name: str) -> None:
        value = self.faces.get(name)
        if value is None:
            logger.warning(f"Expression '{name}' is not in FACES")
            return
        self.client.send_message(self.face_address, value)

    async def send_chat(self, text: str) -> None:
        if self.chat_address:
            self.client.send_message(self.chat_address, text)
