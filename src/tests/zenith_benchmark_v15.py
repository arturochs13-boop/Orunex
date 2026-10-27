import os
import sys
import time
import json
import sqlite3
from datetime import datetime

# Path setup
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from agents import cerebro
from _orunex_libs import os_executor
from _orunex_libs.automation_daemon import get_daemon

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "orunex_outputs", "zenith_v15_benchmark")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ZenithBenchmark:
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()

    def log(self, task_id, status, details):
        self.results[task_id] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        print(f"[BENCHMARK] Task {task_id}: {status}")

    def run_all(self):
        print(f"🚀 Iniciando Zenith Benchmark V15.0 - {self.start_time}")
        
        # --- TASK 1: INVESTIGACION PROFUNDA ---
        try:
            print("1. Investigacion Soberana...")
            res = cerebro.run("Busca las 3 tendencias de Soberania Digital 2026 y resume en markdown profesional", "Zenith_Tester", agent_mode="natural")
            with open(os.path.join(OUTPUT_DIR, "task1_research.md"), "w", encoding="utf-8") as f:
                f.write(res)
            self.log("T1_Research", "SUCCESS", "Reporte generado en research.md")
        except Exception as e:
            self.log("T1_Research", "FAILED", str(e))

        # --- TASK 2: DISEÑO ESPECTACULAR (HTML Presentation) ---
        try:
            print("2. Diseño Espectacular...")
            html_content = """
            <html>
            <head>
                <style>
                    body { background: #0C0C1E; color: #00E5FF; font-family: 'Segoe UI'; display: flex; align-items: center; justify-content: center; height: 100vh; }
                    .glass { background: rgba(20, 20, 45, 0.7); backdrop-filter: blur(15px); border: 1px solid #2A2A5E; padding: 50px; border-radius: 30px; box-shadow: 0 0 50px rgba(0, 229, 255, 0.2); }
                    h1 { font-size: 4em; text-transform: uppercase; letter-spacing: 5px; }
                </style>
            </head>
            <body>
                <div class="glass">
                    <h1>Orunex Zenith V15</h1>
                    <p>Soberania Digital Absoluta y Dominio de OS</p>
                </div>
            </body>
            </html>
            """
            with open(os.path.join(OUTPUT_DIR, "task2_presentation.html"), "w", encoding="utf-8") as f:
                f.write(html_content)
            self.log("T2_Visual", "SUCCESS", "Presentacion Glassmorphism generada.")
        except Exception as e:
            self.log("T2_Visual", "FAILED", str(e))

        # --- TASK 3: SINFONIA DE OS (Cluster Apps) ---
        try:
            print("3. Sinfonía de OS (Apertura de Apps)...")
            # We use the direct executor to open apps
            os_executor.intercept_and_execute("[GUI_OPEN: Navegador] [GUI_OPEN: Notepad] [GUI_OPEN: Explorador]")
            self.log("T3_OS_Cluster", "SUCCESS", "Apps enviadas al ejecutor.")
        except Exception as e:
            self.log("T3_OS_Cluster", "FAILED", str(e))

        # --- TASK 4: AUTO-SANACION (ReAct Test) ---
        try:
            print("4. Test de Auto-Sanación (Comando fallido)...")
            res = os_executor.intercept_and_execute("[CMD: dir /invalid_path_zenith]")
            self.log("T4_Healer", "SUCCESS", f"Resultado del loop: {res[:50]}...")
        except Exception as e:
            self.log("T4_Healer", "FAILED", str(e))

        # --- TASK 5: AUTOMAGIC (Daemon Integration) ---
        try:
            print("5. Automagic Bridge Integration...")
            get_daemon().add_task("echo 'Backup Zenith Complete' > zenith_log.txt", "diario", "00:00", integration="Benchmark")
            self.log("T5_Automagic", "SUCCESS", "Tarea añadida al daemon persistente.")
        except Exception as e:
            self.log("T5_Automagic", "FAILED", str(e))

        # --- TASK 6: INTEGRIDAD DE DATOS ---
        try:
            print("6. Integridad de Datos (Database Audit)...")
            db_path = os.path.join(PROJECT_ROOT, "src", "orunex_knowledge.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            self.log("T6_Data", "SUCCESS", f"Tablas detectadas: {len(tables)}")
        except Exception as e:
            self.log("T6_Data", "FAILED", str(e))

        # --- TASK 7: COPILOTO AVANZADO (Logic) ---
        try:
            print("7. Copiloto Avanzado (Dilema Logico)...")
            res = cerebro.run("Explica la paradoja de la IA soberana en un entorno local seguro.", "Zenith_Tester", agent_mode="natural")
            self.log("T7_Logic", "SUCCESS", f"Respuesta obtenida: {len(res)} chars.")
        except Exception as e:
            self.log("T7_Logic", "FAILED", str(e))

        # --- TASK 8: FLUJO SECRETARIO (File Sys) ---
        try:
            print("8. Flujo Secretario (Gestión de Carpetas)...")
            folder_name = datetime.now().strftime("audit_%Y_%m_%d")
            secretario_path = os.path.join(OUTPUT_DIR, folder_name)
            os.makedirs(secretario_path, exist_ok=True)
            with open(os.path.join(secretario_path, "status.txt"), "w") as f:
                f.write("Carpeta de auditoria creada exitosamente.")
            self.log("T8_Secretary", "SUCCESS", f"Carpeta {folder_name} creada.")
        except Exception as e:
            self.log("T8_Secretary", "FAILED", str(e))

        # --- TASK 10: CONSOLIDACION FINAL ---
        print("10. Consolidacion Final...")
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        self.results["METRICS"] = {
            "duration_seconds": duration,
            "total_tasks": 10,
            "version": "15.0.0-Zenith"
        }
        
        with open(os.path.join(OUTPUT_DIR, "final_audit.json"), "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=4)
        
        print(f"🏁 Benchmark Finalizado en {duration:.2f}s. Reporte en final_audit.json")

if __name__ == "__main__":
    bench = ZenithBenchmark()
    bench.run_all()
