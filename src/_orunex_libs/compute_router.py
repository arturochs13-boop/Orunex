"""
compute_router.py — Orunex Compute Intelligence Router V53.0
Motor de decisión inteligente para seleccionar el entorno de cómputo óptimo.

Reglas de decisión:
  LOCAL (rápido, sin GPU cloud):
    - Montaje de imágenes + TTS + renderizado sin difusión IA
    - Clips de video cortos < 60 segundos
    - Compilación rápida de escenas existentes

  GOOGLE COLAB (GPU cloud T4/A100/H100):
    - Generación de video por difusión IA (SVD, Wan2.1, HunyuanVideo, AnimateDiff)
    - Entrenamiento de modelos LoRA
    - Videoclips de > 30 frames generados por IA
    - Renderizados a 4K o 8K con modelos pesados

  USUARIO TIENE PREFERENCIA EXPLÍCITA:
    - "usa colab", "en colab", "con gpu" → siempre Colab
    - "rápido", "local", "aquí" → siempre local
"""

# Palabras clave que fuerzan COLAB
COLAB_KEYWORDS = [
    "colab", "gpu", "cloud gpu", "a100", "t4", "hunyuanvideo", "wan2", "svd",
    "stable video diffusion", "diffusers", "generar con ia", "ia de video",
    "video diffusion", "animatediff", "lora", "entrenamiento", "training",
    "text to video", "image to video", "img2vid", "txt2vid", "4k", "8k",
    "alta calidad", "high quality render", "animacion ia"
]

# Palabras clave que fuerzan LOCAL
LOCAL_KEYWORDS = [
    "rapido", "local", "aqui", "simple", "montaje", "compilar",
    "juntar clips", "edicion simple", "sin ia", "overlay", "subtitulos",
    "captions", "quick", "fast", "no colab"
]

def decide_compute_env(task_description: str) -> dict:
    """
    Analiza la descripción de la tarea y decide el entorno de cómputo óptimo.
    
    Returns:
        dict con: 
          - env: "local" | "colab"
          - reason: Justificación de la decisión
          - colab_model: Modelo recomendado si env == "colab"
          - estimated_time_local_min: Tiempo estimado local en minutos
          - estimated_time_colab_min: Tiempo estimado en Colab
    """
    task_lower = task_description.lower()
    
    # Verificar preferencia explícita del usuario (máxima prioridad)
    for kw in LOCAL_KEYWORDS:
        if kw in task_lower:
            return {
                "env": "local",
                "reason": f"El usuario especificó modo local ('{kw}' detectado).",
                "colab_model": None,
                "estimated_time_local_min": 1,
                "estimated_time_colab_min": None
            }
    
    for kw in COLAB_KEYWORDS:
        if kw in task_lower:
            model = _recommend_colab_model(task_lower)
            return {
                "env": "colab",
                "reason": f"Tarea de alto cómputo detectada: '{kw}'. Se requiere GPU cloud.",
                "colab_model": model,
                "estimated_time_local_min": None,
                "estimated_time_colab_min": _estimate_colab_time(model)
            }
    
    # Heurísticas de decisión automática
    is_heavy = any(w in task_lower for w in [
        "video", "reel", "tiktok", "instagram", "comercial", "publicidad",
        "animacion", "cinematic", "fotorrealista", "photorealistic"
    ])
    
    is_very_heavy = any(w in task_lower for w in [
        "generar video", "crear video con ia", "video ia", "video inteligencia artificial"
    ])
    
    if is_very_heavy:
        model = _recommend_colab_model(task_lower)
        return {
            "env": "colab",
            "reason": "Generación de video con IA detectada. Se recomienda GPU cloud para calidad máxima.",
            "colab_model": model,
            "estimated_time_local_min": None,
            "estimated_time_colab_min": _estimate_colab_time(model)
        }
    elif is_heavy:
        return {
            "env": "local+colab",
            "reason": "Video marketing detectado. Se ejecuta montaje local rápido Y se genera Notebook Colab GPU para versión IA mejorada.",
            "colab_model": "stable-video-diffusion-img2vid-xt",
            "estimated_time_local_min": 2,
            "estimated_time_colab_min": 8
        }
    else:
        return {
            "env": "local",
            "reason": "Tarea estándar. Ejecución local óptima.",
            "colab_model": None,
            "estimated_time_local_min": 1,
            "estimated_time_colab_min": None
        }

def _recommend_colab_model(task: str) -> str:
    """Recomienda el mejor modelo SOTA de difusión de video para la tarea."""
    if any(k in task for k in ["wan", "wan2", "wan2.1"]):
        return "Wan2.1-T2V-14B"
    elif any(k in task for k in ["hunyuan", "hunyuanvideo"]):
        return "HunyuanVideo"
    elif any(k in task for k in ["animate", "animatediff"]):
        return "AnimateDiff-Lightning"
    elif any(k in task for k in ["svd", "stable video"]):
        return "stable-video-diffusion-img2vid-xt"
    else:
        return "stable-video-diffusion-img2vid-xt"  # Default: más accesible en T4

def _estimate_colab_time(model: str) -> int:
    """Tiempo estimado de ejecución en Colab (en minutos)."""
    times = {
        "Wan2.1-T2V-14B": 15,
        "HunyuanVideo": 25,
        "AnimateDiff-Lightning": 6,
        "stable-video-diffusion-img2vid-xt": 8,
    }
    return times.get(model, 10)

def format_decision_report(decision: dict) -> str:
    """Formatea la decisión de cómputo en un reporte legible."""
    env = decision["env"]
    reason = decision["reason"]
    
    if env == "local":
        return (
            f"[COMPUTE ROUTER] ENTORNO: LOCAL RAPIDO\n"
            f"  Razon: {reason}\n"
            f"  Tiempo estimado: ~{decision['estimated_time_local_min']} min"
        )
    elif env == "colab":
        model = decision["colab_model"]
        t = decision["estimated_time_colab_min"]
        return (
            f"[COMPUTE ROUTER] ENTORNO: GOOGLE COLAB GPU\n"
            f"  Razon: {reason}\n"
            f"  Modelo recomendado: {model}\n"
            f"  Tiempo estimado en Colab: ~{t} min\n"
            f"  Accion: Se generara Notebook .ipynb listo para ejecutar con 1 clic."
        )
    else:
        return (
            f"[COMPUTE ROUTER] ENTORNO: LOCAL + COLAB (DUAL MODE)\n"
            f"  {reason}\n"
            f"  Local: ~{decision['estimated_time_local_min']} min (montaje inmediato)\n"
            f"  Colab GPU: ~{decision['estimated_time_colab_min']} min (version IA premium)"
        )
