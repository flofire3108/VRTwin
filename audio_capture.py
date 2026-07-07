"""WASAPI loopback hearing for Windows (INPUT_MODE=loopback).

Captures the game's sound straight from an output device via WASAPI loopback
(PyAudioWPatch) - no virtual input cable needed. The loopback stream runs at
the device's native rate/channels; chunks are downmixed to mono and resampled
to the pipeline's sample rate here, so the rest of AIAvatarKit sees exactly
what a normal microphone recorder would produce.

Drop-in replacement for aiavatar.device.AudioRecorder (same interface:
`start_stream()` async generator of int16 bytes + `stop_stream()`).
"""

import asyncio
import logging

import numpy as np

logger = logging.getLogger(__name__)


def _get_pyaudiowpatch():
    try:
        import pyaudiowpatch

        return pyaudiowpatch
    except ImportError:
        return None


def loopback_available() -> bool:
    return _get_pyaudiowpatch() is not None


def find_loopback_device(device_name: str = ""):
    """Returns (pyaudiowpatch module, loopback device info dict) or (None, None).

    device_name: name fragment of the OUTPUT device to tap (e.g. "Speakers");
    empty selects the system default output device.
    """
    pyaudio = _get_pyaudiowpatch()
    if pyaudio is None:
        return None, None
    try:
        p = pyaudio.PyAudio()
        try:
            if device_name:
                for info in p.get_loopback_device_info_generator():
                    if device_name.lower() in info["name"].lower():
                        return pyaudio, info
                logger.warning(f"No loopback device matches '{device_name}'")
                return pyaudio, None
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            if speakers.get("isLoopbackDevice"):
                return pyaudio, speakers
            for info in p.get_loopback_device_info_generator():
                if speakers["name"] in info["name"]:
                    return pyaudio, info
            logger.warning(f"No loopback analogue found for '{speakers['name']}'")
            return pyaudio, None
        finally:
            p.terminate()
    except Exception as ex:
        logger.warning(f"WASAPI loopback lookup failed: {ex}")
        return pyaudio, None


def downmix_and_resample(chunk: bytes, channels: int, source_rate: int, target_rate: int) -> bytes:
    """int16 interleaved frames -> mono int16 at target_rate (linear interpolation)."""
    samples = np.frombuffer(chunk, dtype=np.int16)
    if channels > 1:
        samples = samples[: len(samples) - len(samples) % channels]
        samples = samples.reshape(-1, channels).mean(axis=1)
    samples = samples.astype(np.float32)
    if source_rate != target_rate and len(samples):
        target_length = max(1, int(round(len(samples) * target_rate / source_rate)))
        positions = np.linspace(0, len(samples) - 1, target_length)
        samples = np.interp(positions, np.arange(len(samples)), samples)
    return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()


class LoopbackAudioRecorder:
    """AudioRecorder-compatible recorder fed by a WASAPI loopback stream."""

    def __init__(self, target_sample_rate: int = 16000, device_name: str = "",
                 chunk_size: int = 512):
        self.pyaudio, self.device_info = find_loopback_device(device_name)
        if self.device_info is None:
            raise RuntimeError("No WASAPI loopback device available")
        self.sample_rate = target_sample_rate  # what the pipeline receives
        self.channels = 1
        self.chunk_size = chunk_size
        self.device_index = int(self.device_info["index"])
        self.native_rate = int(self.device_info["defaultSampleRate"])
        self.native_channels = max(1, int(self.device_info["maxInputChannels"]))
        # Read enough native frames that one yielded chunk ≈ chunk_size target frames
        self.native_chunk = max(1, int(chunk_size * self.native_rate / target_sample_rate))
        self.is_listening = False
        logger.info(
            f"Loopback capture: '{self.device_info['name']}' "
            f"{self.native_rate}Hz x{self.native_channels} -> {target_sample_rate}Hz mono"
        )

    async def start_stream(self):
        p = self.pyaudio.PyAudio()
        stream = p.open(
            rate=self.native_rate,
            channels=self.native_channels,
            format=self.pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.native_chunk,
            input_device_index=self.device_index,
        )
        self.is_listening = True
        try:
            while self.is_listening:
                raw = stream.read(self.native_chunk, exception_on_overflow=False)
                yield downmix_and_resample(raw, self.native_channels,
                                           self.native_rate, self.sample_rate)
                await asyncio.sleep(0.0001)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            logger.info("Loopback stream closed.")

    def stop_stream(self):
        self.is_listening = False


def create_loopback_recorder(target_sample_rate: int, device_name: str = ""):
    """LoopbackAudioRecorder, or None (with a logged reason) so the caller can
    fall back to normal device recording."""
    if not loopback_available():
        logger.warning(
            "INPUT_MODE=loopback but PyAudioWPatch is not installed (Windows only) - "
            "falling back to recording from INPUT_DEVICE."
        )
        return None
    try:
        return LoopbackAudioRecorder(target_sample_rate=target_sample_rate,
                                     device_name=device_name)
    except Exception as ex:
        logger.warning(f"Loopback capture unavailable ({ex}) - "
                       "falling back to recording from INPUT_DEVICE.")
        return None
