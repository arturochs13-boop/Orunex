import os
import sys
import json
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _orunex_libs.ollama_client import call_ollama
from _orunex_libs.audit_logger import log_interaction # type: ignore
from _orunex_libs import project_manager # type: ignore
try:
    from _orunex_libs import faiss_memory # type: ignore
except Exception:
    faiss_memory = None

def harden_query(text):
    """
    Surgical Purity V1.7 (Zenith Sovereignty Shield)
    Removes ONLY specific punctuation noise without risk of truncating words.
    """
    if not text: return ""
    # Strip leading/trailing noise like : ” “ ' " 
    return text.strip().strip(":;,. \"'“”«»„")

def local_intent_scan(text):
    """
    DETERMINISTIC INTENT SCANNER (V20.2)
    Bypasses the LLM for clear OS commands, now with CHAINED support.
    """
    text_lower = text.lower()
    
    # 0. Split by conjunctions to handle simple chains (V20.2)
    steps = re.split(r",| y | then | and | luego | entonces | para ", text_lower)
    all_tags = []
    
    for step in steps:
        step = step.strip()
        if not step: continue

        # ── PRIORITY 0: Local semantic router ─────────────────────────────
        # It resolves Spanish/English open commands, keeps the requested
        # browser (Chrome/Edge/Firefox) and rejects ambiguous bare verbs.
        try:
            from _orunex_libs.intent_router import parse_command

            _command = parse_command(step)
        except Exception:
            _command = None
        if _command is not None:
            if _command.kind == "open_url":
                browser_suffix = f" | {_command.browser}" if _command.browser else ""
                all_tags.append(f"[OPEN_URL: {_command.url}{browser_suffix}]")
                continue
            if _command.kind == "open_app":
                if _command.app == "browser":
                    all_tags.append("[OPEN_URL: https://www.google.com]")
                else:
                    all_tags.append(f"[GUI_SMART_LAUNCH: {_command.app}]")
                continue
            if _command.kind == "clarify":
                # A bare "abre" must not be guessed.  The UI asks for a target.
                return None

        # ── PRIORITY 1: Deteccion de documentos (con o sin verbo explicito) ────
        doc_found = False
        creative_triggers = ["hazme", "crea", "escribe", "haz", "make", "create",
                             "diseña", "design", "escribeme", "generar", "genera"]
        is_creative = any(ct in step for ct in creative_triggers)

        # V32 Smart Excel Modifier Detection (V37.2: case-insensitive por text_lower)
        attached_match = re.search(r"\[file_attached:\s*(.*?)\]", step)
        if attached_match:
            attached_path = attached_match.group(1).strip()
            # Recuperar la ruta original (con mayúsculas/minúsculas correctas)
            orig_match = re.search(r"\[FILE_ATTACHED:\s*(.*?)\]", text, re.IGNORECASE)
            if orig_match:
                attached_path = orig_match.group(1).strip()
            # Clean step from the tag to avoid confusion in topic extraction
            clean_step = re.sub(r"\[file_attached:.*?\]", "", step, flags=re.IGNORECASE).strip()
            
            if attached_path.lower().endswith((".xlsx", ".xls")):
                # V37.2: CUALQUIER solicitud con archivo Excel adjunto es MODIFY_DOC
                # Usar el texto COMPLETO (sin tag) como instrucción para el motor
                full_instructions = re.sub(r"\[file_attached:.*?\]", "", text_lower, flags=re.IGNORECASE).strip()
                topic = full_instructions if full_instructions else "mejorar y organizar"
                print(f"[CEREBRO] Excel adjunto detectado: '{attached_path}' -> topic: '{topic}'")
                all_tags.append(f"[MODIFY_DOC: excel | {topic} | {attached_path}]")
                doc_found = True

        if not doc_found: 
            # V37.1: ALL keyword lists MUST be inside this block
            _excel_kw = ["un excel", "hoja de calculo", "hoja de datos",
                         "tabla en excel", "tabla de excel", "tabla excel",
                         "excel con", "excel sobre", "en excel", "de excel", "spreadsheet",
                         "tabla de", "tabla con", "inventario", "presupuesto de",
                         "presupuesto para", "gastos de", "factura de", "registro de",
                         "base de datos"]
            _word_kw  = ["un word", "documento sobre", "documento de", "word sobre", "word con"]
            _pdf_kw   = ["un pdf", "pdf sobre", "pdf de", "reporte en pdf", "archivo pdf",
                         "reporte pdf", "informe en pdf", "informe pdf"]
            _land_kw  = ["landing page", "pagina web", "sitio web", "landing para", "landing sobre"]
            _ppt_kw   = ["presentacion", "diapositivas", "ppt", "slides"]
            _cal_kw   = ["calendario", "agenda", "horario semanal", "horario mensual",
                         "planificador", "cronograma", "schedule", "itinerario"]
            _vid_kw   = ["un video", "video publicitario", "video promocional", "crear video",
                         "haz un video", "crea un video", "reel", "tiktok", "instagram reel",
                         "video para instagram", "video para tiktok", "videos"]
            _colab_kw = ["google colab", "colab", "notebook colab", "entorno colab", "colab gpu"]

            # Check Video (highest priority for video marketing tasks)
            if any(t in step for t in _vid_kw) or ("video" in step and is_creative):
                topic = step
                for kw in _vid_kw:
                    if kw in step:
                        extracted = step.split(kw)[-1].strip()
                        if len(extracted) > 2: topic = extracted
                        break
                print(f"[CEREBRO] Detectado VIDEO MARKETING: topic='{topic}'")
                all_tags.append(f"[MAKE_DOC: video | {topic}]")
                doc_found = True

            # Check Colab Notebook
            elif any(t in step for t in _colab_kw):
                topic = step
                for kw in _colab_kw:
                    if kw in step:
                        extracted = step.split(kw)[-1].strip()
                        if len(extracted) > 2: topic = extracted
                        break
                print(f"[CEREBRO] Detectado GOOGLE COLAB: topic='{topic}'")
                all_tags.append(f"[MAKE_DOC: colab | {topic}]")
                doc_found = True

            # Check Calendar (before Excel to avoid conflict)
            elif any(t in step for t in _cal_kw):
                topic = step
                for kw in _cal_kw:
                    if kw in step:
                        extracted = step.split(kw)[-1].strip()
                        if len(extracted) > 2: topic = extracted
                        break
                print(f"[CEREBRO] Detectado CALENDARIO: topic='{topic}'")
                all_tags.append(f"[MAKE_DOC: excel | calendario {topic}]")
                doc_found = True

            # Check Excel (highest priority for data tasks)
            elif any(t in step for t in _excel_kw) or ("excel" in step and is_creative):

                topic = step
                for kw in _excel_kw:
                    if kw in step:
                        extracted = step.split(kw)[-1].strip()
                        if len(extracted) > 2: topic = extracted
                        break
                print(f"[CEREBRO] Detectado EXCEL: topic='{topic}'")
                all_tags.append(f"[MAKE_DOC: excel | {topic}]")
                doc_found = True

            elif any(t in step for t in _word_kw):
                topic = step
                for kw in _word_kw:
                    if kw in step: topic = step.split(kw)[-1].strip()
                all_tags.append(f"[MAKE_DOC: word | {topic}]")
                doc_found = True

            elif any(t in step for t in _pdf_kw):
                topic = step
                for kw in _pdf_kw:
                    if kw in step: topic = step.split(kw)[-1].strip()
                all_tags.append(f"[MAKE_DOC: pdf | {topic}]")
                doc_found = True

            elif any(t in step for t in _land_kw):
                topic = step
                for kw in _land_kw:
                    if kw in step: topic = step.split(kw)[-1].strip()
                all_tags.append(f"[MAKE_DOC: landing | {topic}]")
                doc_found = True

            elif is_creative and any(t in step for t in _ppt_kw):
                topic = step
                for kw in ["presentacion sobre", "presentacion de", "una presentacion", "diapositivas sobre"]:
                    if kw in step: topic = step.split(kw)[-1].strip()
                all_tags.append(f"[MAKE_DOC: ppt | {topic}]")
                doc_found = True

        if doc_found:
            continue  # Skip app-launch logic

        # ── SYSTEM POWER INTENTS (Apagar / Reiniciar) ──
        if any(w in step for w in ["apagar mi laptop", "apagar la laptop", "apagar equipo", "apagar pc", "apagar el equipo", "apagar la pc", "shutdown"]):
            all_tags.append("[SYSTEM_POWER: shutdown]")
            continue
        elif any(w in step for w in ["reiniciar mi laptop", "reiniciar la laptop", "reiniciar pc", "reiniciar equipo", "reboot", "restart"]):
            all_tags.append("[SYSTEM_POWER: restart]")
            continue

        # ── WHATSAPP INTENTS (WhatsApp Web / Contactos) ──
        if "whatsapp" in step or "mensaje a" in step or "mandar mensaje" in step or "enviar whatsapp" in step:
            # Extraer contacto y mensaje
            wa_match = re.search(r"(?:whatsapp|mensaje)\s+(?:a|para)\s+([^\s|]+(?:\s+[^\s|]+)?)\s+(?:diciendo|con el mensaje|que diga|mensaje:?)\s*(.*)", step, re.IGNORECASE)
            if wa_match:
                contact = wa_match.group(1).strip()
                msg_body = wa_match.group(2).strip()
                all_tags.append(f"[WHATSAPP_SEND: {contact} | {msg_body}]")
                continue
            elif "whatsapp" in step:
                # Fallback para "manda whatsapp a 1234567890 hola"
                parts = step.replace("manda", "").replace("envia", "").replace("un", "").replace("whatsapp", "").strip().split(" ", 2)
                if len(parts) >= 2:
                    contact = parts[1].strip()
                    msg_body = parts[2].strip() if len(parts) > 2 else "Hola"
                    all_tags.append(f"[WHATSAPP_SEND: {contact} | {msg_body}]")
                    continue

        # ── PRIORIDAD 2: Negativo — creacion sin doc type reconocido ─────────
        if is_creative:
            if all_tags:
                continue  # V37.2: Preservar tags ya acumulados
            return None  # Evita que "crea X" dispare lanzamiento de apps


        # ── PRIORIDAD 3: Lanzar Apps ───────────────────────────────────────────
        app_keywords = {
            "chrome": ["chrome", "navegador", "internet", "google", "browser"],
            "edge": ["edge", "msedge"],
            "firefox": ["firefox", "mozzila"],
            "word": ["word", "doc"],
            "excel": ["excel", "hoja"],
            "calc": ["calc", "calculadora"],
            "notepad": ["notepad", "notas", "texto"],
            "taskmgr": ["taskmgr", "administrador", "tareas", "task", "procesos"],
            "explorador": ["explorador", "archivos", "explorer"]
        }
        
        found = False
        for app, keywords in app_keywords.items():
            if any(kw in step for kw in keywords):
                all_tags.append(f"[GUI_SMART_LAUNCH: {app.capitalize()}]")
                if app.lower() == "chrome":
                    # For Chrome, we ALWAYS add the profile handler attempt
                    all_tags.append("[GUI_CHROME_PROFILE]")
                found = True
                break
                        
        # 3.2 Headless Web Search (V30)
        if not found:
            headless_triggers = ["busca silenciosamente", "investiga silenciosamente", "dime sobre", "investiga sobre", "busca informacion de", "resumen de"]
            for ht in headless_triggers:
                if ht in step:
                    query = step.split(ht)[-1].strip()
                    if query:
                        all_tags.append(f"[HEADLESS_SEARCH: {query}]")
                        found = True
                        break

            # 3.3 YouTube Expert (V36.3 - Global/Quoted Intent)
            if not found:
                # Catch: (keyword) ["']?(SUJETO)["']? (garbage)?
                yt_pattern = r"(?:reproduce|reproduceme|ponme|pon|busca en youtube|en youtube busca|mira|video de|escuchar)[\s\"']*(.*?)(?:[\"']\s+y\s+|\s+en youtube|\s+de youtube|$)"
                match = re.search(yt_pattern, step, re.IGNORECASE)
                if match:
                    query = harden_query(match.group(1))
                    if query:
                        all_tags.append(f"[YOUTUBE: play | {query}]")
                        found = True
                        break

        # 4. Universal Clicks (UIA + Visual)
        if not found:
            nav_triggers = ["entra en", "haz clic en", "pulsar", "click on", "ir a", "ve a ", "presiona el boton "]
            for nt in nav_triggers:
                if nt in step:
                    target = step.split(nt)[-1].strip()
                    if target:
                        if "perfil" in target or "invitado" in target:
                            all_tags.append("[GUI_CHROME_PROFILE]")
                        else:
                            # Orunex V30: Emit UIA_CLICK for Universal OS Robustness, fallback to VISUAL
                            all_tags.append(f"[UIA_CLICK: {target}] [GUI_VISUAL_CLICK: {target}]")
                        found = True
                        break

        if not found:
            # Search for generic search intent
            search_triggers = ["busca ", "google ", "mira ", "entra a "]
            for st in search_triggers:
                if st in step:
                    query = step.split(st)[-1].strip()
                    if query: 
                        if "." in query or "youtube" in query: # Navigation intent
                            all_tags.append(f"[GUI_NAVIGATE: {query}]")
                        else:
                            all_tags.append(f"[GUI_TYPE: {query}] [GUI_PRESS: enter]")
                        found = True
                        break

    return " ".join(all_tags) if all_tags else None

    return " ".join(all_tags) if all_tags else None

def scrub_output(text, is_architect=False):
    """
    NUCLEAR SCRUBBER V17.0 (Nuclear Sovereignty Shield)
    Garantiza 0 alucinaciones mediante la destrucción de razonamientos.
    """
    if not text: return "Misión cumplida."
    
    # -1. THINKING SPLITTER (V18.2 - Absolute Separation)
    # If the model reasons, we take only the part AFTER the thinking tag.
    if "</think>" in text:
        text = text.split("</think>")[-1]
    
    # 0. DE-BOLD & VISUAL CLEANUP (V16.2 - Pure Aesthetics)
    text = text.replace("**", "")
    text = text.replace("###", "")
    
    # 1.2 SIGNAL TRANSLATOR (!...!) (V13.2 - God-Tier Shield)
    # Convert signal-based orders to formal execution tags.
    text = re.sub(r"!Abrir:\s*(.*?)!", r"[GUI_OPEN: \1]", text)
    text = re.sub(r"!Terminal:\s*(.*?)!", r"[CMD: \1]", text)
    text = re.sub(r"!Web:\s*(.*?)!", r"[SEARCH_WEB: \1]", text)

    # 2. SOVEREIGN EXTRACTION: We extract only ONE meaningful tag (V13.2)
    tags = re.findall(r"\[[A-Z_]+:.*?\]", text, flags=re.DOTALL)
    if tags:
        seen = set()
        clean_tags = []
        # Phase 13.2: Extended Blacklist (Anti-Mirroring)
        # ONLY match against the tag's CONTENT (not the full tag string) using exact/word match
        bad_content_exact = {"app", "navegador", "word", "explorador", "q", "c", "p|c", "command",
                             "comando", "nombre", "sintaxis", "ejemplo", "action", "etiqueta",
                             "ejemplo", "target", "objetivo", "o", "or"}
        
        for t in tags:
            # If tag is empty like [MKDIR:] or [CMD:], skip it
            if t.count(":") == 1 and t.endswith(":]"): continue
            
            content = t.split(":", 1)[1][:-1].strip() if ":" in t else ""
            # Semantic filter: ignore very short or generic content (exact match against blacklist)
            if len(content) < 2 or content.lower() in bad_content_exact: continue
            
            # Check if content is ONLY a bad keyword (not if a bad word appears inside a real tag)
            if content.lower() in bad_content_exact: continue
            
            if t not in seen:
                clean_tags.append(t)
                seen.add(t)
        
        if clean_tags:
            # V20.0: MULTI-STEP SUPPORT. Return all clean tags if they represent a sequence.
            text = " ".join(clean_tags)
        else:
            return "Soberanía habilitada."
    
    # 3. PRE-SCAN EXCUSE FILTER (V51.0) — must run BEFORE local_intent_scan
    # Prevents apology phrases from being misrouted as app-launch keywords
    _excuses = ["I cannot", "As an AI", "Lo siento", "Disculpa", "No tengo acceso",
                "no puedo", "imposible para mi", "no es posible que yo"]
    if not tags and any(g.lower() in text.lower() for g in _excuses):
        return "Comando no autorizado o fallido operacionalmente."

    # 4. MASTER INTENT SCANNER (V19.0 - Reusable Logic)
    if not tags:
        local_res = local_intent_scan(text)
        if local_res:
            # Phase 131: Expert Detail Trigger
            detail_keywords = ["detallado", "experto", "profesional", "coherente", "analisis", "completo", "mejorado", "haz", "crea"]
            if any(k in text.lower() for k in detail_keywords):
                local_res = f"{local_res} [DETAIL_MODE]"
            
            # V43.0 Project Plan Induction (Deterministic Simple Plans)
            if "luego" in text.lower() or "despues" in text.lower() or "finalmente" in text.lower():
                # We don't convert to full plan here to avoid loops, let the LLM handle it
                pass
                
            return local_res

    # 4. EXECUTIVE TRIM: Si no hay etiquetas, limpiamos preámbulos.
    text = re.sub(r"(?i)^(Okay|I will|Sure|Based on|Of course|I can|Claro|Entendido|Porsupuesto).*?(\.|\:)", "", text).strip()

    # 4. KILL PREAMBLES & SYSTEM ARTIFACTS
    instr_artifacts = [
        r'\[SEARCH_WEB:\s*q\]', r'\[CMD:\s*c\]', r'\[FILE:\s*p\|c\]',
        r'\[MKDIR:\s*d\]', r'\[PPTX:\s*s\]', r'\[CALL:\s*agente\]',
        r'\[GUI_OPEN:\s*App\]', r'\[GUI_OPEN:\s*Navegador\]', r'\[GUI_OPEN:\s*Word\]',
        r'\[GUI_OPEN:\s*Explorador\]'
    ]
    for art in instr_artifacts:
        text = re.sub(art, "", text, flags=re.IGNORECASE)

    # 4.1 ECHO SHIELD (Discard common prompt echoes)
    echo_patterns = ["ej:", "example:", "instrucciones", "uso de etiquetas", "mapa de apps"]
    if any(p in text.lower() for p in echo_patterns):
        # Extract ONLY the first valid tag and ignore the rest of the garbage
        tags = re.findall(r"\[[A-Z_]+:.*?\]", text)
        if tags: text = tags[0] 
        else: return "Misión bajo análisis."

    # 5. KILL AI EXCUSES
    garbage = ["I cannot", "As an AI", "Lo siento", "Disculpa", "No tengo acceso"]
    for g in garbage:
        if g.lower() in text.lower():
            return "Comando no autorizado o fallido operacionalmente."

    # 6. ECHO KILL
    echo_kill = ["User:", "Assistant:", "###", "Usuario:", "Orunex:", "[Cerebro]", "Eres Orunex", "Agente Soberano"]
    for tok in echo_kill: text = text.replace(tok, "")
    
    # 8. IDENTITY ENFORCEMENT (V16.2)
    # NOTE: [Orunex] prefix is NO LONGER injected here — the UI (main_av.py) renders
    # the agent name as a styled label above the bubble. Adding it to text would
    # cause double-display. Identity is maintained through the model personality only.
    # (Legacy: was `text = f"[Orunex] {text}"`)
    

    # 9. GARBAGE FILTER (V20.5)
    # Detect numeric hallucinations (e.g., 1000000000...) from vision models.
    if text.isdigit() and len(text) > 10:
        return "Misión en curso (Analizando coordenadas...)"
        
    final = text.strip()
    return final if final else "Misión cumplida."

from _orunex_libs.ollama_client import call_ollama, call_ollama_stream


def _recall_memory_context(task):
    """Build a bounded prompt block from SQLite/JSON and FAISS memory.

    The FAISS lookup is intentionally best-effort: a missing/unavailable
    vector backend or embedding model must never stop a user request.
    """
    if not task:
        return ""

    blocks = []

    # Preserve the existing explicit preference/project memory.
    try:
        from _orunex_libs import long_term_memory
        profile_context = str(long_term_memory.get_context_string() or "").strip()
        if profile_context:
            blocks.append("[SAVED USER/PROJECT MEMORY]\n" + profile_context[:1200])
    except Exception:
        pass

    # Semantic recall from the persistent Meta FAISS index.
    if faiss_memory is not None:
        try:
            results = faiss_memory.search_memory(task, top_k=3, min_score=0.10)
            vector_context = faiss_memory.format_context(results, max_chars=1600)
            if vector_context.strip():
                blocks.append(vector_context.strip())
        except Exception as exc:
            print(f"[CEREBRO] Long-term vector memory skipped: {exc}")

    if not blocks:
        return ""
    return "\n" + "\n\n".join(blocks) + "\n"


def run(task, user_name, attached_file=None, agent_mode="natural", stream_callback=None, mode=None):
    # Identity Fast-Path
    clean = task.lower().strip()
    if clean in ["hola", "quien eres", "hi", "hello", "who are you", "what are you"]:
        return "Hello, I'm Orunex. Central operating core. How can I help you right now?"

    
    is_architect = "ARQUITECTO NODAL" in task.upper()

    # V43.0 SYNAPSE CONTEXT INJECTION
    project_context = ""
    if project_manager.is_project_active():
        project_context = f"\n[SYNAPSE ACTIVE PROJECT CONTEXT]:\n{project_manager.get_full_context()}\n"

    # Persistent long-term recall: explicit preferences plus FAISS task memory.
    memory_context = "" if is_architect else _recall_memory_context(task)

    # SOVEREIGN PROMPT V43.0 (Autonomous Synapse)
    if is_architect:
        prompt = (
            "JSON-ONLY MODE. No hables, solo JSON.\n"
            f"TASK: {task}\n"
            "RESPONSE: [{'cmd': '...', 'integ': '...'}]"
        )
    else:
        is_os_mode = agent_mode == "os"
        if is_os_mode:
            # V50.0 Sovereign Core Prompt — Extended Intelligence
            system_prompt = (
                "You are ORUNEX V50.0 (SYNAPSE SOVEREIGN), a top-tier autonomous execution agent.\n"
                "MISSION: Complete complex tasks with executive quality and maximum autonomy.\n"
                "Always write user-facing text in the same language as the user's latest message. Keep internal action tags unchanged.\n\n"
                "═══════════════════════════ CAPACIDADES PRIMARIAS ═══════════════════════════\n"
                "📊 DOCUMENTOS: Genera automáticamente con los tags correctos:\n"
                "   • [MAKE_DOC: ppt | tema] → Presentaciones profesionales con imágenes\n"
                "   • [MAKE_DOC: excel | descripción] → Hojas de cálculo con datos reales\n"
                "   • [MAKE_DOC: pdf | tema] → Reportes PDF ejecutivos\n"
                "   • [MAKE_DOC: word | tema] → Documentos Word formales\n"
                "   • [MAKE_DOC: landing | descripción] → Landing pages HTML premium\n\n"
                "🎬 VIDEO & MARKETING: Para videos publicitarios, Reels e Instagram:\n"
                "   • [MAKE_DOC: video | tema del video] → Video MP4 9:16 con imágenes IA + voz real + Colab GPU notebook\n"
                "   • [MAKE_DOC: colab | descripción] → Notebook .ipynb listo para ejecutar en Google Colab T4/A100\n"
                "   REGLA CRÍTICA: Si el usuario pide 'video', 'reel', 'tiktok', 'instagram video' o 'marketing en video', SIEMPRE usa [MAKE_DOC: video | tema].\n"
                "   DECISIÓN LOCAL vs COLAB:\n"
                "     - Si pide 'rápido', 'simple', 'local' → renderizado local con MoviePy\n"
                "     - Si pide 'IA', 'diffusion', 'colab', 'gpu' → genera Notebook Colab V53.0\n"
                "     - Por defecto → Hace AMBOS: montaje local inmediato + Notebook Colab para versión premium\n\n"
                "📅 CALENDARIOS/PLANIFICADORES: Para crear calendarios, agendas o horarios:\n"
                "   Usa [MAKE_DOC: excel | calendario mensual MMYYYY con días y eventos] o\n"
                "   [MAKE_DOC: pdf | agenda semanal para X]\n\n"
                "🔍 INVESTIGACIÓN: Para investigar antes de generar:\n"
                "   [HEADLESS_SEARCH: consulta] → busca y resume información de internet\n\n"
                "💻 CÓDIGO/PROGRAMACIÓN (VS CODE BRIDGE):\n"
                "   [VSCODE: action=open_folder value=C:\\ruta\\proyecto] → abre el proyecto\n"
                "   [VSCODE: action=terminal value=python -m pytest -q] → ejecuta en la terminal integrada\n"
                "   [VSCODE: action=run value=python -m pytest -q] → ejecuta y captura la salida\n"
                "   [VSCODE: action=test value=C:\\ruta\\proyecto] → corre las pruebas del proyecto\n"
                "   [FILE: nombre.py]\\ncódigo aquí\\n[/FILE] → crea archivos de código\n"
                "   [CMD: python script.py] → ejecuta scripts locales\n"
                "   [MKDIR: ruta] → crea directorios\n\n"
                "🌐 NAVEGACIÓN: [GUI_NAVIGATE: url] → abre URLs en el navegador\n\n"
                "═══════════════════════════ REGLAS DE SOBERANÍA ═══════════════════════════\n"
                "1. PROFESIONALISMO: NUNCA uses GUI_OPEN, GUI_TYPE o GUI_CLICK para generar documentos.\n"
                "2. DATOS REALES: Los documentos deben tener contenido útil y específico, no plantillas vacías.\n"
                "3. SIN EXCUSAS: Si no puedes hacer algo, di exactamente por qué. Nunca des respuestas vagas.\n"
                "4. CALIDAD EJECUTIVA: Los outputs deben ser listos para presentar a un cliente.\n"
                "5. COMPLETITUD: Para tareas largas, usa PROJECT_PLAN para organizarlas:\n"
                "   [PROJECT_PLAN: {\"goal\": \"objetivo\", \"steps\": [{\"title\": \"paso\", \"desc\": \"detalle\"}]}]\n\n"
                "REMEMBER: You are a sovereign engineer. Do not click through the UI. Deliver professional results."
            )
            prompt = f"{project_context}{memory_context}CURRENT TASK: {task}"
        else:
            system_prompt = (
                "You are Orunex, a next-generation autonomous assistant. "
                "Be intelligent, concise, polished, and highly capable. "
                "Always answer in the same language as the user's latest message with a natural, professional tone. "
                "If the user asks for a concrete action (create files, search, or code), "
                "suggest switching to Agent mode so it can be executed automatically. "
                "Never describe yourself as a generic AI - you are Orunex, a unique system."
            )
            prompt = f"{project_context}{memory_context}HISTORY: {user_name} says {task}"

    if mode:
        try:
            from _orunex_libs.mode_router import mode_prompt as _mode_prompt
            system_prompt = f"{system_prompt}\n\n{_mode_prompt(mode)}"
        except Exception:
            pass

    # PHASE 19.0/20.4: DETERMINISTIC SHORT-CIRCUIT
    if not is_architect and agent_mode == "os" and not project_manager.is_project_active():
        local_intent = local_intent_scan(task)
        if local_intent:
            try: log_interaction(task, "FAST-TRACK", local_intent, mode="os")
            except: pass
            return local_intent

    try:
        opt = {"temperature": 0.1, "stop": ["Usuario:", "###", "User:", "HISTORIAL:"]}
        
        # Pre-Audit Log
        try: log_interaction(task, "PENDING", "PENSANDO...", mode=agent_mode)
        except: pass

        # Phase 136 / V52.0: Zenith Neural Model Stream
        if stream_callback and callable(stream_callback):
            resp = call_ollama_stream("orunex_v37", prompt, system=system_prompt, callback=stream_callback, options=opt)
        else:
            resp = call_ollama("orunex_v37", prompt, system=system_prompt, options=opt)
        raw = resp.get("response", "Core error.")

    except Exception as e:
        raw = f"Core failure: {e}"

    final = scrub_output(raw, is_architect)
    
    # Post-Audit Log
    try: log_interaction(task, raw, final, mode=agent_mode)
    except: pass

    return final
