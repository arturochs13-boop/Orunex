"""
motion_engine.py — Orunex Kinetic Animation System V41.0
Motor de animaciones CSS y curvas de movimiento élite.
"""

# Curvas de movimiento profesional (Bezier)
CURVES = {
    "smooth_entry": "cubic-bezier(0.16, 1, 0.3, 1)", # Entrada rápida, frenado suave
    "bounce":       "cubic-bezier(0.68, -0.6, 0.32, 1.6)",
    "linear":       "linear",
    "soft_in_out":  "cubic-bezier(0.42, 0, 0.58, 1)",
}

def get_motion_keyframes():
    """Devuelve los Keyframes CSS para animaciones cinéticas élite."""
    from .ui_engine import ORUNEX_PALETTE
    gold = ORUNEX_PALETTE["gold"]
    
    return f"""
    @keyframes orunex-fade-in-up {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes orunex-glow-pulse {{
        0% {{ box-shadow: 0 0 5px {gold}55; }}
        50% {{ box-shadow: 0 0 25px {gold}aa; }}
        100% {{ box-shadow: 0 0 5px {gold}55; }}
    }}
    @keyframes orunex-shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}
    @keyframes orunex-floating {{
        0% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-10px); }}
        100% {{ transform: translateY(0px); }}
    }}
    """

def get_animation_utility():
    """Genera utilidades CSS listas para usar en clases HTML."""
    return f"""
    .ani-fade-in {{
        animation: orunex-fade-in-up 0.8s {CURVES["smooth_entry"]} forwards;
    }}
    .ani-glow {{
        animation: orunex-glow-pulse 3s infinite {CURVES["soft_in_out"]};
    }}
    .ani-float {{
        animation: orunex-floating 5s infinite {CURVES["soft_in_out"]};
    }}
    .ani-delayed {{
        animation-delay: 0.3s;
    }}
    """

def inject_motion(content: str, animation_class: str = "ani-fade-in") -> str:
    """Envuelve contenido en un contenedor animado."""
    return f"<div class='{animation_class}'>{content}</div>"

def get_elite_motion_styles():
    """Compila todos los estilos de movimiento para inyectar en <style>."""
    return get_motion_keyframes() + get_animation_utility()
