"""Floating Copilot widget for Orunex.

A small always-on-top assistant with a live screen preview, a compact chat,
optional offline voice input, and a write-back action for generated code.
"""
import queue
import re
import subprocess
import tempfile
import threading
import time

import customtkinter as ctk  # type: ignore
from PIL import Image  # type: ignore

CTHEME = {
    "bg": "#F8F9FA",
    "surface": "#FFFFFF",
    "surface_soft": "#F8F9FA",
    "surface_muted": "#F2F4F7",
    "border": "#E6E9EE",
    "border_strong": "#D9DEE6",
    "blue": "#0668E1",
    "blue_soft": "#EDF4FF",
    "blue_border": "#CFE2FF",
    "red": "#E15241",
    "red_soft": "#FEF1EF",
    "text": "#111318",
    "text_dim": "#667085",
    "muted": "#98A2B3",
}

_VISUAL_KW = [
    "what do you see", "what is on screen", "describe", "look", "screen",
    "screenshot", "what does it show", "what does it say", "click", "press",
    "button", "que ves", "qué ves", "que hay", "qué hay", "mira", "pantalla",
    "captura", "que muestra", "qué muestra", "que dice", "qué dice", "pulsa",
    "presiona", "boton", "botón",
]
_CHAT_KW = [
    "hello", "hi", "hey", "who are you", "how are you", "thanks", "thank you",
    "what can you do", "help", "what are you", "hola", "buenas", "quien eres",
    "quién eres", "como estas", "cómo estás", "gracias", "que puedes",
    "qué puedes", "ayuda", "que eres", "que haces",
]
_ACTION_KW = [
    "open", "close", "create", "make", "run", "search", "install", "write",
    "download", "move", "delete", "remove", "launch", "start", "copy", "paste",
    "click", "press", "turn on", "abre", "cierra", "crea", "haz", "ejecuta",
    "busca", "instala", "escribe", "presenta", "descarga", "mueve", "borra",
    "elimina", "lanza", "inicia", "copia", "pega", "pon", "enciende", "pulsa",
    "presiona",
]


def _strip_markdown(text: str) -> str:
    """Remove formatting so speech sounds natural."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _speak_async(text: str):
    clean = _strip_markdown(text)[:450]
    clean = clean.replace('"', "").replace("'", "").replace("\n", ". ")
    script = f"""import pyttsx3
try:
    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.say("{clean}")
    engine.runAndWait()
except Exception:
    pass
"""
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    threading.Thread(
        target=subprocess.run,
        args=(["python", "-c", script],),
        kwargs={"creationflags": create_no_window, "timeout": 45},
        daemon=True,
    ).start()


class CopilotoWidget(ctk.CTkToplevel):
    """Floating Copilot with vision, chat, and optional voice input."""

    def __init__(self, cerebro_run_fn, user_name: str = "User", on_close=None):
        super().__init__()
        self._cerebro_run = cerebro_run_fn
        self._user_name = user_name
        self._on_close_callback = on_close
        self._closed = False
        self._vision_on = True
        self._mic_active = False
        self._voice_thread_started = False
        self._running = True
        self._last_frame = None

        self.title("Copilot — Orunex")
        try:
            scale = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        except Exception:
            scale = 1.0
        available_h = int(self.winfo_screenheight() / scale)
        panel_height = min(640, max(500, available_h - 100))
        self.geometry(f"340x{panel_height}+40+20")
        self.resizable(False, False)
        self.configure(fg_color=CTHEME["bg"])
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.bind("<ButtonPress-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_move)
        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()
        self._start_vision_thread()
        self.chat_append(
            "Ready. Ask me about your screen or type a task.",
            "bot",
        )

    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _drag_move(self, event):
        self.geometry(
            f"+{self.winfo_x() + event.x - self._drag_x}"
            f"+{self.winfo_y() + event.y - self._drag_y}"
        )

    def _build_ui(self):
        header = ctk.CTkFrame(
            self, fg_color=CTHEME["surface"], corner_radius=0, height=46
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Copilot",
            font=("Segoe UI", 12, "bold"),
            text_color=CTHEME["text"],
        ).pack(side="left", padx=(12, 8))

        ctk.CTkButton(
            header,
            text="×",
            width=26,
            height=26,
            corner_radius=7,
            fg_color="transparent",
            text_color=CTHEME["red"],
            hover_color=CTHEME["red_soft"],
            font=("Segoe UI", 14),
            command=self.close,
        ).pack(side="right", padx=(2, 8))

        self._vision_btn = ctk.CTkButton(
            header,
            text="Vision on",
            width=66,
            height=26,
            corner_radius=7,
            fg_color=CTHEME["blue_soft"],
            text_color=CTHEME["blue"],
            hover_color=CTHEME["blue_border"],
            font=("Segoe UI", 9, "bold"),
            command=self._toggle_vision,
        )
        self._vision_btn.pack(side="right", padx=2)

        self._monitor_var = ctk.StringVar(value="Monitor 1")
        self._mon_menu = ctk.CTkOptionMenu(
            header,
            values=["Monitor 1", "Monitor 2", "Monitor 3", "All monitors"],
            width=94,
            height=26,
            corner_radius=7,
            variable=self._monitor_var,
            font=("Segoe UI", 9),
            fg_color=CTHEME["surface_soft"],
            button_color=CTHEME["surface_soft"],
            button_hover_color=CTHEME["surface_muted"],
            dropdown_fg_color=CTHEME["surface"],
            dropdown_hover_color=CTHEME["surface_muted"],
            dropdown_text_color=CTHEME["text"],
            text_color=CTHEME["text_dim"],
            command=self._on_monitor_change,
        )
        self._mon_menu.pack(side="right", padx=2)

        ctk.CTkFrame(self, height=1, fg_color=CTHEME["border"]).pack(fill="x")

        preview_frame = ctk.CTkFrame(
            self,
            fg_color=CTHEME["surface"],
            corner_radius=10,
            border_width=1,
            border_color=CTHEME["border"],
            height=118,
        )
        preview_frame.pack(fill="x", padx=10, pady=(10, 4))
        preview_frame.pack_propagate(False)

        self._preview_lbl = ctk.CTkLabel(
            preview_frame,
            text="Starting screen preview...",
            text_color=CTHEME["text_dim"],
            font=("Segoe UI", 9),
        )
        self._preview_lbl.pack(expand=True)

        self._chat_box = ctk.CTkTextbox(
            self,
            fg_color=CTHEME["surface"],
            text_color=CTHEME["text"],
            font=("Segoe UI", 10),
            corner_radius=10,
            border_width=1,
            border_color=CTHEME["border"],
            wrap="word",
            state="disabled",
        )
        self._chat_box.pack(fill="both", expand=True, padx=10, pady=4)

        text_widget = self._chat_box._textbox
        text_widget.tag_configure("bot", foreground=CTHEME["text"])
        text_widget.tag_configure("user", foreground=CTHEME["blue"])
        text_widget.tag_configure("err", foreground=CTHEME["red"])
        text_widget.tag_configure("sys", foreground=CTHEME["text_dim"])

        input_row = ctk.CTkFrame(self, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 4))

        self._input_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Ask about your screen or type a task...",
            fg_color=CTHEME["surface"],
            border_color=CTHEME["border"],
            text_color=CTHEME["text"],
            placeholder_text_color=CTHEME["muted"],
            font=("Segoe UI", 10),
            corner_radius=8,
            height=34,
        )
        self._input_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._input_entry.bind("<Return>", lambda _event: self._on_send())

        self._mic_btn = ctk.CTkButton(
            input_row,
            text="Mic",
            width=42,
            height=34,
            corner_radius=8,
            fg_color=CTHEME["surface"],
            border_width=1,
            border_color=CTHEME["border"],
            text_color=CTHEME["text_dim"],
            hover_color=CTHEME["surface_muted"],
            font=("Segoe UI", 9),
            command=self._toggle_mic,
        )
        self._mic_btn.pack(side="left")

        self._fix_btn = ctk.CTkButton(
            self,
            text="Apply to IDE",
            font=("Segoe UI", 10, "bold"),
            fg_color=CTHEME["blue"],
            text_color="#FFFFFF",
            hover_color="#0059C7",
            height=34,
            corner_radius=8,
            command=self._apply_fix_to_ide,
        )

        self._status_lbl = ctk.CTkLabel(
            self,
            text="Ready",
            font=("Segoe UI", 8),
            text_color=CTHEME["text_dim"],
        )
        self._status_lbl.pack(pady=(0, 6))

    def chat_append(self, text: str, tag: str = "sys"):
        def do_insert():
            self._chat_box.configure(state="normal")
            prefix = {
                "bot": "Copilot: ",
                "user": "You: ",
                "err": "Error: ",
                "sys": "",
            }.get(tag, "")
            self._chat_box._textbox.insert("end", prefix + text + "\n\n", tag)
            self._chat_box._textbox.see("end")
            self._chat_box.configure(state="disabled")

            if "```" in text:
                self._show_fix_btn(text)
            else:
                self._hide_fix_btn()

        self.after(0, do_insert)

    def _on_monitor_change(self, value):
        self.chat_append(f"Switched preview to {value}.", "sys")

    def _get_monitor_index(self) -> int:
        value = self._monitor_var.get()
        if value.startswith("Monitor"):
            try:
                return int(value.split()[-1])
            except ValueError:
                return 1
        return 0

    def _set_status(self, message: str):
        self.after(0, lambda: self._status_lbl.configure(text=message))

    def _on_send(self, spoken_text=None):
        task = spoken_text or self._input_entry.get().strip()
        if not task:
            return
        if not spoken_text:
            self._input_entry.delete(0, "end")
        self.chat_append(task, "user")
        threading.Thread(
            target=self._process_task,
            args=(task, spoken_text is not None),
            daemon=True,
        ).start()

    def _process_task(self, task: str, from_voice: bool):
        self._set_status("Thinking...")
        try:
            lowered = task.lower()
            use_frame = (
                self._last_frame
                if any(keyword in lowered for keyword in _VISUAL_KW)
                else None
            )

            is_chat = any(keyword in lowered for keyword in _CHAT_KW) and not any(
                keyword in lowered for keyword in _ACTION_KW
            )
            mode = "natural" if is_chat else "os"

            if use_frame:
                task = f"{task} (Monitor {self._get_monitor_index()})"

            result = self._cerebro_run(
                task, self._user_name, use_frame, agent_mode=mode
            )
            if not result or not result.strip():
                result = "I could not generate a response. Please try again."

            if mode == "os" and "[" in result:
                from _orunex_libs.os_executor import intercept_and_execute

                self._set_status("Thinking...")
                execution_result = intercept_and_execute(result)
                if execution_result:
                    self.chat_append(
                        f"Execution results:\n{execution_result}", "sys"
                    )

            self.chat_append(result, "bot")
            if from_voice:
                _speak_async(result)
        except Exception as exc:
            self.chat_append(f"Internal error: {exc}", "err")
        finally:
            try:
                from _orunex_libs.os_executor import set_copiloto_context

                set_copiloto_context(False)
            except Exception:
                pass
            self._set_status("Ready")

    def _show_fix_btn(self, text):
        self._last_code_detected = text
        self._fix_btn.pack(fill="x", padx=10, pady=5, before=self._status_lbl)

    def _hide_fix_btn(self):
        self._fix_btn.pack_forget()

    def _apply_fix_to_ide(self):
        if not getattr(self, "_last_code_detected", None):
            return

        match = re.search(
            r"```(?:\w+)?\n(.*?)\n```", self._last_code_detected, re.DOTALL
        )
        if not match:
            return

        code = match.group(1)
        parent = self.master
        if hasattr(parent, "ide_tabs") and hasattr(parent, "current_ide_files"):
            active_tab = parent.ide_tabs.get()
            if active_tab in parent.current_ide_files:
                editor = parent.current_ide_files[active_tab]["editor"]
                editor.delete("1.0", "end")
                editor.insert("1.0", code)
                self.chat_append("Code applied to the active IDE file.", "sys")
                self._hide_fix_btn()
            else:
                self.chat_append("No file is open in the IDE.", "err")
        else:
            self.chat_append("Could not connect to the IDE.", "err")

    def _toggle_vision(self):
        self._vision_on = not self._vision_on
        if self._vision_on:
            self._vision_btn.configure(
                text="Vision on",
                fg_color=CTHEME["blue_soft"],
                text_color=CTHEME["blue"],
            )
        else:
            self._vision_btn.configure(
                text="Vision off",
                fg_color=CTHEME["surface_muted"],
                text_color=CTHEME["text_dim"],
            )

    def _start_vision_thread(self):
        def loop():
            try:
                import mss
                import mss.tools  # type: ignore

                has_mss = True
            except ImportError:
                has_mss = False

            while self._running:
                try:
                    if self._vision_on:
                        temp_file = tempfile.NamedTemporaryFile(
                            delete=False, suffix=".png"
                        )
                        temp_file.close()
                        temp_path = temp_file.name

                        if has_mss:
                            import mss  # type: ignore

                            with mss.mss() as capture:
                                monitor_index = self._get_monitor_index()
                                if monitor_index > 0:
                                    monitor_index = min(
                                        max(1, monitor_index),
                                        len(capture.monitors) - 1,
                                    )
                                    shot = capture.grab(capture.monitors[monitor_index])
                                    mss.tools.to_png(
                                        shot.rgb, shot.size, output=temp_path
                                    )
                                else:
                                    import pyautogui  # type: ignore

                                    pyautogui.screenshot().save(temp_path)
                        else:
                            import pyautogui  # type: ignore

                            pyautogui.screenshot().save(temp_path)

                        self._last_frame = temp_path
                        self._update_preview(temp_path)
                    time.sleep(2.5)
                except Exception:
                    time.sleep(5)

        threading.Thread(target=loop, daemon=True).start()

    def _update_preview(self, path: str):
        def do_update():
            try:
                image = Image.open(path)
                image.thumbnail((320, 112))
                self._preview_ctk = ctk.CTkImage(
                    light_image=image, dark_image=image, size=image.size
                )
                self._preview_lbl.configure(image=self._preview_ctk, text="")
            except Exception:
                pass

        self.after(0, do_update)

    def _toggle_mic(self):
        self._mic_active = not self._mic_active
        if self._mic_active:
            self._mic_btn.configure(
                fg_color=CTHEME["red_soft"],
                border_color=CTHEME["red"],
                text_color=CTHEME["red"],
            )
            if not self._voice_thread_started:
                self._voice_thread_started = True
                self._start_voice_thread()
            self._set_status("Listening...")
        else:
            self._mic_btn.configure(
                fg_color=CTHEME["surface"],
                border_color=CTHEME["border"],
                text_color=CTHEME["text_dim"],
            )
            self._set_status("Mic off")

    def _start_voice_thread(self):
        def loop():
            try:
                from faster_whisper import WhisperModel  # type: ignore
                import sounddevice as sd  # type: ignore
                import numpy as np  # type: ignore
            except ImportError:
                self.chat_append(
                    "Voice input needs faster-whisper and sounddevice.",
                    "err",
                )
                return

            self._set_status("Voice ready")
            try:
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
            except Exception as exc:
                self.chat_append(f"Could not load Whisper: {exc}", "err")
                return

            audio_queue = queue.Queue()

            def callback(indata, frames, timestamp, status):
                if self._mic_active:
                    audio_queue.put(indata.copy())

            with sd.InputStream(
                samplerate=16000, channels=1, callback=callback
            ):
                while self._running:
                    if not self._mic_active:
                        time.sleep(0.3)
                        continue

                    audio_chunks = []
                    self._set_status("Listening...")
                    silence_chunks = 0
                    max_silence = 10
                    energy_threshold = 0.012

                    while self._mic_active:
                        try:
                            chunk = audio_queue.get(timeout=0.08)
                            audio_chunks.append(chunk)
                            energy = np.abs(chunk).mean()
                            if energy < energy_threshold:
                                silence_chunks += 1
                            else:
                                silence_chunks = 0
                            if silence_chunks >= max_silence and len(audio_chunks) > 6:
                                break
                        except queue.Empty:
                            if audio_chunks:
                                break

                    if not audio_chunks:
                        continue

                    full_audio = np.concatenate(audio_chunks, axis=0).flatten()
                    if len(full_audio) < 4000:
                        continue

                    self._set_status("Transcribing...")
                    segments, _info = model.transcribe(full_audio, beam_size=1)
                    text = "".join(segment.text for segment in segments).strip()
                    if text and len(text) > 1:
                        self._set_status(f"Heard: {text[:28]}...")
                        self._on_send(spoken_text=text)

                    time.sleep(0.1)

        threading.Thread(target=loop, daemon=True).start()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._running = False
        self._mic_active = False
        try:
            from _orunex_libs.os_executor import set_copiloto_context

            set_copiloto_context(False)
        except Exception:
            pass
        callback = self._on_close_callback
        try:
            self.destroy()
        finally:
            if callback:
                try:
                    callback()
                except Exception:
                    pass
