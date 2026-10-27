"""VS Code bridge — guarded autonomous source edits + optional rebuild.

Safety contract (enforced here, not by the model):
* paths must resolve inside the workspace and use an allow-listed suffix;
* a patch is a list of exact ``search`` -> ``replace`` replacements, each
  search string must occur exactly once (no fuzzy writes);
* every applied file is backed up first and written atomically;
* a unified diff is always produced for the log/UI.
"""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from core.config import Settings, get_settings
from core.events import VSCODE, EventBus

ALLOWED_SUFFIXES = {
    ".kt", ".kts", ".java", ".xml", ".py", ".js", ".ts", ".tsx",
    ".html", ".css", ".json", ".gradle", ".md", ".txt",
}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PatchError(RuntimeError):
    pass


@dataclass
class PatchResult:
    path: Path
    backup_path: Optional[Path]
    diff: str
    replacements: int
    applied: bool


class VSCodeBridge:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus

    def _log(self, message: str, *, level: str = "INFO", next_stage: str = "") -> None:
        if self.bus:
            self.bus.log(VSCODE, message, level=level, next_stage=next_stage)

    # --------------------------------------------------------------- guardrails
    def resolve_source_file(self, relative_or_path: str) -> Path:
        candidate = Path(relative_or_path).expanduser()
        if not candidate.is_absolute():
            candidate = self.settings.workspace_root / candidate
        resolved = candidate.resolve()
        workspace = self.settings.workspace_root.resolve()
        if workspace not in resolved.parents and resolved != workspace:
            raise PatchError(f"Path escapes the workspace: {relative_or_path}")
        if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
            raise PatchError(f"File type not allow-listed for edits: {resolved.suffix}")
        if not resolved.exists():
            raise PatchError(f"Source file does not exist: {resolved}")
        if resolved.stat().st_size > 512_000:
            raise PatchError("Source file too large for an autonomous patch.")
        return resolved

    # ------------------------------------------------------------------- edit
    def apply_patch(
        self,
        relative_or_path: str,
        replacements: list[dict[str, Any]],
        *,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply exact replacements, or only compute the diff when dry_run."""
        path = self.resolve_source_file(relative_or_path)
        if not replacements:
            raise PatchError("Patch contains no replacements.")
        if len(replacements) > self.settings.max_patch_replacements:
            raise PatchError(
                f"Patch has {len(replacements)} replacements; "
                f"limit is {self.settings.max_patch_replacements}."
            )
        original = path.read_text(encoding="utf-8", errors="strict")
        updated = original
        for index, item in enumerate(replacements, start=1):
            search = str(item.get("search") or "")
            replace = str(item.get("replace") or "")
            if not search:
                raise PatchError(f"Replacement #{index} has an empty search string.")
            count = updated.count(search)
            if count != 1:
                raise PatchError(
                    f"Replacement #{index} search occurs {count} time(s) in "
                    f"{path.name}; exactly 1 required. No file was modified."
                )
            updated = updated.replace(search, replace, 1)

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(path),
                tofile=str(path) + " (patched)",
            )
        )
        if dry_run:
            self._log(f"Dry-run patch for {path.name} ({len(replacements)} change(s))")
            return PatchResult(path, None, diff, len(replacements), applied=False)

        backup_dir = self.settings.workspace_root / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, backup)
        tmp = path.with_suffix(path.suffix + ".orunex.tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, path)
        self._log(
            f"Patched {path.name} ({len(replacements)} change(s)); backup: {backup.name}",
            next_stage="ADB Bridge",
        )
        return PatchResult(path, backup, diff, len(replacements), applied=True)

    # ------------------------------------------------------------------ editor
    def open_in_vscode(self, path: Path, line: int = 1) -> bool:
        """Open the patched file at a line. Best effort; never raises."""
        code_exe: Optional[str] = None
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            shutil.which("code") or "",
            str(Path(local) / "Programs" / "Microsoft VS Code" / "Code.exe") if local else "",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                code_exe = candidate
                break
        if not code_exe:
            self._log("VS Code executable not found; file left on disk.", level="WARN")
            return False
        try:
            subprocess.Popen(
                [code_exe, "-g", f"{path}:{max(1, int(line))}:1"],
                creationflags=_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._log(f"Opened {path.name}:{line} in VS Code")
            return True
        except OSError as exc:
            self._log(f"Could not open VS Code: {exc}", level="WARN")
            return False

    # ------------------------------------------------------------------- build
    @staticmethod
    def _find_gradle(project: Path) -> Optional[Path]:
        """Wrapper first, then GRADLE_HOME, then the local wrapper cache."""
        wrapper = project / ("gradlew.bat" if os.name == "nt" else "gradlew")
        if wrapper.exists():
            return wrapper
        gradle_home = os.environ.get("GRADLE_HOME", "")
        if gradle_home:
            candidate = Path(gradle_home) / "bin" / ("gradle.bat" if os.name == "nt" else "gradle")
            if candidate.exists():
                return candidate
        dists = Path.home() / ".gradle" / "wrapper" / "dists"
        if dists.exists():
            name = "gradle.bat" if os.name == "nt" else "gradle"
            cached = sorted(
                dists.rglob(f"bin/{name}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if cached:
                return cached[0]
        found = shutil.which("gradle")
        return Path(found) if found else None

    def build_android(self) -> dict[str, Any]:
        """Build with Gradle (wrapper or cached distribution) when available."""
        project = self.settings.android_project_dir
        gradle = self._find_gradle(project)
        if gradle is None:
            message = (
                f"No Gradle found for {project}; skipping rebuild. "
                "Install Gradle or open the project in Android Studio once."
            )
            self._log(message, level="WARN", next_stage="ADB Bridge")
            return {"built": False, "skipped": True, "message": message}
        try:
            if os.name == "nt":
                command = ["cmd", "/c", str(gradle), "assembleDebug", "--console=plain"]
            else:
                command = [str(gradle), "assembleDebug", "--console=plain"]
            result = subprocess.run(
                command, cwd=str(project), capture_output=True, text=True,
                timeout=900, creationflags=_NO_WINDOW,
            )
            apks = sorted(
                project.rglob("app-debug.apk"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            apk = apks[0] if apks else None
            ok = result.returncode == 0
            tail = (result.stdout + result.stderr)[-1_500:]
            self._log(f"Gradle assembleDebug {'OK' if ok else 'FAILED'}", next_stage="ADB Bridge")
            return {"built": ok, "skipped": False, "apk": str(apk) if apk else "",
                    "output_tail": tail}
        except Exception as exc:
            return {"built": False, "skipped": False,
                    "message": f"{type(exc).__name__}: {exc}"}
