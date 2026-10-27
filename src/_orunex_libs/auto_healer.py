import os
import re
from agents import cerebro # type: ignore

def heuristic_heal(original_command: str, error_text: str) -> str:
    """
    V52.0 FAST-HEALER LAYER 1 (Sub-50ms Deterministic Repair)
    Repairs common syntax, path, and environment errors without calling the GGUF model.
    """
    cmd = original_command.strip()
    err = str(error_text).lower()

    # Rule 1: Mismatched quotes fix
    single_q = cmd.count("'")
    double_q = cmd.count('"')
    if single_q % 2 != 0: cmd += "'"
    if double_q % 2 != 0: cmd += '"'

    # Rule 2: Path slash normalization for Windows
    if "/" in cmd and not cmd.startswith("http"):
        # Convert forward slashes in local paths
        parts = cmd.split()
        repaired_parts = []
        for p in parts:
            if "/" in p and not p.startswith("http://") and not p.startswith("https://"):
                repaired_parts.append(p.replace("/", "\\"))
            else:
                repaired_parts.append(p)
        cmd = " ".join(repaired_parts)

    # Rule 3: Missing directory auto-creation for python/file operations
    if "filenotfounderror" in err or "no such file or directory" in err or "cannot find the path" in err:
        path_match = re.search(r"[a-zA-Z]:\\[^\s\"']+", cmd)
        if path_match:
            target_path = path_match.group(0)
            parent_dir = os.path.dirname(target_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                print(f"[FAST-HEALER] Carpeta creada automáticamente: {parent_dir}")
                return cmd

    # Rule 4: Common Windows command aliases
    if cmd.startswith("python3 "):
        return cmd.replace("python3 ", "python ", 1)
    if cmd.startswith("ls "):
        return cmd.replace("ls ", "dir ", 1)
    if cmd.startswith("touch "):
        file_target = cmd.split("touch ", 1)[1].strip()
        return f"type nul > {file_target}"
        
    # If any deterministic modification was performed, return it
    if cmd != original_command.strip():
        print(f"[FAST-HEALER] Auto-reparado en <1ms: {cmd}")
        return cmd

    return None

def heal_command(original_command, error_text):
    """
    Receives a command that failed and its error, then attempts Fast-Healer first, falling back to Cerebro.
    """
    print(f"[HEALER] Analizando fallo en: {original_command[:50]}...")

    # Fast-Healer Layer 1 (Deterministic Sub-50ms)
    fast_fix = heuristic_heal(original_command, error_text)
    if fast_fix:
        log_auto_heal(original_command, f"FAST-HEALER: {fast_fix}")
        return fast_fix

    # LLM Healer Layer 2
    prompt = (
        f"ERROR DETECTADO EN EJECUCIÓN SOBERANA:\n"
        f"COMANDO INTENTADO: {original_command}\n"
        f"ERROR RECIBIDO: {error_text}\n\n"
        "TU MISIÓN: Proporciona ÚNICAMENTE el comando o etiqueta corregida para solucionar esto.\n"
        "Si el archivo no existe, búscalo primero o propón una ruta válida.\n"
        "Si es un error de sintaxis, corrígelo.\n"
        "RESPUESTA: [CORRECCION: ...]"
    )

    fix_resp = cerebro.run(prompt, "System_Healer", agent_mode="os")

    match = re.search(r"\[CORRECCION:\s*(.*?)\]", fix_resp, re.IGNORECASE | re.DOTALL)
    if match:
        log_auto_heal(original_command, match.group(1).strip())
        return match.group(1).strip()

    if "[" in fix_resp and "]" in fix_resp:
        return fix_resp.strip()

    return f"[ERR] No se pudo auto-sanar el comando: {error_text}"


def log_auto_heal(original, fixed, mission_id="GLOBAL"):
    with open("synapse_healer.log", "a", encoding="utf-8") as f:
        f.write(f"[{mission_id}] {original} -> FIXED: {fixed}\n")
