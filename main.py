"""VRTwin - run a VRChat account as an AI avatar.

Pipeline (all wired through AIAvatarKit):
  VRChat audio -> VB-CABLE A -> voice detection -> OpenAI Whisper (STT)
  -> Claude Sonnet 5 via OpenRouter (reasoning disabled)
  -> OpenAI TTS -> VB-CABLE B -> VRChat microphone
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


def build_llm() -> ChatGPTService:
    """Claude Sonnet 5 through OpenRouter's OpenAI-compatible endpoint.

    OpenRouter's `reasoning` body parameter is sent via extra_body to turn
    Claude's thinking off entirely, so replies come back fast and cheap.
    """
    if not config.OPENROUTER_API_KEY:
        raise SystemExit("OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in.")

    return ChatGPTService(
        openai_api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        model=config.OPENROUTER_MODEL,
        system_prompt=config.build_system_prompt(),
        extra_body={"reasoning": {"enabled": False}},
        debug=config.DEBUG,
    )


def list_devices() -> None:
    import pyaudio

    p = pyaudio.PyAudio()
    devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
    p.terminate()
    if not devices:
        print("No audio devices found. Is VB-CABLE A+B installed (and did you reboot)?")
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
    [face:...] expression tags without VRChat, audio devices, or an OpenAI key."""
    llm = build_llm()
    context_id = "console"
    user_id = "console_user"
    print(f"Console chat with {config.CHARACTER_NAME} ({config.OPENROUTER_MODEL}). Ctrl+C to quit.")
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
            if chunk.text:
                print(chunk.text, end="", flush=True)
                response_text += chunk.text
        print()
        await llm.update_context(context_id, user_id, messages, response_text)


async def run_avatar() -> None:
    from pythonosc import udp_client

    from aiavatar.adapter.local.client import AIAvatar
    from aiavatar.device import AudioDevice
    from aiavatar.face.vrchat import VRChatFaceController
    from aiavatar.sts.stt.openai import OpenAISpeechRecognizer
    from aiavatar.sts.tts.openai import OpenAISpeechSynthesizer

    if not config.OPENAI_API_KEY:
        raise SystemExit("OPENAI_API_KEY is not set (needed for speech-to-text and the voice).")

    app = AIAvatar(
        llm=build_llm(),
        stt=OpenAISpeechRecognizer(
            openai_api_key=config.OPENAI_API_KEY,
            model=config.STT_MODEL,
            language=config.STT_LANGUAGE,
            sample_rate=16000,
        ),
        tts=OpenAISpeechSynthesizer(
            openai_api_key=config.OPENAI_API_KEY,
            model=config.TTS_MODEL,
            speaker=config.TTS_VOICE,
        ),
        face_controller=VRChatFaceController(
            osc_address=config.FACE_OSC_ADDRESS,
            faces=config.FACES,
            host=config.OSC_HOST,
            port=config.OSC_PORT,
            debug=config.DEBUG,
        ),
        audio_devices=AudioDevice(
            input_device=config.INPUT_DEVICE,
            output_device=config.OUTPUT_DEVICE,
        ),
        vad_volume_db_threshold=config.VAD_VOLUME_DB_THRESHOLD,
        cancel_echo=True,  # don't listen to the bot's own voice
        voice_recorder_enabled=False,
        debug=config.DEBUG,
    )
    app.charactername = config.CHARACTER_NAME

    # Mirror every reply into the VRChat chatbox so players can also read it.
    chatbox = udp_client.SimpleUDPClient(config.OSC_HOST, config.OSC_PORT)

    @app.on_response("final")
    async def mirror_to_chatbox(response):
        if config.CHATBOX_ENABLED and response.voice_text:
            # /chatbox/input: [text (max 144 chars), send immediately, no notification sound]
            chatbox.send_message("/chatbox/input", [response.voice_text[:144], True, False])

    print(f"{config.CHARACTER_NAME} is live. Listening on '{config.INPUT_DEVICE}', "
          f"speaking on '{config.OUTPUT_DEVICE}', OSC -> {config.OSC_HOST}:{config.OSC_PORT}. "
          "Ctrl+C to stop.")
    await app.start_listening()


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
