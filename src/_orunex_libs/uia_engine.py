import time
import uiautomation as auto

def uia_click(element_name, timeout=5):
    """
    Sovereign UIA Engine V30.
    Busca elementos interactivos en todo el SO por su nombre, ignorando pixeles, OCR o coordenadas.
    Es 100% robusto a cambios de resolucion o tema.
    """
    print(f"[UIA_ENGINE] Buscando elemento de SO: '{element_name}'")
    try:
        # Búsqueda global por nombre de control
        control = auto.Control(Name=element_name)
        if control.Exists(timeout, 1):
            control.Click(simulateMove=False)
            time.sleep(0.5)
            print(f"[UIA_ENGINE] Clic exitoso en: '{element_name}'")
            return f"[OK] Clic UIA universal en '{element_name}'"
        else:
            print(f"[UIA_ENGINE] Elemento '{element_name}' no hallado en {timeout}s.")
            return f"[ERR] Elemento UIA '{element_name}' no existe."
    except Exception as e:
        print(f"[UIA_ENGINE] Falla estructural: {e}")
        return f"[ERR] Falla UIA: {e}"
