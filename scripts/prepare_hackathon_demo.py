#!/usr/bin/env python3
"""Rehearse the hackathon demo end-to-end (emulator only, paper only).

Subcommands:
    python scripts/prepare_hackathon_demo.py start-emulator
    python scripts/prepare_hackathon_demo.py plant-bug     # Send -> Sned + rebuild + install
    python scripts/prepare_hackathon_demo.py seed          # FAISS: android code + strategies
    python scripts/prepare_hackathon_demo.py reset-paper   # clean $10k paper account
    python scripts/prepare_hackathon_demo.py status        # one-screen readiness check
    python scripts/prepare_hackathon_demo.py reset         # ensure the app says Send

Run `reset-paper` + `plant-bug` + `seed` before recording, then drive the fix
live from `python app.py` so the audience sees the whole autonomous repair.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INDEX_HTML = ROOT / "android" / "app" / "src" / "main" / "assets" / "index.html"
SEND = '<button class="send-button" id="sendButton" type="button">Send</button>'
SNED = '<button class="send-button" id="sendButton" type="button">Sned</button>'


def _brain():
    from core.agent_brain import AgentBrain

    return AgentBrain()


def start_emulator(avd: str) -> int:
    from bridges.adb_bridge import AndroidADBBridge

    adb = AndroidADBBridge()
    if adb.available:
        try:
            adb.ensure_device()
            print(f"Emulator already ready: {adb.serial}")
            return 0
        except Exception:
            pass
    sdk = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
    emulator = sdk / "emulator" / "emulator.exe"
    if not emulator.exists():
        print("emulator.exe not found under", sdk)
        return 1
    subprocess.Popen(
        [str(emulator), "-avd", avd, "-netdelay", "none", "-netspeed", "full",
         "-gpu", "angle_indirect", "-memory", "1536", "-no-audio",
         "-no-boot-anim", "-no-snapshot", "-no-snapshot-save"],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
    print(f"Emulator {avd} starting…")
    for _ in range(60):
        time.sleep(5)
        try:
            serial = adb.ensure_device()
            boot = adb._text(["shell", "getprop", "sys.boot_completed"], check=False)
            if boot.strip() == "1":
                print(f"BOOT_COMPLETED on {serial}")
                return 0
        except Exception:
            continue
    print("Emulator did not finish booting in time.")
    return 1


def _set_label(target: str) -> bool:
    html = INDEX_HTML.read_text(encoding="utf-8")
    source, wanted = (SEND, SNED) if target == "Sned" else (SNED, SEND)
    if wanted in html:
        print(f"Label already {target}.")
        return True
    if source not in html:
        print("Send button markup not found; aborting.")
        return False
    INDEX_HTML.write_text(html.replace(source, wanted, 1), encoding="utf-8")
    print(f"Label set to {target} in {INDEX_HTML.name}.")
    return True


def plant_bug() -> int:
    if not _set_label("Sned"):
        return 1
    brain = _brain()
    try:
        build = brain.vscode.build_android()
        if not build.get("built"):
            print("Build failed:", build)
            return 1
        brain.adb.ensure_device()
        brain.adb.wake()
        brain.adb.keep_screen_awake()
        brain.adb.install(Path(build["apk"]))
        brain.adb.launch()
        brain.adb.wait_for_focus(timeout=20)
        time.sleep(4)
        print("Buggy app installed and in foreground. Ready to record the fix.")
        return 0
    finally:
        brain.shutdown()


def reset() -> int:
    if not _set_label("Send"):
        return 1
    brain = _brain()
    try:
        build = brain.vscode.build_android()
        if not build.get("built"):
            print("Build failed:", build)
            return 1
        brain.adb.ensure_device()
        brain.adb.wake()
        brain.adb.keep_screen_awake()
        brain.adb.install(Path(build["apk"]))
        brain.adb.launch()
        print("Clean app installed (button says Send).")
        return 0
    finally:
        brain.shutdown()


def seed() -> int:
    brain = _brain()
    try:
        added = brain.memory.index_codebase(brain.settings.android_project_dir)
        for strategy in (
            "BTCUSDT trend-following: buy pullbacks when EMA trend is up and RSI "
            "between 55 and 70; stop below the swing low, take profit near 2R.",
            "Risk playbook: max 1% paper risk per trade, position cap 20%, "
            "reject entries without a stop loss, prefer HOLD when unsure.",
        ):
            hits = brain.memory.search(strategy, top_k=1, kind="strategy")
            if hits and hits[0]["score"] > 0.98:
                continue  # already seeded; keep the demo memory clean
            brain.memory.remember("strategy", strategy)
        print(f"FAISS seeded (+{added} code chunks). Stats: {brain.memory.stats()}")
        return 0
    finally:
        brain.shutdown()


def reset_paper() -> int:
    brain = _brain()
    try:
        path = brain.settings.paper_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"balance": float(brain.settings.paper_initial_balance), "orders": []},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"Paper account reset: {brain.settings.paper_initial_balance:.2f} "
            f"{brain.settings.paper_currency}, 0 open orders."
        )
        return 0
    finally:
        brain.shutdown()


def status() -> int:
    brain = _brain()
    try:
        diag = brain.diagnostics()
        print("Status:", diag["status"])
        print("Problems:", diag["settings_problems"] or "none")
        print("ADB devices:", diag["adb_devices"])
        print("Memory:", diag["memory"])
        print("Paper:", diag["paper"]["mode"], diag["paper"]["balance"],
              brain.settings.paper_currency, "| open:", len(diag["paper"]["open_orders"]))
        if diag["paper"]["open_orders"]:
            print("WARNING: open paper order(s) present; Muse may HOLD the demo alert. "
                  "Run reset-paper before recording.")
        html = INDEX_HTML.read_text(encoding="utf-8")
        print("Android button label:", "Sned (bug planted)" if SNED in html else "Send (clean)")
        return 0
    finally:
        brain.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Hackathon demo preparation")
    parser.add_argument(
        "command",
        choices=["start-emulator", "plant-bug", "seed", "reset-paper", "status", "reset"],
    )
    parser.add_argument("--avd", default=os.environ.get("DEMO_AVD", "Transportes65"))
    args = parser.parse_args()
    return {
        "start-emulator": lambda: start_emulator(args.avd),
        "plant-bug": plant_bug,
        "seed": seed,
        "reset-paper": reset_paper,
        "status": status,
        "reset": reset,
    }[args.command]()


if __name__ == "__main__":
    sys.exit(main())
