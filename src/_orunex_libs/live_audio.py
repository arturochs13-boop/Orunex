"""Microphone listening loop for Orunex Live mode.

The live button used to open only a screen-capture loop.  This module adds the
missing audio half: it captures a spoken turn from the default microphone and
sends a small mono WAV file to Meta Model API's speech-to-text endpoint.

The API key is read from ``META_API_KEY`` (or the legacy aliases) and is never
stored in this file or in the public repository.
"""

from __future__ import annotations

import io
import json
import os
import queue
import tempfile
import threading
import time
import wave
from collections import deque
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional desktop dependency
    sd = None


DEFAULT_ASR_ENDPOINT = "https://api.meta.ai/v1/asr/transcribe"
DEFAULT_ASR_MODEL = "muse-voice-transcribe-1.0"
SAMPLE_RATE = 16_000
BLOCK_FRAMES = 1_600  # 100 ms
# The old 800 ms silence window made every turn feel like a phone menu.
# 300 ms is the Live-mode sweet spot: commands end immediately, while the
# release threshold and two-block onset still reject clicks and room spikes.
SPEECH_THRESHOLD = 0.006
SILENCE_BLOCKS = 3
MIN_SPEECH_BLOCKS = 2
PRE_ROLL_BLOCKS = 4
ONSET_BLOCKS = 2
MAX_TURN_SECONDS = 9.0
MIN_TURN_SECONDS = 0.35


class LiveAudioUnavailable(RuntimeError):
    """Raised when microphone or speech-to-text support is unavailable."""


def _config_value(key: str) -> str:
    try:
        from _orunex_libs import config_manager

        value = config_manager.get_val(key)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _api_key() -> str:
    for name in ("META_API_KEY", "MODEL_API_KEY", "META_AI_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return _config_value("meta_api_key").strip()


def _asr_endpoint() -> str:
    explicit = (
        os.environ.get("META_ASR_ENDPOINT")
        or _config_value("meta_asr_endpoint")
        or ""
    ).strip()
    if explicit:
        return explicit
    base = (
        os.environ.get("META_API_BASE")
        or os.environ.get("META_API_ENDPOINT")
        or os.environ.get("META_AI_ENDPOINT")
        or "https://api.meta.ai/v1"
    ).strip().rstrip("/")
    if base.endswith("/asr/transcribe"):
        return base
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base + "/asr/transcribe"


def _asr_model() -> str:
    return (
        os.environ.get("META_ASR_MODEL")
        or _config_value("meta_asr_model")
        or DEFAULT_ASR_MODEL
    ).strip()


def _wav_bytes(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)
    return buffer.getvalue()


def _debug(message: str) -> None:
    """Opt-in diagnostic log; it must never leak into the Live conversation UI.

    Set ``ORUNEX_LIVE_DEBUG=1`` only while diagnosing the microphone.  Normal
    use stays silent: no "hearing", "transcribing" or transcript lines.
    """
    if os.environ.get("ORUNEX_LIVE_DEBUG", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    try:
        path = os.path.join(tempfile.gettempdir(), "orunex_live_debug.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except Exception:
        pass


class LiveAudioSession:
    """Capture microphone turns and transcribe them with Meta Model API."""

    def __init__(
        self,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
        language_bias: Optional[list[str]] = None,
        threshold: Optional[float] = None,
        device: Optional[int] = None,
    ):
        self.on_transcript = on_transcript
        self.on_status = on_status
        self.language_bias = language_bias or ["Spanish", "English"]
        self.threshold = float(
            threshold
            if threshold is not None
            else os.environ.get("META_MIC_THRESHOLD", SPEECH_THRESHOLD)
        )
        self.device = device

        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._muted = threading.Event()
        self._last_error = ""
        self._active_threshold = self.threshold
        self._http = None

    @property
    def active(self) -> bool:
        return bool(self._active)

    @property
    def last_error(self) -> str:
        return self._last_error

    def start(self) -> None:
        _debug(f"start requested active={self._active} muted={self._muted.is_set()}")
        if self._active:
            # Live can be re-armed after the assistant spoke.  A stale mute
            # flag here was the reason the microphone appeared "dead": it was
            # capturing blocks and discarding every one of them.
            self._muted.clear()
            _debug("start: already active, cleared mute")
            return
        self._muted.clear()
        self._last_error = ""
        self._active = True
        stop_event = threading.Event()
        self._stop_event = stop_event
        self._thread = threading.Thread(
            target=self._run,
            args=(stop_event,),
            name="orunex-live-audio",
            daemon=True,
        )
        self._thread.start()

    def stop(self, wait: bool = False) -> None:
        was_active = self._active
        self._active = False
        self._muted.clear()
        if self._stop_event is not None:
            self._stop_event.set()
        thread = self._thread
        if wait and thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        if was_active:
            self._emit_status("Live microphone off.", "info")

    def suspend(self) -> None:
        """Mute the microphone while the assistant is speaking.

        The stream stays open, but incoming blocks are discarded so the
        assistant's own voice is never transcribed as a new user turn.
        """
        self._muted.set()

    def resume(self) -> None:
        self._muted.clear()

    def _run(self, stop_event: threading.Event) -> None:
        if sd is None:
            self._last_error = "sounddevice is not installed"
            self._active = False
            self._emit_status(
                "Live microphone unavailable: install sounddevice.", "error"
            )
            return

        key = _api_key()
        if not key:
            self._last_error = "META_API_KEY is not configured"
            self._active = False
            self._emit_status(
                "Live microphone unavailable: META_API_KEY is not configured.",
                "error",
            )
            return

        try:
            import requests

            self._http = requests.Session()
        except Exception:
            self._http = None

        turn_queue: queue.Queue = queue.Queue(maxsize=2)
        worker = None
        try:
            _debug(f"run: opening input device={self.device!r} threshold={self.threshold}")
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=BLOCK_FRAMES,
                device=self.device,
            ) as stream:
                self._calibrate(stream)
                _debug(f"run: listening active_threshold={self._active_threshold:.5f}")
                # Speech-to-text runs on its own worker.  The microphone keeps
                # listening during the network round-trip, so a background
                # phrase cannot block the next real command for a second.
                worker = threading.Thread(
                    target=self._transcription_worker,
                    args=(stop_event, key, turn_queue),
                    name="orunex-live-asr",
                    daemon=True,
                )
                worker.start()
                while not stop_event.is_set():
                    pcm = self._record_turn(stream, stop_event)
                    if stop_event.is_set():
                        break
                    if not pcm:
                        continue
                    try:
                        turn_queue.put_nowait(pcm)
                    except queue.Full:
                        # A noisy room can generate turns faster than the ASR
                        # round-trip.  Drop the oldest queued turn instead of
                        # falling behind the user forever.
                        try:
                            turn_queue.get_nowait()
                            turn_queue.put_nowait(pcm)
                        except Exception:
                            pass
                        _debug("turn dropped because a transcription was pending")
        except Exception as exc:
            self._last_error = str(exc)
            _debug(f"run: error {exc!r}")
            self._emit_status(
                f"Live microphone error: {exc}", "error"
            )
        finally:
            try:
                turn_queue.put(None, timeout=0.2)
            except Exception:
                pass
            if worker is not None:
                worker.join(timeout=0.5)
            try:
                if self._http is not None:
                    self._http.close()
            except Exception:
                pass
            self._http = None
            self._muted.clear()
            self._active = False
            _debug("run: ended")

    def _transcription_worker(
        self, stop_event: threading.Event, key: str, turn_queue: "queue.Queue"
    ) -> None:
        """Transcribe completed turns without pausing microphone capture."""
        while not stop_event.is_set():
            try:
                pcm = turn_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if pcm is None:
                break
            if stop_event.is_set() or self._muted.is_set():
                continue
            try:
                wav_path = os.path.join(
                    tempfile.gettempdir(), "orunex_live_last.wav"
                )
                with open(wav_path, "wb") as handle:
                    handle.write(_wav_bytes(pcm))
                _debug(
                    "run: saved turn "
                    f"bytes={len(pcm)} seconds={len(pcm)/2/SAMPLE_RATE:.2f} "
                    f"muted={self._muted.is_set()}"
                )
            except Exception as exc:
                _debug(f"run: could not save turn: {exc}")

            transcript = self._transcribe(pcm, key)
            if (
                transcript
                and not stop_event.is_set()
                and not self._muted.is_set()
            ):
                self._emit_transcript(transcript)

    @staticmethod
    def _rms(block) -> float:
        samples = np.asarray(block, dtype=np.float32).reshape(-1) / 32768.0
        if not samples.size:
            return 0.0
        return float(np.sqrt(np.mean(samples * samples)))

    def _calibrate(self, stream) -> None:
        """Find a threshold above the room noise, not merely above zero.

        The previous calibration could only *lower* the configured threshold.
        In a quiet room it therefore stayed at 0.0035 and every fan, lyric or
        distant voice crossed it.  Calibration now takes a slightly longer
        sample and raises the gate with the measured noise floor, while the
        two-block onset and peak check below stop isolated clicks.
        """
        levels = []
        try:
            for _ in range(8):
                data, _overflow = stream.read(BLOCK_FRAMES)
                levels.append(self._rms(data))
        except Exception:
            levels = []
        configured = max(0.0045, float(self.threshold))
        if levels:
            noise = float(np.median(levels))
            adaptive = max(0.0055, min(0.025, noise * 2.8 + 0.0045))
            self._active_threshold = max(configured, adaptive)
        else:
            self._active_threshold = configured
        _debug(
            f"calibrate: levels={[round(level, 5) for level in levels]} "
            f"active_threshold={self._active_threshold:.5f}"
        )

    def _record_turn(
        self, stream, stop_event: threading.Event
    ) -> Optional[bytes]:
        """Wait for speech, then return one WAV-ready PCM utterance.

        Nothing is sent to the network unless the turn passes an energy/peak
        quality check.  This is what keeps a TV, a call or the tail of the
        assistant's own voice from occupying the transcriber forever.
        """
        pre_roll: deque[np.ndarray] = deque(maxlen=PRE_ROLL_BLOCKS)
        chunks: list[np.ndarray] = []
        started = False
        silence_blocks = 0
        onset_blocks = 0
        started_at = 0.0
        threshold = max(0.0045, float(self._active_threshold))

        while not stop_event.is_set():
            data, overflowed = stream.read(BLOCK_FRAMES)
            if overflowed:
                # Keep going; a dropped block should not stop the live mode.
                pass
            block = np.asarray(data)
            if block.ndim > 1:
                block = block[:, 0]
            block = np.ascontiguousarray(block, dtype=np.int16)

            if self._muted.is_set():
                pre_roll.clear()
                chunks.clear()
                started = False
                silence_blocks = 0
                onset_blocks = 0
                continue

            rms = self._rms(block)

            if not started:
                pre_roll.append(block.copy())
                if rms >= threshold:
                    onset_blocks += 1
                else:
                    onset_blocks = 0
                if onset_blocks < ONSET_BLOCKS:
                    continue
                started = True
                started_at = time.monotonic()
                chunks.extend(pre_roll)
                pre_roll.clear()
                silence_blocks = 0
                onset_blocks = 0
                continue

            chunks.append(block.copy())
            if rms < threshold * 0.55:
                silence_blocks += 1
            else:
                silence_blocks = 0

            enough_audio = len(chunks) >= MIN_SPEECH_BLOCKS + PRE_ROLL_BLOCKS
            if enough_audio and silence_blocks >= SILENCE_BLOCKS:
                break
            if time.monotonic() - started_at >= MAX_TURN_SECONDS:
                break

        if not started or not chunks:
            return None

        try:
            block_rms = [self._rms(chunk) for chunk in chunks]
            peak = max(block_rms)
            mean = float(np.mean(block_rms))
            duration = len(chunks) * BLOCK_FRAMES / SAMPLE_RATE
            min_peak = max(0.006, threshold * 1.25)
            min_mean = max(0.0008, threshold * 0.24)
            usable = (
                duration >= MIN_TURN_SECONDS
                and peak >= min_peak
                and mean >= min_mean
            )
            _debug(
                "record: turn "
                f"blocks={len(chunks)} seconds={duration:.2f} "
                f"peak={peak:.5f} mean={mean:.5f} threshold={threshold:.5f} "
                f"usable={usable}"
            )
            if not usable:
                return None
        except Exception:
            pass
        return b"".join(chunk.tobytes() for chunk in chunks)

    def _transcribe(self, pcm: bytes, key: str) -> str:
        wav = _wav_bytes(pcm)
        request = {
            "audioEncoding": "WAV",
            "mode": "PUSH_TO_TALK",
            "model": _asr_model(),
        }
        if self.language_bias:
            request["languageBias"] = self.language_bias

        headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }
        files = {
            "request": (None, json.dumps(request), "application/json"),
            "audio": ("live.wav", wav, "audio/wav"),
        }

        try:
            import requests

            client = self._http if self._http is not None else requests
            _debug(
                "asr: post "
                f"endpoint={_asr_endpoint()} model={_asr_model()} "
                f"bytes={len(pcm)} seconds={len(pcm)/2/SAMPLE_RATE:.2f}"
            )
            started_at = time.monotonic()
            response = client.post(
                _asr_endpoint(),
                headers=headers,
                files=files,
                timeout=20,
            )
            _debug(
                f"asr: status={response.status_code} "
                f"bytes={len(response.content)} "
                f"elapsed={time.monotonic() - started_at:.2f}s"
            )
        except Exception as exc:
            self._last_error = str(exc)
            _debug(f"asr: exception {exc!r}")
            self._emit_status(f"Live transcription failed: {exc}", "error")
            return ""

        if response.status_code != 200:
            message = ""
            try:
                body = response.json()
                error = body.get("error") if isinstance(body, dict) else None
                if isinstance(error, dict):
                    message = str(
                        error.get("message") or error.get("type") or ""
                    )
            except Exception:
                pass
            if not message:
                message = response.text.strip()[:400]
            self._last_error = (
                f"Meta ASR HTTP {response.status_code}: {message or 'request failed'}"
            )
            _debug(f"asr: error {self._last_error[:500]}")
            self._emit_status(self._last_error, "error")
            return ""

        try:
            body = response.json()
        except ValueError:
            self._emit_status("Live transcription returned invalid JSON.", "error")
            _debug(f"asr: invalid json {response.text[:500]!r}")
            return ""

        transcript = body.get("transcript") if isinstance(body, dict) else ""
        text = " ".join(str(transcript or "").split()).strip()
        _debug(f"asr: transcript={text!r} body={str(body)[:500]!r}")
        return text

    def _emit_transcript(self, text: str):
        callback = self.on_transcript
        if callback is None:
            return
        try:
            callback(text)
        except Exception as exc:
            self._last_error = str(exc)

    def _emit_status(self, message: str, level: str = "info"):
        callback = self.on_status
        if callback is None:
            return
        try:
            callback(message, level)
        except Exception:
            pass
