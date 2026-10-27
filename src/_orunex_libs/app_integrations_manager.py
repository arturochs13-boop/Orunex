"""
integrations.py — Motor de Detección y Gestión de Integraciones V31
Detecta apps instaladas, lee perfiles de Chrome, y gestiona el perfil activo.
Los perfiles se almacenan en orunex_outputs/integrations.json (local, sin nube).
"""
import os
import json
import shutil

# ── Ruta de persistencia de perfiles (local al proyecto) ──────────────────────
_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_INTEG_FILE = os.path.join(_PROJ_ROOT, "orunex_outputs", "integrations.json")

def _load_integ() -> dict:
    try:
        os.makedirs(os.path.dirname(_INTEG_FILE), exist_ok=True)
        if os.path.exists(_INTEG_FILE):
            with open(_INTEG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "chrome_profiles": ["Invitado"],
        "active_chrome_profile": "Invitado"
    }

def _save_integ(data: dict):
    try:
        os.makedirs(os.path.dirname(_INTEG_FILE), exist_ok=True)
        with open(_INTEG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[INTEG] Error guardando: {e}")

# ── Detección de Chrome ────────────────────────────────────────────────────────
def detect_chrome() -> dict | None:
    """Retorna info de Chrome si está instalado."""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            return {"path": p, "name": "Google Chrome", "version": _get_chrome_version(p)}
    return None

def _get_chrome_version(path: str) -> str:
    try:
        import subprocess
        r = subprocess.run(
            ['powershell', '-command', f'(Get-Item "{path}").VersionInfo.FileVersion'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt"
            else 0,
        )
        return r.stdout.strip() or "Desconocida"
    except Exception:
        return "Desconocida"

# ── Detección de Office ────────────────────────────────────────────────────────
def detect_office() -> list[dict]:
    """Retorna lista de apps Office detectadas."""
    detected = []
    office_apps = {
        "Word": [
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
            r"C:\Program Files\Microsoft Office\Office16\WINWORD.EXE",
        ],
        "Excel": [
            r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
            r"C:\Program Files\Microsoft Office\Office16\EXCEL.EXE",
        ],
        "PowerPoint": [
            r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"C:\Program Files\Microsoft Office\Office16\POWERPNT.EXE",
        ],
        "Outlook": [
            r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
        ],
    }
    for name, paths in office_apps.items():
        for p in paths:
            if os.path.exists(p):
                detected.append({"name": name, "path": p})
                break
    return detected

# ── Detección de VSCode (V36.8) ────────────────────────────────────────────────
def detect_vscode() -> dict | None:
    """Busca VSCode en rutas estándar."""
    paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return {"path": p, "name": "VSCode", "version": "SOTA"}
    return None

# ── Gestión de Perfiles de Chrome ──────────────────────────────────────────────
def list_system_chrome_profiles() -> dict[str, str]:
    """Lee Local State de Chrome y retorna {nombre_visible: carpeta}.
    Siempre incluye 'Invitado' como opción especial."""
    profiles = {"Invitado": "Guest Profile"}
    
    local_state_path = os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State"
    )
    if not os.path.exists(local_state_path):
        return profiles
    
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        info_cache = state.get("profile", {}).get("info_cache", {})
        for folder, info in info_cache.items():
            name = info.get("name", folder)
            profiles[name] = folder
    except Exception as e:
        print(f"[INTEG] Error leyendo Local State: {e}")
    
    return profiles

def get_managed_profiles() -> list[str]:
    """Retorna la lista de perfiles gestionados por Orunex (guardados localmente)."""
    return _load_integ().get("chrome_profiles", ["Invitado"])

def add_chrome_profile(name: str) -> tuple[bool, str]:
    """Agrega un perfil al gestor de Orunex (validando que exista en Chrome)."""
    name = name.strip()
    if not name:
        return False, "El nombre no puede estar vacío."
    
    # Validate against system profiles
    sys_profiles = list_system_chrome_profiles()
    valid_names = [n.lower() for n in sys_profiles.keys()]
    
    if name.lower() not in valid_names and name.lower() != "invitado":
        return False, f"Perfil '{name}' no encontrado en Chrome. Verifica el nombre exacto en chrome://settings/."
    
    data = _load_integ()
    profiles = data.get("chrome_profiles", ["Invitado"])
    if name not in profiles:
        profiles.append(name)
        data["chrome_profiles"] = profiles
        _save_integ(data)
        return True, f"Perfil '{name}' agregado."
    return False, f"El perfil '{name}' ya está en la lista."

def remove_chrome_profile(name: str) -> tuple[bool, str]:
    """Elimina un perfil del gestor (no puede eliminar 'Invitado')."""
    if name == "Invitado":
        return False, "El perfil 'Invitado' es predeterminado y no puede eliminarse."
    data = _load_integ()
    profiles = data.get("chrome_profiles", ["Invitado"])
    if name in profiles:
        profiles.remove(name)
        data["chrome_profiles"] = profiles
        if data.get("active_chrome_profile") == name:
            data["active_chrome_profile"] = "Invitado"
        _save_integ(data)
        return True, f"Perfil '{name}' eliminado."
    return False, f"Perfil '{name}' no encontrado."

def get_active_profile() -> str:
    return _load_integ().get("active_chrome_profile", "Invitado")

def set_active_profile(name: str) -> tuple[bool, str]:
    data = _load_integ()
    if name not in data.get("chrome_profiles", ["Invitado"]):
        return False, f"'{name}' no está en los perfiles gestionados. Agrégalo primero."
    data["active_chrome_profile"] = name
    _save_integ(data)
    return True, f"Perfil activo: '{name}'"

def get_chrome_profile_dir(profile_name: str) -> tuple[str, str]:
    """Retorna (user_data_dir, profile_dir) para el perfil dado."""
    user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    if profile_name.lower() in ("invitado", "guest", "guest profile"):
        return user_data_dir, "Guest Profile"
    
    sys_profiles = list_system_chrome_profiles()
    for name, folder in sys_profiles.items():
        if name.lower() == profile_name.lower():
            return user_data_dir, folder
    
    return user_data_dir, "Default"
