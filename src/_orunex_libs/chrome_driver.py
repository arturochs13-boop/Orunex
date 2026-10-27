"""
chrome_driver.py — Motor Chrome Orunex V37 (Dual Engine)
- open_url_in_chrome(): Abre URLs de forma nativa (subprocess). NO SE CIERRA.
- launch_chrome_stealth(): Selenium avanzado, solo para scraping que requiere JS.
"""
import os
import time
import subprocess
import warnings

# Suppress ResourceWarnings globally for this module
warnings.simplefilter('ignore', ResourceWarning)

# Global registry to prevent GC from closing Selenium sessions
DRIVER_SESSIONS = []


def open_url_in_chrome(url: str, profile_name: str = "Invitado") -> str:
    """
    MÉTODO PRINCIPAL para abrir URLs (YouTube, web, etc.)
    Usa subprocess directo contra chrome.exe — NUNCA se cierra solo.
    """
    try:
        from .app_integrations_manager import get_chrome_profile_dir, detect_chrome

        chrome_info = detect_chrome()
        if not chrome_info:
            # Fallback: usar 'start chrome' de Windows
            subprocess.Popen(
                f'start chrome "{url}"',
                shell=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return f"[OK] Chrome abierto via Windows Shell: {url}"

        chrome_exe = chrome_info["path"]
        user_data_dir, profile_dir = get_chrome_profile_dir(profile_name)

        is_guest = profile_name.lower() in ("invitado", "guest", "guest profile")

        cmd = [chrome_exe]
        # SIEMPRE especificar perfil para evitar el selector de perfiles
        if is_guest:
            cmd.append("--profile-directory=Default")
        else:
            cmd.append(f"--profile-directory={profile_dir}")
        if url:
            cmd.append(url)

        # CREATE_NEW_PROCESS_GROUP makes Chrome fully independent of Python
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        return f"[OK] Chrome abierto (perfil: {profile_name}): {url}"

    except Exception as e:
        # Ultimate fallback
        try:
            os.startfile(url)
            return f"[OK] URL abierta con navegador predeterminado: {url}"
        except:
            return f"[ERR] No se pudo abrir Chrome: {e}"


def launch_chrome_stealth(url: str = "", profile_name: str = "Invitado") -> str:
    """
    Lanza Chrome con undetected-chromedriver (Selenium).
    SOLO usar cuando se necesita control JS (scraping, extracción de datos).
    Para reproducir URLs, usar open_url_in_chrome() en su lugar.
    """
    global DRIVER_SESSIONS
    driver = None
    try:
        import undetected_chromedriver as uc  # type: ignore
        from .app_integrations_manager import get_chrome_profile_dir

        user_data_dir, profile_dir = get_chrome_profile_dir(profile_name)

        options = uc.ChromeOptions()
        options.add_argument("--no-first-run")
        options.add_argument("--password-store=basic")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=es-MX")

        is_guest = profile_name.lower() in ("invitado", "guest", "guest profile")
        if not is_guest:
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile_dir}")
        else:
            import tempfile
            tmp_dir = tempfile.mkdtemp(prefix="orunex_chrome_")
            options.add_argument(f"--user-data-dir={tmp_dir}")

        driver = uc.Chrome(options=options, use_subprocess=True)
        DRIVER_SESSIONS.append(driver)
        _patch_driver(driver)

        if url:
            driver.get(url)
            time.sleep(1)

        return f"[OK] Chrome Stealth abierto (perfil: {profile_name})"

    except Exception as e:
        err_msg = str(e).lower()
        if driver:
            try: driver.quit()
            except: pass

        if "user data directory is already in use" in err_msg or "handle is invalid" in err_msg:
            print(f"[WARN] Perfil bloqueado. Usando lanzamiento nativo...")
            return open_url_in_chrome(url, profile_name)
        return f"[ERR] Chrome Stealth falló: {e}"


def _patch_driver(driver):
    """Inyecta JavaScript para ocultar señales de automatización."""
    stealth_js = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['es-MX', 'es', 'en-US', 'en']});
    window.chrome = { runtime: {} };
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """
    try:
        driver.execute_script(stealth_js)
    except Exception:
        pass


def get_youtube_results_native(query: str, profile_name: str = "Invitado", max_results: int = 5):
    """Realiza una busqueda DIRECTA en YouTube via Chrome y extrae resultados."""
    try:
        import undetected_chromedriver as uc
        from .app_integrations_manager import get_chrome_profile_dir

        user_data_dir, profile_dir = get_chrome_profile_dir(profile_name)
        options = uc.ChromeOptions()

        is_guest = profile_name.lower() in ("invitado", "guest")
        if not is_guest:
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile_dir}")

        driver = uc.Chrome(options=options, use_subprocess=True)
        _patch_driver(driver)

        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        driver.get(search_url)
        time.sleep(3)

        js_extract = """
        let results = [];
        let vids = document.querySelectorAll('ytd-video-renderer');
        for(let v of vids) {
            let titleEl = v.querySelector('#video-title');
            if(titleEl && titleEl.href) {
                results.push({
                    "title": titleEl.innerText.trim(),
                    "url": titleEl.href,
                    "uploader": v.querySelector('#channel-name')?.innerText.trim() || "N/A"
                });
            }
        }
        return results.slice(0, 5);
        """
        results = driver.execute_script(js_extract)
        driver.quit()
        return results
    except Exception as e:
        print(f"[ERR] Native Search Youtube falló: {e}")
        return []
