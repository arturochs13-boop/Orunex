"""
simplex_bridge.py  Puente entre Orunex y Simplex Messenger
Conecta al CLI de Simplex via WebSocket para enviar y recibir mensajes encriptados E2E.

Requisito: simplex-chat CLI corriendo en modo WebSocket  simplex-chat -p 5226
"""
import json
import threading
import time
import queue
import os
import re
import base64
from datetime import datetime
from typing import Optional, Any, Callable, Union, cast

def _clean_simplex_text(text: str) -> str:
    """Strip internal debug/metadata tokens before sending text to Simplex chat."""
    # Remove <think>...</think> deep reasoning blocks
    text = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.DOTALL)
    # Remove {CurlyBrace meta tags}
    text = re.sub(r'\{[^}]{0,80}\}', '', text)
    # Remove [BRACKET: value] debug tokens
    text = re.sub(r'\[[A-Z][A-Z0-9_]{1,20}(?::[^\]]{0,60})?\]', '', text)
    # Remove trailing interrogation marks and junk
    text = text.rstrip('? \t\n\r')
    # Collapse excess whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# --- Importacion opcional de websocket ---
try:
    import websocket  # type: ignore
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

SIMPLEX_PORT = 5227
SIMPLEX_WS_URL = f"ws://localhost:{SIMPLEX_PORT}"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "simplex.json")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def load_config():
    """Carga la configuracion de Simplex desde config/simplex.json."""
    defaults = {
        "enabled": False,
        "ws_port": 5227,
        "contact_address": "",
        "notify_on_complete": True,
        "notify_on_error": True,
        "notify_on_file": True,
        "remote_commands": True,
        "send_screenshot_on_complete": False
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                defaults.update(cfg)
        except:
            pass
    return defaults


class SimplexBridge:
    """
    Puente WebSocket a la CLI de Simplex Chat.
    Soporta enviar mensajes, recibir comandos remotos y adjuntar archivos.
    """

    def __init__(self, on_command_callback: Optional[Callable[[str], Any]] = None):
        self.config = load_config()
        self.on_command = on_command_callback  # fn(command_text: str)  str
        self.ws: Optional[Any] = None
        self.connected: bool = False
        self.send_queue: queue.Queue = queue.Queue()
        self._corr_id: int = 1
        self._lock: threading.Lock = threading.Lock()
        self._listener_thread: Optional[threading.Thread] = None
        self._addr_event: threading.Event = threading.Event()
        self._last_addr: Optional[str] = None
        self._last_contact_name: Optional[str] = (
            self.config.get("last_contact_name") or None
        )
        self._connecting: bool = False
        self.linked: bool = False
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._last_connect_time: float = 0.0
        self._auto_reconnect: bool = True
        self._reconnect_timer: Optional[threading.Timer] = None
        self._closing: bool = False
        self.last_error: str = ""
        self._welcomed_contacts: set = set()

    # -------- CONEXION --------

    def connect(self):
        """Conecta al CLI de Simplex via WebSocket y espera el handshake."""
        if self.connected:
            return True, "Conexion ya activa"
        if self._connecting:
            return False, "Conexion en progreso"

        self._connecting = True
        self._closing = False
        self._auto_reconnect = True
        self.last_error = ""

        if not WS_AVAILABLE:
            self._connecting = False
            self.last_error = "websocket-client no instalado. Ejecuta: pip install websocket-client"
            return False, self.last_error
        if not self.config.get("enabled"):
            self._connecting = False
            self.last_error = "Simplex Bridge desactivado en config/simplex.json"
            return False, self.last_error

        try:
            url = f"ws://127.0.0.1:{self.config.get('ws_port', SIMPLEX_PORT)}"
            print(f"[SIMPLEX] Conectando WebSocket a {url}...")
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            thread = threading.Thread(target=self._run_ws_forever, daemon=True)
            self._listener_thread = thread
            thread.start()

            # Wait for the handshake. The daemon may still be starting.
            for _ in range(450):
                if self.connected:
                    self._connecting = False
                    print("[SIMPLEX] WebSocket conectado.")
                    return True, "Conectado a Simplex CLI"
                if self.ws is None and not self._connecting:
                    break
                time.sleep(0.1)

            self._connecting = False
            if not self.last_error:
                self.last_error = (
                    "El CLI de Simplex no respondio. Comprueba que esta instalado "
                    "y que el puerto esta libre."
                )
            return False, self.last_error
        except Exception as e:
            self._connecting = False
            self.last_error = f"Error conectando a Simplex: {e}"
            print(f"[SIMPLEX] {self.last_error}")
            return False, self.last_error

    def _run_ws_forever(self):
        """Run the WebSocket loop and schedule a single reconnect on close."""
        ws = self.ws
        try:
            if ws:
                ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            print(f"[SIMPLEX] Error en el loop WebSocket: {e}")
            self.last_error = str(e)
        finally:
            self._on_close(None, None, None)
            print("[SIMPLEX] Conexion cerrada.")
            if self._auto_reconnect and not self._closing:
                self._schedule_reconnect()

    def _schedule_reconnect(self):
        if self._reconnect_timer is not None:
            return
        self._reconnect_timer = threading.Timer(5.0, self._reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _reconnect(self):
        self._reconnect_timer = None
        if self._closing or self.connected or self._connecting:
            return
        self.connect()

    def save_config(self):
        """Persiste la configuracion actual a disco."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[SIMPLEX] Error guardando config: {e}")

    def disconnect(self):
        """Cierra la conexion y desactiva la reconexion automatica."""
        self._auto_reconnect = False
        self._closing = True
        if self._reconnect_timer is not None:
            try:
                self._reconnect_timer.cancel()
            except Exception:
                pass
            self._reconnect_timer = None
        ws = self.ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        self.connected = False
        self.linked = False
        self._connecting = False
        self.ws = None

    def is_connected(self):
        return self.connected

    def is_linked(self):
        """Retorna True si hay al menos un contacto vinculado."""
        return self.connected and self.linked

    # -------- ENVIAR MENSAJES --------

    def send_notification(self, text: str, category: str = "info"):
        """Envia una notificacion al telefono del usuario."""
        if not self.connected:
            return False
        # Strip debug metadata, keeping emojis and clean text
        clean = _clean_simplex_text(str(text))
        return self._send_text(clean)

    def send_pulse(self, text: str = ""):
        """Progress pulses are intentionally suppressed.

        A remote task sends exactly one clean ``Thinking...`` message before
        it starts. Intermediate status labels (Spanish or English) would only
        add noise to the Simplex conversation, so progress pulses are ignored.
        """
        return False

    def send_file(self, filepath: str, caption: str = ""):
        """Envia un archivo al telefono del usuario."""
        if not self.connected or not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            filename = os.path.basename(filepath)
            corr = self._next_corr()
            payload = {
                "corrId": corr,
                "cmd": f"APIFileSend {filename} {data}"
            }
            ws = self.ws
            if ws:
                ws.send(json.dumps(payload) + "\n")
            if caption:
                self._send_text(f"[F] {caption}: {filename}")
            return True
        except Exception as e:
            return False

    def send_screenshot(self):
        """Toma screenshot y lo envia al telefono, luego lo elimina."""
        try:
            import pyautogui  # type: ignore
            import tempfile
            img = pyautogui.screenshot()
            fd, tmp = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(tmp)
            success = self.send_file(tmp, "[PIC] Captura de pantalla de Orunex")
            # Clear trace immediately
            if os.path.exists(tmp):
                try: os.remove(tmp)
                except: pass
            return success
        except Exception as e:
            print(f"DEBUG: Error in send_screenshot: {e}")
            return False

    # -------- RECIBIR COMANDOS REMOTOS --------

    def _parse_remote_command(self, text: str):
        """Analiza y ejecuta comandos enviados desde el telefono."""
        text = text.strip()

        if text == "!estado":
            return self._get_system_status()

        elif text.startswith("!archivo:"):
            filename = text[9:].strip()  # type: ignore
            base_dir = os.path.join(PROJECT_ROOT, "orunex_outputs")
            # Buscar el archivo en orunex_outputs/documentos
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if filename.lower() in f.lower():
                        self.send_file(os.path.join(root, f), "Archivo solicitado")
                        return f"[OUT] Enviando archivo: {f}"
            return f"[X] Archivo '{filename}' no encontrado en orunex_outputs."

        elif text == "!captura":
            self.send_screenshot()
            return "[PIC] Captura de pantalla enviada."

        elif text == "!stop":
            # Signal to main app to stop  handled externally by on_command callback
            if self.on_command:
                cast(Callable[[str], Any], self.on_command)("SIMPLEX_KILL_SWITCH")
            return "[STOP] Kill switch activado. Deteniendo tareas activas."

        elif text.startswith("!heartbeat"):
            if "on" in text:
                if self.on_command: 
                    cast(Callable[[str], Any], self.on_command)("SIMPLEX_HEARTBEAT_ON")
                return "[HB] Heartbeat activado."
            else:
                if self.on_command: 
                    cast(Callable[[str], Any], self.on_command)("SIMPLEX_HEARTBEAT_OFF")
                return "[HB] Heartbeat desactivado."

        elif text == "!ayuda":
            return (
                "[i] Comandos disponibles:\n"
                "!estado  Estado del sistema\n"
                "!archivo: [nombre]  Enviar archivo\n"
                "!captura  Captura de pantalla\n"
                "!heartbeat on/off  Control del daemon\n"
                "!stop  Kill switch de emergencia\n"
                "(Cualquier otro mensaje sera procesado por el Agente Orunex de IA)"
            )

        else:
            # Cualquier mensaje natural se asume como tarea para Orunex.
            # Send the single visible processing label synchronously so it
            # always arrives before the final answer. Returning None prevents
            # _on_message from sending a second, duplicate notification.
            if self.on_command:
                self.send_notification("Thinking...")
                threading.Thread(target=self._async_task, args=(str(text),), daemon=True).start()
                return None
            return "[WARN] Motor local no conectado."

    def _async_task(self, task: str):
        """Ejecuta una tarea remota y notifica el resultado."""
        assert self.on_command is not None
        result = cast(Callable[[str], Any], self.on_command)(f"SIMPLEX_TASK:{task}")
        if result:
            clean_result = _clean_simplex_text(str(result))
            self.send_notification(clean_result, "success") # type: ignore

    def _get_system_status(self) -> str:
        """Retorna el estado del sistema."""
        try:
            import psutil  # type: ignore
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"[IDE] Estado de Orunex\n"
                f"CPU: {cpu}%\n"
                f"RAM: {ram.percent}% ({ram.used // 1024**2}MB / {ram.total // 1024**2}MB)\n"
                f"Disco: {disk.percent}% usado\n"
                f"Hora: {datetime.now().strftime('%H:%M:%S')}"
            )
        except:
            import platform
            return f"[IDE] Orunex activo  {platform.system()}  {datetime.now().strftime('%H:%M:%S')}"

    def _send_text(self, text: str) -> bool:
        """Envia un mensaje de texto via WebSocket."""
        if not self.ws or not self.connected:
            self.last_error = "El bridge no esta conectado."
            return False
        try:
            corr = self._next_corr()

            # CLI v7 syntax: @contact <message>
            target_contact = (
                getattr(self, "_last_contact_name", None)
                or self.config.get("last_contact_name")
            )

            if not target_contact:
                print("[SIMPLEX] No hay contacto activo para enviar el mensaje.")
                self.last_error = "No hay un contacto vinculado."
                return False

            payload = {
                "corrId": str(corr),
                "cmd": f"@{target_contact} {text}",
            }
            ws = self.ws
            if ws:
                ws.send(json.dumps(payload) + "\n")
            return True
        except:
            return False

    def _request_address(self, command: str, timeout: float):
        """Send an address command and wait for a link event."""
        self._addr_event.clear()
        self._last_addr = None
        self._send({"cmd": command})
        if self._addr_event.wait(timeout):
            return self._last_addr
        return None

    def get_invite_link_ws(self, timeout: int = 30):
        """Return the pairing link, creating the user address when needed."""
        if not self.connected:
            self.last_error = "El bridge no esta conectado."
            return None
        try:
            # A fresh profile has no address yet: /sa fails with
            # userContactLinkNotFound. Create one with /address, then read it.
            link = self._request_address("/sa", min(12, timeout))
            if link:
                return link

            link = self._request_address("/address", min(15, timeout))
            if link:
                return link

            link = self._request_address("/sa", min(15, timeout))
            if link:
                return link

            self.last_error = (
                "No se pudo crear el link de emparejamiento. Comprueba que el CLI "
                "de Simplex esta actualizado."
            )
            return None
        except Exception as e:
            self.last_error = f"Error al obtener el link de invitacion: {e}"
            print(f"[SIMPLEX] {self.last_error}")
            return None

    def ensure_invite_link(self, timeout: int = 45):
        """Public helper used by the pairing screen."""
        return self.get_invite_link_ws(timeout=timeout)

    def _next_corr(self) -> int:
        with self._lock:
            self._corr_id += 1
            return self._corr_id

    def _send(self, payload: dict) -> bool:
        """Envia un payload JSON generico al WebSocket."""
        if not self.ws or not self.connected:
            return False
        try:
            if "corrId" not in payload:
                payload["corrId"] = str(self._next_corr())
            self.ws.send(json.dumps(payload) + "\n") # type: ignore
            return True
        except Exception as e:
            print(f"DEBUG: Error sending payload: {e}")
            return False

    # -------- CALLBACKS WEBSOCKET --------

    def _on_open(self, ws):
        print("[SIMPLEX] Handshake WebSocket completado.")
        self.connected = True
        self._connecting = False
        self.last_error = ""
        self._last_connect_time = time.time()
        self._last_contact_name = (
            self.config.get("last_contact_name") or self._last_contact_name
        )

        try:
            # Bot mode should accept contact requests automatically. The correct
            # CLI command is /auto_accept on (not /set auto-accept-*).
            self._send({"cmd": "/auto_accept on"})
            self._auto_link_persistence()
            self._start_heartbeat()
        except Exception as e:
            print(f"[SIMPLEX] Error en inicializacion WS: {e}")

    def _auto_link_persistence(self):
        """Recupera el vinculo previo si existe en config, sin emitir avisos."""
        last_id = self.config.get("last_contact_id")
        last_name = self.config.get("last_contact_name")
        if last_id and last_name:
            self.linked = True
            self._last_contact_name = str(last_name)
            print(f"[SIMPLEX] Vinculo persistente recuperado: {last_name} ({last_id})")

    def _start_heartbeat(self):
        """Heartbeat: pide la direccion periodicamente para mantener el socket vivo."""
        if self._heartbeat_timer:
            try:
                self._heartbeat_timer.cancel()
            except Exception:
                pass

        if self.connected:
            self._send({"cmd": "/sa"})
            self._heartbeat_timer = threading.Timer(60.0, self._start_heartbeat)
            if self._heartbeat_timer:
                self._heartbeat_timer.daemon = True
                self._heartbeat_timer.start()

    def _on_error(self, ws, error):
        print(f"[SIMPLEX] Error WebSocket: {error}")
        self.last_error = str(error)
        self.connected = False

    def _on_close(self, ws, code, msg):
        was_active = self.connected or self.linked
        self.connected = False
        self.linked = False
        self._connecting = False
        self.ws = None
        if self._heartbeat_timer:
            try:
                self._heartbeat_timer.cancel()
            except Exception:
                pass
            self._heartbeat_timer = None
        if was_active and self.on_command:
            try:
                self.on_command("SIMPLEX_DISCONNECTED_EVENT")
            except Exception:
                pass

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            resp = data.get("resp", {})
            if not isinstance(resp, dict):
                return
            event = resp.get("type", "")

            # --- Address / pairing link extraction ---
            def find_link(obj):
                if isinstance(obj, str):
                    if ("contact#/" in obj or "/a#" in obj) and (
                        "simplex" in obj or "smp" in obj
                    ):
                        return obj
                elif isinstance(obj, dict):
                    for value in obj.values():
                        result = find_link(value)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_link(item)
                        if result:
                            return result
                return None

            addr = find_link(data)
            if not addr and event in (
                "userContactLinkCreated",
                "userContactLink",
                "userContactLinkUpdated",
            ):
                match = re.search(
                    r'(?:simplex:|https://)[^\s"\'\}]+(?:contact#/|/a#)[^\s"\'\}]+',
                    message,
                )
                if match:
                    addr = match.group(0)

            if addr:
                self._last_addr = addr
                self._addr_event.set()
                print(f"[SIMPLEX] Link de direccion actualizado ({addr[:34]}…).")

            # --- Contact requests: accept with the display name (CLI v7) ---
            if event in ("receivedContactRequest", "contactRequest"):
                def find_obj(obj, key):
                    if isinstance(obj, dict):
                        if key in obj:
                            return obj[key]
                        for value in obj.values():
                            result = find_obj(value, key)
                            if result is not None:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_obj(item, key)
                            if result is not None:
                                return result
                    return None

                req = find_obj(data, "contactRequest")
                if not req:
                    req = find_obj(data, "contact")
                if isinstance(req, dict):
                    display_name = (
                        req.get("localDisplayName")
                        or req.get("name")
                        or req.get("displayName")
                    )
                    if display_name:
                        safe_name = (
                            f'"{display_name}"' if " " in str(display_name) else display_name
                        )
                        print(f"[SIMPLEX] Aceptando solicitud de {display_name}.")
                        self._send({"cmd": f"/accept {safe_name}"})
                    else:
                        print("[SIMPLEX] Solicitud de contacto sin nombre visible.")

            # --- Successful pairing ---
            if event in ("contactAdded", "contactConnected"):
                self.linked = True
                resp_obj = resp.get("contact", {})
                if not resp_obj:
                    resp_obj = (
                        resp.get("connectionEntity", {}).get("contact", {})
                    )
                if isinstance(resp_obj, dict):
                    contact_name = resp_obj.get("localDisplayName")
                    if contact_name:
                        self._last_contact_name = str(contact_name)
                        self.config["last_contact_name"] = str(contact_name)
                        if resp_obj.get("contactId") is not None:
                            self.config["last_contact_id"] = str(
                                resp_obj["contactId"]
                            )
                        self.save_config()

                        if contact_name not in self._welcomed_contacts:
                            self._welcomed_contacts.add(contact_name)
                            welcome_msg = (
                                "[EXE] [ORUNEX ULTIMATE AGENT SOTA]\n\n"
                                "Sistemas sincronizados. Nucleo operativo en linea.\n"
                                "Ya puedes manejar tus automatizaciones remotas con latencia minima.\n"
                                "Escribe '!ayuda' para ver el protocolo de comandos."
                            )
                            threading.Timer(
                                1.5,
                                self.send_notification,
                                args=(welcome_msg, "success"),
                            ).start()

                if self.on_command:
                    cast(Callable[[str], Any], self.on_command)(
                        "SIMPLEX_CONNECTED_EVENT"
                    )
                print("[SIMPLEX] Dispositivo sincronizado.")

            if event == "contactDeleted":
                print("[SIMPLEX] Contacto eliminado. Limpiando persistencia...")
                self.linked = False
                self.config["last_contact_id"] = ""
                self.config["last_contact_name"] = ""
                self._last_contact_name = None
                self.save_config()
                if self.on_command:
                    cast(Callable[[str], Any], self.on_command)(
                        "SIMPLEX_DISCONNECTED_EVENT"
                    )

            if event == "subscriptionEnd":
                self.linked = False
                print("[SIMPLEX] Desvinculado (subscriptionEnd).")

            if event == "newChatItems":
                # Ignore replayed messages immediately after connecting.
                if time.time() - self._last_connect_time < 10.0:
                    return

                items = resp.get("chatItems", [])
                if not isinstance(items, list):
                    return
                for item in items:
                    chat_item = item.get("chatItem", {})
                    chat_info = chat_item.get("chatInfo", {})
                    contact = chat_info.get("contact", {})
                    contact_name = contact.get("localDisplayName")
                    if contact_name:
                        self._last_contact_name = contact_name

                    content = chat_item.get("content", {})
                    if content.get("type") == "sndMsgContent":
                        continue  # Ignore own sent messages
                    text = content.get("msgContent", {}).get("text", "")
                    if text and self.config.get("remote_commands", True):
                        reply = self._parse_remote_command(str(text))
                        if reply:
                            self.send_notification(str(reply))
        except Exception as e:
            print(f"[SIMPLEX] Error procesando mensaje: {e}")


# Singleton instance
_bridge = SimplexBridge()


def get_bridge() -> SimplexBridge:
    return _bridge


def is_connected() -> bool:
    """Public helper: returns True if the Simplex bridge is currently connected."""
    return _bridge.connected


def get_last_error() -> str:
    """Last human-readable bridge error, if any."""
    return _bridge.last_error


def check_and_download_cli():
    import urllib.request
    import shutil
    bin_dir = os.path.join(PROJECT_ROOT, "simplex_bin")
    os.makedirs(bin_dir, exist_ok=True)
    exe_path = os.path.join(bin_dir, "simplex-chat.exe")

    # Check if executable exists and is valid (must be > 20MB and start with MZ header)
    if os.path.exists(exe_path):
        try:
            if os.path.getsize(exe_path) < 20 * 1024 * 1024:
                os.remove(exe_path)
            else:
                with open(exe_path, "rb") as f:
                    header = f.read(2)
                    if header != b"MZ":  # Valid Windows PE executable header
                        f.close()
                        os.remove(exe_path)
        except Exception:
            pass

    if not os.path.exists(exe_path):
        # Current 64-bit Windows CLI asset.
        url = "https://github.com/simplex-chat/simplex-chat/releases/download/v7.0.3/simplex-chat-windows-x86-64"
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(exe_path, "wb") as out_file:
                    shutil.copyfileobj(response, out_file)
        except Exception as e:
            return False, f"Error descargando CLI: {e}"

    # Final validation check
    if not os.path.exists(exe_path) or os.path.getsize(exe_path) < 20 * 1024 * 1024:
        return False, "Simplex CLI no disponible o invalido."

    return True, exe_path


def start_daemon():
    """Start the local Simplex CLI with the WebSocket API port, if needed."""
    global _bridge
    try:
        ok, exe_path = check_and_download_cli()
        if not ok:
            _bridge.last_error = str(exe_path)
            return False

        import subprocess
        import socket

        port = int(load_config().get("ws_port", SIMPLEX_PORT))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_check:
            s_check.settimeout(1.0)
            if s_check.connect_ex(("127.0.0.1", port)) == 0:
                return True  # Daemon already running

        subprocess.run(
            "taskkill /f /im simplex-chat.exe /t",
            shell=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(1)

        db_dir = os.path.join(PROJECT_ROOT, "simplex_data", "orunex_profile")
        os.makedirs(db_dir, exist_ok=True)

        log_path = os.path.join(PROJECT_ROOT, "simplex_debug.log")
        flags = 0x08000000  # CREATE_NO_WINDOW

        cmd_str = (
            f'"{exe_path}" -y -d "{db_dir}" '
            f"--create-bot-display-name Orunex -p {port} > \"{log_path}\" 2>&1"
        )

        process = subprocess.Popen(
            cmd_str,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            shell=True,
        )

        # A cold start can take several seconds while the CLI opens its database.
        for _ in range(20):
            time.sleep(1.0)
            if process.poll() is not None:
                _bridge.last_error = (
                    "El CLI de Simplex se cerro durante el arranque. "
                    f"Revisa {log_path}."
                )
                return False
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True

        _bridge.last_error = "El CLI de Simplex no abrio el puerto WebSocket a tiempo."
    except Exception as e:
        print(f"[SIMPLEX] Daemon error: {e}")
        _bridge.last_error = f"No se pudo iniciar el CLI de Simplex: {e}"
    return False



def generate_qr_image(link: str) -> Optional[str]:
    """Generate a QR code image from the pairing link and return its path."""
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(version=None, box_size=10, border=4)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.convert("RGB") if hasattr(img, "convert") else img

        temp_dir = os.path.join(PROJECT_ROOT, "simplex_bin")
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, "simplex_invite_qr.png")
        img.save(path)
        return path
    except Exception as e:
        print(f"[SIMPLEX] Error generating QR: {e}")
        return None

def notify(text: str, category: str = "info") -> bool:
    """Shortcut para enviar notificacion desde cualquier modulo de Orunex."""
    return _bridge.send_notification(text, category)


def init_bridge(on_command_callback=None, force_enable: bool = False) -> tuple:
    """Inicializa y conecta el bridge en background.

    If a bridge is already connected or connecting, it is reused instead of
    replacing the singleton (which would drop the active WebSocket).
    """
    global _bridge

    if force_enable:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        cfg = load_config()
        cfg["enabled"] = True
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    if _bridge.connected or _bridge._connecting:
        if on_command_callback is not None:
            _bridge.on_command = on_command_callback
        return True, "Simplex Bridge ya esta en ejecucion."

    _bridge = SimplexBridge(on_command_callback)

    def _background_init():
        try:
            if not start_daemon():
                return
            _bridge.connect()
        except Exception as e:
            _bridge.last_error = f"Error iniciando el bridge: {e}"

    threading.Thread(target=_background_init, daemon=True).start()
    return True, "Simplex iniciando en background..."

