import os
import sys
import re

# Simulate the Orunex Environment
sys.path.append(os.path.join(os.getcwd(), "src"))

from agents.cerebro import run as cerebro_run
from _orunex_libs.os_executor import intercept_and_execute

def test_v36_3_prompt():
    user_prompt = 'BUSCA EN YOUTUBE"SYLVANIA EL RIO DE LOS LAMENTOS" Y REPRODUCE EL VIDEO QUE MÀS SE PAREZCA O COINCIDA'
    print(f"--- TEST PROMPT V36.3: '{user_prompt}' ---")
    
    # 1. Cerebro Intent Extraction
    # This simulates cerebro parsing the input
    res = cerebro_run(user_prompt, "User_Test", agent_mode="os")
    print(f"[CEREBRO OUTPUT]: {res}")
    
    if "[YOUTUBE:" in res:
        print("[OK] Intencion de YouTube detectada correctamente.")
    else:
        print("[ERR] Intencion NO detectada. Revisar regex.")
        return

    # 2. OS Executor (Clean & Play)
    # This will search DDG, pick the best video with orunex-v36, and launch Chrome
    # WARNING: This will open a Chrome window on the USER'S PC.
    print("\n[EXECUTING] Lanzando proceso de busqueda técnica...")
    try:
        final_res = intercept_and_execute(res)
        print(f"[FINAL RESULT]: {final_res}")
        if "reproduciendo" in str(final_res).lower():
            print("\n[SUCCESS] El comando ha sido enviado al driver de Chrome.")
        else:
            print("\n[WARN] El comando no confirmo reproduccion.")
    except Exception as e:
        print(f"[OS_EXEC ERR]: {e}")

if __name__ == "__main__":
    test_v36_3_prompt()
