import os
import sys
import time
import json
import psutil
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

# Correct Path Setup for Orunex Architecture
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _orunex_libs import os_executor
from _orunex_libs import project_manager
from agents import cerebro

class SynapseTesterD:
    def __init__(self):
        self.battery = {
            "T1 (Crypto)": "Genera un reporte Excel 'Market_Index.xlsx' con el precio actual de BTC, ETH, SOL, XRP y ADA, incluyendo capitalizacion de mercado.",
            "T2 (Net)": "Realiza un escaneo de conexiones de red activas (sockets) del sistema y repórtalo en 'Network_Audit.txt'.",
            "T3 (Quality)": "Analiza la calidad de código (Technical Debt) de 'src/_orunex_libs' y genera un 'Code_Audit.md' con puntuaciones.",
            "T4 (Storage)": "Busca archivos de más de 5MB en el proyecto y repórtalos en 'Large_Files_Repo.json' para optimización.",
            "T5 (Doc)": "Genera una guía de arquitectura 'System_Map.md' basada en la estructura actual del proyecto.",
            "T6 (DB)": "Verifica la integridad de la base de datos 'orunex_knowledge.db' y repórtalo en 'DB_Health.log'.",
            "T7 (Logs)": "Analiza las acciones más frecuentes en 'audit_log.jsonl' y genera un CSV 'Action_Insights.csv' con el top 5.",
            "T8 (SHA)": "Genera hashes SHA-256 de 'os_executor.py' y 'cerebro.py' para control de integridad en 'Core_Hashes.txt'.",
            "T9 (Deps)": "Verifica vulnerabilidades o dependencias faltantes en 'requirements.txt' y repórtalo en 'Dependency_Report.md'.",
            "T10 (Total)": "Consolida un resumen ejecutivo de soberanía industrial V46.0 en 'Industrial_State.pdf' (via Markdown export)."
        }
        self.results = {}

    def run_mission(self, name, goal):
        print(f"\n🚀 [BATTERY D: {name}]")
        print(f"Objetivo: {goal}")
        start_time = time.time()
        
        try:
            # V46.0 Professionalism: Audit real content
            response = cerebro.run(goal, "Auditor Sentinel", agent_mode="os")
            outcome = os_executor.intercept_and_execute(response)
            
            # Phase 1: Tool execution success
            success = any(kw in str(outcome).upper() for kw in ["SUCCESS", "OK", "COMPLETADO", "GENERADO", "CREADO"])
            
            # Phase 2: QUALITY VALIDATION (Forensic)
            if success:
                file_keywords = [".xlsx", ".pdf", ".txt", ".md", ".log", ".json", ".csv"]
                found_file = False
                for kw in file_keywords:
                    if kw in str(outcome).lower():
                        import re
                        match = re.search(r'[\w\-]+\.' + kw[1:], str(outcome))
                        if match:
                            fname = match.group(0)
                            paths = [
                                os.path.join(os.getcwd(), "orunex_outputs", fname),
                                os.path.join(os.getcwd(), fname),
                                os.path.join(os.path.expanduser("~"), "Desktop", fname)
                            ]
                            for p in paths:
                                if os.path.exists(p):
                                    if os.path.getsize(p) > 100:
                                        found_file = True
                                        break
                
                if "Excel" in goal or "reporte" in goal.lower() or "csv" in goal.lower():
                    if not found_file:
                        success = False
                        outcome = "[V46.0 ERR] Archivo amateur descubierto (Tamaño insuficiente o inexistente)."

            self.results[name] = "SUCCESS" if success else "FAILED"
            duration = round(time.time() - start_time, 2)
            print(f"Resultado {name}: {self.results[name]} | {duration}s")
            
        except Exception as e:
            self.results[name] = f"ERROR: {e}"
            print(f"Error en misión {name}: {e}")

    def run_all(self):
        print("==================================================")
        print("SENTINEL AUDIT: HIGH-STAKES BATTERY D (V46.0)")
        print("Sovereign Mode: ON | Zero GUI Policy: ENFORCED")
        print("==================================================")
        
        for name, goal in self.battery.items():
            self.run_mission(name, goal)
            time.sleep(1)
            
        print("\n==================================================")
        print("REPORTE FINAL SOBERANÍA V46.0")
        print("==================================================")
        success_count = list(self.results.values()).count("SUCCESS")
        for name, res in self.results.items():
            icon = "✅" if res == "SUCCESS" else "❌"
            print(f"{icon} {name}: {res}")
        
        print(f"\nSCORE FINAL: {success_count}/10")
        print(f"ESTADO: {'INFALIBLE' if success_count == 10 else 'ESTABLE'}")
        print("==================================================")

if __name__ == "__main__":
    tester = SynapseTesterD()
    tester.run_all()
