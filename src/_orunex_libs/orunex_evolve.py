import os
import json
import re

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "orunex_system.log")
CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "..", "agents", "specialists", "calibration.json")

def evolve():
    """
    Analyzes logs for 'watches', 'relojes', or 'timepieces' and updates 
    the system calibration to harden the 'Zero-Watch' protocol.
    """
    if not os.path.exists(LOG_FILE):
        return "No logs found."

    hallucination_count = 0
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = f.read().lower()
        hallucination_count = logs.count("watch") + logs.count("reloj") + logs.count("timepiece")

    # Load or init calibration
    calibration = {"watch_shield_strength": 1.0, "hallucinations_detected": 0}
    if os.path.exists(CALIBRATION_FILE):
        try:
            with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
                calibration = json.load(f)
        except: pass

    # Incremental update based on feedback
    if hallucination_count > calibration.get("hallucinations_detected", 0):
        calibration["watch_shield_strength"] += 0.5
        calibration["hallucinations_detected"] = hallucination_count
        
        with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
            json.dump(calibration, f, indent=4)
        return f"Evolucion completada. Escudo reforzado a {calibration['watch_shield_strength']}."
    
    return "Sistema estable. No se requiere evolucion."

if __name__ == "__main__":
    print(evolve())
