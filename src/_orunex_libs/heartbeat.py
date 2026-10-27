"""
heartbeat.py  Daemon proactivo de Orunex
Lee `heartbeat_tasks.md` y ejecuta tareas periodicas sin esperar ordenes del usuario.
"""
import threading
import time
import os
import re
from datetime import datetime, timedelta

TASKS_FILE = os.path.abspath(os.path.join(os.getcwd(), "heartbeat_tasks.md"))

_daemon_thread = None
_running = False
_agent_callback = None  # fn(task: str)  str
_notify_callback = None  # fn(text: str, category: str)


def set_callbacks(agent_fn, notify_fn):
    """Registra las funciones de ejecucion y notificacion."""
    global _agent_callback, _notify_callback
    _agent_callback = agent_fn
    _notify_callback = notify_fn


def start():
    """Inicia el daemon de heartbeat en un hilo separado."""
    global _running, _daemon_thread
    if _running:
        return False, "Heartbeat ya esta activo."
    _running = True
    _daemon_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _daemon_thread.start()
    _safe_notify(" Heartbeat Daemon activado.", "success")
    return True, "Heartbeat iniciado."


def stop():
    """Detiene el daemon de heartbeat."""
    global _running
    _running = False
    _safe_notify(" Heartbeat Daemon detenido.", "warning")
    return True, "Heartbeat detenido."


def is_running() -> bool:
    return _running


def _heartbeat_loop():
    """Bucle principal del daemon. Lee tasks y ejecuta segun intervalo."""
    task_last_run = {}  # {task_id: datetime}

    while _running:
        tasks = _load_tasks()
        now = datetime.now()

        for task in tasks:
            task_id = task["id"]
            interval = task.get("interval_minutes", 60)
            last = task_last_run.get(task_id)

            should_run = (
                last is None or
                (now - last) >= timedelta(minutes=interval)
            )

            if should_run and task.get("enabled", True):
                task_last_run[task_id] = now
                _execute_task(task)

        # Background Semantic Indexer (Orunex Recall)
        try:
            import _orunex_libs.semantic_search as semantic
            semantic.index_directory(os.path.abspath(os.path.join(os.getcwd(), "orunex_outputs")))
        except Exception:
            pass

        time.sleep(60)  # Check every 60 seconds


def _execute_task(task: dict):
    """Ejecuta una tarea del heartbeat y notifica el resultado."""
    name = task.get("name", "Tarea Anonima")
    command = task.get("command", "")
    if not command:
        return

    _safe_notify(f" Heartbeat ejecutando: {name}", "info")

    if _agent_callback:
        try:
            result = _agent_callback(command)
            _safe_notify(f"[OK] {name} completado.", "success")
        except Exception as e:
            _safe_notify(f"[ERR] Error en heartbeat '{name}': {e}", "error")


def _load_tasks() -> list:
    """Parsea heartbeat_tasks.md y retorna lista de tareas."""
    tasks = []
    if not os.path.exists(TASKS_FILE):
        _create_default_tasks_file()

    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse tasks in format:
        # ## Task Name
        # - interval: 60
        # - command: investiga noticias de tecnologia
        # - enabled: true
        blocks = re.split(r'^##\s+', content, flags=re.MULTILINE)
        for i, block in enumerate(blocks[1:], 1):  # Skip header
            lines = block.strip().split('\n')
            if not lines:
                continue
            task = {"id": f"task_{i}", "name": lines[0].strip()}
            for line in lines[1:]:
                m = re.match(r'-\s*(\w+):\s*(.+)', line.strip())
                if m:
                    key, val = m.group(1), m.group(2).strip()
                    if key == "interval":
                        task["interval_minutes"] = int(val)
                    elif key == "command":
                        task["command"] = val
                    elif key == "enabled":
                        task["enabled"] = val.lower() != "false"
            tasks.append(task)
    except:
        pass
    return tasks


def _create_default_tasks_file():
    """Crea un archivo de tareas de ejemplo."""
    content = """# heartbeat_tasks.md  Tareas Automaticas de Orunex
Edita este archivo para programar tareas periodicas.
Formato: ## Nombre, luego - interval: minutos, - command: instruccion, - enabled: true/false

## Resumen Diario de Noticias
- interval: 1440
- command: [SEARCH_WEB: noticias tecnologia e inteligencia artificial hoy]
- enabled: false

## Limpieza de Logs
- interval: 10080
- command: [CMD: del orunex_outputs\\*.log 2>nul]
- enabled: false
"""
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def _safe_notify(text: str, category: str = "info"):
    """Notifica via Simplex y por consola."""
    try:
        from _orunex_libs.simplex_bridge import notify
        notify(text, category)
    except:
        pass
    if _notify_callback:
        try:
            _notify_callback(text, category)
        except:
            pass
