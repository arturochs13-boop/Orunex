import json
import os
import re

MEMORY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'orunex_memory.json'))

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"preferences": [], "context": {}}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"preferences": [], "context": {}}

def save_memory(data):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except:
        pass

def add_preference(pref: str):
    data = load_memory()
    if pref not in data["preferences"]:
        data["preferences"].append(pref)
        save_memory(data)

def update_context(key: str, value: str):
    data = load_memory()
    data["context"][key] = value
    save_memory(data)

def get_context_string():
    data = load_memory()
    prefs = "\n".join(f"- {p}" for p in data["preferences"])
    ctx = "\n".join(f"- {k}: {v}" for k, v in data["context"].items())
    
    res = ""
    if prefs:
         res += f"PREFERENCIAS DEL USUARIO:\n{prefs}\n"
    if ctx:
         res += f"INFORMACION DE PROYECTO CREADA:\n{ctx}\n"
    return res

def get_all_memories() -> list:
    """Returns all memory entries (preferences + context) for display in the Config Panel."""
    data = load_memory()
    entries = []
    for p in data.get("preferences", []):
        entries.append({"agent": "Preferencia", "task": p})
    for k, v in data.get("context", {}).items():
        entries.append({"agent": "Contexto", "task": f"{k}: {v}"})
    return entries

def delete_memory_by_index(idx: int):
    """Deletes a specific memory entry by its index in get_all_memories() order."""
    data = load_memory()
    prefs = data.get("preferences", [])
    ctx_items = list(data.get("context", {}).items())
    
    all_entries = [("pref", i) for i in range(len(prefs))] + [("ctx", i) for i in range(len(ctx_items))]
    
    if 0 <= idx < len(all_entries):
        kind, inner_idx = all_entries[idx]
        if kind == "pref":
            prefs.pop(inner_idx)
            data["preferences"] = prefs
        else:
            key = ctx_items[inner_idx][0]
            del data["context"][key]
        save_memory(data)

# --- V40.4 MISSION JOURNAL & LEARNING ---
def log_mission_outcome(mission_id, command, status, details=""):
    """Records the result of a delegated mission for future learning."""
    log_path = os.path.join(os.path.dirname(MEMORY_FILE), "orunex_mission_journal.json")
    try:
        history = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            
        entry = {
            "id": mission_id,
            "timestamp": os.path.getmtime(MEMORY_FILE) if os.path.exists(MEMORY_FILE) else 0, # Simplified
            "command": command,
            "status": status,
            "details": details[:200]
        }
        history.append(entry)
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(history[-100:], f, indent=4) # Keep last 100
            
        return f"[MEMORY] Misión {mission_id} registrada."
    except:
        return "[MEMORY ERR] Fallo al loguear misión."
