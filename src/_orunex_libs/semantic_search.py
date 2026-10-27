# src/utils/semantic_search.py
import os
import json
import numpy as np
import requests

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
INDEX_FILE = os.path.abspath(os.path.join(os.getcwd(), "orunex_outputs", "semantic_index.json"))

def get_embedding(text: str):
    """Obtiene el vector de embedding de forma 100% local y soberana."""
    try:
        from _orunex_libs.ollama_client import get_local_embedding
        return get_local_embedding(text)
    except:
        return []

def extract_text_from_file(filepath: str) -> str:
    """Extrae texto plano de archivos para el indice vectorial."""
    ext = filepath.lower().split('.')[-1]
    if ext in ['txt', 'md', 'csv', 'json', 'py', 'js', 'html']:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()[:2000] # Limitar a los primeros 2000 caracteres para el indice
        except:
            pass
    elif ext == 'pdf':
        try:
            # Requerira pypdf2 si el usuario tiene PDFs reales
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages[:3]: # Primeras 3 paginas
                text += page.extract_text() + "\n"
            return text[:2000]
        except:
            pass
    return ""

def index_directory(directory: str):
    """Recorre un directorio y actualiza la base de datos vectorial local (Recall local)."""
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except:
            index_data = {}
    else:
        index_data = {}
        
    updated = False
    for root, _, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            # Solo indexar si no esta en el index (simplificado para evitar re-computar)
            if path not in index_data:
                content = extract_text_from_file(path)
                if content.strip():
                    vec = get_embedding(content)
                    if vec:
                        index_data[path] = {
                            "content_preview": content[:200].strip().replace('\n', ' '),
                            "vector": vec
                        }
                        updated = True
    
    if updated:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index_data, f)
            
    return len(index_data)

def display_search(query: str, top_k: int = 3):
    """Busca semanticamente en el indice local."""
    if not os.path.exists(INDEX_FILE):
        return "[WARN] Indice vacio. Iniciando primera indexacion de orunex_outputs..."
        
    query_vec = get_embedding(query)
    if not query_vec:
        return "[ERR] Error al generar embedding. Asegurate de tener instalado el modelo: `ollama pull nomic-embed-text`"
        
    query_np = np.array(query_vec)
    
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
    except:
        return "[ERR] Indice corrupto."
        
    if not index_data:
        return "[WARN] Indice vacio."
        
    results = []
    for path, data in index_data.items():
        doc_np = np.array(data["vector"])
        # Similitud Coseno
        similarity = np.dot(query_np, doc_np) / (np.linalg.norm(query_np) * np.linalg.norm(doc_np))
        results.append((similarity, path, data["content_preview"]))
        
    # Ordenar por mayor similitud
    results.sort(key=lambda x: x[0], reverse=True)
    
    out = []
    for sim, path, preview in results[:top_k]:
        if sim > 0.35: # Trheshold de relevancia semantica
            out.append(f"- [{sim:.2f}] {path}\n  Fragmento: {preview}...")
            
    if not out:
        return "No se encontraron archivos semanticamente relevantes."
        
    return "\n".join(out)
