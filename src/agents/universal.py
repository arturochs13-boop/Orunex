import os
import sys
import re

# Add libs to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from _orunex_libs.ollama_client import call_ollama

def run(task, user_name, attached_file=None, mode="os"):
    """
    Universal Orunex Orchestrator.
    Unifies all specialized reasoning under the orunex-zenith engine.
    """
    from . import cerebro
    
    # Route to cerebro but with unified Zenith settings
    # Cerebro already uses orunex-zenith and specialists/
    return cerebro.run(task, user_name, attached_file=attached_file, agent_mode=mode)

def voice_synthesis(text, user_name):
    """
    Neuro-Voice Synthesis using Orunex Voice specialist.
    """
    specialist_path = os.path.join(os.path.dirname(__file__), "specialists", "neural_voice.txt")
    with open(specialist_path, "r", encoding="utf-8") as f:
        voice_p = f.read()
    
    prompt = f"El usuario es {user_name}. Respuesta tecnica: '{text}'. Genera respuesta oral amigable y corta:"
    
    # V37.3: Use the robust orunex_v37 model for voice framing
    resp = call_ollama("orunex_v37", prompt, system=voice_p)
    raw = resp.get("response", "")
    
    if not raw: return "" # Silencio si no hay respuesta inteligente
    
    # Clean for TTS
    clean = re.sub(r'\[.*?\]', '', raw).strip()
    clean = clean.replace('*', '').replace('#', '').strip()
    return clean
