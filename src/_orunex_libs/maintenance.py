import os
import shutil
import time
from datetime import datetime

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB

def rotate_logs():
    """Rotacion de logs para evitar saturacion de disco."""
    logs_to_check = [
        os.path.join(os.getcwd(), "simplex_debug.log"),
        os.path.join(os.getcwd(), "simplex_raw_debug.json"),
        os.path.join(os.getcwd(), "orunex.log")
    ]
    
    for log in logs_to_check:
        if os.path.exists(log) and os.path.getsize(log) > MAX_LOG_SIZE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = f"{log}.{timestamp}.bak"
            try:
                shutil.move(log, backup)
                print(f"DEBUG: Log rotado: {os.path.basename(log)} -> {os.path.basename(backup)}")
            except Exception as e:
                print(f"DEBUG: Error rotando {log}: {e}")

def kernel_health_check():
    """Verifica la salud de los procesos criticos del Kernel."""
    import psutil # type: ignore
    procs = ["simplex-chat.exe", "python.exe"]
    status = {}
    for p in procs:
        running = any(p.lower() in proc.name().lower() for proc in psutil.process_iter())
        status[p] = "OK" if running else "CRITICAL"
    return status

if __name__ == "__main__":
    rotate_logs()
    print(kernel_health_check())
