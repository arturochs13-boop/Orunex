"""Human-sounding text-to-speech for Orunex Live mode.

The primary voice is Microsoft Edge's neural TTS (via the ``edge-tts``
package).  It is dramatically more natural than the SAPI desktop voices and
does not require an API key.  If the network or the package is unavailable,
the speaker falls back to the local Windows SAPI voices so Live mode never
goes silent.

Playback is done with pygame's SDL mixer, which supports the MP3 stream that
Edge returns.  The whole operation runs on a worker thread and exposes a
generation counter so a stopped sentence can never play after Live is turned
off or a newer answer replaces it.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import tempfile
import threading
import time
from typing import Callable, Optional


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


_SPANISH_HINTS = re.compile(
    r"[\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00bf\u00a1]|"
    r"\b(hola|gracias|puedo|estoy|para|que|como|c\u00f3mo|claro|bueno|"
    r"ahora|tambien|archivo|tarea|hecho|listo|vale|perfecto|"
    r"agente|pantalla|voz|hablar|responder|abriendo|abierto|navegador)\b",
    re.IGNORECASE,
)
_ENGLISH_HINTS = re.compile(
    r"\b(the|and|you|your|this|that|with|from|have|will|can|please|"
    r"hello|here|task|file|ready|done|sure|how|what|Im|I am|opening|"
    r"browser|completed|successfully|open|close|start|stop|search|"
    r"find|create|delete|save|load|send|receive|help|assistant|"
    r"agent|computer|screen|window|tab|click|type|scroll|wait|"
    r"buy|sell|trade|order|stop|profit|loss|take|market|limit|"
    r"chart|candle|candlestick|price|entry|exit|position|"
    r"paper|real|funds|broker|account|balance|equity|margin|"
    r"buy|selling|buying|trading|traded|opened|closed|filled|"
    r"pending|confirmed|rejected|cancelled|executed|processing|"
    r"executing|done|ready|success|error|fail|failure|warning|"
    r"info|information|status|update|log|report|summary|"
    r"yes|no|maybe|probably|certainly|sure|absolutely|"
    r"today|yesterday|tomorrow|now|soon|later|always|never|"
    r"here|there|where|when|why|who|which|what|how|"
    r"good|bad|better|worse|best|worst|great|terrible|"
    r"happy|sad|angry|excited|nervous|calm|"
    r"hot|cold|warm|cool|wind|rain|sun|cloud|"
    r"red|blue|green|yellow|black|white|gray|orange|purple|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"hundred|thousand|million|billion|"
    r"dollar|euro|pound|yen|money|cash|"
    r"hour|minute|second|day|week|month|year|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"spring|summer|autumn|winter|"
    r"north|south|east|west|"
    r"country|city|town|village|street|avenue|"
    r"house|apartment|building|office|store|market|"
    r"restaurant|cafe|bar|hotel|hospital|school|church|"
    r"bank|post|police|fire|ambulance|"
    r"car|motorcycle|bicycle|bus|train|plane|boat|helicopter|"
    r"eat|drink|sleep|walk|run|swim|fly|"
    r"read|write|draw|paint|sing|dance|"
    r"play|work|study|teach|learn|"
    r"buy|sell|pay|charge|"
    r"love|hate|like|dislike|prefer|choose|"
    r"better|worse|more|less|very|quite|"
    r"everything|nothing|something|somebody|nobody|everybody|"
    r"all|none|my|your|his|her|its|our|their|"
    r"this|that|these|those|"
    r"which|who|whom|whose|how much|how many|"
    r"where|to where|from where|when|since|until|"
    r"for|with|without|on|under|between|toward|from|"
    r"and|or|but|although|if|like|while|"
    r"then|after|before|during|"
    r"now|then|already|still|not anymore|"
    r"always|never|sometimes|frequently|rarely|"
    r"probably|possibly|certainly|surely|"
    r"maybe|perhaps|probably|"
    r"well|badly|better|worse|optimal|pessimal|"
    r"easy|difficult|simple|complex|"
    r"fast|slow|quick|paused|"
    r"good|bad|regular|excellent|"
    r"high|low|big|small|medium|"
    r"long|short|wide|narrow|"
    r"fat|thin|slim|thin|"
    r"young|old|elderly|child|adult|"
    r"man|woman|boy|girl|guy|"
    r"father|mother|son|daughter|brother|sister|"
    r"friend|male friend|female friend|companion|"
    r"boss|employee|client|provider|"
    r"doctor|nurse|teacher|student|"
    r"lawyer|judge|police|firefighter|"
    r"cook|waiter|waitress|"
    r"artist|musician|painter|writer|"
    r"athlete|player|player|coach|"
    r"king|queen|prince|princess|"
    r"god|angel|demon|ghost|"
    r"cat|dog|bird|fish|horse|cow|pig|"
    r"sheep|goat|chicken|duck|rabbit|"
    r"lion|tiger|elephant|giraffe|monkey|bear|"
    r"wolf|fox|deer|rabbit|squirrel|"
    r"snake|lizard|turtle|frog|"
    r"fish|shark|whale|dolphin|"
    r"spider|scorpion|bee|wasp|"
    r"butterfly|ant|fly|mosquito|"
    r"flower|tree|plant|grass|"
    r"fruit|apple|pear|orange|banana|"
    r"grape|strawberry|watermelon|melon|"
    r"vegetable|vegetables|lettuce|tomato|onion|"
    r"potato|carrot|corn|bean|rice|"
    r"bread|cheese|butter|egg|meat|fish|"
    r"chicken|beef|pork|lamb|turkey|"
    r"milk|yogurt|ice cream|juice|soda|water|"
    r"coffee|tea|chocolate|beer|wine|"
    r"salt|sugar|honey|jam|"
    r"bread|cake|cookie|candy|"
    r"soup|salad|sandwich|hamburger|pizza|"
    r"taco|burrito|quesadilla|tamales|"
    r"ice|golf|tennis|soccer|basketball|"
    r"baseball|volleyball|swimming|cycling|"
    r"run|walk|hiking|camping|"
    r"fishing|hunting|skiing|skating|"
    r"dance|sing|music|painting|sculpture|"
    r"theater|cinema|television|radio|internet|"
    r"phone|computer|tablet|watch|"
    r"camera|microphone|speaker|printer|"
    r"keyboard|mouse|screen|cable|"
    r"battery|charger|plug|outlet|"
    r"lamp|light|candle|bulb|"
    r"door|window|wall|ceiling|floor|"
    r"bed|sofa|chair|table|shelf|wardrobe|"
    r"kitchen|bathroom|bedroom|living room|dining room|"
    r"garden|patio|balcony|terrace|"
    r"garage|storage|attic|basement|"
    r"country|continent|world|planet|earth|"
    r"sun|moon|star|sky|cloud|"
    r"sea|ocean|river|lake|pond|"
    r"mountain|hill|valley|desert|jungle|"
    r"forest|meadow|plain|"
    r"beach|island|peninsula|bay|gulf|"
    r"river|stream|spring|waterfall|"
    r"volcano|geyser|earthquake|hurricane|"
    r"tornado|flood|drought|fire|tremor|"
    r"accident|emergency|disaster|crisis|"
    r"war|peace|conflict|negotiation|"
    r"law|rule|norm|standard|policy|"
    r"government|president|minister|senator|deputy|"
    r"mayor|councilor|governor|"
    r"democracy|republic|monarchy|dictatorship|"
    r"election|vote|campaign|debate|"
    r"tax|budget|debt|credit|"
    r"bank|money|cash|card|check|"
    r"purchase|sale|rent|mortgage|loan|"
    r"insurance|policy|claim|coverage|"
    r"health|illness|pain|fever|"
    r"cough|cold|flu|covid|virus|bacteria|"
    r"vaccine|medicine|pill|injection|"
    r"doctor|nurse|hospital|clinic|pharmacy|"
    r"appointment|prescription|diagnosis|treatment|"
    r"operation|surgery|recovery|rehabilitation|"
    r"exercise|sport|gym|training|"
    r"diet|nutrition|food|meal|drink|"
    r"breakfast|lunch|dinner|snack|dessert|drink|"
    r"soda|juice|water|milk|coffee|"
    r"tea|chocolate|beer|wine|liquor\b",
    re.IGNORECASE,
)

_EDGE_VOICES = {
    # Male, natural-series voices.  Jorge (Mexico) keeps the user's accent
    # and sits in a medium register - warm without sounding deep.  Andrew
    # (US) is the newer natural male voice: lighter and more conversational
    # than the older Guy/Christopher set.
    "es": "es-MX-JorgeNeural",
    "en": "en-US-AndrewNeural",
}
_EDGE_RATE = "+6%"
_CACHE_DIR = os.path.join(tempfile.gettempdir(), "orunex_tts_cache")


_PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$culture = $env:ORUNEX_TTS_CULTURE
try {
    $candidates = $synth.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.Name -like ($culture + '*')
    }
    # Only a male voice may be used.  Falling back to the installed female
    # desktop voices changed Orunex's identity and sounded low quality, so
    # when no male SAPI voice exists the fallback stays silent and the text
    # answer still appears in the chat.
    $voice = $candidates | Where-Object {
        $_.VoiceInfo.Gender -eq 'Male'
    } | Select-Object -First 1
    if (-not $voice) { exit 0 }
    $synth.SelectVoice($voice.VoiceInfo.Name)
} catch { }
$text = [Console]::In.ReadToEnd()
if ($text) { $synth.Speak($text) }
$synth.Dispose()
"""


def clean_speech_text(text: str, limit: int = 1400) -> str:
    """Remove markdown, code, URLs and machine tags before speaking."""
    value = str(text or "")
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`[^`]*`", " ", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", " ", value)
    # Executor/agent tags such as [OPEN_URL: ...], [Cerebro], [OK].
    value = re.sub(r"\[[A-Z][A-Z0-9_ -]{0,45}(?::[^\]]*)?\]", " ", value)
    value = re.sub(
        r"\[(?:Cerebro|ORUNEX|Orunex|CEREBRO|Agent|SYSTEM|SISTEMA)[^\]]*\]",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"[*_#>|~]+", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    if len(value) > limit:
        cut = value[:limit]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if end >= 120:
            cut = cut[: end + 1]
        value = cut.rstrip(" ,;:") + "..."
    return value


def _split_speech_chunks(speech: str, max_len: int = 220) -> list:
    """Split a reply into sentence chunks that can be voiced independently.

    Synthesizing a whole paragraph before playing anything was the audible
    lag of Live mode: the text bubble appeared and the voice arrived seconds
    later.  Short chunks synthesize in a fraction of that time, and each one
    is cached on its own, so repeated sentences are instant forever.
    """
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", str(speech or ""))]
    chunks: list = []
    buffer = ""
    for part in parts:
        if not part:
            continue
        while len(part) > max_len:
            cut = max(
                part.rfind(", ", 0, max_len),
                part.rfind("; ", 0, max_len),
                part.rfind(" ", 0, max_len),
            )
            if cut < 60:
                cut = max_len
            chunks.append(part[:cut].strip(" ,;"))
            part = part[cut:].strip(" ,;")
        if not buffer:
            buffer = part
        elif len(buffer) + 1 + len(part) <= max_len:
            buffer = f"{buffer} {part}"
        else:
            chunks.append(buffer)
            buffer = part
    if buffer:
        chunks.append(buffer)
    return chunks or [str(speech or "")]


def _debug_enabled() -> bool:
    return os.environ.get("ORUNEX_LIVE_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def choose_voice_language(text: str, default: str = "es") -> str:
    """Pick Spanish or English from the response text."""
    value = str(text or "")
    spanish = len(_SPANISH_HINTS.findall(value))
    english = len(_ENGLISH_HINTS.findall(value))
    if spanish > english:
        return "es"
    if english > spanish:
        return "en"
    return default


class LiveSpeaker:
    """Neural voice output with a local SAPI fallback and hard stop."""

    def __init__(
        self,
        on_status: Optional[Callable[[str, str], None]] = None,
        default_language: str = "es",
    ):
        self.on_status = on_status
        self.default_language = default_language
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._generation = 0
        self._playback_lock = threading.Lock()
        self._last_error = ""

    @property
    def speaking(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------ public
    def speak(
        self,
        text: str,
        language: Optional[str] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> bool:
        speech = clean_speech_text(text)
        if not speech or os.name != "nt":
            return False

        # Incrementing the generation invalidates any older sentence and
        # stops its audio immediately.  Never join the old speech thread on
        # the caller's thread: that was a visible Live-mode stall.
        self.stop(wait=False)
        with self._lock:
            self._generation += 1
            generation = self._generation
        self._stop_event.clear()
        code = (language or choose_voice_language(speech, self.default_language)).lower()
        if not code.startswith(("es", "en")):
            code = self.default_language

        def worker():
            try:
                self._prepare_audio()
                if self._is_current(generation):
                    if self._speak_edge_fast(speech, code, generation):
                        return
                    # One short retry: the first Edge synthesis after a cold
                    # start can miss while later ones succeed.  Only after
                    # that may the (male-only) local fallback run.
                    time.sleep(0.35)
                    if self._is_current(generation) and self._speak_edge_fast(
                        speech, code, generation
                    ):
                        return
                    if self._is_current(generation):
                        if _debug_enabled():
                            print(
                                "[LIVE TTS] neural voice unavailable; "
                                "using SAPI fallback"
                            )
                        self._speak_sapi(speech, code, generation)
            finally:
                if self._is_current(generation) and on_done is not None:
                    try:
                        on_done()
                    except Exception:
                        pass

        self._thread = threading.Thread(
            target=worker, name="orunex-live-tts", daemon=True
        )
        self._thread.start()
        return True

    def stop(self, wait: bool = True) -> None:
        self._stop_event.set()
        with self._lock:
            self._generation += 1
            process = self._process
        # Stop the audible stream first.  Everything after this is cleanup and
        # may wait for synthesis; the user must not hear another syllable when
        # Live is switched off.
        self._stop_playback()
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                if wait:
                    process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        thread = self._thread
        self._thread = None
        if wait and thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def shutdown(self) -> None:
        self.stop()
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass

    def prepare(self) -> None:
        """Warm the audio device so the first answer starts without a hitch."""
        self._prepare_audio()

    def prepare_async(self) -> None:
        try:
            threading.Thread(
                target=self._prepare_audio,
                name="orunex-live-tts-warm",
                daemon=True,
            ).start()
        except Exception:
            pass

    def warm(self, texts, language: Optional[str] = None) -> None:
        """Pre-render common short replies into the on-disk voice cache.

        The first Edge synthesis is network-bound.  Commands such as
        ``abrir YouTube en Chrome`` always produce the same short sentence, so
        caching it turns every later reply into an instant local playback.
        """
        values = [clean_speech_text(item) for item in (texts or [])]
        values = [item for item in values if item]
        if not values:
            return

        def worker():
            self._prepare_audio()
            for speech in values:
                if self._stop_event.is_set():
                    return
                code = (
                    language or choose_voice_language(speech, self.default_language)
                ).lower()
                if not code.startswith(("es", "en")):
                    code = self.default_language
                target = self._cache_path(speech, code)
                if os.path.exists(target) and os.path.getsize(target) > 200:
                    continue
                try:
                    self._synthesize_edge_file(speech, code, target)
                except Exception as exc:
                    self._last_error = f"edge-tts warm: {exc}"

        try:
            threading.Thread(
                target=worker,
                name="orunex-live-tts-prewarm",
                daemon=True,
            ).start()
        except Exception:
            pass

    # ------------------------------------------------------------------ voices
    def _is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation and not self._stop_event.is_set()

    def _prepare_audio(self) -> bool:
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame  # type: ignore

            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=24000,
                    size=-16,
                    channels=2,
                    buffer=1024,
                )
            return True
        except Exception as exc:
            self._last_error = f"pygame: {exc}"
            return False

    def _cache_path(self, speech: str, code: str) -> str:
        voice = _EDGE_VOICES.get(code, _EDGE_VOICES["es"])
        digest = hashlib.sha1(
            f"{voice}|{_EDGE_RATE}|{speech}".encode("utf-8")
        ).hexdigest()
        return os.path.join(_CACHE_DIR, f"{voice}_{digest}.mp3")

    def _synthesize_edge_file(
        self, speech: str, code: str, target: str, timeout: float = 10.0
    ) -> bool:
        """Synthesize one MP3 atomically into ``target`` (or its cache)."""
        import edge_tts  # type: ignore

        os.makedirs(_CACHE_DIR, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix="orunex_voice_", suffix=".part.mp3", dir=_CACHE_DIR
        )
        os.close(fd)
        voice = _EDGE_VOICES.get(code, _EDGE_VOICES["es"])
        try:
            async def synthesize():
                communicate = edge_tts.Communicate(
                    speech,
                    voice=voice,
                    rate=_EDGE_RATE,
                    volume="+0%",
                    pitch="+0Hz",
                )
                await communicate.save(temporary)

            if _debug_enabled():
                print(
                    f"[LIVE TTS] neural voice={voice} chars={len(speech)} "
                    f"cache={'hit' if os.path.exists(target) else 'miss'}"
                )
            asyncio.run(asyncio.wait_for(synthesize(), timeout=timeout))
            if not os.path.exists(temporary) or os.path.getsize(temporary) < 200:
                return False
            os.replace(temporary, target)
            return True
        finally:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except Exception:
                pass

    def _speak_edge_fast(self, speech: str, code: str, generation: int) -> bool:
        """Voice-first playback: synthesize sentence chunks, play in order.

        A background thread renders chunk N+1 while chunk N is playing, so
        the first sound starts after one short synthesis instead of after
        the whole reply has been rendered.  Returns False only when nothing
        could be played at all, so the caller can fall back to SAPI.
        """
        chunks = _split_speech_chunks(speech)
        if len(chunks) <= 1:
            return self._speak_edge(speech, code, generation)

        paths = [self._cache_path(chunk, code) for chunk in chunks]
        ready = [threading.Event() for _ in chunks]
        failed = [False] * len(chunks)

        def synthesize_one(index, chunk):
            try:
                if not self._is_current(generation):
                    failed[index] = True
                    return
                target = paths[index]
                ok = os.path.exists(target) and os.path.getsize(target) > 200
                if not ok:
                    try:
                        ok = self._synthesize_edge_file(chunk, code, target)
                    except Exception as exc:
                        self._last_error = f"edge-tts: {exc}"
                        ok = False
                failed[index] = not ok
            finally:
                ready[index].set()

        def synthesizer():
            # Render every chunk in parallel (bounded).  The player below
            # still speaks them strictly in order, but it never waits for a
            # sequential synthesis chain while a short chunk is playing.
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(synthesize_one, index, chunk)
                    for index, chunk in enumerate(chunks)
                ]
                for future in futures:
                    try:
                        future.result(timeout=25.0)
                    except Exception:
                        pass

        threading.Thread(
            target=synthesizer,
            name="orunex-live-tts-synth",
            daemon=True,
        ).start()

        played = False
        for index, path in enumerate(paths):
            deadline = time.monotonic() + 25.0
            while not ready[index].wait(0.05):
                if not self._is_current(generation):
                    return True
                if time.monotonic() > deadline:
                    failed[index] = True
                    break
            if not self._is_current(generation):
                return True
            if failed[index]:
                # If some audio already played, end gracefully instead of
                # restarting the whole reply with the fallback voice.
                return played
            ok_play = self._play_mp3(path, generation)
            played = True
            if not ok_play:
                if not self._is_current(generation):
                    return True
                return played and index > 0
        return True

    def _speak_edge(self, speech: str, code: str, generation: int) -> bool:
        """Use cached neural audio, or synthesize once and play it."""
        try:
            target = self._cache_path(speech, code)
            cached = os.path.exists(target) and os.path.getsize(target) > 200
            if not cached:
                if not self._synthesize_edge_file(speech, code, target):
                    return False
            if not self._is_current(generation):
                return True
            if not os.path.exists(target) or os.path.getsize(target) < 200:
                return False
            if not self._play_mp3(target, generation):
                return False
            return True
        except Exception as exc:
            self._last_error = f"edge-tts: {exc}"
            return False

    def _play_mp3(self, path: str, generation: int) -> bool:
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame  # type: ignore
        except Exception as exc:
            self._last_error = f"pygame: {exc}"
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=1024)
            with self._playback_lock:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play()
            deadline = time.monotonic() + 180.0
            while pygame.mixer.music.get_busy() and time.monotonic() < deadline:
                if not self._is_current(generation):
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            return self._is_current(generation)
        except Exception as exc:
            self._last_error = f"pygame playback: {exc}"
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            return False

    def _stop_playback(self) -> None:
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def _speak_sapi(self, speech: str, code: str, generation: int) -> bool:
        """Local fallback. It still uses the old desktop voices."""
        process = None
        try:
            env = os.environ.copy()
            env["ORUNEX_TTS_CULTURE"] = code
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    _PS_SCRIPT,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=env,
            )
            with self._lock:
                self._process = process
            if process.stdin is not None:
                process.stdin.write(speech)
                process.stdin.close()
            process.wait()
            return self._is_current(generation)
        except Exception as exc:
            self._last_error = f"SAPI: {exc}"
            return False
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

    def _emit_status(self, message: str, level: str = "info"):
        callback = self.on_status
        if callback is None:
            return
        try:
            callback(message, level)
        except Exception:
            pass
