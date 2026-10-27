"""
memory_gc.py  Context Compaction Garbage Collector (Mega-Phase 4)
Compacta la historia del chat cada N turnos, resumiendo lo que paso
para manter el contexto bajo 1500 tokens y evitar overflow del LLM.
"""
import threading
import time

# Estado en memoria (no se persiste para privacidad maxima)
_conversation_buffer = []
_compacted_summary = ""
_turn_counter = 0
_gc_lock = threading.Lock()

# Umbral de compactacion: Cada N turnos, el GC resume la historia
GC_THRESHOLD = 10

def add_turn(role: str, content: str):
    """Anade un turno a la historia del chat."""
    global _turn_counter
    with _gc_lock:
        _conversation_buffer.append({"role": role, "content": content[:2000]})
        _turn_counter += 1
        # Compactamos en background si alcanzamos el umbral
        if _turn_counter > 0 and _turn_counter % GC_THRESHOLD == 0:
            threading.Thread(target=_compact_history, daemon=True).start()

def _compact_history():
    """Hilo de trasfondo: Pide al LLM un resumen comprimido del buffer."""
    global _compacted_summary, _conversation_buffer
    try:
        from _orunex_libs.ollama_client import call_ollama
        with _gc_lock:
            if len(_conversation_buffer) < 5:
                return
            history_text = "\n".join(
                f"[{t['role'].upper()}]: {t['content']}" for t in _conversation_buffer
            )
        
        compact_prompt = f"""Eres un sistema de compresion de contexto de IA.
Resume de forma precisa y concisa la siguiente conversacion entre el usuario y el asistente.
El resumen debe capturar: tareas realizadas, decisiones tomadas, archivos creados/editados, y preferencias del usuario.
Se especifico con nombres de archivos y acciones. Maximo 500 palabras.

HISTORIAL:
{history_text}

RESUMEN COMPRIMIDO:"""
        
        # Phase 112: Network call OUTSIDE the lock to avoid deadlocks
        resp = call_ollama(compact_prompt, system="Eres un compresor de contexto preciso y conciso.")
        new_summary = resp.get("response", "") if isinstance(resp, dict) else str(resp)
        
        with _gc_lock:
            _compacted_summary = new_summary.strip()
            # Limpiamos los turnos viejos, dejando solo los ultimos 3
            _conversation_buffer = _conversation_buffer[-3:]
    except Exception as e:
        # Error silencioso - la GC no debe interrumpir el flujo principal
        pass

def get_context_for_prompt() -> str:
    """Devuelve el contexto compactado listo para inyectar en el prompt del LLM."""
    with _gc_lock:
        if not _compacted_summary and not _conversation_buffer:
            return ""
        
        context_parts = []
        if _compacted_summary:
            context_parts.append(f"## RESUMEN DE SESION ANTERIOR (Compactado):\n{_compacted_summary}")
        
        recent = _conversation_buffer[-3:]
        if recent:
            recent_text = "\n".join(f"[{t['role'].upper()}]: {t['content'][:400]}" for t in recent)
            context_parts.append(f"## ULTIMAS INTERACCIONES:\n{recent_text}")
        
        return "\n\n".join(context_parts)

def get_turn_count() -> int:
    """Devuelve el numero de turnos en la sesion actual."""
    return _turn_counter

def reset_session():
    """Reinicia la memoria de la sesion actual (sin borrar memoria a largo plazo)."""
    global _conversation_buffer, _compacted_summary, _turn_counter
    with _gc_lock:
        _conversation_buffer = []
        _compacted_summary = ""
        _turn_counter = 0
