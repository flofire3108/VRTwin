# VRTwin — an AI that plays VRChat

VRTwin logs a VRChat account in as a living AI character. It **hears** the players
around it, **thinks** with Claude Sonnet 5, **talks back** with a natural
text-to-speech voice, shows its replies in the **chatbox**, and plays **custom facial
expressions** on the avatar — powered by
[AIAvatarKit](https://github.com/uezo/aiavatarkit) and VRChat's OSC interface.
All three AI stages (hearing, thinking, speaking) run through a **single
[OpenRouter](https://openrouter.ai) API key**.

```
player speaks ─► VRChat audio ─► CABLE-A ─► speech-to-text
                                            (openai/gpt-4o-transcribe via OpenRouter)
                                              │
                                              ▼
                              Claude Sonnet 5 via OpenRouter (no reasoning)
                                              │  reply text + [face:joy] tags
                          ┌───────────────────┼──────────────────────┐
                          ▼                   ▼                      ▼
              Gemini 3.1 Flash TTS    OSC /avatar/parameters   OSC /chatbox/input
              (via OpenRouter)        (facial expression)      (text bubble)
              ─► CABLE-B ─► VRChat microphone
```

## What you need

| Thing | Why | Where |
|---|---|---|
| Windows 10/11 PC | runs VRChat + this script | — |
| Python 3.10 – 3.12 | runs the script | [python.org](https://www.python.org/downloads/) — tick **"Add python.exe to PATH"** |
| VB-CABLE **A+B** | two virtual audio cables between VRChat and the bot | [VB-Audio Cable A+B](https://vb-audio.com/Cable/#DownloadASIOBridge) (donationware) |
| A VRChat account for the bot | the AI needs its own account/avatar | ideally a second account so you can join it with your main |
| OpenRouter API key | brain (Claude Sonnet 5) + ears (gpt-4o-transcribe) + voice (Gemini 3.1 Flash TTS) | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) |

## Setup

### 1. Install the software

1. Install Python 3.10–3.12 (**tick "Add python.exe to PATH"**).
2. Install **VB-CABLE A+B** (run the installer as administrator, then reboot).
   After the reboot you'll have `CABLE-A` and `CABLE-B` audio devices.
3. Download/clone this repository somewhere, e.g. `C:\VRTwin`.
4. Copy `.env.example` to `.env` and paste in your OpenRouter API key.

### 2. Route the audio (the important part)

Two one-way cables:

| Cable | Carries | How to set it |
|---|---|---|
| **CABLE-A** | VRChat's sound → the bot's ears | Windows Settings → System → Sound → **App volume and device preferences** → set **VRChat**'s *Output* to **CABLE-A Input (VB-Audio Cable A)** |
| **CABLE-B** | the bot's voice → VRChat's mic | In VRChat: Settings → Audio & Voice → *Microphone* → **CABLE-B Output (VB-Audio Cable B)** |

Also in VRChat: set the microphone to **Toggle** mode and leave it on, so the bot's
voice always transmits.

> Tip: with VRChat's output routed to CABLE-A you won't hear the world on your
> headphones anymore — that's expected for a dedicated bot PC/account. If you want to
> listen in, enable "Listen to this device" on CABLE-A in the Windows sound control
> panel, or just join the instance with your main account from another device.

### 3. Enable OSC in VRChat

On the bot account, open the **Action Menu** (hold `R` on desktop) →
**Options → OSC → Enable**. OSC is what lets the script drive expressions and the
chatbox on `127.0.0.1:9000`.

### 4. Avatar expressions (AIAvatarKit convention)

The avatar needs one **synced `int` parameter** named `FaceOSC` (default `0`) whose
values switch face animations in the FX animator:

| Value | Expression |
|---|---|
| 0 | neutral |
| 1 | joy |
| 2 | angry |
| 3 | sorrow |
| 4 | fun |
| 5 | surprise |

Claude adds tags like `[face:joy]` to its replies; the script converts them to OSC
messages on `/avatar/parameters/FaceOSC`. If your avatar uses a different parameter
name, values, or expression set, change `FACE_OSC_ADDRESS` and `FACES` in `.env` —
the AI is automatically told which expressions exist.

No expressions set up yet? Everything else still works — the OSC messages are simply
ignored by the avatar.

### 5. Run it

Double-click **`run.bat`**. First run creates a virtual environment and installs
dependencies (a few minutes), then the bot goes live.

Useful test commands (run in a terminal in this folder, after the first `run.bat`):

```bat
.venv\Scripts\activate
python main.py --list-devices   REM show audio devices if CABLE-A/B aren't found
python main.py --text           REM chat with the AI in the console - tests your
                                REM OpenRouter key and face tags without VRChat/audio
```

Then start VRChat, log in with the bot account, join a world — and talk to it.

## Tuning

Everything lives in `.env` (see `.env.example` for all options):

- **Bot doesn't hear / hears too much** → adjust `VAD_VOLUME_DB_THRESHOLD`
  (closer to 0 = less sensitive, e.g. `-40`; more negative = more sensitive, e.g. `-60`).
- **Different voice** → `TTS_VOICE` — Gemini prebuilt voices like `Kore`, `Puck`,
  `Zephyr`, `Charon`, `Fenrir`, `Leda`, `Orus`, `Aoede`.
- **Personality** → `PERSONA` and `CHARACTER_NAME`.
- **Other models** → `OPENROUTER_MODEL` (brain), `STT_MODEL` (ears), `TTS_MODEL`
  (voice) — any matching OpenRouter model ids work. If you switch to a TTS model
  that doesn't output 24 kHz PCM, set `TTS_SAMPLE_RATE` accordingly.
- **Other language** → `STT_LANGUAGE` (e.g. `nl`) and mention the language in `PERSONA`.

## Troubleshooting

- **`CABLE-A` not found on startup** — run `python main.py --list-devices` and put the
  exact index or name in `.env` (`INPUT_DEVICE` must be the *"CABLE-A **Output**"*
  recording device, `OUTPUT_DEVICE` the *"CABLE-B **Input**"* playback device).
- **Bot talks but no expressions / no chatbox** — OSC is disabled (step 3), or VRChat
  runs on another PC (set `OSC_HOST`).
- **Bot answers itself in a loop** — VRChat's mic is set to the wrong device, or its
  output isn't routed to CABLE-A (step 2). Echo cancellation is on by default, but
  correct routing is required.
- **401 errors** — your OpenRouter key is wrong or out of credits; everything
  (chat, transcription, speech) authenticates against `openrouter.ai`.
- **Bot hears but stays silent** — run with `DEBUG=true` and check for TTS errors;
  if the voice name is rejected, try another Gemini voice in `TTS_VOICE`.

## Notes

- The reasoning of Claude Sonnet 5 is disabled via OpenRouter's
  `reasoning: {"enabled": false}` request parameter (see `build_llm()` in `main.py`) —
  ideal for real-time voice chat.
- Conversation history is kept per session in a local `aiavatar.db` SQLite file.
- Keep your `.env` private; it contains your API keys and is git-ignored.
- Running a bot account is subject to the VRChat Terms of Service — be transparent
  with the people you talk to and don't leave it unattended in public instances.
