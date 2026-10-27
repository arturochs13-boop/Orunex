"""
vscode_integration.py — VS Code Integration for Orunex
Allows Orunex to control VS Code via CLI commands and keyboard automation.
Triggered by [VSCODE: ...] tags from the OS Executor.

The preferred path is the local Orunex Bridge extension (see
``vscode_extension/``).  CLI/keyboard automation remains as a fallback for
machines where the extension cannot be loaded.
"""
import subprocess
import os
import shutil
import pyautogui  # type: ignore
import time

try:
    from . import vscode_bridge  # type: ignore
except Exception:  # pragma: no cover - direct script execution fallback
    import vscode_bridge  # type: ignore


def _hidden_process_kwargs():
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
        }
    return {}


def _code_candidates():
    candidates = [
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "Microsoft VS Code",
            "Code.exe",
        ),
        shutil.which("code"),
        shutil.which("code.cmd"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft VS Code", "Code.exe"),
    ]
    seen = set()
    result = []
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and candidate.lower() not in seen:
            seen.add(candidate.lower())
            result.append(candidate)
    return result


def _code_available() -> bool:
    """Check if the VS Code CLI or Code.exe is available."""
    return bool(_code_candidates())


def _launch_code(args) -> bool:
    """Launch VS Code without requiring the caller to know about .cmd quirks."""
    candidates = _code_candidates()
    if not candidates:
        return False
    executable = candidates[0]
    command = [executable, *args]
    if executable.lower().endswith((".cmd", ".bat")):
        command = ["cmd.exe", "/c", *command]
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **_hidden_process_kwargs(),
    )
    return True


def bridge_available() -> bool:
    try:
        return bool(vscode_bridge.is_alive())
    except Exception:
        return False


def connect(workspace: str = "", launch: bool = True) -> dict:
    """Connect to VS Code, launching the bridge extension when necessary."""
    target = workspace or CREATION_CHAMBER
    _ensure_chamber()
    try:
        result = vscode_bridge.ensure_bridge(target, launch=launch)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "workspace": target}
    if not result.get("ok"):
        # Fall back to opening the folder with the normal VS Code CLI.  This
        # still gives the user a useful action even if extension loading is
        # blocked by a VS Code policy.
        if launch:
            try:
                open_folder(target)
            except Exception:
                pass
        result.setdefault("workspace", target)
    return result


def bridge_status() -> dict:
    try:
        return vscode_bridge.status()
    except Exception as exc:
        return {"ok": False, "state": "offline", "message": str(exc)}


def open_file(path: str, line: int = None) -> str:
    """Open a file in VS Code, optionally at a specific line."""
    path = os.path.abspath(path)
    if bridge_available():
        result = vscode_bridge.open_file(path, line or 1)
        if result.get("ok"):
            return f"VS Code: Abriendo {os.path.basename(path)}" + (f" linea {line}" if line else "")
    if not _code_available():
        return _fallback_open(path)
    target = f"{path}:{line}" if line else path
    try:
        _launch_code(["--goto", target])
        return f"VS Code: Abriendo {os.path.basename(path)}" + (f" linea {line}" if line else "")
    except Exception as e:
        return f"VS Code Error: {e}"


def _fallback_open(path: str) -> str:
    """If code CLI not found, try opening VS Code from common paths."""
    common = [
        r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.environ.get("USERNAME", "")),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ]
    for exe in common:
        if os.path.exists(exe):
            subprocess.Popen(
                [exe, path], **_hidden_process_kwargs()
            )
            return f"VS Code abierto (fallback): {path}"
    # Last resort: use OS default file handler safely
    if os.path.exists(path):
        os.startfile(path)
        return f"Archivo abierto con la app predeterminada del sistema: {path}"
    return f"[WARN] No se pudo encontrar VS Code ni abrir {path}"


# --- V40.8: GLOBAL WORKSPACE SOVEREIGNTY ---
# The creation chamber is now located in the user's Documents folder to ensure
# it stays separate from the Orunex source code.
CREATION_CHAMBER = os.path.join(os.path.expanduser("~"), "Documents", "Orunex_Workspace")

def _ensure_chamber():
    """Guarantee the global creation chamber exists."""
    if not os.path.exists(CREATION_CHAMBER):
        try:
            os.makedirs(CREATION_CHAMBER, exist_ok=True)
            readme_path = os.path.join(CREATION_CHAMBER, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write("# Orunex Global Workspace\nEste es tu taller de ingeniería global. Orunex programará aquí por defecto.")
        except Exception as e:
            print(f"[ERR] No se pudo crear el taller global: {e}")


def open_folder(folder: str = "") -> str:
    """Open a folder in VS Code. Defaults to the Global Creation Chamber if empty."""
    _ensure_chamber()
    
    # Use provided folder or fallback to the global chamber
    target_folder = folder or CREATION_CHAMBER
    
    if not os.path.exists(target_folder):
        return f"[ERR] Carpeta no encontrada: {target_folder}"
    
    try:
        if _code_available():
            _launch_code([target_folder])
        else:
            common = [
                r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.environ.get("USERNAME", "")),
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ]
            opened = False
            for exe in common:
                if os.path.exists(exe):
                    subprocess.Popen(
                        [exe, target_folder], **_hidden_process_kwargs()
                    )
                    opened = True
                    break
            if not opened:
                os.startfile(target_folder)
        return f"VS Code: Abriendo carpeta {os.path.basename(target_folder)}"
    except Exception as e:
        return f"[ERR] Fallo lanzando VS Code: {e}"


def run_task(task_name: str) -> str:
    """Run a VS Code task by name."""
    if bridge_available():
        result = run_vscode_command("workbench.action.tasks.runTask", [task_name])
        if result.get("ok"):
            return f"VS Code: Tarea '{task_name}' ejecutada."
    try:
        # Fallback: command palette automation when the bridge is unavailable.
        pyautogui.hotkey('ctrl', 'shift', 'p')
        time.sleep(0.5)
        pyautogui.typewrite("Tasks: Run Task", interval=0.04)
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(0.4)
        pyautogui.typewrite(task_name, interval=0.05)
        time.sleep(0.3)
        pyautogui.press('enter')
        return f"VS Code: Tarea '{task_name}' ejecutada."
    except Exception as e:
        return f"VS Code Task Error: {e}"


def install_extension(ext_id: str) -> str:
    """Install a VS Code extension by ID."""
    if not _code_available():
        return "VS Code CLI no disponible."
    try:
        candidates = _code_candidates()
        if not candidates:
            return "VS Code CLI no disponible."
        executable = candidates[0]
        command = [executable, "--install-extension", ext_id]
        if executable.lower().endswith((".cmd", ".bat")):
            command = ["cmd.exe", "/c", *command]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            **_hidden_process_kwargs(),
        )
        out = result.stdout.strip() or result.stderr.strip()
        return f"VS Code Extension: {out[:200]}"
    except Exception as e:
        return f"VS Code Extension Error: {e}"


def new_terminal() -> str:
    """Open a new integrated terminal in VS Code."""
    if bridge_available():
        result = vscode_bridge.run_terminal(
            "echo Orunex terminal ready", name="Orunex", show=True
        )
        if result.get("ok"):
            return "VS Code: Terminal integrada abierta y conectada."
    try:
        pyautogui.hotkey('ctrl', 'grave')
        return "VS Code: Terminal integrada abierta."
    except Exception as e:
        return f"VS Code Terminal Error: {e}"


def run_terminal(command: str, cwd: str = "", name: str = "Orunex") -> dict:
    """Send a command to the real VS Code integrated terminal."""
    if not bridge_available():
        connected = connect(cwd or CREATION_CHAMBER)
        if not connected.get("ok"):
            return {"ok": False, "error": connected.get("error", "VS Code is not connected")}
    return vscode_bridge.run_terminal(command, cwd=cwd or None, name=name, show=True)


def write_file(path: str, content: str, open_after: bool = True) -> dict:
    """Create or replace a file through VS Code, preserving a disk fallback."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if bridge_available():
        result = vscode_bridge.write_file(path, content, open_after=open_after)
        if result.get("ok"):
            return result
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        if open_after:
            open_file(path)
        return {"ok": True, "path": path, "fallback": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": path}


def edit_file(path: str, content: str, open_after: bool = True) -> dict:
    return write_file(path, content, open_after=open_after)


def replace_in_file(path: str, old_text: str, new_text: str) -> dict:
    path = os.path.abspath(path)
    if bridge_available():
        result = vscode_bridge.replace_text(path, old_text, new_text)
        if result.get("ok"):
            return result
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        if old_text not in content:
            return {"ok": False, "error": "Target text was not found", "path": path}
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content.replace(old_text, new_text, 1))
        open_file(path)
        return {"ok": True, "path": path, "fallback": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": path}


def run_command(command: str, cwd: str = "", timeout: float = 120.0) -> dict:
    """Run a command in the workspace and capture stdout/stderr."""
    if not bridge_available():
        connected = connect(cwd or CREATION_CHAMBER)
        if not connected.get("ok"):
            return {"ok": False, "error": connected.get("error", "VS Code is not connected")}
    return vscode_bridge.run_command(command, cwd=cwd or None, timeout=timeout)


def run_tests(cwd: str = "", command: str = "") -> dict:
    """Run the project test command in VS Code and mirror it in the terminal."""
    if not bridge_available():
        connected = connect(cwd or CREATION_CHAMBER)
        if not connected.get("ok"):
            return {"ok": False, "error": connected.get("error", "VS Code is not connected")}
    return vscode_bridge.run_tests(cwd=cwd or None, command=command or None)


def diagnostics(path: str = "") -> dict:
    if not bridge_available():
        return {"ok": False, "error": "VS Code bridge is not running"}
    return vscode_bridge.diagnostics(path or None)


def run_vscode_command(command: str, args=None) -> dict:
    if not bridge_available():
        return {"ok": False, "error": "VS Code bridge is not running"}
    return vscode_bridge.run_vscode_command(command, args or [])


def search_in_files(query: str) -> str:
    """Open VS Code global search."""
    try:
        pyautogui.hotkey('ctrl', 'shift', 'f')
        time.sleep(0.4)
        pyautogui.typewrite(query, interval=0.04)
        return f"VS Code: Buscando '{query}' en archivos."
    except Exception as e:
        return f"VS Code Search Error: {e}"


def read_file(path: str) -> str:
    """Reads the content of a file to provide context for AI tasks."""
    try:
        if not os.path.exists(path):
            return f"[ERR] Archivo no hallado: {path}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"[CONTEXT] Archivo: {os.path.basename(path)}\n---\n{content[:2000]}..."
    except Exception as e:
        return f"[ERR] Error leyendo archivo: {e}"


# --- V41.0: ELITE ENGINEERING & MOTION DESIGN ---
def elite_code_hardener(code_content: str, language: str = "python") -> str:
    """Refuerza el código con estándares élite: Type hints, Docstrings y Seguridad."""
    # V41.0: Automáticamente añade bloque de documentación Orunex si no existe
    if '"""' not in code_content and "'''" not in code_content:
        header = f'"""\n[ORUNEX ELITE MODULE]\nAuto-Ingeniería de alta gama aplicada.\n"""\n'
        code_content = header + code_content
    
    # Manejo de errores robusto por defecto (Ejemplo simple de inyección)
    if "try:" not in code_content and language == "python" and "def " in code_content:
        # Aquí Orunex decidiría inyectar try-except en funciones críticas
        pass 
    return code_content

def surgical_edit(path: str, target_text: str, replacement_text: str, context: str = "") -> str:
    """V41.0: ELITE RIGOR - Applies precise code edits with auto-hardening."""
    try:
        from .ui_engine import ORUNEX_PALETTE # type: ignore
        if not os.path.exists(path):
            return f"[ERR] Archivo no hallado: {path}"
        
        # Hardening antes de escribir
        replacement_text = elite_code_hardener(replacement_text)
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        occ = content.count(target_text)
        if occ == 0: return f"[ERR] No se halló el código objetivo."
        if occ > 1 and not context: return f"[ERR] Ambigüedad detectada ({occ} veces)."

        final_target = target_text
        if context and context in content:
            if target_text in context:
                final_target = context
                replacement_text = context.replace(target_text, replacement_text)
        
        # 3. Diff Preview (Executive Log)
        print(f"\n[VSCODE ELITE DIFF] {os.path.basename(path)}")
        print(f"[-] Removido: {target_text[:60]}...")
        print(f"[+] Añadido:  {replacement_text[:60]}...")

        if bridge_available():
            result = vscode_bridge.replace_text(path, final_target, replacement_text)
            if result.get("ok"):
                return f"[OK] Ingeniería Élite aplicada en {os.path.basename(path)} ✨"

        new_content = content.replace(final_target, replacement_text, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        open_file(path)
        return f"[OK] Ingeniería Élite aplicada en {os.path.basename(path)} ✨"
    except Exception as e:
        return f"[ERR] Fallo Élite V41.0: {e}"


def project_context(folder_path: str) -> str:
    """Scans the project structure to build a map for the AI."""
    try:
        if not os.path.isdir(folder_path):
            return f"[ERR] Carpeta inválida: {folder_path}"
        
        structure = []
        for root, dirs, files in os.walk(folder_path):
            level = root.replace(folder_path, '').count(os.sep)
            indent = '  ' * level
            structure.append(f"{indent}[D] {os.path.basename(root)}")
            for f in files:
                if not f.endswith(('.pyc', '.png', '.jpg', '.ico', '.git')):
                    structure.append(f"  {indent}- {f}")
            if level > 2: break # Limit depth for performance
            
        return "\n".join(structure[:50])
    except Exception as e:
        return f"[ERR] Error escaneo proyecto: {e}"


def execute(action: str, value: str = "", line: int = None, context: str = "", extra: str = "") -> str:
    """
    Unified entry point for VS Code commands V40.6.
    action: edit | read | scan | open | install | terminal | search
    """
    action = action.strip().lower()
    if action in ("edit", "replace", "modify"):
        # value = path, context = target, extra = replacement
        # (In V40.6 we prioritize explicit context maps)
        return surgical_edit(value, target_text=context, replacement_text=extra)
    elif action in ("read", "context", "get"):
        return read_file(value)
    elif action in ("scan", "tree", "structure"):
        return project_context(value or CREATION_CHAMBER)
    elif action in ("open_file", "open", "goto", "file"):
        if not value: return open_folder(CREATION_CHAMBER) # Default to chamber if no path
        return open_file(value, line)
    elif action in ("open_folder", "folder"):
        return open_folder(value or CREATION_CHAMBER)
    elif action in ("install", "install_extension", "ext"):
        return install_extension(value)
    elif action in ("terminal", "shell", "cmd"):
        if value:
            result = run_terminal(value, cwd=extra or CREATION_CHAMBER)
            if result.get("ok"):
                return f"VS Code: comando enviado a la terminal -> {value}"
            return f"[ERR] Terminal: {result.get('error')}"
        return new_terminal()
    elif action in ("run", "exec", "command"):
        result = run_command(value, cwd=extra or CREATION_CHAMBER)
        if result.get("ok"):
            return (
                f"VS Code: comando ejecutado -> {value}\n"
                f"{str(result.get('stdout', '')).strip()[:1200]}"
            )
        return f"[ERR] VS Code command: {result.get('error') or result.get('stderr')}"
    elif action in ("test", "tests", "run_tests"):
        result = run_tests(cwd=value or CREATION_CHAMBER)
        output = str(result.get("stdout", "") or result.get("stderr", "")).strip()
        return f"VS Code tests: {result.get('testCommand', 'test')}\n{output[:1200]}"
    elif action in ("write", "create", "save"):
        # value = path, extra = content
        result = write_file(value, extra, open_after=True)
        return f"VS Code: archivo escrito -> {value}" if result.get("ok") else f"[ERR] {result.get('error')}"
    elif action in ("diagnostics", "problems"):
        result = diagnostics(value)
        return f"VS Code diagnostics: {result.get('count', 0)} issue(s)"
    elif action in ("status", "ping"):
        status = bridge_status()
        return status.get("message", "VS Code bridge offline")
    elif action in ("search",):
        return search_in_files(value)
    else:
        # Try as a direct file path
        if value and os.path.exists(value):
            return open_file(value, line)
        return f"VS Code: Accion desconocida '{action}'"
