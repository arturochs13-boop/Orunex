"""TASK 1 — Autonomous Android ⇄ Laptop bugfix (Live / voice & vision).

Pipeline (every semantic step is Muse Spark)::

    [ADB Bridge] screencap
        -> [Meta API] multimodal diagnosis (JSON)
        -> [FAISS Match] candidate source files
        -> [Meta API] choose file + exact patch (JSON)
        -> [VS Code] guarded patch (backup + diff) and open editor
        -> [ADB Bridge] rebuild/install/restart (when available)
        -> [Meta API] verify the new screenshot
        -> [FAISS Memory] remember the episode

Voice entry point: Orunex Live (ASR in ``src/_orunex_libs/live_audio.py``)
can pass the transcribed instruction as ``BugfixRequest.instruction``;
this task itself is transport-agnostic and UI-free.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from bridges.adb_bridge import AndroidADBBridge
from bridges.vscode_bridge import PatchError, VSCodeBridge
from core.config import Settings, get_settings
from core.events import ADB, BRAIN, FAISS, META, VSCODE, EventBus
from core.faiss_memory import FAISSMemory
from core.meta_api import MetaAPIClient
from tasks.base import TaskResult, TaskState

DIAGNOSIS_SCHEMA = (
    '{"has_error": bool, "severity": "none|low|medium|high|critical", '
    '"screen": str, "component": str, "visible_text": [str], '
    '"suspected_cause": str, "search_query": str, "confidence": 0.0}'
)
PATCH_SCHEMA = (
    '{"file": str, "line_hint": int, "rationale": str, '
    '"replacements": [{"search": str, "replace": str}], "confidence": 0.0}'
)
VERIFY_SCHEMA = (
    '{"fixed": bool, "still_visible_error": str, "confidence": 0.0, "notes": str}'
)

DIAGNOSIS_SYSTEM = (
    "You are Muse Spark, an expert Android UI debugger. Analyse the phone "
    "screenshot precisely: broken layout, wrong text, crashes, blank areas, "
    "error dialogs. Ground every claim in visible pixels."
)
PATCH_SYSTEM = (
    "You are Muse Spark, a senior Android engineer. Choose the ONE candidate "
    "file that owns the broken component and propose a minimal exact patch. "
    "Each 'search' string must be copied verbatim from the candidate snippet "
    "and occur exactly once in that file. Never invent code that is not shown."
)


@dataclass
class BugfixRequest:
    instruction: str = ""                 # optional voice/text instruction
    package: str = ""                     # defaults to Settings.android_package
    auto_apply: Optional[bool] = None     # None -> Settings.auto_apply_fixes
    rebuild: bool = True
    index_codebase_first: bool = True


@dataclass
class AndroidBugfixTask:
    meta: MetaAPIClient
    memory: FAISSMemory
    adb: AndroidADBBridge
    vscode: VSCodeBridge
    settings: Settings = field(default_factory=get_settings)
    bus: Optional[EventBus] = None

    def _log(self, stage: str, message: str, *, nxt: str = "", level: str = "INFO") -> None:
        if self.bus:
            self.bus.log(stage, message, level=level, next_stage=nxt)

    # ------------------------------------------------------------------- run
    def run(self, request: Optional[BugfixRequest] = None) -> TaskResult:
        request = request or BugfixRequest()
        result = TaskResult(kind="android_bugfix")
        auto_apply = (
            self.settings.auto_apply_fixes if request.auto_apply is None
            else bool(request.auto_apply)
        )
        try:
            # 1) Capture -----------------------------------------------------
            self._log(BRAIN, "Bugfix pipeline started", nxt=ADB)
            image = self.adb.screencap()
            focus = self.adb.current_focus()
            hierarchy = self.adb.ui_hierarchy()
            logcat = self.adb.recent_errors()

            # 2) Muse multimodal diagnosis -----------------------------------
            prompt = (
                "Diagnose this Android screen. "
                f"Current focus: {focus or 'unknown'}. "
                f"User instruction: {request.instruction or '(none)'}. "
                f"UI hierarchy excerpt: {hierarchy[:1500] or '(unavailable)'}. "
                f"Recent logcat errors: {logcat[:1200] or '(none)'}."
            )
            diagnosis = self.meta.analyze_image(
                image, prompt, system=DIAGNOSIS_SYSTEM
            )
            result.data["diagnosis"] = diagnosis
            self._log(
                META,
                f"Diagnosis: has_error={diagnosis.get('has_error')} "
                f"component={diagnosis.get('component')!r} "
                f"confidence={diagnosis.get('confidence')}",
                nxt=FAISS,
            )
            if not diagnosis.get("has_error"):
                self.memory.remember(
                    "episode",
                    f"Android screen checked, no error. Screen: {diagnosis.get('screen')}",
                    task="bugfix_check", outcome="no_error",
                )
                return result.finish(TaskState.COMPLETED, "No UI error detected on screen.")

            # 3) FAISS Match ---------------------------------------------------
            if request.index_codebase_first and self.memory.stats()["kinds"].get("code", 0) == 0:
                self._log(FAISS, "Code index empty -> indexing workspace", nxt=FAISS)
                self.memory.index_codebase()
            query = " ".join(str(x) for x in [
                diagnosis.get("search_query", ""), diagnosis.get("component", ""),
                diagnosis.get("suspected_cause", ""), request.instruction,
            ]).strip()
            candidates = self.memory.find_code_candidates(query, top_k=5)
            result.data["candidates"] = [
                {"path": c["metadata"].get("path"), "score": round(c["score"], 3)}
                for c in candidates
            ]
            if not candidates:
                return result.finish(
                    TaskState.FAILED,
                    "FAISS found no candidate source file. Index the codebase first.",
                )
            self._log(
                FAISS,
                "Top match: " + ", ".join(
                    f"{c['metadata'].get('path')} ({c['score']:.2f})" for c in candidates[:3]
                ),
                nxt=META,
            )

            # 4) Muse chooses file + exact patch ------------------------------
            candidate_blocks = []
            for index, cand in enumerate(candidates, start=1):
                meta = cand["metadata"]
                candidate_blocks.append(
                    f"--- CANDIDATE {index}: {meta.get('path')} "
                    f"(lines from {meta.get('line_start')}, symbols={meta.get('symbols')}) ---\n"
                    f"{cand['text'][:2600]}"
                )
            patch = self.meta.reason_json(
                system=PATCH_SYSTEM,
                user=(
                    f"Diagnosis: {diagnosis}\n\n"
                    + "\n\n".join(candidate_blocks)
                    + "\n\nPick the owning file and propose the minimal exact patch."
                ),
                schema_hint=PATCH_SCHEMA,
            )
            result.data["patch"] = patch
            if float(patch.get("confidence") or 0) < 0.35:
                return result.finish(
                    TaskState.AWAITING_APPROVAL,
                    f"Muse confidence too low ({patch.get('confidence')}); patch kept as proposal.",
                )
            allowed = {str(c["metadata"].get("path")) for c in candidates}
            if str(patch.get("file")) not in allowed:
                raise PatchError(
                    f"Muse picked {patch.get('file')!r}, which is not a FAISS candidate."
                )
            chosen = next(
                c for c in candidates
                if str(c["metadata"].get("path")) == str(patch.get("file"))
            )
            # FAISS paths are relative to the indexed root; the patch guard
            # wants a workspace-absolute target, which the candidate carries.
            patch_target = str(
                chosen["metadata"].get("absolute_path") or patch["file"]
            )

            # 5) Guarded write ---------------------------------------------------
            patch_result = self.vscode.apply_patch(
                patch_target,
                list(patch.get("replacements") or []),
                dry_run=not auto_apply,
            )
            result.data["diff"] = patch_result.diff[:6_000]
            self.vscode.open_in_vscode(patch_result.path, int(patch.get("line_hint") or 1))
            if not auto_apply:
                self.memory.remember(
                    "episode",
                    f"Bugfix proposed for {patch_result.path.name}: {diagnosis.get('suspected_cause')}",
                    task="bugfix", outcome="patch_proposed",
                )
                return result.finish(
                    TaskState.AWAITING_APPROVAL,
                    f"Patch proposed for {patch_result.path.name} (auto-apply off). "
                    "Enable AGENT_AUTO_APPLY_FIXES or approve from the UI.",
                )

            # 6) Rebuild / restart / verify --------------------------------------
            verification: dict[str, Any] = {}
            build: dict[str, Any] = {}
            if request.rebuild:
                build = self.vscode.build_android()
                result.data["build"] = build
                apk = build.get("apk")
                if build.get("built") and apk:
                    self.adb.install(Path(apk))
            self.adb.restart_app(request.package or None)
            time.sleep(3.0)  # WebView first paint can lag the focus change
            verify_image = self.adb.screencap()
            verification = self.meta.reason_json(
                system="You are Muse Spark verifying an Android UI fix from pixels only.",
                user=(
                    f"Original diagnosis: {diagnosis}. Patch rationale: "
                    f"{patch.get('rationale')}. Is the error gone in this new screenshot?"
                ),
                schema_hint=VERIFY_SCHEMA,
                images=[verify_image],
            )
            result.data["verification"] = verification
            fixed = bool(verification.get("fixed"))
            self.memory.remember(
                "episode",
                f"Android bugfix on {patch_result.path.name}: "
                f"{diagnosis.get('suspected_cause')} -> fixed={fixed}",
                task="bugfix", outcome="fixed" if fixed else "not_fixed",
                file=str(patch_result.path),
            )
            self._log(BRAIN, f"Verification fixed={fixed}", nxt=VSCODE if fixed else META)
            return result.finish(
                TaskState.COMPLETED if fixed else TaskState.AWAITING_APPROVAL,
                f"Patch applied to {patch_result.path.name}; "
                f"on-device verification: {'fixed' if fixed else 'error still visible'}.",
            )
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            self._log(BRAIN, result.error, level="ERROR")
            return result.finish(TaskState.FAILED, f"Bugfix failed: {result.error}")
