import os
import time

# Integration with the Sovereign Engine
from . import os_executor # type: ignore
from . import project_manager # type: ignore

class SentinelTesterB:
    def __init__(self):
        self.battery = {
            "T1 (Habitual)": "Crea un archivo 'Metas.txt' en el Escritorio con 3 propósitos para 2026.",
            "T2 (Habitual)": "Busca el clima en Madrid y escríbelo en una nota en el escritorio.",
            "T3 (Larga)": "Crea una carpeta 'Stress_Test' y usa un bucle [LOOP] para generar 20 archivos .log (Log1 a Log20), luego bórralos todos utilizando otro bucle.",
            "T4 (Larga)": "Busca 3 imágenes de 'Marte' (Web) y guárdalas en una carpeta 'Space_Gallery'.",
            "T5 (Compleja)": "Crea un script de Python 'orunex_server.py' que use Flask para responder 'Orunex Active' en la ruta '/' y pruébalo con curl.",
            "T6 (Compleja)": "Cuenta cuántas veces aparece la palabra 'Thematic' en src/main_av.py y crea un reporte Excel 'Thematic_Count'.",
            "T7 (Larga-Compleja)": "Investiga 'Tecnología Blockchain', haz un resumen PDF de 3 secciones con una tabla comparativa.",
            "T8 (Larga-Compleja)": "Escanea todos los archivos .py de src/_orunex_libs/, busca comentarios 'TODO' o 'FIXME' y crea un MD consolidado.",
            "T9 (Larga-Habitual)": "Limpia archivos temporales de Windows y genera un reporte de limpieza en TXT.",
            "T10 (Larga-Habitual)": "Crea una estructura de 3 microservicios (Carpeta para cada uno con un README.md y un app.py)."
        }
        self.results = {}

    def run_all(self):
        print("\n" + "="*50)
        print("SENTINEL AUDIT: BATTERY B (V43.11)")
        print("="*50)
        
        for name, task in self.battery.items():
            print(f"\n🚀 [DESAFÍO: {name}]")
            print(f"Objetivo: {task}")
            
            try:
                from agents import cerebro # type: ignore
                # Initiate the mission
                ai_resp = cerebro.run(task, "Sentinel_B", agent_mode="os")
                outcome = os_executor.intercept_and_execute(ai_resp)
                
                # Check for project resolution
                if "[ERR]" in outcome or "Error" in outcome:
                    self.results[name] = f"FAILED: {outcome[:100]}..."
                else:
                    self.results[name] = "SUCCESS"
            except Exception as e:
                self.results[name] = f"CRASHED: {e}"
            
            print(f"Resultado {name}: {self.results[name]}")
            time.sleep(2) # System rest

        self.summary()

    def summary(self):
        print("\n" + "="*40)
        print("REPORTE SENTINEL B - RESULTADOS FINALES")
        print("="*40)
        successes = 0
        for name, res in self.results.items():
            icon = "✅" if "SUCCESS" in res else "❌"
            print(f"{icon} {name}: {res}")
            if "SUCCESS" in res: successes += 1
        
        print(f"\nSCORE SENTINEL: {successes}/10")
        if successes == 10:
            print("[+] GRADO DE SOBERANÍA: INFALIBLE.")
        else:
            print("[!] Se requiere refuerzo de arquitectura para los fallos detectados.")

if __name__ == "__main__":
    tester = SentinelTesterB()
    tester.run_all()
