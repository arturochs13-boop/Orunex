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

import re
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
    "Candidates may include an 'EXACT SOURCE LINES' block; its 'Lx:' prefixes "
    "are only for orientation, so copy the source text after them verbatim. "
    "Each 'search' string must be copied verbatim from the shown source and "
    "occur exactly once in that file. Never invent code that is not shown."
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

    def _evidence_block(
        self,
        path_value: Any,
        tokens: list[str],
        weights: dict[str, float],
        *,
        radius: int = 3,
        max_hits: int = 6,
    ) -> str:
        """Exact source lines around diagnosis terms (deterministic retrieval).

        FAISS chunks can be longer than the snippet budget, so the line that
        contains the visible typo may fall outside it.  This block guarantees
        Muse can copy a literal ``search`` string without inventing code.
        """
        if not path_value or not tokens:
            return ""
        try:
            path = Path(str(path_value)).resolve()
            workspace = self.settings.workspace_root.resolve()
            if workspace not in path.parents or not path.is_file():
                return ""
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return ""
        ranked: list[tuple[float, int]] = []
        for index, line in enumerate(lines):
            lowered = line.lower()
            score = sum(weights.get(token, 1.0) for token in tokens if token in lowered)
            if score:
                ranked.append((score, index))
        if not ranked:
            return ""
        ranked.sort(key=lambda item: (-item[0], item[1]))
        chosen: set[int] = set()
        for _, index in ranked[:max_hits]:
            chosen.update(range(max(0, index - radius), min(len(lines), index + radius + 1)))
            if len(chosen) >= 40:
                break
        block = "\n".join(f"L{index + 1}: {lines[index]}" for index in sorted(chosen))
        return block[:4_000]

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
            package = request.package or self.settings.android_package
            ensure = getattr(self.adb, "ensure_device", None)
            if callable(ensure):
                ensure()
            wake = getattr(self.adb, "wake", None)
            if callable(wake):
                wake()
            keep_awake = getattr(self.adb, "keep_screen_awake", None)
            if callable(keep_awake):
                keep_awake()
            focus = self.adb.current_focus()
            if package not in focus:
                self._log(ADB, f"Foregrounding {package}", nxt=META)
                self.adb.launch(package)
                if not self.adb.wait_for_focus(package, timeout=20):
                    raise RuntimeError(f"Could not bring {package} to the foreground.")
                time.sleep(1.2)
                focus = self.adb.current_focus()
            image = self.adb.screencap()
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
            if request.index_codebase_first:
                # Incremental refresh keeps candidate snippets in sync with the
                # file on disk (e.g. after re-planting the demo defect).
                self._log(FAISS, "Refreshing code index (incremental)", nxt=FAISS)
                index_root = self.settings.android_project_dir
                if not index_root.is_dir():
                    index_root = self.settings.workspace_root
                added = self.memory.index_codebase(index_root)
                if added:
                    self._log(FAISS, f"Code index refreshed: +{added} chunk(s)", nxt=FAISS)
            visible = diagnosis.get("visible_text") or []
            if isinstance(visible, str):
                visible = [visible]
            elif not isinstance(visible, (list, tuple)):
                visible = [visible]
            query = " ".join(str(x) for x in [
                diagnosis.get("search_query", ""), diagnosis.get("component", ""),
                diagnosis.get("suspected_cause", ""),
                " ".join(str(v) for v in visible), request.instruction,
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
            evidence_text = " ".join(str(x) for x in [
                " ".join(str(v) for v in visible),
                diagnosis.get("search_query", ""), diagnosis.get("component", ""),
                diagnosis.get("suspected_cause", ""), request.instruction,
            ])
            evidence_tokens = list(dict.fromkeys(
                re.findall(r"[A-Za-z0-9_.$#-]{3,}", evidence_text.lower())
            ))
            weights: dict[str, float] = {}
            for token in evidence_tokens:
                docs = sum(1 for c in candidates if token in c["text"].lower())
                weights[token] = 3.0 if docs == 1 else 1.0  # rare = distinctive
            candidate_blocks = []
            evidence_count = 0
            for index, cand in enumerate(candidates, start=1):
                meta = cand["metadata"]
                evidence = self._evidence_block(
                    meta.get("absolute_path"), evidence_tokens, weights
                )
                if evidence:
                    evidence_count += 1
                block = (
                    f"--- CANDIDATE {index}: {meta.get('path')} "
                    f"(lines from {meta.get('line_start')}, symbols={meta.get('symbols')}) ---\n"
                    f"{cand['text'][:2200]}"
                )
                if evidence:
                    block += (
                        f"\n--- EXACT SOURCE LINES FROM {meta.get('path')} "
                        f"(copy the text after 'Lx: ') ---\n{evidence}"
                    )
                candidate_blocks.append(block)
            if evidence_count:
                self._log(
                    FAISS,
                    f"Attached exact evidence lines for {evidence_count} candidate(s)",
                    nxt=META,
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
                if not build.get("built") or not apk:
                    detail = str(
                        build.get("message") or build.get("output_tail") or "unknown build error"
                    )[-500:]
                    return result.finish(
                        TaskState.FAILED,
                        f"Patch applied to {patch_result.path.name}, but the Android "
                        f"rebuild failed: {detail}",
                    )
                self.adb.install(Path(apk))
            focused = self.adb.restart_app(request.package or None)
            if focused is False:
                self._log(
                    ADB, "App did not regain focus; retrying launch", level="WARN", nxt=META
                )
                self.adb.launch(request.package or None)
                self.adb.wait_for_focus(request.package or None, timeout=15)
            time.sleep(3.0)  # WebView first paint can lag the focus change
            verify_image = self.adb.screencap()
            # A cold WebView can report focus while still showing a blank
            # frame.  Wait until the frame has real content (measured by PNG
            # size relative to the pre-patch capture) before asking Muse.
            if len(image) >= 20_000:
                expected = max(40_000, len(image) // 2)
                deadline = time.monotonic() + 12.0
                if len(verify_image) < expected:
                    self._log(
                        ADB, "Verification frame still painting; waiting for content",
                        nxt=META,
                    )
                while len(verify_image) < expected and time.monotonic() < deadline:
                    time.sleep(1.5)
                    verify_image = self.adb.screencap()
                if len(verify_image) >= expected:
                    self._log(
                        ADB, f"Verification frame ready ({len(verify_image) // 1024} KB)",
                        nxt=META,
                    )
            verification: dict[str, Any] = {}
            for attempt in range(2):
                verification = self.meta.reason_json(
                    system="You are Muse Spark verifying an Android UI fix from pixels only.",
                    user=(
                        f"Original diagnosis: {diagnosis}. Patch rationale: "
                        f"{patch.get('rationale')}. Is the error gone in this new screenshot?"
                    ),
                    schema_hint=VERIFY_SCHEMA,
                    images=[verify_image],
                )
                if verification.get("fixed") or attempt:
                    break
                self._log(
                    META, "Verification not fixed yet; recapturing after settle",
                    level="WARN",
                )
                time.sleep(2.0)
                verify_image = self.adb.screencap()
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
