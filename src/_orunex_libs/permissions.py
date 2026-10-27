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
    "DOC": PermLevel.SAFE,
    "PPTX": PermLevel.SAFE,
    "GUI_SEE": PermLevel.SAFE,
    "MKDIR": PermLevel.ELEVATED,
    "FILE": PermLevel.ELEVATED,
    "EDIT": PermLevel.ELEVATED,
    "CMD": PermLevel.ELEVATED,
    "GUI_CLICK": PermLevel.ELEVATED,
    "GUI_TYPE": PermLevel.ELEVATED,
    "GUI_SCROLL": PermLevel.ELEVATED,
    "LOOP": PermLevel.ELEVATED,
    "WATCH": PermLevel.ELEVATED,
    "DEL": PermLevel.DANGEROUS,
    "CALL": PermLevel.ELEVATED,
    "VSCODE": PermLevel.ELEVATED,
    "SOCIAL": PermLevel.DANGEROUS,
    "SCREENSHOT": PermLevel.SAFE,
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

    strict_perm = os.environ.get("ORUNEX_STRICT_PERM", "0")
    
    if level == PermLevel.DANGEROUS and strict_perm == "1":
        if _ui_confirm_callback:
            approved = _ui_confirm_callback(
                f"[WARN] Accion de Riesgo Detectada\n\n"
                f"El agente [{agent}] quiere ejecutar:\n[{tag}: {context[:80]}]\n\n"
                f"Autorizar esta accion?"
            )
            if not approved:
                log_entry(tag=tag, context=context, agent=agent, level=level.value, status="REJECTED_BY_USER")
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
