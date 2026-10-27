"""Persistent Meta FAISS long-term vector memory for Orunex.

The module deliberately keeps the storage layer independent from the UI and
from any particular embedding model:

* :meth:`MetaFAISSMemory.add_memory` accepts a pre-computed vector and metadata.
* :meth:`MetaFAISSMemory.search_context` accepts a pre-computed query vector.
* :meth:`MetaFAISSMemory.add_text` / :meth:`search_text` are convenience
  wrappers that use an optional embedding provider.  When no provider is
  available, a small deterministic hashing embedder is used.  This keeps the
  memory operational on machines where the local Llama/Ollama embedding model
  has not been installed yet.  A real embedding backend can be injected at any
  time with ``get_memory(embedding_provider=...)`` or
  ``MetaFAISSMemory.set_embedding_provider(...)``; vectors must use the same
  dimension as the existing index.

Persistence
-----------
The FAISS index is written atomically to ``memory.index`` in the project root
(or to ``ORUNEX_MEMORY_INDEX``).  The text metadata is kept in the sidecar
``memory.index.meta.json``.  FAISS only stores vectors and integer IDs; the
sidecar is what lets the agent recover the task/result context later.

Thread safety
-------------
FAISS objects are not safe for concurrent mutation.  Every access to the index,
the metadata map and the on-disk files is serialised by one ``RLock`` per
``MetaFAISSMemory`` instance.  Embedding calls happen outside that lock, so a
slow model does not block searches.  The module-level singleton in
:func:`get_memory` has its own creation lock.  This is important because Orunex
runs agent work, swarm workers and UI callbacks in different threads.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np

try:
    import faiss  # type: ignore
except Exception as exc:  # pragma: no cover - exercised only when not installed
    faiss = None  # type: ignore
    _FAISS_IMPORT_ERROR: Optional[Exception] = exc
else:
    _FAISS_IMPORT_ERROR = None


# ``src/_orunex_libs/faiss_memory.py`` -> two levels up is the project root.
if getattr(sys, "frozen", False):
    # A bundled app must not write inside PyInstaller's temporary _MEIPASS.
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_INDEX_PATH = os.path.join(BASE_DIR, "memory.index")
DEFAULT_METADATA_PATH = DEFAULT_INDEX_PATH + ".meta.json"
DEFAULT_EMBEDDING_DIMENSION = 384
MEMORY_FORMAT_VERSION = 1

EmbeddingProvider = Callable[[str], Sequence[float]]

_MEMORY_INSTANCE: Optional["MetaFAISSMemory"] = None
_MEMORY_INSTANCE_LOCK = threading.Lock()

_WORD_RE = re.compile(r"[a-z0-9_+#.-]+", re.UNICODE)
_LOW_SIGNAL_TASKS = {
    "hola",
    "hi",
    "hello",
    "hey",
    "buenas",
    "buenos dias",
    "good morning",
    "test",
    "ping",
    "thanks",
    "gracias",
}


def _json_safe(value: Any) -> Any:
    """Convert common Python/NumPy values into JSON-serialisable objects."""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalise_text(text: str) -> str:
    """Lowercase and strip accents so the fallback is deterministic."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower()


def _bucket(feature: str, dimension: int) -> tuple[int, float]:
    """Return a stable bucket and sign for one textual feature."""
    digest = hashlib.blake2b(
        feature.encode("utf-8", "ignore"), digest_size=8
    ).digest()
    value = int.from_bytes(digest, "little")
    index = value % dimension
    sign = 1.0 if (value >> 63) & 1 else -1.0
    return index, sign


def local_hash_embedding(
    text: str,
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
) -> np.ndarray:
    """Create a low-latency deterministic embedding without a model.

    This is a feature-hashing vectorizer over words, word bigrams and character
    trigrams.  It is intentionally a *fallback*: it provides useful lexical
    recall and keeps FAISS available when no transformer embedding backend is
    installed.  If an embedding model/provider is configured, it is used
    instead (see :class:`MetaFAISSMemory`).
    """
    dimension = max(1, int(dimension or DEFAULT_EMBEDDING_DIMENSION))
    vector = np.zeros(dimension, dtype=np.float32)
    normalised = _normalise_text(text)

    words = _WORD_RE.findall(normalised)
    if not words and normalised:
        words = [normalised]

    counts: Dict[str, float] = {}

    def add_feature(feature: str, weight: float) -> None:
        counts[feature] = counts.get(feature, 0.0) + weight

    for word in words:
        add_feature("w:" + word, 1.0)

    for left, right in zip(words, words[1:]):
        add_feature("b:" + left + " " + right, 0.6)

    compact = re.sub(r"\s+", " ", normalised).strip()
    for index in range(max(0, len(compact) - 2)):
        add_feature("c:" + compact[index:index + 3], 0.25)

    for feature, weight in counts.items():
        bucket, sign = _bucket(feature, dimension)
        # Sub-linear term frequency, like a lightweight TF representation.
        vector[bucket] += sign * (1.0 + np.log1p(weight))

    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        # An empty/very unusual string still receives a stable non-zero vector.
        bucket, sign = _bucket("empty:" + normalised, dimension)
        vector[bucket] = sign
        norm = 1.0

    vector /= norm
    return np.ascontiguousarray(vector, dtype=np.float32)


def _as_normalised_vector(vector: Any) -> np.ndarray:
    """Validate and L2-normalise a single vector to shape ``(1, d)``."""
    try:
        array = np.asarray(vector, dtype=np.float32)
    except Exception as exc:
        raise ValueError("The vector must be numeric.") from exc

    if array.ndim == 1:
        array = array.reshape(1, -1)
    elif array.ndim == 2 and array.shape[0] == 1:
        pass
    else:
        raise ValueError(
            "Expected a 1-D vector or an array with shape (1, dimension)."
        )

    if array.size == 0 or array.shape[1] == 0:
        raise ValueError("The vector cannot be empty.")
    if not np.all(np.isfinite(array)):
        raise ValueError("The vector contains NaN or infinite values.")

    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise ValueError("The vector cannot have zero length.")

    array = array / norms
    return np.ascontiguousarray(array, dtype=np.float32)


class MetaFAISSMemory:
    """A thread-safe, persistent FAISS cosine-similarity memory.

    Parameters
    ----------
    index_path:
        Path of the FAISS file.  Defaults to ``memory.index`` in the project
        root.  The metadata sidecar is stored next to it.
    metadata_path:
        Optional override for the JSON sidecar path.
    dimension:
        Optional fixed vector dimension.  When omitted, the dimension is
        learned from the first vector or from the loaded index.
    embedding_provider:
        Optional callable ``text -> vector`` used by :meth:`add_text` and
        :meth:`search_text`.  The vector must have the same dimension as the
        index.  When it fails or is absent, the deterministic local fallback is
        used.

    Notes
    -----
    Vectors are normalised and stored in ``IndexIDMap2(IndexFlatIP(d))``.
    Inner product on L2-normalised vectors is cosine similarity.
    """

    def __init__(
        self,
        index_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        dimension: int = 0,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        if faiss is None:
            raise RuntimeError(
                "FAISS is not installed. Install it with "
                "`pip install faiss-cpu` and restart Orunex."
            ) from _FAISS_IMPORT_ERROR

        self.index_path = os.path.abspath(
            os.path.expanduser(index_path or os.environ.get("ORUNEX_MEMORY_INDEX", DEFAULT_INDEX_PATH))
        )
        self.metadata_path = os.path.abspath(
            os.path.expanduser(
                metadata_path
                or os.environ.get("ORUNEX_MEMORY_META", "")
                or (self.index_path + ".meta.json")
            )
        )
        self._lock = threading.RLock()
        self._embedding_provider = embedding_provider
        self._index: Optional[Any] = None
        self._metadata: Dict[int, Dict[str, Any]] = {}
        self._dimension = max(0, int(dimension or 0))
        self._next_id = 1
        self._last_error: Optional[str] = None
        self._load_locked(silent=True)

    # ------------------------------------------------------------------
    # Basic state
    # ------------------------------------------------------------------
    @property
    def index(self) -> Optional[Any]:
        """The underlying FAISS index (read-only use is not thread-safe)."""
        return self._index

    @property
    def dimension(self) -> int:
        with self._lock:
            return int(self._dimension)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._metadata)

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def __len__(self) -> int:
        return self.count

    def set_embedding_provider(
        self, provider: Optional[EmbeddingProvider]
    ) -> None:
        """Install or remove the optional text embedding provider."""
        with self._lock:
            self._embedding_provider = provider

    # ------------------------------------------------------------------
    # Core vector API required by the Orunex memory contract
    # ------------------------------------------------------------------
    def add_memory(
        self,
        vector: Any,
        metadata: Optional[Mapping[str, Any]] = None,
        *,
        persist: bool = True,
    ) -> int:
        """Store one vector and its contextual metadata.

        Parameters
        ----------
        vector:
            A 1-D sequence/array or a ``(1, dimension)`` array.
        metadata:
            JSON-friendly mapping.  The text field is normally stored under
            ``"text"``; :meth:`add_text` does this automatically.
        persist:
            Write ``memory.index`` and its sidecar immediately.  Keep it True
            for the normal single-memory path.  Batch importers may pass False
            and call :meth:`save` once at the end.

        Returns
        -------
        int
            Stable FAISS ID assigned to the memory.
        """
        prepared = _as_normalised_vector(vector)

        with self._lock:
            if self._index is None:
                vector_dimension = int(prepared.shape[1])
                if self._dimension and vector_dimension != self._dimension:
                    raise ValueError(
                        f"Vector dimension {vector_dimension} does not match "
                        f"the configured dimension {self._dimension}."
                    )
                self._dimension = vector_dimension
                self._index = self._new_index(vector_dimension)
            elif prepared.shape[1] != self._dimension:
                raise ValueError(
                    f"Vector dimension {prepared.shape[1]} does not match "
                    f"the memory dimension {self._dimension}."
                )

            memory_id = int(self._next_id)
            ids = np.asarray([memory_id], dtype=np.int64)
            self._index.add_with_ids(prepared, ids)

            if isinstance(metadata, str):
                raw_metadata: Any = {"text": metadata}
            elif isinstance(metadata, Mapping):
                raw_metadata = dict(metadata)
            else:
                raw_metadata = {"value": metadata} if metadata is not None else {}

            safe_metadata = dict(_json_safe(raw_metadata))
            safe_metadata.setdefault("created_at", time.time())
            safe_metadata["id"] = memory_id
            self._metadata[memory_id] = safe_metadata
            self._next_id += 1

            if persist:
                self._save_locked()
            return memory_id

    def search_context(
        self,
        query_vector: Any,
        top_k: int = 3,
        *,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return the most similar memories for a query vector.

        The result is a list of dictionaries with ``id``, ``score``, ``text``
        and the complete ``metadata`` mapping.  Similarity is cosine
        similarity, because all vectors are L2-normalised.
        """
        prepared = _as_normalised_vector(query_vector)
        try:
            k = max(1, int(top_k))
        except (TypeError, ValueError):
            k = 3
        threshold = float(min_score)

        with self._lock:
            if self._index is None or self._index.ntotal <= 0:
                return []
            if prepared.shape[1] != self._dimension:
                raise ValueError(
                    f"Query dimension {prepared.shape[1]} does not match "
                    f"the memory dimension {self._dimension}."
                )

            k = min(k, int(self._index.ntotal))
            scores, ids = self._index.search(prepared, k)

            results: List[Dict[str, Any]] = []
            for score, memory_id in zip(scores[0], ids[0]):
                memory_id = int(memory_id)
                if memory_id < 0:
                    continue
                similarity = float(score)
                if similarity < threshold:
                    continue
                metadata = copy.deepcopy(self._metadata.get(memory_id, {}))
                text = (
                    metadata.get("text")
                    or metadata.get("content")
                    or metadata.get("task")
                    or ""
                )
                results.append(
                    {
                        "id": memory_id,
                        "score": similarity,
                        "text": str(text),
                        "context": str(text),
                        "metadata": metadata,
                    }
                )
            return results

    # ------------------------------------------------------------------
    # Text convenience API used by Orunex
    # ------------------------------------------------------------------
    def add_text(
        self,
        text: str,
        metadata: Optional[Mapping[str, Any]] = None,
        *,
        persist: bool = True,
    ) -> int:
        """Embed and store a text memory."""
        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("Cannot store an empty memory.")

        vector = self._embed_text(clean_text)
        if isinstance(metadata, str):
            enriched: Dict[str, Any] = {"note": metadata}
        elif isinstance(metadata, Mapping):
            enriched = dict(metadata)
        else:
            enriched = {}
        enriched.setdefault("text", clean_text)
        return self.add_memory(vector, enriched, persist=persist)

    def search_text(
        self,
        query: str,
        top_k: int = 3,
        *,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Embed a text query and return matching memories."""
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        return self.search_context(
            self._embed_text(clean_query), top_k=top_k, min_score=min_score
        )

    def remember(
        self,
        text: str,
        metadata: Optional[Mapping[str, Any]] = None,
        *,
        persist: bool = True,
    ) -> int:
        """Alias for :meth:`add_text` for readable call sites."""
        return self.add_text(text, metadata, persist=persist)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self) -> bool:
        """Atomically write the FAISS index and its metadata sidecar."""
        with self._lock:
            return self._save_locked()

    def save_index(self) -> bool:
        """Explicit alias for :meth:`save`."""
        return self.save()

    def load(self) -> bool:
        """Reload the index and metadata from disk."""
        with self._lock:
            return self._load_locked(silent=False)

    def load_index(self) -> bool:
        """Explicit alias for :meth:`load`."""
        return self.load()

    def clear(self, *, persist: bool = True) -> bool:
        """Remove all memories.  Useful for tests and explicit resets."""
        with self._lock:
            if self._index is not None:
                self._index.reset()
            self._metadata.clear()
            self._next_id = 1
            self._last_error = None
            if persist:
                return self._save_locked()
            return True

    def _new_index(self, dimension: int) -> Any:
        base = faiss.IndexFlatIP(int(dimension))
        return faiss.IndexIDMap2(base)

    def _save_locked(self) -> bool:
        if self._index is None:
            return False

        index_dir = os.path.dirname(self.index_path) or BASE_DIR
        metadata_dir = os.path.dirname(self.metadata_path) or BASE_DIR
        try:
            os.makedirs(index_dir, exist_ok=True)
            os.makedirs(metadata_dir, exist_ok=True)

            index_fd, index_tmp = tempfile.mkstemp(
                prefix=".memory-", suffix=".index.tmp", dir=index_dir
            )
            os.close(index_fd)
            try:
                faiss.write_index(self._index, index_tmp)
                os.replace(index_tmp, self.index_path)
            finally:
                if os.path.exists(index_tmp):
                    os.remove(index_tmp)

            payload = {
                "version": MEMORY_FORMAT_VERSION,
                "dimension": int(self._dimension),
                "next_id": int(self._next_id),
                "entries": {
                    str(memory_id): metadata
                    for memory_id, metadata in self._metadata.items()
                },
            }
            meta_fd, meta_tmp = tempfile.mkstemp(
                prefix=".memory-", suffix=".meta.tmp", dir=metadata_dir
            )
            os.close(meta_fd)
            try:
                with open(meta_tmp, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(meta_tmp, self.metadata_path)
            finally:
                if os.path.exists(meta_tmp):
                    os.remove(meta_tmp)

            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            print(f"[FAISS] Could not persist memory: {self._last_error}")
            return False

    def _load_locked(self, *, silent: bool) -> bool:
        if not os.path.exists(self.index_path):
            return False

        try:
            loaded_index = faiss.read_index(self.index_path)
            if loaded_index.d <= 0:
                raise ValueError("The FAISS index has an invalid dimension.")

            metadata: Dict[int, Dict[str, Any]] = {}
            stored_next_id = 1
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
                if isinstance(entries, Mapping):
                    for raw_id, raw_metadata in entries.items():
                        try:
                            memory_id = int(raw_id)
                        except (TypeError, ValueError):
                            continue
                        if isinstance(raw_metadata, Mapping):
                            metadata[memory_id] = dict(_json_safe(raw_metadata))
                try:
                    stored_next_id = max(1, int(payload.get("next_id", 1)))
                except (TypeError, ValueError, AttributeError):
                    stored_next_id = 1

            self._index = loaded_index
            self._dimension = int(loaded_index.d)
            self._metadata = metadata
            self._next_id = max(
                stored_next_id,
                max(metadata.keys(), default=0) + 1,
            )
            self._last_error = None
            return True
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            if not silent:
                print(f"[FAISS] Could not load memory: {self._last_error}")
            return False

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def _embed_text(self, text: str) -> np.ndarray:
        provider = self._embedding_provider
        if provider is not None:
            try:
                candidate = provider(text)
                candidate_vector = _as_normalised_vector(candidate)
                if (
                    not self._dimension
                    or candidate_vector.shape[1] == self._dimension
                ):
                    return candidate_vector[0]
                self._last_error = (
                    "Embedding provider returned dimension "
                    f"{candidate_vector.shape[1]}, expected {self._dimension}; "
                    "using the local fallback."
                )
            except Exception as exc:
                self._last_error = (
                    f"Embedding provider failed ({type(exc).__name__}: {exc}); "
                    "using the local fallback."
                )

        dimension = self._dimension or DEFAULT_EMBEDDING_DIMENSION
        return local_hash_embedding(text, dimension)


# ----------------------------------------------------------------------
# Thread-safe singleton and small Orunex integration helpers
# ----------------------------------------------------------------------
def get_memory(
    index_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
    dimension: int = 0,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> MetaFAISSMemory:
    """Return the process-wide memory instance, creating it under a lock."""
    global _MEMORY_INSTANCE
    with _MEMORY_INSTANCE_LOCK:
        if _MEMORY_INSTANCE is None:
            _MEMORY_INSTANCE = MetaFAISSMemory(
                index_path=index_path,
                metadata_path=metadata_path,
                dimension=dimension,
                embedding_provider=embedding_provider,
            )
        return _MEMORY_INSTANCE


def search_memory(
    query: str,
    top_k: int = 3,
    *,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """Recall from the shared memory without ever raising into the agent."""
    try:
        return get_memory().search_text(query, top_k=top_k, min_score=min_score)
    except Exception as exc:
        print(f"[FAISS] Memory recall skipped: {type(exc).__name__}: {exc}")
        return []


def remember_text(
    text: str,
    metadata: Optional[Mapping[str, Any]] = None,
    *,
    persist: bool = True,
) -> Optional[int]:
    """Store a text memory in the shared index, returning its ID on success."""
    try:
        return get_memory().add_text(text, metadata, persist=persist)
    except Exception as exc:
        print(f"[FAISS] Memory write skipped: {type(exc).__name__}: {exc}")
        return None


def remember_task(agent_name: str, task: str, result: str) -> Optional[int]:
    """Store a completed agent task as one long-term memory entry."""
    task_text = str(task or "").strip()
    result_text = str(result or "").strip()
    if not task_text and not result_text:
        return None
    if _normalise_text(task_text).strip(" .!?¡¿,") in _LOW_SIGNAL_TASKS:
        return None

    text = f"Task: {task_text}\nOutcome: {result_text}"
    metadata = {
        "type": "task_outcome",
        "agent": str(agent_name or "Cerebro"),
        "task": task_text[:2000],
        "result": result_text[:6000],
        "created_at": time.time(),
    }
    return remember_text(text, metadata)


def remember_task_async(agent_name: str, task: str, result: str) -> threading.Thread:
    """Record a task without blocking the UI/agent worker thread."""
    worker = threading.Thread(
        target=remember_task,
        args=(agent_name, task, result),
        name="OrunexFAISSMemory",
        daemon=True,
    )
    worker.start()
    return worker


def format_context(
    results: Sequence[Mapping[str, Any]],
    max_chars: int = 1800,
) -> str:
    """Format FAISS search results as a prompt-safe context block."""
    lines: List[str] = []
    used = 0
    for item in results:
        metadata = item.get("metadata", {}) if isinstance(item, Mapping) else {}
        if not isinstance(metadata, Mapping):
            metadata = {}

        task_text = str(metadata.get("task") or "").strip()
        result_text = str(
            metadata.get("result") or metadata.get("content") or ""
        ).strip()
        memory_text = str(item.get("text") or "").strip()
        if not task_text and not result_text and not memory_text:
            continue

        if task_text:
            line = f"- Task: {task_text[:260]}"
            if result_text:
                line += f"\n  Outcome: {result_text[:460]}"
        else:
            line = f"- Memory: {memory_text[:420]}"
        if not line:
            continue

        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)

    if not lines:
        return ""
    return (
        "[LONG-TERM VECTOR MEMORY - RECALLED FROM FAISS - REFERENCE ONLY]\n"
        + "\n".join(lines)
        + "\n"
    )
