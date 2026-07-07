"""Platform controller interface.

The AI pipeline (STT -> LLM -> TTS) is platform-agnostic: the LLM always emits
`[face:joy]`-style tags using the expression names from config.FACES. A
PlatformController is the only piece that knows how to translate an expression
*name* or a chat line into what the target platform expects (an OSC int, a
WebSocket JSON payload, ...). Supporting a new game means writing one new
subclass — the engine never changes.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PlatformController(ABC):
    """One target platform (VRChat, ChilloutVR, Resonite, VTube Studio, ...)."""

    # Identifier used in the PLATFORM setting, e.g. "vrchat"
    id: str = ""
    # Human name shown in the GUI dropdown
    display_name: str = ""
    # Shown in the GUI's Platform tab so users know what to enable in the game
    setup_instructions: str = ""
    # Whether send_chat does anything on this platform (drives the GUI hint)
    supports_chat: bool = False

    async def connect(self) -> None:
        """Establish the connection. Called once before the avatar starts."""

    async def disconnect(self) -> None:
        """Tear down the connection. Called when the avatar stops."""

    @abstractmethod
    async def send_expression(self, name: str) -> None:
        """Show the expression with this (platform-agnostic) name."""

    async def send_chat(self, text: str) -> None:
        """Show a chat/subtitle message, if the platform has such a thing."""
