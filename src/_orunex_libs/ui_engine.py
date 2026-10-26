"""
ui_engine.py — Orunex Elite Design System V41.0
Motor central de generación de interfaces de alta gama (Glassmorphism & Executive Styling).
"""

ORUNEX_PALETTE = {
    "bg_dark":      "#0A0F1E",   # Espacio profundo
    "navy":         "#1B2A4A",   # Navy ejecutivo
    "gold":         "#C9A84C",   # Oro Orunex
    "cyber_blue":   "#00D1FF",   # Neón azul
    "glass_bg":     "rgba(27, 42, 74, 0.65)", # Navy traslúcido
    "glass_border": "rgba(201, 168, 76, 0.4)", # Oro suave
    "text_main":    "#FFFFFF",
    "text_dim":     "#B0BEC5",
}

def get_glass_styles():
    """Devuelve el bloque de estilos CSS para el efecto Glassmorphism Élite."""
    return f"""
    .orunex-glass {{
        background: {ORUNEX_PALETTE["glass_bg"]};
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid {ORUNEX_PALETTE["glass_border"]};
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        color: {ORUNEX_PALETTE["text_main"]};
        padding: 20px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    .orunex-glass:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 40px 0 {ORUNEX_PALETTE["gold"]}44;
        border-color: {ORUNEX_PALETTE["gold"]};
    }}
    .orunex-glow-text {{
        color: {ORUNEX_PALETTE["gold"]};
        text-shadow: 0 0 10px {ORUNEX_PALETTE["gold"]}88;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
    }}
    .orunex-btn {{
        background: linear-gradient(135deg, {ORUNEX_PALETTE["navy"]}, {ORUNEX_PALETTE["bg_dark"]});
        border: 1px solid {ORUNEX_PALETTE["gold"]};
        color: {ORUNEX_PALETTE["gold"]};
        padding: 10px 24px;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 600;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .orunex-btn:hover {{
        background: {ORUNEX_PALETTE["gold"]};
        color: {ORUNEX_PALETTE["bg_dark"]};
        box-shadow: 0 0 20px {ORUNEX_PALETTE["gold"]}aa;
    }}
    """

def generate_glass_container(content: str, title: str = "") -> str:
    """Genera un contenedor Glassmorphism con el contenido inyectado."""
    header = f"<h2 class='orunex-glow-text'>{title}</h2>" if title else ""
    return f"""
    <div class="orunex-glass">
        {header}
        <div class="orunex-content">
            {content}
        </div>
    </div>
    """

def get_executive_layout(content: str, title: str = "ORUNEX ELITE") -> str:
    """Devuelve un layout HTML completo con el estilo de Orunex V41.0."""
    styles = get_glass_styles()
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&family=Inter:wght@300;600&display=swap" rel="stylesheet">
        <style>
            body {{
                background-color: {ORUNEX_PALETTE["bg_dark"]};
                color: {ORUNEX_PALETTE["text_main"]};
                font-family: 'Inter', sans-serif;
                margin: 0;
                padding: 40px;
                background-image: radial-gradient(circle at 50% 50%, {ORUNEX_PALETTE["navy"]} 0%, {ORUNEX_PALETTE["bg_dark"]} 100%);
                min-height: 100vh;
            }}
            {styles}
        </style>
    </head>
    <body>
        {generate_glass_container(content, title)}
    </body>
    </html>
    """
