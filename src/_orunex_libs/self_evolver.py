"""
self_evolver.py  Self-Evolution Sandbox (Phase 48)
Orunex puede analizar su propio log de errores, identificar fallos repetidos,
generar un parche de codigo usando Ollama, y aplicarlo de forma autonoma.

Tags soportados (desde os_executor.py):
  [SELF_EVOLVE]           Activa un ciclo de auto-analisis y parcheo.
  [SELF_EVOLVE: modulo]   Analiza y parchea un modulo especifico de utils/agents.
"""
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path

# 
# CONFIGURACION
# 
BASE_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_FILE  = os.path.join(BASE_SRC, "..", "orunex_error.log")
EVOLVE_LOG = os.path.join(BASE_SRC, "..", "orunex_evolution.log")

# Archivos que NUNCA se auto-parchean (proteccion de seguridad)
PROTECTED_FILES = {
    "permissions.py", "long_term_memory.py", "main_av.py", "self_evolver.py"
}

_evolve_lock = threading.Lock()

# 
# PASO 1: Analizar el Log de Errores
# 
def _read_error_log(max_lines: int = 200) -> str:
    """Lee el log de errores de Orunex y devuelve las ultimas N lineas."""
    if not os.path.exists(LOG_FILE):
        return ""
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except Exception as e:
        return f"[Error leyendo log: {e}]"

def _find_repeated_errors(log_text: str, min_count: int = 2) -> list[dict]:
    """
    Extrae errores repetidos del log y los agrupa por tipo.
    Devuelve lista de {'error': str, 'count': int, 'file': str}.
    """
    error_pattern = re.compile(
        r'(?:ERROR|Exception|Traceback|[ERR]).*?File \"(.*?)\".*?line (\d+).*?([\w]+Error|[\w]+Exception[^\n]*)',
        re.IGNORECASE
    )
    matches = error_pattern.findall(log_text)
    
    # Contar ocurrencias por (archivo, tipo de error)
    counter = Counter()
    for filepath, lineno, err_type in matches:
        filename = os.path.basename(filepath)
        if filename not in PROTECTED_FILES:
            counter[(filename, err_type.strip())] += 1
    
    # Filtrar los errores frecuentes
    repeated = []
    for (filename, err_type), count in counter.most_common(5):
        if count >= min_count:
            repeated.append({"file": filename, "error": err_type, "count": count})
    
    return repeated

# 
# PASO 2: Leer el Archivo a Parchear
# 
def _resolve_source_file(filename: str) -> str | None:
    """Busca un archivo en src/utils/ o src/agents/."""
    for subfolder in ("utils", "agents"):
        candidate = os.path.join(BASE_SRC, subfolder, filename)
        if os.path.exists(candidate):
            return candidate
    return None

def _read_source_file(path: str, max_chars: int = 4000) -> str:
    """Lee el contenido del archivo fuente con limite de tokens."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content[:max_chars]
    except Exception as e:
        return f"[Error leyendo fuente: {e}]"

# 
# PASO 3: Generar el Parche con Ollama
# 
def _generate_patch(file_content: str, filename: str, error_type: str, error_count: int) -> str:
    """
    Envia el codigo fuente + descripcion del error al LLM
    y recibe un parche en formato [EDIT:] tag.
    """
    try:
        from _orunex_libs.ollama_client import call_ollama
        patch_prompt = f"""Eres un ingeniero senior de Python especializado en correccion autonoma de errores.
Se ha detectado el error '{error_type}' repetido {error_count} veces en el archivo '{filename}'.

CODIGO ACTUAL DEL ARCHIVO (fragmento):
```python
{file_content}
```

INSTRUCCION:
1. Analiza el codigo y encuentra la causa raiz del error '{error_type}'.
2. Disena una correccion minima pero robusta (try/except, validacion de tipo, guard clause, etc.).
3. Devuelve EXCLUSIVAMENTE el parche usando este formato exacto:

[EDIT: {filename}]
---BUSCAR---
codigo exacto a reemplazar (pocas lineas)
---REEMPLAZAR---
codigo corregido con el fix
[/EDIT]

REGLAS:
- Solo devuelve el bloque [EDIT:...[/EDIT]], sin texto extra.
- El codigo en ---BUSCAR--- debe existir EXACTAMENTE en el archivo.
- No hagas cambios a logica de negocio, solo corrije el error especifico.
"""
        resp = call_ollama("orunex_v37", patch_prompt, system=None)
        return resp.get("response", "")
    except Exception as e:
        return f"[Error generando parche: {e}]"

# 
# PASO 4: Aplicar el Parche
# 
def _apply_patch(patch_text: str) -> list[str]:
    """
    Extrae bloques [EDIT:...[/EDIT]] del parche generado por el LLM
    y los aplica usando la logica interna de os_executor.
    """
    from _orunex_libs.os_executor import intercept_and_execute
    results = intercept_and_execute(patch_text, auto_healer_agent="self_evolver")
    return results

def _log_evolution(entry: str):
    """Registra el ciclo de evolucion en orunex_evolution.log."""
    try:
        with open(EVOLVE_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {entry}\n")
    except Exception:
        pass

# 
# API PRINCIPAL
# 
def run_evolution_cycle(target_module: str = None) -> str:
    """
    Punto de entrada del Self-Evolution Sandbox.
    1. Lee el error log.
    2. Identifica errores repetidos.
    3. Por cada error, genera un parche con Ollama.
    4. Aplica los parches a los archivos fuente.
    5. Devuelve un reporte de lo que cambio.
    """
    with _evolve_lock:
        report_lines = ["[DNA] CICLO DE AUTO-EVOLUCION INICIADO"]
        
        log_text = _read_error_log()
        if not log_text:
            return "[DNA] Auto-Evolucion: Log de errores vacio. Nada que corregir  todo funciona perfectamente!"
        
        report_lines.append(f" Log leido: {len(log_text)} caracteres")
        
        repeated = _find_repeated_errors(log_text)
        if not repeated:
            return "[DNA] Auto-Evolucion: No hay errores repetidos en el log. Sistema estable."
        
        report_lines.append(f"[WARN] Errores repetidos detectados: {len(repeated)}")
        
        patched = 0
        for err_info in repeated:
            fname = err_info["file"]
            etype = err_info["error"]
            count = err_info["count"]
            
            # Si se especifico un modulo, solo parchear ese
            if target_module and target_module.lower() not in fname.lower():
                continue
            
            report_lines.append(f"\n Analizando: {fname}  '{etype}' ({count})")
            
            src_path = _resolve_source_file(fname)
            if not src_path:
                report_lines.append(f"  [WARN] Archivo '{fname}' no encontrado en src/")
                continue
            
            if fname in PROTECTED_FILES:
                report_lines.append(f"   '{fname}' esta protegido. Omitido.")
                continue
            
            file_content = _read_source_file(src_path)
            report_lines.append(f"   Generando parche con deepseek-r1...")
            patch_text = _generate_patch(file_content, fname, etype, count)
            
            if "[EDIT:" in patch_text and "[/EDIT]" in patch_text:
                report_lines.append(f"  [OK] Parche generado. Aplicando...")
                result = _apply_patch(patch_text)
                if result:
                    report_lines.append(f"   Resultado: {result}")
                    _log_evolution(f"Parchado {fname}  {etype} ({count})")
                    patched += 1
                else:
                    report_lines.append(f"  [ERR] El parche no pudo aplicarse (buscar: texto no encontrado).")
            else:
                report_lines.append(f"  [WARN] LLM no genero un parche valido. Skip.")
        
        report_lines.append(f"\n Ciclo completo. Archivos parcheados: {patched}/{len(repeated)}")
        if patched > 0:
            report_lines.append("[TIP] Recarga Orunex para aplicar los cambios permanentemente.")
        
        return "\n".join(report_lines)


def run_evolution_background(target_module: str = None):
    """Lanza un ciclo de auto-evolucion en un hilo de trasfondo."""
    def _bg():
        try:
            result = run_evolution_cycle(target_module)
            _log_evolution(f"Ciclo BG completado: {result[:200]}")
        except Exception as e:
            _log_evolution(f"Ciclo BG fallo: {e}")
    
    t = threading.Thread(target=_bg, daemon=True)
    t.start()
    return "[DNA] Ciclo de Auto-Evolucion iniciado en segundo plano. Revisa `orunex_evolution.log` para seguimiento."
