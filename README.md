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
| A PC that runs VRChat | **Windows 10/11** (native) or **Linux** (via Steam Proton). macOS has no VRChat client — see [Platform notes](#platform-notes) | — |
| Python 3.10 – 3.12 | runs the script | [python.org](https://www.python.org/downloads/) or your package manager |
| Two virtual audio cables | carry sound between VRChat and the bot | Windows: [VB-CABLE A+B](https://vb-audio.com/Cable/#DownloadASIOBridge) (donationware) · Linux: created automatically by `run.sh` · macOS: [BlackHole](https://existential.audio/blackhole/) 2ch + 16ch |
| A VRChat account for the bot | the AI needs its own account/avatar | ideally a second account so you can join it with your main |
| OpenRouter API key | brain (Claude Sonnet 5) + ears (gpt-4o-transcribe) + voice (Gemini 3.1 Flash TTS) | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) |

## Setup

### 1. Install the software

**Windows**

1. Install Python 3.10–3.12 (**tick "Add python.exe to PATH"**).
2. Install **VB-CABLE A+B** (run the installer as administrator, then reboot).
   After the reboot you'll have `CABLE-A` and `CABLE-B` audio devices.
3. Download/clone this repository somewhere, e.g. `C:\VRTwin`.

**Linux**

1. Install the prerequisites, e.g. on Debian/Ubuntu:
   `sudo apt install python3 python3-venv python3-tk python3-dev portaudio19-dev`
   (PyAudio compiles against PortAudio; the GUI needs Tk.)
2. Clone this repository. `./run.sh` handles the rest, including creating the
   two virtual audio cables (`VRTwin-Ears`, `VRTwin-Voice`) via PulseAudio/PipeWire.

**macOS**

1. `brew install python python-tk portaudio blackhole-2ch blackhole-16ch`
   (the two BlackHole drivers are the two "cables").
2. Clone this repository and use `./run.sh`.

### 2. Route the audio (the important part)

Two one-way cables: cable A carries VRChat's sound to the bot's ears, cable B
carries the bot's voice to VRChat's microphone.

**Windows (VB-CABLE)**

| Cable | Carries | How to set it |
|---|---|---|
| **CABLE-A** | VRChat's sound → the bot's ears | Windows Settings → System → Sound → **App volume and device preferences** → set **VRChat**'s *Output* to **CABLE-A Input (VB-Audio Cable A)** |
| **CABLE-B** | the bot's voice → VRChat's mic | In VRChat: Settings → Audio & Voice → *Microphone* → **CABLE-B Output (VB-Audio Cable B)** |

**Linux (PulseAudio/PipeWire)**

`./run.sh` creates two virtual cables at every launch: **VRTwin-Ears** and
**VRTwin-Voice** (the bot is wired to them out of the box via `PULSE_SOURCE`/
`PULSE_SINK`). Route VRChat to them with `pavucontrol` (install it if needed)
while VRChat is running:

| Cable | Carries | How to set it (pavucontrol) |
|---|---|---|
| **VRTwin-Ears** | VRChat's sound → the bot's ears | *Playback* tab → set VRChat's output to **VRTwin-Ears** |
| **VRTwin-Voice** | the bot's voice → VRChat's mic | *Recording* tab → set VRChat's capture to **Monitor of VRTwin-Voice** |

The cables disappear on reboot — `./run.sh` simply recreates them next launch
(re-check the pavucontrol routing after a reboot too).

**macOS (BlackHole)**

| Cable | Carries | How to set it |
|---|---|---|
| **BlackHole 2ch** | the game's sound → the bot's ears | set the game/app's audio output to **BlackHole 2ch** |
| **BlackHole 16ch** | the bot's voice → the game's mic | set the game/app's microphone to **BlackHole 16ch** |

Also in VRChat: set the microphone to **Toggle** mode and leave it on, so the bot's
voice always transmits.

> Tip: with VRChat's output routed to cable A you won't hear the world on your
> headphones anymore — that's expected for a dedicated bot PC/account. If you want to
> listen in, enable "Listen to this device" on the cable (Windows sound control
> panel) / play the cable's monitor to your headphones (pavucontrol on Linux), or
> just join the instance with your main account from another device.

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

Double-click **`run.bat`** (Windows) or run **`./run.sh`** (Linux/macOS). First run
creates a virtual environment and installs dependencies (a few minutes), then the
**VRTwin control panel** opens.

Then start VRChat, log in with the bot account, join a world — and talk to it.

## Using the control panel

Everything is configured and run from the GUI — no file editing needed:

- **▶ Start avatar / ■ Stop avatar** (top) — saves your settings and starts the bot;
  its output streams into the **Avatar log** panel at the bottom. Settings changes
  apply after a restart (Stop, then Start).
- **Settings tabs** — every option, each with a one-line explanation right under it:
  - **Keys & Models** — your OpenRouter API key, the brain/ears/voice models, the
    reasoning switch and the reply-randomness (temperature) field.
  - **Hearing & Voice** — the microphone-sensitivity and end-of-sentence-pause
    sliders, echo cancel, sample rates and timeouts.
  - **Audio Devices** — pick the bot's ears and mouth (the two virtual cables)
    from dropdowns; **↻ Refresh device lists** rescans your hardware.
  - **VRChat** — OSC address/port, the expression parameter, the expressions JSON,
    the chatbox toggle and character limit.
  - **Character** — the AI's name and personality.
  - **Tools** — the tools (MCP) switch, the tool timeout, and the MCP server
    editor (see [Tools (MCP)](#tools-mcp) below).
  - **Advanced** — HTTP tuning, history file, voice recorder, debug logging.
- **💾 Save settings** — validates everything and writes it to `.env` (only values
  you changed are stored).
- **↩ Reset to defaults** — puts every option back to its out-of-the-box value
  (after a confirmation); click Save to make it permanent.

### Command line (advanced)

The engine still works without the GUI:

```bat
.venv\Scripts\activate          REM Linux/macOS: source .venv/bin/activate
python main.py                  REM run the avatar directly
python main.py --list-devices   REM show audio devices if the cables aren't found
python main.py --text           REM chat with the AI in the console - tests your
                                REM OpenRouter key and face tags without VRChat/audio
```

`run.bat`/`./run.sh` with any argument (e.g. `run.bat --text` or `./run.sh --text`)
also runs the CLI instead of the GUI.

## Tools (MCP)

The AI can use tools from [MCP](https://modelcontextprotocol.io) servers. Out of
the box it gets (configured in `mcp_servers.json`, created on first run):

- **fetch** — read a web page the players mention.
- **search** — search the web via DuckDuckGo (no API key needed).
- **time** — the current time and timezone conversions.
- **memory** — a persistent knowledge graph, so it remembers players across
  sessions (stored in `mcp_workspace/memory.json`). Needs Node.js.
- **filesystem** — read/write files, sandboxed to the `mcp_workspace/` folder.
  Needs Node.js.

The fetch/search/time servers are Python and installed with everything else;
memory and filesystem run via `npx` and are skipped automatically (with a log
line) when Node.js is not installed. A server that fails to start never stops
the avatar - it just comes up without those tools.

Add or edit servers on the **Tools** tab of the control panel (name, command,
arguments, environment, per-server on/off), or edit `mcp_servers.json` directly -
it uses the same `mcpServers` format as Claude Desktop, plus an `"enabled"` flag.
`"command": "python"` always means VRTwin's own venv Python. Turn all tools off
with the switch on the Tools tab (`MCP_ENABLED=false`).

## Tuning

Adjust these in the GUI (or in `.env` by hand — see `.env.example`):

- **Bot doesn't hear / hears too much** → adjust `VAD_VOLUME_DB_THRESHOLD`
  (closer to 0 = less sensitive, e.g. `-40`; more negative = more sensitive, e.g. `-60`).
  `VAD_SILENCE_DURATION_THRESHOLD` controls how long a pause has to be before
  the bot considers you done talking.
- **Different voice** → `TTS_VOICE` — any of the 30 Gemini prebuilt voices:
  `Zephyr` (Bright), `Puck` (Upbeat), `Charon` (Informative), `Kore` (Firm),
  `Fenrir` (Excitable), `Leda` (Youthful), `Orus` (Firm), `Aoede` (Breezy),
  `Callirrhoe` (Easy-going), `Autonoe` (Bright), `Enceladus` (Breathy), `Iapetus` (Clear),
  `Umbriel` (Easy-going), `Algieba` (Smooth), `Despina` (Smooth), `Erinome` (Clear),
  `Algenib` (Gravelly), `Rasalgethi` (Informative), `Laomedeia` (Upbeat), `Achernar` (Soft),
  `Alnilam` (Firm), `Schedar` (Even), `Gacrux` (Mature), `Pulcherrima` (Forward),
  `Achird` (Friendly), `Zubenelgenubi` (Casual), `Vindemiatrix` (Gentle),
  `Sadachbia` (Lively), `Sadaltager` (Knowledgeable), `Sulafat` (Warm).
- **Voice style / pace / accent** → `TTS_STYLE`, `TTS_PACE`, `TTS_ACCENT` — optional
  director's notes sent to Gemini TTS before each response, e.g.
  `TTS_STYLE=warm and friendly`, `TTS_PACE=natural conversational pace`,
  `TTS_ACCENT=American English`. Leave empty for model defaults.
- **Personality** → `PERSONA`, `CHARACTER_NAME` and `OPENROUTER_TEMPERATURE`
  (higher = more varied replies).
- **Smarter but slower replies** → `OPENROUTER_REASONING_ENABLED=true` turns
  Claude's reasoning back on.
- **Other models** → `OPENROUTER_MODEL` (brain), `STT_MODEL` (ears), `TTS_MODEL`
  (voice) — any matching OpenRouter model ids work. If you switch to a TTS model
  that doesn't output 24 kHz PCM, set `TTS_SAMPLE_RATE` accordingly.
- **Other language** → `STT_LANGUAGE` (e.g. `nl`) and mention the language in `PERSONA`.
- **Running more than one bot on the same PC** → give each its own
  `DB_CONNECTION_STR` (conversation history file) so they don't share history.
- **Every setting** lives in `.env.example`, including HTTP timeouts, connection
  pool sizes, the voice recorder, and the chatbox character limit — copy any
  line you need into `.env`.

## Platform notes

- **Windows** — native VRChat; fully supported with VB-CABLE A+B.
- **Linux** — VRChat runs well through **Steam Proton** (install VRChat in Steam,
  enable Proton in its compatibility settings); fully supported with the
  auto-created PulseAudio/PipeWire cables. Works on both PulseAudio and PipeWire
  (`pactl` talks to either).
- **macOS** — there is **no VRChat client for macOS**, so a Mac cannot run the
  bot's VRChat account itself. Everything else works: the control panel, console
  chat (`./run.sh --text`), and the full audio pipeline via BlackHole — useful for
  developing, testing personas, or driving other audio apps. (OSC can reach VRChat
  on another machine via `OSC_HOST`, but the audio cables cannot cross machines
  without extra tooling.)

## Troubleshooting

- **Audio cable not found on startup** — run `python main.py --list-devices` and put
  the exact index or name in the GUI's Audio Devices tab (or `.env`). On Windows,
  `INPUT_DEVICE` must be the *"CABLE-A **Output**"* recording device and
  `OUTPUT_DEVICE` the *"CABLE-B **Input**"* playback device.
- **`pip install` fails on PyAudio (Linux/macOS)** — install the PortAudio headers
  first (`sudo apt install portaudio19-dev python3-dev` / `brew install portaudio`),
  delete `.venv`, and run `./run.sh` again.
- **Linux: bot hears nothing after a reboot** — the virtual cables are recreated by
  `./run.sh`, but VRChat's routing resets: re-select **VRTwin-Ears** (Playback) and
  **Monitor of VRTwin-Voice** (Recording) in `pavucontrol`.
- **Bot talks but no expressions / no chatbox** — OSC is disabled (step 3), or VRChat
  runs on another PC (set `OSC_HOST`).
- **Bot answers itself in a loop** — VRChat's mic is set to the wrong device, or its
  output isn't routed to cable A (step 2). Echo cancellation is on by default, but
  correct routing is required.
- **401 errors** — your OpenRouter key is wrong or out of credits; everything
  (chat, transcription, speech) authenticates against `openrouter.ai`.
- **Bot hears but stays silent** — run with `DEBUG=true` and check for TTS errors;
  if the voice name is rejected, try another Gemini voice in `TTS_VOICE` (see the full list in the Tuning section above).

## Notes

- The reasoning of Claude Sonnet 5 is disabled via OpenRouter's
  `reasoning: {"enabled": false}` request parameter (see `build_llm()` in `main.py`) —
  ideal for real-time voice chat.
- Conversation history is kept per session in a local `aiavatar.db` SQLite file.
- Keep your `.env` private; it contains your API keys and is git-ignored.
- Running a bot account is subject to the VRChat Terms of Service — be transparent
  with the people you talk to and don't leave it unattended in public instances.
