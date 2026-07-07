"""VTube Studio controller: expressions via the VTS WebSocket API.

Structurally different from the OSC platforms: VTS speaks JSON over a
WebSocket (default ws://127.0.0.1:8001). On first connect the plugin requests
an authentication token - VTube Studio pops up an "Allow plugin?" dialog the
user must approve once; the token is cached in vts_token.json for next time.

Expressions are triggered as VTS hotkeys: VTS_HOTKEYS maps each face name from
FACES to the name (or unique ID) of a hotkey you created in VTube Studio.
Failures are logged and never crash the voice loop.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

import websockets

from .base import PlatformController

logger = logging.getLogger(__name__)

TOKEN_PATH = Path(__file__).parent.parent / "vts_token.json"
PLUGIN_NAME = "VRTwin"
PLUGIN_DEVELOPER = "VRTwin"


class VTubeStudioController(PlatformController):
    id = "vtubestudio"
    display_name = "VTube Studio"
    supports_chat = False
    setup_instructions = (
        "In VTube Studio: enable 'Start API' in the settings (default port 8001). "
        "Create a hotkey per expression (e.g. an expression toggle named 'joy') and "
        "map face names to hotkey names in 'VTS hotkeys' below. On the first start, "
        "VTube Studio shows an 'Allow plugin?' popup - click Allow once."
    )

    def __init__(self, *, ws_url: str, hotkeys: dict, auth_timeout: float = 60.0):
        self.ws_url = ws_url
        self.hotkeys = hotkeys  # face name -> VTS hotkey name or unique ID
        self.auth_timeout = auth_timeout
        self.ws = None
        self._send_lock = asyncio.Lock()

    # --- protocol helpers ---

    @staticmethod
    def _message(message_type: str, data: dict = None) -> str:
        return json.dumps({
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": uuid.uuid4().hex[:16],
            "messageType": message_type,
            "data": data or {},
        })

    async def _request(self, message_type: str, data: dict = None, timeout: float = 10.0) -> dict:
        await self.ws.send(self._message(message_type, data))
        reply = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
        if reply.get("messageType") == "APIError":
            raise RuntimeError(f"VTS APIError: {reply.get('data', {}).get('message')}")
        return reply

    def _load_token(self) -> str:
        try:
            return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))["token"]
        except (OSError, ValueError, KeyError):
            return ""

    # --- lifecycle ---

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.ws_url)
        token = self._load_token()
        if not token:
            token = await self._request_new_token()
        if not await self._authenticate(token):
            # cached token was revoked - ask for a fresh one and retry
            token = await self._request_new_token()
            if not await self._authenticate(token):
                raise RuntimeError("VTube Studio rejected the plugin authentication.")
        logger.info("Connected and authenticated with VTube Studio.")

    async def _request_new_token(self) -> str:
        logger.info("Requesting a plugin token - click 'Allow' in VTube Studio...")
        reply = await self._request(
            "AuthenticationTokenRequest",
            {"pluginName": PLUGIN_NAME, "pluginDeveloper": PLUGIN_DEVELOPER},
            timeout=self.auth_timeout,  # waits for the user to click Allow
        )
        token = reply["data"]["authenticationToken"]
        TOKEN_PATH.write_text(json.dumps({"token": token}), encoding="utf-8")
        return token

    async def _authenticate(self, token: str) -> bool:
        reply = await self._request(
            "AuthenticationRequest",
            {"pluginName": PLUGIN_NAME, "pluginDeveloper": PLUGIN_DEVELOPER,
             "authenticationToken": token},
        )
        return bool(reply["data"].get("authenticated"))

    async def disconnect(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None

    # --- actions ---

    async def send_expression(self, name: str) -> None:
        hotkey = self.hotkeys.get(name)
        if not hotkey:
            logger.warning(f"Face '{name}' has no VTS hotkey mapped (VTS_HOTKEYS)")
            return
        async with self._send_lock:  # one request/response in flight at a time
            for attempt in (1, 2):
                try:
                    if self.ws is None:
                        await self.connect()
                    await self._request("HotkeyTriggerRequest", {"hotkeyID": hotkey})
                    return
                except Exception as ex:
                    logger.warning(f"VTS hotkey '{hotkey}' failed (attempt {attempt}): {ex}")
                    self.ws = None  # force reconnect on the retry
