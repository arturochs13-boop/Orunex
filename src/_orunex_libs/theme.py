THEME_DARK = {
    "bg": "#0B132B",          # Deep Navy Blue backdrop
    "panel": "#14213D",       # Elevated Dark Blue panel
    "accent": "#4FC3F7",      # Vibrant Light Blue accent
    "success": "#66BB6A",     # Green
    "warning": "#FFB703",     # Orange/Amber
    "error": "#E63946",       # Red
    "text": "#F8F9FA",        # Clear White
    "text_dim": "#ADB5BD",    # Gray textual accents
    "border": "#28385E"       # Subtle panel border
}

THEME_LIGHT = {
    "bg": "#F8F9FA",          # Clean Off-White backdrop
    "panel": "#FFFFFF",       # Pure White panel
    "accent": "#0077B6",      # Strong Ocean Blue accent
    "success": "#2D6A4F",     # Dark Green
    "warning": "#FB8500",     # Deep Orange
    "error": "#D90429",       # Deep Red
    "text": "#212529",        # Charcoal / Near Black
    "text_dim": "#6C757D",    # Dim Gray
    "border": "#E9ECEF"       # Soft border
}

# The active theme pointer (defaulting to dark initially)
THEME = THEME_DARK.copy()

def switch_theme(mode: str):
    """Updates the THEME dictionary in-place based on 'dark' or 'light'."""
    global THEME
    new_theme = THEME_DARK if mode == "dark" else THEME_LIGHT
    for k, v in new_theme.items():
        THEME[k] = v
