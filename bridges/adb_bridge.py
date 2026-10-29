"""Android ADB bridge — background device control, zero shell injection.

Every command is executed as an argv list (never ``shell=True`` with user
input).  The bridge only transports bytes/commands; all interpretation of
a screenshot is done by Muse Spark in :mod:`core.meta_api`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from core.config import Settings, get_settings
from core.events import ADB, EventBus

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ADBError(RuntimeError):
    pass


def find_adb(settings: Optional[Settings] = None) -> Optional[str]:
    """Locate adb: env override -> PATH -> common Android SDK locations."""
    settings = settings or get_settings()
    candidates: list[str] = []
    if settings.adb_path:
        candidates.append(settings.adb_path)
    found = shutil.which("adb")
    if found:
        candidates.append(found)
    local = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()
    candidates += [
        str(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe") if local else "",
        str(home / "Android" / "Sdk" / "platform-tools" / "adb"),
        str(home / "Library" / "Android" / "sdk" / "platform-tools" / "adb"),
        "/usr/lib/android-sdk/platform-tools/adb",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return found


class AndroidADBBridge:
    """Background ADB control for one Android device/emulator."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus
        self.adb = find_adb(self.settings)
        self.serial = self.settings.adb_serial or ""
        self._serial_is_explicit = bool(self.settings.adb_serial)
        self._ready_at = 0.0
        self._prepared_at = 0.0
        self._prepared_package = ""

    # ------------------------------------------------------------------ util
    def _log(self, message: str, *, level: str = "INFO", next_stage: str = "") -> None:
        if self.bus:
            self.bus.log(ADB, message, level=level, next_stage=next_stage)

    @property
    def available(self) -> bool:
        return bool(self.adb)

    def _base_args(self) -> list[str]:
        args = [self.adb or "adb"]
        if self.serial:
            args += ["-s", self.serial]
        return args

    def run(
        self,
        args: list[str],
        *,
        timeout: float = 30.0,
        binary: bool = False,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        if not self.adb:
            raise ADBError(
                "adb not found. Install Android platform-tools or set ADB_PATH in .env."
            )
        full = self._base_args() + [str(a) for a in args]
        try:
            result = subprocess.run(
                full,
                capture_output=True,
                timeout=timeout,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise ADBError(f"adb timed out after {timeout:.0f}s: {' '.join(args)}") from exc
        except OSError as exc:
            raise ADBError(f"adb could not start: {exc}") from exc
        if check and result.returncode != 0:
            stderr = result.stderr.decode("utf-8", "ignore").strip()[:300]
            raise ADBError(f"adb {' '.join(args)} failed ({result.returncode}): {stderr}")
        return result

    def _text(self, args: list[str], **kwargs) -> str:
        return self.run(args, **kwargs).stdout.decode("utf-8", "ignore").strip()

    # --------------------------------------------------------------- devices
    def devices(self) -> list[dict[str, str]]:
        output = self._text(["devices"], timeout=15)
        devices: list[dict[str, str]] = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                devices.append({"serial": parts[0], "state": parts[1]})
        return devices

    def _pick_device(self, devices: list[dict[str, str]]) -> str:
        """Pick the intended serial without silently switching targets."""
        ready = [d["serial"] for d in devices if d.get("state") == "device"]
        if self._serial_is_explicit:
            return self.serial if self.serial in ready else ""
        if self.serial and self.serial in ready:
            return self.serial
        if self.settings.android_avd:
            for serial in ready:
                if serial.startswith("emulator-"):
                    return serial
        return ready[0] if ready else ""

    def ensure_device(self, *, force: bool = False) -> str:
        """Return a ready serial, auto-starting the configured AVD if needed."""
        # A very short readiness cache removes several adb round-trips from
        # the hot path (capture -> verify) without hiding a dead emulator for
        # more than a few seconds.
        if (
            not force and self.serial
            and time.monotonic() - self._ready_at < 5.0
        ):
            return self.serial
        devices = [d for d in self.devices() if d["state"] == "device"]
        if self.serial:
            deadline = time.monotonic() + 25.0
            while not any(d["serial"] == self.serial for d in devices):
                if time.monotonic() >= deadline:
                    break
                time.sleep(1.0)
                devices = [d for d in self.devices() if d["state"] == "device"]
            if any(d["serial"] == self.serial for d in devices):
                self._ready_at = time.monotonic()
                return self.serial
            # The emulator may have died while Gradle was building.  Restart
            # the configured AVD instead of failing the whole task.  An
            # explicitly configured serial is never replaced by another one.
            can_restart_avd = self.settings.android_avd and (
                not self._serial_is_explicit or self.serial.startswith("emulator-")
            )
            if can_restart_avd and not self._emulator_process_running():
                self._ready_at = 0.0
                if self._start_emulator():
                    devices = [d for d in self.devices() if d["state"] == "device"]
                    chosen = self._pick_device(devices)
                    if chosen:
                        self.serial = chosen
                        self._ready_at = time.monotonic()
                        return self.serial
            raise ADBError(f"Configured device {self.serial} is not ready.")
        if not devices:
            # An emulator process may already own the AVD while ADB has not
            # listed it yet.  Launching a second instance for the same AVD
            # can kill both, so wait for the existing process first.
            if self._emulator_process_running():
                wait_deadline = time.monotonic() + 60.0
                while time.monotonic() < wait_deadline and not devices:
                    time.sleep(2.0)
                    devices = [d for d in self.devices() if d["state"] == "device"]
            if not devices and self.settings.android_avd and self._start_emulator():
                devices = [d for d in self.devices() if d["state"] == "device"]
            if not devices:
                raise ADBError(
                    "No Android device ready. Connect USB (debugging on), start an "
                    "emulator, or set ANDROID_AVD so the bridge can start one."
                )
        chosen = self._pick_device(devices)
        if not chosen:
            raise ADBError("No Android device ready.")
        self.serial = chosen
        self._ready_at = time.monotonic()
        self._log(f"Device ready: {self.serial}", next_stage="Meta API")
        return self.serial

    @staticmethod
    def _emulator_process_running() -> bool:
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10,
                creationflags=_NO_WINDOW,
            )
            output = (result.stdout or "").lower()
            return '"emulator.exe"' in output or '"qemu-system-x86_64.exe"' in output
        except (OSError, subprocess.SubprocessError):
            return False

    def _start_emulator(self, boot_timeout: float = 240.0) -> bool:
        """Launch the configured AVD (visible window) and wait for full boot."""
        avd = self.settings.android_avd
        emulator: Optional[Path] = None
        if self.adb:
            candidate = Path(self.adb).resolve().parent.parent / "emulator" / (
                "emulator.exe" if os.name == "nt" else "emulator"
            )
            if candidate.exists():
                emulator = candidate
        if emulator is None:
            found = shutil.which("emulator")
            emulator = Path(found) if found else None
        if emulator is None:
            self._log("emulator executable not found next to adb.", level="WARN")
            return False
        self._log(f"Starting emulator AVD {avd}…", next_stage="Meta API")
        try:
            # GPU auto (host) renders this 1080x2340 AVD smoothly; software
            # rendering saturated SystemUI in testing. RAM stays capped.
            subprocess.Popen(
                [str(emulator), "-avd", avd, "-netdelay", "none", "-netspeed", "full",
                 "-gpu", "angle_indirect", "-memory", "1536", "-no-audio",
                 "-no-boot-anim", "-no-snapshot", "-no-snapshot-save"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        except OSError as exc:
            self._log(f"Could not start emulator: {exc}", level="ERROR")
            return False
        deadline = time.monotonic() + boot_timeout
        started_at = time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(4)
            try:
                ready = [d for d in self.devices() if d["state"] == "device"]
                if not ready:
                    # Do not burn the whole boot timeout if the launcher
                    # exited (common when another instance owns the AVD).
                    if (
                        time.monotonic() - started_at > 20.0
                        and not self._emulator_process_running()
                    ):
                        self._log("Emulator process exited before ADB was ready.", level="ERROR")
                        return False
                    continue
                chosen = self._pick_device(ready)
                if not chosen:
                    continue
                self.serial = chosen
                boot = self._text(
                    ["shell", "getprop", "sys.boot_completed"], timeout=10, check=False
                )
                if boot.strip() == "1":
                    self._ready_at = time.monotonic()
                    self._log(f"Emulator booted: {self.serial}", next_stage="Meta API")
                    return True
            except ADBError:
                continue
        self._log("Emulator did not finish booting in time.", level="ERROR")
        return False

    # ------------------------------------------------------------ interaction
    def screencap(self, save_to: Optional[Path] = None) -> bytes:
        """Capture the current screen as PNG bytes (kept in memory by default)."""
        self.ensure_device()
        started = time.monotonic()
        try:
            data = self.run(["exec-out", "screencap", "-p"], timeout=30, binary=True).stdout
        except ADBError as exc:
            if "not found" not in str(exc) and "offline" not in str(exc):
                raise
            self._ready_at = 0.0
            self.ensure_device(force=True)
            data = self.run(["exec-out", "screencap", "-p"], timeout=30, binary=True).stdout
        if not data.startswith(_PNG_MAGIC):
            raise ADBError("screencap did not return a PNG image.")
        if save_to:
            Path(save_to).parent.mkdir(parents=True, exist_ok=True)
            Path(save_to).write_bytes(data)
        self._log(
            f"Screenshot ready ({len(data) / 1024:.0f} KB, "
            f"{time.monotonic() - started:.1f}s)",
            next_stage="Meta API",
        )
        return data

    def tap(self, x: int, y: int) -> None:
        self.run(["shell", "input", "tap", str(int(x)), str(int(y))], timeout=15)
        self._log(f"Tap ({int(x)}, {int(y)})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.run(
            ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
            timeout=15,
        )

    def keyevent(self, keycode: int | str) -> None:
        self.run(["shell", "input", "keyevent", str(keycode)], timeout=15)

    def input_text(self, text: str) -> None:
        # ADB input replaces spaces with %s and rejects shell metacharacters.
        safe = re.sub(r"[^A-Za-z0-9 .,;:_\-@]", "", str(text)).replace(" ", "%s")
        if safe:
            self.run(["shell", "input", "text", safe], timeout=15)

    def force_stop(self, package: Optional[str] = None) -> None:
        package = package or self.settings.android_package
        self.run(["shell", "am", "force-stop", package], timeout=15)
        self._log(f"Force-stopped {package}")

    def resolve_launcher_activity(self, package: Optional[str] = None) -> str:
        """Return the launcher component (``package/activity``) or ''."""
        package = package or self.settings.android_package
        try:
            output = self._text(
                ["shell", "cmd", "package", "resolve-activity", "--brief",
                 "-a", "android.intent.action.MAIN",
                 "-c", "android.intent.category.LAUNCHER", package],
                timeout=15, check=False,
            )
        except ADBError:
            return ""
        match = re.search(r"([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)", output)
        return match.group(1) if match else ""

    def launch(self, package: Optional[str] = None, activity: Optional[str] = None) -> str:
        package = package or self.settings.android_package
        activity = activity or self.settings.android_activity
        component = ""
        if activity:
            component = activity if "/" in activity else f"{package}/{activity}"
        else:
            component = self.resolve_launcher_activity(package)
        if component:
            output = self._text(
                ["shell", "am", "start", "-n", component], timeout=20, check=False
            )
        else:  # last resort: monkey launcher injection
            output = self._text(
                ["shell", "monkey", "-p", package, "-c",
                 "android.intent.category.LAUNCHER", "1"],
                timeout=20, check=False,
            )
        self._log(f"Launched {package}", next_stage="Meta API")
        return output

    def wait_for_focus(self, package: Optional[str] = None, timeout: float = 15.0) -> bool:
        """Poll until the package owns the foreground window (or time out)."""
        package = package or self.settings.android_package
        deadline = time.monotonic() + max(1.0, timeout)
        while time.monotonic() < deadline:
            if package in self.current_focus():
                return True
            time.sleep(0.5)
        return False

    def wake(self) -> None:
        """Wake the display and dismiss a non-secure keyguard (best effort)."""
        # One device-shell round-trip for both static commands.  A busy
        # emulator must never fail the actual task because of this nicety.
        try:
            self.run(
                ["shell", "input keyevent 224; wm dismiss-keyguard"],
                timeout=10, check=False,
            )
        except ADBError:
            pass

    def keep_screen_awake(self) -> None:
        """Keep the demo device awake while it is charging (best effort)."""
        try:
            self.run(
                ["shell", "svc power stayon true; settings put system screen_off_timeout 1800000"],
                timeout=15, check=False,
            )
        except ADBError:
            pass

    def dismiss_system_anr(self) -> bool:
        """Dismiss a 'System UI isn't responding' dialog by tapping Wait."""
        hierarchy = self.ui_hierarchy()
        if "aerr_wait" not in hierarchy and "System UI isn" not in hierarchy:
            return False
        match = re.search(
            r'resource-id="android:id/aerr_wait"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            hierarchy,
        )
        if not match:
            match = re.search(
                r'text="Wait"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                hierarchy,
            )
        if not match:
            return False
        x1, y1, x2, y2 = (int(value) for value in match.groups())
        self.tap((x1 + x2) // 2, (y1 + y2) // 2)
        time.sleep(1.0)
        self._log("Dismissed SystemUI ANR dialog (Wait)", level="WARN")
        return True

    def prepare_for_task(self, package: Optional[str] = None) -> str:
        """Fast task entry: ready device + awake screen + app in foreground."""
        package = package or self.settings.android_package
        self.ensure_device()
        now = time.monotonic()
        if package != self._prepared_package or now - self._prepared_at > 60.0:
            self.wake()
            self.keep_screen_awake()
            self._prepared_package = package
            self._prepared_at = now
        focus, anr_visible = self._focus_snapshot()
        if anr_visible:
            self.dismiss_system_anr()
            focus = self.current_focus()
        if package not in focus:
            self.launch(package)
            if not self.wait_for_focus(package, timeout=20):
                raise ADBError(f"Could not bring {package} to the foreground.")
            time.sleep(0.6)  # first frame after a cold start
            _focus, anr_visible = self._focus_snapshot()
            if anr_visible:
                self.dismiss_system_anr()
            focus = self.current_focus()
        return focus

    def restart_app(self, package: Optional[str] = None, *, settle: float = 2.5) -> bool:
        self.ensure_device()
        self.force_stop(package)
        time.sleep(0.6)
        self.launch(package)
        focused = self.wait_for_focus(package)
        if not focused:  # one cold-start retry before giving up
            self.launch(package)
            focused = self.wait_for_focus(package, timeout=10)
        _focus, anr_visible = self._focus_snapshot()
        if anr_visible:
            self.dismiss_system_anr()
        if settle > 0:
            time.sleep(settle)  # let splash/WebView finish before any screenshot
        _focus, anr_visible = self._focus_snapshot()
        if anr_visible:
            self.dismiss_system_anr()
        return focused

    def install(self, apk_path: Path, *, replace: bool = True) -> None:
        args = ["install"] + (["-r"] if replace else []) + [str(apk_path)]
        for attempt in range(2):
            try:
                self.ensure_device(force=attempt > 0)
                self.run(args, timeout=300)
                self._log(f"Installed {apk_path.name}")
                return
            except ADBError as exc:
                message = str(exc).lower()
                recoverable = any(
                    token in message
                    for token in ("not found", "offline", "no devices", "not ready")
                )
                if attempt or not recoverable:
                    raise
                self._ready_at = 0.0
                self._log(
                    "Device disappeared before install; recovering emulator and retrying",
                    level="WARN",
                )
                self.ensure_device(force=True)

    def _focus_snapshot(self) -> tuple[str, bool]:
        """Return ``(foreground component, system ANR dialog visible)``."""
        anr_visible = False
        # Android 16 reports focus under `dumpsys window displays`; older
        # versions used `dumpsys window windows`. Try both, then activities.
        for args in (
            ["shell", "dumpsys", "window", "displays"],
            ["shell", "dumpsys", "window", "windows"],
            ["shell", "dumpsys", "activity", "activities"],
        ):
            try:
                output = self._text(args, timeout=20, check=False)
            except ADBError:
                continue
            if "Application Not Responding" in output or "System UI isn" in output:
                anr_visible = True
            match = re.search(r"mCurrentFocus=Window\{[^}]*\s(\S+/\S+)\}", output)
            if match:
                return match.group(1), anr_visible
            match = re.search(r"topResumedActivity=\S+\s(\S+/\S+)", output)
            if match:
                return match.group(1), anr_visible
        return "", anr_visible

    def current_focus(self) -> str:
        return self._focus_snapshot()[0]

    def ui_hierarchy(self) -> str:
        """Best-effort visible UI tree (helps Muse ground a component)."""
        try:
            output = self._text(
                ["exec-out", "uiautomator", "dump", "/dev/tty"], timeout=25, check=False
            )[:12_000]
            if output.lstrip().upper().startswith("ERROR"):
                return ""  # e.g. transient null root while a WebView loads
            return output
        except ADBError:
            return ""

    def recent_errors(self, lines: int = 80) -> str:
        try:
            output = self._text(
                ["logcat", "-d", "-t", str(int(lines)), "*:E"], timeout=20, check=False
            )
            return output[-6_000:]
        except ADBError:
            return ""
