"""
sovereign_validator_v12.py — Script de Perfección Total V12.1
Verifica OS, UI, Logic, Integrations y Voice de Orunex.
"""
import os
import sys
import time
import subprocess
import threading

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import cerebro
from _orunex_libs import os_executor
from _orunex_libs import automation_daemon
from _orunex_libs import database

def test_log(msg):
    print(f" [CHECK] {msg}")

def run_tests():
    print("\n" + "="*50)
    print("      ORUNEX SOVEREIGN VALIDATOR V12.1")
    print("="*50 + "\n")

    score = 0
    total = 5

    # 1. OS EXECUTION TEST (Zero-Sim)
    test_log("Test 1: Ejecución OS (Escribir archivo real)...")
    try:
        task = "[FILE: v12_audit_confirm.txt]SOVEREIGN_V12_LEVEL_ACCESS[/FILE]"
        res = os_executor.intercept_and_execute(task)
        
        # Check in orunex_outputs
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        check_path = os.path.join(proj_root, "orunex_outputs", "v12_audit_confirm.txt")
        
        if os.path.exists(check_path):
            with open(check_path, "r") as f:
                content = f.read().strip()
            if content == "SOVEREIGN_V12_LEVEL_ACCESS":
                test_log("  -> [OK] Archivo escrito y verificado en disco.")
                score += 1
            else:
                test_log("  -> [FAIL] Contenido incorrecto.")
        else:
            test_log(f"  -> [FAIL] No se encontró el archivo en: {check_path}")
    except Exception as e:
        test_log(f"  -> [ERROR] {e}")

    # 2. WEB ANALYTICS TEST
    test_log("Test 2: Búsqueda Web Real-Time...")
    try:
        task = "[SEARCH_WEB: bitcoin price]"
        res = os_executor.intercept_and_execute(task)
        if "Resultados Web" in res and len(res) > 50:
            test_log("  -> [OK] Búsqueda DuckDuckGo exitosa.")
            score += 1
        else:
            test_log("  -> [FAIL] No se obtuvieron resultados válidos.")
    except Exception as e:
        test_log(f"  -> [ERROR] {e}")

    # 3. CORE COGNITION (Cerebro V11.2)
    test_log("Test 3: Razonamiento y Scrubber Nuclear...")
    try:
        task = "Dime un chiste corto de programadores y asegúrate de no usar nada de markdown."
        res = cerebro.run(task, "Validator")
        if res and "null" in res.lower() or "bit" in res.lower() or "chiste" in res.lower():
            if "<think>" not in res:
                test_log("  -> [OK] Cerebro respondió con humor y sin fugas.")
                score += 1
            else:
                test_log("  -> [FAIL] Fuga de pensamiento detectada.")
        else:
            test_log(f"  -> [FAIL] Respuesta inesperada o vacía: {res}")
    except Exception as e:
        test_log(f"  -> [ERROR] {e}")

    # 4. DAEMON HEARTBEAT
    test_log("Test 4: Integridad del Daemon de Automatización...")
    try:
        d = automation_daemon.get_daemon()
        if d:
            test_log("  -> [OK] Singleton del Daemon recuperado.")
            score += 1
        else:
            test_log("  -> [FAIL] Daemon no inicializado.")
    except Exception as e:
        test_log(f"  -> [ERROR] {e}")

    # 5. UI THEME CONSISTENCY
    test_log("Test 5: Consistencia de Tema Zenith V12.1...")
    try:
        import main_av
        if main_av.THEME["accent"] == "#00E5FF":
            test_log("  -> [OK] Paleta Zenith Cian confirmada en el núcleo.")
            score += 1
        else:
            test_log(f"  -> [FAIL] El tema no coincide: {main_av.THEME['accent']}")
    except:
        test_log("  -> [FAIL] No se pudo leer main_av.THEME")

    print("\n" + "="*50)
    pf = (score / total) * 100
    print(f" RESULTADO FINAL: {pf:.1f}%")
    print(" STATUS: " + ("PERFECTO 💠" if pf == 100 else "DEBÉIS SEGUIR UPGRADIENDO 🛠️"))
    print("="*50 + "\n")
    
    # Simple Cleanup
    try:
        os.remove(check_path)
    except: pass

if __name__ == "__main__":
    run_tests()
