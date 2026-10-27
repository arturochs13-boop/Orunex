import subprocess
import pyautogui # type: ignore
import time
import os
import tempfile
import re # type: ignore
import threading
import json
import importlib
try: import win32gui, win32con # type: ignore
except: pass

import mss # type: ignore
import base64
from integrations import vscode_integration as vscode # type: ignore
from integrations import social_media as social # type: ignore
from _orunex_libs.ollama_client import call_ollama # type: ignore

import threading
TEMP_DIR = tempfile.mkdtemp(prefix="orunex_")


def _hidden_process_kwargs():
    """Run helper processes without flashing a console window on Windows."""
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
        }
    return {}

# Thread-local flag: set to True inside Copiloto calls to silence Simplex
_copiloto_ctx = threading.local()

# Global UI progress callback (registered by the main app)
_ui_progress_cb = None

def register_ui_progress_callback(cb):
    """Register a callable(msg, mtype) to receive all progress notifications in the UI."""
    global _ui_progress_cb
    _ui_progress_cb = cb

def set_copiloto_context(active: bool = True):
    """Call before running a Copiloto task to suppress Simplex notifications."""
    _copiloto_ctx.active = active

def notify_progress(msg, mtype="info"):
    try:
        print(f"  [ORUNEX PULSE] {msg}")
    except Exception:
        try:
            safe_msg = str(msg).encode('ascii', errors='replace').decode('ascii')
            print(f"  [ORUNEX PULSE] {safe_msg}")
        except Exception:
            pass
    
    # Always call UI callback if registered (local or remote)
    if _ui_progress_cb:
        try:
            _ui_progress_cb(msg, mtype)
        except Exception:
            pass

    # Phase 37.7: Copiloto context check (Silenced)
    if getattr(_copiloto_ctx, 'active', False):
        return

    try:
        from . import simplex_bridge as sx  # type: ignore
        bridge = sx.get_bridge()
        if bridge and bridge.linked:
            # Progress pulses stay UI-only. The Simplex conversation gets one
            # Thinking... before the task and the final answer afterwards.
            bridge.send_pulse(msg)
    except:
        pass


def execute_shell(cmd, cwd=None, return_code=False):
    try:
        work_dir = cwd or TEMP_DIR
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=work_dir,
            timeout=30,
            **_hidden_process_kwargs(),
        )
        output = result.stdout.strip() or result.stderr.strip()
        if return_code:
            return result.returncode, output
        return output
    except Exception as e:
        if return_code:
            return 1, f"Error: {str(e)}"
        return f"Error: {str(e)}"

def open_browser():
    return smart_launch("msedge")


def open_url(url, browser=None):
    """Open a web page in a chosen browser without UI automation.

    ``browser`` accepts chrome/edge/firefox/brave/opera/vivaldi.  When it is
    omitted the OS default browser is used.  Passing the URL on the browser
    command line is what prevents the "search for youtube in Chrome" / Bing
    failure: Chrome receives the real YouTube address directly.
    """
    raw = str(url or "").strip().strip('"').strip("'")
    if not raw:
        return "[ERR] No se recibio una URL."
    if raw.lower() in {"youtube", "youtube.com", "www.youtube.com"}:
        raw = "https://www.youtube.com"
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.IGNORECASE):
        if re.match(r"^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:\/\S*)?$", raw, re.IGNORECASE):
            raw = "https://" + raw
        else:
            return f"[ERR] URL no válida: {raw}"

    requested = str(browser or "").strip().lower()
    aliases = {
        "google chrome": "chrome", "chrome": "chrome", "crome": "chrome",
        "microsoft edge": "edge", "msedge": "edge", "edge": "edge",
        "mozilla firefox": "firefox", "firefox": "firefox",
        "brave browser": "brave", "brave": "brave",
        "opera": "opera", "vivaldi": "vivaldi",
    }
    requested = aliases.get(requested, requested)
    labels = {
        "chrome": "Chrome", "edge": "Edge", "firefox": "Firefox",
        "brave": "Brave", "opera": "Opera", "vivaldi": "Vivaldi",
    }

    def default_open():
        try:
            if os.name == "nt" and hasattr(os, "startfile"):
                os.startfile(raw)  # type: ignore[attr-defined]
            else:
                import webbrowser

                if not webbrowser.open(raw, new=2):
                    return f"[ERR] No se pudo abrir {raw}."
            return f"[OK] Abriendo {raw} en el navegador."
        except Exception as exc:
            return f"[ERR] No se pudo abrir {raw}: {exc}"

    if not requested or requested == "browser":
        return default_open()

    exe = _browser_executable(requested)
    if not exe:
        result = default_open()
        if result.startswith("[OK]"):
            return (
                f"[WARN] No encontré {labels.get(requested, requested)}; "
                f"abriendo {raw} en el navegador predeterminado."
            )
        return result

    try:
        args = [exe]
        if requested == "firefox":
            args.append("-new-window")
        else:
            args.append("--new-window")
        args.append(raw)
        flags = _hidden_process_kwargs()
        subprocess.Popen(args, **flags)
        return f"[OK] Abriendo {raw} en {labels.get(requested, requested)}."
    except Exception as exc:
        result = default_open()
        if result.startswith("[OK]"):
            return (
                f"[WARN] No pude iniciar {labels.get(requested, requested)} "
                f"({exc}); abriendo en el navegador predeterminado."
            )
        return result


def _browser_executable(name):
    """Locate a Chromium/Firefox browser executable without launching it."""
    import shutil

    key = str(name or "").strip().lower()
    paths = {
        "chrome": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
            r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
        ],
        "brave": [
            r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
        "opera": [
            r"%LocalAppData%\Programs\Opera\Launcher.exe",
            r"%ProgramFiles%\Opera\Launcher.exe",
        ],
        "vivaldi": [
            r"%LocalAppData%\Vivaldi\Application\vivaldi.exe",
            r"%ProgramFiles%\Vivaldi\Application\vivaldi.exe",
        ],
    }.get(key, [])
    for candidate in paths:
        candidate = os.path.expandvars(candidate)
        if os.path.exists(candidate):
            return candidate
    return shutil.which(key) or ""


def _split_open_target(value):
    """Parse ``url | browser`` used by deterministic navigation tags."""
    text = str(value or "").strip()
    browser = ""
    if "|" in text:
        text, browser = [part.strip() for part in text.split("|", 1)]
    if browser.lower().startswith("browser="):
        browser = browser.split("=", 1)[1].strip()
    return text, browser

def click_text_ocr(target_text):
    """
    NATIVE OCR CLICKER V28.0
    Scans the screen for the exact text and clicks its geometry.
    """
    try:
        import pytesseract # type: ignore
        import cv2 # type: ignore
        import numpy as np # type: ignore
        
        target = target_text.strip().lower()
        tesseract_path = os.path.abspath(os.path.join(os.getcwd(), "resources", "Tesseract-OCR", "tesseract.exe"))
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
        screen_np = np.array(pyautogui.screenshot()) # type: ignore
        gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        
        for i in range(len(data['text'])): # type: ignore
            if target in str(data['text'][i]).lower() and int(data['conf'][i]) > 30: # type: ignore
                cx = int(data['left'][i]) + int(data['width'][i])//2 # type: ignore
                cy = int(data['top'][i]) + int(data['height'][i])//2 # type: ignore
                pyautogui.moveTo(cx, cy, duration=0.3)
                pyautogui.click()
                return True
    except:
        pass
    return False

def force_activate_app(app_name):
    """
    UNIVERSAL BOOT V26.0 (Total Win Focus)
    Tries to find and launch ANY application with Alt+Tab hardware focus.
    """
    return smart_launch(app_name)

def smart_launch(app_name):
    """
    UNIVERSAL BOOT V26.0 (Total Win Focus)
    Tries to find and launch ANY application safely without triggering OS binary errors.
    """
    if not app_name or not str(app_name).strip():
        return "[ERR] Nombre de app no proporcionado."
        
    raw_name = str(app_name).strip().lower()
    
    # Handle Orunex self-reference safely
    if any(k in raw_name for k in ["orunex", "orunex.exe", "project_orunex", "app_orunex"]):
        try:
            if hasattr(pyautogui, "getWindowsWithTitle"):
                wins = pyautogui.getWindowsWithTitle("Orunex")
                if wins:
                    wins[0].activate()
        except Exception:
            pass
        return "[OK] Orunex ya está abierto y en ejecución."

    # Known safe executable mappings
    SAFE_APPS = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "msedge",
        "msedge": "msedge",
        "microsoft edge": "msedge",
        "firefox": "firefox",
        "code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "notepad": "notepad",
        "bloc de notas": "notepad",
        "calc": "calc",
        "calculadora": "calc",
        "taskmgr": "taskmgr",
        "administrador de tareas": "taskmgr",
        "explorer": "explorer",
        "explorador": "explorer",
        "cmd": "cmd",
        "powershell": "powershell",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt"
    }
    
    target_bin = SAFE_APPS.get(raw_name, raw_name)
    import shutil
    resolved = shutil.which(target_bin)
    
    try:
        if resolved or target_bin in SAFE_APPS.values():
            subprocess.Popen(
                f"start {target_bin}",
                shell=True,
                **_hidden_process_kwargs(),
            )
            time.sleep(1.5)
            total_win_focus(target_bin, "Chrome_WidgetWin_1" if "chrome" in target_bin else None)
            return f"[OK] {app_name} lanzado y enfocado."
        elif os.path.exists(app_name) and app_name.lower().endswith(('.exe', '.bat', '.cmd', '.lnk')):
            os.startfile(app_name)
            return f"[OK] {app_name} abierto."
    except Exception as e:
        return f"[ERR] Error al intentar lanzar {app_name}: {e}"

    # Search via WHERE command safely
    try:
        res = subprocess.run(
            f'where "{target_bin}"',
            shell=True,
            capture_output=True,
            text=True,
            **_hidden_process_kwargs(),
        )
        if res.returncode == 0:
            path = res.stdout.splitlines()[0].strip()
            if os.path.exists(path) and path.lower().endswith(('.exe', '.bat', '.cmd')):
                subprocess.Popen(
                    f'"{path}"',
                    shell=True,
                    **_hidden_process_kwargs(),
                )
                return f"[OK] Ejecutable hallado: {path}"
    except Exception:
        pass
        
    return f"[WARN] No se encontró el ejecutable '{app_name}' en el sistema."

def get_active_window_element_bounds(target_name):
    """
    V52.0 DETERMINISTIC GUI VISION GROUNDING (Win32/UIA)
    Inspects active window elements to return exact (x, y) coordinates for target_name.
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                # Center of active window fallback
                cx = rect.left + w // 2
                cy = rect.top + h // 2
                return (cx, cy)
    except:
        pass
    return None

def visual_click(target_name):
    """
    SOVEREIGN EYE CLICK (Moondream V20.0 / V52.0 Win32 Grounding)
    Finds and clicks a UI element by visual description or UIA bounds.
    """
    # Try deterministic Win32/UIA bounds first
    bounds_coords = get_active_window_element_bounds(target_name)
    if bounds_coords and "centro" in target_name.lower():
        pyautogui.click(bounds_coords[0], bounds_coords[1])
        return f"[OK] Clic UIA Grounding en: {target_name} ({bounds_coords})"

    from . import vision_engine as ve
    coords = ve.get_ui_coordinates(target_name)
    if coords:
        pyautogui.click(coords[0], coords[1])
        return f"[OK] Clic visual en: {target_name} ({coords})"
    return f"[ERR] No se pudo ver {target_name} en pantalla."


def wait_for_ui(target_name, timeout=10):
    """Waits for a UI element to appear visually."""
    start = time.time()
    from . import vision_engine as ve
    while time.time() - start < timeout:
        coords = ve.get_ui_coordinates(target_name)
        if coords: return True
        time.sleep(1)
    return False

def take_screenshot(monitor=1):
    timestamp = int(time.time() * 1000)
    path = os.path.join(TEMP_DIR, f"screen_{monitor}_{timestamp}.png")
    try:
        with mss.mss() as sct:
            if monitor == 0: # All monitors
                # Simple fallback to pyautogui for "all"
                import pyautogui
                img = pyautogui.screenshot()
                img.save(path)
            else:
                m_idx = min(max(1, monitor), len(sct.monitors)-1)
                sct_img = sct.grab(sct.monitors[m_idx])
                import mss.tools
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=path)
        return path
    except Exception as e:
        # Fallback
        import pyautogui
        img = pyautogui.screenshot()
        img.save(path)
        return path

def write_text(text):
    pyautogui.typewrite(text)
    return f"Texto escrito: '{text[:30]}...'"

def press_key(key):
    pyautogui.press(key)
    return f"Tecla '{key}' presionada."

def click_at(x, y):
    pyautogui.click(x, y)
    return f"Clic en ({x}, {y})"

def save_file(filename, content):
    path = os.path.join(TEMP_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Archivo guardado: {path}"

def visual_navigate(url):
    """
    VISUAL NAVIGATION V27.0 (Sovereign Eye)
    Locates and clicks the address bar visually to ensure reliable URL entry.
    """
    try:
        # 1. Force Maximize (Alt+Space, X) for consistent layout
        pyautogui.hotkey('alt', 'space')
        time.sleep(0.3)
        pyautogui.press('x')
        time.sleep(1)
        
        # 2. Click the Address Bar area (Standard top-center in Chrome)
        # We also try visual identification for robustness
        from . import vision_engine as ve
        coords = ve.get_ui_coordinates("Address bar")
        if coords:
            pyautogui.click(coords[0], coords[1])
        else:
            # Fallback for 1920x1080 maximized: Click at the top center
            pyautogui.click(400, 50) 
            
        time.sleep(0.5)
        
        # 3. Clear and Type (Sovereign Injection)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.press('backspace')
        time.sleep(0.2)
        pyautogui.typewrite(url)
        time.sleep(0.2)
        pyautogui.press('enter')
        return f"[OK] Navegación visual a {url} completada."
    except Exception as e:
        return f"[ERR] Fallo en navegación visual: {e}"

def debug_screenshot(name):
    """Saves a diagnostic screenshot to the debug folder."""
    try:
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        debug_dir = os.path.join(proj_root, "orunex_outputs", "debug")
        os.makedirs(debug_dir, exist_ok=True)
        path = os.path.join(debug_dir, f"{name}_{int(time.time())}.png")
        # Step-by-step hardened capture
        tmp_path = take_screenshot()
        import shutil
        shutil.copy(tmp_path, path)
        return f"[DEBUG] Captura guardada: {path}"
    except Exception as e:
        return f"[DEBUG] Error en captura: {e}"

def total_win_focus(app_name, class_name=None):
    """
    KERNEL FOCUS HIJACK V26.0
    The ultimate way to force a window to the front on Windows.
    """
    try:
        import win32process # type: ignore
        import win32api # type: ignore
        
        def callback(hwnd, params):
            target_name, target_class, found = params
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                cls = win32gui.GetClassName(hwnd)
                if (target_name.lower() in title) or (target_class and target_class == cls):
                    found.append(hwnd)
        
        found_hwnds = []
        win32gui.EnumWindows(callback, (app_name, class_name, found_hwnds))
        
        if found_hwnds:
            hwnd = found_hwnds[0]
            # 1. Hardware-Level Alt+Tab Simulation (Bypasses focus protection)
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
            
            # 2. Kernel Thread Attachment (SetForegroundWindow trick)
            curr_thread = win32api.GetCurrentThreadId()
            fore_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
            if curr_thread != fore_thread:
                win32process.AttachThreadInput(curr_thread, fore_thread, True)
                win32gui.SetForegroundWindow(hwnd)
                win32process.AttachThreadInput(curr_thread, fore_thread, False)
            
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            return True
    except: pass
    return False

def robust_navigate(url):
    """
    KERNEL-LEVEL NAVIGATION V27.0
    Uses Visual Sovereignty to bypass shortcut blockers.
    """
    try:
        # Final Win Focus
        total_win_focus("Chrome", "Chrome_WidgetWin_1")
        return visual_navigate(url)
    except Exception as e:
        return f"[ERR] Fallo en navegación robusta: {e}"

def focus_window(title_substring):
    """Brings a window to the front by its title."""
    try:
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title_substring.lower() in title.lower():
                    windows.append(hwnd)
        
        wins = []
        win32gui.EnumWindows(callback, wins)
        if wins:
            # Force focus
            win32gui.ShowWindow(wins[0], win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(wins[0])
            return True
    except:
        pass
    return False

def chrome_profile_handler():
    """Detects and clicks the Guest button in Chrome Profile Picker with Image Template bypass."""
    print("[Profile-Handler] Maximizando selector de perfil para estabilizar geometria...")
    
    # 1. Force Maximize to stabilize layout
    pyautogui.hotkey('alt', 'space')
    time.sleep(0.3)
    pyautogui.press('x')
    time.sleep(1.5)
    
    # 2. 100% Deterministic Template Matching (V29.0)
    try:
        template_path = os.path.join(os.path.dirname(__file__), "guest_btn.png")
        if os.path.exists(template_path):
            print("[Profile-Handler] Buscando plantilla del boton 'Guest mode'...")
            coords = pyautogui.locateCenterOnScreen(template_path, confidence=0.7)
            if coords:
                pyautogui.moveTo(coords[0], coords[1], duration=0.3)
                pyautogui.click()
                time.sleep(2.5)
                return f"[INFO] Clic de Precision Visual en Plantilla ({coords[0]}, {coords[1]})."
    except Exception as e:
        print(f"[WARN] Fallo Plantilla: {e}")

    # 3. Fallback Coordinate if all Vision fails
    print("[Profile-Handler] Vision fallo, inyectando clic de rescate en el borde inferior del modulo.")
    pyautogui.click(650, 800) 
    time.sleep(2)
    return "[INFO] Clic de redundancia en area geometrica."

# --- V40.1 MISSION DISPATCHER ---
class MissionDispatcher:
    """Gestiona misiones asíncronas en segundo plano (Silent Nodes)."""
    @staticmethod
    def dispatch(mission_cmd: str, agent: str = "cerebro"):
        def run_mission():
            try:
                # Marcar inicio en entorno
                os.environ["ORUNEX_MISSION_ACTIVE"] = "true"
                notify_progress(f"🚀 Misión Iniciada: {mission_cmd[:40]}...", "info")
                
                # Ejecución real en sub-entorno
                rcode, output = execute_shell(mission_cmd, return_code=True)
                
                # V40.5: Log outcome in Mission Journal
                from .long_term_memory import log_mission_outcome # type: ignore
                status = "COMPLETO" if rcode == 0 else "FALLIDO"
                log_mission_outcome(f"M-{int(time.time())}", mission_cmd, status, output)

                # Notificación final según resultado
                if rcode == 0:
                    notify_progress(f"✅ Misión Completada: {mission_cmd[:30]}", "success")
                else:
                    notify_progress(f"⚠️ Misión con advertencias: {mission_cmd[:30]}", "warning")
            except Exception as e:
                print(f"[MISSION ERR] {e}")
            finally:
                os.environ["ORUNEX_MISSION_ACTIVE"] = "false"

        threading.Thread(target=run_mission, daemon=True).start()
        return f"[NODES] Misión delegada al fondo: {mission_cmd}"


def _tag_field(meta: str, key: str, default: str = "") -> str:
    """Read ``key=\"value with spaces\"`` or key=value from a tag payload."""
    pattern = rf'{re.escape(key)}\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(.+?))(?=\s+\w+\s*=|$)'
    match = re.search(pattern, str(meta or ""), flags=re.DOTALL)
    if not match:
        return default
    return next((group for group in match.groups() if group is not None), default).strip()


def intercept_and_execute(text: str, auto_healer_agent: str = "cerebro", auto_heal_attempt: int = 1) -> str:
    """Busca etiquetas [EXEC:], [SEARCH_WEB:], [SEARCH_IMAGE:], [CMD:], [MKDIR:], [FILE:] y [MEMORIZE:] en el texto."""
    from . import permissions as perms # type: ignore
    
    # NUCLEAR DEFENSIVE V3: VARIABLE INJECTION (Scorched Earth)
    # Define LAYOUT as a global variable in this context so if it appears as a variable, it won't crash.
    global LAYOUT # type: ignore
    LAYOUT = "ORUNEX_LAYOUT_GUARD"
    
    # Strip any {LAYOUT: xxx} tags or "LAYOUT = ..." hallucinations (IGNORECASE)
    # This is done GLOBALLY on the raw response text before any tag parsing
    text = re.sub(r'\{LAYOUT:\s*[^}]*\}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'LAYOUT\s*[:=]\s*[^}\n]*', '', text, flags=re.IGNORECASE)
    
    # NEW: Remove hallucinated variables name "LAYOUT" from inside Python script blocks too
    # We do a second pass inside [FILE:] later, but this first pass clears the way.
    
    # Strip slide headers that confuse the executor
    text = re.sub(r'(?i)Slide\s*\d+\s*:.*?\n', '', text)
    text = re.sub(r'(?i)Diapositiva\s*\d+\s*:.*?\n', '', text)

    
    # NUCLEAR DEFENSIVE V11.2: Filter out system instruction fragments
    # These are fragments that small models sometimes echo from the prompt
    instr_fragments = ["[SEARCH_WEB: q]", "[CMD: c]", "[FILE: p|c]", "[MKDIR: d]", "[PPTX: s]"]
    for frag in instr_fragments:
        text = text.replace(frag, "")
    
    # 0. Legacy [EXEC:]
    # Phase 37.3: Base directory initialization
    base_dir = os.path.abspath(os.path.join(os.getcwd(), "orunex_outputs"))
    output_dir = base_dir
    os.makedirs(base_dir, exist_ok=True)

    commands = re.findall(r"\[EXEC:\s*(.*?)\]", text)
    results = []
    if commands:
        for cmd in commands:
            if cmd.lower().startswith("open_browser"):
                res = open_browser()
            elif cmd.lower().startswith("start "): 
                res = execute_shell(cmd)
            else:
                res = execute_shell(cmd)
            results.append(f"Ejecutando '{cmd}': {res}")

    # 1. Advanced Orchestration [CALL: AgentName]
    call_matches = re.findall(r"\[CALL:\s*(.*?)\](.*?)\[/CALL\]", text, re.DOTALL)
    for agent_raw_name, payload in call_matches:
        try:
            agent_name = agent_raw_name.strip().lower()
            if agent_name in ["cerebro", "trader", "empresarial", "automatizador", "general"]:
                # Use absolute import for agents as they are outside utils
                agent_module = importlib.import_module(f"agents.{agent_name}")
                sub_response = agent_module.run(payload.strip(), "Sub-Orquestacion Cerebro", agent_mode="os")
                results.append(f" Agente [{agent_name}] Invocado:\n  {sub_response.strip()[:200]}...")
        except Exception as e:
            results.append(f"[ERR] Error al invocar {agent_raw_name}: {e}")

    # 1. Advanced Universal OS Actions
    mkdir_matches = re.findall(r"\[MKDIR:\s*(.*?)\]", text)
    cmd_matches = re.findall(r"\[CMD:\s*(.*?)\]", text)
    cmd_async_matches = re.findall(r"\[CMD_ASYNC:\s*(.*?)\]", text)
    load_skill_matches = re.findall(r"\[LOAD_SKILL:\s*(.*?)\]", text)
    get_windows_matches = re.findall(r"\[GET_WINDOWS_STATE\]", text)
    search_pc_matches = re.findall(r"\[SEARCH_PC:\s*(.*?)\]", text)
    gui_open_matches = re.findall(r"\[GUI_OPEN:\s*(.*?)\]", text)
    file_matches = re.findall(r"\[FILE:\s*(.*?)\](.*?)\[/FILE\]", text, re.DOTALL)
    
    # Phase 20.0: Sovereign Eye extractions
    smart_launch_matches = re.findall(r'\[GUI_SMART_LAUNCH:\s*(.*?)\]', text, re.IGNORECASE)
    visual_click_matches = re.findall(r'\[GUI_VISUAL_CLICK:\s*(.*?)\]', text, re.IGNORECASE)
    gui_wait = re.findall(r"\[GUI_WAIT:\s*(.*?)\]", text, re.IGNORECASE)
    
    # V43.0 Synapse: Project Planning
    project_plan_matches = re.findall(r"\[PROJECT_PLAN:\s*(.*?)\]", text, re.DOTALL)
    from . import project_manager # type: ignore
    
    # Phase 103: New Integrations
    vscode_matches = re.findall(r"\[VSCODE:\s*(.*?)\]", text)
    social_matches = re.findall(r"\[SOCIAL:\s*(.*?)\]", text)
    screenshot_matches = re.findall(r"\[SCREENSHOT(?::\s*monitor=(\d+))?\]", text)
    gui_navigate_matches = re.findall(r"\[GUI_NAVIGATE:\s*(.*?)\]", text, re.IGNORECASE)
    open_url_matches = re.findall(r"\[OPEN_URL:\s*(.*?)\]", text, re.IGNORECASE)
    chrome_profile_matches = re.findall(r"\[GUI_CHROME_PROFILE\]", text, re.IGNORECASE)
    
    # Phase 30.0: Universal Modules
    headless_search_matches = re.findall(r"\[HEADLESS_SEARCH:\s*(.*?)\]", text)
    make_ppt_matches = re.findall(r"\[MAKE_PPT:\s*(.*?)\]", text)
    make_doc_matches = re.findall(r"\[MAKE_DOC:\s*(.*?)\|\s*(.*?)\]", text)
    # Phase 32.0: Smart Doc Modifier (V37.3: Robust regex for OneDrive paths)
    modify_doc_matches = re.findall(r"\[MODIFY_DOC:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\]", text)
    # Phase 35.0: YouTube Expert
    youtube_matches = re.findall(r"\[YOUTUBE:\s*play\s*\|\s*(.*?)\]", text)
    # Phase 31.0: Chrome Stealth
    chrome_open_matches = re.findall(r"\[CHROME_OPEN:\s*(.*?)\]", text, re.IGNORECASE)
    # Phase 40.0: Executive Missions
    mission_matches = re.findall(r"\[MISSION:\s*(.*?)\]", text, re.IGNORECASE)
    # Phase 40.2: Native Office Integration
    office_matches = re.findall(r"\[OFFICE_MISSION:\s*(.*?)\|\s*(.*?)\|\s*(.*?)\]", text, re.IGNORECASE)
    # Phase 40.4: Sovereign UI Cleaner
    ui_clean_matches = re.findall(r"\[UI_CLEAN\]", text, re.IGNORECASE)
    # Phase 20.0: Vision & Shortcuts (Restored)
    uia_click_matches = re.findall(r"\[UIA_CLICK:\s*(.*?)\]", text, re.IGNORECASE)
    gui_shortcut = re.findall(r"\[GUI_SHORTCUT:\s*(.*?)\]", text)
    
    # Phase 12.8: ANTISPAM (Silence Shield V13.0)
    # Strict Policy: Only 1 action allowed per system response to prevent loops.
    # V37.3: MODIFY_DOC is now EXEMPT from the 1-action limit to ensure it always runs.
    all_tags_count = len(mkdir_matches) + len(cmd_matches) + len(gui_open_matches) + len(file_matches) + \
                     len(make_doc_matches) + len(mission_matches) + len(office_matches) + len(ui_clean_matches)
    if all_tags_count > 1:
        results.append("[WARN] Silence-Shield: Multi-accion detectada. Priorizando ejecucion.")
        if gui_open_matches: gui_open_matches = [gui_open_matches[0]]
        else:
            if mkdir_matches: mkdir_matches = [mkdir_matches[0]]
            if file_matches: file_matches = [file_matches[0]]
            if cmd_matches: cmd_matches = [cmd_matches[0]]
        
        # Clear others
        if gui_open_matches: mkdir_matches = []; file_matches = []; cmd_matches = []
        elif mkdir_matches: file_matches = []; cmd_matches = []
        elif file_matches: cmd_matches = []
    
    # Phase 12.1: Hardened Absolute Base Directory
    # We set it relative to the PROJECT ROOT (one level up from _orunex_libs/..)
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    base_dir = os.path.join(proj_root, "orunex_outputs")
    os.makedirs(base_dir, exist_ok=True)
    
    # 1A. MKDIR
    if mkdir_matches:
        for d in mkdir_matches:
            if not perms.check_permission("MKDIR", d.strip(), auto_healer_agent): continue
            safe_d = os.path.abspath(os.path.join(base_dir, d.strip()))
            if safe_d.startswith(base_dir):
                os.makedirs(safe_d, exist_ok=True)
                msg = f" Carpeta creada: {d.strip()}"
                results.append(msg)
                notify_progress(msg, "success")
                perms.log_result("MKDIR", "Success", auto_healer_agent)
                
    # 1A.2 GUI_OPEN (High-Level App Launching)
    if gui_open_matches:
        from . import app_integrator as app_int # type: ignore
        for app in gui_open_matches:
            if not perms.check_permission("APP_HOOK", f"open:{app.strip()}"): continue
            res = app_int.integrate(app.strip(), "open", "default")
            results.append(f" [GUI] {res}")
            notify_progress(f" Abriendo: {app.strip()}", "success")
                
    # 1B. FILE
    created_files = []
    for filename, content in file_matches:
        if not perms.check_permission("FILE", filename.strip(), auto_healer_agent): continue
        filename = filename.strip()
        safe_path = os.path.abspath(os.path.join(base_dir, filename))
        if safe_path.startswith(base_dir):
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            try:
                # NUCLEAR: Prepend guard to Python files
                final_content = content.strip()
                
                # Strip hallucinations (IGNORECASE) from inside the file content
                final_content = re.sub(r'\{LAYOUT:\s*[^}]*\}', '', final_content, flags=re.IGNORECASE).strip()
                final_content = re.sub(r'(?m)^LAYOUT\s*[:=].*$', '', final_content, flags=re.IGNORECASE).strip()

                if filename.endswith(".py"):
                    # Add guard as the first line
                    final_content = "LAYOUT = 'ORUNEX_GUARD'\n" + final_content
                
                with open(safe_path, "w", encoding="utf-8") as f:
                    f.write(final_content)
                created_files.append(filename)
            except Exception as e:
                results.append(f"[ERR] Error escribiendo {filename}: {e}")
                
    if created_files:
        msg = f"[OK] Archivos generados: {', '.join(created_files)}"
        results.append(msg)
        notify_progress(msg, "success")
        
    # 1C. CMD (execute in base_dir without changing global CWD) + ReAct Auto-Heal
    if cmd_matches:
        for cmd in cmd_matches:
            if not perms.check_permission("CMD", cmd.strip(), auto_healer_agent): continue
            
            # V43.15 Auto-Async Enforcement (Prevent Deadlocks)
            server_kw = ["flask", "http.server", "npm start", "node ", "server.py", "python -m http"]
            cmd_val = cmd.strip()
            if any(kw in cmd_val.lower() for kw in server_kw):
                notify_progress(f"⚡ Sentinel: Forzando ejecución asíncrona para servidor: {cmd_val[:30]}...", "warning")
                subprocess.Popen(
                    cmd_val,
                    shell=True,
                    cwd=base_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **_hidden_process_kwargs(),
                )
                results.append(f"[CMD_ASYNC_FORCE] Servidor iniciado en segundo plano.")
                continue

            cmd_to_run = cmd_val

            # NUCLEAR: Inject guard into one-liners
            if "python" in cmd_to_run.lower() and "-c" in cmd_to_run:
                if '"' in cmd_to_run:
                    cmd_to_run = cmd_to_run.replace("-c \"", "-c \"LAYOUT='GUARD'; ")
                elif "'" in cmd_to_run:
                    cmd_to_run = cmd_to_run.replace("-c '", "-c 'LAYOUT=\"GUARD\"; ")
            
            rcode, res = execute_shell(cmd_to_run, cwd=base_dir, return_code=True)
            perms.log_result("CMD", res, auto_healer_agent)
            
            # Phase 12.7: Detect empty or failing commands
            if not cmd_to_run.strip():
                results.append("[ERR] Comando vacio ignorado.")
                continue
            
            # SELF-HEALING ReAct LOOP
            if rcode != 0 and auto_heal_attempt < 3:
                results.append(f"[WARN] Comando Fallido: {cmd.strip()}\n  > Error: {res[:200]}...\n  > [CORE] Iniciando Auto-Sanacion (Intento {auto_heal_attempt})...") # type: ignore
                try:
                    import importlib
                    agent_module = importlib.import_module(f"agents.{auto_healer_agent}")
                    prompt = f"Ejecutaste el comando '{cmd}' en la terminal pero fallo con este error:\n\n{res}\n\nPor favor, analiza el por que fallo. Genera nuevamente las etiquetas [FILE:], [EDIT:] o [CMD:] necesarias para arreglar el error y volver a intentarlo."
                    fix_response = agent_module.run(prompt, "ReAct Auto-Healer", agent_mode="os")
                    
                    # Recursive Call
                    final_res = intercept_and_execute(fix_response, auto_healer_agent=auto_healer_agent, auto_heal_attempt=auto_heal_attempt+1)
                    results.append(f" Resultado de Auto-Sanacion:\n{final_res}")
                except Exception as e:
                    results.append(f"[ERR] Error en Auto-Sanacion: {e}")
            else:
                msg = f"[GEAR] Comando Terminal: {cmd.strip()}"
                results.append(f"{msg}\n  > Salida: {res[:200]}...") # type: ignore
                notify_progress(msg, "success")
                
    # 1C.1 CMD_ASYNC (Hilo paralelo sin bloqueo LLM)
    if cmd_async_matches:
        for cmd in cmd_async_matches:
            if not perms.check_permission("CMD", cmd.strip(), auto_healer_agent): continue
            def run_async(command):
                rcode, res = execute_shell(command, cwd=base_dir, return_code=True)
                perms.log_result("CMD_ASYNC", f"{command} -> {res[:100]}", auto_healer_agent) # type: ignore
                try:
                    from . import simplex_bridge as simplex # type: ignore
                    # Keep asynchronous command progress local; the remote task
                    # gets one Thinking... and the final answer with this output.
                    simplex.get_bridge().send_pulse(
                        f"[EXE] [CMD_ASYNC] completado:\n{command}\nResultado: {res[:100]}..."
                    )
                except: pass
            import threading
            threading.Thread(target=run_async, args=(cmd.strip(),), daemon=True).start()
            results.append(f"[EXE] Tarea Asincrona Iniciada en Background: {cmd.strip()}")
                
    # 1D. MEMORIZE (Long-Term Vector Memory)
    memo_matches = re.findall(r"\[MEMORIZE:\s*(.*?)\]", text)
    if memo_matches:
        try:
            from .long_term_memory import add_preference # type: ignore
            from . import faiss_memory # type: ignore
            for memo in memo_matches:
                add_preference(memo.strip())
                try:
                    faiss_memory.remember_text(
                        memo.strip(),
                        {"type": "explicit_memory", "agent": "user"},
                    )
                except Exception:
                    pass
                results.append(f"[CORE] Memoria a Largo Plazo Actualizada: '{memo.strip()}'")
        except: pass
                
    # 1E. Vision-First GUI Control & OCR
    from . import permissions as perms # type: ignore
    
    gui_see = re.findall(r"\[GUI_SEE:\s*(.*?)\]", text)
    gui_click_xy = re.findall(r"\[GUI_CLICK:\s*(\d+)\s*,\s*(\d+)\]", text)
    gui_click_txt = re.findall(r"\[GUI_CLICK_TEXT:\s*(.*?)\]", text)
    gui_type = re.findall(r"\[GUI_TYPE:\s*(.*?)\]", text)
    gui_scroll = re.findall(r"\[GUI_SCROLL:\s*(up|down)\s*(\d+)\]", text, re.IGNORECASE)
    gui_press = re.findall(r"\[GUI_PRESS:\s*(.*?)\]", text)
    
    # 1G. VSCODE
    if vscode_matches:
        for v_meta in vscode_matches:
            # Supports both quoted and unquoted values:
            #   action="open" value="C:\\ruta con espacios\\main.py" line=12
            #   action=terminal value="python -m pytest -q"
            act = _tag_field(v_meta, "action")
            val = _tag_field(v_meta, "value")
            extra = _tag_field(v_meta, "extra")
            line = re.search(r'line\s*=\s*(\d+)', v_meta)

            res = vscode.execute(
                action=act or "open",
                value=val or v_meta.strip(),
                line=int(line.group(1)) if line else None,
                extra=extra,
            )
            results.append(f"[VSCODE] {res}")
            notify_progress(res, "success")

    # 1H. SOCIAL
    if social_matches:
        for s_meta in social_matches:
            net = re.search(r'network\s*=\s*["\']?(.*?)["\']?(?:\s|$)', s_meta)
            act = re.search(r'action\s*=\s*["\']?(.*?)["\']?(?:\s|$)', s_meta)
            txt = re.search(r'text\s*=\s*["\']?(.*?)["\']?(?:\s|$)', s_meta)
            qry = re.search(r'query\s*=\s*["\']?(.*?)["\']?(?:\s|$)', s_meta)
            cnt = re.search(r'contact\s*=\s*["\']?(.*?)["\']?(?:\s|$)', s_meta)
            
            res = social.execute(
                network=net.group(1) if net else "",
                action=act.group(1) if act else "open",
                text=txt.group(1) if txt else "",
                query=qry.group(1) if qry else "",
                contact=cnt.group(1) if cnt else ""
            )
            results.append(f"[SOCIAL] {res}")
            notify_progress(f"Social: {res[:50]}...", "success")

    # 1I. SCREENSHOT (Multi-Monitor)
    if screenshot_matches:
        for m_idx in screenshot_matches:
            m = int(m_idx) if m_idx else 1
            path = take_screenshot(m)
            results.append(f" Captura de pantalla (Monitor {m}):\n[WIDGET: {path}]")
            
    # Phase 30.0 Executions: Headless & PPT
    if headless_search_matches:
        try:
            from .headless_web import search_and_summarize # type: ignore
            for query in headless_search_matches:
                res = search_and_summarize(query.strip())
                results.append(res)
        except Exception as e:
            results.append(f"[ERR] Motor Headless falló: {e}")

    # Phase 35.0: YouTube Expert (Smart Choice & Play)
    if youtube_matches:
        try:
            from .headless_web import search_youtube # type: ignore
            from .chrome_driver import open_url_in_chrome # type: ignore
            from .app_integrations_manager import get_active_profile  # type: ignore
            
            for query in youtube_matches:
                # Phase 36.9.1.7: Surgical Symbol Scrubber (Zenith Sovereignty Guard)
                # Removes ONLY leading/trailing punctuation noise like : ” “ ' " 
                clean_query = query.strip().strip(":;,. \"'“”«»„")
                
                # Strip conversational fluff
                clean_query = re.sub(r"(?i)\by\s+reproduce.*|\by\s+pon.*|\bque\s+coincida.*|\bel\s+mejor.*|\bel\s+que\s+mejor.*|\bel\s+video\s+que.*", "", clean_query).strip()
                if not clean_query: clean_query = query.strip()
                
                from .simplex_bridge import get_bridge # type: ignore
                get_bridge().send_pulse(f"Buscando '{clean_query[:40]}' en YouTube...")
                
                from .headless_web import search_youtube # type: ignore
                vids = search_youtube(clean_query)
                
                if not vids:
                    # Fallback: Abrir búsqueda directa en Chrome nativo (no Selenium)
                    active_p = get_active_profile()
                    search_url = f"https://www.youtube.com/results?search_query={clean_query.replace(' ', '+')}"
                    results.append(f"[YOUTUBE] Buscadores agotados. Abriendo YouTube directo...")
                    open_url_in_chrome(search_url, profile_name=active_p)
                    results.append(f"[OK] YouTube abierto en Chrome.")
                    continue
                
                get_bridge().send_pulse("Analizando resultados con Orunex Brain...")
                v_list = ""
                for i, v in enumerate(vids):
                    v_list += f"{i+1}. {v['title']} (by {v['uploader']})\n"
                
                reasoning_prompt = f"El usuario quiere ver un video sobre '{query}'. De esta lista de YouTube, cual es el titulo que mejor coincide? Responde UNICAMENTE con el numero del indice (1-{len(vids)}).\n\nLISTA:\n{v_list}"
                
                resp = call_ollama("orunex_v37", reasoning_prompt, options={"temperature": 0.0})
                choice_raw = resp.get("response", "1")
                if "</think>" in choice_raw: choice_raw = choice_raw.split("</think>")[-1].strip()
                
                try:
                    idx = int(re.search(r"\d+", choice_raw).group()) - 1 # type: ignore
                    if idx < 0 or idx >= len(vids): idx = 0
                except: idx = 0
                
                winner = vids[idx]
                get_bridge().send_pulse(f"▶ Reproduciendo: '{winner['title']}'")
                results.append(f"[YOUTUBE] Orunex eligió: '{winner['title']}'")
                
                profile = get_active_profile()
                open_url_in_chrome(url=winner['url'], profile_name=profile)
                results.append(f"[OK] Reproduciendo: {winner['url']}")
        except Exception as e:
            results.append(f"[ERR] YouTube Expert error: {e}")

    if make_ppt_matches:
        try:
            from .ppt_maker import generate_presentation # type: ignore
            from .simplex_bridge import get_bridge # type: ignore
            for topic in make_ppt_matches:
                get_bridge().send_pulse(f"Diseñando presentación PPT sobre '{topic[:30]}...'")
                res_path = generate_presentation(topic.strip(), base_dir)
                if res_path:
                    results.append(
                        f"[PPT_MAKER] Presentacion Lista en: {res_path}"
                        f"\n[ARTIFACT: {res_path}|pptx|{topic.strip()}]"
                    )
                    execute_shell(f'start "" "{res_path}"')
                else:
                    results.append("[PPT_MAKER] Fallo la creacion del archivo PPT.")
        except Exception as e:
            results.append(f"[ERR] Creador PPT fallo: {e}")

    # Phase 30.5: Document Factory (Excel, Word, PDF, Landing, PPT)
    if make_doc_matches:
        try:
            from .doc_factory import generate_excel, generate_word, generate_pdf, generate_landing  # type: ignore
            from .ppt_maker import generate_presentation  # type: ignore
            from .simplex_bridge import get_bridge # type: ignore
            from . import artifact_studio  # type: ignore

            def _fallback_artifact(kind: str, title: str, out_dir: str = base_dir):
                try:
                    return artifact_studio.create_artifact(kind, title, out_dir=out_dir)
                except Exception as fallback_error:
                    notify_progress(
                        f"Fallback de documento falló: {fallback_error}", "error"
                    )
                    return None

            for dtype, topic in make_doc_matches:
                dtype = dtype.strip().lower()
                topic = topic.strip()
                notify_progress(f"📋 Iniciando generación de {dtype.upper()}: '{topic[:30]}'...", "info")
                res_path = None
                if dtype == "landing":
                    has_vsc = vscode._code_available()
                    target_dir = vscode.CREATION_CHAMBER if has_vsc else base_dir
                    os.makedirs(target_dir, exist_ok=True)
                    try:
                        res_path = generate_landing(topic, target_dir)
                    except Exception:
                        res_path = _fallback_artifact("html", topic, target_dir)
                    if res_path and os.path.exists(res_path):
                        if has_vsc:
                            vscode.open_file(res_path)
                            results.append(
                                f"[ORUNEX CODE] Landing Page generada en el Espacio Soberano y abierta en VSCode."
                                f"\n[ARTIFACT: {res_path}|html|{topic}]"
                            )
                        else:
                            results.append(
                                f"[DOC_FACTORY] Landing Page lista: '{os.path.basename(res_path)}'"
                                f"\n[ARTIFACT: {res_path}|html|{topic}]"
                            )
                            execute_shell(f'start "" "{res_path}"')
                    else:
                        results.append(f"[ERR] Fallo la emision de la landing page profesional.")
                    continue

                if dtype == "video":
                    notify_progress("🎬 Video Marketing Master V52.0 — Diseñando guión AIDA, escenas 9:16 y Colab GPU Notebook...", "info")
                    def _vid_cb(msg: str): notify_progress(msg, "info")
                    try:
                        from .video_marketing_engine import generate_social_video_campaign
                        camp = generate_social_video_campaign(topic, base_dir, progress_cb=_vid_cb)
                        res_path = camp.get("video_mp4_path") or camp.get("colab_notebook_path")
                        msg_cap = f"📲 CAPTION INSTAGRAM:\n{camp.get('instagram_caption')}\n\n{camp.get('hashtags')}"
                        results.append(f"[VIDEO_MARKETING] {msg_cap}")
                    except Exception as _v_err:
                        notify_progress(f"❌ Error en Video Engine: {_v_err}", "error")

                elif dtype == "colab":
                    notify_progress("⚡ Google Colab Master — Generando Notebook .ipynb optimizado para Cloud GPU...", "info")
                    try:
                        from .colab_master import generate_colab_notebook
                        res_path = generate_colab_notebook(topic, "AI Video Render", base_dir)
                    except Exception as _c_err:
                        notify_progress(f"❌ Error en Colab Master: {_c_err}", "error")

                elif dtype == "excel":
                    # Excel Master V52.0 — investigación real + gráficas + pivot + VBA macros
                    notify_progress("📊 Excel Master V52.0 — Investigando y generando reporte ejecutivo...", "info")
                    def _excel_progress_cb(msg: str):
                        notify_progress(msg, "info")
                    try:
                        from .excel_master import generate_excel_master  # type: ignore
                        res_path = generate_excel_master(topic, base_dir, progress_cb=_excel_progress_cb)
                    except Exception as _em_err:
                        notify_progress(f"⚠️ Master fallback: {_em_err}", "warn")
                        try:
                            res_path = generate_excel(topic, base_dir)
                        except Exception:
                            res_path = _fallback_artifact("xlsx", topic)
                elif dtype == "word":
                    notify_progress("📄 Generando documento Word...", "info")
                    try:
                        res_path = generate_word(topic, base_dir)
                    except Exception:
                        res_path = _fallback_artifact("docx", topic)
                elif dtype == "pdf":
                    notify_progress("📑 Generando PDF...", "info")
                    try:
                        res_path = generate_pdf(topic, base_dir)
                    except Exception:
                        res_path = _fallback_artifact("pdf", topic)
                elif dtype == "ppt":
                    # Pass a live progress callback so the UI logs each step
                    notify_progress("🎨 Iniciando motor de presentaciones profesionales...", "info")
                    def _ppt_progress_cb(msg: str):
                        notify_progress(msg, "info")
                    try:
                        res_path = generate_presentation(topic, base_dir, progress_cb=_ppt_progress_cb)
                    except Exception:
                        res_path = _fallback_artifact("pptx", topic)

                if res_path:
                    fname = os.path.basename(res_path)
                    msg = f"✅ {dtype.upper()} listo: '{fname}'"
                    kind = os.path.splitext(res_path)[1].lstrip(".").lower() or dtype
                    results.append(
                        f"[DOC_FACTORY] {msg}\n[ARTIFACT: {res_path}|{kind}|{topic}]"
                    )
                    notify_progress(msg, "success")
                    execute_shell(f'start "" "{res_path}"')
                else:
                    results.append(f"[ERR] Fallo la emision del documento {dtype.upper()}.")
        except Exception as e:
            import traceback
            results.append(f"[ERR] Doc Factory error: {e}\n{traceback.format_exc()[:300]}")
            notify_progress(f"❌ Error generando documento: {e}", "error")
    
    # Phase 31.0: Chrome URL Open (Nativo V37)
    if open_url_matches:
        for target in open_url_matches:
            target_url, target_browser = _split_open_target(target)
            results.append(open_url(target_url, target_browser))
            notify_progress(f"Abriendo {target_url} en el navegador.", "success")

    if chrome_open_matches:
        try:
            from .chrome_driver import open_url_in_chrome  # type: ignore
            from .app_integrations_manager import get_active_profile  # type: ignore
            profile = get_active_profile()
            for url in chrome_open_matches:
                url = url.strip()
                res = open_url_in_chrome(url=url, profile_name=profile)
                results.append(res)
        except Exception as e:
            results.append(f"[ERR] Chrome Stealth: {e}")

    # Phase 32.0: Smart Doc Modifier (V37.3: Linked to Expert Excel Engine)
    if modify_doc_matches:
        try:
            from .excel_engine import modify_excel # type: ignore
            for target_type, topic, fpath in modify_doc_matches:
                target_type = target_type.strip().lower()
                topic = topic.strip()
                fpath = fpath.strip().replace('"', '').replace("'", "")
                
                if target_type == "excel":
                    notify_progress(f"📊 SISTEMA: Transformando base de datos Excel...", "info")
                    res = modify_excel(topic, fpath, output_dir)
                    if res and os.path.exists(str(res)):
                        msg = f"✅ Excel Modificado: {os.path.basename(res)}"
                        results.append(msg)
                        notify_progress(f"🚀 {msg}. Abriendo resultado...", "success")
                        try: os.startfile(res) 
                        except: pass
                    else:
                        err_msg = f"❌ Falla critica al modificar Excel: {os.path.basename(fpath)}"
                        results.append(err_msg)
                        notify_progress(err_msg, "error")
                else:
                    results.append(f"[WARN] Modificador no soportado para {target_type}")
            
            # --- V37.3: Notificación Final Experta (Condicional) ---
            has_errors = any("❌" in r or "[ERR]" in r for r in results)
            if not has_errors:
                notify_progress("✅ Tarea completada exitosamente.", "success")
        except Exception as e:
            err_detail = f"Error en motor: {type(e).__name__} (Detail: {e})"
            results.append(f"[ERR] {err_detail}")
            notify_progress(f"Falla tecnica: {err_detail}", "error")

    # Phase 40.0: Executive Missions Dispatcher
    if mission_matches:
        for m_cmd in mission_matches:
            res = MissionDispatcher.dispatch(m_cmd, auto_healer_agent)
            results.append(res)

    # Phase 40.2: Native Office Executive Integration
    if office_matches:
        from .office_integrator import run_office_mission # type: ignore
        for target, action, payload in office_matches:
            # Check for extended kwargs (path, topic, etc) if available in text or context
            # Simplex Logic: Extract from text if payload contains metadata
            res = run_office_mission(target.strip().lower(), action.strip().lower(), payload)
            results.append(res)

    # Phase 40.4: Sovereign UI Cleaner Logic
    if ui_clean_matches:
        try:
            from .vision_engine import skip_ads_intelligent # type: ignore
            res = skip_ads_intelligent()
            results.append(f"[VISION] Limpiando UI: {res}")
        except Exception as e:
            results.append(f"[VISION ERR] {e}")

    if uia_click_matches:
        try:
            from .uia_engine import uia_click # type: ignore
            for target in uia_click_matches:
                res = uia_click(target.strip())
                results.append(res)
        except Exception as e:
            results.append(f"[ERR] Falla General en UIA Engine: {e}")
    
    if gui_see or gui_click_xy or gui_click_txt or gui_type or gui_scroll or gui_press or gui_shortcut or smart_launch_matches or gui_navigate_matches or chrome_profile_matches or visual_click_matches or gui_wait:
        try:
            import pyautogui # type: ignore
            import time
            from PIL import Image # type: ignore
            
            # --- 1. SMART LAUNCH (Professional Filter V45.0) ---
            for app in smart_launch_matches:
                if not perms.check_permission("GUI_OPEN", app): continue
                
                # V45.0 Filter: Prevent amateur drift
                amateur_apps = ["taskmgr", "task manager", "excel.exe", "excel", "notepad"]
                if any(kw in app.lower() for kw in amateur_apps):
                    results.append(f"[PROFESSIONAL_GUARD] Bloqueado lanzamiento de '{app}'. Usa [EXCEL:] o psutil en CMD para misiones industriales.")
                    notify_progress(f"🛡️ Bloqueando herramienta no profesional: {app}", "warning")
                    continue

                res = smart_launch(app)
                results.append(res)
                perms.log_result("GUI_SMART_LAUNCH", res)
                debug_screenshot(f"launch_{app}") # V23.0 Telemetry
                time.sleep(1.5)

            # --- 2. CHROME PROFILE HANDLER ---
            if chrome_profile_matches:
                results.append(" [Profile-Handler] Intentando superar selector de Chrome...")
                results.append(chrome_profile_handler())
                debug_screenshot("profile_after") # V23.0 Telemetry

            # --- 3. GUI WAIT ---
            for target in gui_wait:
                results.append(f" [Wait] Esperando aparicion visual de '{target}'...")
                if wait_for_ui(target):
                    results.append(f" [OK] Elemento '{target}' detectado.")
                else:
                    results.append(f" [ERR] Time-out esperando '{target}'.")

            # --- 4. VISUAL CLICK ---
            for target in visual_click_matches:
                if not perms.check_permission("GUI_CLICK", target): continue
                results.append(f" [Sovereign Eye] Localizando visualmente '{target}'...")
                res = visual_click(target)
                results.append(res)
                perms.log_result("GUI_VISUAL_CLICK", res)
                time.sleep(0.8)

            # --- 5. ROBUST NAVIGATION ---
            for url in gui_navigate_matches:
                target_url, target_browser = _split_open_target(url)
                results.append(open_url(target_url, target_browser))
                notify_progress(f"Abriendo {target_url} en el navegador.", "success")
            
            # --- VISION (GUI_SEE) ---
            for prompt in gui_see:
                if not perms.check_permission("GUI_SEE", prompt): continue
                results.append(f"[VIS] Vision Activa: Analizando pantalla para '{prompt}'...")
                screen_path = take_screenshot()
                
                try:
                    with open(screen_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    v_res = call_ollama(
                        model="moondream",
                        prompt=f"Describe where the '{prompt}' is located in this screen and give me the (x, y) coordinates if possible.",
                        images=[encoded_string]
                    )
                    vision_text = v_res.get("response", "No se detecto nada claro.")
                    results.append(f"[ZENITH-EYE] Analisis Visual: {vision_text}")
                except Exception as ve:
                    results.append(f"[ERR] Error en Vision Moondream: {ve}")
                
                perms.log_result("GUI_SEE", "Analisis completado via Moondream")
            
            # --- CLICK COORDINATES ---
            for x, y in gui_click_xy:
                if not perms.check_permission("GUI_CLICK", f"{x},{y}"): continue
                try:
                    pyautogui.moveTo(int(x), int(y), duration=0.3)
                    pyautogui.click()
                    msg = f" GUI_CLICK: ({x}, {y})"
                    results.append(msg)
                    perms.log_result("GUI_CLICK", msg)
                    time.sleep(0.5)
                except Exception as ce:
                    if auto_heal_attempt < 3:
                        results.append(f"[WARN] El click en ({x},{y}) fallo (fuera de limites). [VIS] Iniciando Vision Auto-Heal...")
                        import tempfile
                        screen = pyautogui.screenshot()
                        tmp_path = os.path.join(tempfile.gettempdir(), "vision_heal_coord.png")
                        screen.save(tmp_path)
                        import importlib
                        vision_agent = importlib.import_module("agents.vision")
                        prompt = f"Intente hacer click en las coordenadas ({x},{y}) pero el sistema lo rechazo. Analiza la pantalla y dame las coordenadas correctas usando [GUI_CLICK: X, Y]."
                        fix_response = vision_agent.run(prompt, "Vision-Healer", image_path=tmp_path)
                        final_res = intercept_and_execute(fix_response, auto_healer_agent=auto_healer_agent, auto_heal_attempt=auto_heal_attempt+1)
                        results.append(f" Recuperacion Visual de Coordenadas:\n{final_res}")
                    else:
                        results.append(f"[ERR] Error critico en GUI_CLICK: {ce}")
                
            # --- CLICK TEXT (OCR) ---
            for click_text in gui_click_txt:
                if not perms.check_permission("GUI_CLICK", click_text): continue
                target = click_text.strip().lower()
                results.append(f" Buscando texto '{target}' en pantalla...")
                try:
                    import pytesseract # type: ignore
                    import cv2 # type: ignore
                    import numpy as np # type: ignore
                    
                    tesseract_path = os.path.abspath(os.path.join(os.getcwd(), "resources", "Tesseract-OCR", "tesseract.exe"))
                    if os.path.exists(tesseract_path):
                        pytesseract.pytesseract.tesseract_cmd = tesseract_path
                        
                    screen_np = np.array(pyautogui.screenshot()) # type: ignore
                    gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
                    
                    found = False
                    for i in range(len(data['text'])): # type: ignore
                        if target in str(data['text'][i]).lower() and int(data['conf'][i]) > 30: # type: ignore
                            cx = int(data['left'][i]) + int(data['width'][i])//2 # type: ignore
                            cy = int(data['top'][i]) + int(data['height'][i])//2 # type: ignore
                            pyautogui.moveTo(cx, cy, duration=0.3)
                            pyautogui.click()
                            msg = f" GUI_CLICK_TEXT: '{click_text}' presionado en ({cx}, {cy})"
                            results.append(msg)
                            perms.log_result("GUI_CLICK_TEXT", msg)
                            found = True
                            break
                    if not found:
                        if auto_heal_attempt < 3:
                            results.append(f"[WARN] OCR fallo para '{click_text}'. [VIS] Activando Vision Auto-Heal (Intento {auto_heal_attempt})...")
                            import tempfile
                            screen = pyautogui.screenshot()
                            tmp_path = os.path.join(tempfile.gettempdir(), "vision_heal_ocr.png")
                            screen.save(tmp_path)
                            
                            vision_agent = importlib.import_module("agents.vision")
                            prompt = f"El usuario intento ubicar/pulsar '{click_text}' pero el OCR basico fallo. Mira la pantalla y dime donde esta ahora. Entrega EXCLUSIVAMENTE un tag como [GUI_CLICK: X, Y] para que yo presione las coordenadas exactas sobre '{click_text}'."
                            fix_response = vision_agent.run(prompt, "Vision-Healer", image_path=tmp_path)
                            
                            final_res = intercept_and_execute(fix_response, auto_healer_agent=auto_healer_agent, auto_heal_attempt=auto_heal_attempt+1)
                            results.append(f" Recuperacion Visual:\n{final_res}")
                        else:
                            results.append(f"[WARN] GUI_CLICK_TEXT: Imposible ubicar '{click_text}' tras fallar Vision Auto-Heal.")
                except Exception as oe:
                    results.append(f"[ERR] Error OCR/PyAutoGUI: {oe}")
                time.sleep(0.5)

            # --- TYPE TEXT ---
            for type_text in gui_type:
                if not perms.check_permission("GUI_TYPE", type_text): continue
                pyautogui.typewrite(type_text, interval=0.01)
                msg = f" GUI_TYPE: '{type_text}'"
                results.append(msg)
                perms.log_result("GUI_TYPE", msg)
                time.sleep(0.5)
                
            # --- SCROLL ---
            for direction, amount in gui_scroll:
                if not perms.check_permission("GUI_SCROLL", f"{direction} {amount}"): continue
                scroll_val = int(amount) if direction.lower() == "up" else -int(amount)
                pyautogui.scroll(scroll_val)
                msg = f" GUI_SCROLL: {direction} {amount}"
                results.append(msg)
                perms.log_result("GUI_SCROLL", msg)
                time.sleep(0.5)
                
            # --- KEYBOARD PRESS ---
            for key_text in gui_press:
                if not perms.check_permission("GUI_PRESS", key_text): continue
                pyautogui.press(key_text.strip().lower())
                msg = f" GUI_PRESS: Tecla '{key_text}'"
                results.append(msg)
                perms.log_result("GUI_PRESS", msg)
                time.sleep(0.5)
                
            # --- KEYBOARD-FIRST SHORTCUTS (Mega Fase 2) ---
            for shortcut in gui_shortcut:
                if not perms.check_permission("GUI_SHORTCUT", shortcut): continue
                keys = [k.strip().lower() for k in shortcut.split('+')]
                # Map common key names to pyautogui format
                key_map = {'win': 'winleft', 'windows': 'winleft', 'ctrl': 'ctrl',
                           'alt': 'alt', 'shift': 'shift', 'tab': 'tab',
                           'esc': 'escape', 'del': 'delete', 'ins': 'insert',
                           'left': 'left', 'right': 'right', 'up': 'up', 'down': 'down',
                           'enter': 'return', 'f4': 'f4', 'f5': 'f5', 'home': 'home',
                           'end': 'end', 'pgup': 'pageup', 'pgdn': 'pagedown'}
                mapped = [key_map.get(k, k) for k in keys]
                try:
                    pyautogui.hotkey(*mapped)
                    msg = f" [Keyboard-First] Atajo '{shortcut}' ejecutado a nivel Kernel."
                    results.append(msg)
                    perms.log_result("GUI_SHORTCUT", msg)
                    time.sleep(0.4)
                except Exception as ke:
                    results.append(f"[ERR] Error ejecutando atajo '{shortcut}': {ke}")

            # --- UIA CLICK (MATRIX VISION NATIVA) ---
            if uia_click_matches:
                import uiautomation as auto # type: ignore
                for btn_name in uia_click_matches:

                    if not perms.check_permission("UIA_CLICK", btn_name): continue
                    results.append(f" [Matrix Vision] Buscando nodo nativo '{btn_name}'...")
                    try:
                        # Buscar recursivamente en todo el arbol de accesibilidad del SO (TimeOut 3s)
                        btn = auto.Control(Name=btn_name, searchDepth=7)
                        if btn.Exists(3, 1):
                            btn.Click()
                            msg = f"[EXE] UIA_CLICK: Nodo '{btn_name}' presionado exitosamente a nivel Kernel."
                            results.append(msg)
                            perms.log_result("UIA_CLICK", msg)
                        else:
                            results.append(f"[WARN] UIA_CLICK: No se detecto un nodo semantico llamado '{btn_name}'. Trata con [GUI_CLICK_TEXT:] o comandos de teclado en su lugar.")
                    except Exception as uia_err:
                        results.append(f"[ERR] Error en Matrix Vision (UIA): {uia_err}")
                time.sleep(0.3)
            
        except Exception as e:
            results.append(f"[ERR] Error Critico en Control GUI/UIA: {e}")
            
    # 1E.2 Carga Dinamica de Skills (Dynamic Tool Loading)
    if load_skill_matches:
        for skill_name in load_skill_matches:
            from .skills_registry import get_skill # type: ignore
            skill_content = get_skill(skill_name)
            results.append(f"[CORE] Cargando modulo experto temporal: {skill_name}")
            
            if auto_heal_attempt < 3:
                try:
                    import importlib
                    agent_module = importlib.import_module(f"agents.{auto_healer_agent}")
                    prompt = f"""EL MODULO '{skill_name.upper()}' HA SIDO CARGADO EN TU MEMORIA RAM:
{skill_content}

INSTRUCCION: Con esta nueva experiencia experta, resuelve la orden original del usuario.
Usa las etiquetas del Sistema Operativo para ejecutar la tarea de forma autonoma."""
                    
                    fix_raw = agent_module.run(prompt, "ReAct Skill-Loader", agent_mode="os")
                    final_res = intercept_and_execute(fix_raw, auto_healer_agent=auto_healer_agent, auto_heal_attempt=auto_heal_attempt+1)
                    results.append(final_res)
                except Exception as e:
                    results.append(f"[ERR] Error inyectando skill {skill_name}: {e}")
                    
    # 1E.3 Estado del SO (Windows State Awareness)
    if get_windows_matches:
        try:
            import pygetwindow as gw # type: ignore
            windows = gw.getAllTitles()
            # Filtramos ventanas vacias
            active_windows = [w for w in windows if w.strip()]
            windows_str = "\n".join(f"- {w}" for w in active_windows)
            if not windows_str: windows_str = "No hay ventanas detectadas."
            
            results.append(f" Ventanas Activas en el Sistema:\n{windows_str}")
        except Exception as e:
            results.append(f"[ERR] Error obteniendo estado de ventanas: {e}")
            
    # 1E.4 Busqueda Vectorial Local ("Orunex Recall")
    if search_pc_matches:
        try:
            from . import semantic_search as semantic # type: ignore
            for query in search_pc_matches:
                res_text = semantic.display_search(query.strip())
                results.append(f" Busqueda Vectorial ('{query}'):\n{res_text}")
        except Exception as e:
            results.append(f"[ERR] Error en busqueda semantica (instala 'nomic-embed-text' en Ollama): {e}")
            
    # 1F. Busqueda Web Real-Time + ReAct Loop (Regex relajado para evitar fallos del LLM)
    web_search = re.findall(r"\[SEARCH_WEB[:\. ]*(.*?)\]", text)
    if web_search:
        import urllib.request, urllib.parse # type: ignore
        for query in web_search:
            try:
                # Phase 74: Robust DuckDuckGo Lite search with increased timeout
                url = "https://lite.duckduckgo.com/lite/"
                data = urllib.parse.urlencode({'q': query}).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; x64)"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode('utf-8')
                    snippets = re.findall(r'<td class=\'result-snippet\'>(.*?)</td>', html, re.IGNORECASE | re.DOTALL)
                    clean_snippets = []
                    for s in snippets[:4]: # type: ignore
                        clean = re.sub(r'<[^>]+>', '', s).strip() # type: ignore
                        clean_snippets.append(f"- {clean}")
                    res_text = "\n".join(clean_snippets) if clean_snippets else "No se encontraron resultados utiles."
                    results.append(f" Resultados Web de '{query}':\n{res_text}")
                    notify_progress(f" Busqueda web: {query}", "success")
            except Exception as e:
                results.append(f"[ERR] Error en busqueda web: {e}")

    # V43.0: Intercept Project Plan (V43.2 Hardened JSON Extraction)
    if project_plan_matches:
        try:
            plan_raw = project_plan_matches[0].strip()
            # Surgical JSON extraction: Find first { and last }
            start = plan_raw.find('{')
            end = plan_raw.rfind('}')
            if start != -1 and end != -1:
                json_str = plan_raw[start:end+1]
                plan_data = json.loads(json_str)
                goal = plan_data.get("goal", "Misión Autónoma")
                steps = plan_data.get("steps", [])
                
                if steps:
                    # V43.11 Sentinel Mode: Pre-validation for mission-critical goals
                    is_critical = any(kw in goal.lower() for kw in ["server", "flask", "scan", "blockchain", "audit", "clean"])
                    if is_critical:
                        notify_progress(f"🛡️ MODALIDAD SENTINEL: Misión Crítica Detectada.", "warning")
                        # Add a hidden instruction to the first step to be extra careful (V43.12 Async Force)
                        steps[0]["desc"] = f"[SENTINEL ADVISORY] Usa [CMD_ASYNC] para comandos que no terminen (servidores). {steps[0].get('desc', '')}"

                    project_manager.start_project(goal, steps)

                    msg = f"🚀 PROYECTO INICIADO: {goal}"
                    notify_progress(msg, "info")
                    results.append(msg)
                    
                    # Auto-trigger first step (with plan context)
                    first_step = project_manager.get_current_step()
                    if first_step:
                        notify_progress(f"📍 Fase 1: {first_step.title}", "info")
                        from agents import cerebro # type: ignore
                        next_task = f"ESTÁS EN UN PROYECTO: {goal}.\nPASO 1: {first_step.title}.\nINSTRUCCIÓN: {first_step.description}"
                        res = cerebro.run(next_task, "System", agent_mode="os")
                        return intercept_and_execute(res, auto_healer_agent)
            else:
                results.append("[ERR] Estructura JSON no encontrada en el plan.")
        except Exception as e:
            results.append(f"[ERR] Error en motor Synapse (Parse): {e}")

    # 2. Document Generation: [DOC: tipo=pdf titulo="Mi Doc"]contenido[/DOC]
    doc_matches = re.findall(r'\[DOC:\s*(.*?)\](.*?)\[/DOC\]', text, re.DOTALL)
    for m_tuple in doc_matches:
        try:
            meta, content = m_tuple # type: ignore
            from .document_engine import create_pdf, create_docx # type: ignore
            tipo = "pdf"  # default
            titulo = "Documento Orunex"
            tipo_m = re.search(r'tipo\s*=\s*(\w+)', meta)
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']?(.*?)["\']?\s*$', meta)
            if tipo_m: tipo = tipo_m.group(1).lower()
            if titulo_m: titulo = titulo_m.group(1).strip()
            
            if tipo == "docx":
                path = create_docx(titulo, content.strip())
            else:
                path = create_pdf(titulo, content.strip())
            msg = f" Documento generado: {os.path.basename(path)}"
            results.append(
                f"{msg}\n[WIDGET: {path}]\n[ARTIFACT: {path}|{tipo}|{titulo}]"
            )
            notify_progress(msg, "success")
        except Exception as e:
            results.append(f"[ERR] Error generando documento: {e}")
            
    # 2.1 Universal Document Engine: [EXCEL:], [CSV:], [MD:], [HTML:]
    excel_matches = re.findall(r'\[EXCEL:\s*(.*?)\](.*?)\[/EXCEL\]', text, re.DOTALL)
    for e_tuple in excel_matches:
        try:
            meta, content = e_tuple # type: ignore
            from .document_engine import create_excel # type: ignore
            titulo = "Datos Orunex"
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']?(.*?)["\']?\s*$', meta)
            if titulo_m: titulo = titulo_m.group(1).strip()
            path = create_excel(titulo, content.strip())
            results.append(
                f" Excel generado en tu entorno.\n[WIDGET: {path}]"
                f"\n[ARTIFACT: {path}|xlsx|{titulo}]"
            )
        except Exception as e:
            results.append(f"[ERR] Error generando Excel: {e}")

    csv_matches = re.findall(r'\[CSV:\s*(.*?)\](.*?)\[/CSV\]', text, re.DOTALL)
    for c_tuple in csv_matches:
        try:
            meta, content = c_tuple # type: ignore
            from .document_engine import create_csv # type: ignore
            titulo = "Datos Orunex"
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']?(.*?)["\']?\s*$', meta)
            if titulo_m: titulo = titulo_m.group(1).strip()
            path = create_csv(titulo, content.strip())
            results.append(
                f" CSV generado en tu entorno.\n[WIDGET: {path}]"
                f"\n[ARTIFACT: {path}|csv|{titulo}]"
            )
        except Exception as e:
            results.append(f"[ERR] Error generando CSV: {e}")

    md_matches = re.findall(r'\[MD:\s*(.*?)\](.*?)\[/MD\]', text, re.DOTALL)
    for m_xtra in md_matches:
        try:
            meta, content = m_xtra # type: ignore
            from .document_engine import create_md # type: ignore
            titulo = "Documento Markdown"
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']?(.*?)["\']?\s*$', meta)
            if titulo_m: titulo = titulo_m.group(1).strip()
            path = create_md(titulo, content.strip())
            results.append(
                f"[TASK] Markdown generado en tu entorno.\n[WIDGET: {path}]"
                f"\n[ARTIFACT: {path}|md|{titulo}]"
            )
        except Exception as e:
            results.append(f"[ERR] Error generando MD: {e}")

    # 2.5 App Auto-Integration Engine: [APP_HOOK: App="Chrome" Action="navigate" Value="url"]
    app_hook_matches = re.findall(
        r'\[APP_HOOK:\s*App=["\'](.*?)["\'][,\s]*Action=["\'](.*?)["\'][,\s]*Value=["\'](.*?)["\']\]',
        text, re.IGNORECASE
    )
    for app_name, action, value in app_hook_matches:
        try:
            from . import app_integrator as app_int # type: ignore
            if not perms.check_permission("APP_HOOK", f"{app_name}:{action}"): continue # type: ignore
            hook_result = app_int.integrate(app_name, action, value)
            results.append(f" App Auto-Integration '{app_name}':\n{hook_result}")
        except Exception as e:
            results.append(f"[ERR] Error en App Auto-Integration: {e}")

    # 2.6 Self-Evolution Sandbox: [SELF_EVOLVE] or [SELF_EVOLVE: module]
    self_evolve_bg = re.findall(r'\[SELF_EVOLVE(?::\s*([\w.]+))?\]', text, re.IGNORECASE)
    if self_evolve_bg:
        try:
            from . import self_evolver as evolver # type: ignore
            for match in self_evolve_bg:
                target_mod = match.strip() if match else None
                label = f" (modulo: {target_mod})" if target_mod else " (analisis global)"
                results.append(f"[DNA] Self-Evolution Sandbox activado{label}...")
                # Run in background to avoid blocking the UI
                bg_msg = evolver.run_evolution_background(target_mod)
                results.append(bg_msg)
        except Exception as e:
            results.append(f"[ERR] Error en Self-Evolution: {e}")

    html_matches = re.findall(r'\[HTML:\s*(.*?)\](.*?)\[/HTML\]', text, re.DOTALL)
    for h_tuple in html_matches:
        try:
            meta, content = h_tuple # type: ignore
            from .document_engine import create_html # type: ignore
            titulo = "Pagina Orunex"
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']?(.*?)["\']?\s*$', meta)
            if titulo_m: titulo = titulo_m.group(1).strip()
            path = create_html(titulo, content.strip())
            results.append(
                f" HTML generado en tu entorno.\n[WIDGET: {path}]"
                f"\n[ARTIFACT: {path}|html|{titulo}]"
            )
        except Exception as e:
            results.append(f"[ERR] Error generando HTML: {e}")

    # 2.1 WhatsApp Automation: [WHATSAPP_SEND: contacto_o_numero | mensaje]
    wa_matches = re.findall(r'\[WHATSAPP_SEND:\s*(.*?)\s*\|\s*(.*?)\]', text, re.DOTALL)
    for target, msg in wa_matches:
        try:
            from .whatsapp_master import send_whatsapp_message
            notify_progress(f"💬 Abriendo WhatsApp Web para enviar mensaje a '{target}'...", "info")
            res = send_whatsapp_message(target.strip(), msg.strip())
            results.append(f"💬 WhatsApp: {res.get('detail')}")
            notify_progress(f"✅ Mensaje de WhatsApp enviado a '{target}'.", "success")
        except Exception as e:
            results.append(f"[ERR] Error al enviar WhatsApp: {e}")

    # 2.2 System Power Control: [SYSTEM_POWER: shutdown] o [SYSTEM_POWER: restart]
    sys_matches = re.findall(r'\[SYSTEM_POWER:\s*(shutdown|restart|apagar|reiniciar)\]', text, re.IGNORECASE)
    for action in sys_matches:
        try:
            act_lower = action.lower()
            if act_lower in ["shutdown", "apagar"]:
                notify_progress("⚠️ Apagando el equipo en 5 segundos...", "warning")
                subprocess.Popen(
                    "shutdown /s /t 5 /c \"Apagado solicitado por Orunex\"",
                    shell=True,
                    **_hidden_process_kwargs(),
                )
                results.append("🔴 El sistema se apagara en 5 segundos.")
            elif act_lower in ["restart", "reiniciar"]:
                notify_progress("⚠️ Reiniciando el equipo en 5 segundos...", "warning")
                subprocess.Popen(
                    "shutdown /r /t 5 /c \"Reinicio solicitado por Orunex\"",
                    shell=True,
                    **_hidden_process_kwargs(),
                )
                results.append("🔄 El sistema se reiniciara en 5 segundos.")
        except Exception as e:
            results.append(f"[ERR] Error al ejecutar comando de energia: {e}")
    
    # 3. Presentation Generation: [PPTX: titulo="Mi Presentacion" theme="dark" accent="#FF0000"]slides[/PPTX]
    pptx_matches = re.findall(r'\[PPTX:\s*(.*?)\](.*?)\[/PPTX\]', text, re.DOTALL)
    for p_tuple in pptx_matches:
        try:
            meta, content = p_tuple # type: ignore
            from .document_engine import create_pptx # type: ignore
            titulo = "Presentacion Orunex"
            theme_val = "dark"
            accent_val = "#00E5FF"
            
            titulo_m = re.search(r't[ii]tulo\s*=\s*["\']([^"\']+)["\']', meta)
            theme_m = re.search(r'theme\s*=\s*["\']([^"\']+)["\']', meta)
            accent_m = re.search(r'accent\s*=\s*["\']([^"\']+)["\']', meta)
            
            if titulo_m: titulo = titulo_m.group(1).strip()
            if theme_m: theme_val = theme_m.group(1).strip()
            if accent_m: accent_val = accent_m.group(1).strip()
            
            # notify_progress at start
            notify_progress("Generando Presentacion Maestra con Orunex Designer...", "info")
            
            # Phase 113: DO NOT strip layout tags here, document_engine needs them
            clean_content = content.strip() 
            path = create_pptx(titulo, clean_content, theme=theme_val, accent_color=accent_val)
            msg = f" Presentacion Master generada: {os.path.basename(path)}"
            results.append(f"{msg}\n[ARTIFACT: {path}|pptx|{titulo}]")
            notify_progress(msg, "success")
            try: 
                if hasattr(os, "startfile"): os.startfile(path) # type: ignore
            except: pass
        except Exception as e:
            results.append(f"[ERR] Error critico disenando PPTX: {e}")
            
    # 4. File Editing: [EDIT: file.py]---BUSCAR---old---REEMPLAZAR---new[/EDIT]
    edit_matches = re.findall(r'\[EDIT:\s*(.*?)\](.*?)\[/EDIT\]', text, re.DOTALL)
    edited_files = []
    for filepath, content in edit_matches:
        try:
            if not perms.check_permission("EDIT", filepath.strip(), auto_healer_agent): continue
            filepath = filepath.strip()
            # Si dan una ruta absoluta que existe
            if os.path.exists(filepath): # type: ignore
                safe_path = filepath
            else:
                # Intentar relativa a orunex_outputs
                safe_path = os.path.abspath(os.path.join(base_dir, filepath)) # type: ignore
            
            if not os.path.exists(safe_path):
                # --- AUTO HEALER BUSQUEDA PROFUNDA ---
                found_path = None
                search_filename = os.path.basename(filepath)
                # Buscar en todo el entorno actual
                for root, dirs, files in os.walk(os.getcwd()):
                    if search_filename in files:
                        found_path = os.path.join(root, search_filename)
                        break
                
                if found_path:
                    safe_path = found_path
                    results.append(f" Auto-Healer: Ruta original invalida, pero archivo encontrado en: {safe_path}")
                else:
                    results.append(f"[ERR] Error: El archivo a editar ({filepath}) no existe ni siquiera tras busqueda profunda.")
                    continue
                # --- FIN AUTO HEALER ---
                
            parts = re.split(r'---REEMPLAZAR---', content)
            if len(parts) != 2: continue
            
            buscar = re.sub(r'^---BUSCAR---\s*', '', parts[0]).strip()
            reemplazar = parts[1].strip()
            
            with open(safe_path, "r", encoding="utf-8") as f: # type: ignore
                file_text = f.read()
                
            if buscar in file_text:
                new_text = file_text.replace(buscar, reemplazar)
                with open(safe_path, "w", encoding="utf-8") as f: # type: ignore
                    f.write(new_text)
                edited_files.append(filepath)
                # Anadir marca especial para la IDE
                results.append(f"[TASK] Archivo modificado: {filepath}\n[IDE_RELOAD:{safe_path}]")
            else:
                results.append(f"[WARN] No se encontro el bloque exacto en: {filepath}")
        except Exception as e:
            results.append(f"[ERR] Error editando {filepath}: {e}")
            
    # 2. Borrado de Archivos: [DEL: archivo.txt]
    del_matches = re.findall(r'\[DEL:\s*(.*?)\]', text)
    for filepath in del_matches:
        try:
            if not perms.check_permission("DEL", filepath.strip(), auto_healer_agent): continue
            filepath = filepath.strip()
            if os.path.exists(filepath): # type: ignore
                safe_path = filepath
            else:
                safe_path = os.path.abspath(os.path.join(base_dir, filepath)) # type: ignore
                
            if os.path.exists(safe_path): # type: ignore
                os.remove(safe_path) # type: ignore
                results.append(f"[CLEAR] Archivo eliminado: {filepath}")
            else:
                results.append(f"[WARN] DEL: No se encontro el archivo {filepath}")
        except Exception as e:
            results.append(f"[ERR] Error al eliminar {filepath}: {e}")
            
    if edited_files:
        pass # Message handled above
        
    # Phase 21.0: SOVEREIGN NATIVE LOOPS [LOOP: count=N][TAG: ...][/LOOP] (V43.13)
    loop_matches = re.findall(r'\[LOOP:\s*count=(\d+)\](.*?)\[/LOOP\]', text, re.IGNORECASE | re.DOTALL)
    for count_str, content in loop_matches:
        count = int(count_str)
        notify_progress(f"🔄 Iniciando bucle soberano: {count} repeticiones.", "info")
        for i in range(1, count + 1):
             # Inject the index into the content if needed
             indexed_content = content.replace("{i}", str(i))
             loop_res = intercept_and_execute(indexed_content)
             results.append(f"Loop {i}/{count}: {loop_res}")

    # Phase 22.0: FILE CHUNKING [FILE_CHUNK: file=... start=X end=Y] (V43.13)
    chunk_matches = re.findall(r'\[FILE_CHUNK:\s*file=(.*?)\s*start=(\d+)\s*end=(\d+)\]', text, re.IGNORECASE)
    for filepath, start, end in chunk_matches:
        try:
            p_clean = filepath.strip().rstrip('.,;!?')
            if not os.path.exists(p_clean):
                 results.append(f"[ERR] Archivo no encontrado: {p_clean}")
                 continue
            with open(p_clean, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                chunk = "".join(lines[int(start)-1:int(end)])
                results.append(f"[CHUNK {start}-{end}]:\n{chunk}")
        except Exception as e:
            results.append(f"[ERR] Error leyendo fragmento: {e}")

    # 6. Tareas Programadas Autonomas (Daemon L3)
    schedule_matches = re.findall(r'\[SCHEDULE:\s*(.*?)\](.*?)\[/SCHEDULE\]', text, re.DOTALL)
    for s_tuple in schedule_matches:
        try:
            meta, content = s_tuple # type: ignore
            from .automation_daemon import get_daemon # type: ignore
            freq_match = re.search(r'frecuencia\s*=\s*["\']?(.*?)["\']?(?:\s|$)', meta)
            time_match = re.search(r'hora\s*=\s*["\']?(.*?)["\']?(?:\s|$)', meta)
            
            freq = freq_match.group(1).strip() if freq_match else "diario"
            time_str = time_match.group(1).strip() if time_match else ""
            
            d = get_daemon()
            cmd = content.strip()
            if d.add_task(cmd, freq, time_str):
                results.append(f" Automatizacion reservada en el Kernel: {freq.upper()} {'a las '+time_str if time_str else ''}.")
            else:
                results.append(f"[ERR] Error al empalmar la tarea en el Daemon Cron.")
        except Exception as e:
            results.append(f"[ERR] Error interno Daemon: {e}")
        
    # 7. Autoreconstruccion Evolutiva (P2P - Phase 92)
    # [SELF_RECONSTRUCT: file.py] content [/SELF_RECONSTRUCT]
    reconstruct_matches = re.findall(r'\[SELF_RECONSTRUCT:\s*(.*?)\](.*?)\[/SELF_RECONSTRUCT\]', text, re.DOTALL)
    for r_tuple in reconstruct_matches:
        try:
            filename, content = r_tuple # type: ignore
            filename = filename.strip()
            # Seguridad: Solo archivos dentro del proyecto
            abs_path = os.path.abspath(filename)
            if not abs_path.startswith(os.getcwd()):
                results.append(f" Seguridad: Bloqueada reconstruccion fuera del Kernel ({filename}).")
                continue
                
            # Guardar propuesta en archivo temporal .patch
            patch_path = abs_path + ".patch"
            with open(patch_path, "w", encoding="utf-8") as f:
                f.write(content.strip())
            
            results.append(f"[DNA] EVOLUCION DETECTADA: He disenado un parche para `{os.path.basename(filename)}`.")
            results.append(f"[WARN] CONFIRMACION REQUERIDA: Responde con `!si` o haz click en 'APROBAR' en la UI para aplicar los cambios.")
        except Exception as e:
            results.append(f"[ERR] Error en Motor Evolutivo: {e}")
    if not results and re.search(r'\[[A-Z_]+:.*?\]', text):
        results.append("Lo siento, intenta de nuevo.")
        
    # V43.0 SYNAPSE: Post-Execution Autonomous Loop (V43.3 Infallibility)
    from . import project_manager # type: ignore
    if project_manager.is_project_active():
        current_step = project_manager.get_current_step()
        if current_step:
            # Step Completion Logic
            outcome = "\n".join(results)
            
            # V43.3: INFALLIBILITY AUTO-CORRECTION BRIDGE
            if "[ERR]" in outcome or "Error" in outcome:
                 msg = f"⚠️ [SYNAPSE HEALER] Error detectado en '{current_step.title}'. Intentando auto-corrección..."
                 notify_progress(msg, "warning")
                 
                 # Invoke Healer Agent
                 from .auto_healer import heal_command # type: ignore
                 healed_resp = heal_command(text, outcome) # Try to heal the last command
                 
                 # Re-execute the healed command once (Corrected parameter type V43.4)
                 healed_outcome = intercept_and_execute(healed_resp, auto_healer_agent="cerebro")
                 outcome = f"{outcome}\n[POST-HEALING]:\n{healed_outcome}"
                 
            project_manager.mark_step_success(outcome)

            
            next_step = project_manager.get_current_step()
            if next_step:
                msg = f"✅ Paso '{current_step.title}' completado (o corregido). Avanzando a: {next_step.title}"
                notify_progress(msg, "info")
                
                from agents import cerebro # type: ignore
                prompt_loop = f"OBJETIVO GLOBAL: {project_manager.ACTIVE_PROJECT.goal}\nESTADO ACTUAL: {project_manager.get_full_context()}\n\n"
                prompt_loop += f"Paso anterior '{current_step.title}' finalizado. Resultado: {outcome[:300]}\n\nAHORA PROCEDE CON EL SIGUIENTE PASO: {next_step.title}. {next_step.description}"
                ai_resp = cerebro.run(prompt_loop, "System", agent_mode="os")
                
                # RECURSIVE SYNAPSE LOOP
                loop_res = intercept_and_execute(ai_resp, auto_healer_agent)
                results.append(loop_res)
            else:
                msg = "🏁 [SYNAPSE] PROYECTO FINALIZADO CON INFALIBILIDAD."
                notify_progress(msg, "success")
                results.append(msg)
                project_manager.ACTIVE_PROJECT = None # Close session

    if results:
        # Phase 40.6: SMART STATUS REPORT
        has_errors = any("[ERR]" in str(r) or "Error" in str(r) for r in results)
        status_header = "\n\n[ SISTEMA ORUNEX: REPORTE DE INCIDENCIAS]\n" if has_errors else "\n\n[ SISTEMA ORUNEX: ACCIONES AUTONOMAS]\n"
        
        # Limpiar etiquetas procesadas para que el usuario no vea el codigo bruto
        tags_to_clean = r'\[/?(?:FILE|CMD|DOC|PPTX|EDIT|MKDIR|SEARCH_WEB|OPEN_URL|GUI_NAVIGATE|DEL|LOOP|WATCH|CALL|TITLE|MOD|SCHEDULE|GET_WINDOWS_STATE|GUI_SEE|GUI_CLICK|GUI_TYPE|UIA_CLICK|ADDR|SELF_RECONSTRUCT|MISSION|OFFICE_MISSION|UI_CLEAN|VSCODE|PROJECT_PLAN|ARTIFACT):.*?\]'
        clean_text = re.sub(tags_to_clean, '', text, flags=re.DOTALL)
        clean_text = re.sub(r'\[/?(?:MISSION|OFFICE_MISSION|UI_CLEAN|VSCODE)\]', '', clean_text, flags=re.DOTALL)
        
        final_msg = clean_text.strip() + status_header + "\n".join(results)
        
        # Phase 40.6: Anti-False-Positive
        if not has_errors:
            final_msg += "\n\n[+] Tarea ejecutada con éxito."
        else:
            final_msg += "\n\n[!] Se detectaron errores técnicos. Revisa el reporte superior."
            
        return final_msg
        
    return text

