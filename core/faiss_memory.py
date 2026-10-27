"""Local FAISS vector memory for code, strategies and agent episodes.

Design note (Muse-Spark exclusivity): embeddings here are a deterministic
feature-hashing vectorizer, *not* a learned model.  FAISS therefore does
pure storage/recall; every semantic judgement (what matches, what to fix,
whether to trade) is made by ``muse-spark`` in :mod:`core.meta_api`.

Namespaces (``kind`` metadata):
    ``code``      chunks of local source files (Android bugfix lookup)
    ``strategy``  trading strategies / playbooks (paper-trading recall)
    ``episode``   completed task outcomes (long-term learning)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover
    faiss = None  # type: ignore
    _FAISS_ERROR: Optional[Exception] = exc
else:
    _FAISS_ERROR = None

from .config import Settings, get_settings
from .events import FAISS, MEMORY, EventBus

DIMENSION = 384
_WORD_RE = re.compile(r"[a-z0-9_+#.\-]+", re.UNICODE)
CODE_EXTENSIONS = {
    ".kt", ".kts", ".java", ".xml", ".py", ".js", ".ts", ".tsx",
    ".html", ".css", ".json", ".gradle",
}
SKIP_DIRS = {
    ".git", ".gradle", "build", "__pycache__", "node_modules",
    ".ruff_cache", "simplex_bin", "simplex_data", "scratch",
}


# --------------------------------------------------------------------------
# Deterministic embedding (no model involved)
# --------------------------------------------------------------------------
def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def hash_embedding(text: str, dimension: int = DIMENSION) -> np.ndarray:
    vector = np.zeros(max(1, dimension), dtype=np.float32)
    words = _WORD_RE.findall(_normalise(text))
    counts: dict[str, float] = {}

    def add(feature: str, weight: float) -> None:
        counts[feature] = counts.get(feature, 0.0) + weight

    for word in words:
        add("w:" + word, 1.0)
    for left, right in zip(words, words[1:]):
        add(f"b:{left} {right}", 0.6)
    compact = re.sub(r"\s+", " ", _normalise(text)).strip()
    for i in range(max(0, len(compact) - 2)):
        add("c:" + compact[i : i + 3], 0.25)

    for feature, weight in counts.items():
        digest = hashlib.blake2b(feature.encode("utf-8", "ignore"), digest_size=8).digest()
        value = int.from_bytes(digest, "little")
        vector[value % len(vector)] += (1.0 if (value >> 63) & 1 else -1.0) * (
            1.0 + np.log1p(weight)
        )
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        vector[0] = 1.0
        norm = 1.0
    return np.ascontiguousarray(vector / norm, dtype=np.float32)


class FAISSMemory:
    """Thread-safe persistent FAISS memory (cosine via inner product)."""

    def __init__(
        self,
        index_path: Optional[Path] = None,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        if faiss is None:
            raise RuntimeError(
                "FAISS is not installed. Run: pip install faiss-cpu"
            ) from _FAISS_ERROR
        self.settings = settings or get_settings()
        self.bus = bus
        self.index_path = Path(index_path or self.settings.memory_index_path)
        self.metadata_path = Path(str(self.index_path) + ".meta.json")
        self._lock = threading.RLock()
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(DIMENSION))
        self._metadata: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._load()

    # ---------------------------------------------------------------- basics
    @property
    def count(self) -> int:
        with self._lock:
            return len(self._metadata)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            kinds: dict[str, int] = {}
            for meta in self._metadata.values():
                kind = str(meta.get("kind") or "misc")
                kinds[kind] = kinds.get(kind, 0) + 1
            return {"total": len(self._metadata), "kinds": kinds,
                    "index_path": str(self.index_path)}

    def _log(self, message: str, *, next_stage: str = "", level: str = "INFO") -> None:
        if self.bus:
            self.bus.log(MEMORY, message, next_stage=next_stage, level=level)

    # ------------------------------------------------------------- core CRUD
    def add_text(
        self, text: str, metadata: Optional[Mapping[str, Any]] = None, *, persist: bool = True
    ) -> int:
        clean = str(text or "").strip()
        if not clean:
            raise ValueError("Cannot store an empty memory.")
        vector = hash_embedding(clean).reshape(1, -1)
        with self._lock:
            memory_id = int(self._next_id)
            self._index.add_with_ids(vector, np.asarray([memory_id], dtype=np.int64))
            meta = dict(metadata or {})
            meta.update({"id": memory_id, "text": clean, "created_at": time.time()})
            self._metadata[memory_id] = meta
            self._next_id += 1
            if persist:
                self._save_locked()
            return memory_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        kind: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        if not clean:
            return []
        vector = hash_embedding(clean).reshape(1, -1)
        with self._lock:
            if self._index.ntotal <= 0:
                return []
            # Over-fetch when filtering by kind so the filter cannot starve us.
            fetch = min(int(self._index.ntotal), max(top_k * 6, top_k))
            scores, ids = self._index.search(vector, fetch)
            results: list[dict[str, Any]] = []
            for score, memory_id in zip(scores[0], ids[0]):
                memory_id = int(memory_id)
                if memory_id < 0 or float(score) < min_score:
                    continue
                meta = dict(self._metadata.get(memory_id, {}))
                if kind and meta.get("kind") != kind:
                    continue
                results.append({
                    "id": memory_id,
                    "score": float(score),
                    "text": str(meta.get("text") or ""),
                    "metadata": meta,
                })
                if len(results) >= top_k:
                    break
            self._log(
                f"Recall '{clean[:48]}' -> {len(results)} hit(s)"
                + (f" kind={kind}" if kind else ""),
                next_stage=FAISS,
            )
            return results

    def remember(self, kind: str, text: str, **metadata: Any) -> int:
        return self.add_text(text, {"kind": kind, **metadata})

    # ------------------------------------------------------- codebase index
    def index_codebase(
        self,
        root: Optional[Path] = None,
        *,
        chunk_lines: int = 120,
        overlap: int = 20,
    ) -> int:
        """Index local source files so a diagnosis can find its file."""
        root = Path(root or self.settings.workspace_root)
        added = 0
        # path -> (indexed file mtime, [chunk ids]) so changed files refresh.
        indexed: dict[str, tuple[float, list[int]]] = {}
        with self._lock:
            for memory_id, meta in self._metadata.items():
                if meta.get("kind") != "code":
                    continue
                entry = indexed.setdefault(
                    str(meta.get("absolute_path") or meta.get("path")),
                    (float(meta.get("file_mtime") or 0), []),
                )
                entry[1].append(int(memory_id))
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                stat = path.stat()
                if stat.st_size > 512_000:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            relative = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            previous = indexed.get(str(path))
            if previous and stat.st_mtime <= previous[0]:
                continue  # unchanged since it was indexed
            if previous:  # changed on disk: drop stale chunks before re-adding
                stale_ids = np.asarray(previous[1], dtype=np.int64)
                with self._lock:
                    try:
                        self._index.remove_ids(stale_ids)
                    except Exception:
                        pass
                    for stale_id in previous[1]:
                        self._metadata.pop(int(stale_id), None)
            lines = content.splitlines()
            step = max(1, chunk_lines - overlap)
            for start in range(0, max(1, len(lines)), step):
                chunk = "\n".join(lines[start : start + chunk_lines])
                if not chunk.strip():
                    continue
                symbols = re.findall(
                    r"(?:class|fun|function|def|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
                    chunk,
                )
                self.add_text(
                    f"FILE {relative}\n{chunk}",
                    {
                        "kind": "code",
                        "path": relative,
                        "absolute_path": str(path),
                        "file_mtime": stat.st_mtime,
                        "line_start": start + 1,
                        "symbols": symbols[:12],
                        "language": path.suffix.lower().lstrip("."),
                    },
                    persist=False,
                )
                added += 1
        if added:
            with self._lock:
                self._save_locked()
        self._log(f"Codebase indexed: +{added} chunk(s), total={self.count}", next_stage=FAISS)
        return added

    def find_code_candidates(
        self, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """FAISS Match step: files most likely to own the diagnosed component."""
        return self.search(query, top_k=top_k, kind="code")

    # ------------------------------------------------------------ persistence
    def _save_locked(self) -> None:
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                prefix=".memory-", suffix=".tmp", dir=str(self.index_path.parent)
            )
            os.close(fd)
            try:
                faiss.write_index(self._index, tmp)
                os.replace(tmp, self.index_path)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
            payload = {
                "version": 1,
                "next_id": self._next_id,
                "entries": {str(k): v for k, v in self._metadata.items()},
            }
            meta_fd, meta_tmp = tempfile.mkstemp(
                prefix=".meta-", suffix=".tmp", dir=str(self.index_path.parent)
            )
            os.close(meta_fd)
            try:
                Path(meta_tmp).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                os.replace(meta_tmp, self.metadata_path)
            finally:
                if os.path.exists(meta_tmp):
                    os.remove(meta_tmp)
        except Exception as exc:
            self._log(f"Persist failed: {type(exc).__name__}: {exc}", level="ERROR")

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        try:
            loaded = faiss.read_index(str(self.index_path))
            if int(loaded.d) != DIMENSION:
                self._log("Existing index has another dimension; starting fresh.", level="WARN")
                return
            self._index = loaded
            if self.metadata_path.exists():
                payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
                self._metadata = {
                    int(k): dict(v) for k, v in entries.items() if isinstance(v, Mapping)
                }
                self._next_id = max(
                    int(payload.get("next_id", 1)), max(self._metadata, default=0) + 1
                )
            self._log(f"Loaded {self.count} memor(ies) from disk.")
        except Exception as exc:
            self._log(f"Load failed ({exc}); starting with empty memory.", level="WARN")
