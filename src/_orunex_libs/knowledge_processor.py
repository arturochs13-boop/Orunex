import os
import shutil
import json
from datetime import datetime

# Rutas de conocimiento
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
RAW_JSON_DIR = os.path.join(KNOWLEDGE_DIR, "raw_json")
RAW_PDF_DIR = os.path.join(KNOWLEDGE_DIR, "raw_pdfs")
INDEX_FILE = os.path.join(KNOWLEDGE_DIR, "knowledge_index.json")

# Asegurar estructura
for d in [RAW_JSON_DIR, RAW_PDF_DIR]:
    os.makedirs(d, exist_ok=True)

def ingest_file(file_path):
    """
    Ingiere un archivo al sistema de conocimiento de Orunex.
    Retorna (success, message).
    """
    if not os.path.exists(file_path):
        return False, "El archivo no existe."

    filename = os.path.basename(file_path)
    ext = filename.split('.')[-1].lower()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{filename}"

    try:
        if ext == 'json':
            target = os.path.join(RAW_JSON_DIR, safe_name)
            shutil.copy2(file_path, target)
            _update_index(filename, "json", target)
            return True, f"JSON '{filename}' ingerido y estructurado."
            
        elif ext == 'pdf':
            target = os.path.join(RAW_PDF_DIR, safe_name)
            shutil.copy2(file_path, target)
            _update_index(filename, "pdf", target)
            return True, f"Documento PDF '{filename}' guardado para analisis."
            
        else:
            return False, f"Formato .{ext} no soportado aun."
            
    except Exception as e:
        return False, f"Error critico en ingesta: {e}"

def _update_index(original_name, file_type, storage_path):
    """Actualiza el indice maestro de conocimiento."""
    index = []
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
        except:
            index = []
            
    entry = {
        "name": original_name,
        "type": file_type,
        "path": storage_path,
        "date": datetime.now().isoformat(),
        "status": "ready"
    }
    index.append(entry)
    
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=4)

def get_knowledge_context():
    """Retorna un resumen del conocimiento disponible para inyectar al prompt."""
    if not os.path.exists(INDEX_FILE):
        return ""
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
        if not index: return ""
        
        names = [item["name"] for item in index[-5:]] # Ultimos 5
        return f"\n[INTERNAL KNOWLEDGE BASE]: Posees informacion adicional de: {', '.join(names)}."
    except:
        return ""
