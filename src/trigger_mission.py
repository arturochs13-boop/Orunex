import sys
import os
import time

# Path setup
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from agents import cerebro
from _orunex_libs import os_executor

def run_mission():
    # SYLVANIA MISSION: The ultimate test of Visionary Orchestration
    # V30.5 DOC FACTORY TEST
    task = "crea un excel con 10 ideas de nombres para startups tecnologicas"
    print(f"[MISSION] Task: {task}")
    
    # 1. Get the technical sequence
    sequence = cerebro.run(task, "Usuario", agent_mode="os")
    print(f"[MISSION] Sequence: {sequence}")
    
    # 2. Execute with Total Win Sovereignty (V26.0)
    # 3-second buffer to guarantee focus stabilization
    time.sleep(3)
    result = os_executor.intercept_and_execute(sequence)
    print(f"[MISSION] Execution Results:\n{result}")

if __name__ == "__main__":
    run_mission()
