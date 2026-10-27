"""Client for the local Orunex VS Code bridge.

The bridge is a tiny VS Code extension (``vscode_extension/``) that listens on
localhost.  It lets Orunex open/edit files, run commands in the integrated
terminal, execute tests and read diagnostics without fragile keyboard
automation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

HOST = "127.0.0.1"
BASE_PORT = 8765
PORT_ATTEMPTS = 12
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".orunex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "vscode_bridge.json")
EXTENSION_DIR = os.path.join(os.path.dirname(__file__), "vscode_extension")
DEFAULT_WORKSPACE = os.path.join(
    os.path.expanduser("~"), "Documents", "Orunex_Workspace"
)


def _hidden_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _candidate_ports() -> list[int]:
    config = load_config()
    ports = []
    try:
        port = int(config.get("port"))
        if port > 0:
            ports.append(port)
    except Exception:
        pass
    for port in range(BASE_PORT, BASE_PORT + PORT_ATTEMPTS):
        if port not in ports:
            ports.append(port)
    return ports


def _http_json(
    method: str,
    path: str,
    payload: Optional[dict] = None,
    timeout: float = 8.0,
    port: Optional[int] = None,
    token: Optional[str] = None,
) -> dict:
    config = load_config()
    port = int(port or config.get("port") or BASE_PORT)
    token = token if token is not None else str(config.get("token") or "")
    url = f"http://{HOST}:{port}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["X-Orunex-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"error": body or str(exc)}
        parsed.setdefault("ok", False)
        parsed["status"] = exc.code
        return parsed
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def health(timeout: float = 0.8) -> dict:
    for port in _candidate_ports():
        result = _http_json("GET", "/health", timeout=timeout, port=port, token="")
        if result.get("ok") and result.get("extension") == "orunex.orunex-bridge":
            result["port"] = port
            return result
    return {"ok": False, "error": "Orunex Bridge is not running"}


def is_alive() -> bool:
    return bool(health().get("ok"))


def _code_command() -> list[str]:
    candidates = [
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "Microsoft VS Code",
            "Code.exe",
        ),
        shutil.which("code"),
        shutil.which("code.cmd"),
        shutil.which("code-insiders"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            if candidate.lower().endswith((".cmd", ".bat")):
                return [candidate]
            return [candidate]
    return []


def launch_vscode(workspace: Optional[str] = None) -> dict:
    """Open a new VS Code window with the bridge extension loaded."""
    workspace = os.path.abspath(workspace or DEFAULT_WORKSPACE)
    os.makedirs(workspace, exist_ok=True)
    extension_dir = os.path.abspath(EXTENSION_DIR)
    if not os.path.isdir(extension_dir):
        return {"ok": False, "error": f"Bridge extension folder not found: {extension_dir}"}
    command = _code_command()
    if not command:
        return {"ok": False, "error": "VS Code CLI/Code.exe was not found"}
    args = [
        *command,
        "--new-window",
        f"--extensionDevelopmentPath={extension_dir}",
        workspace,
    ]
    try:
        subprocess.Popen(
            args,
            cwd=workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_hidden_kwargs(),
        )
    except Exception as exc:
        return {"ok": False, "error": f"Could not launch VS Code: {exc}"}
    deadline = time.time() + 28.0
    while time.time() < deadline:
        time.sleep(0.8)
        result = health(timeout=0.7)
        if result.get("ok"):
            result["launched"] = True
            result["workspace"] = workspace
            return result
    return {
        "ok": False,
        "launched": True,
        "workspace": workspace,
        "error": "VS Code opened, but the Orunex Bridge did not answer. "
                 "Check that the extension window finished loading.",
    }


def ensure_bridge(workspace: Optional[str] = None, launch: bool = True) -> dict:
    """Return a healthy bridge, launching VS Code if needed."""
    current = health()
    if current.get("ok"):
        config = load_config()
        current["workspace"] = (
            (current.get("workspaceFolders") or [None])[0]
            or config.get("workspaceFolders", [None])[0]
            or workspace
            or DEFAULT_WORKSPACE
        )
        current["launched"] = False
        return current
    if not launch:
        return {"ok": False, "error": "Orunex Bridge is not running"}
    return launch_vscode(workspace)


def _call(path: str, payload: Optional[dict] = None, method: str = "POST", timeout: float = 10.0) -> dict:
    if not health().get("ok"):
        return {"ok": False, "error": "Orunex Bridge is not running"}
    result = _http_json(method, path, payload=payload, timeout=timeout)
    if result.get("status") == 401:
        # The extension may have restarted and regenerated its token.
        time.sleep(0.2)
        result = _http_json(method, path, payload=payload, timeout=timeout)
    return result


def open_file(path: str, line: int = 1) -> dict:
    return _call("/open", {"path": path, "line": line})


def write_file(path: str, content: str, open_after: bool = True) -> dict:
    return _call("/create", {"path": path, "content": content, "open": open_after})


def edit_file(path: str, content: str, open_after: bool = True) -> dict:
    return _call("/edit", {"path": path, "content": content, "open": open_after})


def replace_text(path: str, old_text: str, new_text: str) -> dict:
    return _call("/edit", {"path": path, "mode": "replace", "oldText": old_text, "newText": new_text})


def run_terminal(command: str, cwd: Optional[str] = None, name: str = "Orunex", show: bool = True) -> dict:
    return _call("/terminal", {"command": command, "cwd": cwd, "name": name, "show": show})


def run_command(command: str, cwd: Optional[str] = None, timeout: float = 120.0) -> dict:
    return _call(
        "/exec",
        {"command": command, "cwd": cwd, "timeout": int(timeout * 1000)},
        timeout=timeout + 5.0,
    )


def run_tests(cwd: Optional[str] = None, command: Optional[str] = None) -> dict:
    """Run tests in the workspace and mirror the command in the terminal."""
    if not command:
        command = "python -m pytest -q"
    terminal = run_terminal(command, cwd=cwd, name="Orunex Tests")
    result = run_command(command, cwd=cwd, timeout=180.0)
    if not result.get("ok") and "No module named pytest" in (
        str(result.get("stderr", "")) + str(result.get("stdout", ""))
    ):
        command = 'python -m unittest discover -s . -p "test_*.py"'
        terminal = run_terminal(command, cwd=cwd, name="Orunex Tests")
        result = run_command(command, cwd=cwd, timeout=180.0)
    result["terminal"] = terminal
    result["testCommand"] = command
    return result


def diagnostics(path: Optional[str] = None) -> dict:
    query = f"?path={urllib.parse.quote(path)}" if path else ""
    return _call("/diagnostics" + query, method="GET")


def run_vscode_command(command: str, args: Optional[list] = None) -> dict:
    return _call("/command", {"command": command, "args": args or []})


def save_all() -> dict:
    return _call("/save", {})


def workspace_info() -> dict:
    return _call("/workspace", method="GET")


def status() -> dict:
    info = health()
    if not info.get("ok"):
        return {
            "ok": False,
            "state": "offline",
            "message": "VS Code bridge is offline",
        }
    info["state"] = "connected"
    info["message"] = (
        "VS Code bridge connected"
        + (f" · {os.path.basename((info.get('workspaceFolders') or [''])[0])}" if info.get("workspaceFolders") else "")
    )
    return info
