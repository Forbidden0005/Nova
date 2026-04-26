"""voice/io.py — Voice input (STT) and output (TTS). Designed for background threading."""
from __future__ import annotations
import io
import logging
import threading
from typing import Callable

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE, USE_ELEVENLABS

logger = logging.getLogger(__name__)

# PyAudio is required by SpeechRecognition for mic access.
# It has no wheel for Python 3.14+ yet, so we degrade gracefully.
try:
    import speech_recognition as sr
    import pyaudio  # noqa: F401 — validate PortAudio binding is present
    _MIC_AVAILABLE = True
except Exception:
    _MIC_AVAILABLE = False
    sr = None  # type: ignore[assignment]
    logger.warning(
        "PyAudio not available — microphone input disabled. "
        "Install PyAudio manually (e.g. via pipwin) to enable voice input."
    )


class VoiceIO:
    """Threaded voice input/output handler."""

    def __init__(self) -> None:
        self._speak_lock = threading.Lock()
        self._listening = threading.Event()
        if _MIC_AVAILABLE:
            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold = 0.8
            self._recognizer.energy_threshold = 300
        else:
            self._recognizer = None
        if USE_ELEVENLABS:
            self._init_elevenlabs()
        logger.info(
            "VoiceIO ready — TTS=%s  MIC=%s",
            "ElevenLabs" if USE_ELEVENLABS else "pyttsx3",
            "on" if _MIC_AVAILABLE else "off (PyAudio missing)",
        )

    def _init_elevenlabs(self) -> None:
        if not ELEVENLABS_API_KEY:
            logger.warning("ElevenLabs API key is empty — falling back to pyttsx3")
            import config as cfg
            cfg.USE_ELEVENLABS = False
            self._el_client = None
            return
        try:
            from elevenlabs import ElevenLabs
            self._el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        except Exception as exc:
            logger.warning("ElevenLabs init failed, using pyttsx3: %s", exc)
            import config as cfg
            cfg.USE_ELEVENLABS = False
            self._el_client = None

    def listen(self, timeout: float = 5.0, phrase_limit: float = 15.0) -> str | None:
        """Listen for speech and transcribe it. Returns text or None."""
        if not _MIC_AVAILABLE:
            logger.warning("listen() called but PyAudio is not installed — mic disabled.")
            return None
        self._listening.set()
        try:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            self._listening.clear()
            return None
        except Exception as exc:
            logger.warning("Mic error: %s", exc)
            self._listening.clear()
            return None
        finally:
            self._listening.clear()

        try:
            return self._recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
        try:
            return self._recognizer.recognize_sphinx(audio)
        except Exception:
            pass
        return None

    def listen_async(self, on_result: Callable[[str], None], on_error: Callable[[str], None] | None = None) -> threading.Thread:
        def _worker() -> None:
            result = self.listen()
            if result:
                on_result(result)
            elif on_error:
                on_error("No speech recognised")
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    def speak(self, text: str) -> None:
        """Synthesise and play text as speech (blocking)."""
        with self._speak_lock:
            if USE_ELEVENLABS:
                self._speak_elevenlabs(text)
            else:
                self._speak_pyttsx3(text)

    def speak_async(self, text: str) -> threading.Thread:
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread

    def _speak_elevenlabs(self, text: str) -> None:
        try:
            import sounddevice as sd
            import soundfile as sf
            audio_bytes = self._el_client.text_to_speech.convert(
                text=text, voice_id=ELEVENLABS_VOICE,
                model_id="eleven_turbo_v2", output_format="mp3_44100_128",
            )
            buf = io.BytesIO(b"".join(audio_bytes))
            data, samplerate = sf.read(buf, dtype="float32")
            sd.play(data, samplerate)
            sd.wait()
        except Exception as exc:
            logger.error("ElevenLabs TTS failed: %s", exc)
            self._speak_pyttsx3(text)

    @staticmethod
    def _speak_pyttsx3(text: str) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 0.95)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            logger.error("pyttsx3 TTS failed: %s", exc)

    @property
    def is_listening(self) -> bool:
        return self._listening.is_set()
