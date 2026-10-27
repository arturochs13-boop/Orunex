import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))
from _orunex_libs.headless_web import search_youtube
from _orunex_libs.ollama_client import call_ollama
import re

def debug_youtube(query):
    print(f"--- DEBUG YOUTUBE: '{query}' ---")
    vids = search_youtube(query)
    
    if not vids:
        print("[FAIL] No se encontraron videos.")
        return
        
    print(f"[OK] Se encontraron {len(vids)} videos:")
    v_list = ""
    for i, v in enumerate(vids):
        line = f"{i+1}. {v['title']} (by {v.get('uploader', 'N/A')})"
        print(f"  {line}")
        v_list += f"{line}\n"
    
    reasoning_prompt = f"El usuario quiere ver un video sobre '{query}'. De esta lista de YouTube, cual es el indice que mejor coincide? Responde UNICAMENTE con el numero del indice (1-{len(vids)}).\n\nLISTA:\n{v_list}"
    
    print("\n[THINKING] Consultando reasoning a orunex-v36...")
    resp = call_ollama("orunex-v36", reasoning_prompt, options={"temperature": 0.0})
    choice_raw = resp.get("response", "1")
    if "</think>" in choice_raw: choice_raw = choice_raw.split("</think>")[-1].strip()
    
    print(f"[AI CHOICE RAW]: {choice_raw}")
    
    try:
        match = re.search(r"\d+", choice_raw)
        idx = int(match.group()) - 1 if match else 0
        if idx < 0 or idx >= len(vids): idx = 0
    except:
        idx = 0
        
    winner = vids[idx]
    print(f"\n[WINNER]: '{winner['title']}'")
    print(f"[URL]: {winner['url']}")
    
    if "youtube.com/watch" in winner['url'] or "youtu.be" in winner['url']:
        print("[SUCCESS] La URL parece valida para reproduccion.")
    else:
        print("[WARN] La URL podria no ser directa.")

if __name__ == "__main__":
    debug_youtube("SYLVANIA EL RIO DE LOS LAMENTOS")
