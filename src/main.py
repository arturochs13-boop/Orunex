import sys
import io
import os

# Tk must see the real desktop resolution so the window can fill the screen
# and the footer/composer are not clipped on high-DPI Windows displays. This
# has to run before tkinter creates any window.
if os.name == "nt":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    if sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True,
            write_through=True,
        )
    if sys.stderr is not None:
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True,
            write_through=True,
        )
except:
    pass

import random
import math
import colorsys
import tkinter as tk
import tkinter.font as tkfont
import threading
import time
import traceback
import re
from tkinter import messagebox, simpledialog

# --- NUCLEAR LAYOUT GUARD (Global) ---
LAYOUT = "ORUNEX_GUARD"
# INFERENCE CORE — Meta Model API (configured through META_API_KEY).

# --- IMPORTACIONES ---
try:
    import customtkinter as ctk # type: ignore
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk # type: ignore
    import pyautogui # type: ignore
    from fpdf import FPDF # type: ignore
    from docx import Document # type: ignore

    # Keep the desktop layout predictable on Windows displays with custom DPI
    # scaling. The window still fits low-resolution screens; the UI simply uses
    # a 1:1 scale instead of multiplying every dimension by the OS scale.
    ctk.set_window_scaling(1.0)
    ctk.set_widget_scaling(1.0)
except Exception as e:
    import traceback
    traceback.print_exc()
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing application dependencies",
        f"Could not import a required module:\n{e}\n\n"
        "Run: pip install -r requirements.txt",
    )
    sys.exit(1)

# --- RUTAS ---
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS # type: ignore
    ICON_PATH = os.path.join(BASE_DIR, "orunex.ico")
    IMG_PATH = os.path.join(BASE_DIR, "orunex.png")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ICON_PATH = os.path.join(BASE_DIR, "orunex.ico")
    IMG_PATH = os.path.join(BASE_DIR, "orunex.png")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# --- UTILS (inline para evitar dependencias rotas) ---
from _orunex_libs.languages import LANGUAGES # type: ignore
from _orunex_libs import database, project_manager, chat_store # type: ignore
from _orunex_libs import mode_router, artifact_studio # type: ignore
from _orunex_libs.live_vision import LiveVisionSession, MetaVisionProvider # type: ignore
from widgets.live_vision_button import LiveVisionButton # type: ignore
from widgets.animated_gradient_text import AnimatedGradientText # type: ignore
# Orunex light design system. Meta blue is the single accent; red is reserved
# for emergency and destructive actions.
THEME = {
    "bg": "#F8F9FA",
    "fg": "#111318",
    "accent": "#0668E1",
    "accent_hover": "#0059C7",
    "secondary": "#F2F4F7",
    "panel": "#FFFFFF",
    "surface": "#FFFFFF",
    "surface_soft": "#F8F9FA",
    "surface_muted": "#F2F4F7",
    "success": "#0668E1",
    "warning": "#B54708",
    "error": "#E15241",
    "error_hover": "#C94334",
    "border": "#E6E9EE",
    "border_strong": "#D9DEE6",
    "blue": "#0668E1",
    "blue_soft": "#EDF4FF",
    "blue_border": "#CFE2FF",
    "red": "#E15241",
    "red_soft": "#FEF1EF",
    "red_border": "#F4CFC9",
    "text": "#111318",
    "text_dim": "#667085",
    "muted": "#98A2B3",
    "glass": "#FFFFFF",
    "warning_soft": "#FFF7ED",
}

def fade_in(widget, alpha=0.0, step=0.02):
    if alpha < 1.0:
        widget.attributes("-alpha", alpha)
        widget.after(30, lambda: fade_in(widget, alpha + step, step))
    else:
        widget.attributes("-alpha", 1.0)
        
def fade_out_and_destroy(widget, alpha=1.0, step=0.04, on_complete=None):
    if alpha > 0.0:
        widget.attributes("-alpha", alpha)
        widget.after(30, lambda: fade_out_and_destroy(widget, alpha - step, step, on_complete))
    else:
        if on_complete:
            on_complete()
        # Never destroy the widget from inside its own `after` callback:
        # Tk's callit() would then try to delete the command from a widget
        # whose command table is already gone.  Hand the destroy to the root.
        try:
            host = widget._root()
        except Exception:
            host = None
        try:
            if host is not None and host is not widget and host.winfo_exists():
                host.after(0, widget.destroy)
            else:
                widget.destroy()
        except Exception:
            try:
                widget.destroy()
            except Exception:
                pass


def fit_window(window, width, height, min_width=360, min_height=320):
    """Size a secondary window for the effective desktop area.

    CustomTkinter reports physical screen pixels while Tk geometry values are
    multiplied by the window scaling factor. Dividing by that factor keeps
    dialogs inside the work area on 125/150% Windows displays.
    """
    try:
        scale = ctk.ScalingTracker.get_window_scaling(window) or 1.0
    except Exception:
        scale = 1.0
    available_w = int(window.winfo_screenwidth() / scale)
    available_h = int(window.winfo_screenheight() / scale)
    final_w = min(width, max(min_width, available_w - 40))
    final_h = min(height, max(min_height, available_h - 80))
    x = max(0, (available_w - final_w) // 2)
    y = max(0, (available_h - final_h) // 2)
    window.geometry(f"{final_w}x{final_h}+{x}+{y}")


def _brain_available():
    """Cheap check for the configured inference backend."""
    try:
        from _orunex_libs import ollama_client

        if hasattr(ollama_client, "is_available"):
            return bool(ollama_client.is_available())

        model_path = getattr(ollama_client, "_MODEL_PATH", "")
        return bool(model_path and os.path.exists(model_path))
    except Exception:
        return False


# --- AGENTS ---
from agents.cerebro import run as cerebro_run # type: ignore
from agents.supervisor import decide_agent # type: ignore

AGENTS_INFO = {
    "Cerebro": {"run": cerebro_run, "color": "#0668E1", "icon": "[CORE]", "desc": "Orunex Core reasoning and task planning."},
}

INTERNAL_AGENTS = {
    "Cerebro": {"run": cerebro_run, "color": THEME["accent"], "icon": "[VOC]"},
}


# --- APP PRINCIPAL ---
class OrunexApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orunex — Desktop Agent")
        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        try:
            window_scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            window_scale = 1.0
        window_scale = window_scale or 1.0
        physical_work_w = screen_w
        physical_work_h = screen_h

        # Keep the window inside the usable desktop. On Windows the taskbar
        # occupies part of the screen, and a DPI-aware Tk window can otherwise
        # extend underneath it, hiding the composer footer.
        work_x = 0
        work_y = 0
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes

                work_area = wintypes.RECT()
                if ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(work_area), 0
                ):
                    physical_work_w = work_area.right - work_area.left
                    physical_work_h = work_area.bottom - work_area.top
                    work_x = int(work_area.left / window_scale)
                    work_y = int(work_area.top / window_scale)
            except Exception:
                pass

        # On compact high-DPI displays a 150% Tk scale can make the shell's
        # 1040x600 logical footprint larger than the physical work area. That
        # clipped the composer footer off-screen. Reduce the global window and
        # widget scale just enough to keep the whole shell visible.
        try:
            desired_scale = min(
                1.25,
                (physical_work_w - 24) / 1240.0,
                (physical_work_h - 56) / 600.0,
            )
            desired_scale = max(0.75, desired_scale)
            if desired_scale < window_scale:
                factor = desired_scale / window_scale
                ctk.set_widget_scaling(max(0.4, factor))
                ctk.set_window_scaling(max(0.4, factor))
                window_scale = (
                    ctk.ScalingTracker.get_window_scaling(self) or 1.0
                )
        except Exception:
            pass

        available_w = int(physical_work_w / window_scale)
        available_h = int(physical_work_h / window_scale)
        width = min(1240, max(1000, available_w - 24))
        height = min(840, max(600, available_h - 72))
        min_height = min(720, max(560, available_h - 120))
        x = max(work_x, work_x + (available_w - width) // 2)
        # Account for the native title bar when centring the outer window.
        y = max(work_y, work_y + (available_h - height - 38) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(1040, min_height)
        self.resizable(True, True)
        ctk.set_appearance_mode("light")

        # Variables
        self.execution_status = "IDLE"
        import threading
        self.execution_flag = threading.Event()
        self.current_agent = "Cerebro"
        self.agent_mode = "natural"  # "natural" or "os"
        self.user_name = "User"
        self.fullscreen_state = False
        self.current_language = "English"
        self.lang_dict = LANGUAGES["English"]
        self.is_processing = False
        self._glow_active = False
        self._screen_glow = None
        self._live_vision_active = False
        self._live_vision_session = None
        self._live_audio_session = None
        self._live_speaker = None
        self._live_transcript_queue = []
        self._live_conversation_until = 0.0
        self._live_recent_transcripts = None
        self._last_live_vision_frame = None
        self._last_live_toggle = 0.0
        self._live_audio_watch_after = None
        self._command_context = {}
        self._shutting_down = False
        self._thinking_visible = False
        self._thinking_after_id = None
        self._thinking_phase = 0.0
        self._thinking_idle_since = None
        self._vscode_visible = False
        self._vscode_after_id = None
        self._vscode_phase = 0.0
        self._vscode_min_visible_until = 0.0
        self._vscode_last_status = ""
        self.current_mode = mode_router.MODE_DEFAULT
        self._resolved_mode = mode_router.MODE_DEFAULT
        self._logo_image = None
        self._active_view = "workspace"
        self._simplex_paired = False
        self._simplex_connected = False
        self._settings_view = None
        self._simplex_view = None
        self._memory_view = None
        self._simplex_link = ""
        self._simplex_busy = False
        self._simplex_qr_ctk = None
        self._composer_glow_photo = None
        self._composer_glow_image_id = None
        self._composer_glow_phase = 0.0
        self._composer_focused = False
        self._composer_glow_masks = None
        self._chat_menu = None
        self._chat_menu_click_bind = None
        self._chat_menu_escape_bind = None
        self._sidebar_expanded = True
        self._sidebar_width = 252
        self._sidebar_collapsed_width = 72
        self.empty_state = None
        self._empty_headline = None
        self._current_chat_key = "current"
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.end_fullscreen)

        # --- Configuration ---
        from _orunex_libs import config_manager
        self.config = config_manager.load_config()
        self.user_name = self.config.get("user_name") or "User"

        # --- Local chat history ---
        # Chats are loaded before the UI is built so the sidebar can show the
        # saved conversations on the first frame.
        self.chats = chat_store.load_chats()
        self.current_chat = None
        self.current_chat_id = None
        self._initial_chat_loaded = False
        self._send_screenshot_var = ctk.StringVar(
            value="1" if self.config.get("send_screenshot", True) else "0"
        )
        self._send_remote_screenshot_var = ctk.StringVar(
            value="1" if self.config.get("send_remote_screenshot", False) else "0"
        )

        # UI
        self.configure(fg_color=THEME["bg"])
        self.create_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_splash()

        # The splash animates while these services start. Running them after
        # the event loop begins avoids freezing the intro and leaving the main
        # window visible behind the splash on slower machines.
        self._backend_ready = False
        self.after(700, self._start_backend_services)

    def _start_backend_services(self):
        """Bring up background services without blocking the intro animation."""
        try:
            # Phase 119: Evolution Heartbeat
            self.start_evolution_heartbeat()

            # --- Phase 35: Backend Services Init ---
            import _orunex_libs.languages as languages # type: ignore
            import _orunex_libs.permissions as perms # type: ignore
            import _orunex_libs.simplex_bridge as simplex # type: ignore
            import _orunex_libs.heartbeat as hb # type: ignore

            perms.set_ui_confirm_callback(self.ui_confirm_dangerous_action)
            success, msg = simplex.init_bridge(
                on_command_callback=self.handle_simplex_command
            )
            if success:
                print(f"[OK] Bridge Simplex: {msg}")
            hb.set_callbacks(self.run_silent_agent_task, simplex.notify)
            hb.start()

            # --- Phase 87/92: Simplex UI Monitor & Maintenance ---
            self.start_simplex_monitor()
            self.start_maintenance_loop()

            # --- Phase 120: Sovereign Automation Engine (Zero-Sim) ---
            try:
                from _orunex_libs.automation_daemon import get_daemon # type: ignore
                from _orunex_libs.os_executor import intercept_and_execute # type: ignore
                daemon = get_daemon()
                daemon.callback = intercept_and_execute
                daemon.start()
                print("[OK] Motor de Automatización Orunex V11.0 Iniciado.")
            except Exception as e:
                print(f"[ERR] No se pudo arrancar el motor de automatización: {e}")

            # --- V46.0: Register live UI progress callback ---
            try:
                from _orunex_libs.os_executor import register_ui_progress_callback  # type: ignore

                def _ui_progress_handler(msg: str, mtype: str = "info"):
                    """Called from executor threads — safely updates via self.after()."""
                    def _update():
                        try:
                            self.write_real_time(
                                msg,
                                mtype if mtype in ("info", "warn", "error", "success") else "info",
                            )
                        except Exception:
                            pass
                    self.after(0, _update)
                register_ui_progress_callback(_ui_progress_handler)
                print("[OK] UI Progress Callback registrado.")
            except Exception as e:
                print(f"[WARN] No se pudo registrar UI progress callback: {e}")
        except Exception as e:
            print(f"[ERR] Backend startup: {e}")
        finally:
            self._backend_ready = True
            self._maybe_finish_splash()

    def start_evolution_heartbeat(self):
        """Triggers the autonomous evolution script every 5 minutes."""
        def evolve_loop():
            from _orunex_libs import orunex_evolve
            while True:
                time.sleep(300) # Every 5 minutes
                try:
                    res = orunex_evolve.evolve()
                    if res:
                        self.after(0, lambda m=res: self._update_log_pill(m))
                except Exception:
                    pass
        import threading
        threading.Thread(target=evolve_loop, daemon=True).start()

    def _update_log_pill(self, msg):
        """Backward-compatible status hook used by background services."""
        self.after(0, lambda: self._set_activity(str(msg), "info"))

    # ── Screen Glow Overlay (continuous blue aura) ────────────────────────────
    def start_screen_glow(self):
        """Start the rounded, alpha-blended animated border.

        The old implementation used four rectangular Tk strips.  This now uses
        a single Win32 layered window with per-pixel alpha, so corners are
        genuinely rounded and the blue tones can flow without seams.
        """
        if getattr(self, "_glow_active", False):
            return
        if not self.config.get("screen_glow", True):
            return
        try:
            from _orunex_libs.screen_glow import ScreenGlowOverlay

            # Glow over the usable desktop area, not under the taskbar.  A
            # full-monitor topmost layered window makes Windows hide the
            # taskbar for the whole duration of a task.
            try:
                import ctypes
                from ctypes import wintypes

                work = wintypes.RECT()
                if not ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(work), 0
                ):
                    raise OSError("SPI_GETWORKAREA failed")
                glow_width = max(320, work.right - work.left)
                glow_height = max(240, work.bottom - work.top)
            except Exception:
                glow_width = self.winfo_screenwidth()
                glow_height = self.winfo_screenheight()

            overlay = getattr(self, "_screen_glow", None)
            if (
                overlay is None
                or overlay.width != glow_width
                or overlay.height != glow_height
            ):
                if overlay is not None:
                    overlay.stop(wait=True)
                overlay = ScreenGlowOverlay(glow_width, glow_height, fps=24)
                self._screen_glow = overlay
            overlay.start()
            self._glow_active = bool(overlay.active)
            if not self._glow_active and overlay.last_error():
                print(f"[WARN] Screen glow: {overlay.last_error()}")
        except Exception as exc:
            self._glow_active = False
            print(f"[WARN] Screen glow unavailable: {exc}")

    def stop_screen_glow(self, wait=False):
        """Fade out the border and release its layered window."""
        self._glow_active = False
        overlay = getattr(self, "_screen_glow", None)
        if overlay is None:
            return
        try:
            overlay.stop(wait=wait)
        except Exception:
            pass

    def _stop_task_glow(self, wait=False):
        """The blue contour belongs to Live mode, not to individual tasks."""
        if getattr(self, "_live_vision_active", False):
            return
        self.stop_screen_glow(wait=wait)

    def _on_close(self):
        """Stop animated resources before Tk tears down its interpreter."""
        if getattr(self, "_shutting_down", False):
            return
        self._shutting_down = True
        for attr in (
            "_composer_glow_job",
            "_vscode_after_id",
            "_thinking_after_id",
            "_glow_timer_id",
        ):
            job = getattr(self, attr, None)
            if job is None:
                continue
            try:
                self.after_cancel(job)
            except Exception:
                pass
            setattr(self, attr, None)
        try:
            self.stop_screen_glow(wait=True)
        except Exception:
            pass
        try:
            session = getattr(self, "_live_vision_session", None)
            if session is not None:
                session.stop(wait=False)
        except Exception:
            pass
        try:
            audio = getattr(self, "_live_audio_session", None)
            if audio is not None:
                audio.stop(wait=False)
        except Exception:
            pass
        try:
            speaker = getattr(self, "_live_speaker", None)
            if speaker is not None:
                speaker.stop()
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass



    def start_maintenance_loop(self):
        """Periodic system cleanup."""
        try:
            from _orunex_libs.maintenance import rotate_logs # type: ignore
            rotate_logs()
        except: pass
        self.after(3600000, self.start_maintenance_loop) # Every hour

    # Se removieron init_background, draw_geometric_background, y animate_background para maximo rendimiento.
        
    def create_ui(self):
        """Build the light desktop shell once, before background services start."""
        self.main_frame = ctk.CTkFrame(self, fg_color=THEME["bg"], corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)

        # Gemini-style collapsible navigation rail on the left.
        self._build_sidebar()

        self.content_area = ctk.CTkFrame(
            self.main_frame, fg_color=THEME["bg"], corner_radius=0
        )
        self.content_area.pack(side="left", fill="both", expand=True)

        self._build_header()

        # Single in-window content host. Chat, Simplex Bridge and Settings are
        # pages of this host; navigation never opens a second application
        # window.
        self.view_host = ctk.CTkFrame(
            self.content_area, fg_color=THEME["bg"], corner_radius=0
        )
        self.view_host.pack(fill="both", expand=True)

        self.workspace_view = ctk.CTkFrame(
            self.view_host, fg_color=THEME["bg"], corner_radius=0
        )
        self._build_composer(self.workspace_view)
        self._build_workspace(self.workspace_view)

        self._active_view = "workspace"
        self._set_view_title("workspace")
        self.workspace_view.pack(fill="both", expand=True)
        self._style_nav_buttons()
        # Restore the saved conversation only after the splash releases the
        # window.  Building it while the window is withdrawn leaves the
        # scrollable chat content unmapped on Windows, producing an empty
        # conversation card even though messages are loaded.

    def _build_header(self):
        """Slim top bar for the content area. Navigation lives in the sidebar."""
        header = ctk.CTkFrame(
            self.content_area,
            fg_color=THEME["bg"],
            height=62,
            corner_radius=0,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", padx=(26, 0), pady=14)

        self.view_title_lbl = ctk.CTkLabel(
            title_block,
            text="Chat",
            font=("Segoe UI", 16, "bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        self.view_title_lbl.pack(side="left")

        # The upper-right corner intentionally contains only this attribution.
        powered = ctk.CTkFrame(header, fg_color="transparent")
        powered.pack(side="right", padx=(0, 24), pady=18)
        ctk.CTkLabel(
            powered,
            text="Powered by ",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
        ).pack(side="left")
        ctk.CTkLabel(
            powered,
            text="Meta",
            font=("Segoe UI", 11, "bold"),
            text_color=THEME["blue"],
        ).pack(side="left")

        ctk.CTkFrame(
            self.content_area, height=1, fg_color=THEME["border"]
        ).pack(fill="x")

    def _style_nav_buttons(self):
        if not hasattr(self, "nav_buttons"):
            return
        active_nav = "settings" if self._active_view == "memory" else self._active_view
        for name, button in self.nav_buttons.items():
            try:
                if active_nav == name:
                    button.configure(
                        fg_color=THEME["blue_soft"],
                        text_color=THEME["blue"],
                    )
                else:
                    button.configure(
                        fg_color="transparent",
                        text_color=THEME["text_dim"],
                    )
            except Exception:
                pass

    def _build_sidebar(self):
        """Gemini-style navigation rail with a compact collapsed mode."""
        self.sidebar = ctk.CTkFrame(
            self.main_frame,
            width=self._sidebar_width,
            fg_color=THEME["surface"],
            corner_radius=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(14, 10))

        self.sidebar_toggle_btn = ctk.CTkButton(
            top,
            text="☰",
            width=36,
            height=36,
            corner_radius=9,
            fg_color="transparent",
            hover_color=THEME["surface_muted"],
            text_color=THEME["text_dim"],
            font=("Segoe UI Symbol", 16),
            command=self._toggle_sidebar,
        )
        self.sidebar_toggle_btn.pack(side="left")

        self.sidebar_brand = ctk.CTkFrame(top, fg_color="transparent")
        self.sidebar_brand.pack(side="left", padx=(8, 0), fill="x", expand=True)

        wordmark_path = os.path.join(BASE_DIR, "assets", "orunex-wordmark.png")
        if os.path.exists(wordmark_path):
            try:
                wordmark = Image.open(wordmark_path).convert("RGBA")
                self._logo_image = ctk.CTkImage(
                    light_image=wordmark, dark_image=wordmark, size=(96, 23)
                )
                self.sidebar_logo_lbl = ctk.CTkLabel(
                    self.sidebar_brand, image=self._logo_image, text=""
                )
            except Exception:
                self.sidebar_logo_lbl = ctk.CTkLabel(
                    self.sidebar_brand,
                    text="Orunex",
                    font=("Segoe UI", 16, "bold"),
                    text_color=THEME["text"],
                )
        else:
            self.sidebar_logo_lbl = ctk.CTkLabel(
                self.sidebar_brand,
                text="Orunex",
                font=("Segoe UI", 16, "bold"),
                text_color=THEME["text"],
            )
        self.sidebar_logo_lbl.pack(side="left")

        self.new_chat_btn = ctk.CTkButton(
            self.sidebar,
            text="＋   New chat",
            anchor="w",
            height=40,
            corner_radius=10,
            fg_color=THEME["blue_soft"],
            hover_color=THEME["blue_border"],
            text_color=THEME["blue"],
            font=("Segoe UI", 12, "bold"),
            command=self.new_chat,
        )
        self.new_chat_btn.pack(fill="x", padx=12, pady=(4, 12))

        # Menu and Simplex status form a footer so they stay visible even on
        # short screens. The chat list takes the flexible middle of the rail.
        self.sidebar_footer = ctk.CTkFrame(
            self.sidebar, fg_color="transparent"
        )
        self.sidebar_footer.pack(side="bottom", fill="x")

        ctk.CTkFrame(
            self.sidebar_footer, height=1, fg_color=THEME["border"]
        ).pack(fill="x", padx=12, pady=(6, 6))

        self.sidebar_nav_label = ctk.CTkLabel(
            self.sidebar_footer,
            text="Menu",
            font=("Segoe UI", 10, "bold"),
            text_color=THEME["muted"],
            anchor="w",
        )
        self.sidebar_nav_label.pack(fill="x", padx=24, pady=(2, 2), anchor="w")

        self.sidebar_nav = ctk.CTkFrame(
            self.sidebar_footer, fg_color="transparent"
        )
        self.sidebar_nav.pack(fill="x", padx=8)

        def nav_button(icon, label, command):
            button = ctk.CTkButton(
                self.sidebar_nav,
                text=f"{icon}   {label}",
                anchor="w",
                height=40,
                corner_radius=10,
                fg_color="transparent",
                hover_color=THEME["surface_muted"],
                text_color=THEME["text_dim"],
                font=("Segoe UI", 12),
                command=command,
            )
            button.pack(fill="x", pady=2)
            return button

        self.workspace_nav_btn = nav_button(
            "✦", "Chat", lambda: self.show_view("workspace")
        )
        self.simplex_btn = nav_button(
            "⇄", "Simplex Bridge", lambda: self.show_view("simplex")
        )
        self.settings_nav_btn = nav_button(
            "⚙", "Settings", lambda: self.show_view("settings")
        )
        self.nav_buttons = {
            "workspace": self.workspace_nav_btn,
            "simplex": self.simplex_btn,
            "settings": self.settings_nav_btn,
        }
        self._nav_meta = {
            "workspace": ("✦", "Chat"),
            "simplex": ("⇄", "Simplex Bridge"),
            "settings": ("⚙", "Settings"),
        }

        self.sidebar_status = ctk.CTkButton(
            self.sidebar_footer,
            text="○  Simplex offline",
            anchor="w",
            height=38,
            corner_radius=10,
            fg_color="transparent",
            hover_color=THEME["surface_muted"],
            text_color=THEME["text_dim"],
            font=("Segoe UI", 11),
            command=lambda: self.show_view("simplex"),
        )
        self.sidebar_status.pack(fill="x", padx=12, pady=(0, 12))

        # Saved chats are the primary content of the rail, like Gemini.
        self.sidebar_body = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_body.pack(fill="both", expand=True)

        self.chats_label = ctk.CTkLabel(
            self.sidebar_body,
            text="Chats",
            font=("Segoe UI", 10, "bold"),
            text_color=THEME["muted"],
            anchor="w",
        )
        self.chats_label.pack(fill="x", padx=18, pady=(2, 4), anchor="w")

        self.chats_scroll = ctk.CTkScrollableFrame(
            self.sidebar_body,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        self.chats_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._refresh_chat_list()

    def _toggle_sidebar(self):
        """Collapse or expand the navigation rail without recreating widgets."""
        self._sidebar_expanded = not self._sidebar_expanded
        expanded = self._sidebar_expanded

        try:
            self.sidebar.configure(
                width=self._sidebar_width if expanded else self._sidebar_collapsed_width
            )
        except Exception:
            pass

        if expanded:
            self.sidebar_brand.pack(side="left", padx=(8, 0), fill="x", expand=True)
            self.chats_label.pack(fill="x", padx=18, pady=(2, 4), anchor="w")
            self.chats_scroll.pack(
                fill="both", expand=True, padx=6, pady=(0, 4)
            )
            self.sidebar_nav_label.pack(
                fill="x", padx=24, pady=(2, 2), anchor="w",
                before=self.sidebar_nav,
            )
        else:
            self.sidebar_brand.pack_forget()
            self.chats_label.pack_forget()
            self.chats_scroll.pack_forget()
            self.sidebar_nav_label.pack_forget()

        for name, button in getattr(self, "nav_buttons", {}).items():
            icon, label = self._nav_meta.get(name, ("•", name))
            try:
                button.configure(
                    text=f"{icon}   {label}" if expanded else icon,
                    anchor="w" if expanded else "center",
                    font=("Segoe UI", 12)
                    if expanded
                    else ("Segoe UI Symbol", 16),
                )
            except Exception:
                pass

        try:
            self.new_chat_btn.configure(
                text="＋   New chat" if expanded else "＋",
                anchor="w" if expanded else "center",
                font=("Segoe UI", 12, "bold")
                if expanded
                else ("Segoe UI Symbol", 18),
            )
        except Exception:
            pass

        self._update_sidebar_status(
            getattr(self, "_simplex_connected", False),
            getattr(self, "_simplex_paired", False),
        )

    def _set_view_title(self, name):
        titles = {
            "workspace": "Chat",
            "simplex": "Simplex Bridge",
            "settings": "Settings",
            "memory": "Saved memory",
        }
        try:
            self.view_title_lbl.configure(text=titles.get(name, "Chat"))
        except Exception:
            pass

    def _update_sidebar_status(self, connected, paired, contact=""):
        if not hasattr(self, "sidebar_status"):
            return
        if paired:
            label = "Simplex · Paired"
            tone = THEME["blue"]
        elif connected:
            label = "Simplex · Online"
            tone = THEME["blue"]
        else:
            label = "Simplex offline"
            tone = THEME["text_dim"]
        text = f"●  {label}" if self._sidebar_expanded else "●"
        try:
            self.sidebar_status.configure(text=text, text_color=tone)
        except Exception:
            pass

    def show_view(self, name):
        """Switch between in-window pages without creating another window."""
        if name not in ("workspace", "simplex", "settings", "memory"):
            return

        if name == "simplex" and self._simplex_view is None:
            self._build_simplex_view()
        if name == "settings" and self._settings_view is None:
            self._build_settings_view()
        if name == "memory" and self._memory_view is None:
            self._build_memory_view()

        for page in (
            self.workspace_view,
            self._simplex_view,
            self._settings_view,
            self._memory_view,
        ):
            if page is not None:
                try:
                    if page.winfo_exists():
                        page.pack_forget()
                except Exception:
                    pass

        target = {
            "workspace": self.workspace_view,
            "simplex": self._simplex_view,
            "settings": self._settings_view,
            "memory": self._memory_view,
        }.get(name)
        if target is None:
            return
        target.pack(fill="both", expand=True)
        self._active_view = name
        self._set_view_title(name)
        self._style_nav_buttons()

        if name == "simplex":
            self._refresh_simplex_page()
        elif name == "settings":
            self._sync_settings_widgets()
        elif name == "memory":
            refresh = getattr(self, "_refresh_memory_page", None)
            if callable(refresh):
                refresh()

    def _build_composer(self, parent=None):
        parent = parent or self.main_frame
        self.composer_wrap = ctk.CTkFrame(
            parent, fg_color=THEME["bg"]
        )
        self.composer_wrap.pack(
            side="bottom", fill="x", padx=24, pady=(4, 10)
        )

        # Aceternity / Magic UI inspired composer edge: a moving mesh-gradient
        # stroke with a soft outer glow. It is rendered natively with Pillow so
        # it can live inside the CustomTkinter window without a web view.
        try:
            ui_scale = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        except Exception:
            ui_scale = 1.0
        # The canvas has extra breathing room so the animated halo can fade
        # completely before it reaches the canvas edge. The composer itself is
        # slightly inset, leaving a crisp gradient rim around the white pill.
        self._composer_canvas_height = int(130 * ui_scale)
        self._composer_relwidth = 0.976
        self._composer_relheight = 0.70
        # Radius and rim are stored in physical canvas pixels. CTk scales the
        # corner radius passed to CTkFrame, so convert it back to its logical
        # value below; otherwise the white pill cuts into the gradient ring.
        self._composer_radius = max(18, int(24 * ui_scale))
        self._composer_rim = max(3, int(5 * ui_scale))
        # The white pill is painted into the gradient image. The control
        # frame must sit fully inside that pill; otherwise its opaque square
        # canvas covers the gradient at the rounded corners.
        self._composer_control_inset = max(
            12, int(self._composer_radius * 0.62)
        )
        self.composer_canvas = tk.Canvas(
            self.composer_wrap,
            height=self._composer_canvas_height,
            bg=THEME["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.composer_canvas.pack(fill="x")
        self.composer_canvas.bind(
            "<Configure>", self._on_composer_canvas_configure
        )

        # This is only the control container. It is deliberately inset from
        # the painted pill so its rectangular corners never reach the rim.
        self.composer = ctk.CTkFrame(
            self.composer_canvas,
            bg_color=THEME["surface"],
            fg_color=THEME["surface"],
            corner_radius=0,
            border_width=0,
        )
        self.composer.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            relwidth=self._composer_relwidth,
            relheight=self._composer_relheight,
        )
        self.composer.pack_propagate(False)

        self.attach_btn = ctk.CTkButton(
            self.composer,
            text="Attach",
            bg_color=THEME["surface"],
            width=64,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=0,
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 11),
            command=self.load_image,
        )
        self.attach_btn.pack(side="left", padx=(8, 2), pady=12)

        # Chat modes are hints, not gates. "Default" lets the local router pick
        # the most useful mode for the request, while an explicit mode keeps the
        # user's preference for that message.
        self.mode_option = ctk.CTkOptionMenu(
            self.composer,
            values=[
                mode_router.MODE_LABELS[mode]
                for mode in (
                    mode_router.MODE_DEFAULT,
                    mode_router.MODE_PROGRAMMER,
                    mode_router.MODE_RESEARCH,
                    mode_router.MODE_SWAPPING,
                )
            ],
            command=self._on_mode_selected,
            width=128,
            height=34,
            corner_radius=8,
            bg_color=THEME["surface"],
            fg_color=THEME["surface_soft"],
            button_color=THEME["surface_soft"],
            button_hover_color=THEME["surface_muted"],
            dropdown_fg_color=THEME["surface"],
            dropdown_hover_color=THEME["blue_soft"],
            dropdown_text_color=THEME["text"],
            text_color=THEME["text_dim"],
            font=("Segoe UI", 10),
            dropdown_font=("Segoe UI", 10),
        )
        self.mode_option.set(mode_router.MODE_LABELS[mode_router.MODE_DEFAULT])
        self.mode_option.pack(side="left", padx=(0, 4), pady=12)

        self.input_entry = ctk.CTkEntry(
            self.composer,
            bg_color=THEME["surface"],
            placeholder_text="Ask Orunex or describe a task...",
            placeholder_text_color=THEME["muted"],
            height=38,
            corner_radius=8,
            font=("Segoe UI", 13),
            border_width=0,
            fg_color=THEME["surface"],
            text_color=THEME["text"],
        )
        self.input_entry.pack(
            side="left", fill="both", expand=True, padx=(2, 2), pady=10
        )
        self.input_entry.bind("<Return>", self.on_enter)
        self.input_entry.bind("<FocusIn>", self._on_composer_focus_in)
        self.input_entry.bind("<FocusOut>", self._on_composer_focus_out)

        # Retained for the existing execution pipeline, with no extra control
        # rendered in the simplified composer.
        self.swarm_var = ctk.StringVar(value="Swarm 1")

        self.pause_btn = ctk.CTkButton(
            self.composer,
            text="Pause",
            bg_color=THEME["surface"],
            width=66,
            height=34,
            corner_radius=8,
            fg_color=THEME["surface_soft"],
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 11),
            command=self.toggle_pause,
        )
        # Hidden until an execution starts.

        self.send_bot_btn = ctk.CTkButton(
            self.composer,
            text="Send",
            bg_color=THEME["surface"],
            width=84,
            height=38,
            corner_radius=10,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color=THEME["accent_hover"],
            font=("Segoe UI", 12, "bold"),
            command=self.send_task,
        )
        self.send_bot_btn.pack(side="right", padx=(6, 9), pady=10)

        # Live Vision: concentric-circle toggle inspired by Gemini Live.
        # It arms screen observation now and leaves the Meta AI brain
        # attachable through LiveVisionSession.set_analyzer().
        self.live_vision_btn = LiveVisionButton(
            self.composer,
            command=self.toggle_live_vision,
            size=40,
            bg=THEME["surface"],
            active_color=THEME["blue"],
            idle_color=THEME["muted"],
            halo_color=THEME["blue_border"],
        )
        self.live_vision_btn.pack(side="right", padx=(2, 0), pady=9)

        self._composer_glow_job = None
        self._layout_composer_controls()
        self._render_composer_glow()
        self._composer_glow_job = self.after(60, self._animate_composer_glow)

    def _layout_composer_controls(self):
        """Keep the control frame entirely inside the painted white pill."""
        try:
            canvas_w = self.composer_canvas.winfo_width()
            canvas_h = self.composer_canvas.winfo_height()
            if canvas_w < 80 or canvas_h < 40:
                return
            pill_w = max(220, int(canvas_w * self._composer_relwidth))
            pill_h = max(48, int(canvas_h * self._composer_relheight))
            inset = self._composer_control_inset
            control_w = max(180, pill_w - 2 * inset)
            control_h = max(60, pill_h - 2 * inset)
            self.composer.place(
                relx=0.5,
                rely=0.5,
                anchor="center",
                relwidth=control_w / canvas_w,
                relheight=control_h / canvas_h,
            )
        except Exception:
            pass

    def _on_mode_selected(self, value):
        """Store the dropdown choice; Default remains automatic."""
        label = str(value or "").strip()
        selected = mode_router.MODE_DEFAULT
        for mode, mode_label in mode_router.MODE_LABELS.items():
            if label.lower() == mode_label.lower() or label.lower() == mode.lower():
                selected = mode
                break
        self.current_mode = selected
        if not self.is_processing:
            hint = (
                "Auto-selects the best mode for each task."
                if selected == mode_router.MODE_DEFAULT
                else f"{selected} is a preference hint; every task still runs."
            )
            self._show_activity_line(f"{mode_router.MODE_LABELS[selected]} — {hint}", "info")

    def _on_composer_focus_in(self, event=None):
        self._composer_focused = True

    def _on_composer_focus_out(self, event=None):
        self._composer_focused = False

    def _on_composer_canvas_configure(self, event=None):
        self._composer_glow_masks = None
        self._layout_composer_controls()
        self._render_composer_glow()

    # ── Live Vision (screen-only, brain-ready) ───────────────────────────────
    def _ensure_live_vision_session(self):
        """Create the local observation loop once, without a brain attached."""
        if self._live_vision_session is None:
            self._live_vision_session = LiveVisionSession(
                on_event=self._on_live_vision_event,
                on_status=self._on_live_vision_status,
                interval=1.5,
                monitor=1,
                skip_own_window=True,
            )
        return self._live_vision_session

    def _live_vision_brain_note(self):
        """Human-readable state of the future Meta AI connection."""
        try:
            provider = MetaVisionProvider()
            if provider.can_analyze:
                return "Meta AI is connected."
            if provider.configured:
                return "Meta AI endpoint is configured; transport is pending."
        except Exception:
            pass
        return "Meta AI is not connected yet; observing locally."

    def toggle_live_vision(self):
        """Toggle the concentric Live Vision control exactly once per click."""
        now = time.monotonic()
        if now - getattr(self, "_last_live_toggle", 0.0) < 0.32:
            return
        self._last_live_toggle = now

        # Trust the session as a fallback if the UI flag ever got out of sync.
        session = getattr(self, "_live_vision_session", None)
        actually_active = bool(
            self._live_vision_active
            or (session is not None and getattr(session, "active", False))
        )
        if actually_active:
            self.stop_live_vision()
        else:
            self.start_live_vision()

    def start_live_vision(self):
        """Start the combined Live mode: screen observation plus microphone."""
        if self._live_vision_active:
            return
        session = self._ensure_live_vision_session()
        self._live_vision_active = True
        try:
            self.live_vision_btn.set_active(True)
        except Exception:
            pass
        # The capture loop only diffs frames locally.  Vision analysis runs
        # on demand when the user asks about the screen: attaching the model
        # to every frame change burned an API call on each video frame and
        # still never answered the actual question.
        session.start()
        self._start_live_audio()
        # Open the audio device before the first answer; pygame's first init
        # was adding a noticeable pause to every new Live session.
        try:
            speaker = self._ensure_live_speaker()
            speaker.prepare_async()
            # Pre-render the short replies Live gives constantly.  Later
            # plays are local file reads, so the answer starts instantly.
            speaker.warm(
                [
                    "Hola, ¿en qué te ayudo?",
                    "Te escucho. ¿En qué te ayudo?",
                    "Hi, how can I help?",
                    "De nada.",
                    "Abriendo YouTube en Chrome.",
                    "Abriendo YouTube en tu navegador.",
                    "Abriendo Google en Chrome.",
                    "Abriendo Chrome.",
                    "Opening YouTube in Chrome.",
                    "¿Qué quieres que abra? Dime el sitio o la aplicación.",
                ]
            )
        except Exception:
            pass
        self.start_screen_glow()
        self._schedule_live_audio_watch()
        if not self.is_processing:
            # The contour is the Live indicator.  Keep this line as a calm
            # state label instead of narrating every microphone event.
            self._show_activity_line("Live", "info")

    def _schedule_live_audio_watch(self):
        """Check occasionally that the microphone thread is still alive."""
        previous = getattr(self, "_live_audio_watch_after", None)
        if previous is not None:
            try:
                self.after_cancel(previous)
            except Exception:
                pass
        try:
            self._live_audio_watch_after = self.after(
                1800, self._watch_live_audio
            )
        except Exception:
            self._live_audio_watch_after = None

    def _watch_live_audio(self):
        self._live_audio_watch_after = None
        if getattr(self, "_shutting_down", False) or not self._live_vision_active:
            return
        audio = getattr(self, "_live_audio_session", None)
        if audio is None or not audio.active:
            self._start_live_audio()
        self._schedule_live_audio_watch()

    def stop_live_vision(self):
        """Disarm screen observation, microphone listening and queued voice."""
        was_active = bool(getattr(self, "_live_vision_active", False))
        self._live_vision_active = False
        self._live_transcript_queue.clear()
        previous = getattr(self, "_live_audio_watch_after", None)
        if previous is not None:
            try:
                self.after_cancel(previous)
            except Exception:
                pass
            self._live_audio_watch_after = None
        try:
            self.live_vision_btn.set_active(False)
        except Exception:
            pass
        # Signal the overlay first.  Its animation thread hides the layered
        # window on the next frame, so the contour goes away without waiting
        # for voice or microphone teardown.
        try:
            self.stop_screen_glow(wait=False)
        except Exception:
            pass
        # Invalidate and silence the neural voice before any cleanup that could
        # block.  The speaker worker is allowed to finish tearing down in the
        # background so Tk can repaint the chat and hide the contour at once.
        speaker = getattr(self, "_live_speaker", None)
        if speaker is not None:
            try:
                speaker.stop(wait=False)
            except Exception:
                pass
        audio = getattr(self, "_live_audio_session", None)
        if audio is not None:
            try:
                audio.stop()
            except Exception:
                pass
        session = getattr(self, "_live_vision_session", None)
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass
        if was_active and not self.is_processing and not getattr(
            self, "_shutting_down", False
        ):
            try:
                self._show_activity_line("At your service", "info")
            except Exception:
                pass
        if was_active and os.environ.get("ORUNEX_LIVE_DEBUG", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            print("[LIVE] stopped; microphone and speech halted, contour off")

    def _start_live_audio(self):
        """Start microphone capture for the Live button, if voice is enabled."""
        if not self.config.get("voice_enabled", True):
            return
        try:
            from _orunex_libs.live_audio import LiveAudioSession

            audio = getattr(self, "_live_audio_session", None)
            if audio is None:
                audio = LiveAudioSession(
                    on_transcript=self._on_live_transcript,
                    on_status=self._on_live_audio_status,
                )
                self._live_audio_session = audio
            if not audio.active:
                audio.start()
        except Exception as exc:
            self._show_activity_line(
                f"Live microphone unavailable: {exc}", "error"
            )

    def _ensure_live_speaker(self):
        speaker = getattr(self, "_live_speaker", None)
        if speaker is None:
            from _orunex_libs.live_tts import LiveSpeaker

            speaker = LiveSpeaker(on_status=self._on_live_speaker_status)
            self._live_speaker = speaker
        return speaker

    def _speak_live_response(self, text):
        """Speak one completed response while Live is active."""
        if not self._live_vision_active or not self.config.get(
            "voice_enabled", True
        ):
            return False
        if getattr(self, "_shutting_down", False):
            return False
        try:
            speaker = self._ensure_live_speaker()
            audio = getattr(self, "_live_audio_session", None)
            if audio is not None:
                audio.suspend()

            def done():
                if not self._live_vision_active:
                    return

                def resume_microphone():
                    if not self._live_vision_active:
                        return
                    # A newer answer may already be speaking.  In that case
                    # its own done callback will re-arm the microphone.
                    try:
                        if speaker.speaking:
                            return
                    except Exception:
                        pass
                    if audio is not None:
                        audio.resume()

                # Room echo and the last SDL buffer can outlive get_busy().
                # Keep the mic muted briefly so the assistant never hears its
                # own voice and turns it into a new task.  This is intentionally
                # short: a long guard was another source of perceived lag.
                try:
                    self.after(300, resume_microphone)
                except Exception:
                    resume_microphone()

            started = speaker.speak(text, on_done=done)
            if started:
                return True
            if audio is not None:
                audio.resume()
            return False
        except Exception as exc:
            audio = getattr(self, "_live_audio_session", None)
            if audio is not None:
                audio.resume()
            self._show_activity_line(f"Voice output unavailable: {exc}", "error")
            return False

    def _on_live_speaker_status(self, message, level="info"):
        if getattr(self, "_shutting_down", False):
            return
        try:
            self.after(
                0,
                lambda m=message, l=level: self._apply_live_audio_status(m, l),
            )
        except Exception:
            pass

    def _on_live_audio_status(self, message, level="info"):
        """Marshal microphone status messages back onto the Tk thread."""
        if getattr(self, "_shutting_down", False):
            return
        try:
            self.after(
                0,
                lambda m=message, l=level: self._apply_live_audio_status(m, l),
            )
        except Exception:
            pass

    def _apply_live_audio_status(self, message, level="info"):
        if getattr(self, "_shutting_down", False):
            return
        # Live must feel like a conversation, not a terminal.  Hearing,
        # transcribing, no-speech and listening updates stay out of the UI.
        # Only actionable failures (no microphone, bad key, ASR down) surface.
        if level in ("error", "warning", "warn"):
            self._show_activity_line(message, "error" if level == "error" else level)

    def _on_live_transcript(self, text):
        """Receive a microphone transcript from the audio worker thread."""
        text = " ".join(str(text or "").split()).strip()
        if not text or getattr(self, "_shutting_down", False):
            return
        try:
            self.after(0, lambda t=text: self._queue_live_transcript(t))
        except Exception:
            pass

    def _strip_live_wake_word(self, text):
        """Remove a leading spoken wake word before routing a transcript."""
        import re

        value = str(text or "").strip()
        return re.sub(
            r"(?i)^\s*(?:(?:oye|hey|hola)\s*,?\s*)?orunex\b[\s,.:;!?\-]*",
            "",
            value,
        ).strip()

    _LIVE_GREETINGS = {
        "hola": "Hola, ¿en qué te ayudo?",
        "hello": "Hi, how can I help?",
        "hey": "Hi, how can I help?",
        "buenas": "Hola, ¿en qué te ayudo?",
        "buenos dias": "Buenos días. ¿En qué te ayudo?",
        "buenas tardes": "Buenas tardes. ¿En qué te ayudo?",
        "buenas noches": "Buenas noches. ¿En qué te ayudo?",
        "que tal": "Muy bien. ¿En qué te ayudo?",
        "como estas": "Muy bien, gracias. ¿En qué te ayudo?",
        "how are you": "I'm doing well. How can I help?",
        "gracias": "De nada.",
        "muchas gracias": "De nada.",
        "thank you": "You're welcome.",
        "thanks": "You're welcome.",
    }

    def _live_greeting_response(self, text):
        """Instant local reply for greetings and wake-only turns.

        These must never wait for a model round-trip: in Live mode a simple
        "Hola" expects an immediate "Hola, ¿en qué te ayudo?" back, the same
        way Gemini Live answers.  Returns ``None`` for real requests.
        """
        import re
        import unicodedata

        value = str(text or "").strip()
        if not value:
            return None
        folded = unicodedata.normalize("NFKD", value)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = folded.lower()
        folded = re.sub(
            r"^\s*(?:(?:oye|hey|hola)\s*,?\s*)?orunex\b[\s,.:;!?-]*",
            "",
            folded,
        )
        folded = re.sub(r"[^\w\s]", " ", folded)
        folded = re.sub(r"\s+", " ", folded).strip()
        if not folded:
            # Wake word on its own: "Orunex" / "Hola Orunex".
            return "Te escucho. ¿En qué te ayudo?"
        return self._LIVE_GREETINGS.get(folded)

    def _is_screen_question(self, text):
        """True for "¿qué ves en mi pantalla?" style questions, ES or EN.

        These are read-only questions about the screen.  They must go to the
        vision path, never to the OS agent: sending one to Cerebro made it
        hallucinate executor tags such as a fake project folder and a bogus
        URL, which the executor then tried to open in Chrome.
        """
        import re
        import unicodedata

        folded = unicodedata.normalize("NFKD", str(text or ""))
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = re.sub(r"\s+", " ", folded.lower()).strip()
        if not folded:
            return False
        patterns = (
            r"\bque ves\b",
            r"\bque se ve\b",
            r"\bque hay en (mi|la|esta|tu) pantalla\b",
            r"\bdescribe(me)? (la|mi|esta|tu)? ?pantalla\b",
            r"\bmira (mi|la|esta) pantalla\b",
            r"\bwhat (do|can) you see\b",
            r"\bwhat'?s on (my|the|your) screen\b",
            r"\bwhat is on (my|the|your) screen\b",
            r"\bdescribe (my|the) screen\b",
            r"\blook at my screen\b",
            r"\bsee (on|in) my (screen|browser)\b",
        )
        return any(re.search(p, folded) for p in patterns)

    def _capture_screen_frame(self):
        """Fresh full-screen capture for an on-demand vision answer."""
        try:
            import mss
            from PIL import Image

            from _orunex_libs.live_vision import LiveVisionFrame

            with mss.mss() as sct:
                if len(sct.monitors) <= 1:
                    return None
                shot = sct.grab(sct.monitors[1])
                image = Image.frombytes(
                    "RGB", shot.size, shot.bgra, "raw", "BGRX"
                )
            # A downscaled frame uploads and analyzes much faster, and the
            # model still reads titles and dialogs at this size.
            if image.width > 1280:
                height = int(image.height * 1280 / image.width)
                image = image.resize((1280, height))
            return LiveVisionFrame(
                image=image, captured_at=time.time(), monitor=1
            )
        except Exception as exc:
            print(f"[VISION] screen capture failed: {exc}")
            return None

    def _describe_screen(self, task):
        """Answer a screen question from a fresh capture. Never raises.

        Technical details go to the console only; the chat and the voice
        always get a short, human answer.
        """
        spanish = not re.search(
            r"\b(what|screen|see|look|describe)\b", str(task or ""), re.I
        )
        unavailable = (
            "Ahora mismo no puedo ver tu pantalla. Inténtalo de nuevo en unos segundos."
            if spanish
            else "I can't see your screen right now. Try again in a few seconds."
        )
        try:
            from _orunex_libs.live_vision import MetaVisionProvider

            provider = MetaVisionProvider()
            if not provider.can_analyze:
                print("[VISION] screen question: provider not configured")
                return unavailable
            provider.timeout = 30.0
            frame = self._capture_screen_frame()
            if frame is None:
                return unavailable
            if spanish:
                prompt = (
                    "Describe en español, en 2 o 3 frases cortas y sin listas, "
                    "qué se ve en esta captura de pantalla: la aplicación o "
                    "sitio principal, el contenido visible (títulos, videos, "
                    "textos) y cualquier ventana de error. Si se ve la "
                    "ventana de Orunex, ignórala y describe el resto de la "
                    "pantalla. No inventes nada que no sea visible."
                )
            else:
                prompt = (
                    "Describe in English, in 2 or 3 short sentences with no "
                    "lists, what is visible in this screenshot: the main app "
                    "or site, the visible content (titles, videos, text) and "
                    "any error dialog. If the Orunex window is visible, "
                    "ignore it and describe the rest of the screen. Do not "
                    "invent anything that is not visible."
                )
            started = time.monotonic()
            answer = str(provider.analyze(frame, prompt) or "").strip()
            print(
                f"[VISION] screen answered in {time.monotonic() - started:.1f}s "
                f"chars={len(answer)}"
            )
            answer = re.sub(r"\s+", " ", answer).strip()
            if not answer:
                return unavailable
            if len(answer) > 500:
                cut = answer[:500]
                end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
                answer = cut[: end + 1] if end >= 200 else cut.rstrip() + "…"
            return answer
        except Exception as exc:
            print(f"[VISION] screen question failed: {exc}")
            return unavailable

    def _voice_transcript_is_actionable(self, text):
        """Reject media/background chatter before it reaches the agent.

        Always-listening mode inevitably hears a video, a call, or the tail of
        Orunex's own voice.  Running every one of those strings through the OS
        agent caused ghost clicks such as the old \"Profile-Handler\" Chrome
        automation.  Direct desktop commands work without a wake word; a
        free-form question or task must include \"Orunex\" so a film or a
        YouTube video cannot silently take over the desktop.
        """
        import re
        import unicodedata

        value = str(text or "").strip()
        if not value:
            return False
        stripped = self._strip_live_wake_word(value)
        if not stripped:
            # Wake word on its own ("Orunex", "Hola Orunex") is the user
            # calling the assistant: answer immediately, do not stay silent.
            return bool(re.search(r"\borunex\b", value, re.IGNORECASE))

        folded = unicodedata.normalize("NFKD", stripped)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = re.sub(r"\s+", " ", folded.lower()).strip()
        folded = re.sub(r"[^\w\s]", " ", folded)
        folded = re.sub(r"\s+", " ", folded).strip()
        if not folded:
            return False

        try:
            from _orunex_libs.intent_router import parse_command

            context = getattr(self, "_command_context", {})
            if parse_command(stripped, context) or parse_command(value, context):
                return True
        except Exception:
            pass

        # A greeting is a conversation opener, not a task.  Answering "Hola"
        # instantly is what makes Live feel alive; it can never launch or
        # automate anything, so the ghost-action risk stays zero.
        if folded in self._LIVE_GREETINGS:
            return True

        # Screen questions are read-only and unmistakably addressed to the
        # assistant while Live is watching the screen.
        if self._is_screen_question(stripped) or self._is_screen_question(value):
            return True

        # Conversation window: once the user has addressed Orunex, follow-ups
        # for a short while do not need the wake word again (Gemini Live
        # behaves this way inside a session).  Outside the window, free-form
        # speech still needs "Orunex" so TV dialogue cannot become a task.
        if time.monotonic() < float(
            self.__dict__.get("_live_conversation_until", 0.0) or 0.0
        ):
            return True

        # Free-form speech needs an explicit wake word.  This is the important
        # barrier against TV dialogue and YouTube captions becoming tasks.
        if stripped == value and not re.search(r"\borunex\b", folded):
            return False
        return bool(folded)

    def _queue_live_transcript(self, text):
        if not self._live_vision_active or getattr(self, "_shutting_down", False):
            return
        if not self._voice_transcript_is_actionable(text):
            # Television, video, music lyrics and other voices disappear
            # silently.  They must not create a status line or a chat bubble.
            return
        text = self._strip_live_wake_word(text) or text
        recent = getattr(self, "_live_recent_transcripts", None)
        if recent is None:
            from collections import deque

            recent = deque(maxlen=4)
            self._live_recent_transcripts = recent
        now = time.monotonic()
        if recent and recent[-1][0] == text.lower() and now - recent[-1][1] < 1.2:
            return
        recent.append((text.lower(), now))
        # An accepted turn opens the short conversation window used above.
        self._live_conversation_until = now + 30.0
        self._live_transcript_queue.append(text)
        self._drain_live_transcripts()

    def _drain_live_transcripts(self):
        """Send one live utterance at a time, never interrupting a running task."""
        if getattr(self, "_shutting_down", False) or not self._live_vision_active:
            return
        if self.is_processing:
            self.after(200, self._drain_live_transcripts)
            return
        if not self._live_transcript_queue:
            return
        text = self._live_transcript_queue.pop(0)
        try:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, text)
            self.send_task()
        except Exception as exc:
            self._show_activity_line(f"Live voice error: {exc}", "error")
        if self._live_transcript_queue:
            self.after(200, self._drain_live_transcripts)

    def _on_live_vision_status(self, message, level="info"):
        """Receive worker-thread status without touching Tk off-thread."""
        if getattr(self, "_shutting_down", False):
            return
        try:
            self.after(
                0,
                lambda m=message, l=level: self._apply_live_vision_status(m, l),
            )
        except Exception:
            pass

    def _apply_live_vision_status(self, message, level="info"):
        if getattr(self, "_shutting_down", False):
            return
        if level == "error" and "unavailable" in str(message).lower():
            self._live_vision_active = False
            try:
                self.live_vision_btn.set_active(False)
            except Exception:
                pass
        if self.is_processing and level not in ("error", "warning", "warn"):
            return
        self._show_activity_line(message, level)

    def _on_live_vision_event(self, frame):
        """Keep the latest meaningful frame; a future brain consumes it here."""
        self._last_live_vision_frame = frame

    def connect_live_vision_brain(self, provider):
        """Attach a vision provider without changing the button or capture loop.

        ``provider.analyze(frame)`` must accept a LiveVisionFrame and return the
        result.  This is the single integration point for the future Meta AI
        adapter.
        """
        if provider is None:
            return False
        if hasattr(provider, "can_analyze") and not provider.can_analyze:
            return False
        session = self._ensure_live_vision_session()
        session.set_analyzer(
            provider.analyze,
            on_analysis=self._on_live_vision_analysis,
        )
        return True

    def _on_live_vision_analysis(self, result):
        """Future policy hook: notify, act, or stay silent."""
        # Intentionally left as the bridge for observe → notify → act once the
        # Meta AI transport is implemented.  Do not auto-execute model output
        # here without the confirmation layer.
        self._last_live_vision_analysis = result
        text = " ".join(str(result or "").split()).strip()
        if not text or getattr(self, "_shutting_down", False):
            return

        def notify():
            if getattr(self, "_shutting_down", False) or self.is_processing:
                return
            self._show_activity_line(f"Live vision: {text[:110]}", "info")

        try:
            self.after(0, notify)
        except Exception:
            pass

    def _window_is_active(self):
        """True while any Orunex window owns the foreground."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            foreground = user32.GetForegroundWindow()
            owner = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(
                foreground, ctypes.byref(owner)
            )
            return owner.value == os.getpid()
        except Exception:
            return True

    def _animate_composer_glow(self):
        if not hasattr(self, "composer_canvas"):
            return
        try:
            if not self.composer_canvas.winfo_exists():
                return
            if (
                self._active_view == "workspace"
                and self.composer_canvas.winfo_ismapped()
                and self._window_is_active()
            ):
                speed = 0.138 if self._composer_focused else 0.090
                self._composer_glow_phase += speed
                self._render_composer_glow()
        except Exception:
            pass
        self._composer_glow_job = self.after(60, self._animate_composer_glow)

    def _render_composer_glow(self):
        """Draw a fluid RGB rim and halo around the prompt composer.

        The gradient is a filled rounded pill under the white composer, not a
        rectangle behind it. The rim follows the real widget geometry and the
        canvas has enough padding for the halo to fade to the page colour.
        """
        try:
            if not hasattr(self, "composer_canvas"):
                return
            canvas_w = self.composer_canvas.winfo_width()
            canvas_h = self.composer_canvas.winfo_height()
            if canvas_w < 80:
                canvas_w = 720
            if canvas_h < 40:
                canvas_h = getattr(self, "_composer_canvas_height", 104)
            if canvas_w < 80 or canvas_h < 40:
                return

            rel_w = getattr(self, "_composer_relwidth", 0.972)
            rel_h = getattr(self, "_composer_relheight", 0.66)
            comp_w = max(220, int(canvas_w * rel_w))
            comp_h = max(48, int(canvas_h * rel_h))
            comp_x = (canvas_w - comp_w) // 2
            comp_y = (canvas_h - comp_h) // 2

            rim = getattr(self, "_composer_rim", 3)
            radius = getattr(self, "_composer_radius", 18)
            cache_key = (
                canvas_w, canvas_h, comp_x, comp_y, comp_w, comp_h,
                rim, radius, self._composer_focused,
            )
            masks = self._composer_glow_masks
            if masks is None or masks[0] != cache_key:
                scale = max(1.0, comp_h / 68.0)
                outer = Image.new("L", (canvas_w, canvas_h), 0)
                ImageDraw.Draw(outer).rounded_rectangle(
                    (
                        comp_x - rim,
                        comp_y - rim,
                        comp_x + comp_w + rim - 1,
                        comp_y + comp_h + rim - 1,
                    ),
                    radius=radius + rim,
                    fill=255,
                )
                inner = Image.new("L", (canvas_w, canvas_h), 0)
                ImageDraw.Draw(inner).rounded_rectangle(
                    (
                        comp_x,
                        comp_y,
                        comp_x + comp_w - 1,
                        comp_y + comp_h - 1,
                    ),
                    radius=radius,
                    fill=255,
                )
                rim_mask = ImageChops.subtract(outer, inner)
                tight = rim_mask.filter(
                    ImageFilter.GaussianBlur(max(4, int(5 * scale)))
                )
                wide = rim_mask.filter(
                    ImageFilter.GaussianBlur(max(8, int(10 * scale)))
                )
                # Paint the white pill itself. Keeping it in the image means
                # no opaque widget rectangle can clip the gradient corners.
                pill_hi = Image.new(
                    "L", (canvas_w * 2, canvas_h * 2), 0
                )
                ImageDraw.Draw(pill_hi).rounded_rectangle(
                    (
                        comp_x * 2,
                        comp_y * 2,
                        (comp_x + comp_w) * 2 - 1,
                        (comp_y + comp_h) * 2 - 1,
                    ),
                    radius=radius * 2,
                    fill=255,
                )
                pill = pill_hi.resize(
                    (canvas_w, canvas_h), Image.Resampling.LANCZOS
                )
                # The gradient alpha is static; only the mesh colours move.
                # Caching it avoids several full-canvas LUT operations per
                # frame, which keeps the larger animated composer light.
                intensity = 0.60 if self._composer_focused else 0.50
                lut_wide = [
                    max(0, min(255, int(value * intensity * 0.72)))
                    for value in range(256)
                ]
                lut_tight = [
                    max(0, min(255, int(value * intensity * 0.95)))
                    for value in range(256)
                ]
                glow_alpha = ImageChops.lighter(
                    wide.point(lut_wide), tight.point(lut_tight)
                )
                full_alpha = ImageChops.lighter(glow_alpha, rim_mask)
                # Keep the pill itself pure white. The white pill is baked
                # into the base so it does not need repainting each frame.
                full_alpha = ImageChops.subtract(full_alpha, pill)
                base_with_pill = Image.new(
                    "RGBA", (canvas_w, canvas_h), THEME["bg"]
                )
                base_with_pill.paste(
                    Image.new("RGBA", (canvas_w, canvas_h), THEME["surface"]),
                    (0, 0),
                    pill,
                )
                masks = (
                    cache_key,
                    rim_mask,
                    tight,
                    wide,
                    pill,
                    full_alpha,
                    base_with_pill,
                )
                self._composer_glow_masks = masks
            full_alpha, base = masks[5], masks[6]

            phase = self._composer_glow_phase
            low_w, low_h = 104, 18
            hue0 = (phase * 0.075) % 1.0
            palette = []
            for index in range(5):
                hue = (hue0 + index * 0.19) % 1.0
                red_c, green_c, blue_c = colorsys.hsv_to_rgb(
                    hue, 0.82, 1.0
                )
                palette.append(
                    (red_c * 255.0, green_c * 255.0, blue_c * 255.0)
                )

            centers = (
                (0.10 + 0.16 * math.sin(phase * 0.94),
                 0.50 + 0.38 * math.cos(phase * 0.78)),
                (0.34 + 0.20 * math.cos(phase * 0.86 + 0.7),
                 0.25 + 0.30 * math.sin(phase * 0.91)),
                (0.54 + 0.18 * math.sin(phase * 1.02 + 1.3),
                 0.70 + 0.27 * math.cos(phase * 0.73 + 0.4)),
                (0.76 + 0.17 * math.cos(phase * 0.80 + 2.0),
                 0.36 + 0.31 * math.sin(phase * 0.97 + 1.1)),
                (0.95 + 0.05 * math.sin(phase * 1.08 + 2.5),
                 0.60 + 0.29 * math.cos(phase * 0.88 + 1.7)),
            )
            sigma = 0.36
            inv = 1.0 / (2.0 * sigma * sigma)
            mesh = Image.new("RGB", (low_w, low_h))
            pixels = mesh.load()
            for y in range(low_h):
                v = y / max(1, low_h - 1)
                for x in range(low_w):
                    u = x / max(1, low_w - 1)
                    total = 0.0
                    red = green = blue = 0.0
                    for (cx, cy), (pr, pg, pb) in zip(centers, palette):
                        dx = u - cx
                        dy = v - cy
                        weight = math.exp(-(dx * dx + dy * dy) * inv)
                        total += weight
                        red += pr * weight
                        green += pg * weight
                        blue += pb * weight
                    if total <= 0.0001:
                        red, green, blue = palette[0]
                        total = 1.0
                    # Saturated RGB light with a small lift so it stays
                    # elegant against the light interface.
                    lift = 0.08
                    pixels[x, y] = (
                        int((red / total) * (1.0 - lift) + 255 * lift),
                        int((green / total) * (1.0 - lift) + 255 * lift),
                        int((blue / total) * (1.0 - lift) + 255 * lift),
                    )

            mesh = mesh.filter(ImageFilter.GaussianBlur(0.6))
            mesh = mesh.resize(
                (canvas_w, canvas_h), Image.Resampling.BILINEAR
            )
            mesh_rgba = mesh.convert("RGBA")

            result = base.copy()
            result.paste(mesh_rgba, (0, 0), full_alpha)

            self._composer_glow_photo = ImageTk.PhotoImage(result)
            if self._composer_glow_image_id is None:
                self._composer_glow_image_id = self.composer_canvas.create_image(
                    0, 0, anchor="nw", image=self._composer_glow_photo
                )
            else:
                self.composer_canvas.itemconfigure(
                    self._composer_glow_image_id,
                    image=self._composer_glow_photo,
                )
        except Exception:
            pass

    def _build_workspace(self, parent=None):
        parent = parent or self.main_frame
        self.workspace_frame = ctk.CTkFrame(
            parent, fg_color="transparent"
        )
        self.workspace_frame.pack(
            fill="both", expand=True, padx=24, pady=(10, 0)
        )

        # Working-state pills live between the conversation and the composer.
        # They stay visually inside the chat area instead of in the header.
        self.status_host = ctk.CTkFrame(
            self.workspace_frame, fg_color="transparent"
        )
        self.status_host.pack(side="bottom", fill="x")
        self._build_thinking_chip(self.status_host)
        self._build_vscode_chip(self.status_host)

        self.history_frame = ctk.CTkFrame(
            self.workspace_frame,
            fg_color=THEME["surface"],
            corner_radius=18,
            border_width=1,
            border_color=THEME["border"],
        )
        self.history_frame.pack(fill="both", expand=True)

        header_hist = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        header_hist.pack(fill="x", padx=20, pady=(14, 4))

        title_block = ctk.CTkFrame(header_hist, fg_color="transparent")
        title_block.pack(side="left", fill="x", expand=True)

        self.hist_lbl = ctk.CTkLabel(
            title_block,
            text="New chat",
            font=("Segoe UI", 15, "bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        self.hist_lbl.pack(anchor="w")

        self.activity_lbl = ctk.CTkLabel(
            title_block,
            text="Ask Orunex anything or describe a task.",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self.activity_lbl.pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header_hist, fg_color="transparent")
        actions.pack(side="right", padx=(12, 0))

        self.stream_status_lbl = ctk.CTkLabel(
            actions,
            text="●  Ready",
            height=26,
            corner_radius=8,
            fg_color=THEME["blue_soft"],
            text_color=THEME["blue"],
            font=("Segoe UI", 10, "bold"),
        )
        self.stream_status_lbl.pack(side="left")

        self.chat_scroll = ctk.CTkScrollableFrame(
            self.history_frame,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        self.chat_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        # The single conversation is exposed through the legacy helper so the
        # rest of the app can keep calling append_history/get_active_history.
        self.history_textboxes = {"current": self.chat_scroll}
        self._current_chat_key = "current"
        self._build_empty_state()

    def _build_empty_state(self):
        """A single clean, animated headline for an empty conversation."""
        if getattr(self, "empty_state", None) is not None:
            try:
                if self.empty_state.winfo_exists():
                    return
            except Exception:
                pass

        frame = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        frame.pack(fill="x", pady=(70, 20))

        try:
            headline = AnimatedGradientText(
                frame,
                text="At your service",
                font_size=52,
                bg=THEME["surface"],
                colors=(
                    "#7C3AED",
                    "#8B5CF6",
                    "#6366F1",
                    "#2563EB",
                    "#3B82F6",
                    "#7C3AED",
                ),
                glow_color="#8B5CF6",
            )
            headline.pack(anchor="center")
            self._empty_headline = headline
        except Exception:
            # Keep the empty state usable if Pillow/NumPy are unavailable.
            self._empty_headline = None
            ctk.CTkLabel(
                frame,
                text="At your service",
                font=("Segoe UI", 32, "bold"),
                text_color=THEME["blue"],
            ).pack(anchor="center", pady=18)

        self.empty_state = frame

        # A previous conversation may have left the scrollable canvas at the
        # bottom.  Keep the empty headline in view without disturbing a chat
        # that is populated before the idle callback runs.
        def _reset_empty_state_scroll(expected=frame):
            if getattr(self, "empty_state", None) is not expected:
                return
            try:
                self.chat_scroll._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass

        try:
            self.after_idle(_reset_empty_state_scroll)
        except Exception:
            pass

    def _dismiss_empty_state(self):
        """Stop and remove the animated headline as soon as a message exists."""
        headline = getattr(self, "_empty_headline", None)
        if headline is not None:
            try:
                headline.stop()
            except Exception:
                pass
        frame = getattr(self, "empty_state", None)
        if frame is not None:
            try:
                frame.pack_forget()
            except Exception:
                pass
            try:
                frame.destroy()
            except Exception:
                pass
        self.empty_state = None
        self._empty_headline = None

    # ── Saved conversations ─────────────────────────────────────────────
    def _open_initial_chat(self):
        """Restore the most recent saved chat, or start an empty draft.

        This runs after the main window is mapped.  Loading and scrolling the
        conversation while the splash has the window withdrawn can leave the
        CTkScrollableFrame's content window unmapped, which shows as a blank
        chat even though the messages are present.
        """
        if getattr(self, "_initial_chat_loaded", False):
            return
        self._initial_chat_loaded = True
        if getattr(self, "chats", None):
            latest = max(
                self.chats,
                key=lambda c: c.get("updated_at") or c.get("created_at") or "",
            )
            self._select_chat(latest.get("id"), switch_view=False)
        else:
            self.new_chat(switch_view=False, focus_input=False)

    def _chat_title_from_text(self, text):
        title = " ".join(str(text).split()).strip()
        if title.lower().startswith("remote simplex task:"):
            title = title.split(":", 1)[1].strip()
        if not title:
            return "New chat"
        return title if len(title) <= 42 else title[:41] + "…"

    def _ensure_chat(self):
        if getattr(self, "current_chat", None) is None:
            self.current_chat = chat_store.new_chat()
            self.current_chat_id = self.current_chat["id"]
        return self.current_chat

    def _persist_current_chat(self):
        chat = getattr(self, "current_chat", None)
        if not chat or not chat.get("messages"):
            return
        if not any(c.get("id") == chat.get("id") for c in self.chats):
            self.chats.append(chat)
        chat_store.save_chats(self.chats)

    def _record_message(self, text, tag, color, is_user, is_system):
        """Append a rendered message to the active chat and persist it."""
        if not text:
            return
        chat = self._ensure_chat()
        role = "user" if is_user else ("system" if is_system else "assistant")
        chat.setdefault("messages", []).append(
            chat_store.message(
                text,
                role,
                tag=str(tag or "info"),
                color=color if isinstance(color, str) else None,
            )
        )
        chat["updated_at"] = chat_store.now()
        if role == "user" and chat.get("title") in (None, "", "New chat"):
            chat["title"] = self._chat_title_from_text(text)
        if not any(c.get("id") == chat.get("id") for c in self.chats):
            self.chats.append(chat)
        chat_store.save_chats(self.chats)
        self.current_chat_id = chat.get("id")
        if hasattr(self, "hist_lbl"):
            try:
                self.hist_lbl.configure(text=chat.get("title") or "New chat")
            except Exception:
                pass
        self._refresh_chat_list()

    def _clear_chat_ui(self, show_empty=True):
        headline = getattr(self, "_empty_headline", None)
        if headline is not None:
            try:
                headline.stop()
            except Exception:
                pass
        active_hist = self.get_active_history()
        if active_hist:
            for widget in active_hist.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
        self.empty_state = None
        self._empty_headline = None
        if show_empty and getattr(self, "chat_scroll", None) is not None:
            self._build_empty_state()

    def new_chat(self, switch_view=True, focus_input=True):
        """Start a clean, unsaved draft chat from the sidebar."""
        self._persist_current_chat()
        self.current_chat = chat_store.new_chat()
        self.current_chat_id = self.current_chat["id"]
        self._clear_chat_ui(show_empty=True)
        try:
            self.hist_lbl.configure(text="New chat")
            self.activity_lbl.configure(
                text="Ask Orunex anything or describe a task."
            )
            self._set_stream_status("Ready", "blue")
        except Exception:
            pass
        if focus_input:
            try:
                self.input_entry.delete(0, "end")
                self.input_entry.focus_set()
            except Exception:
                pass
        self._refresh_chat_list()
        if switch_view:
            self.show_view("workspace")

    def _select_chat(self, chat_id, switch_view=True):
        chat = next(
            (c for c in getattr(self, "chats", []) if c.get("id") == chat_id),
            None,
        )
        if chat is None:
            return
        if (
            getattr(self, "current_chat", None) is not None
            and self.current_chat.get("id") == chat_id
        ):
            if switch_view:
                self.show_view("workspace")
            return
        self._persist_current_chat()
        self.current_chat = chat
        self.current_chat_id = chat_id
        self._clear_chat_ui(show_empty=False)
        messages = chat.get("messages", [])
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            self.append_history(
                msg.get("text", ""),
                tag=msg.get("tag", "info"),
                color=msg.get("color"),
                is_user=msg.get("role") == "user",
                persist=False,
            )
        if not messages:
            self._build_empty_state()
        try:
            self.hist_lbl.configure(text=chat.get("title") or "New chat")
            self.activity_lbl.configure(
                text="Ask Orunex anything or describe a task."
            )
            self._set_stream_status("Ready", "blue")
        except Exception:
            pass
        self._refresh_chat_list()
        if switch_view:
            self.show_view("workspace")

    def _refresh_chat_list(self):
        if hasattr(self, "_close_chat_menu"):
            self._close_chat_menu()
        if not hasattr(self, "chats_scroll"):
            return
        try:
            if not self.chats_scroll.winfo_exists():
                return
            children = list(self.chats_scroll.winfo_children())
        except Exception:
            return
        for widget in children:
            try:
                widget.destroy()
            except Exception:
                pass

        chats = [
            c
            for c in getattr(self, "chats", [])
            if isinstance(c, dict) and c.get("messages")
        ]
        chats.sort(
            key=lambda c: c.get("updated_at") or c.get("created_at") or "",
            reverse=True,
        )
        if not chats:
            ctk.CTkLabel(
                self.chats_scroll,
                text="No saved chats yet",
                font=("Segoe UI", 10),
                text_color=THEME["muted"],
                anchor="w",
            ).pack(fill="x", padx=12, pady=8)
            return

        for chat in chats:
            active = chat.get("id") == getattr(self, "current_chat_id", None)
            row = ctk.CTkFrame(
                self.chats_scroll,
                fg_color=THEME["blue_soft"] if active else "transparent",
                corner_radius=9,
            )
            row.pack(fill="x", padx=2, pady=1)
            title = str(chat.get("title") or "New chat")
            display = title if len(title) <= 28 else title[:27] + "…"
            title_btn = ctk.CTkButton(
                row,
                text=display,
                anchor="w",
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=THEME["blue_border"]
                if active
                else THEME["surface_muted"],
                text_color=THEME["blue"] if active else THEME["text_dim"],
                font=("Segoe UI", 11, "bold" if active else "normal"),
                command=lambda cid=chat.get("id"): self._select_chat(cid),
            )
            title_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))
            menu_btn = ctk.CTkButton(
                row,
                text="⋮",
                width=26,
                height=26,
                corner_radius=7,
                fg_color="transparent",
                hover_color=THEME["surface_muted"],
                text_color=THEME["muted"],
                font=("Segoe UI", 13),
                command=lambda cid=chat.get("id"): self._open_chat_menu(cid),
            )
            menu_btn.pack(side="right", padx=(0, 4), pady=3)

    def _open_chat_menu(self, chat_id):
        """Styled in-window menu for renaming or deleting a chat."""
        chat = next(
            (c for c in getattr(self, "chats", []) if c.get("id") == chat_id),
            None,
        )
        if chat is None:
            return
        self._close_chat_menu()

        menu = ctk.CTkFrame(
            self,
            width=176,
            fg_color=THEME["surface"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        self._chat_menu = menu

        rename = ctk.CTkButton(
            menu,
            text="Rename",
            anchor="w",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=THEME["surface_muted"],
            text_color=THEME["text"],
            font=("Segoe UI", 11),
            command=lambda: self._chat_menu_action(self._rename_chat, chat_id),
        )
        rename.pack(fill="x", padx=6, pady=(6, 2))

        separator = ctk.CTkFrame(menu, height=1, fg_color=THEME["border"])
        separator.pack(fill="x", padx=10, pady=2)

        delete = ctk.CTkButton(
            menu,
            text="Delete",
            anchor="w",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=THEME["red_soft"],
            text_color=THEME["red"],
            font=("Segoe UI", 11),
            command=lambda: self._chat_menu_action(self._delete_chat, chat_id),
        )
        delete.pack(fill="x", padx=6, pady=(2, 6))

        menu.update_idletasks()
        menu_w = menu.winfo_reqwidth()
        menu_h = menu.winfo_reqheight()
        try:
            ui_scale = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        except Exception:
            ui_scale = 1.0
        pointer_x = self.winfo_pointerx() - self.winfo_rootx()
        pointer_y = self.winfo_pointery() - self.winfo_rooty()
        x = max(8, min(pointer_x + 8, self.winfo_width() - menu_w - 8))
        y = max(8, min(pointer_y + 8, self.winfo_height() - menu_h - 8))
        # CTk applies widget scaling to place() coordinates; convert the
        # physical cursor position back to scaled coordinates.
        menu.place(x=x / ui_scale, y=y / ui_scale)
        menu.lift()
        self._chat_menu_click_bind = self.bind(
            "<Button-1>", self._on_root_click, add="+"
        )
        self._chat_menu_escape_bind = self.bind(
            "<Escape>", lambda _event: self._close_chat_menu(), add="+"
        )

    def _on_root_click(self, event):
        menu = getattr(self, "_chat_menu", None)
        if menu is None:
            return
        widget = event.widget
        while widget is not None:
            if widget is menu:
                return
            widget = getattr(widget, "master", None)
        self._close_chat_menu()

    def _chat_menu_action(self, action, chat_id):
        self._close_chat_menu()
        action(chat_id)

    def _close_chat_menu(self):
        menu = getattr(self, "_chat_menu", None)
        self._chat_menu = None
        if menu is not None:
            try:
                menu.destroy()
            except Exception:
                pass
        for attr in ("_chat_menu_click_bind", "_chat_menu_escape_bind"):
            bind_id = getattr(self, attr, None)
            if bind_id is not None:
                try:
                    self.unbind("<Button-1>" if attr.endswith("click_bind") else "<Escape>", bind_id)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _rename_chat(self, chat_id):
        chat = next(
            (c for c in getattr(self, "chats", []) if c.get("id") == chat_id),
            None,
        )
        if chat is None:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename chat")
        dialog.configure(fg_color=THEME["bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        fit_window(dialog, 440, 220)
        dialog.attributes("-topmost", True)

        card = ctk.CTkFrame(
            dialog,
            fg_color=THEME["surface"],
            corner_radius=16,
            border_width=1,
            border_color=THEME["border"],
        )
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            card,
            text="Rename chat",
            font=("Segoe UI", 17, "bold"),
            text_color=THEME["text"],
        ).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            card,
            text="Choose a short name for this conversation.",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=20, pady=(0, 10))

        entry = ctk.CTkEntry(
            card,
            height=38,
            font=("Segoe UI", 12),
            fg_color=THEME["bg"],
            border_color=THEME["border"],
            text_color=THEME["text"],
        )
        entry.pack(fill="x", padx=20)
        entry.insert(0, chat.get("title") or "New chat")
        entry.select_range(0, "end")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(12, 16))

        def close():
            try:
                dialog.grab_release()
            except Exception:
                pass
            try:
                dialog.attributes("-topmost", False)
            except Exception:
                pass
            try:
                dialog.destroy()
            except Exception:
                pass
            try:
                self.lift()
            except Exception:
                pass

        def save(event=None):
            new_title = " ".join(entry.get().split()).strip()
            if not new_title:
                return "break"
            chat["title"] = new_title[:60]
            chat_store.save_chats(self.chats)
            if getattr(self, "current_chat_id", None) == chat_id:
                try:
                    self.hist_lbl.configure(text=chat["title"])
                except Exception:
                    pass
            self._refresh_chat_list()
            close()
            return "break"

        ctk.CTkButton(
            actions,
            text="Cancel",
            width=92,
            height=36,
            corner_radius=9,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 11),
            command=close,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Save",
            width=92,
            height=36,
            corner_radius=9,
            fg_color=THEME["blue"],
            hover_color=THEME["accent_hover"],
            text_color="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            command=save,
        ).pack(side="right")

        entry.bind("<Return>", save)
        dialog.bind("<Return>", save)
        dialog.bind("<Escape>", lambda _event: close())
        dialog.protocol("WM_DELETE_WINDOW", close)

        def activate():
            try:
                dialog.lift()
                dialog.focus_force()
                dialog.grab_set()
            except Exception:
                pass
            entry.focus_set()

        dialog.after(60, activate)

    def _delete_chat(self, chat_id):
        chat = next(
            (c for c in getattr(self, "chats", []) if c.get("id") == chat_id),
            None,
        )
        if chat is None:
            return
        title = chat.get("title") or "New chat"

        dialog = ctk.CTkToplevel(self)
        dialog.title("Delete chat")
        dialog.configure(fg_color=THEME["bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        fit_window(dialog, 470, 240)
        dialog.attributes("-topmost", True)

        card = ctk.CTkFrame(
            dialog,
            fg_color=THEME["surface"],
            corner_radius=16,
            border_width=1,
            border_color=THEME["border"],
        )
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            card,
            text="Delete chat",
            font=("Segoe UI", 17, "bold"),
            text_color=THEME["text"],
        ).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            card,
            text=f"Delete “{title}”?\n\nThis cannot be undone.",
            justify="left",
            wraplength=380,
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=20, pady=(0, 12))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 16))

        def close():
            try:
                dialog.grab_release()
            except Exception:
                pass
            try:
                dialog.attributes("-topmost", False)
            except Exception:
                pass
            try:
                dialog.destroy()
            except Exception:
                pass
            try:
                self.lift()
            except Exception:
                pass

        def delete_chat_now():
            close()
            self.chats = [c for c in self.chats if c.get("id") != chat_id]
            chat_store.save_chats(self.chats)
            if getattr(self, "current_chat_id", None) == chat_id:
                self.current_chat = None
                self.current_chat_id = None
                if self.chats:
                    latest = max(
                        self.chats,
                        key=lambda c: c.get("updated_at")
                        or c.get("created_at")
                        or "",
                    )
                    self._select_chat(latest.get("id"))
                else:
                    self.new_chat()
            else:
                self._refresh_chat_list()

        ctk.CTkButton(
            actions,
            text="Cancel",
            width=92,
            height=36,
            corner_radius=9,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 11),
            command=close,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Delete",
            width=92,
            height=36,
            corner_radius=9,
            fg_color=THEME["red"],
            hover_color="#B42318",
            text_color="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            command=delete_chat_now,
        ).pack(side="right")

        dialog.bind("<Escape>", lambda _event: close())
        dialog.protocol("WM_DELETE_WINDOW", close)

        def activate():
            try:
                dialog.lift()
                dialog.focus_force()
                dialog.grab_set()
            except Exception:
                pass

        dialog.after(60, activate)

    def _set_stream_status(self, text, tone="blue"):
        if not hasattr(self, "stream_status_lbl") or not self.stream_status_lbl.winfo_exists():
            return
        palettes = {
            "blue": (THEME["blue_soft"], THEME["blue"]),
            "gray": (THEME["surface_muted"], THEME["text_dim"]),
            "red": (THEME["red_soft"], THEME["red"]),
        }
        bg, fg = palettes.get(tone, palettes["blue"])
        self.stream_status_lbl.configure(
            text=f"●  {text}", fg_color=bg, text_color=fg
        )

    @staticmethod
    def _hsv_hex(hue, saturation, value):
        """Return a Tk-friendly hex colour for an animated hue."""
        red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
        return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"

    def _blue_gradient_hex(self, phase, offset=0.0, saturation=0.82, value=0.84):
        """Animated blue-only shade used by the VS Code connection pill.

        The hue stays inside the blue/azure range so the pill remains calm and
        branded while the highlight travels across the label.
        """
        wave = 0.5 + 0.5 * math.sin((phase + offset) * 2.0 * math.pi)
        hue = 0.560 + 0.070 * wave
        brightness = value * (0.90 + 0.10 * wave)
        return self._hsv_hex(hue, saturation, brightness)

    @staticmethod
    def _create_pill(canvas, x1, y1, x2, y2, fill):
        """Draw a pill-shaped canvas region and return its item ids."""
        radius = max(1.0, (y2 - y1) / 2)
        return [
            canvas.create_rectangle(
                x1 + radius, y1, x2 - radius, y2, fill=fill, outline=""
            ),
            canvas.create_oval(x1, y1, x1 + 2 * radius, y2, fill=fill, outline=""),
            canvas.create_oval(x2 - 2 * radius, y1, x2, y2, fill=fill, outline=""),
        ]

    def _build_thinking_chip(self, parent):
        """Create the animated RGB ``Thinking...`` pill for the chat header."""
        try:
            widget_scale = ctk.ScalingTracker.get_widget_scaling(self) or 1.0
        except Exception:
            widget_scale = 1.0
        font_pixels = max(8, round(10 * widget_scale))
        self._thinking_font = tkfont.Font(
            family="Segoe UI", size=-font_pixels, weight="bold"
        )
        label = "Thinking..."
        text_width = sum(
            self._thinking_font.measure(character) for character in label
        )
        width = max(100, 36 + text_width)
        height = max(26, self._thinking_font.metrics("linespace") + 12)
        self._thinking_chip_width = width
        self._thinking_chip_height = height

        canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=THEME["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.thinking_canvas = canvas

        # A pale outer ring and a saturated inner ring form the glow border.
        self._thinking_ring_glow_items = self._create_pill(
            canvas, 1, 2, width - 1, height - 2, "#EAF2FF"
        )
        self._thinking_ring_border_items = self._create_pill(
            canvas, 2, 3, width - 2, height - 3, THEME["blue_border"]
        )
        self._create_pill(
            canvas, 4, 5, width - 4, height - 5, THEME["surface"]
        )

        centre_y = height / 2
        self._thinking_dot_glow_id = canvas.create_oval(
            8, centre_y - 5, 18, centre_y + 5, fill="#EAF2FF", outline=""
        )
        self._thinking_dot_id = canvas.create_oval(
            11, centre_y - 2.5, 16, centre_y + 2.5,
            fill=THEME["blue"], outline=""
        )

        text_x = 24
        self._thinking_text_x = text_x
        self._thinking_text_items = []
        self._thinking_halo_items = []
        for character in label:
            # Four offset copies give the glyphs a soft neon halo.
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self._thinking_halo_items.append(
                    canvas.create_text(
                        text_x + dx,
                        centre_y + dy,
                        text=character,
                        anchor="w",
                        font=self._thinking_font,
                        fill="#DDEBFF",
                    )
                )
            self._thinking_text_items.append(
                canvas.create_text(
                    text_x,
                    centre_y,
                    text=character,
                    anchor="w",
                    font=self._thinking_font,
                    fill=THEME["blue"],
                )
            )
            text_x += self._thinking_font.measure(character)

        # The chip is only packed while Orunex is working.
        canvas.pack_forget()

    def _build_vscode_chip(self, parent):
        """Create the animated blue ``Conectando con VScode...`` chip.

        It mirrors the Thinking... pill, but stays inside a calm blue palette
        so the VS Code connection state looks branded instead of multicolour.
        """
        try:
            widget_scale = ctk.ScalingTracker.get_widget_scaling(self) or 1.0
        except Exception:
            widget_scale = 1.0
        font_pixels = max(8, round(10 * widget_scale))
        self._vscode_font = tkfont.Font(
            family="Segoe UI", size=-font_pixels, weight="bold"
        )
        label = "Conectando con VScode..."
        text_width = sum(
            self._vscode_font.measure(character) for character in label
        )
        width = max(160, 36 + text_width)
        height = max(26, self._vscode_font.metrics("linespace") + 12)
        self._vscode_chip_width = width
        self._vscode_chip_height = height

        canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=THEME["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.vscode_canvas = canvas

        self._vscode_ring_glow_items = self._create_pill(
            canvas, 1, 2, width - 1, height - 2, "#EAF2FF"
        )
        self._vscode_ring_border_items = self._create_pill(
            canvas, 2, 3, width - 2, height - 3, THEME["blue_border"]
        )
        self._create_pill(
            canvas, 4, 5, width - 4, height - 5, THEME["surface"]
        )

        centre_y = height / 2
        self._vscode_dot_glow_id = canvas.create_oval(
            8, centre_y - 5, 18, centre_y + 5, fill="#EAF2FF", outline=""
        )
        self._vscode_dot_id = canvas.create_oval(
            11, centre_y - 2.5, 16, centre_y + 2.5,
            fill=THEME["blue"], outline=""
        )

        text_x = 24
        self._vscode_text_items = []
        self._vscode_halo_items = []
        for character in label:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self._vscode_halo_items.append(
                    canvas.create_text(
                        text_x + dx,
                        centre_y + dy,
                        text=character,
                        anchor="w",
                        font=self._vscode_font,
                        fill="#DDEBFF",
                    )
                )
            self._vscode_text_items.append(
                canvas.create_text(
                    text_x,
                    centre_y,
                    text=character,
                    anchor="w",
                    font=self._vscode_font,
                    fill=THEME["blue"],
                )
            )
            text_x += self._vscode_font.measure(character)

        canvas.pack_forget()

    def _show_vscode_connecting(self, minimum_seconds=2.2):
        """Display the RGB VS Code connection pill for a coding request."""
        if not hasattr(self, "vscode_canvas"):
            return
        try:
            if not self.vscode_canvas.winfo_exists():
                return
            self._hide_thinking()
            if not self._vscode_visible:
                self.activity_lbl.pack_forget()
                self.vscode_canvas.pack(anchor="center", pady=(4, 6))
                self._vscode_visible = True
            self._vscode_min_visible_until = time.time() + max(0.0, float(minimum_seconds))
            self._vscode_last_status = "connecting"
            if self._vscode_after_id is not None:
                try:
                    self.after_cancel(self._vscode_after_id)
                except Exception:
                    pass
                self._vscode_after_id = None
            self._animate_vscode_chip()
        except Exception:
            pass

    def _hide_vscode_connecting(self, show_thinking=True):
        """Hide the VS Code pill and optionally resume Thinking..."""
        self._vscode_visible = False
        self._vscode_min_visible_until = 0.0
        if getattr(self, "_vscode_after_id", None) is not None:
            try:
                self.after_cancel(self._vscode_after_id)
            except Exception:
                pass
            self._vscode_after_id = None
        try:
            self.vscode_canvas.pack_forget()
        except Exception:
            pass
        if show_thinking and self.is_processing and not self._thinking_visible:
            self._show_thinking()

    def _animate_vscode_chip(self):
        """Cycle an animated blue gradient across the VS Code connection pill."""
        self._vscode_after_id = None
        if not self._vscode_visible:
            return
        canvas = getattr(self, "vscode_canvas", None)
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except Exception:
            return

        phase = self._vscode_phase
        glow_color = self._blue_gradient_hex(phase, 0.0, 0.32, 1.0)
        border_color = self._blue_gradient_hex(phase, 0.08, 0.72, 0.94)
        for item in self._vscode_ring_glow_items:
            canvas.itemconfigure(item, fill=glow_color)
        for item in self._vscode_ring_border_items:
            canvas.itemconfigure(item, fill=border_color)
        canvas.itemconfigure(
            self._vscode_dot_glow_id,
            fill=self._blue_gradient_hex(phase, 0.04, 0.34, 1.0),
        )
        canvas.itemconfigure(
            self._vscode_dot_id,
            fill=self._blue_gradient_hex(phase, 0.04, 0.90, 0.92),
        )
        for index, item in enumerate(self._vscode_text_items):
            canvas.itemconfigure(
                item,
                fill=self._blue_gradient_hex(
                    phase, index * 0.026, 0.84, 0.82
                ),
            )
        for index, item in enumerate(self._vscode_halo_items):
            character_index = index // 4
            canvas.itemconfigure(
                item,
                fill=self._blue_gradient_hex(
                    phase, character_index * 0.026, 0.34, 1.0
                ),
            )
        self._vscode_phase = (phase + 0.018) % 1.0
        self._vscode_after_id = self.after(70, self._animate_vscode_chip)

    def _show_thinking(self):
        """Show the animated Thinking... label instead of activity text."""
        if not hasattr(self, "thinking_canvas"):
            return
        try:
            if not self.thinking_canvas.winfo_exists():
                return
            if getattr(self, "_vscode_visible", False):
                if time.time() < getattr(self, "_vscode_min_visible_until", 0.0):
                    return
                self._hide_vscode_connecting(show_thinking=False)
            if self._thinking_visible:
                return
            self.activity_lbl.pack_forget()
            self.thinking_canvas.pack(anchor="center", pady=(4, 6))
            self._thinking_visible = True
            self._thinking_idle_since = None
            if self._thinking_after_id is not None:
                try:
                    self.after_cancel(self._thinking_after_id)
                except Exception:
                    pass
                self._thinking_after_id = None
            self._animate_thinking()
        except Exception:
            pass

    def _hide_thinking(self):
        """Hide the animated label without touching the activity text."""
        self._thinking_visible = False
        self._thinking_idle_since = None
        if getattr(self, "_thinking_after_id", None) is not None:
            try:
                self.after_cancel(self._thinking_after_id)
            except Exception:
                pass
            self._thinking_after_id = None
        try:
            self.thinking_canvas.pack_forget()
        except Exception:
            pass

    def _animate_thinking(self):
        """Cycle a rainbow gradient and glow across the Thinking... label."""
        self._thinking_after_id = None
        if not self._thinking_visible:
            return
        canvas = getattr(self, "thinking_canvas", None)
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except Exception:
            return

        phase = self._thinking_phase
        glow_color = self._hsv_hex(phase, 0.35, 1.0)
        border_color = self._hsv_hex(phase + 0.08, 0.62, 0.92)
        for item in self._thinking_ring_glow_items:
            canvas.itemconfigure(item, fill=glow_color)
        for item in self._thinking_ring_border_items:
            canvas.itemconfigure(item, fill=border_color)

        canvas.itemconfigure(
            self._thinking_dot_glow_id,
            fill=self._hsv_hex(phase + 0.04, 0.35, 1.0),
        )
        canvas.itemconfigure(
            self._thinking_dot_id,
            fill=self._hsv_hex(phase + 0.04, 0.9, 0.9),
        )

        for index, item in enumerate(self._thinking_text_items):
            canvas.itemconfigure(
                item,
                fill=self._hsv_hex(phase + index * 0.065, 0.82, 0.78),
            )
        for index, item in enumerate(self._thinking_halo_items):
            character_index = index // 4
            canvas.itemconfigure(
                item,
                fill=self._hsv_hex(
                    phase + character_index * 0.065, 0.35, 1.0
                ),
            )

        self._thinking_phase = (phase + 0.014) % 1.0

        # Safety net: if a task ends without a final status message, stop the
        # animation after a quiet period instead of leaving it on forever.
        if not self.is_processing and self.execution_status not in ("RUNNING", "PAUSED"):
            now = time.time()
            if self._thinking_idle_since is None:
                self._thinking_idle_since = now
            elif now - self._thinking_idle_since > 12.0:
                self._show_activity_line("Ready.", "info")
                return
        else:
            self._thinking_idle_since = None

        self._thinking_after_id = self.after(70, self._animate_thinking)

    def _show_activity_line(self, message, level="info"):
        """Restore the normal activity line and hide the animated chip."""
        if not hasattr(self, "activity_lbl") or not self.activity_lbl.winfo_exists():
            return
        self._hide_thinking()
        self._hide_vscode_connecting(show_thinking=False)
        colors = {
            "info": THEME["text_dim"],
            "warn": THEME["warning"],
            "warning": THEME["warning"],
            "error": THEME["error"],
            "success": THEME["text_dim"],
        }
        short = message if len(message) <= 120 else message[:117] + "..."
        try:
            if not self.activity_lbl.winfo_manager():
                self.activity_lbl.pack(anchor="w", pady=(2, 0))
            self.activity_lbl.configure(
                text=short, text_color=colors.get(level, THEME["text_dim"])
            )
        except Exception:
            pass

    def _should_show_thinking(self, message, level="info"):
        """Collapse every thinking/processing status into one label."""
        text = str(message or "").lower()
        keywords = (
            "thinking", "processing", "procesando", "pensando", "analizando",
            "analyzing", "analysing", "classifying", "reasoning", "planning",
            "delegating", "executing", "starting task", "selecting tools",
            "working on",
        )
        if any(keyword in text for keyword in keywords):
            return True
        # While Orunex works, ordinary progress lines are noise. Keep the
        # single Thinking... chip and let errors/pauses/completion through.
        if self.is_processing and level in ("info", "warn", "warning"):
            quiet_exceptions = ("pause", "stop", "cancel", "error", "fail", "kill")
            if not any(term in text for term in quiet_exceptions):
                return True
        return False

    def _set_activity(self, message, level="info"):
        if not hasattr(self, "activity_lbl") or not self.activity_lbl.winfo_exists():
            return
        if self._should_show_thinking(message, level):
            self._show_thinking()
            return
        self._show_activity_line(message, level)

    def _refresh_simplex_btn(self):
        """Compatibility hook: refresh the in-window bridge page silently."""
        self._refresh_simplex_page()

    def start_simplex_monitor(self):
        """Keep the bridge page and window title in sync with the real state."""
        def monitor_loop():
            try:
                self._refresh_simplex_page()
                if project_manager.is_project_active():
                    step = project_manager.get_current_step()
                    if step:
                        self.title(f"Orunex — Synapse: {step.title}")
                    else:
                        self.title("Orunex — Finalizing task")
                else:
                    self.title("Orunex — Desktop Agent")
            except Exception:
                pass
            self.after(3000, monitor_loop)

        self.after(3000, monitor_loop)

    # ── In-window Simplex Bridge page ────────────────────────────────────────

    def _build_simplex_view(self):
        page = ctk.CTkFrame(
            self.view_host, fg_color=THEME["bg"], corner_radius=0
        )
        self._simplex_view = page

        scroll = ctk.CTkScrollableFrame(
            page,
            fg_color=THEME["bg"],
            corner_radius=0,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(18, 24))

        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            head,
            text="Pair Orunex with Simplex on your phone and control it over an "
                 "end-to-end encrypted channel.",
            font=("Segoe UI", 12),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=760,
        ).pack(anchor="w", pady=(4, 0))

        connection = ctk.CTkFrame(
            scroll,
            fg_color=THEME["surface"],
            corner_radius=16,
            border_width=1,
            border_color=THEME["border"],
        )
        connection.pack(fill="x", pady=(0, 12))

        conn_top = ctk.CTkFrame(connection, fg_color="transparent")
        conn_top.pack(fill="x", padx=22, pady=(18, 4))

        self.simplex_status_lbl = ctk.CTkLabel(
            conn_top,
            text="●  Checking bridge…",
            height=28,
            corner_radius=8,
            fg_color=THEME["surface_muted"],
            text_color=THEME["text_dim"],
            font=("Segoe UI", 11, "bold"),
        )
        self.simplex_status_lbl.pack(side="left")

        self.simplex_disconnect_btn = ctk.CTkButton(
            conn_top,
            text="Disconnect",
            width=96,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 10),
            command=self._disconnect_simplex,
        )
        self.simplex_disconnect_btn.pack(side="right", padx=(8, 0))

        self.simplex_pair_btn = ctk.CTkButton(
            conn_top,
            text="Start & pair",
            width=132,
            height=30,
            corner_radius=8,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color=THEME["accent_hover"],
            font=("Segoe UI", 10, "bold"),
            command=self.connect_simplex,
        )
        self.simplex_pair_btn.pack(side="right")

        self.simplex_detail_lbl = ctk.CTkLabel(
            connection,
            text="Orunex is checking the local Simplex CLI.",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.simplex_detail_lbl.pack(fill="x", padx=22, pady=(4, 16))

        pair_row = ctk.CTkFrame(connection, fg_color="transparent")
        pair_row.pack(fill="x", padx=22, pady=(0, 20))

        qr_card = ctk.CTkFrame(
            pair_row,
            fg_color=THEME["surface_soft"],
            width=238,
            height=238,
            corner_radius=14,
            border_width=1,
            border_color=THEME["border"],
        )
        qr_card.pack(side="left")
        qr_card.pack_propagate(False)

        self.simplex_qr_label = ctk.CTkLabel(
            qr_card,
            text="Your pairing QR\nwill appear here",
            font=("Segoe UI", 11),
            text_color=THEME["muted"],
            justify="center",
        )
        self.simplex_qr_label.pack(fill="both", expand=True, padx=12, pady=12)

        pair_info = ctk.CTkFrame(pair_row, fg_color="transparent")
        pair_info.pack(side="left", fill="both", expand=True, padx=(22, 0))

        ctk.CTkLabel(
            pair_info,
            text="Pair in three steps",
            font=("Segoe UI", 14, "bold"),
            text_color=THEME["text"],
            anchor="w",
        ).pack(anchor="w")
        for number, step in (
            ("1", "Tap the button above to create a secure invitation."),
            ("2", "Open Simplex on your phone and scan the QR code."),
            ("3", "Orunex becomes available for remote commands and notifications."),
        ):
            row = ctk.CTkFrame(pair_info, fg_color="transparent")
            row.pack(fill="x", pady=(7, 0))
            ctk.CTkLabel(
                row,
                text=number,
                width=22,
                height=22,
                corner_radius=11,
                fg_color=THEME["blue_soft"],
                text_color=THEME["blue"],
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left", anchor="n")
            ctk.CTkLabel(
                row,
                text=step,
                font=("Segoe UI", 11),
                text_color=THEME["text_dim"],
                anchor="w",
                justify="left",
                wraplength=440,
            ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        ctk.CTkLabel(
            pair_info,
            text="Pairing link",
            font=("Segoe UI", 10, "bold"),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(fill="x", pady=(16, 4))

        self.simplex_link_box = ctk.CTkTextbox(
            pair_info,
            height=62,
            font=("Consolas", 10),
            fg_color=THEME["surface_soft"],
            text_color=THEME["text"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=8,
        )
        self.simplex_link_box.pack(fill="x")
        self.simplex_link_box.insert("1.0", "No pairing link yet.")
        self.simplex_link_box.configure(state="disabled")

        link_actions = ctk.CTkFrame(pair_info, fg_color="transparent")
        link_actions.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            link_actions,
            text="Copy link",
            width=88,
            height=28,
            corner_radius=7,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 10),
            command=self._copy_simplex_link,
        ).pack(side="left")
        self.simplex_feedback_lbl = ctk.CTkLabel(
            link_actions,
            text="",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
        )
        self.simplex_feedback_lbl.pack(side="left", padx=(10, 0))

        prefs = ctk.CTkFrame(
            scroll,
            fg_color=THEME["surface"],
            corner_radius=16,
            border_width=1,
            border_color=THEME["border"],
        )
        prefs.pack(fill="x")
        ctk.CTkLabel(
            prefs,
            text="Bridge preferences",
            font=("Segoe UI", 14, "bold"),
            text_color=THEME["text"],
            anchor="w",
        ).pack(fill="x", padx=22, pady=(18, 2))
        ctk.CTkLabel(
            prefs,
            text="Choose what Orunex may send to your paired device.",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(fill="x", padx=22, pady=(0, 8))

        import _orunex_libs.simplex_bridge as sx_cfg  # type: ignore
        bridge_cfg = sx_cfg.load_config()
        self.simplex_notify_var = ctk.BooleanVar(
            value=bool(bridge_cfg.get("notify_on_complete", True))
        )
        self.simplex_remote_var = ctk.BooleanVar(
            value=bool(bridge_cfg.get("remote_commands", True))
        )

        for text, variable in (
            ("Notify me when a task finishes", self.simplex_notify_var),
            ("Accept commands sent from Simplex", self.simplex_remote_var),
            ("Send a local screenshot after tasks", self._send_screenshot_var),
            ("Send remote screenshots automatically", self._send_remote_screenshot_var),
        ):
            switch = ctk.CTkSwitch(
                prefs,
                text=text,
                variable=variable,
                onvalue="1",
                offvalue="0",
                progress_color=THEME["blue"],
                text_color=THEME["text"],
                font=("Segoe UI", 11),
            )
            switch.pack(anchor="w", padx=22, pady=5)

        prefs_actions = ctk.CTkFrame(prefs, fg_color="transparent")
        prefs_actions.pack(fill="x", padx=22, pady=(10, 18))
        ctk.CTkButton(
            prefs_actions,
            text="Save preferences",
            width=140,
            height=32,
            corner_radius=8,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color=THEME["accent_hover"],
            font=("Segoe UI", 11, "bold"),
            command=self._save_simplex_prefs,
        ).pack(side="left")
        self.simplex_prefs_feedback = ctk.CTkLabel(
            prefs_actions,
            text="",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
        )
        self.simplex_prefs_feedback.pack(side="left", padx=(12, 0))

        self._refresh_simplex_page()

    def _set_simplex_status(self, text, tone="idle"):
        if not hasattr(self, "simplex_status_lbl"):
            return
        palettes = {
            "ok": (THEME["blue_soft"], THEME["blue"]),
            "idle": (THEME["surface_muted"], THEME["text_dim"]),
            "warn": (THEME["warning_soft"], THEME["warning"]),
            "error": (THEME["red_soft"], THEME["red"]),
        }
        bg, fg = palettes.get(tone, palettes["idle"])
        try:
            self.simplex_status_lbl.configure(
                text=f"●  {text}", fg_color=bg, text_color=fg
            )
        except Exception:
            pass

    def _refresh_simplex_page(self):
        """Update the sidebar indicator and bridge page from the real state."""
        try:
            import _orunex_libs.simplex_bridge as sx  # type: ignore
            bridge = sx.get_bridge()
            connected = sx.is_connected()
            paired = bridge.is_linked()
            contact = bridge.config.get("last_contact_name") or ""
        except Exception:
            connected = False
            paired = False
            contact = ""

        self._simplex_paired = paired
        self._simplex_connected = connected
        self._update_sidebar_status(connected, paired, contact)

        if self._simplex_view is None or not hasattr(self, "simplex_status_lbl"):
            return
        try:
            if not self.simplex_status_lbl.winfo_exists():
                return
        except Exception:
            return

        if self._simplex_busy:
            return

        if paired:
            self._set_simplex_status("Paired", "ok")
            detail = (
                f"Linked to {contact}. Remote commands and notifications are active."
                if contact else
                "This desktop is linked. Remote commands and notifications are active."
            )
        elif connected:
            self._set_simplex_status("Connected · awaiting pairing", "warn")
            detail = (
                "The local bridge is online. Generate a pairing link and scan it "
                "with the Simplex app."
            )
        else:
            self._set_simplex_status("Not connected", "idle")
            detail = (
                "The local Simplex CLI is not reachable yet. Start the bridge to "
                "create a secure invitation."
            )

        try:
            self.simplex_detail_lbl.configure(text=detail)
            self.simplex_pair_btn.configure(
                text="Generate pairing link" if connected else "Start & pair",
                state="normal",
            )
            self.simplex_disconnect_btn.configure(
                state="normal" if connected else "disabled"
            )
        except Exception:
            pass

    def connect_simplex(self):
        """Start the bridge (if needed) and create a pairing link in-page."""
        if self._simplex_busy:
            return
        self._simplex_busy = True
        self._set_simplex_status("Starting bridge…", "warn")
        try:
            self.simplex_detail_lbl.configure(
                text="Starting the local Simplex CLI and creating a secure invitation. "
                     "This may take a few seconds."
            )
            self.simplex_pair_btn.configure(text="Connecting…", state="disabled")
            self.simplex_feedback_lbl.configure(text="", text_color=THEME["text_dim"])
        except Exception:
            pass

        def worker():
            import _orunex_libs.simplex_bridge as sx  # type: ignore
            started = time.time()
            try:
                if not sx.is_connected():
                    sx.init_bridge(
                        on_command_callback=self.handle_simplex_command,
                        force_enable=True,
                    )
                while not sx.is_connected() and (time.time() - started) < 90:
                    time.sleep(1)

                if not sx.is_connected():
                    error = (
                        sx.get_last_error()
                        or "The local Simplex CLI did not respond. Check that it is installed."
                    )
                    self.after(0, lambda e=error: self._simplex_pair_failed(e))
                    return

                link = sx.get_bridge().ensure_invite_link(timeout=45)
                if not link:
                    self.after(
                        0,
                        lambda: self._simplex_pair_failed(
                            "The bridge is online, but the pairing link could not be generated."
                        ),
                    )
                    return
                self.after(0, lambda l=link: self._show_simplex_link(l))
            except Exception as exc:
                self.after(0, lambda e=str(exc): self._simplex_pair_failed(e))
            finally:
                self.after(0, self._finish_simplex_pairing)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_simplex_pairing(self):
        self._simplex_busy = False
        try:
            self.simplex_pair_btn.configure(state="normal")
        except Exception:
            pass
        self._refresh_simplex_page()

    def _simplex_pair_failed(self, message):
        self._set_simplex_status("Bridge error", "error")
        try:
            self.simplex_detail_lbl.configure(text=message)
            self.simplex_feedback_lbl.configure(
                text=message, text_color=THEME["error"]
            )
            self.simplex_pair_btn.configure(text="Try again", state="normal")
        except Exception:
            pass

    def _show_simplex_link(self, link):
        self._simplex_link = link
        self._set_simplex_status("Ready to pair", "ok")
        try:
            self.simplex_detail_lbl.configure(
                text="Scan the QR code with the Simplex app, or copy the pairing "
                     "link to the device you want to link."
            )
            import _orunex_libs.simplex_bridge as sx  # type: ignore
            qr_path = sx.generate_qr_image(link)
            if qr_path and os.path.exists(qr_path):
                image = Image.open(qr_path)
                self._simplex_qr_ctk = ctk.CTkImage(
                    light_image=image, dark_image=image, size=(214, 214)
                )
                self.simplex_qr_label.configure(
                    image=self._simplex_qr_ctk, text=""
                )
            else:
                self.simplex_qr_label.configure(
                    image=None, text="QR code unavailable\nCopy the link below."
                )

            self.simplex_link_box.configure(state="normal")
            self.simplex_link_box.delete("1.0", "end")
            self.simplex_link_box.insert("1.0", link)
            self.simplex_link_box.configure(state="disabled")
            self.simplex_feedback_lbl.configure(
                text="Pairing link ready. Keep it private.",
                text_color=THEME["text_dim"],
            )
        except Exception as exc:
            self._simplex_pair_failed(f"Could not display the pairing link: {exc}")

    def _copy_simplex_link(self):
        if not self._simplex_link:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._simplex_link)
            self.simplex_feedback_lbl.configure(
                text="Link copied to the clipboard.", text_color=THEME["blue"]
            )
        except Exception:
            pass

    def _disconnect_simplex(self):
        try:
            import _orunex_libs.simplex_bridge as sx  # type: ignore
            sx.get_bridge().disconnect()
        except Exception:
            pass
        self._simplex_link = ""
        try:
            self.simplex_qr_label.configure(image=None, text="Your pairing QR\nwill appear here")
            self.simplex_link_box.configure(state="normal")
            self.simplex_link_box.delete("1.0", "end")
            self.simplex_link_box.insert("1.0", "No pairing link yet.")
            self.simplex_link_box.configure(state="disabled")
            self.simplex_feedback_lbl.configure(
                text="Bridge disconnected.", text_color=THEME["text_dim"]
            )
        except Exception:
            pass
        self._refresh_simplex_page()

    def _save_simplex_prefs(self):
        from _orunex_libs import config_manager
        self.config["send_screenshot"] = self._send_screenshot_var.get() == "1"
        self.config["send_remote_screenshot"] = (
            self._send_remote_screenshot_var.get() == "1"
        )
        config_manager.save_config(self.config)
        try:
            import _orunex_libs.simplex_bridge as sx  # type: ignore
            bridge = sx.get_bridge()
            bridge.config["notify_on_complete"] = bool(self.simplex_notify_var.get())
            bridge.config["remote_commands"] = bool(self.simplex_remote_var.get())
            bridge.save_config()
        except Exception:
            pass
        try:
            self.simplex_prefs_feedback.configure(
                text="Preferences saved.", text_color=THEME["blue"]
            )
            self.after(
                2200,
                lambda: self.simplex_prefs_feedback.configure(text=""),
            )
        except Exception:
            pass

    def toggle_fullscreen(self, event=None):
        self.fullscreen_state = not self.fullscreen_state
        self.attributes("-fullscreen", self.fullscreen_state)
        # Forzar redibujado de botones
        return "break"

    def end_fullscreen(self, event=None):
        self.fullscreen_state = False
        self.attributes("-fullscreen", False)
        return "break"

    def open_task_list_builder(self):
        """Create a sequential list of tasks and run them in order."""
        popup = ctk.CTkToplevel(self)
        popup.title("Task list builder")
        fit_window(popup, 620, 720)
        popup.attributes("-topmost", True)
        popup.configure(fg_color=THEME["bg"])
        popup.transient(self)

        ctk.CTkLabel(
            popup,
            text="Sequential task list",
            font=("Segoe UI", 19, "bold"),
            text_color=THEME["text"],
        ).pack(anchor="w", padx=28, pady=(24, 2))
        ctk.CTkLabel(
            popup,
            text="Queue several requests and run them one after another.",
            font=("Segoe UI", 12),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=28, pady=(0, 16))

        name_entry = ctk.CTkEntry(
            popup,
            placeholder_text="List name",
            width=400,
            height=40,
            font=("Segoe UI", 12),
            fg_color=THEME["surface"],
            border_color=THEME["border"],
            text_color=THEME["text"],
        )
        name_entry.pack(fill="x", padx=28, pady=4)

        import tkinter as tk
        notify_var = tk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(
            popup,
            text="Send progress to Simplex",
            font=("Segoe UI", 12),
            variable=notify_var,
            text_color=THEME["text"],
            fg_color=THEME["blue"],
            hover_color=THEME["accent_hover"],
        )
        chk.pack(anchor="w", padx=28, pady=10)

        import _orunex_libs.simplex_bridge as sx  # type: ignore
        if not sx.is_connected():
            chk.configure(
                state="disabled",
                text="Send progress to Simplex (pair the bridge first)",
            )

        tasks_frame = ctk.CTkScrollableFrame(
            popup,
            width=500,
            height=220,
            fg_color=THEME["surface"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        tasks_frame.pack(pady=8, fill="both", expand=True, padx=24)

        task_entries = []

        def add_task_field():
            idx = len(task_entries) + 1
            row = ctk.CTkFrame(tasks_frame, fg_color="transparent")
            row.pack(fill="x", pady=7)

            ctk.CTkLabel(
                row,
                text=f"{idx}.",
                font=("Segoe UI", 13, "bold"),
                text_color=THEME["blue"],
                width=26,
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row,
                placeholder_text=f"Describe task {idx}...",
                height=38,
                font=("Segoe UI", 12),
                fg_color=THEME["surface_soft"],
                border_color=THEME["border"],
                text_color=THEME["text"],
            )
            entry.pack(side="left", fill="x", expand=True, padx=6)

            def rem_row(r=row, e=entry):
                r.destroy()
                if e in task_entries:
                    task_entries.remove(e)

            ctk.CTkButton(
                row,
                text="Remove",
                width=64,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                border_width=0,
                text_color=THEME["error"],
                hover_color=THEME["red_soft"],
                font=("Segoe UI", 10),
                command=rem_row,
            ).pack(side="right")

            task_entries.append(entry)

        add_task_field()

        ctk.CTkButton(
            popup,
            text="+ Add task",
            width=110,
            height=34,
            corner_radius=8,
            fg_color=THEME["surface"],
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            command=add_task_field,
        ).pack(pady=8)

        def execute_list():
            tasks = [e.get().strip() for e in task_entries if e.get().strip()]
            if not tasks:
                return
            list_name = name_entry.get().strip() or "Untitled task list"
            notify = notify_var.get()

            import threading
            import time

            def runner():
                self.after(
                    0,
                    lambda: self.write_real_time(
                        f"Starting task list: {list_name} ({len(tasks)} tasks)", "info"
                    ),
                )

                for index, task in enumerate(tasks, 1):
                    while self.is_processing:
                        time.sleep(1)

                    self.is_processing = True
                    msg = f"Task {index}/{len(tasks)} — {list_name}:\n{task}"
                    self.after(0, lambda m=msg: self.append_history(m, is_user=True))

                    try:
                        self.after(0, lambda: self.write_real_time("Thinking...", "info"))
                        self.after(500, lambda: self.write_real_time("Thinking...", "success"))

                        import agents.cerebro as cerebro  # type: ignore
                        answer = cerebro.run(task, self.user_name, agent_mode="os")  # type: ignore
                        answer = answer.replace("[Cerebro]", "").replace("[CEREBRO]", "").strip()
                        self.after(0, lambda a=answer: self.append_history(a))

                        if notify and sx.is_connected():
                            safe_answer = (answer[:300] + "...") if len(answer) > 300 else answer
                            sx.notify(
                                f"Task {index}/{len(tasks)} ({list_name}) completed:\n{safe_answer}",
                                "success",
                            )
                    except Exception as exc:
                        self.after(
                            0,
                            lambda err=exc: self.write_real_time(
                                f"Task list error: {err}", "error"
                            ),
                        )
                        if notify and sx.is_connected():
                            sx.notify(
                                f"Task {index}/{len(tasks)} ({list_name}) failed: {exc}",
                                "error",
                            )
                    finally:
                        self.is_processing = False
                        self.execution_status = "IDLE"

                    time.sleep(2)

                self.after(
                    0,
                    lambda: self.write_real_time(
                        f"Task list completed: {list_name}", "success"
                    ),
                )
                if notify and sx.is_connected():
                    sx.notify(
                        f"Task list '{list_name}' completed all {len(tasks)} tasks.",
                        "info",
                    )

            threading.Thread(target=runner, daemon=True).start()

        ctk.CTkButton(
            popup,
            text="Run full list",
            height=44,
            corner_radius=10,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
            hover_color=THEME["accent_hover"],
            command=execute_list,
        ).pack(fill="x", padx=28, pady=(8, 6))
        ctk.CTkButton(
            popup,
            text="Close",
            height=36,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            command=popup.destroy,
        ).pack(fill="x", padx=28, pady=(0, 18))

    def show_splash(self):
        """Borderless intro: only the wordmark text, on a transparent window."""
        self.withdraw()
        try:
            self.update_idletasks()
        except Exception:
            pass

        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        width, height = 460, 240
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        splash.geometry(f"{width}x{height}+{x}+{y}")

        # A colour-keyed transparent window removes the white card entirely;
        # the labels are the only visible pixels. The key matches the light
        # app background so antialiased text edges stay clean.
        transparent = "#F8F9FA"
        splash.configure(bg=transparent)
        try:
            splash.attributes("-transparentcolor", transparent)
            splash.attributes("-topmost", True)
        except Exception:
            pass
        splash.attributes("-alpha", 0.0)

        # Centre both labels as a group. Giving `expand=True` to the first
        # label used to consume all the vertical space and clip the subtitle.
        content = tk.Frame(splash, bg=transparent)
        content.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            content,
            text="Orunex",
            bg=transparent,
            fg=THEME["text"],
            font=("Segoe UI", 44, "bold"),
        ).pack()
        tk.Label(
            content,
            text="DESKTOP AGENT",
            bg=transparent,
            fg=THEME["blue"],
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(2, 0))

        self._splash_window = splash
        self._splash_min_done = False
        self._splash_finishing = False
        splash.update_idletasks()
        fade_in(splash, 0.0, step=0.05)
        splash.after(1700, self._splash_minimum_elapsed)

    def _splash_minimum_elapsed(self):
        """Keep the intro up long enough to read, but not longer than needed."""
        self._splash_min_done = True
        self._maybe_finish_splash()

    def _maybe_finish_splash(self):
        """Dismiss the intro only when both the timer and services are ready."""
        splash = getattr(self, "_splash_window", None)
        if splash is None or getattr(self, "_splash_finishing", False):
            return
        if not getattr(self, "_backend_ready", False):
            return
        if not getattr(self, "_splash_min_done", False):
            return
        self._splash_finishing = True
        try:
            if not splash.winfo_exists():
                self.hide_splash()
                return
            fade_out_and_destroy(
                splash, step=0.07, on_complete=self.hide_splash
            )
        except Exception:
            self.hide_splash()

    def hide_splash(self):
        self._splash_window = None
        self._splash_finishing = False
        try:
            self.deiconify()
            self.state("normal")
            self.update_idletasks()
            # A short topmost pulse defeats Windows' focus-stealing guard so
            # the app is visible immediately when the intro fades away.
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.after(120, self._restore_idle_placeholder)
            # The chat is intentionally restored only once the window is
            # mapped; see _open_initial_chat for the Windows scroll-frame bug
            # this avoids.
            self.after(180, self._open_initial_chat)
            self.after(350, lambda: self.attributes("-topmost", False))
        except Exception:
            try:
                self.deiconify()
                self.lift()
            except Exception:
                pass

    def _restore_idle_placeholder(self):
        """Leave a fresh empty chat calm instead of showing a blinking caret."""
        try:
            if not self.input_entry.get():
                self.focus_set()
        except Exception:
            pass

    def write_real_time(self, message: str, level: str = "info", color=None):
        """Write a live status line without adding noise to the conversation."""
        def apply_status():
            self._set_activity(str(message), level)
            if level == "error":
                self._set_stream_status("Needs attention", "red")
            elif level in ("warn", "warning"):
                self._set_stream_status("Running", "blue")
            elif level == "success" and self.execution_status not in ("RUNNING", "PAUSED"):
                self._set_stream_status("Ready", "blue")

        self.after(0, apply_status)
        print(f"[{level.upper()}] {message}")

    def add_chat_tab(self):
        """Compatibility alias for the sidebar's New chat action."""
        self.new_chat()

    def clear_chat(self):
        """Reset the active chat to an empty draft.

        The header no longer exposes a Clear button; this helper remains for
        callers that need to discard the current draft without touching the
        other saved conversations.
        """
        chat = self._ensure_chat()
        chat["messages"] = []
        chat["title"] = "New chat"
        if any(c.get("id") == chat.get("id") for c in self.chats):
            self.chats = [
                c for c in self.chats if c.get("id") != chat.get("id")
            ]
            chat_store.save_chats(self.chats)
        self._clear_chat_ui(show_empty=True)
        try:
            self.hist_lbl.configure(text="New chat")
            self.activity_lbl.configure(
                text="Ask Orunex anything or describe a task."
            )
            self._set_stream_status("Ready", "blue")
        except Exception:
            pass
        self._refresh_chat_list()

    def get_active_history(self):
        if getattr(self, "chat_scroll", None) is None:
            return None
        try:
            if not self.chat_scroll.winfo_exists():
                return None
        except Exception:
            return None
        return self.chat_scroll

    def _artifact_badge(self, kind, path):
        """Return ``(label, foreground, background)`` for a file-type icon."""
        ext = (kind or os.path.splitext(path)[1].lstrip(".")).lower()
        palette = {
            "pdf": ("PDF", "#B42318", "#FEF1EF"),
            "docx": ("DOC", "#175CD3", "#EFF8FF"),
            "doc": ("DOC", "#175CD3", "#EFF8FF"),
            "xlsx": ("XLS", "#067647", "#ECFDF3"),
            "xls": ("XLS", "#067647", "#ECFDF3"),
            "pptx": ("PPT", "#B54708", "#FFF7ED"),
            "ppt": ("PPT", "#B54708", "#FFF7ED"),
            "csv": ("CSV", "#067647", "#ECFDF3"),
            "py": ("PY", "#5925DC", "#F4F3FF"),
            "js": ("JS", "#B54708", "#FFFAEB"),
            "ts": ("TS", "#175CD3", "#EFF8FF"),
            "html": ("HTML", "#B54708", "#FFFAEB"),
            "css": ("CSS", "#175CD3", "#EFF8FF"),
            "json": ("JSON", "#475467", "#F2F4F7"),
            "md": ("MD", "#475467", "#F2F4F7"),
            "txt": ("TXT", "#475467", "#F2F4F7"),
            "png": ("IMG", "#5925DC", "#F4F3FF"),
            "jpg": ("IMG", "#5925DC", "#F4F3FF"),
            "jpeg": ("IMG", "#5925DC", "#F4F3FF"),
            "svg": ("SVG", "#5925DC", "#F4F3FF"),
            "zip": ("ZIP", "#475467", "#F2F4F7"),
        }
        return palette.get(ext, ((ext.upper() or "FILE")[:4], "#475467", "#F2F4F7"))

    def _open_artifact_path(self, path, kind=""):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            messagebox.showwarning(
                "File not found",
                f"Orunex could not find this file:\n{path}",
            )
            return
        ext = (kind or os.path.splitext(path)[1].lstrip(".")).lower()
        if ext in ("py", "js", "ts", "html", "css", "json", "md", "txt", "java", "cpp", "c", "cs"):
            try:
                from integrations import vscode_integration

                if vscode_integration.bridge_available():
                    vscode_integration.open_file(path)
                    return
            except Exception:
                pass
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            self.write_real_time(f"Could not open the document: {exc}", "error")

    def _build_artifact_card(self, parent, spec):
        path = spec.get("path", "")
        kind = spec.get("kind", "")
        title = spec.get("title", "")
        filename = os.path.basename(path) or title or "Artifact"
        badge, fg, bg = self._artifact_badge(kind, path)
        type_label = artifact_studio.KIND_LABELS.get(
            kind.lower(), (os.path.splitext(path)[1].lstrip(".") or "FILE").upper()
        )
        try:
            size = os.path.getsize(path)
            size_label = (
                f"{size / (1024 * 1024):.1f} MB"
                if size >= 1024 * 1024
                else f"{max(1, size // 1024)} KB"
            )
        except Exception:
            size_label = ""

        card = ctk.CTkFrame(
            parent,
            fg_color=THEME["surface_soft"],
            corner_radius=10,
            border_width=1,
            border_color=THEME["border"],
        )
        card.pack(fill="x", pady=3)

        icon = ctk.CTkLabel(
            card,
            text=badge,
            width=46,
            height=36,
            corner_radius=8,
            fg_color=bg,
            text_color=fg,
            font=("Segoe UI", 9, "bold"),
        )
        icon.pack(side="left", padx=(8, 8), pady=8)

        copy = ctk.CTkFrame(card, fg_color="transparent")
        copy.pack(side="left", fill="x", expand=True, pady=6)
        name_lbl = ctk.CTkLabel(
            copy,
            text=filename,
            font=("Segoe UI", 11, "bold"),
            text_color=THEME["text"],
            anchor="w",
            justify="left",
            wraplength=340,
        )
        name_lbl.pack(anchor="w")
        meta_lbl = ctk.CTkLabel(
            copy,
            text=f"{type_label}" + (f" · {size_label}" if size_label else "")
                + (f" · {title}" if title and title != filename else ""),
            font=("Segoe UI", 9),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=340,
        )
        meta_lbl.pack(anchor="w")

        open_btn = ctk.CTkButton(
            card,
            text="Open",
            width=58,
            height=28,
            corner_radius=7,
            fg_color=THEME["blue_soft"],
            text_color=THEME["blue"],
            hover_color=THEME["blue_border"],
            font=("Segoe UI", 9, "bold"),
            command=lambda p=path, k=kind: self._open_artifact_path(p, k),
        )
        open_btn.pack(side="right", padx=(6, 8), pady=8)

        for widget in (icon, name_lbl, meta_lbl):
            try:
                widget.bind(
                    "<Button-1>",
                    lambda _event, p=path, k=kind: self._open_artifact_path(p, k),
                )
            except Exception:
                pass

    def _clean_visible_text(self, text):
        """Strip internal agent/executor tags from a user-facing bubble."""
        import re

        value = str(text or "")
        # Known machine tags, including [OPEN_URL: ...], [CMD: ...], [OK].
        value = re.sub(
            r"\[[A-Z][A-Z0-9_ -]{0,48}(?::[^\]]*)?\]", "", value
        )
        value = re.sub(
            r"\[(?:Cerebro|ORUNEX|Orunex|CEREBRO|Agent|SYSTEM|SISTEMA)[^\]]*\]",
            "",
            value,
            flags=re.IGNORECASE,
        )
        # Executor status headings and success/error wrappers.
        value = re.sub(
            r"(?m)^\s*\[\s*SISTEMA ORUNEX:[^\]]*\]\s*$", "", value
        )
        value = re.sub(r"(?m)^\s*\[\+\][^\n]*$", "", value)
        value = re.sub(r"(?m)^\s*\[!\][^\n]*$", "", value)
        # Any remaining leading labels such as [Kernel-Nav] or [GUI].
        value = re.sub(r"(?m)^\s*\[[^\]\n]{1,60}\]\s*", "", value)

        # Executor/live-status chatter must never look like an answer.  Older
        # chats saved these lines before the sanitizer existed; filtering here
        # also cleans them when a conversation is re-opened.
        internal_prefixes = (
            "intentando superar selector",
            "clic de redundancia",
            "click de redundancia",
            "chrome lanzado",
            "edge lanzado",
            "firefox lanzado",
            "navegador lanzado",
            "live vision:",
            "live microphone:",
            "live heard:",
            "task completed successfully.",
        )
        kept_lines = []
        for line in value.splitlines():
            normalized = line.strip().lower()
            if any(normalized.startswith(prefix) for prefix in internal_prefixes):
                continue
            kept_lines.append(line)
        value = "\n".join(kept_lines)

        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def append_history(
        self, text, tag="info", color=None, is_user=False, persist=True
    ):
        active_hist = self.get_active_history()
        if not active_hist:
            return

        import os
        import re

        widgets = re.findall(r'\[WIDGET:\s*(.*?)\]', text)
        artifact_specs = []
        for raw_artifact in re.findall(
            r'\[ARTIFACT:\s*(.*?)\]', text, flags=re.DOTALL
        ):
            parts = [part.strip() for part in raw_artifact.split("|")]
            if not parts or not parts[0]:
                continue
            artifact_path = os.path.abspath(parts[0])
            artifact_kind = (
                parts[1].lower()
                if len(parts) > 1 and parts[1]
                else os.path.splitext(artifact_path)[1].lstrip(".").lower()
            )
            artifact_title = (
                parts[2]
                if len(parts) > 2 and parts[2]
                else os.path.splitext(os.path.basename(artifact_path))[0]
            )
            artifact_specs.append(
                {
                    "path": artifact_path,
                    "kind": artifact_kind,
                    "title": artifact_title,
                }
            )
        clean_text = re.sub(r'\[WIDGET:\s*.*?\]', '', text)
        clean_text = re.sub(
            r'\[ARTIFACT:\s*.*?\]', '', clean_text, flags=re.DOTALL
        ).strip()

        is_user = bool(is_user) or tag == "user"
        if not is_user:
            clean_text = self._clean_visible_text(clean_text)
            # A bubble made only of internal status lines adds noise; do not
            # replace it with a fake \"Action completed\" message.
        if not clean_text and not widgets and not artifact_specs:
            return

        # The headline is only for an empty conversation.
        if getattr(self, "empty_state", None) is not None:
            self._dismiss_empty_state()

        is_system = tag in ["sys", "info", "error", "success", "warning"]
        if persist:
            # Keep renderable tags in the saved copy so artifact cards survive
            # a chat reload.  The visible bubble still uses clean_text.
            persist_text = text if (widgets or artifact_specs) else clean_text
            self._record_message(persist_text, tag, color, is_user, is_system)
        row_frame = ctk.CTkFrame(active_hist, fg_color="transparent")
        row_frame.pack(fill="x", padx=4, pady=5)

        if is_system:
            ctk.CTkLabel(
                row_frame,
                text=clean_text,
                font=("Segoe UI", 10),
                text_color=color or THEME["text_dim"],
                justify="left",
                anchor="w" if tag == "error" else "center",
                wraplength=640,
            ).pack(
                anchor="w" if tag == "error" else "center",
                padx=14,
                pady=2,
            )
            def scroll_to_bottom(hist=active_hist):
                try:
                    hist._parent_canvas.yview_moveto(1.0)
                except Exception:
                    pass

            active_hist.after(20, scroll_to_bottom)
            active_hist.after(120, scroll_to_bottom)
            return

        column = ctk.CTkFrame(row_frame, fg_color="transparent")
        column.pack(
            side="right" if is_user else "left",
            padx=(80, 8) if is_user else (8, 80),
            pady=1,
        )

        bubble_color = THEME["blue_soft"] if is_user else THEME["surface"]
        text_color = THEME["text"]
        bubble = ctk.CTkFrame(
            column,
            fg_color=bubble_color,
            corner_radius=16 if is_user else 12,
            border_width=0,
        )
        bubble.pack(anchor="e" if is_user else "w")

        if not is_user and clean_text:
            ctk.CTkLabel(
                bubble,
                text="Orunex",
                font=("Segoe UI", 9, "bold"),
                text_color=THEME["blue"],
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(9, 0))

        lbl = None
        if clean_text:
            lbl = ctk.CTkLabel(
                bubble,
                text=clean_text,
                font=("Segoe UI", 12),
                text_color=text_color,
                justify="left",
                anchor="w",
                wraplength=560,
            )
            lbl.pack(
                padx=14,
                pady=(4, 11) if not is_user else 10,
                fill="x",
                expand=True,
            )

        if not is_user and artifact_specs:
            artifact_stack = ctk.CTkFrame(bubble, fg_color="transparent")
            artifact_stack.pack(
                fill="x",
                padx=12,
                pady=(0 if clean_text else 10, 10),
            )
            for spec in artifact_specs:
                self._build_artifact_card(artifact_stack, spec)
        elif artifact_specs:
            # User-side artifacts are uncommon, but keeping the card next to
            # the message makes the behavior consistent.
            artifact_stack = ctk.CTkFrame(column, fg_color="transparent")
            artifact_stack.pack(anchor="e", pady=(4, 0))
            for spec in artifact_specs:
                self._build_artifact_card(artifact_stack, spec)

        if lbl is not None:
            def on_resize(event=None, label=lbl, hist_panel=active_hist):
                try:
                    width = hist_panel.winfo_width()
                    if width < 10:
                        width = 640
                    label.configure(wraplength=max(220, width - 180))
                except Exception:
                    pass

            active_hist.bind("<Configure>", on_resize, add="+")
            self.after(100, on_resize)

        if not is_user and (clean_text or widgets):
            tools_row = ctk.CTkFrame(column, fg_color="transparent")
            tools_row.pack(anchor="w", pady=(2, 0))

            if clean_text:
                def copy_text(t=clean_text):
                    self.clipboard_clear()
                    self.clipboard_append(t.strip())

                ctk.CTkButton(
                    tools_row,
                    text="Copy",
                    width=44,
                    height=22,
                    corner_radius=6,
                    fg_color="transparent",
                    border_width=0,
                    text_color=THEME["muted"],
                    hover_color=THEME["surface_muted"],
                    font=("Segoe UI", 9),
                    command=copy_text,
                ).pack(side="left")

            for widget_path in widgets:
                def open_widget(p=widget_path):
                    try:
                        os.startfile(p)  # type: ignore
                    except Exception as exc:
                        self.write_real_time(
                            f"Could not open the document: {exc}", "error"
                        )

                w_name = os.path.basename(widget_path.strip())
                ctk.CTkButton(
                    tools_row,
                    text=f"Open {w_name}",
                    height=22,
                    corner_radius=6,
                    fg_color=THEME["blue_soft"],
                    border_width=0,
                    text_color=THEME["blue"],
                    hover_color=THEME["blue_border"],
                    font=("Segoe UI", 9),
                    command=open_widget,
                ).pack(side="left", padx=(8, 0))

        def scroll_to_bottom(hist=active_hist):
            try:
                hist._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass

        active_hist.after(20, scroll_to_bottom)
        active_hist.after(120, scroll_to_bottom)

    def handle_remote_command(self, cmd_text):
        """Gateway for commands arriving from a paired mobile client."""
        if "SIMPLEX_KILL_SWITCH" in cmd_text:
            self.write_real_time("Remote kill switch activated. Aborting local work...", "error")
            self.is_processing = False
            return "Local work was stopped by the remote kill switch."

        if cmd_text.startswith("SIMPLEX_TASK:"):
            task = cmd_text.replace("SIMPLEX_TASK:", "").strip()
            self.after(0, lambda: self._process_remote_task(task))
            # The bridge already sent the single Thinking... label. The final
            # answer is delivered by _process_remote_task, so never return an
            # intermediate "executing" status here.
            return None

        return "Unknown network command."

    def _process_remote_task(self, task):
        """Route a remote Simplex request through the local agent."""
        msg = f"Remote Simplex task:\n{task}"
        self.append_history(msg, is_user=True)

        if self.is_processing:
            try:
                import _orunex_libs.simplex_bridge as sx  # type: ignore
                sx.get_bridge().send_notification(
                    "Orunex is busy with another task. Try again later or send !stop.",
                    "warning",
                )
            except Exception:
                pass
            return

        self.is_processing = True
        self._set_stream_status("Running", "blue")
        self.write_real_time("Thinking...", "info")

        import threading
        def runner():
            remote_ok = True
            try:
                import _orunex_libs.simplex_bridge as sx # type: ignore
                # Phase 74: Pure Unified Nucleus (Cerebro)
                from agents.cerebro import run as cerebro_run # type: ignore

                ans = cerebro_run(task, "SimplexRemoteUser", agent_mode="os") # type: ignore
                
                # Execute OS actions (YouTube, apps, power control, etc.)
                from _orunex_libs.os_executor import intercept_and_execute # type: ignore
                exec_results = intercept_and_execute(ans)
                
                # Clean answer for GUI and Simplex display
                clean_ans = ans.replace("[Cerebro]", "").replace("[Orunex]", "").replace("[CEREBRO]", "").strip()
                if exec_results and exec_results != ans.strip():
                    clean_ans = f"{clean_ans}\n\n{exec_results}"
                
                # Append to laptop screen UI
                self.after(0, lambda a=clean_ans: self.append_history(a, tag="Cerebro"))
                
                try:
                    if sx.get_bridge().linked:
                        safe_ans = (clean_ans[:600] + '\n(Response truncated for network delivery)') if len(clean_ans) > 600 else clean_ans
                        sx.get_bridge().send_notification(safe_ans)

                        # Optional visual proof, removed immediately after delivery.
                        if self.config.get("send_remote_screenshot", False):
                            from _orunex_libs.os_executor import take_screenshot  # type: ignore
                            import os as _os
                            path = take_screenshot()
                            if path and _os.path.exists(path):
                                sx.get_bridge().send_file(path, caption="Visual proof")
                                _os.remove(path)
                except Exception:
                    pass
            except Exception as e:
                remote_ok = False
                self.after(0, lambda: self.write_real_time(f"Remote error: {e}", "error"))
                try:
                    import _orunex_libs.simplex_bridge as sx  # type: ignore
                    sx.get_bridge().send_notification(f"Orunex error: {e}", "error")
                except Exception:
                    pass
            finally:
                self.is_processing = False
                if remote_ok:
                    def finish_remote():
                        self._set_stream_status("Ready", "blue")
                        self._set_activity("Ready.", "info")
                    self.after(0, finish_remote)
                else:
                    self.after(
                        0,
                        lambda: self._set_stream_status(
                            "Needs attention", "red"
                        ),
                    )

        threading.Thread(target=runner, daemon=True).start()

    def listen_voice(self):
        # Check dependencies BEFORE opening UI
        try:
            import speech_recognition as sr # type: ignore
            import pyttsx3 # type: ignore
            import pyaudio # Required for Microphone
        except ImportError as ie:
            messagebox.showerror(
                "Missing voice dependencies",
                "Install the voice packages:\n"
                "pip install sounddevice scipy SpeechRecognition pyttsx3\n\n"
                f"Error: {ie}",
            )
            return

        # Voice call window
        self.call_win = ctk.CTkToplevel(self)
        self.call_win.title("Orunex — Voice call")
        fit_window(self.call_win, 480, 550)
        self.call_win.configure(fg_color=THEME["bg"])
        self.call_win.attributes("-topmost", True)
        self.call_win.resizable(False, False)

        frame = ctk.CTkFrame(
            self.call_win,
            fg_color=THEME["surface"],
            corner_radius=15,
            border_width=1,
            border_color=THEME["border"],
        )
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text="Voice call",
            font=("Segoe UI", 20, "bold"),
            text_color=THEME["text"],
        ).pack(pady=(20, 5))

        status_lbl = ctk.CTkLabel(
            frame,
            text="Ready to listen",
            font=("Segoe UI", 13, "bold"),
            text_color=THEME["blue"],
        )
        status_lbl.pack(pady=(5, 10))

        transcript_box = ctk.CTkTextbox(
            frame,
            height=250,
            fg_color=THEME["surface_soft"],
            text_color=THEME["text"],
            font=("Segoe UI", 12),
            corner_radius=10,
            border_width=1,
            border_color=THEME["border"],
        )
        transcript_box.pack(fill="x", padx=20, pady=5)
        transcript_box.insert(
            "end",
            "The call will start in a few seconds.\n"
            "Speak clearly after you see 'Listening'.\n\n",
        )

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.pack(pady=(10, 15))

        self.call_active = True

        def hang_up():
            self.call_active = False
            try:
                self.call_win.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            controls,
            text="End call",
            fg_color=THEME["red"],
            hover_color=THEME["error_hover"],
            command=hang_up,
            width=160,
            height=42,
            corner_radius=10,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=5)

        def call_loop():
            import queue
            try:
                from faster_whisper import WhisperModel # type: ignore
                import sounddevice as sd # type: ignore
                import numpy as np # type: ignore
            except ImportError as ie:
                self.after(0, lambda m=str(ie): transcript_box.insert("end", f"[Whisper error] Missing dependency: {m}\n"))
                return
            # Phase 103: Load Offline Whisper (Tiny)
            try:
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                q = queue.Queue()
                def audio_callback(indata, frames, timestamp, status):
                    if self.call_active: q.put(indata.copy())
            except Exception as e:
                self.after(0, lambda m=str(e): transcript_box.insert("end", f"[Whisper Error] {m}\n"))
                return
            
            # Initialize TTS engine
            try:
                engine = pyttsx3.init()
                # Configure voice: slower rate, Spanish voice if available
                engine.setProperty('rate', 160)
                voices = engine.getProperty('voices')
                for v in voices:
                    if 'spanish' in v.name.lower() or 'espanol' in v.name.lower():
                        engine.setProperty('voice', v.id)
                        break
            except Exception as te:
                err_m = str(te)
                self.after(0, lambda m=err_m: transcript_box.insert("end", f"[Error TTS] {m}\n"))
                return
            
            # Phase 74: Pure Unified Nucleus (Cerebro)
            from agents.cerebro import run as cerebro_run # type: ignore
            
            with sd.InputStream(samplerate=16000, channels=1, callback=audio_callback):
                while self.call_active:
                    try:
                        # Phase 1: LISTENING
                        if hasattr(status_lbl, 'winfo_exists') and status_lbl.winfo_exists():
                            self.after(0, lambda: status_lbl.configure(text="Listening (offline)...", text_color=THEME["blue"]))
                    
                        audio_data = []
                        start_t = time.time()
                        # Capture ~4 seconds or until call_active is False
                        while self.call_active and (time.time() - start_t < 10):
                            try:
                                chunk = q.get(timeout=0.2)
                                audio_data.append(chunk)
                                # Simple silence detection or fixed window
                                if len(audio_data) > 20: break 
                            except queue.Empty:
                                if time.time() - start_t > 1: break
                        
                        if not self.call_active or not audio_data: continue
                        
                        # Phase 2: PROCESSING
                        if hasattr(status_lbl, 'winfo_exists') and status_lbl.winfo_exists():
                            self.after(0, lambda: status_lbl.configure(text="Transcribing...", text_color=THEME["blue"]))
                        
                        full_audio = np.concatenate(audio_data, axis=0).flatten()
                        segments, info = model.transcribe(full_audio, beam_size=5, language="es")
                        heard_text = "".join([s.text for s in segments]).strip()
                        
                        if not heard_text or len(heard_text) < 2:
                            continue
                        
                        # Show what user said
                        txt = heard_text
                        def _upd_u(t=txt):
                            if hasattr(transcript_box, 'winfo_exists') and transcript_box.winfo_exists():
                                transcript_box.insert("end", f" You: {t}\n")
                                transcript_box.see("end")
                        self.after(0, _upd_u)
                        
                        # Phase 3: THINKING & OS CONTROL
                        if hasattr(status_lbl, 'winfo_exists') and status_lbl.winfo_exists():
                            self.after(0, lambda: status_lbl.configure(text="Thinking...", text_color=THEME["blue"]))
                            
                        # Phase 98: OS execution using Cerebro (Deepseek-R1)
                        raw_machine_response = cerebro_run(heard_text, self.user_name, agent_mode="os")
                        
                        # Phase 115: Sovereign Bridge (EXECUTION)
                        from _orunex_libs.os_executor import intercept_and_execute # type: ignore
                        intercept_and_execute(raw_machine_response)
                        
                        # Phase 114: Orunex Universal Synthesis
                        from agents.universal import voice_synthesis as orunex_voice # type: ignore
                        clean_response = orunex_voice(heard_text, self.user_name)
                        
                        if not clean_response:
                            clean_response = "Action completed successfully."
                        
                        # Truncate for display
                        display_text = clean_response[:300] + "..." if len(clean_response) > 300 else clean_response # type: ignore
                        
                        resp_txt = display_text
                        def _upd_r(r=resp_txt):
                            if hasattr(transcript_box, 'winfo_exists') and transcript_box.winfo_exists():
                                transcript_box.insert("end", f" Orunex: {r}\n\n")
                                transcript_box.see("end")
                        self.after(0, _upd_r)
                        
                        # Phase 5: SPEAKING
                        if hasattr(status_lbl, 'winfo_exists') and status_lbl.winfo_exists():
                            self.after(0, lambda: status_lbl.configure(text="Speaking...", text_color=THEME["blue"]))
                        
                        if not self.call_active:
                            break
                        
                        speech_text = clean_response[:500] # type: ignore
                        
                        import subprocess
                        safe_speech = speech_text.replace('"', '').replace("'", "").replace('\n', ' ')
                        script = f'''import pyttsx3, sys
try:
    e = pyttsx3.init()
    e.setProperty('rate', 160)
    for v in e.getProperty('voices'):
        if 'spanish' in v.name.lower() or 'espanol' in v.name.lower():
            e.setProperty('voice', v.id)
            break
    e.say("{safe_speech}")
    e.runAndWait()
except:
    sys.exit(0)
'''
                        subprocess.run(["python", "-c", script], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)

                    
                    except Exception as e:
                        err = str(e)
                        self.after(0, lambda m=err: transcript_box.insert("end", f"[Voice Loop Error] {m}\n"))
            
            # Cleanup
            try:
                engine.stop()
            except:
                pass
                        
        import threading
        threading.Thread(target=call_loop, daemon=True).start()

    def load_image(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Attach a file or document",
            filetypes=[
                (
                    "Orunex documents",
                    "*.png *.jpg *.jpeg *.bmp *.pdf *.txt *.docx *.csv *.xlsx *.xls",
                ),
                ("Excel", "*.xlsx *.xls"),
                ("Images", "*.png *.jpg *.jpeg *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.current_image_path = path
            self.append_history(
                f"Attached: {os.path.basename(path)} (the agent can analyze it)",
                tag="sys",
                color=THEME["text_dim"],
            )

    def toggle_pause(self):
        if self.execution_status == "RUNNING":
            self.execution_status = "PAUSED"
            self.execution_flag.clear()
            self._stop_task_glow()
            self.pause_btn.configure(text="Resume")
            self._set_stream_status("Paused", "gray")
            self.write_real_time("Execution paused. The agent is waiting.", "warn")
        elif self.execution_status == "PAUSED":
            self.execution_status = "RUNNING"
            self.execution_flag.set()
            if self._live_vision_active:
                self.start_screen_glow()
            self.pause_btn.configure(text="Pause")
            self._set_stream_status("Running", "blue")
            self.write_real_time("Execution resumed.", "info")

    def cancel_execution(self):
        if self.execution_status not in ("RUNNING", "PAUSED"):
            self.write_real_time("No active task is running.", "info")
            return

        self.execution_status = "CANCELLED"
        self.execution_flag.set()
        self._stop_task_glow()
        self.update_action_buttons(show=False)
        self.is_processing = False
        self._set_stream_status("Stopped", "red")
        self.write_real_time("Execution stopped by the user.", "error")
        self.append_history(
            "Execution stopped by the user.",
            tag="error",
            color=THEME["red"],
        )
        self._last_task_error = False
        self.after(80, lambda: self._set_stream_status("Stopped", "red"))

    def update_action_buttons(self, show=True):
        if show:
            if not self.pause_btn.winfo_manager():
                self.pause_btn.pack(side="right", padx=(0, 6), pady=12)
            self.pause_btn.configure(text="Pause")
            self._set_stream_status("Running", "blue")
        else:
            self.pause_btn.pack_forget()
            if self.execution_status == "CANCELLED":
                self._set_stream_status("Stopped", "red")
            elif self.execution_status == "PAUSED":
                self._set_stream_status("Paused", "gray")
            elif getattr(self, "_last_task_error", False):
                self._set_stream_status("Needs attention", "red")
            else:
                self._set_stream_status("Ready", "blue")

    def _finish_local_task(self):
        """Reset the UI after a deterministic task that returns early."""
        self.is_processing = False
        if self.execution_status != "CANCELLED":
            self.execution_status = "IDLE"
        self._stop_task_glow()
        self.update_action_buttons(show=False)

    def _complete_artifact_task(self, artifact):
        """Render a deterministic artifact and its clickable chat card."""
        filename = os.path.basename(artifact.get("path", ""))
        label = artifact.get("label", "file")
        title = artifact.get("title", filename)
        message = (
            f"Listo. Creé **{filename}** con Artifact Studio.\n"
            f"Tipo: {label} · Tema: {title}\n\n"
            "Puedes abrirlo directamente desde la tarjeta de abajo."
        )
        self._last_task_error = False
        self.append_history(
            message + "\n\n" + artifact.get("tag", ""),
            tag="Cerebro",
            color=AGENTS_INFO["Cerebro"]["color"],
        )
        self.write_real_time(f"Artifact ready: {filename}", "success")
        self._show_activity_line("Artifact ready.", "success")
        self._set_stream_status("Ready", "blue")
        self._finish_local_task()

    def _run_command_fallback(self, command, cwd):
        """Run a test command if the VS Code bridge is unavailable."""
        import subprocess
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt" else 0,
            )
            return {
                "ok": completed.returncode == 0,
                "code": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
                "testCommand": command,
                "fallback": True,
            }
        except Exception as exc:
            return {
                "ok": False,
                "code": 1,
                "stdout": "",
                "stderr": str(exc),
                "testCommand": command,
                "fallback": True,
            }

    def _complete_programmer_task(self, info, connection, tests):
        """Show only the generated code cards, without technical chatter."""
        tests_ok = bool(tests.get("ok"))
        tags = []
        for path in info.get("files", []):
            if not path or not os.path.exists(path):
                continue
            kind = os.path.splitext(path)[1].lstrip(".").lower() or "file"
            title = os.path.basename(path)
            tags.append(artifact_studio.artifact_tag(path, kind, title))
        if tags:
            self.append_history(
                "\n".join(tags),
                tag="Cerebro",
                color=AGENTS_INFO["Cerebro"]["color"],
            )
        self._last_task_error = not tests_ok
        self._hide_thinking()
        self._hide_vscode_connecting(show_thinking=False)
        self._show_activity_line(
            "Ask Orunex anything or describe a task.", "info"
        )
        self._set_stream_status(
            "Ready" if tests_ok else "Needs attention",
            "blue" if tests_ok else "red",
        )
        self._finish_local_task()

    def _detect_direct_command(self, task):
        """Return a high-confidence local command before the LLM sees it.

        This covers short desktop intents only (open a site/browser/app).  It
        is the zero-latency semantic layer: it recognises Spanish/English
        variants, preserves the requested browser, and refuses ambiguous
        commands such as a bare "abre" instead of letting a model guess.
        """
        try:
            from _orunex_libs.intent_router import parse_command

            return parse_command(task, getattr(self, "_command_context", {}))
        except Exception:
            return None

    def _remember_direct_command(self, intent, ok=True):
        if not ok:
            return
        context = {
            "last_kind": intent.kind,
            "last_app": intent.app,
            "language": getattr(self, "_command_language", "es"),
        }
        if intent.kind == "open_url":
            context.update(
                {
                    "last_url": intent.url,
                    "last_label": intent.label,
                    "last_browser": intent.browser,
                }
            )
        self._command_context = context

    def _complete_direct_command(self, message, ok=True, speak=True):
        self._last_task_error = not ok
        # Live is voice-first: start the spoken reply before painting the
        # text bubble, so synthesis is already running while the UI renders.
        if speak and self._live_vision_active:
            self._speak_live_response(message)
            speak = False
        self.append_history(
            message,
            tag="Cerebro",
            color=AGENTS_INFO["Cerebro"]["color"],
        )
        self.write_real_time(message, "success" if ok else "error")
        self._show_activity_line(
            "Live" if self._live_vision_active else "Ask Orunex anything or describe a task.",
            "info",
        )
        self._set_stream_status("Ready" if ok else "Needs attention", "blue" if ok else "red")
        if speak:
            self._speak_live_response(message)
        self._finish_local_task()

    def send_task(self):
        task = self.input_entry.get().strip()
        if not task:
            return
        self.input_entry.delete(0, "end")

        selected_mode = self.current_mode
        resolved_mode = mode_router.resolve_mode(task, selected_mode)
        self._resolved_mode = resolved_mode
        is_programmer = mode_router.is_programming_request(task, selected_mode)

        self.append_history(f"{task}", tag="user")

        self.execution_status = "RUNNING"
        self.is_processing = True
        self._last_task_error = False
        self.execution_flag.set()
        self.pause_btn.configure(text="Pause")
        self.update_action_buttons(show=True)
        self._set_activity("Thinking...", "info")
        if is_programmer:
            # Every programming request shows the calm blue connection state
            # before work begins.
            self._show_vscode_connecting(2.4)

        # The blue contour is the Live-mode indicator.  It must not appear
        # merely because a typed task is running while Live is off.
        if self._live_vision_active:
            self.after(0, self.start_screen_glow)

        def task_thread():
            nonlocal task

            # ── INSTANT GREETING (zero network latency) ───────────────────
            # "Hola", "Orunex" or "gracias" get a local, pre-cached spoken
            # reply.  Sending them to a model made Live feel dead.
            greeting = self._live_greeting_response(task)
            if greeting is not None:
                self.after(
                    0,
                    lambda m=greeting: self._complete_direct_command(m, True),
                )
                return

            # ── SCREEN QUESTION (vision, never the OS executor) ───────────
            # "¿Qué ves en mi pantalla?" is answered from a fresh capture.
            # Routing it to the reasoning agent made it invent executor
            # tags, show technical errors and poke Chrome instead.
            if self._is_screen_question(task):
                answer = self._describe_screen(task)
                self.after(
                    0,
                    lambda m=answer: self._complete_direct_command(m, True),
                )
                return

            # ── LOCAL SEMANTIC ROUTER (zero network latency) ──────────────
            # Short desktop commands are understood deterministically.  In
            # particular, a bare "abre" asks for clarification instead of
            # guessing Word, and "abre YouTube en Chrome" receives the real
            # YouTube URL on Chrome's command line (never a Bing search).
            command = self._detect_direct_command(task)
            if command is not None:
                if command.kind == "clarify":
                    self.after(
                        0,
                        lambda m=command.message: self._complete_direct_command(
                            m, True
                        ),
                    )
                    return

                # Start the natural voice before the desktop action finishes.
                # Chrome can take a few hundred milliseconds to come forward;
                # the user should hear "Abriendo YouTube en Chrome" as soon as
                # the command is understood, not after every window settles.
                preview = ""
                if command.kind == "open_url":
                    preview = command.message
                elif command.kind == "open_app" and command.label:
                    preview = f"Abriendo {command.label}."
                pre_spoken = False
                if preview and self._live_vision_active:
                    try:
                        self.after(
                            0,
                            lambda m=preview: self._speak_live_response(m),
                        )
                        pre_spoken = True
                    except Exception:
                        pre_spoken = False

                ok = False
                message = "No pude completar esa acción. Intenta de nuevo."
                if command.kind == "open_url":
                    try:
                        from _orunex_libs.os_executor import open_url

                        result = str(open_url(command.url, command.browser))
                    except Exception as exc:
                        result = f"[ERR] {exc}"
                    if result.startswith("[OK]"):
                        ok = True
                        message = command.message
                    elif result.startswith("[WARN]"):
                        ok = True
                        if command.browser:
                            from _orunex_libs.intent_router import BROWSER_LABELS

                            browser_name = BROWSER_LABELS.get(
                                command.browser, command.browser.title()
                            )
                            message = (
                                f"No encontré {browser_name}; abrí "
                                f"{command.label} en tu navegador predeterminado."
                            )
                        else:
                            message = command.message
                    else:
                        message = f"No pude abrir {command.label}. Intenta de nuevo."
                elif command.kind == "open_app":
                    try:
                        if command.app == "browser":
                            from _orunex_libs.os_executor import open_url

                            result = str(open_url("https://www.google.com"))
                        elif command.app in {
                            "chrome", "edge", "firefox", "brave", "opera", "vivaldi"
                        }:
                            from _orunex_libs.os_executor import open_url

                            result = str(open_url("https://www.google.com", command.app))
                        else:
                            from _orunex_libs.os_executor import smart_launch

                            result = str(smart_launch(command.app))
                    except Exception as exc:
                        result = f"[ERR] {exc}"
                    if result.startswith("[OK]"):
                        ok = True
                        message = f"Abriendo {command.label}."
                    elif result.startswith("[WARN]"):
                        message = f"No encontré {command.label} instalado."
                    else:
                        message = f"No pude abrir {command.label}. Intenta de nuevo."

                if ok:
                    self._command_language = "es" if any(
                        token in str(task).lower()
                        for token in ("abre", "abrir", "por favor", "chrome", "youtube")
                    ) else "en"
                    self._remember_direct_command(command, ok=True)
                self.after(
                    0,
                    lambda m=message, good=ok, said=pre_spoken: self._complete_direct_command(
                        m, good, speak=not (said and good)
                    ),
                )
                return

            # ── DETERMINISTIC ARTIFACT PATH ───────────────────────────────
            # Explicit file requests work even when the local model is not
            # available.  The result is a real file plus a clickable card.
            try:
                artifact = artifact_studio.generate_from_request(task)
            except Exception as artifact_error:
                artifact = None
                self.after(
                    0,
                    lambda e=str(artifact_error): self.write_real_time(
                        f"Artifact Studio error: {e}", "error"
                    ),
                )
            if artifact:
                self.after(
                    0, lambda a=artifact: self._complete_artifact_task(a)
                )
                return

            # ── DIRECT VS CODE PATH ────────────────────────────────────────
            if is_programmer:
                try:
                    from integrations import vscode_integration
                    from _orunex_libs import programmer_studio

                    workspace = vscode_integration.CREATION_CHAMBER
                    connection = vscode_integration.connect(workspace=workspace)
                    wait_for_chip = max(
                        0.0,
                        getattr(self, "_vscode_min_visible_until", 0.0)
                        - time.time(),
                    )
                    if wait_for_chip:
                        time.sleep(wait_for_chip)
                    self.after(0, lambda: self._hide_vscode_connecting(show_thinking=True))

                    # Without the local model, create a clean runnable
                    # scaffold, open it in VS Code and run its tests.  With
                    # the model available, the normal agent continues below.
                    if not _brain_available():
                        info = programmer_studio.scaffold(
                            task,
                            root=os.path.join(workspace, "projects"),
                        )
                        if connection.get("ok"):
                            vscode_integration.open_file(info["entry"], 1)
                        else:
                            vscode_integration.open_folder(info["folder"])
                        tests = vscode_integration.run_tests(
                            cwd=info["folder"],
                            command=info["testCommand"],
                        )
                        if not tests.get("ok"):
                            tests = self._run_command_fallback(
                                info["testCommand"], info["folder"]
                            )
                        self.after(
                            0,
                            lambda i=info, c=connection, t=tests: self._complete_programmer_task(i, c, t),
                        )
                        return
                except Exception as programmer_error:
                    self.after(
                        0,
                        lambda e=str(programmer_error): self.append_history(
                            f"Programmer mode could not finish the VS Code setup: {e}",
                            tag="error",
                            color=THEME["red"],
                        ),
                    )
                    self.after(0, lambda: self._hide_vscode_connecting(show_thinking=True))
                    # Continue into the normal agent so the request is not
                    # silently lost when VS Code is unavailable.

            # ── FAST-PATH: simple conversational queries skip full agent overhead
            _task_lower = task.lower().strip()
            _fast_triggers = ["hola", "gracias", "ok", "listo", "bien", "hello",
                              "quien eres", "que eres", "como te llamas"]
            if _task_lower in _fast_triggers or len(_task_lower) < 20 and not any(
                k in _task_lower for k in ["crea", "haz", "genera", "abre", "abrir", "open", "busca",
                "make", "cmd", "run", "video", "excel", "pdf", "ppt"]
            ):
                # Skip all routing overhead — go straight to cerebro fast path
                import agents.cerebro as _cerebro  # type: ignore
                _fast_result = _cerebro.run(task, self.user_name, agent_mode="natural")
                _fast_result = _fast_result.replace("[Cerebro]", "").replace("[Orunex]", "").replace("[CEREBRO]", "").strip()
                self.is_processing = True
                # Voice-first in Live: queue the spoken reply ahead of the
                # text bubble so the two feel simultaneous.
                self.after(
                    0,
                    lambda r=_fast_result: self._speak_live_response(r),
                )
                self.after(0, lambda r=_fast_result: self.append_history(r, tag="Cerebro", color=AGENTS_INFO["Cerebro"]["color"]))
                self.after(200, lambda: self.write_real_time("Done.", "success"))
                self.is_processing = False
                self.execution_status = "IDLE"
                self.after(0, self.stop_screen_glow)
                self.after(0, lambda: self.update_action_buttons(show=False))
                return

            self.is_processing = True
            # ── THINKING LOGS: visible step-by-step progress ──────────────────
            self.after(0, lambda: self.write_real_time("Thinking...", "info"))
            try:
                # V32 Smart Excel Context Injection
                if hasattr(self, 'current_image_path') and self.current_image_path:
                    p = self.current_image_path.lower()
                    if p.endswith(".xlsx") or p.endswith(".xls"):
                         task = f"{task} [FILE_ATTACHED: {self.current_image_path}]"
                if self.execution_status == "CANCELLED": raise InterruptedError()
                self.execution_flag.wait()
                
                has_img = hasattr(self, 'current_image_path') and self.current_image_path is not None
                
                self.write_real_time("Thinking...", "info")
                suggested_agent = decide_agent(task, has_image=has_img)
                
                chosen_agent_name = self.current_agent
                
                # Phase 114: Zenith Universal Routing
                if suggested_agent in ["Cerebro"] and chosen_agent_name == "Agente":
                    chosen_agent_name = "Cerebro"
                elif suggested_agent in ["Voz", "Vision"] and chosen_agent_name == "Agente":
                    chosen_agent_name = suggested_agent
                    self.write_real_time(f"Switching to specialized module: {chosen_agent_name}", "info")
                elif suggested_agent != chosen_agent_name:
                    self.write_real_time(f"Suggested module: {suggested_agent} — running with: {chosen_agent_name}", "warn")

                if chosen_agent_name in INTERNAL_AGENTS:
                    agent_name = chosen_agent_name
                    agent_data = INTERNAL_AGENTS[chosen_agent_name]
                else:
                    # Phase 74: All external agents consolidate into Cerebro Central
                    agent_data = AGENTS_INFO["Cerebro"]
                    chosen_agent_name = "Cerebro"
                
                self.write_real_time("Thinking...", "info")

                if self.execution_status == "CANCELLED": raise InterruptedError()
                self.execution_flag.wait()

                self.after(0, lambda: self.write_real_time("Thinking...", "info"))
                time.sleep(0.1)
                import os as _os
                # V50.0: Use config-driven retries (default 3)
                _cfg_retries = self.config.get("max_retries", 3)
                max_retries = _cfg_retries if _os.environ.get("ORUNEX_AUTO_HEAL", "1") == "1" else 1

                swarm_val = 1
                try:
                    swarm_val = int(self.swarm_var.get().split()[-1])
                except Exception:
                    pass

                def execute_single_agent(agent_name, prompt):
                    """Run an agent with optional self-healing retries."""
                    nonlocal agent_data
                    if not agent_data:
                        agent_name = "Cerebro"
                        agent_data = AGENTS_INFO["Cerebro"]
                    
                    curr_attempt = 1
                    curr_task = prompt
                    res = ""
                    while curr_attempt <= max_retries:
                        if agent_name in ["Vision", "Vision"]:
                            # Transitioning to Orunex Vision (R1 text description)
                            res = "Orunex Vision: this capability is being integrated into the core engine."
                            break 
                        elif agent_name == "Cerebro":
                            res = agent_data["run"](
                                curr_task,
                                self.user_name,
                                getattr(self, 'current_image_path', None)
                                if hasattr(self, 'current_image_path') else None,
                                agent_mode="os",
                                mode=resolved_mode,
                            ) # type: ignore
                            if "Error:" in res and "[ SISTEMA ORUNEX: ACCIONES AUTONOMAS]" in res and max_retries > 1:
                                self.write_real_time(f"Supervisor: execution error detected. Attempting recovery ({curr_attempt}/{max_retries})...", "error")
                                curr_task = f"The command failed with this error:\n{res}\n\nFix the command or script and try again another way."
                                curr_attempt += 1 # type: ignore
                                continue
                            else:
                                break
                        else:
                            res = agent_data["run"](curr_task, self.user_name) # type: ignore
                            break
                    if curr_attempt > max_retries and max_retries > 1:
                        self.write_real_time("Supervisor: persistent critical error. Recovery stopped.", "error")
                    return res
                
                if swarm_val > 1 and chosen_agent_name not in ["Cerebro"]:
                    self.write_real_time(f"Starting Swarm with {swarm_val} concurrent workers...", "warn")
                    import concurrent.futures
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=swarm_val) as executor:
                        futures = [executor.submit(execute_single_agent, chosen_agent_name, task) for _ in range(swarm_val)] # type: ignore
 # type: ignore
                        results = [f.result() for f in concurrent.futures.as_completed(futures)]
                        
                    self.write_real_time(f"Swarm complete. Synthesizing {swarm_val} perspectives...", "info")
                    synth_prompt = f"[MANDATORY SWARM SYNTHESIS]\nYou are the Orunex master agent. Analyze these {swarm_val} responses generated in parallel for the original request ('{task[:100]}'). Merge them into ONE definitive, functional response. Keep the best code and discard anything broken:\n\n"
                    for idx, res in enumerate(results):
                        synth_prompt += f"--- PERSPECTIVA CLON {idx+1} ---\n{res}\n\n"
                        
                    orig_retries = max_retries
                    max_retries = 1  # No iterar errores al sintetizar
                    result = execute_single_agent(chosen_agent_name, synth_prompt)
                    max_retries = orig_retries
                else:
                    result = execute_single_agent(chosen_agent_name, task)

                if not result or result.strip() == "":
                    result = "I could not generate a readable response. Please try the request again."

                if has_img and hasattr(self, 'current_image_path'):
                    setattr(self, 'current_image_path', None)
                
                # Polling Check 3 (pre-print)
                if self.execution_status == "CANCELLED": raise InterruptedError()
                self.execution_flag.wait()

                # Record Memory
                import os as _os
                if _os.environ.get("ORUNEX_MEM_RECORD", "1") == "1":
                    database.save_memory(chosen_agent_name, task, result)
                    if _os.environ.get("ORUNEX_FAISS_RECORD", "1") == "1":
                        try:
                            from _orunex_libs import faiss_memory
                            faiss_memory.remember_task_async(
                                chosen_agent_name, task, result
                            )
                        except Exception as _mem_exc:
                            print(f"[FAISS] Task memory unavailable: {_mem_exc}")

                def on_success():
                    self._last_task_error = False
                    self.write_real_time("Task completed successfully.", "success")

                    # Optional screenshot, removed immediately after delivery.
                    if self.config.get("send_screenshot", False):
                        try:
                            from _orunex_libs.os_executor import take_screenshot
                            import _orunex_libs.simplex_bridge as sx
                            import os as _os

                            path = take_screenshot()
                            if path and _os.path.exists(path):
                                sx.get_bridge().send_file(path, caption=f"Task completed: {task[:50]}")
                                _os.remove(path)
                        except Exception as e:
                            print(f"Screenshot error: {e}")

                    import _orunex_libs.simplex_bridge as sx
                    if sx.is_connected():
                        sx_cfg = sx.load_config()
                        if sx_cfg.get("notify_on_complete", True):
                            sx.notify("Task completed successfully.", "success")
                            if sx_cfg.get("send_screenshot_on_complete", False):
                                self.after(500, lambda: sx.get_bridge().send_screenshot())
                    
                    # Voice output for Live mode is handled centrally by
                    # _speak_live_response() after the visible result is known.

                    # Phase 115: Sovereign Bridge (EXECUTION) — run BEFORE showing result
                    from _orunex_libs.os_executor import intercept_and_execute # type: ignore
                    exec_results = intercept_and_execute(result)
                    
                    # V46.0: Show executor output to the user (not just raw tags)
                    # Extract human-readable lines from exec_results and display them
                    def _format_exec_output(raw: str) -> str:
                        """Converts executor log into a clean, human-readable summary."""
                        import re as _re
                        lines = raw.strip().split("\n")
                        # Filter to meaningful output lines only
                        good = []
                        for ln in lines:
                            ln = ln.strip()
                            if not ln: continue
                            # Skip the raw tag lines (the agent's instruction)
                            if ln.startswith("[MAKE_") or ln.startswith("[CMD:") or ln.startswith("[FILE:") or ln.startswith("[MKDIR:"):
                                continue
                            # Skip internal header/footer
                            if ln == "[ SISTEMA ORUNEX: ACCIONES AUTONOMAS]" or ln == "[+] Tarea ejecutada con éxito." or "Tarea ejecutada con" in ln or ln == "[+] Task executed successfully.":
                                continue
                            # Keep the rest
                            good.append(ln)
                        return "\n".join(good).strip()
                    
                    exec_display = _format_exec_output(exec_results)
                    
                    # Determine what to show: if the result is just one or
                    # more raw machine tags, show the clean executor output
                    # instead.
                    _remaining_text = re.sub(
                        r"\[[^\]]+\]", "", result
                    ).strip()
                    result_is_just_tag = bool(result.strip()) and not _remaining_text and bool(
                        re.search(r"\[[A-Z][^\]]*\]", result)
                    )
                    
                    # ── CLEAN DISPLAY: no [Cerebro] / [AgentName] prefix in bubbles ──
                    if result_is_just_tag:
                        # Don't show raw machine tag — show executor output or friendly status
                        display_text = exec_display if exec_display else "Action completed."
                        # Strip any leftover agent-name tags from exec output
                        display_text = display_text.replace("[Cerebro]", "").replace("[CEREBRO]", "").replace("[Orunex]", "").strip()
                        speech_text = display_text
                        # Voice-first in Live: synthesis starts before the
                        # bubble is painted, not after it.
                        self._speak_live_response(speech_text)
                        self.append_history(display_text, tag="Cerebro", color=agent_data["color"])
                    else:
                        # Show clean agent response WITHOUT the [AgentName] prefix
                        clean_result = result.replace("[Cerebro]", "").replace("[CEREBRO]", "").replace("[Orunex]", "").replace(f"[{chosen_agent_name}]", "").strip()
                        speech_text = clean_result
                        self._speak_live_response(speech_text)
                        self.append_history(clean_result, tag=chosen_agent_name, color=agent_data["color"])
                        # Show executor output if it adds meaningful information
                        if exec_display and exec_display != result.strip():
                            clean_exec = exec_display.replace("[Cerebro]", "").replace("[Orunex]", "").strip()
                            self.append_history(clean_exec, tag="sys", color=THEME["success"])
                    
                    has_err = any(
                        "❌" in entry or "Error" in entry or "[ERR]" in entry
                        for entry in [exec_results]
                    )
                    if not has_err:
                        self.write_real_time("Task completed successfully.", "success")
                        self._set_stream_status("Ready", "blue")
                        try:
                            is_remote = os.environ.get("ORUNEX_REMOTE_TASK", "false").lower() == "true"
                            if is_remote:
                                import _orunex_libs.simplex_bridge as sx
                                sx.get_bridge().send_pulse("Task completed")
                        except Exception:
                            pass
                    else:
                        self._last_task_error = True
                        self.write_real_time("Task finished with warnings.", "warning")
                        self._set_stream_status("Needs attention", "red")
                    
                        # OS Mode Prompt
                        if self.agent_mode == "natural" and "[EXE]" in result:
                            import tkinter.messagebox as mb
                            if mb.askyesno(
                                "OS Agent suggestion",
                                "This task may need to modify files on your system.\n\n"
                                "Enable OS Agent mode for the next message?",
                            ):
                                self.agent_mode = "os"

                self.after(0, on_success)
                
            except InterruptedError:
                pass # Already handled in UI message
            except Exception as e:
                import traceback
                with open("orunex_crash.log", "a", encoding="utf-8") as f_crash:
                    f_crash.write(f"\n--- CRASH {time.ctime()} ---\n{traceback.format_exc()}\n---\n")
                err_msg = str(e)
                def on_error(msg=err_msg):
                    self._last_task_error = True
                    self.write_real_time(f"Error: {msg}", "error")
                    self.append_history(
                        f"Core failure: {msg}. Please try again.\n\n",
                        tag="error",
                        color=THEME["red"],
                    )
                    try:
                        import _orunex_libs.simplex_bridge as simplex  # type: ignore
                        simplex.notify(f"Error: {msg}", "error")
                    except Exception:
                        pass
                self.after(0, on_error)
            finally:
                self.after(0, self._stop_task_glow)
                self.is_processing = False
                if self.execution_status != "CANCELLED":
                    self.execution_status = "IDLE"
                self.after(0, lambda: self.update_action_buttons(show=False))

        import threading
        threading.Thread(target=task_thread, daemon=True).start()

    def on_enter(self, event):
        self.send_task()


    # --- Phase 35: Callbacks y Servicios en Background ---
    def ui_confirm_dangerous_action(self, text: str) -> bool:
        """Blocking confirmation for destructive actions (delete, scripts)."""
        return messagebox.askyesno("Security confirmation", text)

    def handle_simplex_command(self, command_text: str):
        """Callback invoked by simplex_bridge when a remote command arrives."""
        if command_text == "SIMPLEX_KILL_SWITCH":
            self.after(0, self.cancel_execution)
            return "Stopped."
        elif command_text == "SIMPLEX_HEARTBEAT_ON":
            from _orunex_libs.heartbeat import start  # type: ignore
            start()
            return "Enabled."
        elif command_text == "SIMPLEX_HEARTBEAT_OFF":
            from _orunex_libs.heartbeat import stop  # type: ignore
            stop()
            return "Disabled."
        elif command_text == "SIMPLEX_CONNECTED_EVENT":
            # Keep startup silent: the bridge page reflects the real state.
            self.after(0, self._refresh_simplex_page)
            return "Systems synchronized."
        elif command_text == "SIMPLEX_DISCONNECTED_EVENT":
            self.after(0, self._refresh_simplex_page)
            return "Disconnected."
        elif command_text.startswith("SIMPLEX_CALL:") or command_text.startswith("SIMPLEX_VOICE:"):
            task = command_text.split(":", 1)[1].strip()
            return self._process_remote_voice_task(task)
        elif command_text.startswith("SIMPLEX_TASK:"):
            task = command_text.split(":", 1)[1].strip()

            voice_triggers = [
                "por voz", "en voz alta", "hablame", "habla", "usa la voz",
                "llamada", "llamame", "dime", "oralmente",
                "by voice", "out loud", "call me", "voice call",
            ]
            if any(trigger in task.lower() for trigger in voice_triggers):
                return self._process_remote_voice_task(task)

            if task.lower() in ["!si", "si", "confirmar", "aprobar", "yes", "approve"]:
                return self._process_reconstruct_approval()
            return self._process_remote_task(task)

    def _process_reconstruct_approval(self) -> str:
        """Phase 92: Busca parches (.patch) y los aplica."""
        import glob
        patches = glob.glob(os.path.join(os.getcwd(), "**", "*.patch"), recursive=True)
        if not patches:
            return "There are no pending evolution patches to approve."

        results = []
        for p in patches:
            target_file = p.replace(".patch", "")
            try:
                with open(p, "r", encoding="utf-8") as f:
                    new_content = f.read()
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                os.remove(p)
                results.append(f"[DNA] {os.path.basename(target_file)} updated successfully.")
            except Exception as e:
                results.append(f"[ERR] Could not apply patch to {target_file}: {e}")
        
        final_msg = "\n".join(results)
        self.after(0, lambda: self.append_history(final_msg, "success"))
        return final_msg

    def _process_remote_voice_task(self, task: str) -> str:
        """Handler for voice calls arriving through Simplex."""
        self.after(0, lambda: self.append_history(f"Remote voice call: {task}", "info"))
        import threading
        def remote_voice_thread():
            from agents.cerebro import run as cerebro_run # type: ignore
            import _orunex_libs.simplex_bridge as simplex # type: ignore
            try:
                # 1. Background Execution
                res = cerebro_run(task, "Remote_Call", agent_mode="os")
                
                # Phase 115: Sovereign Bridge (EXECUTION)
                from _orunex_libs.os_executor import intercept_and_execute # type: ignore
                intercept_and_execute(res)
                
                self.after(0, lambda: self.append_history(f"OS action completed: {str(res)[:100]}...", "success"))
                
                # Phase 114: Orunex Universal Synthesis
                from agents.universal import voice_synthesis as orunex_voice # type: ignore
                verbal_res = orunex_voice(task, self.user_name, raw_machine_output=res)
   
                # 3. PC Physical Voice Output (Voice configured for Orunex)
                import subprocess, re
                
                # Filter markdown and tags for human-like speech
                clean_speech = verbal_res
                clean_speech = re.sub(r'```.*?```', '', clean_speech, flags=re.DOTALL) # No code blocks
                clean_speech = re.sub(r'\[.*?\]', '', clean_speech) # No tags [CMD:]
                clean_speech = re.sub(r'[*_#`]', '', clean_speech) # No markdown symbols
                safe_speech = clean_speech.replace('"', '').replace("'", "").replace('\n', ' ').strip()
                
                if not safe_speech: return # V37.3: Silencio total si no hay mensaje inteligente
                script = f'''import pyttsx3
import sys
try:
    engine = pyttsx3.init()
    engine.setProperty('rate', 165) # Human-like cadence
    for v in engine.getProperty('voices'):
        if 'spanish' in v.name.lower() or 'espanol' in v.name.lower():
            engine.setProperty('voice', v.id)
            break
    engine.say("{safe_speech}")
    engine.runAndWait()
except:
    sys.exit(0)
'''
                subprocess.run(["python", "-c", script], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                
                # 4. Notify Simplex
                simplex.notify(f"Voice response: {verbal_res}", "success")

            except Exception as e:
                import _orunex_libs.simplex_bridge as simplex  # type: ignore
                simplex.notify(f"Voice error: {e}", "error")

        threading.Thread(target=remote_voice_thread, daemon=True).start()
        return "Connecting the voice call..."

    def run_silent_agent_task(self, task: str) -> str:
        """Run a task in the background without blocking the desktop UI."""
        import threading
        def _bg():
            from agents.cerebro import run as cerebro_run  # type: ignore
            try:
                cerebro_run(task, "Background_Auto", agent_mode="os")
                self.write_real_time("Background task completed.", "success")
            except Exception as e:
                print(f"Background task error: {e}")

        threading.Thread(target=_bg, daemon=True).start()
        return "Background task started."

    # 
    # CONFIG PANEL v2 (Phase 49)  Professional Settings Panel
    # 
    def _build_settings_view(self):
        """In-window settings page (no secondary window)."""
        page = ctk.CTkFrame(
            self.view_host, fg_color=THEME["bg"], corner_radius=0
        )
        self._settings_view = page

        scroll = ctk.CTkScrollableFrame(
            page,
            fg_color=THEME["bg"],
            corner_radius=0,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(18, 24))

        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            head,
            text="Profile, engine behavior and knowledge sources for Orunex.",
            font=("Segoe UI", 12),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(anchor="w")

        def card(title, subtitle=None):
            outer = ctk.CTkFrame(
                scroll,
                fg_color=THEME["surface"],
                corner_radius=16,
                border_width=1,
                border_color=THEME["border"],
            )
            outer.pack(fill="x", pady=(0, 12))
            inner = ctk.CTkFrame(outer, fg_color="transparent")
            inner.pack(fill="x", padx=22, pady=18)
            ctk.CTkLabel(
                inner,
                text=title,
                font=("Segoe UI", 14, "bold"),
                text_color=THEME["text"],
                anchor="w",
            ).pack(fill="x")
            if subtitle:
                ctk.CTkLabel(
                    inner,
                    text=subtitle,
                    font=("Segoe UI", 11),
                    text_color=THEME["text_dim"],
                    anchor="w",
                ).pack(fill="x", pady=(2, 10))
            else:
                ctk.CTkFrame(inner, height=8, fg_color="transparent").pack()
            return inner

        def field_row(parent, label_text, widget_fn):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(
                row,
                text=label_text,
                font=("Segoe UI", 11),
                text_color=THEME["text_dim"],
                width=170,
                anchor="w",
            ).pack(side="left")
            widget = widget_fn(row)
            if widget is not None:
                widget.pack(side="left", fill="x", expand=True)
            return row

        # Profile
        profile = card("Profile")
        self.name_entry_var = ctk.StringVar(value=self.user_name)
        field_row(
            profile,
            "Display name",
            lambda parent: ctk.CTkEntry(
                parent,
                textvariable=self.name_entry_var,
                height=34,
                fg_color=THEME["surface_soft"],
                border_color=THEME["border"],
                text_color=THEME["text"],
            ),
        )
        ctk.CTkButton(
            profile,
            text="Manage saved memory",
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 10),
            command=self.open_gemini_memory_manager,
        ).pack(anchor="w", pady=(8, 0))

        # Appearance
        appearance = card("Appearance")
        field_row(
            appearance,
            "Theme",
            lambda parent: ctk.CTkLabel(
                parent, text="Light", text_color=THEME["text_dim"], anchor="w"
            ),
        )
        field_row(
            appearance,
            "Language",
            lambda parent: ctk.CTkLabel(
                parent, text="English", text_color=THEME["text_dim"], anchor="w"
            ),
        )
        self.scale_var = ctk.DoubleVar(value=float(self.config.get("ui_scale", 1.0)))
        self.settings_scale_lbl = ctk.CTkLabel(
            appearance,
            text=f"Interface scale: {int(self.scale_var.get() * 100)}%",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
        )
        self.settings_scale_lbl.pack(fill="x", pady=(8, 0))
        ctk.CTkSlider(
            appearance,
            from_=0.8,
            to=1.4,
            variable=self.scale_var,
            button_color=THEME["blue"],
            progress_color=THEME["blue"],
            command=lambda v: self.settings_scale_lbl.configure(
                text=f"Interface scale: {int(float(v) * 100)}%"
            ),
        ).pack(fill="x", pady=(2, 4))

        # Engine
        engine = card(
            "Engine",
            "How Orunex executes and remembers tasks on this computer.",
        )
        self.auto_heal_var = ctk.StringVar(value=os.environ.get("ORUNEX_AUTO_HEAL", "1"))
        self.mem_record_var = ctk.StringVar(value=os.environ.get("ORUNEX_MEM_RECORD", "1"))
        self.glow_var = ctk.BooleanVar(value=self.config.get("screen_glow", True))

        for text, variable in (
            ("Automatic recovery on failure", self.auto_heal_var),
            ("Save task memory automatically", self.mem_record_var),
            ("Screen glow while working", self.glow_var),
        ):
            ctk.CTkSwitch(
                engine,
                text=text,
                variable=variable,
                onvalue="1",
                offvalue="0",
                progress_color=THEME["blue"],
                text_color=THEME["text"],
                font=("Segoe UI", 11),
            ).pack(anchor="w", pady=5)

        self.retries_var = ctk.IntVar(value=int(self.config.get("max_retries", 3)))
        retries_lbl = ctk.CTkLabel(
            engine,
            text=f"Maximum retries: {self.retries_var.get()}",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
        )
        retries_lbl.pack(fill="x", pady=(10, 0))
        ctk.CTkSlider(
            engine,
            from_=1,
            to=5,
            number_of_steps=4,
            variable=self.retries_var,
            button_color=THEME["blue"],
            progress_color=THEME["blue"],
            command=lambda v: retries_lbl.configure(
                text=f"Maximum retries: {int(float(v))}"
            ),
        ).pack(fill="x", pady=(0, 4))

        self.num_ctx_var = ctk.DoubleVar(value=int(self.config.get("ctx_len", 8192)))
        ctx_lbl = ctk.CTkLabel(
            engine,
            text=f"Context window: {int(self.num_ctx_var.get())} tokens",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
        )
        ctx_lbl.pack(fill="x", pady=(10, 0))
        ctk.CTkSlider(
            engine,
            from_=2048,
            to=128000,
            variable=self.num_ctx_var,
            button_color=THEME["blue"],
            progress_color=THEME["blue"],
            command=lambda v: ctx_lbl.configure(
                text=f"Context window: {int(float(v))} tokens"
            ),
        ).pack(fill="x", pady=(0, 4))

        # Knowledge Hub
        hub = card(
            "Knowledge Hub",
            "Upload structured data or documentation to extend the local knowledge base.",
        )

        def pick_file(fmt):
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title=f"Upload {fmt}", filetypes=[(fmt, f"*.{fmt.lower()}")]
            )
            if not path:
                return
            self.write_real_time("Thinking...", "info")
            try:
                from _orunex_libs import knowledge_processor
                success, msg = knowledge_processor.ingest_file(path)
                color = THEME["blue"] if success else THEME["error"]
                self.settings_feedback.configure(text=msg, text_color=color)
                self.write_real_time(
                    "Knowledge file ready." if success else f"Knowledge file error: {msg}",
                    "success" if success else "error",
                )
            except Exception as exc:
                self.settings_feedback.configure(
                    text=f"Knowledge Hub error: {exc}", text_color=THEME["error"]
                )
                self.write_real_time(f"Knowledge file error: {exc}", "error")

        hub_actions = ctk.CTkFrame(hub, fg_color="transparent")
        hub_actions.pack(fill="x", pady=(4, 0))
        for label, fmt in (("Upload JSON", "JSON"), ("Upload PDF", "PDF")):
            ctk.CTkButton(
                hub_actions,
                text=label,
                width=112,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                border_width=1,
                border_color=THEME["border"],
                text_color=THEME["text_dim"],
                hover_color=THEME["surface_muted"],
                font=("Segoe UI", 10),
                command=lambda f=fmt: pick_file(f),
            ).pack(side="left", padx=(0, 8))

        # Connection shortcut
        connection = card("Connections")
        connection_row = ctk.CTkFrame(connection, fg_color="transparent")
        connection_row.pack(fill="x")
        ctk.CTkLabel(
            connection_row,
            text="Simplex Bridge pairs Orunex with your phone for remote commands.",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=520,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            connection_row,
            text="Open Simplex Bridge",
            width=150,
            height=32,
            corner_radius=8,
            fg_color=THEME["blue_soft"],
            text_color=THEME["blue"],
            hover_color=THEME["blue_border"],
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.show_view("simplex"),
        ).pack(side="right", padx=(10, 0))

        # Direct VS Code bridge
        vscode_row = ctk.CTkFrame(connection, fg_color="transparent")
        vscode_row.pack(fill="x", pady=(14, 0))
        vscode_copy = ctk.CTkFrame(vscode_row, fg_color="transparent")
        vscode_copy.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            vscode_copy,
            text="VS Code Bridge",
            font=("Segoe UI", 11, "bold"),
            text_color=THEME["text"],
            anchor="w",
        ).pack(anchor="w")
        self.vscode_status_lbl = ctk.CTkLabel(
            vscode_copy,
            text="Checking local bridge...",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.vscode_status_lbl.pack(anchor="w", pady=(1, 0))
        ctk.CTkButton(
            vscode_row,
            text="Connect VS Code",
            width=132,
            height=32,
            corner_radius=8,
            fg_color=THEME["blue_soft"],
            text_color=THEME["blue"],
            hover_color=THEME["blue_border"],
            font=("Segoe UI", 10, "bold"),
            command=self.connect_vscode_from_settings,
        ).pack(side="right", padx=(10, 0))
        self.after(450, self._refresh_vscode_status)

        # Save
        actions = ctk.CTkFrame(scroll, fg_color="transparent")
        actions.pack(fill="x", pady=(2, 10))
        ctk.CTkButton(
            actions,
            text="Apply & save",
            width=140,
            height=38,
            corner_radius=9,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color=THEME["accent_hover"],
            font=("Segoe UI", 11, "bold"),
            command=lambda: self._apply_config_v2(
                new_name=self.name_entry_var.get(), scale_val=self.scale_var.get()
            ),
        ).pack(side="left")
        self.settings_feedback = ctk.CTkLabel(
            actions,
            text="",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            anchor="w",
        )
        self.settings_feedback.pack(side="left", padx=(12, 0))

    def _sync_settings_widgets(self):
        try:
            self.name_entry_var.set(self.user_name)
            self.settings_scale_lbl.configure(
                text=f"Interface scale: {int(self.scale_var.get() * 100)}%"
            )
        except Exception:
            pass
        self.after(250, self._refresh_vscode_status)

    def _apply_vscode_status(self, status):
        label = getattr(self, "vscode_status_lbl", None)
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except Exception:
            return
        ok = bool(status.get("ok"))
        if ok:
            workspace = (status.get("workspaceFolders") or [""])[0]
            port = status.get("port", "")
            text = "Connected"
            if port:
                text += f" on 127.0.0.1:{port}"
            if workspace:
                text += f" · {os.path.basename(workspace)}"
            label.configure(text=text, text_color="#067647")
        else:
            message = status.get("error") or status.get("message") or "Not connected"
            label.configure(
                text=f"{message}. Click Connect VS Code to launch the local bridge.",
                text_color=THEME["text_dim"],
            )

    def _refresh_vscode_status(self):
        """Read the bridge status without blocking the Tk event loop."""
        label = getattr(self, "vscode_status_lbl", None)
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except Exception:
            return

        def worker():
            try:
                from integrations import vscode_integration

                status = vscode_integration.bridge_status()
            except Exception as exc:
                status = {"ok": False, "error": str(exc)}
            try:
                self.after(0, lambda s=status: self._apply_vscode_status(s))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def connect_vscode_from_settings(self):
        """Launch/open VS Code and connect the local bridge from Settings."""
        label = getattr(self, "vscode_status_lbl", None)
        if label is not None:
            try:
                label.configure(
                    text="Opening VS Code and loading the local bridge...",
                    text_color=THEME["text_dim"],
                )
            except Exception:
                pass

        def worker():
            try:
                from integrations import vscode_integration

                status = vscode_integration.connect(launch=True)
                if status.get("ok"):
                    # Bring the workspace forward once the bridge is healthy.
                    try:
                        vscode_integration.open_folder(
                            status.get("workspace")
                            or vscode_integration.CREATION_CHAMBER
                        )
                    except Exception:
                        pass
            except Exception as exc:
                status = {"ok": False, "error": str(exc)}
            try:
                self.after(0, lambda s=status: self._apply_vscode_status(s))
                if not status.get("ok"):
                    self.after(
                        0,
                        lambda e=status.get("error", "VS Code did not connect"): self.write_real_time(
                            str(e), "error"
                        ),
                    )
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def open_config(self):
        """Compatibility wrapper: open settings as an in-window page."""
        self.show_view("settings")

    def _apply_config_v2(self, window=None, feedback_lbl=None, new_name=None, scale_val=None):
        """Persist settings without closing the current screen."""
        from _orunex_libs import config_manager

        if new_name is None:
            new_name = self.user_name
        if scale_val is None:
            scale_val = float(self.config.get("ui_scale", 1.0))

        self.user_name = new_name.strip() or "User"
        self.config["user_name"] = self.user_name
        self.config["language"] = "en"
        self.config["language_full"] = "English"
        self.config["ui_scale"] = scale_val
        self.config["auto_heal"] = self.auto_heal_var.get() == "1"
        self.config["mem_record"] = self.mem_record_var.get() == "1"
        self.config["screen_glow"] = self.glow_var.get()
        self.config["max_retries"] = int(self.retries_var.get())
        self.config["send_screenshot"] = self._send_screenshot_var.get() == "1"
        self.config["send_remote_screenshot"] = (
            self._send_remote_screenshot_var.get() == "1"
        )
        self.config["ctx_len"] = int(self.num_ctx_var.get())

        config_manager.save_config(self.config)
        ctk.set_appearance_mode("light")
        ctk.set_widget_scaling(scale_val)
        if not self.config.get("screen_glow", True):
            self.stop_screen_glow()

        target = feedback_lbl or getattr(self, "settings_feedback", None)
        if target is not None:
            try:
                target.configure(text="Changes saved.", text_color=THEME["blue"])
            except Exception:
                pass

    def _build_memory_view(self):
        """In-window saved-memory manager opened from Settings."""
        page = ctk.CTkFrame(
            self.view_host, fg_color=THEME["bg"], corner_radius=0
        )
        self._memory_view = page

        scroll = ctk.CTkScrollableFrame(
            page,
            fg_color=THEME["bg"],
            corner_radius=0,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(18, 24))

        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", pady=(0, 14))

        copy = ctk.CTkFrame(head, fg_color="transparent")
        copy.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            copy,
            text="Orunex uses these notes to personalize your workspace.\n"
                 "Remove anything that is no longer relevant.",
            font=("Segoe UI", 12),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
        ).pack(anchor="w")

        ctk.CTkButton(
            head,
            text="Back to settings",
            height=32,
            width=132,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 10),
            command=lambda: self.show_view("settings"),
        ).pack(side="right", padx=(16, 0))

        list_card = ctk.CTkFrame(
            scroll,
            fg_color=THEME["surface"],
            corner_radius=16,
            border_width=1,
            border_color=THEME["border"],
        )
        list_card.pack(fill="x")
        list_inner = ctk.CTkFrame(list_card, fg_color="transparent")
        list_inner.pack(fill="x", padx=12, pady=10)

        def refresh_list():
            from _orunex_libs import long_term_memory as ltm  # type: ignore

            for widget in list_inner.winfo_children():
                widget.destroy()

            try:
                entries = ltm.get_all_memories() or []
            except Exception:
                entries = []

            if not entries:
                ctk.CTkLabel(
                    list_inner,
                    text="No memories saved yet.",
                    text_color=THEME["text_dim"],
                    font=("Segoe UI", 12, "italic"),
                ).pack(pady=40)
                return

            for index, entry in enumerate(entries):
                row = ctk.CTkFrame(
                    list_inner,
                    fg_color=THEME["surface_soft"],
                    corner_radius=8,
                    border_width=1,
                    border_color=THEME["border"],
                )
                row.pack(fill="x", pady=6)

                task_preview = str(
                    entry.get("task", entry)
                    if isinstance(entry, dict)
                    else entry
                )[:300]

                ctk.CTkLabel(
                    row,
                    text=task_preview,
                    font=("Segoe UI", 12),
                    text_color=THEME["text"],
                    anchor="w",
                    justify="left",
                    wraplength=700,
                ).pack(side="left", fill="x", expand=True, padx=12, pady=10)

                def make_delete(idx=index):
                    def do_delete():
                        if messagebox.askyesno(
                            "Forget this memory?",
                            "Orunex will permanently forget this note.\n"
                            "This cannot be undone.",
                        ):
                            try:
                                ltm.delete_memory_by_index(idx)
                            except Exception:
                                pass
                            refresh_list()

                    return do_delete

                ctk.CTkButton(
                    row,
                    text="Forget",
                    width=62,
                    height=30,
                    corner_radius=7,
                    fg_color="transparent",
                    border_width=0,
                    text_color=THEME["error"],
                    hover_color=THEME["red_soft"],
                    font=("Segoe UI", 10),
                    command=make_delete(),
                ).pack(side="right", padx=10)

        self._refresh_memory_page = refresh_list
        refresh_list()

    def open_gemini_memory_manager(self):
        """Compatibility wrapper: open saved memory in the main window."""
        self.show_view("memory")

    def _open_gemini_memory_manager_window(self):
        """Legacy Toplevel implementation retained for compatibility."""
        from _orunex_libs import long_term_memory as ltm  # type: ignore

        win = ctk.CTkToplevel(self)
        win.title("Saved memory")
        fit_window(win, 600, 600)
        win.attributes("-topmost", True)
        win.configure(fg_color=THEME["bg"])

        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(22, 10))

        ctk.CTkLabel(
            header,
            text="Saved memory",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Orunex uses these notes to personalize your workspace.\n"
                 "Remove anything that is no longer relevant.",
            font=("Segoe UI", 12),
            text_color=THEME["text_dim"],
            justify="left",
        ).pack(anchor="w", pady=(5, 0))

        scroll = ctk.CTkScrollableFrame(
            win,
            fg_color=THEME["surface"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(10, 20))

        def refresh_list():
            for widget in scroll.winfo_children():
                widget.destroy()

            try:
                entries = ltm.get_all_memories() or []
            except Exception:
                entries = []

            if not entries:
                ctk.CTkLabel(
                    scroll,
                    text="No memories saved yet.",
                    text_color=THEME["text_dim"],
                    font=("Segoe UI", 12, "italic"),
                ).pack(pady=40)
                return

            for index, entry in enumerate(entries):
                row = ctk.CTkFrame(
                    scroll,
                    fg_color=THEME["surface_soft"],
                    corner_radius=8,
                    border_width=1,
                    border_color=THEME["border"],
                )
                row.pack(fill="x", padx=5, pady=6)

                task_preview = str(
                    entry.get("task", entry) if isinstance(entry, dict) else entry
                )[:300]

                ctk.CTkLabel(
                    row,
                    text=task_preview,
                    font=("Segoe UI", 12),
                    text_color=THEME["text"],
                    anchor="w",
                    justify="left",
                    wraplength=420,
                ).pack(side="left", fill="x", expand=True, padx=12, pady=10)

                def make_delete(idx=index):
                    def do_delete():
                        if messagebox.askyesno(
                            "Forget this memory?",
                            "Orunex will permanently forget this note.\n"
                            "This cannot be undone.",
                        ):
                            try:
                                ltm.delete_memory_by_index(idx)
                            except Exception:
                                pass
                            refresh_list()

                    return do_delete

                ctk.CTkButton(
                    row,
                    text="Forget",
                    width=62,
                    height=30,
                    corner_radius=7,
                    fg_color="transparent",
                    border_width=0,
                    text_color=THEME["error"],
                    hover_color=THEME["red_soft"],
                    font=("Segoe UI", 10),
                    command=make_delete(),
                ).pack(side="right", padx=10)

        refresh_list()

        ctk.CTkButton(
            win,
            text="Done",
            height=40,
            width=130,
            corner_radius=9,
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
            hover_color=THEME["accent_hover"],
            command=win.destroy,
        ).pack(pady=(0, 20))




# --- FIN DE ORUNEX APP ---

# --- INICIO ---
if __name__ == "__main__":
    try:
        app = OrunexApp()
        app.mainloop()
    except Exception as e:
        error_msg = f"FATAL ERROR:\n{traceback.format_exc()}"
        print(error_msg)
        with open("orunex_error.log", "w", encoding="utf-8") as f:
            f.write(error_msg)
        messagebox.showerror(
            "Orunex could not start",
            "Orunex stopped unexpectedly. Check orunex_error.log for details.",
        )
