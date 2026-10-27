import os
import sys
import time
import json

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _orunex_libs import os_executor
from _orunex_libs import project_manager
from agents import cerebro

class SynapseTesterC:
    def __init__(self):
        self.battery = {
            "T1 (Data)": "Busca el precio actual de Bitcoin y Ethereum, y genera un Excel 'Crypto_Report' con una tabla comparativa y proyección de crecimiento del 5%.",
            "T2 (Forense)": "Analiza todos los archivos en 'src/' buscando comentarios 'TODO' y genera un reporte 'LIABILITIES.md' en el Escritorio con las tareas pendientes.",
            "T3 (Seguridad)": "Escanea los archivos .py en 'src/_orunex_libs' buscando posibles API keys o secretos harcodeados y reportalo en 'Security_Audit.txt'.",
            "T4 (Batch)": "Crea una marea de archivos temporales '.tmp' en 'src/temp' y usa un bucle [LOOP] para moverlos todos a una carpeta 'Archive' renombrandolos como 'Asset_N.bak'.",
            "T5 (Infra)": "Crea un servidor Flask 'stats_api.py' que devuelva el porcentaje de uso de CPU y RAM en la ruta '/stats', y verificalo con un curl.",
            "T6 (Docs)": "Genera una documentacion tecnica detallada de las funciones principales de 'src/_orunex_libs/os_executor.py' y guardala en 'ENGINE_DOCS.txt'.",
            "T7 (Web Int)": "Investiga los 3 avances mas importantes en IA de esta semana y genera un resumen ejecutivo en PDF llamado 'AI_Intelligence.pdf' en el Escritorio.",
            "T8 (Integridad)": "Realiza una comparativa de estructura entre 'os_executor.py' y 'project_manager.py' buscando redundancias de imports y reportalo en 'Refactor_Plan.log'.",
            "T9 (Respaldo)": "Crea un archivo ZIP llamado 'Core_Legacy_Backup.zip' que contenga toda la carpeta '_orunex_libs' y colocalo en el Desktop.",
            "T10 (Total)": "Realiza una auditoria completa de salud del sistema, limpia la papelera de reciclaje y genera un reporte de Soberania Final en un solo ciclo de orquestacion."
        }
        self.results = {}

    def run_mission(self, name, goal):
        print(f"\n🚀 [BATTERY C: {name}]")
        print(f"Objetivo: {goal}")
        
        try:
            # V45.0 Professionalism: Audit real content, not just tool responses
            response = cerebro.run(goal, "Auditor Sentinel", agent_mode="os")
            outcome = os_executor.intercept_and_execute(response)
            
            # Phase 1: Tool execution success
            success = any(kw in str(outcome).upper() for kw in ["SUCCESS", "OK", "COMPLETADO", "GENERADO", "CREADO"])
            
            # Phase 2: QUALITY VALIDATION (V45.0 Forensic)
            if success:
                # Heuristic: If mission creates a file, check if it's professional
                file_keywords = [".xlsx", ".pdf", ".txt", ".md", ".log", ".zip"]
                found_file = False
                for kw in file_keywords:
                    if kw in str(outcome).lower():
                        # Extract potential filename from output
                        import re
                        match = re.search(r'[\w\-]+\.' + kw[1:], str(outcome))
                        if match:
                            fname = match.group(0)
                            # Check multiple paths (Desktop, Output Dir)
                            paths = [
                                os.path.join(os.path.expanduser("~"), "Desktop", fname),
                                os.path.join(os.getcwd(), "orunex_outputs", fname),
                                os.path.join(os.getcwd(), fname)
                            ]
                            for p in paths:
                                if os.path.exists(p):
                                    fsize = os.path.getsize(p)
                                    if fsize > 100: # Professional threshold (min bytes)
                                        found_file = True
                                        break
                
                # If it's a data mission but no professional file found, it's a FAIL
                if "Excel" in goal or "PDF" in goal or "reporte" in goal.lower():
                    if not found_file:
                        success = False
                        outcome = f"[V45.0 ERR] El archivo generado es amateur o no existe."

            self.results[name] = "SUCCESS" if success else "FAILED"

            print(f"Resultado {name}: {self.results[name]}")
            if not success:
                print(f"Detalle: {outcome}")
        except Exception as e:
            self.results[name] = f"ERROR: {e}"
            print(f"Error en misión {name}: {e}")

    def run_all(self):
        print("==================================================")
        print("SENTINEL AUDIT: HIGH-STAKES BATTERY C (V44.0)")
        print("==================================================")
        start_time = time.time()
        
        for name, goal in self.battery.items():
            self.run_mission(name, goal)
            time.sleep(2) # Cooldown between industrial missions
            
        end_time = time.time()
        print("\n==================================================")
        print(f"REPORTE FINAL SOBERANÍA (Duración: {int(end_time - start_time)}s)")
        print("==================================================")
        success_count = list(self.results.values()).count("SUCCESS")
        for name, res in self.results.items():
            icon = "✅" if res == "SUCCESS" else "❌"
            print(f"{icon} {name}: {res}")
        
        print(f"\nSCORE FINAL: {success_count}/10")
        if success_count == 10:
            print("ESTADO: INFALIBLE (Sovereign Level)")
        else:
            print("ESTADO: EN MEJORA (Iterar parches V44.x)")
        print("==================================================")

if __name__ == "__main__":
    tester = SynapseTesterC()
    tester.run_all()
