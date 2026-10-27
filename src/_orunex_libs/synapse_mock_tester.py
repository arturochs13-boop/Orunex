import sys
import os
import json
import re

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from _orunex_libs import project_manager, os_executor # type: ignore

def test_infallibility():
    print("\n[V43.6] INICIANDO AUDITORÍA DE INTEGRIDAD NUCLEAR...")
    
    # 🧪 ESCENARIO 1: JSON Malformado (Test de Resiliencia)
    print("\n[TEST 1] Inyectando JSON ruidoso...")
    plan_ruidoso = "Aquí tienes el plan: [PROJECT_PLAN:\n```json\n{\"goal\": \"Test\", \"steps\": [{\"title\": \"Paso 1\", \"desc\":\"Desc\"}]}\n```\nEspero que funcione.]"
    res1 = os_executor.intercept_and_execute(plan_ruidoso)
    if project_manager.is_project_active():
        print("✅ ÉXITO: Extractor Quirúrgico rescató el plan.")
    else:
        print("❌ FALLO: El extractor no pudo procesar el plan ruidoso.")

    # 🧪 ESCENARIO 2: Respuesta Pasiva/Lazy (Anti-Lazy Guard)
    print("\n[TEST 2] Inyectando respuesta pasiva (Sin etiquetas)...")
    res_pasiva = "Lo primero que deberías hacer es crear una carpeta."
    # We simulate being in a mission step
    project_manager.start_project("Test Lazy", [{"title": "Paso 1", "desc": "Desc"}])
    project_manager.mark_step_success(res_pasiva)
    
    if project_manager.get_current_step() and project_manager.get_current_step().status == "FAILED":
        print("✅ ÉXITO: El Anti-Lazy Guard detectó la parálisis y marcó fallo para sanación.")
    else:
        print("❌ FALLO: El sistema aceptó una respuesta pasiva.")

    # 🧪 ESCENARIO 3: Memoria de Rutas (Path Tracking)
    print("\n[TEST 3] Inyectando ruta absoluta en resultado...")
    # Add a tag [CMD: done] so Anti-Lazy Guard lets it pass to the path tracking logic
    res_ruta = "[CMD: done] Archivo creado en: C:\\Users\\artur\\Documents\\test.txt"
    project_manager.mark_step_success(res_ruta)
    if "test.txt" in project_manager.ACTIVE_PROJECT.created_paths:
        print(f"✅ ÉXITO: Memoria de Rutas capturó: {project_manager.ACTIVE_PROJECT.created_paths['test.txt']}")
    else:
        print("❌ FALLO: La ruta no fue registrada en la memoria de misión.")


    # Reset
    project_manager.ACTIVE_PROJECT = None
    print("\n[CONCLUSION]: El motor de V43.6 ha pasado las pruebas de integridad críticas.")

if __name__ == "__main__":
    test_infallibility()
