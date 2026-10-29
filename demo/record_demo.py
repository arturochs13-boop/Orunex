"""Record the Orunex Desktop / Muse paper-trading demo.

The recorder drives the real UI only: it launches Orunex with the controlled
historical chart and an isolated demo paper account, records the desktop with
ffmpeg, and verifies each answer through the UI's own chat store.  It never
fakes a Muse decision; the final order is whatever the backend returns.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pygetwindow as gw
import win32gui
import win32process

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scratch"))

from ui_helpers import (  # noqa: E402
    activate_orunex,
    click_new_chat,
    foreground_title,
    minimize_exe_windows,
    shot,
    type_and_send,
)

CHATS = ROOT / "src" / "config" / "chats.json"
CHATS_BACKUP = ROOT / "demo" / "chats_rehearsal_backup.json"
DEMO_STATE = ROOT / "demo" / "paper_demo.json"
OUTPUT = ROOT / "demo" / "orunex_demo.mp4"
CHART_VIEWER = ROOT / "demo" / "chart_viewer.py"
APP = ROOT / "src" / "main.py"
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable)

REASONING_PROMPT = (
    "En 4 frases, explica por qué una estrategia rentable en backtest puede "
    "fallar en vivo y qué validarías antes de arriesgar capital. No inventes "
    "datos."
)
SCREEN_PROMPT = (
    "¿Qué ves en mi pantalla ahora mismo? Describe la ventana principal y el "
    "texto visible."
)
TRADE_PROMPT = (
    "Analiza el gráfico y, si hay una oportunidad, ejecuta la orden paper "
    "con SL y TP."
)
RESULT_MARKERS = (
    "Muse confirmó",
    "no abrió orden paper",
    "Muse analizó",
    "Muse ejecutó",
    "terminó sin un resultado",
)


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def load_chats():
    try:
        data = json.loads(CHATS.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data.get("chats", []) if isinstance(data, dict) else []


def find_chat(prompt_fragment: str, not_before: str = ""):
    matches = [
        chat
        for chat in load_chats()
        if any(
            message.get("role") == "user"
            and prompt_fragment in str(message.get("text") or "")
            for message in chat.get("messages", [])
        )
    ]
    if not_before:
        # Previous rehearsals contain the same prompts.  Only accept a chat
        # created for this run, or the recorder would read an old answer and
        # skip the real request.
        matches = [
            chat
            for chat in matches
            if str(chat.get("created_at") or "") >= not_before
        ]
    return matches[-1] if matches else None


def wait_for_new_chat(not_before: str, timeout: float = 12.0):
    started = time.time()
    while time.time() - started < timeout:
        for chat in load_chats():
            if str(chat.get("created_at") or "") >= not_before:
                return chat
        time.sleep(0.5)
    return None


def wait_for_assistant(
    prompt_fragment: str,
    predicate,
    timeout: float,
    label: str,
    not_before: str = "",
    fail_predicate=None,
) -> str:
    started = time.time()
    last_text = ""
    while time.time() - started < timeout:
        chat = find_chat(prompt_fragment, not_before)
        if chat:
            assistants = [
                message
                for message in chat.get("messages", [])
                if message.get("role") == "assistant"
            ]
            if assistants:
                text = str(assistants[-1].get("text") or "")
                if text != last_text:
                    log(f"{label}: assistant message ({len(text)} chars)")
                    last_text = text
                if predicate(text):
                    return text
                if fail_predicate and fail_predicate(text):
                    log(f"{label}: non-delegated answer detected")
                    return text
        time.sleep(1)
    return ""


def find_orunex_pids() -> list[int]:
    found: list[int] = []

    def _callback(hwnd, _extra):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Orunex" in title and "Desktop Agent" in title:
                    _thread, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid and pid not in found:
                        found.append(pid)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_callback, None)
    return found


def stop_orunex() -> None:
    for pid in find_orunex_pids():
        log(f"stopping existing Orunex pid={pid}")
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    deadline = time.time() + 8
    while time.time() < deadline:
        if not find_orunex_pids():
            break
        time.sleep(0.5)
    time.sleep(1)


def stop_tradingview() -> None:
    subprocess.run(
        ["taskkill", "/IM", "TradingView.exe", "/F"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    time.sleep(1)


def launch_orunex() -> subprocess.Popen:
    env = os.environ.copy()
    env["ORUNEX_DEMO_CHART"] = "demo/charts/btcusdt_1h_pullback.png"
    env["PAPER_STATE_PATH"] = "demo/paper_demo.json"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [str(PYTHONW), str(APP)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        if any(
            "Desktop Agent" in (window.title or "")
            for window in gw.getWindowsWithTitle("Orunex")
        ):
            time.sleep(1.5)
            if activate_orunex():
                return proc
        time.sleep(0.5)
    raise RuntimeError("Orunex window did not appear")


def wait_for_tradingview(timeout: float = 25.0) -> list[str]:
    started = time.time()
    first_seen = None
    last_titles: list[str] = []
    while time.time() - started < timeout:
        titles = [
            window.title
            for window in gw.getAllWindows()
            if window.title
            and ("TradingView" in window.title or "BTCUSD" in window.title)
        ]
        if titles:
            last_titles = titles
            if first_seen is None:
                first_seen = time.time()
            # Give the desktop app time to finish its white loading screen
            # and restore the chart; the old 2 s wait captured only a spinner.
            if any("BTCUSD" in title or "Chart" in title for title in titles):
                time.sleep(3)
                return titles
            if time.time() - first_seen >= 8:
                time.sleep(2)
                return titles
        time.sleep(0.5)
    log("TradingView window not detected")
    return last_titles


def launch_tradingview_fallback() -> bool:
    """Recorder safety net: launch the installed MSIX app directly."""
    local = os.environ.get("LOCALAPPDATA", "")
    packages = Path(local) / "Packages" if local else None
    if not packages or not packages.is_dir():
        return False
    for entry in sorted(packages.iterdir()):
        if entry.name.startswith("TradingView.Desktop_"):
            app_id = f"{entry.name}!TradingView.Desktop"
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log(f"launched TradingView fallback: {app_id}")
            return True
    return False


def start_recording():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not on PATH")
    if OUTPUT.exists():
        OUTPUT.unlink()
    log_path = ROOT / "demo" / "ffmpeg.log"
    handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            "30",
            "-draw_mouse",
            "0",
            "-i",
            "desktop",
            "-t",
            "420",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ],
        stdin=subprocess.PIPE,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    time.sleep(1)
    if proc.poll() is not None:
        handle.close()
        raise RuntimeError("ffmpeg exited early; see demo/ffmpeg.log")
    log("screen recording started")
    return proc, handle


def stop_recording(proc, handle) -> None:
    try:
        if proc is not None and proc.poll() is None:
            proc.stdin.write(b"q")
            proc.stdin.flush()
            proc.wait(timeout=20)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        if handle is not None:
            handle.close()
    except Exception:
        pass
    if OUTPUT.exists():
        log(f"video: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
    else:
        log("video missing")


def reset_chat_store_for_demo() -> None:
    """Keep the real rehearsal history safe but start the video with a clean UI."""
    try:
        if CHATS.exists():
            if not CHATS_BACKUP.exists():
                shutil.copy2(CHATS, CHATS_BACKUP)
            CHATS.write_text('{"chats": []}\n', encoding="utf-8")
            log(f"chat store cleared for the demo; backup: {CHATS_BACKUP}")
    except Exception as exc:
        log(f"could not clear chat store: {exc}")


def run_sequence(record: bool) -> str:
    stop_orunex()
    stop_tradingview()
    if DEMO_STATE.exists():
        DEMO_STATE.unlink()
    reset_chat_store_for_demo()
    app_proc = launch_orunex()
    time.sleep(2)
    log(f"Orunex started pid={app_proc.pid}; foreground={foreground_title()!r}")

    ffmpeg_proc = None
    ffmpeg_log = None
    if record:
        ffmpeg_proc, ffmpeg_log = start_recording()

    result = ""
    try:
        # 1) Muse reasoning quality
        activate_orunex()
        segment_started = datetime.now().isoformat(timespec="seconds")
        click_new_chat()
        wait_for_new_chat(segment_started)
        activate_orunex()
        type_and_send(REASONING_PROMPT)
        log("sent reasoning prompt")
        answer = wait_for_assistant(
            "En 4 frases",
            lambda text: len(text) > 120,
            180,
            "reasoning",
            not_before=segment_started,
        )
        log("reasoning answer: " + answer[:220].replace("\n", " "))
        time.sleep(2)
        shot("record_01_reasoning.png")

        # 2) Live screen vision (Spark)
        activate_orunex()
        segment_started = datetime.now().isoformat(timespec="seconds")
        click_new_chat()
        wait_for_new_chat(segment_started)
        activate_orunex()
        type_and_send(SCREEN_PROMPT)
        log("sent screen-vision prompt")
        vision = wait_for_assistant(
            "¿Qué ves en mi pantalla",
            lambda text: len(text) > 40,
            90,
            "vision",
            not_before=segment_started,
        )
        log("vision answer: " + vision[:220].replace("\n", " "))
        time.sleep(2)
        shot("record_02_vision.png")

        # 3) Real TradingView Desktop launch
        activate_orunex()
        segment_started = datetime.now().isoformat(timespec="seconds")
        click_new_chat()
        wait_for_new_chat(segment_started)
        activate_orunex()
        type_and_send("Abre TradingView")
        log("sent: Abre TradingView")
        command_text = wait_for_assistant(
            "Abre TradingView",
            lambda text: "Abriendo" in text,
            20,
            "tradingview-command",
            not_before=segment_started,
        )
        log("TradingView command answer: " + command_text[:160])
        titles = wait_for_tradingview(25)
        if not titles and launch_tradingview_fallback():
            titles = wait_for_tradingview(20)
        log(f"TradingView windows: {titles[:3]}")
        shot("record_03_tradingview.png")
        time.sleep(2)
        minimized = minimize_exe_windows("TradingView.exe")
        log(f"minimized TradingView windows: {minimized}")
        time.sleep(1)
        activate_orunex()
        shot("record_03_chat.png")

        # 4) Controlled historical chart viewer
        viewer = subprocess.Popen(
            [str(PYTHONW), str(CHART_VIEWER), "--seconds", "12"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        shot("record_04_chart.png")
        log("showing controlled historical chart")
        time.sleep(5)
        try:
            viewer.terminate()
            viewer.wait(timeout=5)
        except Exception:
            subprocess.run(
                ["taskkill", "/PID", str(viewer.pid), "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        time.sleep(1)
        activate_orunex()

        # 5) Muse-confirmed paper order on the controlled chart
        if DEMO_STATE.exists():
            DEMO_STATE.unlink()
        activate_orunex()
        segment_started = datetime.now().isoformat(timespec="seconds")
        click_new_chat()
        wait_for_new_chat(segment_started)
        activate_orunex()
        type_and_send(TRADE_PROMPT)
        log("sent trading prompt")
        result = wait_for_assistant(
            "Analiza el gráfico",
            lambda text: any(marker in text for marker in RESULT_MARKERS),
            240,
            "trade",
            not_before=segment_started,
            fail_predicate=lambda text: any(
                marker in text
                for marker in (
                    "No tengo un símbolo",
                    "¿qué símbolo",
                    "No puedo analizar",
                    "No tengo datos",
                )
            ),
        )
        log("trade result: " + result[:320].replace("\n", " "))
        time.sleep(5)
        shot("record_05_order.png")
        try:
            shutil.copy2(
                ROOT / "scratch" / "record_05_order.png",
                ROOT / "demo" / "order_confirmation.png",
            )
        except Exception:
            pass
        time.sleep(3)
    finally:
        if record:
            stop_recording(ffmpeg_proc, ffmpeg_log)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the Orunex Muse demo")
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="Run the full UI sequence without starting ffmpeg",
    )
    args = parser.parse_args()
    result = run_sequence(record=not args.no_record)
    print("\n=== FINAL TRADE RESULT ===")
    print(result or "NO RESULT")
    if DEMO_STATE.exists():
        print("\n=== DEMO PAPER STATE ===")
        print(DEMO_STATE.read_text(encoding="utf-8")[:4000])
    confirmed = "Muse confirmó una orden paper" in result or "Muse ejecutó una orden paper" in result
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
