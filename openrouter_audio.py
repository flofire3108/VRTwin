"""OpenRouter audio services for AIAvatarKit.

Speech-to-text and text-to-speech through OpenRouter's audio APIs, so the whole
app (brain, ears, voice) runs on a single OpenRouter key:

  STT: POST /api/v1/audio/transcriptions  (JSON, base64 audio)  -> {"text": ...}
  TTS: POST /api/v1/audio/speech          (JSON)                -> raw audio bytes
"""

import base64
import io
import logging
import wave
from typing import List

from aiavatar.sts.stt.base import SpeechRecognizer
from aiavatar.sts.tts.base import SpeechSynthesizer
from aiavatar.sts.tts.preprocessor import TTSPreprocessor

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterSpeechRecognizer(SpeechRecognizer):
    """Transcribes microphone audio via OpenRouter (default: openai/gpt-4o-transcribe)."""

    def __init__(
        self,
        *,
        openrouter_api_key: str,
        model: str = "openai/gpt-4o-transcribe",
        base_url: str = OPENROUTER_BASE_URL,
        language: str = "en",
        alternative_languages: List[str] = None,
        sample_rate: int = 16000,
        min_data_length: int = 4096,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 10.0,
        debug: bool = False,
    ):
        super().__init__(
            language=language,
            alternative_languages=alternative_languages,
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            timeout=timeout,
            debug=debug,
        )
        self.openrouter_api_key = openrouter_api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.sample_rate = sample_rate
        self.min_data_length = min_data_length

    def get_config(self) -> dict:
        config = super().get_config()
        config["model"] = self.model
        config["sample_rate"] = self.sample_rate
        return config

    async def transcribe(self, data: bytes) -> str:
        if len(data) < self.min_data_length:
            if self.debug:
                logger.info(f"Data to transcribe is too short: {len(data)}")
            return None

        wave_buffer = self.to_wave_file(data, self.sample_rate)
        provider_prefix = self.model.split("/")[0] if "/" in self.model else None
        json_body = {
            "model": self.model,
            "input_audio": {
                "data": base64.b64encode(wave_buffer.read()).decode("utf-8"),
                "format": "wav",
            },
        }
        if provider_prefix:
            json_body["provider"] = {"order": [provider_prefix]}
        if self.language and not self.alternative_languages:
            # OpenRouter expects an ISO-639-1 hint, e.g. "en"
            json_body["language"] = self.language.split("-")[0]

        resp = await self.http_request_with_retry(
            method="POST",
            url=f"{self.base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.openrouter_api_key}"},
            json=json_body,
        )

        try:
            recognized_text = resp.json()["text"]
            if self.debug:
                logger.info(f"Recognized: {recognized_text}")
            return recognized_text
        except Exception:
            return None


class OpenRouterSpeechSynthesizer(SpeechSynthesizer):
    """Speaks via OpenRouter TTS (default: google/gemini-3.1-flash-tts-preview).

    Requests raw PCM and wraps it in a WAV header so AIAvatarKit's audio player
    can play it directly. Gemini 3.1 Flash TTS outputs 24 kHz / 16-bit / mono.
    """

    def __init__(
        self,
        *,
        openrouter_api_key: str,
        model: str = "google/gemini-3.1-flash-tts-preview",
        voice: str = "Kore",
        base_url: str = OPENROUTER_BASE_URL,
        pcm_sample_rate: int = 24000,
        tts_style: str = "",
        tts_pace: str = "",
        tts_accent: str = "",
        style_mapper: dict = None,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        timeout: float = 30.0,
        preprocessors: List[TTSPreprocessor] = None,
        cache_dir: str = None,
        debug: bool = False,
    ):
        super().__init__(
            style_mapper=style_mapper,
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            timeout=timeout,
            preprocessors=preprocessors,
            cache_dir=cache_dir,
            cache_ext="wav",
            debug=debug,
        )
        self.openrouter_api_key = openrouter_api_key
        self.model = model
        self.voice = voice
        self.base_url = base_url.rstrip("/")
        self.pcm_sample_rate = pcm_sample_rate
        parts = []
        if tts_style:  parts.append(tts_style)
        if tts_pace:   parts.append(tts_pace)
        if tts_accent: parts.append(f"{tts_accent} accent")
        self._tts_instruction = (
            f"Speak in a {', '.join(parts)} tone.\n\n" if parts else ""
        )

    def get_config(self) -> dict:
        config = super().get_config()
        config["model"] = self.model
        config["voice"] = self.voice
        config["pcm_sample_rate"] = self.pcm_sample_rate
        return config

    def pcm_to_wave(self, pcm_bytes: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.pcm_sample_rate)
            wf.writeframes(pcm_bytes)
        return buffer.getvalue()

    async def synthesize(self, text: str, style_info: dict = None, language: str = None) -> bytes:
        if not text or not text.strip():
            return bytes()

        if self.debug:
            logger.info(f"Speech synthesize: {text}")

        processed_text = await self.preprocess(text, style_info, language)
        if self._tts_instruction:
            processed_text = self._tts_instruction + processed_text

        # Gemini TTS returns empty audio for fragments that end mid-sentence
        # (e.g. " I'm doing great, "). Strip trailing non-terminal punctuation
        # so the TTS always gets a speakable chunk.
        processed_text = processed_text.strip()
        while processed_text and processed_text[-1] in (",", ";", ":", "-", "—"):
            processed_text = processed_text[:-1].strip()

        url = f"{self.base_url}/audio/speech"
        headers = {"Authorization": f"Bearer {self.openrouter_api_key}"}
        provider_prefix = self.model.split("/")[0] if "/" in self.model else None
        json_body = {
            "model": self.model,
            "input": processed_text,
            "voice": self.voice,
            "response_format": "pcm",
        }
        if provider_prefix:
            json_body["provider"] = {"order": [provider_prefix]}

        cache_key = self.make_cache_key(url=url, json_body=json_body)
        if cached := await self.read_cache(cache_key):
            return cached

        resp = await self.http_client.post(url=url, headers=headers, json=json_body)
        if resp.status_code != 200:
            logger.error(f"TTS failed ({resp.status_code}): {resp.text[:500]}")
            return bytes()

        wave_bytes = self.pcm_to_wave(resp.content)
        await self.write_cache(cache_key, wave_bytes)
        return wave_bytes
