import os
import re
import json
import uuid
import time
from datetime import datetime

import threading

# Global Creation Chamber (from VSCode Integration)
WORKSPACE = os.path.join(os.path.expanduser("~"), "Documents", "Orunex_Workspace")

class MissionStep:
    def __init__(self, title, description, order):
        self.id = uuid.uuid4().hex[:6]
        self.title = title
        self.description = description
        self.order = order
        self.status = "PENDING" # PENDING, RUNNING, SUCCESS, FAILED
        self.result = None
        self.started_at = None
        self.ended_at = None
        self.retry_count = 0 # V43.3: Safety Throttle

class ProjectSession:
    def __init__(self, goal, steps_raw):
        self.id = f"PRJ-{int(time.time())}"
        self.goal = goal
        self.steps = []
        self.current_idx = 0
        self.context_accumulator = [] # To pass data between steps
        self.vector_store = [] # V52.0 RAG Memory: List of {"text": ..., "embedding": ...}
        self.created_paths = {} # Map step_id or title to generated file paths
        self.lock = threading.Lock() # V52.0 Thread-safety for parallel DAG

        for i, step_data in enumerate(steps_raw):
            title = step_data.get("title", f"Paso {i+1}")
            desc = step_data.get("desc", "")
            self.steps.append(MissionStep(title, desc, i))

    def to_json(self):
        with self.lock:
            return {
                "id": self.id,
                "goal": self.goal,
                "current_idx": self.current_idx,
                "status": self.get_status(),
                "steps": [vars(s) for s in self.steps],
                "context": self.context_accumulator
            }

    def get_status(self):
        if all(s.status == "SUCCESS" for s in self.steps): return "COMPLETED"
        if any(s.status == "FAILED" for s in self.steps): return "BLOCKED"
        return "IN_PROGRESS"

    def get_parallel_batch(self):
        """
        V52.0 DAG PARALLEL BATCHING ENGINE
        Identifies all remaining PENDING steps that can run concurrently without dependencies.
        Document creation tasks (PDF, PPT, Excel, Word, Landing) or search tasks without explicit previous step references.
        """
        with self.lock:
            pending = [s for s in self.steps if s.status == "PENDING"]
            if not pending: return []
            
            # First pending step is always candidate
            batch = [pending[0]]
            
            # Check if subsequent pending steps are independent document/search tasks
            for s in pending[1:]:
                # Dependency keywords pointing to previous steps
                dep_kw = ["anterior", "paso 1", "paso 2", "del resultado", "archivo creado", "después", "luego"]
                has_dep = any(k in s.description.lower() for k in dep_kw)
                
                # Check if it's an independent doc/search task
                doc_tags = ["MAKE_DOC:", "HEADLESS_SEARCH:", "FILE:"]
                is_independent_doc = any(t in s.description for t in doc_tags) or not has_dep
                
                if is_independent_doc and not has_dep:
                    batch.append(s)
                else:
                    break # Stop batching at first dependent step
            
            return batch


# --- GLOBAL SESSION MANAGER ---
ACTIVE_PROJECT = None

def start_project(goal, steps_list):
    global ACTIVE_PROJECT
    ACTIVE_PROJECT = ProjectSession(goal, steps_list)
    print(f"[SYNAPSE V43] Proyecto '{ACTIVE_PROJECT.id}' iniciado: {goal}")
    return ACTIVE_PROJECT

def get_current_step():
    if not ACTIVE_PROJECT or ACTIVE_PROJECT.current_idx >= len(ACTIVE_PROJECT.steps):
        return None
    return ACTIVE_PROJECT.steps[ACTIVE_PROJECT.current_idx]

def mark_step_success(result):
    global ACTIVE_PROJECT
    if not ACTIVE_PROJECT: return
    step = get_current_step()
    if step:
        # V43.5 Anti-Lazy Guard: Reject non-actionable passive responses (V43.8 Hardened)
        # V51.0 Anti-Lazy Guard — Infallibility Shield (hardened)
        # Accept: formal [TAG: ...] results, file paths, substantial data (search/doc results), or completion keywords
        res_str = str(result) if result is not None else ""
        has_action_tag    = bool(re.search(r'\[[A-Z_]+:.*?\]', res_str))
        has_file_path     = bool(re.search(r'[a-zA-Z]:\\', res_str))
        has_substantial   = len(res_str) > 150  # e.g. headless search output
        has_completion_kw = any(kw in res_str.lower() for kw in [
            "completado", "generado", "listo", "done", "ok", "success",
            "creado", "guardado", "saved", "created", "finished"
        ])
        is_actionable = has_action_tag or has_file_path or has_substantial or has_completion_kw

        if not is_actionable and "System" not in res_str:
             step.status = "FAILED"
             step.result = "[ERR] Respuesta pasiva detectada. Orunex debe ejecutar una accion real."
             return # Trigger the healer in os_executor
             
        step.status = "SUCCESS"
        step.result = res_str if res_str.strip() else "Acción completada con éxito (salida vacía)."

        step.ended_at = datetime.now().isoformat()
        
        # Track file paths automatically if detected in result (V43.9 Robust)
        # Look for Windows-style paths (including those with spaces, non-greedy till delimiters)
        paths = re.findall(r'[a-zA-Z]:\\[^\[\]\n\r\t]+', res_str)
        for p in paths:
            # Clean trailing punctuation and whitespace
            p_clean = p.strip().rstrip('.,;!?')
            if "." in os.path.basename(p_clean): # Likely a file path
                name = os.path.basename(p_clean)
                ACTIVE_PROJECT.created_paths[name] = p_clean

        # V43.13 Context Summarizer: Avoid context blow for massive results
        short_res = res_str
        if len(res_str) > 1500:
             short_res = f"[RESUMEN INDUSTRIAL]: {res_str[:800]} ... (truncado) ... {res_str[-400:]}"
             from _orunex_libs.os_executor import notify_progress
             notify_progress(f"[ZIP] Contexto comprimido para Paso {ACTIVE_PROJECT.current_idx + 1}.", "info")

        ACTIVE_PROJECT.context_accumulator.append(f"Result (Paso {ACTIVE_PROJECT.current_idx + 1}): {short_res}")

        # V52.0 RAG VECTOR MEMORY INDEXING
        try:
            from .ollama_client import get_local_embedding
            text_to_embed = f"{step.title}: {short_res[:500]}"
            emb = get_local_embedding(text_to_embed)
            if emb:
                with ACTIVE_PROJECT.lock:
                    ACTIVE_PROJECT.vector_store.append({
                        "step_idx": ACTIVE_PROJECT.current_idx + 1,
                        "title": step.title,
                        "text": short_res[:800],
                        "embedding": emb
                    })
        except Exception as e:
            pass

        ACTIVE_PROJECT.current_idx += 1


def mark_step_failed(error):
    global ACTIVE_PROJECT
    if not ACTIVE_PROJECT: return
    step = get_current_step()
    if step:
        step.status = "FAILED"
        step.result = f"ERROR: {error}"
        step.ended_at = datetime.now().isoformat()

def search_memory_rag(query: str, top_k: int = 2) -> list:
    """
    V52.0 SYNAPSE VECTOR RAG SEARCH (Hybrid Vector + Keyword)
    Computes cosine similarity between query embedding and stored step embeddings.
    Falls back to keyword matching if embedding similarity threshold is low.
    """
    if not ACTIVE_PROJECT or not ACTIVE_PROJECT.vector_store:
        return []
    try:
        from .ollama_client import get_local_embedding
        q_emb = get_local_embedding(query)
        
        scores = []
        q_words = [w.lower() for w in query.split() if len(w) > 3]

        for item in ACTIVE_PROJECT.vector_store:
            v_emb = item.get("embedding")
            sim = 0.0
            if q_emb and v_emb and len(v_emb) == len(q_emb):
                dot = sum(a * b for a, b in zip(q_emb, v_emb))
                norm_q = (sum(a * a for a in q_emb)) ** 0.5
                norm_v = (sum(b * b for b in v_emb)) ** 0.5
                sim = dot / (norm_q * norm_v) if (norm_q * norm_v) > 0 else 0.0
            
            # Hybrid Keyword Bonus
            text_low = f"{item['title']} {item['text']}".lower()
            kw_match = sum(1 for kw in q_words if kw in text_low)
            combined_score = sim + (kw_match * 0.5)

            if combined_score > 0.1 or kw_match > 0:
                scores.append((combined_score, item))
            
        scores.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scores[:top_k]]
    except:
        return []


def get_full_context(current_query: str = ""):
    if not ACTIVE_PROJECT: return ""
    ctx = f"OBJETIVO GLOBAL: {ACTIVE_PROJECT.goal}\n"
    ctx += "AVANCE DEL PROYECTO:\n"
    for i, step in enumerate(ACTIVE_PROJECT.steps):
        status_icon = "✅" if step.status == "SUCCESS" else "⏳" if step.status == "PENDING" else "❌"
        ctx += f"{status_icon} Paso {i+1}: {step.title} - {step.status}\n"
    
    if ACTIVE_PROJECT.created_paths:
        ctx += "\nARCHIVOS REGISTRADOS:\n"
        if len(ACTIVE_PROJECT.created_paths) > 10:
             by_ext = {}
             for k in ACTIVE_PROJECT.created_paths:
                  ext = k.split('.')[-1] if '.' in k else 'no_ext'
                  by_ext[ext] = by_ext.get(ext, 0) + 1
             ctx += f"- TOTAL: {len(ACTIVE_PROJECT.created_paths)} archivos.\n"
             for ext, count in by_ext.items():
                  ctx += f"  - [*.{ext}]: {count} archivos detectados.\n"
        else:
             for k, v in ACTIVE_PROJECT.created_paths.items():
                  ctx += f"- {k}: {v}\n"

    # V52.0 RAG MEMORY INJECTION
    rag_items = search_memory_rag(current_query or ACTIVE_PROJECT.goal, top_k=3)
    if rag_items:
        ctx += "\nMEMORIA VECTORIAL RAG (Contexto Semántico Relevante):\n"
        for item in rag_items:
            ctx += f"- [Paso {item['step_idx']} {item['title']}]: {item['text'][:300]}\n"
    else:
        ctx += "\nMEMORIA CRÍTICA (Últimas Misiones):\n"
        ctx += "\n---\n".join(ACTIVE_PROJECT.context_accumulator[-3:])
        
    return ctx



def is_project_active():
    return ACTIVE_PROJECT is not None and ACTIVE_PROJECT.get_status() == "IN_PROGRESS"
