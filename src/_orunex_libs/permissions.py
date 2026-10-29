"""
permissions.py  Sistema de Permisos y Audit Trail para Orunex
Controla que acciones puede hacer el agente y registra cada una.
"""
import json
import os
import threading
from datetime import datetime
from enum import Enum

class PermLevel(Enum):
    SAFE = "SAFE"            # Leer archivos, buscar web, generar documentos
    ELEVATED = "ELEVATED"    # Crear archivos, ejecutar CMD seguros
    DANGEROUS = "DANGEROUS"  # Eliminar archivos, ejecutar scripts externos, acceso a red

# Tags y sus niveles de permiso
TAG_PERMISSIONS = {
    "SEARCH_WEB": PermLevel.SAFE,
    "HEADLESS_SEARCH": PermLevel.SAFE,
    "DOC": PermLevel.SAFE,
    "PPTX": PermLevel.SAFE,
    "GUI_SEE": PermLevel.SAFE,
    "SCREENSHOT": PermLevel.ELEVATED,
    "YOUTUBE": PermLevel.ELEVATED,
    "OPEN_URL": PermLevel.ELEVATED,
    "GUI_NAVIGATE": PermLevel.ELEVATED,
    "GUI_OPEN": PermLevel.ELEVATED,
    "GUI_SMART_LAUNCH": PermLevel.ELEVATED,
    "GUI_CHROME_PROFILE": PermLevel.ELEVATED,
    "APP_HOOK": PermLevel.ELEVATED,
    "UIA_CLICK": PermLevel.ELEVATED,
    "GUI_VISUAL_CLICK": PermLevel.ELEVATED,
    "GUI_CLICK_TEXT": PermLevel.ELEVATED,
    "MKDIR": PermLevel.ELEVATED,
    "FILE": PermLevel.ELEVATED,
    "EDIT": PermLevel.ELEVATED,
    "CMD": PermLevel.ELEVATED,
    "GUI_CLICK": PermLevel.ELEVATED,
    "GUI_TYPE": PermLevel.ELEVATED,
    "GUI_SCROLL": PermLevel.ELEVATED,
    "GUI_PRESS": PermLevel.ELEVATED,
    "GUI_SHORTCUT": PermLevel.ELEVATED,
    "GUI_TAB_CLOSE": PermLevel.ELEVATED,
    "GUI_TAB_NEXT": PermLevel.ELEVATED,
    "GUI_TAB_PREV": PermLevel.ELEVATED,
    "GUI_FULLSCREEN": PermLevel.ELEVATED,
    "GUI_MAXIMIZE": PermLevel.ELEVATED,
    "GUI_MINIMIZE": PermLevel.ELEVATED,
    "LOOP": PermLevel.ELEVATED,
    "WATCH": PermLevel.ELEVATED,
    "CALL": PermLevel.ELEVATED,
    "VSCODE": PermLevel.ELEVATED,
    "MEMORIZE": PermLevel.ELEVATED,
    "DEL": PermLevel.DANGEROUS,
    "SOCIAL": PermLevel.DANGEROUS,
    "WHATSAPP_SEND": PermLevel.DANGEROUS,
    "SYSTEM_POWER": PermLevel.DANGEROUS,
    "SELF_EVOLVE": PermLevel.DANGEROUS,
    "MISSION": PermLevel.DANGEROUS,
}

AUDIT_LOG_PATH = os.path.abspath(
    os.path.join(os.getcwd(), "orunex_outputs", "audit_log.jsonl")
)
os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

_log_lock = threading.Lock()
_ui_confirm_callback = None  # Set by main_av.py to show modal dialogs


def set_ui_confirm_callback(fn):
    """Registra la funcion de confirmacion modal de la UI."""
    global _ui_confirm_callback
    _ui_confirm_callback = fn


def check_permission(tag: str, context: str = "", agent: str = "Sistema") -> bool:
    """
    Verifica si un tag tiene permiso para ejecutarse.
    DANGEROUS tags requieren confirmacion del usuario si hay callback registrado.
    Retorna True si debe ejecutarse, False si fue rechazado.
    """
    level = TAG_PERMISSIONS.get(tag.upper(), PermLevel.ELEVATED)

    log_entry(tag=tag, context=context, agent=agent, level=level.value, status="PENDING")

    # Aggressive mode: when ORUNEX_AGGRESSIVE=1, allow dangerous actions
    # without confirmation UI, useful for trusted headless environments.
    aggressive = os.environ.get("ORUNEX_AGGRESSIVE", "0") in {"1", "true", "yes"}

    if level == PermLevel.DANGEROUS and aggressive:
        # In aggressive mode, allow dangerous actions without confirmation.
        log_entry(tag=tag, context=context, agent=agent, level=level.value, status="AGGRESSIVE_ALLOWED")
        return True

    # Dangerous actions are confirmation-gated by default.  Operators can
    # explicitly opt out with ORUNEX_STRICT_PERM=0 for a trusted headless run.
    strict_perm = os.environ.get("ORUNEX_STRICT_PERM", "1").strip().lower()
    strict_enabled = strict_perm not in {"0", "false", "no", "off"}

    if level == PermLevel.DANGEROUS and strict_enabled:
        if _ui_confirm_callback:
            try:
                approved = _ui_confirm_callback(
                    f"[WARN] Accion de Riesgo Detectada\n\n"
                    f"El agente [{agent}] quiere ejecutar:\n"
                    f"[{tag}: {context[:80]}]\n\n"
                    f"Autorizar esta accion?"
                )
            except Exception as exc:
                log_entry(
                    tag=tag,
                    context=context,
                    agent=agent,
                    level=level.value,
                    status=f"CONFIRMATION_ERROR: {type(exc).__name__}",
                )
                return False
            if not approved:
                log_entry(
                    tag=tag,
                    context=context,
                    agent=agent,
                    level=level.value,
                    status="REJECTED_BY_USER",
                )
                return False
        elif os.environ.get("ORUNEX_ALLOW_DANGEROUS", "0") != "1":
            # No UI is attached to ask.  Do not silently execute deletion,
            # shutdown, messaging or social actions in that situation.
            log_entry(
                tag=tag,
                context=context,
                agent=agent,
                level=level.value,
                status="BLOCKED_NO_CONFIRMATION",
            )
            return False

    log_entry(tag=tag, context=context, agent=agent, level=level.value, status="APPROVED")
    return True


def log_entry(tag: str, context: str, agent: str, level: str, status: str, result: str = ""):
    """Registra una accion en el audit log JSONL."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "tag": tag,
        "level": level,
        "status": status,
        "context": context[:200] if context else "",
        "result": result[:200] if result else ""
    }
    try:
        with _log_lock:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except:
        pass


def log_result(tag: str, result: str, agent: str = "Sistema"):
    """Actualiza el log con el resultado de una accion ejecutada."""
    log_entry(tag=tag, context="", agent=agent, level="RESULT", status="COMPLETED", result=result)


def get_recent_logs(n: int = 20) -> list:
    """Retorna los ultimos N registros del audit log."""
    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [json.loads(l) for l in lines[-n:] if l.strip()]
    except:
        return []
