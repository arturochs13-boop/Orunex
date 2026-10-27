import os
import json
import time

# Simulation/Execution Bridge
from . import os_executor # type: ignore
from . import project_manager # type: ignore

class SynapseTester:
    def __init__(self):
        self.battery = {
            "Habitual 1": "Crea una nota en el escritorio llamada 'Recordatorio' que diga 'Check Synapse V43'.",
            "Habitual 2": "Crea una carpeta en Documentos llamada 'Orunex_Test' y mueve todos los archivos .txt de Descargas allí (Simulado).",
            "Larga 3": "Crea 12 carpetas (Meses 2026) en Orunex_Workspace.",
            "Larga 4": "Busca 3 noticias sobre IA y crea un reporte PDF llamado 'IA_News'.",
            "Compleja 5": "Crea un script de Python llamado 'math_test.py' que calcule la serie de Fibonacci y ejecútalo.",
            "Compleja 6": "Diseña una landing page HTML básica con CSS incrustado sobre una agencia de viajes.",
            "Larga-Compleja 7": "Investiga 'DeepSeek-R1', haz un resumen MD y conviértelo a PDF.",
            "Larga-Compleja 8": "Analiza los procesos de Windows, busca los 3 que consumen más RAM y crea un Excel.",
            "Larga-Habitual 9": "Genera 5 archivos de texto con nombres aleatorios y comprimelos en un .zip.",
            "Larga-Habitual 10": "Crea una estructura de proyecto completa para una app de notas (Folders: src, tests, docs)."
        }
        self.results = {}

    def run_all(self):
        print("\n[V43.3] INICIANDO BATERÍA DE PRUEBAS DE INFALIBILIDAD...")
        for name, task in self.battery.items():
            print(f"\n--- [TEST: {name}] ---")
            print(f"Objetivo: {task}")
            
            try:
                # Direct Injection into the OS Executor
                # This will trigger the Synapse project logic if it gets complex enough
                from agents import cerebro # type: ignore
                ai_resp = cerebro.run(task, "Tester", agent_mode="os")
                outcome = os_executor.intercept_and_execute(ai_resp)
                
                # Check for errors
                if "[ERR]" in outcome or "Error" in outcome:
                    self.results[name] = f"FAILED: {outcome[:100]}..."
                else:
                    self.results[name] = "SUCCESS"
            except Exception as e:
                self.results[name] = f"CRASHED: {e}"
            
            print(f"Resultado: {self.results[name]}")
            time.sleep(1) # Let the OS Rest

        self.summary()

    def summary(self):
        print("\n" + "="*40)
        print("REPORTE DE INFALIBILIDAD V43.3")
        print("="*40)
        successes = 0
        for name, res in self.results.items():
            status = "✅" if "SUCCESS" in res else "❌"
            print(f"{status} {name}: {res}")
            if "SUCCESS" in res: successes += 1
        
        print(f"\nSCORE FINAL: {successes}/10")
        if successes < 10:
            print("[!] Se requieren parches de ingeniería para alcanzar la infalibilidad.")
        else:
            print("[+] INFALIBILIDAD ALCANZADA. Orunex es ahora Soberano.")

def start_audit():
    tester = SynapseTester()
    tester.run_all()

if __name__ == "__main__":
    start_audit()
