import os
import json
import time

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
AUDIT_FILE = os.path.join(LOG_DIR, "audit.log")

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def log_interaction(prompt, raw_output, final_output, mode="natural"):
    """
    Guarda una traza detallada de la interaccion para auditoria.
    Incluye el pensamiento interno (<think>) del modelo.
    """
    ensure_log_dir()
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Extraer el bloque <think> si existe para facilitar mi lectura
    import re
    thought = re.search(r"<think>(.*?)</think>", raw_output, re.DOTALL | re.IGNORECASE)
    thought_text = thought.group(1).strip() if thought else "N/A"
    
    entry = {
        "timestamp": timestamp,
        "mode": mode,
        "prompt": prompt,
        "thought": thought_text,
        "raw_output": raw_output,
        "final_output": final_output
    }
    
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[AUDIT ERROR] No se pudo escribir log: {e}")
