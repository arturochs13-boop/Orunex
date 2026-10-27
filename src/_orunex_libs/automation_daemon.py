"""
automation_daemon.py  Daemon de Tareas Programadas de Orunex
Permite a Orunex ejecutar comandos de SO basados en horarios "Cron" invisibles.
Lee de un archivo automations.json y dispara tareas recurrentes via hilos asincronos.
"""
import os
import json
import time
import threading
import uuid
from datetime import datetime

# Se asume instalacion de 'schedule' via pip
try:
    import schedule
except ImportError:
    schedule = None

AUTOMATIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "automations.json")

class AutomationDaemon:
    def __init__(self, callback_execute_task=None):
        self.callback = callback_execute_task
        self.running = False
        self.thread = None
        
        # Crear archivo json base si no existe
        if not os.path.exists(os.path.dirname(AUTOMATIONS_FILE)):
            os.makedirs(os.path.dirname(AUTOMATIONS_FILE), exist_ok=True)
            
        if not os.path.exists(AUTOMATIONS_FILE):
            with open(AUTOMATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({"tasks": []}, f, indent=4)

    def load_and_schedule(self):
        """Lee el archivo JSON y monta las rutinas en la libreria schedule."""
        if not schedule:
            return

        schedule.clear()
        try:
            with open(AUTOMATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for task in data.get("tasks", []):
                if task.get("status") == "pausado": continue
                
                cmd = task.get("command")
                freq = task.get("frequency") # "diario", "hora", "minuto"
                time_str = task.get("time") # "15:00"
                
                if cmd and self.callback:
                    job = lambda c=cmd: self._job_runner(c)
                    
                    if freq == "minuto":
                        schedule.every().minute.do(job)
                    elif freq == "hora":
                        schedule.every().hour.do(job)
                    elif freq == "diario" and time_str:
                        schedule.every().day.at(time_str).do(job)
                        
        except Exception as e:
            pass

    def _job_runner(self, command):
        """Enviroment hook para inyectar el comando al executor asincronamente."""
        if self.callback:
            threading.Thread(target=self.callback, args=(command,), daemon=True).start()

    def get_all_tasks(self):
        """Devuelve la lista actual de tareas."""
        try:
            if not os.path.exists(AUTOMATIONS_FILE):
                return []
            with open(AUTOMATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("tasks", [])
        except:
            return []

    def remove_task(self, task_id):
        """Elimina una tarea por su ID."""
        try:
            with open(AUTOMATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            new_tasks = [t for t in data.get("tasks", []) if t.get("id") != str(task_id)]
            data["tasks"] = new_tasks
            
            with open(AUTOMATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            self.load_and_schedule()
            return True
        except:
            return False

    def add_task(self, command, frequency, time_str="", integration="Sistema"):
        """Añade una nueva tarea al registro persistente."""
        try:
            with open(AUTOMATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            task_id = str(uuid.uuid4())[:8]
            new_task = {
                "id": task_id,
                "command": command,
                "frequency": frequency,
                "time": time_str,
                "integration": integration,
                "status": "activo",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_run": "Nunca"
            }
            
            data.setdefault("tasks", []).append(new_task)
            
            with open(AUTOMATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            self.load_and_schedule()
            return task_id
        except Exception as e:
            print(f"[DAEMON ERR] No se pudo añadir tarea: {e}")
            return None

    def toggle_task(self, task_id):
        """Alterna entre activo y pausado."""
        try:
            with open(AUTOMATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for t in data.get("tasks", []):
                if t.get("id") == str(task_id):
                    t["status"] = "pausado" if t.get("status") == "activo" else "activo"
            
            with open(AUTOMATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            
            self.load_and_schedule()
            return True
        except:
            return False

    def start(self):
        if not schedule: return
        self.running = True
        self.load_and_schedule()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            schedule.run_pending()
            time.sleep(1)

# Singleton global instance
_daemon = AutomationDaemon()

def get_daemon():
    return _daemon
