"""VRTwin - run a VRChat account as an AI avatar.

Pipeline (all wired through AIAvatarKit, all AI on one OpenRouter key):
  VRChat audio -> VB-CABLE A -> voice detection
  -> OpenRouter STT (openai/gpt-4o-transcribe)
  -> Claude Sonnet 5 via OpenRouter (reasoning disabled)
  -> OpenRouter TTS (google/gemini-3.1-flash-tts-preview)
  -> VB-CABLE B -> VRChat microphone
  plus [face:...] tags -> OSC -> avatar expressions, and replies mirrored
  to the VRChat chatbox.

Usage:
  python main.py                 run the avatar
  python main.py --list-devices  print audio device indices/names
  python main.py --text          console chat mode (no audio/VRChat needed)
"""

import argparse
import asyncio
import logging
import warnings

# aiavatar.adapter.local is deprecated upstream but is the right fit for a
# single-PC setup; the version is pinned in requirements.txt.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiavatar")

from aiavatar.sts.llm.chatgpt import ChatGPTService

import config
from context_manager import LimitedSQLiteContextManager


def build_llm() -> ChatGPTService:
    """Claude Sonnet 5 through OpenRouter's OpenAI-compatible endpoint.

    OpenRouter's `reasoning` body parameter is sent via extra_body to turn
    Claude's thinking off entirely, so replies come back fast and cheap. History
    is capped and replies are length-limited to keep the voice loop snappy.
    """
    if not config.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in.")

    llm = ChatGPTService(
        openai_api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        model=config.OPENROUTER_MODEL,
        system_prompt=config.build_system_prompt(),
        temperature=config.OPENROUTER_TEMPERATURE,
        extra_body={"reasoning": {"enabled": config.OPENROUTER_REASONING_ENABLED}},
        # aiavatar's tool filtering sends the OpenAI-only `allowed_tools` tool_choice,
        # which non-OpenAI providers on OpenRouter reject.
        enable_tool_filtering=False,
        context_manager=LimitedSQLiteContextManager(
            db_path=config.DB_CONNECTION_STR,
            context_timeout=config.HISTORY_TIMEOUT_SECONDS,
            max_messages=config.HISTORY_MAX_MESSAGES,
        ),
        option_split_threshold=config.LLM_OPTION_SPLIT_THRESHOLD,
        debug=config.DEBUG,
    )

    @llm.edit_chat_completion_params
    def _cap_max_tokens(params, context_id, user_id):
        params["max_tokens"] = config.LLM_MAX_TOKENS

    return llm


async def start_mcp(llm):
    """Connect the configured MCP servers and hand their tools to the brain.
    Returns the manager (stop it on shutdown), or None when MCP is off."""
    if not config.MCP_ENABLED:
        return None
    from mcp_manager import MCPManager

    mcp = MCPManager(config.MCP_CONFIG_PATH, tool_timeout=config.MCP_TOOL_TIMEOUT)
    await mcp.start()
    tool_names = mcp.register_tools(llm)
    if tool_names:
        llm.system_prompt += (
            "\n\n## Tools\n"
            f"You have these tools: {', '.join(tool_names)}. Use them whenever a "
            "request needs live information, the web, the time, memory, or files. "
            "Your replies are spoken out loud, so before calling a tool say one "
            "short natural line like 'Let me check that.' and keep the answer "
            "you give afterwards just as short as usual."
        )
        print(f"MCP: {len(tool_names)} tools from {len(mcp.sessions)} server(s) ready.")
    return mcp


def list_devices() -> None:
    import pyaudio

    p = pyaudio.PyAudio()
    devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
    p.terminate()
    if not devices:
        print("No audio devices found. Are the virtual audio cables installed?")
        print("(Windows: VB-CABLE A+B, then reboot. Linux: run via ./run.sh. macOS: BlackHole.)")
        return
    print("==== Input devices (pick the one for INPUT_DEVICE, e.g. CABLE-A Output) ====")
    for i, d in enumerate(devices):
        if d.get("maxInputChannels", 0) > 0:
            print(f'  {i}: {d["name"]}')
    print("==== Output devices (pick the one for OUTPUT_DEVICE, e.g. CABLE-B Input) ====")
    for i, d in enumerate(devices):
        if d.get("maxOutputChannels", 0) > 0:
            print(f'  {i}: {d["name"]}')


async def text_chat() -> None:
    """Type-to-chat console mode: tests the OpenRouter/Sonnet 5 pipeline and the
    [face:...] expression tags without VRChat or audio devices."""
    llm = build_llm()
    mcp = await start_mcp(llm)
    context_id = "console"
    user_id = "console_user"
    print(f"Console chat with {config.CHARACTER_NAME} ({config.OPENROUTER_MODEL}). Ctrl+C to quit.")
    try:
        while True:
            try:
                text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not text:
                continue
            messages = await llm.compose_messages(context_id, user_id, text)
            response_text = ""
            print(f"{config.CHARACTER_NAME}: ", end="", flush=True)
            async for chunk in llm.get_llm_stream_response(context_id, user_id, messages):
                if chunk.tool_call and not chunk.tool_call.result:
                    print(f"\n[tool: {chunk.tool_call.name}]", flush=True)
                elif chunk.text:
                    print(chunk.text, end="", flush=True)
                    response_text += chunk.text
            print()
            await llm.update_context(context_id, user_id, messages, response_text)
    finally:
        if mcp:
            await mcp.stop()


class StatusSTT:
    """Wraps the STT recognizer to emit pipeline status before transcribing."""

    def __new__(cls, **kwargs):
        from openrouter_audio import OpenRouterSpeechRecognizer

        class _StatusSTT(OpenRouterSpeechRecognizer):
            async def transcribe(self, data: bytes) -> str:
                print("STATUS:transcribing", flush=True)
                return await super().transcribe(data)

        return _StatusSTT(**kwargs)


class VRTwinAvatar:
    """Thin wrapper around AIAvatar that adds the interrupt gate."""

    def __new__(cls, **kwargs):
        from aiavatar.adapter.local.client import AIAvatar

        class _VRTwinAvatar(AIAvatar):
            def __init__(self, **kw):
                super().__init__(**kw)
                self._is_processing = False

            @property
            def _is_busy(self):
                return self._is_processing or self.audio_player.is_playing

            async def send_microphone_worker(self, session_id: str):
                async for data in self.audio_recorder.start_stream():
                    if not self.cancel_echo or not self.audio_player.is_playing:
                        if config.INTERRUPT_ENABLED or not self._is_busy:
                            await self.send_microphone_data(data, session_id)

        return _VRTwinAvatar(**kwargs)


async def run_avatar() -> None:
    from pythonosc import udp_client

    from aiavatar.device import AudioDevice
    from aiavatar.face.vrchat import VRChatFaceController

    from openrouter_audio import OpenRouterSpeechSynthesizer

    llm = build_llm()
    mcp = await start_mcp(llm)

    app = VRTwinAvatar(
        llm=llm,
        stt=StatusSTT(
            openrouter_api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            model=config.STT_MODEL,
            language=config.STT_LANGUAGE,
            sample_rate=config.AUDIO_SAMPLE_RATE,
            min_data_length=config.STT_MIN_DATA_LENGTH,
            max_connections=config.HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=config.HTTP_MAX_KEEPALIVE_CONNECTIONS,
            timeout=config.STT_TIMEOUT,
            debug=config.DEBUG,
        ),
        tts=OpenRouterSpeechSynthesizer(
            openrouter_api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            model=config.TTS_MODEL,
            voice=config.TTS_VOICE,
            pcm_sample_rate=config.TTS_SAMPLE_RATE,
            tts_style=config.TTS_STYLE,
            tts_pace=config.TTS_PACE,
            tts_accent=config.TTS_ACCENT,
            max_connections=config.HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=config.HTTP_MAX_KEEPALIVE_CONNECTIONS,
            timeout=config.TTS_TIMEOUT,
            cache_dir=config.TTS_CACHE_DIR,
            debug=config.DEBUG,
        ),
        face_controller=VRChatFaceController(
            osc_address=config.FACE_OSC_ADDRESS,
            faces=config.FACES,
            neutral_key=config.FACE_NEUTRAL_KEY,
            host=config.OSC_HOST,
            port=config.OSC_PORT,
            debug=config.DEBUG,
        ),
        audio_devices=AudioDevice(
            input_device=config.INPUT_DEVICE,
            output_device=config.OUTPUT_DEVICE,
        ),
        vad_volume_db_threshold=config.VAD_VOLUME_DB_THRESHOLD,
        vad_silence_duration_threshold=config.VAD_SILENCE_DURATION_THRESHOLD,
        vad_sample_rate=config.AUDIO_SAMPLE_RATE,
        cancel_echo=config.CANCEL_ECHO,
        voice_recorder_enabled=config.VOICE_RECORDER_ENABLED,
        voice_recorder_dir=config.VOICE_RECORDER_DIR,
        db_connection_str=config.DB_CONNECTION_STR,
        debug=config.DEBUG,
    )
    app.charactername = config.CHARACTER_NAME

    # Mirror every reply into the VRChat chatbox so players can also read it.
    chatbox = udp_client.SimpleUDPClient(config.OSC_HOST, config.OSC_PORT)

    _speaking = False

    @app.on_response("start")
    async def mark_busy(response):
        app._is_processing = True
        print("STATUS:thinking", flush=True)

    @app.on_response("chunk")
    async def on_chunk(response):
        nonlocal _speaking
        if not _speaking and response.audio_data:
            _speaking = True
            print("STATUS:speaking", flush=True)

    @app.on_response("final")
    async def mirror_to_chatbox(response):
        nonlocal _speaking
        app._is_processing = False
        _speaking = False
        if config.CHATBOX_ENABLED and response.voice_text:
            # /chatbox/input: [text, send immediately, no notification sound]
            chatbox.send_message(
                "/chatbox/input", [response.voice_text[: config.CHATBOX_MAX_LENGTH], True, False]
            )
        asyncio.create_task(_wait_for_idle())

    async def _wait_for_idle():
        for _ in range(10):
            if app.audio_player.is_playing:
                break
            await asyncio.sleep(0.1)
        while app.audio_player.is_playing:
            await asyncio.sleep(0.1)
        print("STATUS:listening", flush=True)

    print(f"{config.CHARACTER_NAME} is live. Listening on '{config.INPUT_DEVICE}', "
          f"speaking on '{config.OUTPUT_DEVICE}', OSC -> {config.OSC_HOST}:{config.OSC_PORT}. "
          "Ctrl+C to stop.")
    print("STATUS:listening", flush=True)
    try:
        await app.start_listening()
    finally:
        if mcp:
            await mcp.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="VRTwin - VRChat AI avatar")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    parser.add_argument("--text", action="store_true", help="console chat mode (no audio/VRChat)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if config.DEBUG else logging.INFO)

    if args.list_devices:
        list_devices()
    elif args.text:
        asyncio.run(text_chat())
    else:
        try:
            asyncio.run(run_avatar())
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
