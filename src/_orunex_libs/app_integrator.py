"""
app_integrator.py  App Auto-Integration Engine (Phase 47)
Orunex ahora puede "enchufarse" a aplicaciones abiertas e inyectar
comportamiento autonomo usando COM, Named Pipes, stdin, o WebSocket.

Tags soportados:
  [APP_HOOK: App="Chrome" Action="navigate" Value="https://..."]
  [APP_HOOK: App="Notepad" Action="type" Value="Hola mundo"]
  [APP_HOOK: App="Excel" Action="set_cell" Value="A1=123"]
  [APP_HOOK: App="custom" Action="send_stdin" Value="comando"]
"""
import subprocess
import os
import re
import time

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import uiautomation as auto
except Exception:
    auto = None


def _hidden_process_kwargs():
    """Keep helper commands silent instead of opening a black console."""
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
        }
    return {}

# 
# REGISTRO DE INTEGRACIONES NATIVAS (por nombre de app normalizado)
# 
APP_ALIASES = {
    "chrome":    ["chrome", "google chrome"],
    "edge":      ["msedge", "microsoft edge"],
    "firefox":   ["firefox"],
    "notepad":   ["notepad", "bloc de notas"],
    "explorer":  ["explorer", "file explorer", "explorador"],
    "excel":     ["excel", "microsoft excel"],
    "word":      ["word", "microsoft word"],
    "powerpoint":["powerpoint", "microsoft powerpoint"],
    "vscode":    ["code", "visual studio code"],
    "cmd":       ["cmd", "simbolo del sistema"],
    "powershell":["powershell"],
    "obs":       ["obs studio"],
    "spotify":   ["spotify"],
    "discord":   ["discord"],
    "whatsapp":  ["whatsapp", "wasap"],
    "navegador": ["navegador", "browser", "internet"],
    "explorador":["explorador", "archivos", "carpetas", "explorer"],
    "calc":      ["calc", "calculadora"],
    "taskmgr":   ["taskmgr", "administrador de tareas", "tareas"],
}

def normalize_app_name(app: str) -> str:
    """Devuelve el nombre de app normalizado para comparacion."""
    al = app.lower().strip()
    for key, aliases in APP_ALIASES.items():
        if any(alias in al for alias in aliases):
            return key
    return al

def find_app_window(app_name: str):
    """Intentar obtener el control de ventana de la app con UIAutomation."""
    if auto is None:
        return None
    try:
        win = auto.WindowControl(Name=app_name, searchDepth=2)
        if win.Exists(2, 1):
            win.SetFocus()
            return win
        # Busqueda parcial
        for w in auto.GetRootControl().GetChildren():
            if app_name.lower() in w.Name.lower():
                w.SetFocus()
                return w
    except Exception:
        pass
    return None

def hook_browser(app_key: str, action: str, value: str) -> str:
    """Auto-integracion especializada para navegadores."""
    if pyautogui is None:
        return "[ERR] pyautogui no disponible"
    
    # Focus browser via command
    if app_key == "chrome":
        subprocess.Popen(
            ["start", "chrome"], shell=True, **_hidden_process_kwargs()
        )
    elif app_key == "edge":
        subprocess.Popen(
            ["start", "msedge"], shell=True, **_hidden_process_kwargs()
        )
    elif app_key == "firefox":
        subprocess.Popen(
            ["start", "firefox"], shell=True, **_hidden_process_kwargs()
        )
    elif app_key == "navegador":
        # Phase 12.7: Launch default system browser via URL
        subprocess.Popen(
            ["start", "https://www.google.com"],
            shell=True,
            **_hidden_process_kwargs(),
        )
    time.sleep(1.2)
    
    if action == "navigate":
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.3)
        pyautogui.typewrite(value, interval=0.02)
        pyautogui.press('return')
        return f" Navegador: yendo a '{value}'"
    elif action == "new_tab":
        pyautogui.hotkey('ctrl', 't')
        time.sleep(0.4)
        pyautogui.typewrite(value, interval=0.02)
        pyautogui.press('return')
        return f" Navegador: nueva pestana  '{value}'"
    elif action == "find":
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.3)
        pyautogui.typewrite(value, interval=0.02)
        return f" Buscar en pagina: '{value}'"
    elif action == "close_tab":
        pyautogui.hotkey('ctrl', 'w')
        return f"[ERR] Pestana cerrada."
    return f"[WARN] Accion '{action}' no reconocida para navegador."

def hook_office(app_key: str, action: str, value: str) -> str:
    """Auto-integracion para apps de Office via COM (si disponible)."""
    if action == "open":
        if os.path.exists(value):
            os.startfile(value)
            return f" {app_key.capitalize()} abrio: {value}"
        return f"[WARN] Archivo no encontrado: {value}"
    
    if action == "set_cell" and app_key == "excel":
        try:
            import win32com.client
            xl = win32com.client.GetActiveObject("Excel.Application")
            sheet = xl.ActiveSheet
            m = re.match(r"(\w+)\s*=\s*(.*)", value)
            if m:
                cell, val = m.group(1), m.group(2)
                sheet.Range(cell).Value = val
                return f" Excel: celda {cell} = '{val}'"
        except Exception as e:
            return f"[ERR] Error COM Excel: {e}"
    
    if action == "type":
        if pyautogui:
            pyautogui.typewrite(value, interval=0.02)
            return f" {app_key.capitalize()}: texto escrito."
    return f"[WARN] Accion '{action}' no reconocida para {app_key}."

def hook_discord(action: str, value: str) -> str:
    """Integracion via Discord Webhook o Browser."""
    if "http" in value:
        import requests
        try:
            requests.post(value, json={"content": "Orunex Bridge Active."})
            return f" Discord: Webhook enviado a {value[:30]}..."
        except:
            return f"[ERR] Discord Webhook fallo."
    return hook_browser("chrome", "navigate", "https://discord.com/app")

def hook_whatsapp(action: str, value: str) -> str:
    """Integracion via WhatsApp Web."""
    return hook_browser("chrome", "navigate", "https://web.whatsapp.com/")

def hook_terminal(app_key: str, action: str, value: str) -> str:
    """Auto-integracion para terminales (CMD, PowerShell)."""
    if action == "run":
        try:
            result = subprocess.run(
                value,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                **_hidden_process_kwargs(),
            )
            out = (result.stdout or result.stderr or "").strip()[:500]
            return f"[IDE] Terminal ejecuto:\n{out}"
        except Exception as e:
            return f"[ERR] Error en terminal hook: {e}"
    return f"[WARN] Accion terminal '{action}' no reconocida."

# 
# API PRINCIPAL: integrate(tag_text)
# 
def integrate(app: str, action: str, value: str) -> str:
    """
    Punto de entrada del motor de App Auto-Integration.
    app: nombre legible de la app (Chrome, Excel, etc.)
    action: accion a ejecutar (navigate, set_cell, type, run, etc.)
    value: contenido del parametro
    """
    app_key = normalize_app_name(app)
    results = []
    
    # Navegadores
    if app_key in ("chrome", "edge", "firefox"):
        results.append(hook_browser(app_key, action, value))

    # Discord
    elif app_key == "discord":
        results.append(hook_discord(action, value))

    # WhatsApp
    elif app_key == "whatsapp":
        results.append(hook_whatsapp(action, value))

    # Office
    elif app_key in ("excel", "word", "powerpoint"):
        results.append(hook_office(app_key, action, value))

    # Terminal
    elif app_key in ("cmd", "powershell"):
        results.append(hook_terminal(app_key, action, value))

    # Generico: abrir cualquier exe/app
    elif action == "open":
        try:
            subprocess.Popen(
                app, shell=True, **_hidden_process_kwargs()
            )
            results.append(f"[EXE] App '{app}' lanzada.")
        except Exception as e:
            results.append(f"[ERR] Error lanzando '{app}': {e}")

    # Generico: type text into focused window
    elif action == "type":
        if pyautogui:
            win = find_app_window(app)
            if win:
                win.SetFocus()
                time.sleep(0.3)
            pyautogui.typewrite(value, interval=0.02)
            results.append(f" Texto inyectado en '{app}': '{value}'")
        else:
            results.append("[ERR] pyautogui no disponible para type generico.")

    # Generico: click on a named control inside the app
    elif action == "click_control":
        if auto:
            try:
                ctrl = auto.Control(Name=value, searchDepth=8)
                if ctrl.Exists(3, 1):
                    ctrl.Click()
                    results.append(f"[EXE] Control '{value}' en '{app}' presionado (Matrix Vision).")
                else:
                    results.append(f"[WARN] Control '{value}' no encontrado en '{app}'.")
            except Exception as e:
                results.append(f"[ERR] Error al integrar control: {e}")
        else:
            results.append("[ERR] uiautomation no disponible.")
    else:
        results.append(f"[WARN] Accion '{action}' no reconocida para app '{app}'.")

    return "\n".join(results) if results else f"[WARN] No se pudo integrar con '{app}'."
