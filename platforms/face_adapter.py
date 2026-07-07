"""Bridges AIAvatarKit's FaceController interface to a PlatformController.

AIAvatarKit parses `[face:name]` tags from the LLM reply and calls
`set_face(name, duration)`; after `duration` a background thread calls
`reset()`. This adapter forwards both to the active platform controller so the
AI pipeline stays completely platform-agnostic.
"""

import asyncio
import logging

from aiavatar.face import FaceControllerBase

from .base import PlatformController

logger = logging.getLogger(__name__)


class ControllerFaceController(FaceControllerBase):
    def __init__(self, controller: PlatformController, faces: dict, neutral_key: str = "neutral",
                 debug: bool = False):
        super().__init__(debug)
        self.controller = controller
        self.faces = faces
        self.neutral_key = neutral_key
        self._current_face = neutral_key
        self._loop = None  # captured on first set_face; reset() runs on a plain thread

    async def set_face(self, name: str, duration: float):
        if name not in self.faces:
            logger.warning(f"Face '{name}' is not registered")
            return
        self._loop = asyncio.get_running_loop()
        if duration > 0:
            from time import time

            self.subscribe_reset(time() + duration)
        logger.info(f"face: {name}")
        await self.controller.send_expression(name)
        self.current_face = name

    def reset(self):
        logger.info(f"Reset face: {self.neutral_key}")
        self.current_face = self.neutral_key
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.controller.send_expression(self.neutral_key), self._loop
            )
