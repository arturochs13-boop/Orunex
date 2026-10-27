from _orunex_libs.ollama_client import call_ollama

# LOCAL LAYOUT GUARD
LAYOUT = "ORUNEX_GUARD"

def decide_agent(task_prompt: str, has_image: bool = False) -> str:
    """
    Analiza la peticion y decide entre Vision, Voz o el Cerebro Central.
    """
    if has_image:
        return "Vision"

    task_lower = task_prompt.lower()
    
    # Heuristica rapida de vision
    vision_keywords = ["mira", "pantalla", "que ves", "imag", "captura", "screenshot", "que hay"]
    if any(k in task_lower for k in vision_keywords):
        return "Vision"

    # Heuristica rapida de voz/charla casual
    voice_keywords = ["hola", "charlar", "voz", "llama", "cuentame", "quien eres"]
    if any(k in task_lower for k in voice_keywords) and len(task_prompt) < 100:
        return "Voz"

    return "Cerebro" # Todo lo demas al Nucleo Central
