# Orunex

**Autonomous Desktop Agent · Live Multimodal Runtime · Simplex Remote Control · Android Companion · Blockchain Markdown Platform**

**BMD Engine v2.1.0** · **Meta Muse reasoning** · **Windows desktop + Android**

> *One agent. One desktop. One cryptographically verifiable record.*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Platform at a Glance](#2-platform-at-a-glance)
3. [System Architecture](#3-system-architecture)
4. [Desktop Application](#4-desktop-application)
5. [The Agent Runtime](#5-the-agent-runtime)
6. [Live Mode](#6-live-mode)
7. [Memory and Knowledge](#7-memory-and-knowledge)
8. [Connections and Integrations](#8-connections-and-integrations)
9. [Paper Trading](#9-paper-trading)
10. [Android Companion](#10-android-companion)
11. [Blockchain Markdown: Complete Manual](#11-blockchain-markdown-complete-manual)
12. [BMD Inside Orunex](#12-bmd-inside-orunex)
13. [Configuration](#13-configuration)
14. [Installation and Launch](#14-installation-and-launch)
15. [Repository Map](#15-repository-map)
16. [Example Use Cases](#16-example-use-cases)
17. [Verification and Test Coverage](#17-verification-and-test-coverage)
18. [Security Model and Operational Guarantees](#18-security-model-and-operational-guarantees)
19. [Summary: The Agent and Blockchain Markdown](#19-summary-the-agent-and-blockchain-markdown)
20. [Appendix: Complete Inventory of Additions](#20-appendix-complete-inventory-of-additions)

---

## 1. Executive Summary

Orunex is a Windows desktop agent that turns natural language, voice, screen context, and remote messages into verified work on a real computer. It combines five capabilities in one product:

1. **A desktop agent** that reasons with Meta Muse, executes through deterministic local subsystems, and reports every result as a concrete artifact.
2. **Live mode**, a multimodal loop that observes the screen, listens through the microphone, speaks with a neural voice, and routes short commands without a model round-trip.
3. **Simplex Bridge**, an end-to-end encrypted remote channel that lets a paired phone command the desktop agent, receive progress, and approve results.
4. **An Android companion** built as a native WebView application with chat history, modes, local artifacts, settings, and a Simplex pairing surface.
5. **Blockchain Markdown (BMD) v2.1.0**, a complete cryptographic document platform with a zero-dependency C11 engine, Ed25519 signatures, SHA-512 ledger hashes, an in-terminal Redact Studio, and a full CLI.

The design principle is simple: **Muse reasons; deterministic systems execute; FAISS remembers; BMD provides custody.** The language model is never asked to perform arithmetic that a risk gate can enforce, never asked to type a signature that a device key can produce, and never asked to invent a file path that the filesystem can verify.

Orunex is built for demonstrable, inspectable work. A request becomes a plan, the plan becomes a sequence of bounded actions, and the actions produce files, screenshots, ledger entries, paper orders, or spoken confirmations. Every important operation has a deterministic path that remains available even when the reasoning model is slow or offline.

### 1.1 What Makes Orunex Distinct

| Pillar | Implementation |
|:---|:---|
| **Reasoning** | Meta Muse Wonder for long-horizon work; Meta Muse Spark for routing, extraction, and screen vision. No other LLM provider is accepted. |
| **Execution** | Deterministic command router, BMD expert, Artifact Studio, VS Code bridge, OS executor, and a bounded agent tool loop. |
| **Perception** | Live screen capture with change detection, Meta vision, microphone ASR, and a neural TTS voice with local fallback. |
| **Memory** | Persistent 384-dimensional FAISS index with `code`, `strategy`, `episode`, and BMD knowledge namespaces. |
| **Remote control** | Simplex WebSocket bridge with contact allowlisting, duplicate suppression, a kill switch, and structured confirmations. |
| **Trading** | TradingView-native paper execution with deterministic risk gates, explicit-order retries, and mandatory GUI verification. |
| **Documents** | PDF, Word, Excel, PowerPoint, CSV, Markdown, HTML, and Blockchain Markdown artifacts generated from natural language. |
| **Custody** | BMD v2.1.0: draft/transfer state machine, device-anchored Ed25519 signatures, SHA-512 hashes, read-only sealing, and chained ledger audits. |
| **Companion** | Android app `com.orunex.mobile`, minSdk 26, targetSdk 36, with local chat history, modes, artifacts, and Simplex UI. |

### 1.2 Documentation Map

| Document | Purpose |
|:---|:---|
| **README.md** (this document) | Definitive English overview of Orunex, the agent, Live mode, integrations, paper trading, Android, and the complete BMD manual. |
| [BMD manual.md](BMD%20manual.md) | Authoritative long-form BMD specification and CLI reference. This README integrates its full operational content and points here for deeper study. |
| [docs/HACKATHON_ARCHITECTURE.md](docs/HACKATHON_ARCHITECTURE.md) | Architecture notes for the hackathon build. |
| [docs/SIMPLEX_INTEGRACION_SEGURA.md](docs/SIMPLEX_INTEGRACION_SEGURA.md) | Security design notes for the Simplex integration. |
| [.env.example](.env.example) | Complete environment-variable reference with safe defaults. |
| [bmd_engine/README.md](bmd_engine/README.md) | Engine build notes. The lifecycle described in this README and in `BMD manual.md` is the authoritative v2.1.0 behavior. |
| [android/](android/) | Gradle project for the Android companion. |

---

## 2. Platform at a Glance

### 2.1 Product Surfaces

| Surface | Entry Point | Primary Use |
|:---|:---|:---|
| **Desktop application** | `Lanzar_Orunex_Windows.vbs` or `pythonw.exe src\main.py` | Chat, Live mode, Simplex pairing, settings, saved memory, artifacts. |
| **Headless agent** | `python app.py` | Diagnostics, codebase indexing, paper demo, warm-up, remote-order rehearsal. |
| **Simplex remote** | Paired Simplex contact | Remote commands, status, notifications, screenshots, paper orders. |
| **Android companion** | `android/app/build/outputs/apk/debug/app-debug.apk` | Mobile chat, modes, artifacts, settings, Simplex pairing. |
| **BMD CLI** | `bmd` / `bmd_engine\bin\bmd_cli.exe` | Draft, sign, compile, co-sign, verify, inspect, render, audit, property injection. |
| **BMD Redact Studio** | `bmd redact` | In-terminal drafting, preview, signing, compiling, IP injection. |

### 2.2 Core Runtime Stack

| Layer | Technology | Responsibility |
|:---|:---|:---|
| Desktop UI | Python 3.12, CustomTkinter, Pillow | Native Windows shell, animated composer, Live control, settings, chat history. |
| Reasoning | Meta Muse API (OpenAI-compatible) | Text, vision, JSON decisions, routing, synthesis, trading analysis. |
| Orchestration | `core/agent_brain.py` | Bounded thread pool, task submission, status, diagnostics, Simplex routing. |
| Memory | FAISS `IndexIDMap2` + `IndexFlatIP` | 384-dimensional cosine recall over code, strategies, episodes, and BMD knowledge. |
| Transport | WebSocket, HTTP, ADB, VS Code bridge | Simplex, Meta API, Android device control, editor automation. |
| Desktop automation | PyAutoGUI, MSS, Win32/UIA, virtual input | Screenshots, clicks, typing, window control, native application driving. |
| Documents | fpdf2, python-docx, openpyxl, python-pptx | Real PDF, DOCX, XLSX, PPTX, CSV, Markdown, and HTML output. |
| Custody | C11 BMD engine + Ed25519 + SHA-512 + ChaCha20 | Immutable documents, signatures, ledger audits, encrypted IP bundles. |
| Android | Java 17, WebView, Gradle 8.13.2 | Native shell around a self-contained HTML/CSS/JS application. |

### 2.3 Design Invariants

1. **Meta Muse is the only reasoning engine.** FAISS stores vectors; bridges transport bytes; risk gates enforce arithmetic; only Muse makes semantic decisions.
2. **Paper trading only.** `paper_trading_only` is a hard, non-configurable invariant. There is no broker integration and no real-funds code path.
3. **TradingView native execution.** Paper orders are placed through the native TradingView desktop ticket, not a broker API.
4. **BMD custody is cryptographic.** Signatures are derived from device identity keys; users never type a signature.
5. **Deterministic paths come first.** Greetings, screen questions, direct commands, BMD orders, and artifact requests are handled before the general reasoning path.
6. **The desktop shortcut always opens maximized.** The launcher and the application both enforce a maximized window.
7. **The `.bmd` file is the canonical record.** HTML, terminal, and Office representations are presentation layers only.

---

## 3. System Architecture

### 3.1 High-Level Topology

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            USER SURFACES                                     │
│  Desktop Chat · Live Voice/Screen · Simplex Phone · Android Companion        │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                                   │
│  src/main.py                                                                 │
│  Chat workspace · Composer · Live button · Simplex page · Settings · Memory  │
│  CustomTkinter · animated gradient composer · activity log · artifact cards  │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC ROUTING LAYER                               │
│  1. Instant greetings                                                        │
│  2. Screen questions (fresh capture + vision)                                │
│  3. Complex-task delegation (Android repair, TradingView analysis/execution) │
│  4. Direct desktop commands (open app, open URL, browser selection)          │
│  5. BMD expert (real CLI/FFI operations)                                     │
│  6. Artifact Studio (real document files)                                    │
│  7. VS Code / Programmer path                                                │
│  8. Cerebro + Supervisor (Muse reasoning)                                    │
│  9. OS executor tags                                                         │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌───────────────────┐   ┌───────────────────────┐   ┌──────────────────────────┐
│   META MUSE       │   │   FAISS MEMORY        │   │   BRIDGES                │
│   Wonder (deep)   │   │   384-d cosine        │   │   Simplex WebSocket      │
│   Spark (fast)    │   │   code / strategy /   │   │   ADB / Android          │
│   Vision          │   │   episode / BMD       │   │   VS Code                │
│   JSON decisions  │   │   persistent index    │   │   TradingView            │
└─────────┬─────────┘   └───────────┬───────────┘   └────────────┬─────────────┘
          │                         │                            │
          └─────────────────────────┼────────────────────────────┘
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                                      │
│  OS executor · virtual input · screenshots · Chrome · Office · BMD engine    │
│  TradingView GUI agent · Android repair · VS Code patches · artifacts        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Responsibilities

| Component | File | Responsibility |
|:---|:---|:---|
| Desktop shell | `src/main.py` | Window, splash, sidebar, chat, composer, Live, Simplex page, settings, memory manager, artifact cards, delegation watcher. |
| Orchestrator | `core/agent_brain.py` | Owns bridges, memory, tasks; bounded `ThreadPoolExecutor`; remote command routing; status and diagnostics. |
| Meta client | `core/meta_api.py` | OpenAI-compatible text/vision/JSON client; model policy; retry on truncated responses; fenced-JSON extraction. |
| FAISS memory | `core/faiss_memory.py` | 384-d deterministic embeddings, persistent index, codebase chunking, namespace recall. |
| Trading intent | `core/trade_intent.py` | Detects explicit natural-language paper orders and symbols. |
| Task base | `tasks/base.py` | Task state machine, result object, event emission. |
| Android repair | `tasks/bugfix_task.py` | Screencap → Muse diagnosis → FAISS file match → guarded patch → rebuild/install → visual verification. |
| Paper trading | `tasks/trading_task.py` | Alert parsing, strategy recall, Muse decision, risk gate, paper engine, duplicate guard, GUI handoff. |
| TradingView GUI | `tasks/tradingview_gui.py` | Bounded vision/action loop over the native paper ticket; paper-panel verification; normalized coordinates. |
| ADB bridge | `bridges/adb_bridge.py` | Device discovery, emulator start, screencap, install, restart, shell. |
| Simplex bridge | `bridges/simplex_bridge.py` | WebSocket listener on `ws://127.0.0.1:5227`; normalizes `newChatItems` into `RemoteCommand`. |
| TradingView bridge | `bridges/tradingview_bridge.py` | Launches TradingView, opens symbols, captures charts. |
| VS Code bridge | `bridges/vscode_bridge.py` | Guarded file writes, diffs, backups, terminal commands, tests, diagnostics. |
| Mode router | `src/_orunex_libs/mode_router.py` | Default / Programmer / Deep Research / Agent Swapping detection and prompts. |
| BMD expert | `src/_orunex_libs/bmd_expert.py` | Real CLI/FFI BMD operations, natural-language intents, `[BMD: ...]` tags, draft creation, clause library. |
| BMD knowledge | `src/_orunex_libs/bmd_knowledge.py` | 21-entry verified BMD knowledge pack, versioned and synchronized to FAISS. |
| Artifact Studio | `src/_orunex_libs/artifact_studio.py` | Detects explicit file requests and writes real PDF/DOCX/XLSX/PPTX/CSV/MD/HTML files. |
| Office expert | `src/_orunex_libs/office_expert.py` | Research-backed Office plans, native charts, styled decks, workbooks, documents, PDFs. |
| OS executor | `src/_orunex_libs/os_executor.py` | Parses and executes `[GUI_*]`, `[MAKE_DOC]`, `[HEADLESS_SEARCH]`, `[BMD]`, `[VSCODE]`, and related tags. |
| Agent loop | `src/_orunex_libs/agentic_loop.py` | Sandboxed tool loop with bounded calls, steps, and wall-clock budget. |
| Tool registry | `src/_orunex_libs/agent_tools.py` | Allow-listed tools; no generated Python or shell execution. |
| Live vision | `src/_orunex_libs/live_vision.py` | 1.5 s capture loop, local change detection, Meta vision adapter. |
| Live audio | `src/_orunex_libs/live_audio.py` | 16 kHz microphone capture, silence gating, Meta ASR transcription. |
| Live TTS | `src/_orunex_libs/live_tts.py` | Edge neural voice, sentence chunking, SAPI fallback, hard stop. |
| Simplex production bridge | `src/_orunex_libs/simplex_bridge.py` | Pairing, notifications, heartbeat, status, command handling. |
| Auto-healer | `src/_orunex_libs/auto_healer.py` | Deterministic fast repair layer followed by Muse correction. |
| Knowledge processor | `src/_orunex_libs/knowledge_processor.py` | JSON/PDF ingestion into the local knowledge base. |
| Android shell | `android/app/src/main/java/com/orunex/mobile/MainActivity.java` | WebView, SharedPreferences, file chooser, artifact downloads, back handling. |
| Android UI | `android/app/src/main/assets/app.js` | Chat, history, modes, artifacts, settings, Simplex pairing UI. |

### 3.3 Request Lifecycle

Every desktop request follows a deterministic ladder. The order is deliberate: cheap, local, and verifiable operations complete before the model is asked to reason.

```text
User input
   │
   ├─ 1. Instant greeting?  → local cached reply, spoken immediately
   │
   ├─ 2. Screen question?   → fresh capture → Meta vision → answer
   │
   ├─ 3. Complex task?      → delegation to headless agent
   │       ├─ Android repair  → `!fix ...`
   │       └─ TradingView     → `!trade ...` / analysis
   │
   ├─ 4. Direct command?    → open app, open URL, choose browser, clarify
   │
   ├─ 5. BMD order?         → real CLI/FFI operation → artifact card
   │
   ├─ 6. Artifact order?    → real file in Artifact Studio → artifact card
   │
   ├─ 7. Programmer?        → VS Code bridge → files, tests, terminal
   │
   ├─ 8. Muse reasoning     → Cerebro → Supervisor → OS executor tags
   │
   └─ 9. Report             → chat bubble, activity log, artifact card, speech
```

The ladder is not a hard gate for the user. A selected mode is a preference hint; the router still chooses the most useful execution path. What matters is that the same request always reaches the same deterministic subsystem before the model is consulted.

### 3.4 Concurrency Model

| Mechanism | Behavior |
|:---|:---|
| UI thread | CustomTkinter event loop; never blocked by network or task work. |
| Agent pool | `ThreadPoolExecutor(max_workers=4, thread_name_prefix="AgentWorker")`. |
| Warm-up pool | A separate two-worker pool for emulator and TradingView preparation. |
| Task futures | Every submission returns a `Future`; `wait_for_idle` and `completed_summaries` provide deterministic completion. |
| Event bus | `core/events.py` publishes structured events for the UI, logs, and console. |
| Live capture thread | Dedicated screen loop with change detection; the vision call happens outside the capture thread. |
| Live audio thread | Dedicated 16 kHz capture and ASR worker; a watchdog restarts the microphone if it stops. |
| Delegation watcher | Background thread tails the headless agent log and relays the final result into chat and speech. |
| Trading GUI thread | Bounded recursive vision/action loop with a hard step and time budget. |

### 3.5 Muse Model Policy

| Role | Default Model | Configuration | Use |
|:---|:---|:---|:---|
| Primary reasoning | `muse-wonder-1.0` | `META_MODEL` | Chat, planning, deep synthesis, trading decisions. |
| Fast routing | `muse-spark-1.3` | `META_FAST_MODEL` | Intent extraction, classification, short operational checks. |
| Screen vision | `muse-spark-1.3` | `META_AI_VISION_MODEL` | Live screen questions, chart reading, ticket verification. |

The client enforces the Muse-only policy. A configured model that does not begin with `muse-` is rejected by `Settings.validate()`. The primary model uses `META_REASONING_EFFORT=high` and an 8192-token ceiling; the fast model uses `low` effort and a 2048-token ceiling; vision uses `minimal` effort for latency.

`core/meta_api.py` provides:

- OpenAI-compatible `POST {META_API_BASE}/chat/completions` with a Bearer key.
- Text, image (data URL), and JSON-decision calls.
- Fenced JSON extraction and tolerant parsing.
- One corrective retry when a response is truncated, preserving the requested effort.
- Reasoning cleanup that removes action tags from user-visible prose while preserving Markdown.

---

## 4. Desktop Application

### 4.1 Launch and Window Behavior

Orunex launches through `Lanzar_Orunex_Windows.vbs`:

```vbscript
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = projectDir
WshShell.Run "pythonw.exe src\main.py", 3, False
```

The `3` window style requests a maximized process. The application independently calls `self.state("zoomed")` after the splash screen, so the desktop shortcut `C:\Users\Hp\Desktop\Orunex.lnk` always opens maximized even if the shortcut is recreated. The window also raises itself briefly to the foreground and then releases the topmost flag, so the first interaction is immediate without pinning the window above other applications.

The splash screen displays the Orunex mark, a progress animation, and the current initialization stage. The main window uses a light theme with a soft surface hierarchy, a moving gradient composer rim, and a compact navigation rail that can collapse.

### 4.2 Navigation

| Destination | How to Reach It | Purpose |
|:---|:---|:---|
| **Chat** | Sidebar → Chat | Main conversation, Live control, composer, task queue, activity log. |
| **Simplex Bridge** | Sidebar → Simplex Bridge | Pairing QR, pairing link, bridge status, notification preferences. |
| **Settings** | Sidebar → Settings | Profile, appearance, engine, knowledge hub, connections. |
| **Saved memory** | Settings → Profile → Manage saved memory | Inspect, add, and forget long-term memories. |

The sidebar also shows the current connection state for Simplex and a compact brand mark. The top bar displays the active page title and the current execution status.

### 4.3 Chat Workspace

The Chat page is the operational center of the product.

| Element | Behavior |
|:---|:---|
| **Chat history rail** | Lists saved conversations, most recent first; supports open, rename, and delete. |
| **New chat** | Creates a fresh conversation with the title `New chat`; the first user message becomes the title. |
| **Conversation header** | Shows the current chat title and the subtitle “Ask Orunex anything or describe a task.” |
| **Empty state** | Displays “At your service” with suggested starting points for chat, research, code, and artifacts. |
| **Message bubbles** | Distinguish user, agent, system, and artifact messages; support Markdown, code blocks, and copy. |
| **Artifact cards** | Show file type, title, path, and actions to open the file or reveal it in Explorer. |
| **Activity log** | A collapsible panel titled “AGENT ACTIVITY” with Show/Hide control; records routing, tool, and execution events. |
| **Status line** | Shows Ready, Thinking, Running, Paused, or Needs attention, with a colored indicator. |
| **Screen glow** | An optional blue contour around the window while Live is active; it belongs to Live mode, not to typed tasks. |

### 4.4 Composer

The composer is a floating pill with an animated gradient rim and a soft outer glow, rendered natively with Pillow inside CustomTkinter.

| Control | Behavior |
|:---|:---|
| **Attach** | Opens a file chooser and attaches a document or image to the next request. |
| **Mode selector** | Chooses Default, Programmer, Deep Research, or Agent Swapping. |
| **Pause / Resume** | Pauses the active execution flag; the label changes between Pause and Resume. |
| **Send** | Submits the request; Enter also sends. |
| **Live button** | A concentric-circle control inspired by Gemini Live; toggles the combined screen + microphone session. |

The composer is intentionally small. Long-running work is represented in the conversation and the activity log, not by locking the input.

### 4.5 Chat Modes

Modes are preference hints, not hard gates. If the selector is on Default, the router infers the most useful mode. If the user selects a mode, that mode wins. The selected mode is forwarded to the agent as an explicit instruction.

| Mode | Intent | Behavior |
|:---|:---|:---|
| **Default** | Automatic | Chooses the best approach. Auto-detection order: Agent Swapping, Programmer, Deep Research. |
| **Programmer** | Build and verify code | Opens VS Code, creates or edits real files, runs tests, uses the integrated terminal, and reports files, commands, and results. |
| **Deep Research** | Investigate and synthesize | Compares sources, separates facts from assumptions, cites URLs or documents, and produces a structured synthesis with next steps. |
| **Agent Swapping** | Multi-specialist orchestration | Splits the task into specialist roles, lets each role contribute, and merges the best result into one definitive answer with an explicit execution plan. |

The mode router uses whole-word and whole-phrase matching to avoid false positives. Explanations, comparisons, reviews, and plans remain reasoning work unless the user explicitly asks for code to be written or changed. This keeps VS Code from opening for a question that merely mentions a repository.

### 4.6 Sequential Task List

The chat workspace includes a sequential task queue for multi-step sessions:

- Add several requests to the list.
- Run the full list in order.
- Each item completes before the next begins.
- Progress is visible in the conversation and the activity log.
- Pause and Resume apply to the active item.

This is useful for demos and for workflows such as “draft the document, export the PDF, then create the deck.”

### 4.7 Settings

Settings is organized into five cards.

#### Profile

| Field | Behavior |
|:---|:---|
| **Display name** | Personalizes greetings and the chat header. |
| **Manage saved memory** | Opens the Saved Memory manager. |

#### Appearance

| Field | Behavior |
|:---|:---|
| **Theme** | Light theme, optimized for the Orunex surface palette. |
| **Language** | English interface. |
| **Interface scale** | 80%–140% slider; updates the CustomTkinter scaling and the saved configuration. |

#### Engine

| Control | Behavior |
|:---|:---|
| **Automatic recovery on failure** | Enables the auto-healer and supervisor recovery path. |
| **Save task memory automatically** | Records completed episodes into FAISS. |
| **Screen glow while working** | Enables the blue Live contour. |
| **Maximum retries** | 1–5 slider; default 3. |
| **Context window** | 2,048–128,000 token slider; default 8,192. |

#### Knowledge Hub

| Control | Behavior |
|:---|:---|
| **Upload JSON** | Ingests structured records into the local knowledge base. |
| **Upload PDF** | Extracts and ingests PDF text. |
| **Feedback line** | Confirms ingestion and reports the number of records or pages processed. |

#### Connections

| Connection | Behavior |
|:---|:---|
| **Simplex Bridge** | Opens the pairing page; explains that Simplex pairs Orunex with a phone for remote commands. |
| **VS Code Bridge** | Opens or connects the local VS Code bridge; shows bridge status. |

### 4.8 Simplex Bridge Page

The Simplex page is a complete pairing and preferences surface.

| Section | Contents |
|:---|:---|
| **Connection card** | Live status pill, Start & pair / Try again button, Disconnect button, and a detail line describing the current link. |
| **Pairing QR** | A 238×238 QR card; shows “Your pairing QR will appear here” until a link is created. |
| **Pair in three steps** | 1. Create a secure invitation. 2. Scan the QR with Simplex on the phone. 3. Orunex becomes available for remote commands and notifications. |
| **Pairing link** | Read-only text box with the full invitation; Copy link action and confirmation. |
| **Bridge preferences** | Notify me when a task finishes; Accept commands sent from Simplex; Send a local screenshot after tasks; Send remote screenshots automatically. |
| **Save preferences** | Persists the four switches to the local Simplex configuration. |

The page reflects real bridge state, not a mock: `is_connected()` and `is_linked()` drive the status pill, the button labels, and the sidebar indicator.

### 4.9 Saved Memory

The Saved Memory manager is a dedicated window opened from Profile. It provides:

- A scrollable list of stored memories with their text, namespace, and age.
- **Forget** to remove a single memory.
- **Clear** to remove all memories after confirmation.
- **Add** to store a new note manually.
- A search field for filtering the visible memories.

The manager operates on the same persistent FAISS index used by the agent, so a memory added here is immediately available to code lookup, strategy recall, and episode recall.

---

## 5. The Agent Runtime

### 5.1 AgentBrain Orchestrator

`core/agent_brain.py` is the single dependency graph for the agent. The UI stays deliberately thin: it submits work, renders events, and never owns a bridge or a model client.

Responsibilities:

- Own every bridge, memory index, and task.
- Run work on a bounded pool so the UI never freezes.
- Route encrypted Simplex commands.
- Expose an immutable status snapshot and diagnostics.
- Coordinate warm-up, codebase indexing, paper demos, and TradingView chart opening.
- Enforce the kill switch and remote duplicate suppression.

Public operations:

| Method | Purpose |
|:---|:---|
| `submit_bugfix(request)` | Start an Android diagnosis and repair task. |
| `submit_trading(request)` | Start a paper-trading decision and optional GUI execution. |
| `submit_index_codebase()` | Chunk and index the workspace into FAISS. |
| `submit_tradingview(symbol, timeframe)` | Open a symbol in TradingView and confirm the chart. |
| `warmup_async(reason)` | Prepare the emulator and TradingView in the background. |
| `submit_remote_text(text, contact)` | Rehearse or execute a Simplex-style order. |
| `handle_remote_text(text, contact)` | Synchronous remote-order entry point. |
| `wait_for_idle(timeout)` | Wait for all submitted work to settle. |
| `completed_summaries()` | Return `(kind, state, summary)` for completed tasks. |
| `status()` | Compact status string for the UI and remote status replies. |
| `diagnostics()` | Structured health report for `app.py --check`. |
| `set_kill_switch(active)` | Stop new paper activity and mark the runtime as halted. |
| `shutdown()` | Stop the executor, bridges, and background workers. |

### 5.2 Direct Command Router

Short desktop commands are handled locally with zero network latency. The router understands:

- Open an application by friendly name (Chrome, Edge, Firefox, Brave, Opera, Vivaldi, VS Code, Word, Excel, PowerPoint, Notepad, Explorer, Terminal, and others).
- Open a URL in a named browser or in the visible browser.
- Open a new browser tab when the request explicitly asks for one.
- Ask for clarification when a bare “open” has no target.
- Select the browser from the current screen context when the user does not name one.
- Pre-speak the confirmation in Live mode before the window finishes opening.
- Remember the last direct command so follow-ups such as “do it again” remain on the same path.

The router uses `_orunex_libs/intent_router.py` for browser labels and intent objects, and `_orunex_libs/os_executor.py` for `open_url`, `smart_launch`, and window control.

### 5.3 Complex-Task Delegation

Some requests are too long for a single chat turn. The desktop app detects them and starts the headless agent backend (`app.py --command ...`) as a separate process, then watches its log and relays the result.

Delegated tasks:

| Task | Payload | Behavior |
|:---|:---|:---|
| **Android repair** | `!fix <instruction>` | Screenshot the device, diagnose with Muse, locate source with FAISS, patch with the VS Code bridge, rebuild/install, verify visually, remember the episode. |
| **Paper entry** | `!trade <alert or instruction>` | Run the full paper-trading pipeline and GUI execution. |
| **TradingView analysis** | `!tv <symbol>` or natural language | Open the chart, capture it, ask Muse for analysis, and return a structured view. |
| **Warm-up** | `!warmup` | Prepare the emulator and TradingView. |

The delegation watcher:

1. Launches the backend with a unique log file `orunex_delegated_<timestamp>.log`.
2. Persists the delegation context so follow-ups such as “execute the order” stay on the trading path.
3. Tails the log for `AGENT_RESULT`.
4. Relays the final message into chat.
5. Speaks the result when Live is active.
6. Clears the “delegating” state even when the task takes minutes.

### 5.4 Cerebro and Supervisor

`src/agents/cerebro.py` is the reasoning nucleus. It receives the task, the user name, and the active mode, builds the appropriate prompt, calls Muse, and returns a response that may contain executable tags. It is responsible for:

- Planning multi-step work.
- Producing Office and artifact tags.
- Choosing between direct execution and explanation.
- Formatting the final answer for the chat bubble.
- Respecting the selected mode’s instruction.

`src/agents/supervisor.py` decides which agent profile should handle a request. In the current architecture, all external profiles consolidate into Cerebro, which keeps the execution graph simple and auditable. The supervisor also owns the recovery loop:

- Detect a failed execution.
- Ask the auto-healer for a corrected command or tag.
- Retry up to the configured maximum (default 3).
- Report a clear terminal state if recovery is exhausted.

### 5.5 Auto-Healer

`src/_orunex_libs/auto_healer.py` implements a two-layer repair strategy.

**Layer 1 — deterministic fast repair (sub-50 ms):**

| Rule | Repair |
|:---|:---|
| Unbalanced quotes | Appends the missing single or double quote. |
| Windows path separators | Converts forward slashes to backslashes for local paths, leaving URLs untouched. |
| Missing parent directory | Creates the parent directory for a referenced absolute path. |
| `python3` on Windows | Rewrites to `python`. |
| `ls` on Windows | Rewrites to `dir`. |
| `touch` on Windows | Rewrites to `type nul > file`. |

**Layer 2 — Muse correction:**

If no deterministic rule applies, the healer sends the failed command and its output to Cerebro with a strict instruction to return only a corrected command or tag in `[CORRECCION: ...]` form. The correction is logged and retried by the supervisor.

The healer is intentionally conservative. It never rewrites a command that already succeeded, and it never hides the original failure from the activity log.

### 5.6 Bounded Agent Loop and Tool Registry

`src/_orunex_libs/agentic_loop.py` provides a sandboxed tool loop for tasks that benefit from iterative tool use.

| Limit | Default | Environment Variable |
|:---|:---|:---|
| Maximum tool calls | 6 | `ORUNEX_AGENT_MAX_TOOL_CALLS` |
| Maximum steps | 8 | `ORUNEX_AGENT_MAX_STEPS` |
| Wall-clock budget | 120 s | `ORUNEX_AGENT_TIME_BUDGET` |
| Transcript ceiling | 28,000 characters | Internal constant |

The loop:

1. Sends the task and tool catalog to Muse.
2. Parses a tool request from a fenced `tool`/`json` block, `<tool_call>` XML, a bare JSON object, or a short explanation containing JSON.
3. Executes only allow-listed tools through `ToolRegistry`.
4. Appends the tool result to the transcript.
5. Repeats until the answer is complete or a limit is reached.
6. Makes one final, tool-free synthesis request so the user receives prose, not a raw tool envelope.

The loop never executes generated Python or shell commands. Tools are explicit, typed, and registered in `src/_orunex_libs/agent_tools.py`.

### 5.7 OS Executor and Tag System

`src/_orunex_libs/os_executor.py` is the bridge between model output and the operating system. It parses structured tags, checks permissions, executes the corresponding action, and returns human-readable results plus artifact/widget tags.

#### Core Tag Families

| Tag | Purpose |
|:---|:---|
| `[OPEN_URL: url]` | Open a URL in the selected or default browser. |
| `[GUI_OPEN: app]` | Launch an application. |
| `[GUI_NAVIGATE: url]` | Navigate the active browser. |
| `[GUI_CLICK: x, y]` | Click normalized or absolute coordinates after validation. |
| `[GUI_CLICK_TEXT: label]` | Locate a visible label and click it. |
| `[GUI_TYPE: text]` | Type text into the focused field. |
| `[GUI_PRESS: key]` | Press a key. |
| `[GUI_SHORTCUT: combo]` | Send a keyboard shortcut. |
| `[GUI_SCROLL: up/down N]` | Scroll the active surface. |
| `[GUI_WAIT: seconds]` | Wait for the UI to settle. |
| `[GUI_SEE: question]` | Capture the screen and ask Muse what is visible. |
| `[SCREENSHOT]` / `[SCREENSHOT: monitor=N]` | Capture one or all monitors. |
| `[CMD: command]` | Run a shell command through the permission gate. |
| `[CMD_ASYNC: command]` | Run a shell command without blocking the chat. |
| `[FILE: path]content[/FILE]` | Write a file. |
| `[EDIT: path]---BUSCAR---old---REEMPLAZAR---new[/EDIT]` | Apply a guarded text replacement. |
| `[MKDIR: path]` | Create a directory. |
| `[DEL: path]` | Delete a file through the permission gate. |
| `[VSCODE: action]` | Drive the VS Code bridge. |
| `[SOCIAL: network|action|text]` | Open a social network or prepare a post. |
| `[BMD: instruction]` | Route a Blockchain Markdown operation to the BMD expert. |
| `[ARTIFACT: path|kind|title]` | Render an artifact card in chat. |
| `[WIDGET: path]` | Render a generic file widget. |
| `[MEMORIZE: text]` | Store a long-term memory. |
| `[LOAD_SKILL: name]` | Load a registered skill. |
| `[PROJECT_PLAN: json]` | Create a multi-file project plan. |
| `[MISSION: description]` | Start a high-level mission. |
| `[OFFICE_MISSION: topic|kind|format]` | Start a research-backed Office artifact. |
| `[MAKE_PPT: topic]` | Generate a PowerPoint deck. |
| `[MAKE_DOC: type|topic]` | Generate a document through the document factory. |
| `[HEADLESS_SEARCH: query]` | Run a headless web search and summarize the results. |
| `[YOUTUBE: play|query]` | Search and play a YouTube result. |
| `[WHATSAPP_SEND: contact|message]` | Prepare a WhatsApp message. |
| `[SYSTEM_POWER: shutdown/restart]` | Request a system power action through the permission gate. |
| `[SELF_EVOLVE]` / `[SELF_RECONSTRUCT: file]` | Enter the guarded self-evolution sandbox. |
| `[LOOP: count=N]...[/LOOP]` | Repeat a block of tags. |

#### MAKE_DOC and HEADLESS_SEARCH

These two tags are preserved as first-class deterministic capabilities.

**`[MAKE_DOC: type|topic]`**

The document factory supports:

| Type | Output |
|:---|:---|
| `excel` | Real `.xlsx` workbook with styled headers, rows, and formulas where applicable. |
| `word` | Real `.docx` document with headings, tables, and formatted body text. |
| `pdf` | Real `.pdf` with typography and page layout. |
| `landing` | Standalone HTML landing page. |
| `ppt` / `pptx` | Real `.pptx` presentation. |

The executor calls `doc_factory.generate_excel`, `generate_word`, `generate_pdf`, or `generate_landing`, or `ppt_maker.generate_presentation`, then emits an `[ARTIFACT: ...]` tag so the UI renders a clickable card and opens the file.

**`[HEADLESS_SEARCH: query]`**

The executor calls `_orunex_libs/headless_web.search_and_summarize(query)`, which uses the `ddgs` engine to retrieve results, extracts page text, and returns a concise summary with source URLs. The permission gate checks each query before execution. This gives the agent a research path that does not depend on opening a visible browser.

### 5.8 Permission Model

`src/_orunex_libs/permissions.py` gates sensitive actions. The default configuration is confirmation-gated; trusted headless runs can set `ORUNEX_STRICT_PERM=0`.

| Variable | Default | Effect |
|:---|:---|:---|
| `ORUNEX_STRICT_PERM` | `1` | `0` allows dangerous actions without UI confirmation. |
| `ORUNEX_ALLOW_DANGEROUS` | `0` | `1` allows dangerous actions when no UI confirmation callback exists. |
| `ORUNEX_AGGRESSIVE` | `0` | `1` relaxes mode-router and permission guards for faster operation. |
| `ORUNEX_VERBOSE` | `0` | `1` prints an environment summary at startup. |

Permission checks are applied to shell commands, file deletion, system power actions, headless searches, screenshots, and other sensitive tags. A denied action returns a clear message and does not silently continue.

### 5.9 Artifact Studio

`src/_orunex_libs/artifact_studio.py` converts explicit file requests into real files without waiting for a model.

Supported kinds:

| Kind | Extension | Detection examples |
|:---|:---|:---|
| PDF | `.pdf` | “create a PDF about solar energy” |
| Word | `.docx` | “make a Word document” |
| Excel | `.xlsx` | “build an Excel spreadsheet” |
| PowerPoint | `.pptx` | “create a presentation”, “slides”, “deck” |
| CSV | `.csv` | “export a CSV” |
| Markdown | `.md` | “write a Markdown report” |
| HTML | `.html` | “build a landing page” |

The studio:

1. Detects the requested kind and confirms a creation intent.
2. Extracts a title and any metrics, bullets, or structured data from the request.
3. Selects a theme and content plan.
4. Writes the real file with the appropriate library.
5. Returns a metadata dictionary containing path, kind, title, label, and a ready-to-render artifact tag.

The generated documents use real formatting: styled headings, tables, charts, and page layouts. The UI renders a card with the file type, title, and actions to open the file or show it in Explorer.

### 5.10 Office Expert

`src/_orunex_libs/office_expert.py` is the high-end document engine used for research-backed deliverables.

Capabilities:

- **Research:** optional web research with source extraction and relevance ranking.
- **Planning:** a single structured plan feeds every output format, so the deck, workbook, document, and PDF tell the same story.
- **PowerPoint:** themed covers, agendas, executive summaries, context, findings, native charts, metrics tables, deep dives, frameworks, risks, roadmaps, recommendations, and closing slides.
- **Animations and transitions:** optional native PowerPoint transitions and entrance animations.
- **Excel:** styled workbooks with headers, formulas, number formats, column widths, and summary sheets.
- **Word:** styled documents with headings, tables, hyperlinks, page fields, and consistent typography.
- **PDF:** print-ready output with the same plan and visual identity.
- **Markdown:** a portable representation of the plan.

The Office expert is used when the request calls for a researched, multi-section deliverable rather than a simple artifact. It produces a complete file, not a text outline.

### 5.11 Knowledge Hub

The Knowledge Hub ingests external knowledge into the local memory system.

| Input | Processing |
|:---|:---|
| **JSON** | Parses records, normalizes text, and stores each record with metadata. |
| **PDF** | Extracts page text, chunks it, and stores the chunks with source metadata. |

Ingestion is local. The Knowledge Hub does not upload the user’s documents to a third-party knowledge service. The ingested content becomes available to FAISS recall and to Muse through retrieved context.

---

## 6. Live Mode

Live mode is the multimodal heart of Orunex. It combines screen observation, microphone input, neural speech, and deterministic routing into a single session controlled by the concentric Live button.

### 6.1 Session Lifecycle

| Step | Behavior |
|:---|:---|
| **Start** | The Live button activates; the screen loop starts; the microphone starts if voice is enabled; the speaker is warmed with cached short replies. |
| **Listen** | Audio is captured at 16 kHz mono; silence gating detects the end of a turn; the transcript is sent to Meta ASR. |
| **Understand** | The transcript is stripped of the wake word and routed through the same deterministic ladder as typed text. |
| **Act** | Direct commands execute immediately; screen questions capture a fresh frame; complex tasks delegate; everything else goes to Muse. |
| **Speak** | The response is spoken with the Edge neural voice, sentence by sentence, with a local SAPI fallback. |
| **Continue** | A follow-up window allows short conversational turns without repeating the wake word. |
| **Stop** | The button deactivates; capture stops; speech stops; the contour turns off; the microphone watchdog is cancelled. |

### 6.2 Screen Observation

`src/_orunex_libs/live_vision.py` captures the screen every **1.5 seconds** and measures change locally.

| Parameter | Default | Meaning |
|:---|:---|:---|
| Capture interval | 1.5 s | Time between frames. |
| Change threshold | 4.5 | Minimum local difference score to emit a meaningful frame. |
| Change cooldown | 2.0 s | Minimum time between emitted change events. |
| Monitor | 1 | Primary monitor by default; multi-monitor capture is available. |

The capture thread never calls the model. It emits a frame only when the screen changes meaningfully. The vision analyzer is attached separately through `LiveVisionSession.set_analyzer()`, which keeps capture latency low and prevents a slow model call from blocking the loop.

`MetaVisionProvider` sends a single PNG frame as a data URL to the Meta API’s OpenAI-compatible chat endpoint. Credentials are read from `META_API_KEY`, `MODEL_API_KEY`, or `META_AI_API_KEY`; the key is never written into the module or the repository.

### 6.3 Screen Questions

When the user asks “What do you see on my screen?” or an equivalent question, Orunex takes a fresh capture and asks Muse directly. This path never goes through the OS executor, so the agent describes the screen instead of trying to click it.

The answer can include:

- The active application and window title.
- Visible text, controls, and layout.
- A chart’s symbol, timeframe, trend, and visible levels.
- A paper-trading ticket’s side, quantity, stop loss, and take profit.
- A form’s current values and the next action.

### 6.4 Microphone and ASR

`src/_orunex_libs/live_audio.py` captures microphone audio and transcribes complete turns.

| Parameter | Value |
|:---|:---|
| Sample rate | 16,000 Hz |
| Channels | Mono |
| Format | 16-bit PCM, wrapped as WAV for upload |
| Silence detection | Adaptive noise floor with a short silence window |
| ASR endpoint | `https://api.meta.ai/v1/asr/transcribe` |
| ASR model | `muse-voice-transcribe-1.0` |
| Fallback endpoint | `META_ASR_ENDPOINT` |
| Fallback model | `META_ASR_MODEL` |

The audio session:

- Calibrates the noise floor at the start of a session.
- Rejects very short noise bursts.
- Avoids transcribing the assistant’s own voice.
- Runs transcription on a worker thread so capture continues.
- Emits status changes: Ready to listen, Listening (offline), Transcribing, Thinking, Speaking.
- Is watched by a UI watchdog that restarts the microphone if the thread stops unexpectedly.

### 6.5 Neural Voice

`src/_orunex_libs/live_tts.py` provides natural speech.

| Layer | Behavior |
|:---|:---|
| **Primary** | Microsoft Edge neural TTS via `edge-tts`, with a curated male voice per language. |
| **Streaming** | Splits replies into sentence chunks and plays them in order, so the first sentence is heard quickly. |
| **Cache** | Pre-renders common short replies (greetings, confirmations, “Live mode enabled”) to disk. |
| **Fallback** | Local Windows SAPI voice when the neural service is unavailable. |
| **Control** | A generation counter allows a hard stop; stale audio is discarded immediately. |
| **Identity** | The fallback uses a male SAPI voice when available, preserving Orunex’s voice identity. |

The speaker runs on a worker thread and exposes status updates to the UI. Live mode never blocks the interface while speech is generated or played.

### 6.6 Wake Word and Conversation Window

Live mode supports hands-free operation:

- A leading wake word (“Orunex” or “Hey Orunex”) is stripped before routing.
- A wake word on its own triggers an instant local greeting.
- After a response, a short conversation window (30 seconds) allows follow-up turns without repeating the wake word.
- Free-form speech outside the window requires an explicit wake word, which prevents ambient conversation from triggering actions.
- Direct desktop commands work without a wake word when typed in chat.

### 6.7 Instant Greetings

Greetings and wake-only turns are answered locally with a cached reply, without a network call. This makes Live feel immediate: the user hears “At your service” or an equivalent greeting as soon as the turn is recognized.

### 6.8 Live Routing

Live uses the same deterministic ladder as typed chat:

1. Instant greeting.
2. Screen question.
3. Complex-task delegation.
4. Direct command.
5. BMD expert.
6. Artifact Studio.
7. VS Code path.
8. Muse reasoning.
9. OS executor.

The difference is timing: Live pre-speaks confirmations for open-app and open-URL commands, so the user hears the action before the window finishes appearing. It also speaks delegated results when they arrive.

### 6.9 Live Safety

- The screen loop captures only when Live is active.
- The microphone is released when Live stops.
- Speech is stopped immediately on toggle-off.
- Screen questions are answered from a fresh frame, not from stale context.
- The agent never sends a screen frame to a non-Muse provider.
- The Live contour is a state indicator, not a decorative animation: it appears only when Live is active.

---

## 7. Memory and Knowledge

### 7.1 FAISS Architecture

Orunex uses a persistent local FAISS index for long-term recall.

| Property | Value |
|:---|:---|
| Index type | `IndexIDMap2(IndexFlatIP(384))` |
| Dimension | 384 |
| Similarity | Cosine via inner product on normalized vectors |
| Persistence | `memory.index` plus `memory.index.meta.json` |
| Default path | `data/hackathon_memory.index` |
| Thread safety | `RLock` around mutations and queries |
| Atomic writes | Temporary file + `os.replace` |

The index is a storage and recall mechanism, not a reasoning engine. Embeddings are deterministic feature hashing, not a learned model. Every semantic judgement—what matches, what to fix, whether to trade—is made by Muse.

### 7.2 Deterministic Embedding

`hash_embedding()` builds a 384-dimensional vector from:

| Feature | Weight |
|:---|:---|
| Word unigrams (`w:word`) | 1.0 |
| Word bigrams (`b:left right`) | 0.6 |
| Character trigrams (`c:abc`) | 0.25 |

Each feature is hashed with BLAKE2b (8-byte digest). The hash selects a dimension and a sign; the weight is added with a logarithmic scale. The vector is L2-normalized before insertion.

This design has three advantages:

1. **Deterministic:** the same text always produces the same vector.
2. **Dependency-light:** no embedding model download, GPU, or external service.
3. **Auditable:** the index can be rebuilt from text at any time.

### 7.3 Namespaces

| Namespace (`kind`) | Contents | Used By |
|:---|:---|:---|
| `code` | Chunks of local source files with path, line range, symbols, language, and mtime. | Android repair, code lookup. |
| `strategy` | Trading strategies, playbooks, and risk notes. | Paper-trading recall. |
| `episode` | Completed task outcomes and lessons. | Long-term learning. |
| `knowledge` | BMD knowledge pack entries and ingested knowledge. | BMD answers, research, general recall. |

`search(query, top_k, kind=...)` filters by namespace and returns metadata plus a similarity score. `find_code_candidates()` is the dedicated code lookup used by the Android repair pipeline.

### 7.4 Codebase Indexing

`index_codebase(root, chunk_lines=120, overlap=20)` indexes the workspace.

| Behavior | Detail |
|:---|:---|
| Extensions | `.kt`, `.kts`, `.java`, `.xml`, `.py`, `.js`, `.ts`, `.tsx`, `.html`, `.css`, `.json`, `.gradle` |
| Skip directories | `.git`, `.gradle`, `build`, `__pycache__`, `node_modules`, `.ruff_cache`, `simplex_bin`, `simplex_data`, `scratch` |
| Chunking | 120 lines with 20 lines of overlap. |
| Symbol extraction | Detects `class`, `fun`, `function`, `def`, `const`, `let`, and `var` declarations. |
| Incremental refresh | Changed files drop stale chunks before re-indexing. |
| Metadata | Relative path, absolute path, mtime, line start, symbols, language. |

Run a full index with:

```bash
python app.py --index-code
```

The resulting index lets a diagnosis such as “the login button does nothing” find the most likely source files before Muse chooses the exact patch.

### 7.5 BMD Knowledge Pack

`src/_orunex_libs/bmd_knowledge.py` contains a verified 21-entry knowledge pack for Blockchain Markdown.

| Property | Value |
|:---|:---|
| Pack version | `bmd-engine-2.1.0/orunex-pack-3` |
| Entries | 21 |
| Storage | Local FAISS index under the `knowledge` namespace |
| Synchronization | Idempotent; re-running the sync does not duplicate entries |

Entry topics:

| Knowledge ID | Topic |
|:---|:---|
| `bmd.overview` | What Blockchain Markdown is and why it exists. |
| `bmd.syntax.frontmatter` | Required frontmatter, payload, and normalization. |
| `bmd.hash.canonical` | The canonical SHA-512 hash: 128 hex characters, not SHA-256. |
| `bmd.modes` | `draft` and `transfer` semantics. |
| `bmd.signatures` | Ed25519 signatures, emitter/receiver roles, and demo seeds. |
| `bmd.signature.governance` | `max_signatures`, unilateral, bilateral, and multilateral governance. |
| `bmd.contracts` | Contract structure, clauses, and governance. |
| `bmd.cli.reference` | Complete CLI reference. |
| `bmd.workflow.draft` | Verified recipe for a valid draft. |
| `bmd.workflow.transfer` | Transfer workflow: sign, verify, co-sign, audit. |
| `bmd.ffi` | Native DLL/FFI operations. |
| `bmd.property` | IP property injection and extraction. |
| `bmd.ledger` | Chained ledger auditing. |
| `bmd.render` | Standalone HTML rendering. |
| `bmd.office` | Office export metadata. |
| `bmd.errors` | Engine result codes and diagnostics. |
| `bmd.security` | Threat model and custody guarantees. |
| `bmd.integration.orunex` | Orunex deterministic intents and tags. |
| `bmd.limits` | Operational limits and capacity. |
| `bmd.recipes` | End-to-end recipes. |
| `bmd.glossary` | Terminology. |

The pack is synchronized at startup and can be searched through the same FAISS recall used by the rest of the agent. This is why BMD questions receive precise answers about hash length, lifecycle, signature governance, and CLI behavior.

### 7.6 Episode Memory

When a task completes, the agent can store an episode:

```text
kind: episode
text: <task summary, decision, outcome, lesson>
metadata: task kind, state, timestamp, artifacts, symbols
```

Episode memory gives the agent continuity across sessions. A later request can recall a similar repair, strategy, or document workflow and use it as context. Automatic episode recording is controlled by the “Save task memory automatically” setting and `ORUNEX_MEM_RECORD`.

### 7.7 Strategy Memory

Paper trading recalls strategies from the `strategy` namespace before asking Muse for a decision. The recalled block is included in the prompt, which keeps the decision anchored to the user’s stored playbook rather than generic market commentary.

### 7.8 Persistence and Recovery

The index is saved after every mutation and on shutdown. Writes are atomic:

1. Write the index to a temporary file in the same directory.
2. Write the metadata sidecar to a temporary file.
3. Replace the live files with `os.replace`.

If an index with a different dimension is found, Orunex starts a fresh index rather than mixing incompatible vectors. The metadata sidecar is human-readable JSON, which makes the memory store inspectable and portable.

---

## 8. Connections and Integrations

### 8.1 Simplex Bridge

Simplex is the encrypted remote-control channel. Orunex connects to the local Simplex Chat CLI over WebSocket and exchanges structured frames.

| Property | Value |
|:---|:---|
| WebSocket URL | `ws://127.0.0.1:5227` |
| Frame shape | `{"corrId": "...", "cmd": "@<contact> <text>"}` |
| Incoming event | `newChatItems` |
| Normalized object | `RemoteCommand(text, contact, received_at, ...)` |
| Default state | Disabled until `SIMPLEX_ENABLED=true` and a contact is paired. |

#### Pairing

1. The user opens **Simplex Bridge** in the desktop app.
2. **Start & pair** launches or connects the local Simplex CLI.
3. Orunex creates a secure invitation and renders it as a QR code and a copyable link.
4. The user scans the QR with Simplex on the phone.
5. The contact is stored as the allowlist for state-changing remote orders.

The page shows a live status pill, the linked contact, and the four bridge preferences.

#### Remote Commands

| Command | Behavior |
|:---|:---|
| `!fix <instruction>` | Start an Android diagnosis and repair task. |
| `!trade <alert or instruction>` | Run the paper-trading pipeline and GUI execution. |
| `!tv <symbol>` / `!tradingview <symbol>` | Open a symbol in TradingView and return chart context or analysis. |
| `!warmup` / `!preparar` / `!ready` | Prepare the emulator and TradingView. |
| `!status` / `!estado` / `!estado agente` | Return the agent status snapshot. |
| `!stop` / `stop` / `kill` | Activate the kill switch and stop new paper activity. |
| `!close <position>` | Close a paper position. |
| `!archivo: <path>` | Send a file from the desktop to the paired contact. |
| `!captura` | Capture the screen and send it to the paired contact. |
| `!heartbeat` | Return a liveness and status heartbeat. |
| `!help` | Return the command reference. |
| Natural language | Routed to Muse for a semantic decision; state-changing actions still pass the allowlist and safety gates. |

#### Security Controls

| Control | Behavior |
|:---|:---|
| **Contact allowlist** | When `SIMPLEX_CONTACT` is configured, state-changing messages from any other contact are ignored. Local CLI and Live entries use reserved contacts and are already inside the machine. |
| **Duplicate suppression** | Identical messages from the same contact inside `REMOTE_DUPLICATE_WINDOW_S` (default 90 s) are ignored. |
| **Kill switch** | `!stop` halts new paper activity and marks the runtime as halted. |
| **Encrypted transport** | Simplex provides end-to-end encryption between the paired devices. Orunex transports text only; routing remains local. |
| **Structured confirmations** | Every order returns a concise result with the task state, symbol, side, entry, stop loss, take profit, and paper-account impact. |

#### Notifications and Heartbeat

The production bridge (`src/_orunex_libs/simplex_bridge.py`) sends:

- A “Thinking...” notification when a remote task starts.
- A completion notification with the cleaned result.
- Optional screenshots after local or remote tasks.
- A heartbeat every 60 seconds with status and liveness.
- A system-status reply with CPU, memory, and running processes.

### 8.2 VS Code Bridge

The VS Code bridge gives the agent a real editor and terminal, not a simulated one.

| Capability | Implementation |
|:---|:---|
| Launch VS Code | `vscode_integration.connect()` and `vscode_bridge.launch_vscode()`. |
| Open a file | `open_file(path, line)`. |
| Write a file | `write_file(path, content, open_after)`. |
| Edit a file | `edit_file` and `replace_text`. |
| Run a terminal command | `run_terminal(command, cwd, name)`. |
| Run a command and capture output | `run_command(command, cwd, timeout)`. |
| Run tests | `run_tests(cwd, command)`. |
| Diagnostics | `diagnostics(path)`. |
| Workspace info | `workspace_info()`. |
| Save all | `save_all()`. |
| VS Code command | `run_vscode_command(command, args)`. |

The bridge uses a local HTTP service on `127.0.0.1` with a port range starting at 8765. It stores its configuration in `%USERPROFILE%\.orunex\vscode_bridge.json` and can install its companion extension from `src/integrations/vscode_extension`.

The Android repair task uses the bridge for guarded patches:

1. Back up the target file.
2. Apply the exact replacement.
3. Produce a diff.
4. Open the file in VS Code.
5. Run the relevant tests.
6. Rebuild and install the Android app when ADB is available.
7. Capture the device again and ask Muse to verify the fix.

### 8.3 Android ADB Bridge

`bridges/adb_bridge.py` controls an Android device or emulator through `adb`.

| Capability | Behavior |
|:---|:---|
| Device discovery | Finds a ready device; can auto-start a configured AVD. |
| Screenshot | `adb exec-out screencap -p` into a PNG. |
| Install | Installs the debug APK. |
| Restart | Starts the main activity after install. |
| Shell | Runs allow-listed shell commands. |
| Package/activity | Reads `ANDROID_PACKAGE` and `ANDROID_ACTIVITY`. |
| Serial selection | Uses `ADB_SERIAL` when multiple devices are present. |
| ADB path | Uses `ADB_PATH` when `adb` is not on `PATH`. |

The Android repair pipeline is:

```text
ADB screencap
  → Meta vision diagnosis (JSON)
  → FAISS code candidate lookup
  → Meta file + patch selection (JSON)
  → VS Code guarded patch (backup + diff)
  → ADB rebuild / install / restart
  → Meta visual verification
  → FAISS episode memory
```

### 8.4 TradingView Bridge

`bridges/tradingview_bridge.py` prepares the native TradingView desktop application.

| Capability | Behavior |
|:---|:---|
| Launch | Finds the installed TradingView executable or app ID. |
| Symbol | Opens `TRADINGVIEW_CHART_BASE_URL` with the requested symbol. |
| Timeframe | Passes the requested interval. |
| Capture | Captures the chart window for Muse vision. |
| Confirmation | Waits for the chart to be ready before returning. |

TradingView is the only execution surface for paper orders. There is no broker API, no webhook broker, and no real-funds path.

### 8.5 Web, Chrome, and Headless Search

| Integration | File | Capability |
|:---|:---|:---|
| Browser launcher | `_orunex_libs/os_executor.py` | Opens URLs in Chrome, Edge, Firefox, Brave, Opera, Vivaldi, or the default browser. |
| Chrome driver | `_orunex_libs/chrome_driver.py` | Launches Chrome with a selected profile and can read native YouTube results. |
| Headless search | `_orunex_libs/headless_web.py` | DDGS search, page text extraction, summary, and source URLs. |
| Web search | `_orunex_libs/web_search.py` | Lightweight DDGS result retrieval. |
| YouTube expert | `_orunex_libs/headless_web.py` | Searches YouTube and returns playable results. |
| Visible-browser selection | `src/main.py` | Chooses the browser from the current screen context when the user does not name one. |

### 8.6 Social and Messaging

`src/integrations/social_media.py` provides controlled social actions:

- Open a social network.
- Prepare a post.
- Search on a network.
- Prepare a WhatsApp message.
- Execute a named network action.

These actions are routed through the permission model. The agent prepares and opens; the human remains in control of publishing.

### 8.7 Office and Document Integrations

| Engine | Output |
|:---|:---|
| `artifact_studio.py` | Fast, deterministic PDF/DOCX/XLSX/PPTX/CSV/MD/HTML files. |
| `office_expert.py` | Research-backed, multi-section Office deliverables with native charts and styling. |
| `doc_factory.py` | Excel, Word, PDF, and landing-page generation from tags. |
| `ppt_maker.py` | PowerPoint generation from `[MAKE_PPT]` and `[PPTX]` tags. |
| `document_engine.py` | Universal document generation. |
| `excel_engine.py` / `excel_master.py` | Workbook creation and advanced spreadsheet operations. |
| `office_integrator.py` | Office application integration. |

All document engines write real files to disk and return artifact metadata. The UI renders the result as a clickable card.

---

## 9. Paper Trading

Orunex includes a complete paper-trading operative that turns TradingView alerts, remote commands, or natural-language orders into simulated positions. It is deliberately separated from real brokerage: the product contains **no broker integration and no real-funds code path**.

### 9.1 Hard Invariants

| Invariant | Implementation |
|:---|:---|
| **Paper only** | `paper_trading_only = True` is a frozen setting, not a configurable flag. |
| **TradingView native** | Execution happens through the native TradingView desktop ticket. |
| **No broker API** | No brokerage SDK, REST endpoint, or order router is imported or called. |
| **No real funds** | The paper engine owns a simulated balance and positions only. |
| **Risk gate is deterministic** | Muse cannot exceed the configured risk limits; the gate validates every order. |
| **GUI is mandatory for entries** | An explicit paper entry is only complete after the native ticket is verified and submitted. |
| **Paper Trading panel verified** | The ticket is not opened until the screenshot shows the Paper Trading panel, confirmed by both Muse and a deterministic template match. |

### 9.2 Trading Pipeline

```text
TradingView alert / Simplex order / natural-language order
  → parse the alert payload (data extraction only)
  → recall strategies from FAISS
  → Meta Muse technical decision (JSON, optional chart image)
  → deterministic risk gate
  → paper engine: position sizing, SL/TP, balance update
  → native TradingView GUI execution
  → structured confirmation
  → FAISS episode memory
```

The model produces a structured decision:

```json
{
  "action": "BUY",
  "symbol": "BTCUSDT",
  "entry": 67000,
  "stop_loss": 66200,
  "take_profit": 68600,
  "confidence": 0.78
}
```

The risk gate then checks:

| Check | Rule |
|:---|:---|
| Action | Must be `BUY`, `SELL`, `HOLD`, or `REJECT` for analysis; explicit orders must be `BUY` or `SELL`. |
| Symbol | Must match the requested symbol and the paper account’s instrument. |
| Entry | Must be positive and coherent with the current price. |
| Stop loss | Must be on the correct side of the entry and within the risk budget. |
| Take profit | Must be on the correct side of the entry and produce a positive reward/risk ratio. |
| Risk per trade | At most `MAX_RISK_PER_TRADE_PCT` (default 1.0%). |
| Position size | At most `MAX_POSITION_PCT` (default 20.0%) of the paper account. |
| Confidence | At least `MIN_TRADE_CONFIDENCE` (default 0.70) for autonomous analysis; at least `EXPLICIT_TRADE_MIN_CONFIDENCE` (default 0.50) for an explicit user order. |
| Duplicate exposure | Rejects a second order for the same symbol inside `PAPER_DUPLICATE_WINDOW_S` (default 900 s). |
| Balance | The simulated account must have sufficient buying power. |

### 9.3 Explicit Orders

An explicit order is a user-authorized paper entry: “execute a long,” “open a paper order,” “buy BTC now,” or a structured `!trade` command.

The explicit-order path is designed so that hesitation cannot silently cancel the user’s instruction:

1. **HOLD and REJECT are removed from the action set.** The model is told that an explicit paper entry is in progress and must choose BUY or SELL.
2. **The model is re-asked up to three times** (`EXPLICIT_TRADE_DECISION_ATTEMPTS=3`) with a stricter correction prompt if it returns an unusable action or a confidence below the explicit threshold.
3. **The same chart evidence is reused** across attempts, so the model is not judging a different market on each retry.
4. **The deterministic risk gate still validates every returned BUY or SELL.** A retry never bypasses the risk limits.
5. **The terminal outcome is a risk-validated paper entry or an explicit execution report.** An explicit order is never satisfied by HOLD or REJECT.

The attempt history is stored in `result.data["decision_attempts"]`, so the reasoning trail is inspectable.

### 9.4 Native TradingView GUI Execution

`tasks/tradingview_gui.py` is the execution half of the trading task. It drives the native TradingView desktop application with Orunex’s own cursor and keyboard.

#### Safety Invariants

| Invariant | Behavior |
|:---|:---|
| **Paper panel required** | `submit` is refused unless the screenshot shows the “Paper Trading” panel. |
| **Dual verification** | Muse’s reading **and** a deterministic template match must confirm the panel. |
| **Second independent check** | A second Muse verification confirms the ticket values before submission. |
| **Bounded loop** | At most 26 steps and 420 seconds by default. |
| **Allow-listed actions** | `click`, `type`, `press`, `hotkey`, `scroll`, `wait`, `think`, `abort`, `submit`, `done`. |
| **Normalized coordinates** | Clicks are relative to the captured TradingView window and cannot land outside it. |
| **No arbitrary execution** | The model never receives Python, shell, or broker access. |
| **No broker API** | The only execution surface is the native desktop ticket. |

#### Execution Flow

```text
Capture the TradingView window
  → Muse describes the screen and chooses one action
  → validate the action
  → perform the action with Orunex input
  → capture again
  → repeat until the ticket is complete
  → verify the Paper Trading panel and ticket values
  → submit
  → confirm the fill and return the reference
```

The GUI agent returns a structured result:

```json
{
  "ok": true,
  "submitted": true,
  "reference": "PAPER-...",
  "fill_price": 67012.5,
  "reason": "Paper Trading panel verified; ticket submitted."
}
```

The trading task stores `gui_verified=true` only when the GUI reports a successful submission. A PENDING_UI reservation prevents a second order from being submitted while the ticket is still being filled.

### 9.5 Paper Account

| Property | Default | Configuration |
|:---|:---|:---|
| Initial balance | 10,000.00 | `PAPER_INITIAL_BALANCE` |
| Currency | USD | `PAPER_CURRENCY` |
| State file | `data/paper_trading.json` | `PAPER_STATE_PATH` |
| Max risk per trade | 1.0% | `MAX_RISK_PER_TRADE_PCT` |
| Max position | 20.0% | `MAX_POSITION_PCT` |
| Autonomous confidence | 0.70 | `MIN_TRADE_CONFIDENCE` |
| Explicit confidence | 0.50 | `EXPLICIT_TRADE_MIN_CONFIDENCE` |
| Explicit attempts | 3 | `EXPLICIT_TRADE_DECISION_ATTEMPTS` |
| Duplicate window | 900 s | `PAPER_DUPLICATE_WINDOW_S` |

The paper engine tracks:

- Cash and equity.
- Open positions with entry, quantity, stop loss, and take profit.
- Realized and unrealized profit and loss.
- Order history with statuses: `PENDING_UI`, `OPEN`, `CLOSED`, `UNCONFIRMED`, `UI_FAILED`, `REJECTED`.
- A kill switch that blocks new activity.

### 9.6 Trading Commands

| Command | Behavior |
|:---|:---|
| `!trade <alert JSON or instruction>` | Run the full paper pipeline. |
| `!tv <symbol>` | Open the symbol in TradingView and return chart context. |
| `!warmup` | Prepare the emulator and TradingView. |
| `!close <position>` | Close an open paper position. |
| Natural language | “Open a paper long on BTCUSDT”, “execute the entry”, “close the position” are detected by `core/trade_intent.py`. |

### 9.7 Warm-Up

Warm-up prepares the environment before a demo or a live session:

1. Start the Android emulator if configured and no device is ready.
2. Launch TradingView.
3. Open the default chart.
4. Confirm that the chart is ready.
5. Report each stage to the activity log and, if paired, to Simplex.

Warm-up runs in a separate two-worker pool so the UI remains responsive.

### 9.8 Why This Design

Paper trading is a demonstration of disciplined autonomy:

- Muse provides market judgement.
- FAISS provides the user’s strategy memory.
- The risk gate provides non-negotiable arithmetic.
- The GUI agent provides native execution.
- The paper engine provides accounting and auditability.
- The absence of a broker provides a hard safety boundary.

The result is an agent that can analyze, decide, execute, and explain a trade without ever touching real funds.

---

## 10. Android Companion

### 10.1 Project Metadata

| Property | Value |
|:---|:---|
| Application ID | `com.orunex.mobile` |
| Namespace | `com.orunex.mobile` |
| `compileSdk` | 36 |
| `minSdk` | 26 |
| `targetSdk` | 36 |
| Version | 1.0 (versionCode 1) |
| Language | Java 17 |
| UI | WebView shell around local HTML/CSS/JS assets |
| Build system | Gradle 8.13.2 |

### 10.2 Architecture

```text
MainActivity (Java)
  ├─ Edge-to-edge window configuration
  ├─ WebView with JavaScript, DOM storage, file access
  ├─ SharedPreferences bridge for chats and settings
  ├─ File chooser for attachments
  ├─ Artifact download bridge → Downloads/Orunex
  ├─ Back-gesture callback
  └─ Local asset loader: index.html, app.js, styles.css, qrcode.js
```

The Android app is a companion surface, not a second reasoning engine. It provides a polished mobile chat experience, local persistence, modes, artifacts, and the Simplex pairing UI. Heavy reasoning, desktop automation, paper trading, and BMD execution remain on the paired desktop agent.

### 10.3 Screens

| Screen | Contents |
|:---|:---|
| **Chat** | Greeting, message list, typing indicator, composer, mode selector, new chat, drawer with history. |
| **Simplex Bridge** | Status pill, pairing QR, pairing link, copy action, three-step instructions, bridge preferences. |
| **Settings** | Display name, interface scale, automatic recovery, save memory, screen glow, retries, context window, mode. |
| **Drawer** | Chat list, active chat highlight, rename/delete menu, Simplex status, new chat. |

### 10.4 Chat Experience

- Chat history is stored locally through `SharedPreferences` and a localStorage fallback.
- Each conversation has a title derived from the first user message.
- Messages support Markdown-like formatting, copy, and artifact cards.
- A typing indicator appears while a reply is pending.
- Mode badges appear on non-default replies.
- Auto-mode replies are labeled with the resolved mode.
- The drawer shows the active chat and supports rename and delete with confirmation dialogs.

### 10.5 Modes on Android

The Android app supports the same four modes:

| Mode | Mobile behavior |
|:---|:---|
| **Default** | Automatic routing based on the request. |
| **Programmer** | Describes the desktop VS Code workflow and produces code artifacts where possible. |
| **Deep Research** | Structures the request into sources, findings, counterarguments, and next steps. |
| **Agent Swapping** | Describes specialist decomposition and result merging. |

The mode selector is a preference hint. The local resolver can auto-detect a mode from the request when Default is selected.

### 10.6 Local Artifacts

The Android app can generate and download:

| Kind | Behavior |
|:---|:---|
| PDF | Builds a text-based PDF locally and downloads it. |
| CSV | Generates comma-separated content. |
| HTML | Generates a standalone page. |
| Markdown | Generates a `.md` file. |
| Text | Generates a `.txt` file. |
| Python | Generates a `.py` file. |
| JavaScript | Generates a `.js` file. |
| Office binaries | Displays a note that the full binary is exported from the desktop app. |

Downloads go through the native `saveArtifact` bridge to `Downloads/Orunex`. The app also supports a browser download fallback.

### 10.7 Simplex on Android

The mobile Simplex page mirrors the desktop pairing experience:

- Paired/Offline status pill.
- Linked contact detail.
- Pairing QR rendered locally with `qrcode.js`.
- Pairing link box and copy action.
- Preferences: notify on completion, accept remote commands, send local screenshots, send remote screenshots.
- Start & pair, Generate pairing link, and Disconnect actions.

The page is a control surface for the bridge; the actual encrypted transport remains the Simplex CLI on the desktop.

### 10.8 Settings on Android

| Setting | Behavior |
|:---|:---|
| Display name | Personalizes the greeting. |
| Interface scale | Adjusts WebView text zoom. |
| Automatic recovery | Mirrors the desktop auto-heal preference. |
| Save task memory | Mirrors the desktop memory preference. |
| Screen glow | Mirrors the desktop Live contour preference. |
| Retries | 1–5. |
| Context window | Token budget preference. |
| Mode | Default, Programmer, Deep Research, Agent Swapping. |

Settings are persisted locally and restored on launch.

### 10.9 Build and Install

```bash
cd android
./gradlew assembleDebug
```

On Windows:

```powershell
cd android
.\gradlew.bat assembleDebug
```

The debug APK is written to:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

Install it with:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

The ADB bridge can also install and restart the app as part of the autonomous repair pipeline.

### 10.10 Manifest and Runtime Behavior

| Manifest property | Value |
|:---|:---|
| `allowBackup` | `true` |
| `enableOnBackInvokedCallback` | `true` |
| `forceDarkAllowed` | `false` |
| `hardwareAccelerated` | `true` |
| `supportsRtl` | `true` |
| Theme | `Theme.OrunexMobile` |

The app uses a dark surface palette, a custom launcher icon, and a splash treatment that matches the desktop brand. The WebView is configured for local assets, JavaScript, DOM storage, and safe file access. External links open through the system handler.

---

## 11. Blockchain Markdown: Complete Manual

> **Canonical source:** [BMD manual.md](BMD%20manual.md) contains the long-form specification. This section integrates the complete operational manual: principles, cryptographic stack, file format, every CLI command, Redact Studio, workflows, engine architecture, and enterprise guidance.

### 11.1 Executive Summary and Strategic Vision

Modern software development, corporate operations, and contract execution suffer from systemic fragmentation. Organizations exchange vulnerable text documents—PDFs, Word files, and ordinary Markdown—across untrusted channels. When autonomous agents generate or modify those documents, the absence of cryptographic boundaries introduces unacceptable risks: unnoticed alteration, hallucinated terms, no non-repudiation, and no reliable audit trail.

**Blockchain Markdown (.bmd)** establishes a mathematically immutable **Single Source of Truth**.

A `.bmd` file couples human-readable Markdown with a strictly validated cryptographic ledger header. Built on an ultra-lightweight, zero-dependency C11 engine, Blockchain Markdown guarantees:

1. **Absolute immutability.** Once compiled, altering a single whitespace or punctuation mark invalidates the SHA-512 ledger hash and the Ed25519 signature.
2. **Cryptographic ground truth.** The `.bmd` file is the sole canonical reality. HTML previews, terminal renders, and Office exports are ephemeral presentation layers.
3. **Hardware-anchored device identity.** Emitter and Receiver signatures are calculated automatically from authenticated device identity keys. Users cannot insert arbitrary or forged signatures.
4. **Autonomous governance.** The engine enforces rigid state transitions (`draft` → `transfer`), non-bypassable signature limits (`max_signatures`), and bilateral consensus verification.

> **Definition of “IP”:** Throughout this specification, **IP** means **Intelligent Property / Intellectual Property**—digital assets such as source code, proprietary algorithms, AI models, and confidential documentation. It never means an Internet Protocol network address.

### 11.2 Core Principles

#### 11.2.1 Zero-Dependency Ledger Identity

Earlier immutable-document schemes relied on arbitrary string identifiers (`block_id`). In high-assurance environments, arbitrary IDs can be forged, spoofed, or duplicated.

In **BMD Protocol v2.1**, `block_id` is optional and non-essential. Document authenticity, identity, and global uniqueness are anchored in mathematical truth:

- The **SHA-512 ledger hash** (128 hexadecimal characters) computed over the exact payload.
- The **Ed25519 signatures** validating author non-repudiation.
- The **previous-hash linkage** in chained ledger records.

#### 11.2.2 The Two Operational Modes

A `.bmd` document exists in one of two deterministic states.

**`mode: draft` — mutable development state**

- Allows drafting, editing lines, modifying frontmatter, and testing layouts.
- `bmd sign` attaches the Emitter’s authenticated Ed25519 signature and computes the SHA-512 hash, but leaves the document **open and mutable** so additional sections, clauses, or signature buttons can be added.
- `bmd sign` is authentication, not sealing.

**`mode: transfer` — frozen, immutable state**

- Triggered exclusively by `bmd compile` (or `:compile` in Redact Studio).
- Displays a retro purple pixel-gradient loading bar during final compilation.
- The core engine permanently freezes the payload and frontmatter.
- Modifying any byte on disk is blocked by the filesystem read-only attribute (`attrib +R`).
- No transition from `transfer` back to `draft` is permitted.
- On completion, the engine prints the **full absolute path** of the sealed file.

This separation is the central lifecycle rule: **sign in draft; compile to transfer.**

#### 11.2.3 Automatic Device Identity Signatures

> Signatures in BMD are always computed automatically from the device’s hardware identity key. Users cannot and must not enter signatures manually.

The engine derives a deterministic 32-byte Ed25519 seed from the authenticated device identity, persisted in:

- `%USERPROFILE%\.bmd\emitter_device.key` — Emitter (author) key.
- `%USERPROFILE%\.bmd\receiver_device.key` — Receiver (counterparty) key.

When signing:

- `bmd sign` computes the SHA-512 hash and signs as Emitter with the host’s authentic device key.
- `bmd compile` recomputes the final hash, freezes the document, and seals it with the Emitter device key.
- `bmd cosign` signs as Receiver with the counterparty’s authentic device key.

No manual seed, no custom hexadecimal entry, and no possibility of forging a signature.

#### 11.2.4 Signature Limits and Consensus Ratification

To prevent unauthorized parties from appending signatures to a sealed document, the protocol enforces a strict signature cap.

| `max_signatures` | Governance model | Behavior |
|:---|:---|:---|
| `0` | Unlimited | No cap; used for open multi-party records. |
| `1` | Unilateral | Only the creator (Emitter) signs. Co-signing is permanently rejected. |
| `2` | Bilateral | Requires both Emitter and Receiver. The document is **CONSENSUS RATIFIED** only when both Ed25519 signatures are present and valid. |
| `N` | Multilateral | Configurable multi-party consensus. |

### 11.3 The Cryptographic Stack and Security Model

#### 11.3.1 Cryptographic Primitives

The BMD core runtime is written in pure C11 without external dependencies (no OpenSSL, no libsodium), based on audited implementations.

| Primitive | Standard | Function in the Protocol |
|:---|:---|:---|
| **SHA-512** | NIST FIPS 180-4 | 128-hex-character payload integrity hash; deterministic tamper-evident lock. |
| **Ed25519** | RFC 8032 | Asymmetric digital signature over the twisted Edwards curve Edwards25519. |
| **Key derivation** | RFC 8032 / SHA-512 | Derivation of the 32-byte public key and 64-byte secret key from the authenticated seed. |
| **SHA-256** | NIST FIPS 180-4 | Chained block ledger auditing (`previous_hash` → `current_hash`) and IP trees. |
| **ChaCha20** | RFC 8439 | Stream cipher for optional authenticated payload confidentiality. |

#### 11.3.2 Anti-Decompilation and Tamper-Proofing

A recurring question is whether a compiled document can be “decompiled” or modified back into a draft.

1. **State-machine lock.** The C11 engine strictly prevents reverse transitions. Once a document reaches `mode: transfer`, the engine forbids changing `mode` back to `draft`.
2. **Payload hash interlock.** The SHA-512 ledger hash is calculated over every byte of the payload. Changing a single character, space, or newline produces an immediate hash breach detected by `bmd verify`.
3. **Signature invalidation.** The Ed25519 signature signs the SHA-512 digest. Tampering with the payload breaks signature verification instantly.
4. **OS attribute enforcement.** On compile, the file is protected with the read-only attribute (`attrib +R`), preventing external editors from silently modifying it.
5. **No manual signature entry.** The engine never accepts externally crafted or user-typed signatures. All signing material derives from hardware device identity, making forgery structurally impossible.

### 11.4 File Format Specification

A `.bmd` file has two contiguous sections:

1. **YAML frontmatter header** delimited by `---` lines.
2. **Document payload body** written in semantic Markdown with BMD structural directives.

#### 11.4.1 Frontmatter Metadata Schema

```yaml
---
bmd_version: 2.1
document_type: agreement
mode: transfer
jurisdiction: International / Open Standard
max_signatures: 2
timestamp: 1772580000
public_key: 3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29
signature_layer_2: 2109a7b92715aa2f34175add60997db597db644cd841bb95c3a7005f61dc76f9...
receiver_public_key: 8c4d29fe3412ab7891230cdba456ef1234567890abcdef1234567890abcdef12
receiver_signature: 4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b...
current_hash: 09711beb10fee338fced10ec5fac2c8da1820e91fa15e1ac2be40d401a92dda9174c026ec53427ceded9369c791b3be4af74b03cbd1f8e5229368f91f0f75da3
---
```

#### 11.4.2 Field Dictionary

| Field | Type | Required | Description |
|:---|:---|:---|:---|
| `bmd_version` | String | Yes | Protocol specification version (current: `2.1`). |
| `document_type` | String | Yes | Classification: `contract`, `declaration`, `license`, `invoice`, `agreement`, `ip_assignment`, and related types. |
| `mode` | String | Yes | `draft` (mutable) or `transfer` (immutable sealed). |
| `jurisdiction` | String | Yes | Legal framework governing the agreement (for example `International`, `US - Delaware`). |
| `max_signatures` | Integer | Yes | Signature cap: `0` unlimited, `1` unilateral, `2` bilateral, `N` multilateral. |
| `timestamp` | Integer | Yes | Unix epoch timestamp of creation or signing. |
| `public_key` | Hex (64) | On sign | 32-byte Ed25519 public key of the primary signer (Emitter). Auto-computed. |
| `signature_layer_2` | Hex (128) | On sign | 64-byte Ed25519 signature of the Emitter over the SHA-512 payload hash. Auto-computed. |
| `receiver_public_key` | Hex (64) | On cosign | 32-byte Ed25519 public key of the co-signer (Receiver). Auto-computed. |
| `receiver_signature` | Hex (128) | On cosign | 64-byte Ed25519 signature of the Receiver. Auto-computed. |
| `current_hash` | Hex (128) | On sign | SHA-512 hash calculated strictly over the payload content. Auto-computed. |
| `previous_hash` | Hex (128) | Optional | SHA-512 hash of the previous block (defaults to 64 zeros when omitted). |
| `block_id` | String | Optional | Optional legacy label; not required for integrity or identification. |

> All cryptographic fields (`public_key`, `signature_layer_2`, `receiver_public_key`, `receiver_signature`, `current_hash`) are computed automatically by the engine. They are never written by hand.

#### 11.4.3 Document Body and Button Directives

Content uses standard Markdown enhanced with semantic directives that produce consistent professional legal typography in both terminal and HTML rendering.

**Typography tags**

| Tag | Terminal rendering | HTML rendering |
|:---|:---|:---|
| `<title>Text</title>` | Bold white, centered, uppercase, `*** TITLE ***` | 28px / 800 weight, centered, uppercase. |
| `<subtitle>Text</subtitle>` | Dimmed, centered, `-- Subtitle --` | 15px / 500 weight, muted. |
| `<heading>Text</heading>` | Bold, centered, uppercase, `=== HEADING ===` | 18px / 700 weight, uppercase. |
| `<body>Text</body>` | Left-aligned, wrapped at 72 columns. | 14px / 400 weight, justified. |

Standard Markdown headings (`#`, `##`, `###`) map to the same hierarchy automatically.

**Structural directives**

| Directive | Purpose |
|:---|:---|
| `<bmd:sign_button>` | Emitter signature button. In preview, an ASCII frame (display only). In `bmd read` after compile, shows the verified public key and status. Shortcut: `:add sign_button`. |
| `<bmd:cosign_button>` | Receiver co-signature button. Sets `max_signatures = 2` automatically. Shortcut: `:add cosign_button`. |
| `<bmd:rule>` | Double horizontal rule separator (`====================`) across the sheet. |
| `<bmd:rule single>` | Single horizontal rule separator (`--------------------`) across the sheet. |
| `<bmd:parties>` | Two-column table displaying Emitter and Receiver public keys side by side. |
| `<bmd:signatures>` | Verification panel showing Ed25519 signature statuses (`DIGITALLY SEALED` / `RATIFIED`). |
| `<bmd:seal>` | Cryptographic custody seal banner with verified SHA-512 integrity status. |

> Signature buttons in `:preview` are display-only. They render as ASCII framed boxes but execute no action. Only after `bmd compile` are buttons interactive when viewed with `bmd read`.

### 11.5 Complete CLI Reference

The `bmd` command-line utility provides direct access to the C11 engine. All commands support auto-path resolution, UTF-8 console output, and strict exit codes suitable for automation.

#### 11.5.1 Command Summary

```text
================================================================================
  BLOCKCHAIN MARKDOWN (.bmd) COMMAND REFERENCE MANUAL
================================================================================

DOCUMENT VIEWING & VERIFICATION:
  bmd read <file.bmd>                   Render document natively (letter-sheet view)
  bmd <file.bmd>                        Short form: immediately view document
  bmd verify <file.bmd>                 Verify SHA-512 hash & Ed25519 signatures
  bmd verify --json <file.bmd>          Same verification with JSON output
  bmd inspect <file.bmd>                Full block metadata, hashes & signature cap

DRAFTING & REDACT STUDIO:
  bmd redact [file.bmd]                 Open terminal editor (create or edit draft)

SIGNING & IMMUTABILITY:
  bmd sign <file.bmd>                   Sign as Emitter in DRAFT mode (auto device key & SHA-512)
  bmd compile <file.bmd>                Compile, freeze to TRANSFER mode & seal disk
  bmd cosign <file.bmd>                 Receiver co-signs (auto device key)
  bmd lock <file.bmd>                   Apply OS read-only attribute to file

LEDGER AUDIT:
  bmd audit <b1.bmd> [b2.bmd ...]       Audit cryptographic chain of custody

EXPORTS & INTELLIGENT / INTELLECTUAL PROPERTY (IP):
  bmd render <file.bmd> [out.html]      Export standalone zero-dependency HTML viewer
  bmd --inject-property <dir> <bmd>     Inject IP (Intelligent Property) code bundle
  bmd --extract-property <bmd> [--out]  Extract & decrypt IP assets from block
  bmd --export-office <file.bmd>        Export structured JSON metadata for integrations

SHELL & UTILITY:
  bmd                                   Launch interactive BMD shell
  /help, help, -h, --help               Display this command manual
  exit, quit, q                         Exit the interactive shell
================================================================================
```

#### 11.5.2 Detailed Command Specifications

##### `bmd read <file.bmd>`

Renders the `.bmd` file as a framed **Executive Letter-Sheet** directly in the terminal using ASCII-safe borders (`+`, `-`, `|`, `=`).

- Resolves paths automatically across working directories.
- Verifies the SHA-512 hash and Ed25519 signatures on load.
- Renders `<bmd:sign_button>` and `<bmd:cosign_button>` as framed ASCII buttons showing real signature status.
- Renders `<title>` in bold white centered text, `<subtitle>` dimmed and centered, `<heading>` bold uppercase, and `<body>` left-aligned and wrapped.

```bash
bmd read contracts/service_agreement.bmd
# Or simply:
bmd contracts/service_agreement.bmd
```

##### `bmd verify <file.bmd>`

Performs an instant mathematical verification:

1. Recomputes the SHA-512 hash of the payload text.
2. Compares it with the frontmatter `current_hash`.
3. Validates the Emitter’s Ed25519 signature against `public_key`.
4. If co-signed, validates the Receiver’s signature against `receiver_public_key`.

| Exit code | Meaning |
|:---|:---|
| `0` | Authentic, verified, unmodified. |
| `2` | Tamper detected or signature mismatch. |

##### `bmd verify --json <file.bmd>`

Executes verification with structured JSON output for automated integrations and agent loops.

```bash
bmd verify --json contracts/service_agreement.bmd
```

The v2.1 canonical form is `verify --json`; `--verify` remains available as a backwards-compatible alias in the same binary.

##### `bmd inspect <file.bmd>`

Prints a complete forensic audit of the block’s frontmatter, including timestamps, role definitions, signature capacity slots remaining, and an excerpt of the raw payload.

##### `bmd redact [file.bmd]`

Launches **BMD Redact Studio**, an in-terminal visual drafting application. It composes documents, inserts signature-button directives, previews clean letter-sheets, and executes automated compile-and-sign workflows without leaving the terminal.

- With no filename, opens a blank document.
- With a `.bmd` filename, loads it for editing only if it is in `mode: draft`.

##### `bmd sign <file.bmd>`

Signs the document as Emitter in **`mode: draft`**:

- Derives the authentic device identity key from `%USERPROFILE%\.bmd\emitter_device.key`.
- Computes the SHA-512 payload hash automatically.
- Attaches the Ed25519 public key and signature to the frontmatter.
- **Leaves the document in `mode: draft`** so additional clauses or buttons can be added before sealing.

> No manual seed or key input is required or accepted. The SHA-512 hash and Ed25519 signature are always computed from the device’s authentic identity.

##### `bmd compile <file.bmd>`

The definitive sealing step:

- Plays the retro TrueColor purple pixel-gradient loading bar animation across the terminal.
- Recalculates the final SHA-512 ledger hash over the complete payload.
- Permanently sets `mode: transfer`.
- Applies the OS read-only filesystem lock attribute (`attrib +R`).
- Prints the full absolute path of the compiled file:

```text
File         : C:\Users\You\Documents\contracts\service_agreement.bmd
SHA-512 Hash : 0d904b4870ec3b5d...
Pubkey       : 3b6a27bcceb6a42d...
Mode         : TRANSFER (IMMUTABLE SEALED)
Disk Status  : Read-only locked (tamper-proof)
```

##### `bmd cosign <file.bmd>`

Executes counterparty co-signature on a compiled document:

- Checks that the document is already signed by the Emitter.
- Verifies that `max_signatures >= 2`.
- Uses the counterparty device identity key from `%USERPROFILE%\.bmd\receiver_device.key`.
- Transitions the document status to **CONSENSUS RATIFIED**.

##### `bmd lock <file.bmd>`

Sets the OS-level read-only attribute, preventing accidental modification by external editors. `bmd compile` does this automatically; `bmd lock` provides manual control.

##### `bmd audit <b1.bmd> [b2.bmd ...]`

Evaluates a chain of `.bmd` blocks in sequence, verifying that block N’s `previous_hash` equals block N−1’s `current_hash`.

##### `bmd render <file.bmd> [out.html]`

Compiles the `.bmd` file into a self-contained, zero-dependency standalone HTML5 viewer with embedded WebCrypto verification logic, proper legal typography (28px title versus 14px body), and a print-ready stylesheet.

##### `bmd --inject-property <dir> <bmd>`

Packages a source directory into an encrypted ChaCha20 bundle, builds the SHA-256 Merkle tree, and embeds the bundle into the `.bmd` block. The source folder is securely moved/destroyed as part of the True Ownership Transfer workflow.

##### `bmd --extract-property <bmd> [--out <dir>]`

Decrypts and restores the embedded IP bundle from the block into the target directory (defaults to `./extracted_ip`).

##### `bmd --export-office <file.bmd>`

Exports structured JSON metadata for Office and enterprise integrations, including document identity, hashes, signatures, and ledger fields.

##### `bmd` (interactive shell)

Launches the interactive BMD shell. `/help`, `help`, `-h`, and `--help` display the command manual; `exit`, `quit`, and `q` exit the shell.

##### `bmd genkey` (utility)

Generates a new Ed25519 seed and public key pair for controlled test environments. Production signing always uses the device identity keys under `%USERPROFILE%\.bmd\`.

### 11.6 BMD Redact Studio

#### 11.6.1 Studio Architecture and Interface

The Redact Studio provides an authoring environment directly inside standard Windows Command Prompt and PowerShell windows.

```text
  ================================================================================
   BMD REDACT STUDIO  |  contracts/nda.bmd  |  mode: DRAFT (MUTABLE)
  ================================================================================

  Frontmatter:
    type            : contract
    jurisdiction    : International / Open Standard
    max_signatures  : 2  (bilateral - requires Emitter + Receiver)
    emitter_sig     : [SIGNED]  pubkey: 3b6a27bcceb6a42d62a3a8d02a6f0d73653215771...
    receiver_sig    : [AWAITING CO-SIGNATURE]
    SHA-512 hash    : f0510a5105482fd03ceee936f0232031d0139149c44e797fb802891ee0e9e37c
                      8c9f80897931d957110850e647a9c0d7b520c9aba8821eb5391e1185091d7fb7

  Document  (6 lines):
  +--------+--------------------------------------------------------------------+
  |  Line  |  Content                                                           |
  +--------+--------------------------------------------------------------------+
  |      1 | <title>Mutual Non-Disclosure Agreement</title>                     |
  |      2 | <bmd:rule>                                                         |
  |      3 | <body>The parties agree to hold proprietary data confidential.</body>|
  |      4 | <bmd:sign_button>                                                  |
  |      5 | <bmd:cosign_button>                                                |
  |      6 | <bmd:seal>                                                         |
  +--------+--------------------------------------------------------------------+

  ================================================================================
  ACTIONS:
  +-----------------------------+  +-----------------------------+
  |  :sign                      |  |  :compile                   |
  |  Sign with auto device key  |  |  Retro purple loading bar   |
  |  (remains in DRAFT mode)    |  |  Freeze to IMMUTABLE mode   |
  +-----------------------------+  +-----------------------------+

  BUTTONS:  :add sign_button   :add cosign_button
  IP ASSET: :inject <path>     (encrypts folder & embeds into block)
  CONTENT:  :add <tag> text   :insert N <tag> text   :delete N   :set <field> <val>
  UTILITY:  :save [file]  :preview  :list  :verify  :render  :help  :quit
  ================================================================================

  redact>
```

#### 11.6.2 Interactive Button Directives

**In `:preview` (draft — display only):**

```text
  |  +------------------------------------------------------------------+  |
  |  |  [ SIGN AS EMITTER ]   SHA-512 auto-computed  (run :sign)        |  |
  |  +------------------------------------------------------------------+  |
```

```text
  |  +------------------------------------------------------------------+  |
  |  |  [ CO-SIGN AS RECEIVER ]  SHA-512 auto-computed  (run :cosign)   |  |
  |  +------------------------------------------------------------------+  |
```

**In `bmd read` after compile (functionally verified):**

```text
  |  +-- [ BUTTON: SIGN AS EMITTER ] ----------------------------------------+ |
  |  | Status: DIGITALLY SEALED (Ed25519 Verified)                            | |
  |  | Pubkey: 3b6a27bcceb6a42d62a3a8d...                                     | |
  |  +------------------------------------------------------------------------+ |
```

#### 11.6.3 Key Studio Actions

| Action | Behavior |
|:---|:---|
| `:add sign_button` | Appends `<bmd:sign_button>` to the document body. |
| `:add cosign_button` | Appends `<bmd:cosign_button>` and sets `max_signatures = 2`. |
| `:inject <path>` | Injects and encrypts an IP codebase or directory into the current document without exiting the editor. The source folder is securely moved/destroyed (True Ownership Transfer), and the encrypted ChaCha20 bundle is embedded into the block. |
| `:extract [dir]` | Decrypts and restores the IP bundle into the specified directory (defaults to `./extracted_ip`). |
| `:sign` | Signs the draft as Emitter with the automatic device key. Remains in DRAFT mode. |
| `:compile` | Plays the retro purple pixel loading bar, transitions to TRANSFER (IMMUTABLE), locks the file read-only, and prints the full absolute path. |
| `:cosign` | Signs as Receiver with the counterparty device key (only when `max_signatures >= 2`). |

> If the document has no filename when `:sign` or `:compile` is run, the studio asks for a filename interactively. A manual `:save` is not required first.

#### 11.6.4 In-Studio Command Dictionary

| Studio command | Action |
|:---|:---|
| `:help` | Opens the full reference manual and syntax examples. |
| `:add <tag> text` | Appends a new tagged line to the bottom of the document. |
| `:add sign_button` | Inserts the Emitter interactive signature button (`<bmd:sign_button>`). |
| `:add cosign_button` | Inserts the Receiver co-signature button (`<bmd:cosign_button>`) and sets `max_signatures = 2`. |
| `:insert <N> <tag> text` | Inserts a line before line number N (1-based). |
| `:delete <N>` | Deletes line number N. |
| `:set <field> <value>` | Updates a frontmatter field (`type`, `jurisdiction`, `max_signatures`). |
| `:preview` | Displays a clean reading preview with rendered signature buttons and formatted text. |
| `:list` | Displays the complete document with continuous line numbering. |
| `:inject [path]` | Injects and encrypts an IP codebase or folder directly into the document. |
| `:extract [dir]` | Extracts and decrypts the IP bundle into the target folder. |
| `:sign` | Computes the SHA-512 hash and signs as Emitter with the auto device key (remains in DRAFT). |
| `:compile` | Plays the retro purple animation, freezes to TRANSFER mode, locks the file read-only, and prints the full path. |
| `:cosign` | Receiver co-signs with the auto device key (only when `max_signatures >= 2`). |
| `:save [filename.bmd]` | Writes the current buffer and metadata to disk. Optional before `:sign` or `:compile`. |
| `:verify` | Performs an immediate cryptographic audit of the saved file. |
| `:render [out.html]` | Exports the document to a zero-dependency standalone HTML viewer. |
| `:read <file.bmd>` | Opens another `.bmd` file in the studio. |
| `:up` / `:down` / `:top` / `:bottom` | Scrolls the document view. |
| `:quit` / `:q` | Exits the studio (warns if unsaved changes exist). |
| `:quit!` / `:q!` | Forces exit without saving. |

### 11.7 Operational Workflows and Real-World Scenarios

#### Scenario A — Unilateral Declaration (Sole Author)

*Use case: proof of authorship, copyright registration, public declaration.*

1. Open the studio:

```bash
bmd redact my_declaration.bmd
```

2. Set metadata and content:

```text
:set type declaration
:set jurisdiction International
:set max_signatures 1
:add <title>Declaration of Software Authorship</title>
:add <bmd:rule>
:add <body>I hereby declare sole authorship of the enclosed codebase.</body>
:add sign_button
:add <bmd:seal>
```

3. Sign and compile (no manual `:save` required):

```text
:sign
:compile
```

*Result:* the document is cryptographically sealed with the author’s device key and permanently locked in TRANSFER mode. The full file path is displayed.

#### Scenario B — Bilateral Commercial Agreement (Dual-Party Ratification)

*Use case: service contracts, NDAs, partnership agreements.*

1. **Party A (Emitter) drafts, signs, and compiles:**

```text
bmd redact service_agreement.bmd
:set type contract
:set max_signatures 2
:add <title>Master Engineering Agreement</title>
:add <subtitle>Between [Provider] and [Client]</subtitle>
:add <bmd:rule>
:add <heading>1. Terms</heading>
:add <body>[Provider] agrees to maintain cryptographic core infrastructure.</body>
:add sign_button
:add cosign_button
:add <bmd:signatures>
:add <bmd:seal>
:sign
:compile
```

*Result:* the document is compiled into TRANSFER mode. Party A sees the absolute path of the sealed file.

2. **Transmission:** Party A sends `service_agreement.bmd` to Party B.

3. **Party B (Receiver) validates and co-signs:**

```bash
# Party B verifies Party A's signature:
bmd verify service_agreement.bmd

# Party B co-signs with the device key:
bmd cosign service_agreement.bmd
```

*Result:* the document is **CONSENSUS RATIFIED** with both signatures mathematically embedded.

#### Scenario C — Intellectual Property Escrow and Registration

*Use case: sealing proprietary algorithms, models, or confidential codebases.*

##### Method 1 — In-Studio Workflow (Recommended)

Draft the contract, inject the codebase, sign, compile, and extract without leaving Redact Studio.

```text
# 1. Open the studio with the target document:
bmd redact ai_model_escrow.bmd

# 2. Add metadata and legal clauses:
:set type ip_assignment
:add <title>PROPRIETARY AI MODEL ESCROW & ASSIGNMENT</title>
:add <body>The source code bundle encrypted in this block is assigned to the recipient.</body>
:add sign_button
:add <bmd:seal>

# 3. Inject the IP codebase directly (moves the source folder into the block and encrypts it with ChaCha20):
:inject ./src/ai_model

# 4. Sign as Emitter (auto device key and SHA-512 over payload + bundle):
:sign

# 5. Compile to TRANSFER mode (retro purple animation, locks disk read-only):
:compile

# 6. (Optional) Test-extract and verify the code inside the studio:
:extract ./extracted_model

# 7. Exit when finished:
:quit
```

##### Method 2 — Command-Line Batch Workflow

For CI/CD pipelines, automated agents, or terminal scripting.

```bash
# 1. Package and encrypt a source folder into a BMD container (destroys the source on disk):
bmd --inject-property ./src/ai_model ./contracts/ai_model_ip.bmd

# 2. Sign and lock the asset (auto device key, no manual seed):
bmd sign ./contracts/ai_model_ip.bmd
bmd compile ./contracts/ai_model_ip.bmd

# 3. Third parties verify the integrity of the asset:
bmd verify ./contracts/ai_model_ip.bmd

# 4. Decrypt and restore the source code to a destination folder:
bmd --extract-property ./contracts/ai_model_ip.bmd --out ./restored_code
```

#### Scenario D — Corporate Invoice and Ledger Record

*Use case: immutable financial records and invoice chains.*

```bash
# 1. Create the invoice document:
bmd redact invoice_001.bmd
# (set type invoice, add content, add sign_button)
:sign
:compile

# 2. Create a chained follow-up record linked to the previous hash:
bmd redact invoice_002.bmd
# (use `bmd inspect invoice_001.bmd` to get its current_hash, then link via previous_hash)
:sign
:compile

# 3. Audit the chain integrity:
bmd audit invoice_001.bmd invoice_002.bmd
```

### 11.8 C11 Native Core Engine Architecture

#### 11.8.1 Library Components

| Component | Responsibility |
|:---|:---|
| `bmd_crypto.c` | Pure C implementation of Ed25519 (curve25519 operations, scalar multiplication, SHA-512 digests) and the ChaCha20 stream cipher. |
| `bmd_parser.c` | Streaming tokenizer and parser for YAML frontmatter and payload lines. Handles UTF-8 BOM, CRLF, and all frontmatter fields. |
| `bmd_engine.c` | Lifecycle governance: `bmd_parse_file`, `bmd_transition_to_transfer`, `bmd_sign_document`, `bmd_cosign_receiver`, `bmd_verify_document`, `bmd_save_file`. |
| `bmd_ledger.c` | Multi-block chain verification and Merkle tree generation for IP asset bundles. |
| `bmd_main.c` | High-performance CLI, ANSI color banner, retro purple loading bar, in-terminal Redact Studio, typography helpers, and device identity key management. |
| `bmd_viewer_generator.py` | Zero-dependency standalone HTML generator with embedded WebCrypto, legal CSS typography, and a print stylesheet. |

#### 11.8.2 Compiling and Running Native Unit Tests

To build the engine DLL and CLI on Windows with Microsoft Visual C++:

```cmd
cd bmd_engine
build_full.bat
```

The build script automatically:

1. Compiles `bmd_engine.dll` (shared library).
2. Compiles and runs `test_engine.exe` with five comprehensive C11 unit tests: SHA-256, SHA-512, Ed25519, ChaCha20, and the BMD document lifecycle with tamper detection.
3. Compiles `bmd.exe` and installs it to `%LOCALAPPDATA%\Microsoft\WindowsApps\` for global access.

Expected success output:

```text
[SUCCESS] ALL NATIVE C11 TESTS PASSED WITH 100% INTEGRITY!
```

#### 11.8.3 Build Artifacts

| Artifact | Purpose |
|:---|:---|
| `bmd_engine/bin/bmd_engine.dll` | Shared native engine loaded through FFI. |
| `bmd_engine/bin/bmd_cli.exe` | Command-line interface used by the BMD expert. |
| `bmd_engine/bin/bmd.exe` | Alternate CLI binary. |
| `bmd_engine/bin/test_engine.exe` | Native unit-test runner. |
| `bmd_engine/include/*.h` | Public C headers. |
| `bmd_engine/python/bmd_ffi.py` | Python ctypes bindings. |
| `bmd_engine/python/bmd_property.py` | Property injection and extraction helpers. |
| `bmd_engine/python/bmd_native_viewer.py` | Native viewer helpers. |
| `bmd_engine/python/bmd_viewer_generator.py` | Standalone HTML viewer generator. |
| `bmd_engine/python/bmd_studio_app.py` | Studio application helper. |
| `bmd_engine/python/bmd_agent_executor.py` | Agent-facing BMD executor. |
| `bmd_engine/python/bmd_redact_generator.py` | Draft generator. |
| `bmd_engine/examples/*.bmd` | Reference documents and ledger examples. |
| `bmd_engine/tests/test_engine.c` | Native C test suite. |
| `bmd_engine/tests/test_ffi.py` | FFI tests. |
| `bmd_engine/tests/test_crossvalidate.py` | Cross-validation tests. |
| `bmd_engine/tests/test_seal_unseal.py` | ChaCha20 seal/unseal tests. |

### 11.9 Enterprise Best Practices and Security Advisory

1. **Deterministic device keys.** Back up `%USERPROFILE%\.bmd\` if persistent device identity across OS reinstalls is required. Losing this directory means future signing generates a new identity key.
2. **Canonical authority.** Always treat the `.bmd` file as the primary source of truth. If a dispute arises, verify it with `bmd verify <file.bmd>`. HTML and terminal renders are for human convenience only.
3. **Draft before sealing.** Use `bmd sign` (or `:sign`) while drafting to authenticate without freezing. Execute `bmd compile` (or `:compile`) only when all terms and button directives are final.
4. **Verify before co-signing.** Party B should always run `bmd verify <file.bmd>` before `bmd cosign`, confirming that Party A’s signature is authentic and the content is unaltered.
5. **Offline independence.** The `bmd` runtime requires no internet connection, cloud API, or external server. All cryptographic calculations occur locally.
6. **File path tracking.** After each `bmd compile`, keep the printed absolute path as the canonical record locator.
7. **Bilateral governance.** For any contract between two parties, set `max_signatures: 2` and include both `:add sign_button` and `:add cosign_button` so both signatures are visually represented and cryptographically enforced.

---

## 12. BMD Inside Orunex

Blockchain Markdown is not a separate utility bolted onto the agent. It is a first-class deterministic capability with a dedicated expert, a knowledge pack, artifact cards, and a zero-latency routing path.

### 12.1 The BMD Expert

`src/_orunex_libs/bmd_expert.py` is deliberately independent from the language model. Every operation either runs the real `bmd_engine/bin/bmd_cli.exe` or loads the real `bmd_engine.dll` through `bmd_ffi.py`. Nothing is simulated.

The expert can:

- Create valid `.bmd` drafts with the C11 engine computing the hash.
- Verify, inspect, render, export, and audit real files.
- Sign drafts and co-sign sealed blocks with device keys or explicit seeds for controlled tests.
- Build hash-linked chains.
- Answer deterministic BMD orders without a model round-trip.
- Generate professional contract drafts with a clause library.

The public entry point is `handle_request(text)`. It returns `None` when the text is not a concrete BMD action, so normal conversation can answer questions with the knowledge pack.

### 12.2 Natural-Language BMD Intents

| Intent | Example request | Operation |
|:---|:---|:---|
| **Create** | “Create a BMD contract for a software license.” | Build a draft with frontmatter, clauses, and signature directives; compute the hash with the engine. |
| **Verify** | “Verify `contracts/nda.bmd`.” | Run `bmd verify` and report the result. |
| **Inspect** | “Inspect `contracts/nda.bmd`.” | Run `bmd inspect` and summarize metadata, hashes, and signature capacity. |
| **Render** | “Render this BMD as HTML.” | Run `bmd render` and return the standalone viewer path. |
| **Export** | “Export the Office metadata for this BMD.” | Run `bmd --export-office` and return structured JSON. |
| **Audit** | “Audit the invoice chain.” | Run `bmd audit` over the selected files and report continuity. |
| **Sign** | “Sign this draft.” | Run the engine’s sign operation in draft with the device key; the document remains mutable and ready for an explicit compilation step. |
| **Co-sign** | “Co-sign the agreement as receiver.” | Run `bmd cosign` when `max_signatures >= 2`. |
| **Lock** | “Apply the read-only lock.” | Run `bmd lock`. |
| **Property inject** | “Inject this source folder into the BMD.” | Run `bmd --inject-property` with ChaCha20 encryption and the Merkle tree. |
| **Property extract** | “Extract the IP bundle.” | Run `bmd --extract-property` into the target directory. |
| **Explain** | “What is the BMD signature lifecycle?” | Answer from the verified knowledge pack; no action is executed. |

Compilation is the explicit sealing step: it is performed with `bmd compile` or `:compile` in Redact Studio. The chat expert authenticates a draft and never silently freezes it.

A pure question is never turned into a real signature or audit action. The expert distinguishes explanation from execution with explicit action patterns.

### 12.3 The `[BMD: ...]` Tag

The OS executor recognizes `[BMD: instruction]` tags produced by the model or by a skill. The tag is parsed and routed to the BMD expert, which executes the real engine operation and returns a result.

```text
[BMD: verify contracts/service_agreement.bmd]
[BMD: render contracts/service_agreement.bmd out/service_agreement.html]
[BMD: audit contracts/invoice_001.bmd contracts/invoice_002.bmd]
```

The expert returns a structured result with:

| Field | Meaning |
|:---|:---|
| `handled` | Whether the request was a concrete BMD action. |
| `intent` | `create`, `verify`, `inspect`, `render`, `export`, `audit`, `co-sign`, `compile-sign` (the internal sign-path label), or `error`. |
| `ok` | Whether the engine operation succeeded. |
| `message` | Human-readable summary. |
| `path` | The resulting or inspected file. |
| `artifact` | Artifact metadata for the UI card. |
| `data` | Parsed engine output. |

### 12.4 BMD Knowledge Pack

The 21-entry pack described in Section 7.5 is synchronized into FAISS at startup. It gives the agent precise, consistent answers about:

- The 128-hex SHA-512 hash and why it is not SHA-256.
- The `draft` versus `transfer` state machine.
- The `sign` versus `compile` separation.
- Ed25519 key and signature lengths.
- `max_signatures` governance.
- Device key locations.
- CLI commands and exit codes.
- Redact Studio commands.
- Property injection and extraction.
- Ledger auditing.
- HTML rendering.
- Office export.
- Security guarantees.
- Orunex integration tags.

The pack is versioned (`bmd-engine-2.1.0/orunex-pack-3`) and idempotent, so re-synchronization does not create duplicate memories.

### 12.5 Professional Contract Clause Library

The BMD expert can generate contract drafts with professional clauses. The library covers:

| Document family | Typical sections |
|:---|:---|
| **Commercial services** | Parties, background, definitions, scope, deliverables, fees, payment, term and termination, confidentiality, intellectual property, warranties, liability, indemnity, force majeure, governing law, notices, entire agreement, signatures. |
| **NDA** | Parties, purpose, definition of confidential information, obligations, exclusions, term, return or destruction, remedies, governing law, signatures. |
| **IP assignment / transfer** | Parties, background, definitions, transferred assets, ownership, consideration, moral rights, warranties, further assurances, confidentiality, governing law, signatures. |
| **License** | Parties, grant, scope, restrictions, fees, royalties, term, termination, audit, warranties, liability, governing law, signatures. |
| **Invoice / ledger record** | Issuer, recipient, reference, line items, totals, payment terms, ledger linkage, signature. |
| **Declaration** | Author, work, ownership statement, date, signature. |

The clause library uses **bracketed placeholders** for parties, amounts, dates, jurisdictions, and notice periods. It does not invent parties, figures, or dates. The user or the organization fills in the specifics; the engine hashes and seals the final text.

### 12.6 BMD Artifact Cards

When a BMD operation completes, the UI renders an artifact card with:

- The BMD file type and title.
- The absolute path.
- The operation result (created, verified, rendered, audited).
- An **Open** action that launches the native viewer or the generated HTML.
- A **Show in Explorer** action.

The card is produced from the `artifact` metadata returned by the expert, using `artifact_studio.artifact_tag(path, "bmd", title)`.

### 12.7 CLI Entry Points and the Background Terminal

Orunex ships several ways to reach the BMD engine:

| Entry point | Use |
|:---|:---|
| `bmd` (installed) | Global command after `build_full.bat`. |
| `bmd_engine\bin\bmd_cli.exe` | Direct engine CLI used by the expert. |
| `bmd.bat` | Convenience launcher from the repository root. |
| `bmd.exe` | Alternate root binary. |
| `bmd redact` | In-terminal Redact Studio. |
| `bmd_redact_studio.html` | Standalone browser companion for visual drafting. |

The BMD expert invokes the CLI in a background process with `CREATE_NO_WINDOW`, captures stdout/stderr, enforces a timeout, and returns a structured `BMDResult`. The agent can therefore run BMD operations while the chat remains responsive, and the operation is visible in the activity log.

### 12.8 Python FFI and Native Helpers

| Module | Capability |
|:---|:---|
| `bmd_engine/python/bmd_ffi.py` | ctypes bindings to `bmd_engine.dll` for parse, sign, verify, seal, unseal, and ledger operations. |
| `bmd_engine/python/bmd_property.py` | Property injection, extraction, Merkle tree, and ChaCha20 bundle handling. |
| `bmd_engine/python/bmd_native_viewer.py` | Native viewer integration. |
| `bmd_engine/python/bmd_viewer_generator.py` | Standalone HTML viewer generation with WebCrypto verification. |
| `bmd_engine/python/bmd_studio_app.py` | Studio application support. |
| `bmd_engine/python/bmd_agent_executor.py` | Agent-facing execution helpers. |
| `bmd_engine/python/bmd_redact_generator.py` | Draft and redact generation. |

The FFI path is used for operations that require direct engine access, such as ChaCha20 sealing and unsealing. The CLI path is used for user-facing commands and for operations whose output is already structured for display.

### 12.9 Office Export

`bmd --export-office <file.bmd>` produces structured JSON metadata for enterprise integrations. The export includes:

- Document identity and type.
- Mode and jurisdiction.
- Timestamps.
- Public keys and signature status.
- Current and previous hashes.
- Signature capacity and remaining slots.
- Ledger fields.

The BMD expert parses this JSON and returns it as structured data, so an Office workflow, a downstream ledger, or an enterprise system can consume the record without parsing terminal output.

### 12.10 BMD Examples in the Repository

| Example | Purpose |
|:---|:---|
| `bmd_engine/examples/demo_contrato.bmd` | Demonstration contract. |
| `bmd_engine/examples/draft_contract_example.bmd` | Draft contract with directives. |
| `bmd_engine/examples/genesis_block.bmd` | Genesis ledger block. |
| `bmd_engine/examples/ip_transfer_demo.bmd` | IP transfer and property bundle. |
| `bmd_engine/examples/proof_of_concept_draft.bmd` | Draft proof of concept. |
| `bmd_engine/examples/proof_of_concept_FINAL.bmd` | Compiled proof of concept. |
| `bmd_engine/examples/testamento_ejemplo.bmd` | Testament-style declaration example. |
| `bmd_engine/office_reports/*.csv` | Ledger audit exports. |
| `bmd_engine/office_reports/*.html` | Executive decree exports. |

These examples are useful for demonstrations, regression checks, and understanding the relationship between drafts, compiled blocks, and chained ledgers.

---

## 13. Configuration

### 13.1 Configuration Sources

Orunex resolves configuration in this order:

1. Environment variables loaded from `.env` (via the project’s environment loader).
2. Process environment variables.
3. Safe defaults in `core/config.py`.
4. Local UI preferences stored by the desktop app (`orunex_config.json` and related files).
5. Simplex bridge preferences stored in `config/simplex.json`.

The `.env` file is local and must never be committed with a real key. `.env.example` is the reference template.

### 13.2 Meta Muse Configuration

| Variable | Default | Purpose |
|:---|:---|:---|
| `META_API_KEY` | — | Bearer key for the Meta API. Required. |
| `META_API_BASE` | `https://api.meta.ai/v1` | OpenAI-compatible API base. |
| `META_MODEL` | `muse-wonder-1.0` | Primary reasoning model. Must begin with `muse-`. |
| `META_API_TIMEOUT` | `120` | Request timeout in seconds. |
| `META_MAX_TOKENS` | `8192` | Primary response ceiling. |
| `META_TEMPERATURE` | `0.3` | Sampling temperature. |
| `META_REASONING_EFFORT` | `high` | Primary reasoning effort. |
| `META_FAST_MODEL` | `muse-spark-1.3` | Fast routing model. |
| `META_FAST_MAX_TOKENS` | `2048` | Fast response ceiling. |
| `META_FAST_REASONING_EFFORT` | `low` | Fast reasoning effort. |
| `META_AI_VISION_MODEL` | `muse-spark-1.3` | Screen-vision model. |
| `META_VISION_REASONING_EFFORT` | `minimal` | Vision reasoning effort. |
| `META_ASR_ENDPOINT` | `https://api.meta.ai/v1/asr/transcribe` | Speech-to-text endpoint. |
| `META_ASR_MODEL` | `muse-voice-transcribe-1.0` | Speech-to-text model. |

### 13.3 Workspace and Android

| Variable | Default | Purpose |
|:---|:---|:---|
| `AGENT_WORKSPACE` | repository root | Workspace indexed by FAISS and available for patching. |
| `ANDROID_PROJECT_DIR` | `<repo>/android` | Gradle project for the companion app. |
| `ANDROID_PACKAGE` | `com.orunex.mobile` | Package name used by ADB. |
| `ANDROID_ACTIVITY` | auto-detected | Main activity used after install. |
| `ADB_PATH` | `adb` on `PATH` | Absolute path to `adb.exe`. |
| `ADB_SERIAL` | first ready device | Target device serial. |
| `ANDROID_AVD` | — | AVD to auto-start when no device is ready. |
| `DEMO_AVD` | — | Backwards-compatible alias for the demo AVD. |

### 13.4 Memory and Autonomy

| Variable | Default | Purpose |
|:---|:---|:---|
| `FAISS_INDEX_PATH` | `data/hackathon_memory.index` | Persistent memory index. |
| `AGENT_AUTO_APPLY_FIXES` | `false` | Apply exact patches with backup and diff. |
| `AGENT_MAX_PATCH_REPLACEMENTS` | `3` | Maximum replacements per patch. |
| `ORUNEX_STRICT_PERM` | `1` | Confirmation-gated permissions. |
| `ORUNEX_ALLOW_DANGEROUS` | `0` | Allow dangerous actions without a UI callback. |
| `ORUNEX_AGENT_MAX_TOOL_CALLS` | `6` | Agent-loop tool-call ceiling. |
| `ORUNEX_AGENT_MAX_STEPS` | `8` | Agent-loop step ceiling. |
| `ORUNEX_AGENT_TIME_BUDGET` | `120` | Agent-loop wall-clock budget (seconds). |
| `ORUNEX_AGGRESSIVE` | `0` | Relax mode and permission guards. |
| `ORUNEX_VERBOSE` | `0` | Print environment summary at startup. |
| `ORUNEX_AUTO_HEAL` | `1` | Enable automatic recovery. |
| `ORUNEX_MEM_RECORD` | `1` | Record task episodes automatically. |

### 13.5 Simplex

| Variable | Default | Purpose |
|:---|:---|:---|
| `SIMPLEX_ENABLED` | `false` | Enable the Simplex bridge. |
| `SIMPLEX_WS_URL` | `ws://127.0.0.1:5227` | Local Simplex CLI WebSocket. |
| `SIMPLEX_CONTACT` | last paired contact | Allowlisted remote contact. |
| `REMOTE_DUPLICATE_WINDOW_S` | `90` | Duplicate-message suppression window. |

### 13.6 TradingView and Paper Trading

| Variable | Default | Purpose |
|:---|:---|:---|
| `TRADINGVIEW_ENABLED` | `true` | Enable the TradingView bridge. |
| `TRADINGVIEW_APP_ID` | auto-detected | TradingView application ID. |
| `TRADINGVIEW_EXE` | auto-detected | TradingView executable. |
| `TRADINGVIEW_CHART_BASE_URL` | `https://www.tradingview.com/chart/` | Chart URL base. |
| `TRADINGVIEW_LAUNCH_TIMEOUT_S` | `25` | Launch confirmation timeout. |
| `TRADINGVIEW_CAPTURE_CHART` | `true` | Capture the chart for vision. |
| `TRADINGVIEW_GUI_ENABLED` | `true` | Enable the native GUI executor. |
| `TRADINGVIEW_GUI_MAX_STEPS` | `26` | Maximum GUI actions per ticket. |
| `TRADINGVIEW_GUI_TIMEOUT_S` | `420` | GUI execution timeout. |
| `PAPER_INITIAL_BALANCE` | `10000` | Simulated starting balance. |
| `PAPER_CURRENCY` | `USD` | Simulated account currency. |
| `MAX_RISK_PER_TRADE_PCT` | `1.0` | Maximum risk per trade. |
| `MAX_POSITION_PCT` | `20.0` | Maximum position size. |
| `MIN_TRADE_CONFIDENCE` | `0.70` | Autonomous confidence floor. |
| `EXPLICIT_TRADE_MIN_CONFIDENCE` | `0.50` | Explicit-order confidence floor. |
| `EXPLICIT_TRADE_DECISION_ATTEMPTS` | `3` | Explicit-order retry count. |
| `PAPER_DUPLICATE_WINDOW_S` | `900` | Duplicate-exposure window. |
| `PAPER_STATE_PATH` | `data/paper_trading.json` | Paper-account state file. |

### 13.7 Virtual Input and Live Debug

| Variable | Default | Purpose |
|:---|:---|:---|
| `ORUNEX_VIRTUAL_INPUT` | `1` | Use Orunex’s own pointer and Unicode keyboard. |
| `ORUNEX_VIRTUAL_CURSOR` | `1` | Show the visible agent pointer. |
| `ORUNEX_GHOST_CLICK` | `1` | Hide the system cursor briefly during clicks. |
| `ORUNEX_INPUT_SPEED` | `1.0` | Pointer travel and typing cadence multiplier. |
| `ORUNEX_INPUT_HUMAN` | `1` | Human-like typing jitter and pauses. |
| `ORUNEX_LIVE_DEBUG` | `0` | Print Live lifecycle diagnostics. |
| `ORUNEX_DEMO_CHART` | — | Use a controlled chart for rehearsal. |

### 13.8 Configuration Validation

`Settings.validate()` returns a list of human-readable problems. It checks:

- The Meta API key is present.
- The primary and fast models are Muse models.
- `META_MAX_TOKENS` is at least 1024.
- The workspace exists.
- Risk per trade is in `(0, 5]`.
- Confidence floors are in `(0, 1]`.
- Explicit attempts are at least 1.
- TradingView timeouts and step counts are positive.
- Duplicate windows are non-negative.

`python app.py --check` prints the full diagnostics report, including bridge health, memory statistics, and Meta health.

---

## 14. Installation and Launch

### 14.1 Prerequisites

| Requirement | Version / Notes |
|:---|:---|
| Windows | Windows 10 or Windows 11. |
| Python | 3.12 recommended (the project is developed against 3.12). |
| Meta API key | Required for reasoning, vision, ASR, and trading decisions. |
| Visual C++ | Required only to rebuild the C11 BMD engine. |
| Android SDK | Required only to build or install the companion app. |
| TradingView Desktop | Required only for chart analysis and paper execution. |
| Simplex Chat CLI | Required only for remote control. |

### 14.2 Python Dependencies

```bash
python -m pip install -r src/requirements.txt
```

Or, for the hackathon environment:

```bash
python -m pip install -r requirements-hackathon.txt
```

Core dependencies include:

| Package | Purpose |
|:---|:---|
| `customtkinter` | Desktop UI. |
| `pillow` | Image handling and composer rendering. |
| `pyautogui` | Desktop automation fallback. |
| `fpdf2` | PDF generation. |
| `python-docx` | Word generation. |
| `openpyxl` | Excel generation. |
| `python-pptx` | PowerPoint generation. |
| `opencv-python` | Vision utilities. |
| `requests` | HTTP client. |
| `websocket-client` | Simplex bridge. |
| `qrcode[pil]` | Pairing QR codes. |
| `psutil` | System status. |
| `faiss-cpu` | Vector memory. |
| `numpy` | Vector operations. |
| `sounddevice` | Live microphone capture. |
| `edge-tts` | Neural voice. |
| `ddgs` | Headless search. |
| `pygame` | Audio playback. |

### 14.3 Environment Setup

```bash
copy .env.example .env
```

Edit `.env` and set at least:

```dotenv
META_API_KEY=your_key_here
META_MODEL=muse-wonder-1.0
META_FAST_MODEL=muse-spark-1.3
```

Do not commit `.env`.

### 14.4 BMD Engine Build

```cmd
cd bmd_engine
build_full.bat
```

The script builds the DLL, runs the native C11 tests, builds the CLI, and installs `bmd.exe` to `%LOCALAPPDATA%\Microsoft\WindowsApps\`.

If the prebuilt binaries in `bmd_engine/bin/` are already present, the agent can use them without rebuilding.

### 14.5 Android Build

```bash
cd android
./gradlew assembleDebug
```

On Windows:

```powershell
cd android
.\gradlew.bat assembleDebug
```

Install:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### 14.6 Launch the Desktop Application

**Recommended:** double-click `Lanzar_Orunex_Windows.vbs` or the desktop shortcut `C:\Users\Hp\Desktop\Orunex.lnk`.

The shortcut always opens the application maximized. The launcher runs:

```text
pythonw.exe src\main.py
```

with a maximized window style, and the application also calls `self.state("zoomed")`.

**Manual launch:**

```bash
pythonw.exe src\main.py
```

or, with a console for diagnostics:

```bash
python src/main.py
```

### 14.7 Headless Agent

```bash
python app.py
```

The headless backend is the delegation target. It exposes:

| Flag | Purpose |
|:---|:---|
| `--check` | Print diagnostics and exit. |
| `--index-code` | Index the workspace into FAISS, then exit. |
| `--demo-paper` | Run one paper-trading decision, then exit. |
| `--warmup` | Open the emulator and TradingView, then exit. |
| `--command "!fix ..."` | Rehearse one Simplex-style remote order locally. |
| `--tradingview SYMBOL` | Open a symbol in TradingView and confirm the chart. |
| `--alert JSON` | Provide a TradingView-style alert payload for `--demo-paper`. |

Example:

```bash
python app.py --check
python app.py --index-code
python app.py --demo-paper --alert "{\"symbol\":\"BTCUSDT\",\"side\":\"BUY\",\"price\":67000,\"rsi\":61,\"ema_trend\":\"up\"}"
python app.py --command "!status"
python app.py --tradingview BTCUSDT
```

### 14.8 First-Run Checklist

1. Set `META_API_KEY` in `.env`.
2. Run `python app.py --check` and confirm Meta health.
3. Run `python app.py --index-code` to populate FAISS.
4. Launch the desktop app and confirm the maximized window.
5. Open **Settings → Profile** and set the display name.
6. Open **Settings → Connections** and connect VS Code if desired.
7. Open **Simplex Bridge** and pair a phone if remote control is desired.
8. Open **Settings → Knowledge Hub** and ingest any JSON or PDF knowledge.
9. Open **Settings → Engine** and confirm retries, context window, and recovery preferences.
10. Run a first chat request and a first artifact request.

### 14.9 Desktop Shortcut Guarantee

The shortcut is intentionally a thin wrapper around the root VBS launcher. This design has three benefits:

- The shortcut works regardless of the current working directory.
- The process starts with `pythonw.exe`, so no console window appears.
- The window style and the application’s own `zoomed` call both enforce a maximized launch.

If the shortcut is recreated, point it to:

```text
Target: C:\Windows\System32\wscript.exe
Arguments: "C:\Users\Hp\Downloads\Project_Orunex\Lanzar_Orunex_Windows.vbs"
Start in: C:\Users\Hp\Downloads\Project_Orunex
```

---

## 15. Repository Map

```text
Project_Orunex/
├─ app.py                          Headless agent backend and diagnostics
├─ src/
│  ├─ main.py                      Desktop application and Live mode
│  ├─ requirements.txt             Python dependencies
│  ├─ agents/
│  │  ├─ cerebro.py                Muse reasoning nucleus
│  │  ├─ supervisor.py             Agent selection and recovery
│  │  └─ universal.py              Shared agent helpers
│  ├─ _orunex_libs/
│  │  ├─ bmd_expert.py             Real BMD CLI/FFI expert
│  │  ├─ bmd_knowledge.py          21-entry BMD knowledge pack
│  │  ├─ artifact_studio.py        Deterministic document generation
│  │  ├─ office_expert.py          Research-backed Office engine
│  │  ├─ mode_router.py            Chat mode detection and prompts
│  │  ├─ live_vision.py            Screen capture and Meta vision
│  │  ├─ live_audio.py             Microphone capture and ASR
│  │  ├─ live_tts.py               Neural voice and SAPI fallback
│  │  ├─ os_executor.py            Tag parser and OS execution
│  │  ├─ agentic_loop.py           Bounded tool loop
│  │  ├─ agent_tools.py            Allow-listed tool registry
│  │  ├─ auto_healer.py            Deterministic + Muse repair
│  │  ├─ simplex_bridge.py         Production Simplex bridge
│  │  ├─ headless_web.py           DDGS search and summarization
│  │  ├─ chrome_driver.py          Chrome profile automation
│  │  ├─ permissions.py            Permission gate
│  │  ├─ knowledge_processor.py    JSON/PDF ingestion
│  │  ├─ intent_router.py          Browser and command intents
│  │  ├─ virtual_input.py          Orunex pointer and keyboard
│  │  ├─ theme.py                  Visual tokens
│  │  └─ ...                       Document, Office, media, and utility engines
│  ├─ integrations/
│  │  ├─ vscode_bridge.py          VS Code HTTP bridge
│  │  ├─ vscode_integration.py     VS Code launch and edit helpers
│  │  └─ social_media.py           Social and messaging actions
│  └─ widgets/                     Animated gradient, Live button, UI widgets
├─ core/
│  ├─ agent_brain.py               Orchestrator and thread pool
│  ├─ config.py                    Immutable settings
│  ├─ events.py                    Event bus
│  ├─ faiss_memory.py              384-d persistent vector memory
│  ├─ meta_api.py                  Meta Muse client
│  └─ trade_intent.py              Natural-language trade detection
├─ tasks/
│  ├─ base.py                      Task state and result
│  ├─ bugfix_task.py               Android repair pipeline
│  ├─ trading_task.py              Paper-trading pipeline
│  └─ tradingview_gui.py           Native TradingView GUI executor
├─ bridges/
│  ├─ adb_bridge.py                Android device bridge
│  ├─ simplex_bridge.py            Simplex WebSocket listener
│  ├─ tradingview_bridge.py        TradingView launcher
│  └─ vscode_bridge.py             Guarded editor bridge
├─ android/
│  ├─ app/src/main/java/com/orunex/mobile/MainActivity.java
│  ├─ app/src/main/assets/app.js
│  ├─ app/src/main/assets/index.html
│  ├─ app/src/main/assets/styles.css
│  ├─ app/src/main/assets/qrcode.js
│  ├─ app/build.gradle
│  └─ gradlew.bat
├─ bmd_engine/
│  ├─ bin/                         DLL, CLI, test runner
│  ├─ include/                     C headers
│  ├─ src/                         C11 engine sources
│  ├─ python/                      FFI, property, viewer, studio helpers
│  ├─ examples/                    Reference BMD documents
│  ├─ tests/                       Native and Python tests
│  └─ build_full.bat               Full build and native test run
├─ data/
│  ├─ hackathon_memory.index       FAISS index
│  ├─ hackathon_memory.index.meta.json
│  └─ paper_trading.json           Paper account state
├─ demo/
│  ├─ charts/                      Reference charts for demos
│  ├─ record_demo.py               Demo recorder
│  └─ ...                          Rehearsal fixtures
├─ docs/                           Architecture, security, and design notes
├─ tests_hackathon/
│  └─ test_agent.py                51 automated checks
├─ config/simplex.json             Simplex bridge preferences
├─ Lanzar_Orunex_Windows.vbs       Maximized launcher
├─ BMD manual.md                   Authoritative BMD specification
├─ README.md                       This document
├─ bmd.bat / bmd.exe               BMD convenience launchers
├─ bmd_redact_studio.html          Standalone browser studio
├─ .env.example                    Configuration template
└─ requirements-hackathon.txt      Hackathon dependency set
```

---

## 16. Example Use Cases

### 16.1 Create a BMD Contract from Chat

**Request:**

> Create a bilateral NDA in Blockchain Markdown for a software evaluation, with signature and co-signature buttons.

**What Orunex does:**

1. Routes to the BMD expert before the model.
2. Selects the NDA clause family.
3. Builds frontmatter with `type: contract`, `max_signatures: 2`, and a professional clause set.
4. Inserts `<bmd:sign_button>`, `<bmd:cosign_button>`, `<bmd:signatures>`, and `<bmd:seal>`.
5. Writes the `.bmd` draft and computes the SHA-512 hash with the C11 engine.
6. Returns a BMD artifact card with the path.

**Next steps:**

```bash
bmd sign contracts/nda.bmd
bmd compile contracts/nda.bmd
bmd verify contracts/nda.bmd
```

The counterparty runs `bmd verify` and then `bmd cosign`.

### 16.2 Seal and Audit an IP Bundle

```bash
bmd --inject-property ./src/ai_model ./contracts/ai_model_ip.bmd
bmd sign ./contracts/ai_model_ip.bmd
bmd compile ./contracts/ai_model_ip.bmd
bmd verify ./contracts/ai_model_ip.bmd
bmd --extract-property ./contracts/ai_model_ip.bmd --out ./restored_code
bmd audit ./contracts/ai_model_ip.bmd
```

This workflow demonstrates True Ownership Transfer: the source directory is packaged, encrypted with ChaCha20, embedded in the block, and recoverable only through the engine.

### 16.3 Paper Trade from Simplex

**Remote message:**

```text
!trade {"symbol":"BTCUSDT","side":"BUY","price":67000,"rsi":61,"ema_trend":"up"}
```

**What happens:**

1. The Simplex listener normalizes the message and checks the contact allowlist.
2. The duplicate suppressor checks the 90-second window.
3. The trading task recalls strategies from FAISS.
4. Muse returns a BUY/SELL decision with entry, stop loss, and take profit.
5. The deterministic risk gate validates the order.
6. The GUI agent captures TradingView, confirms the Paper Trading panel, fills the ticket, and verifies the values.
7. The paper engine records the position.
8. Simplex receives a structured confirmation.

**Natural-language equivalent:**

> Open a paper long on BTCUSDT with a stop below the recent swing low.

### 16.4 Android Repair from Live

**Spoken request:**

> Orunex, the login button on the Android app does nothing. Fix it.

**What happens:**

1. Live transcribes the request.
2. The delegation detector starts `!fix`.
3. ADB captures the device screen.
4. Muse diagnoses the visible state.
5. FAISS finds the most likely source files.
6. Muse selects the file and the exact patch.
7. The VS Code bridge backs up the file, applies the patch, and produces a diff.
8. ADB rebuilds, installs, and restarts the app.
9. Muse verifies the new screenshot.
10. The episode is stored in FAISS.
11. The result is spoken and shown in chat.

### 16.5 Research and Build a Deck

**Request:**

> Research the current state of edge AI chips and build a 10-slide executive presentation with a market comparison.

**What happens:**

1. Deep Research mode is selected or auto-detected.
2. Headless search retrieves sources and extracts text.
3. Muse synthesizes findings, counterarguments, and next steps.
4. The Office expert builds a single plan.
5. PowerPoint output includes a cover, agenda, executive summary, context, findings, a native chart, a metrics table, risks, a roadmap, recommendations, and a closing slide.
6. The deck is saved as a real `.pptx` and rendered as an artifact card.

### 16.6 Agent Swapping

**Request:**

> Use several specialists to design a launch plan: product, marketing, finance, and risk. Merge the best result.

**What happens:**

1. Agent Swapping mode is detected.
2. The task is split into specialist roles.
3. Each role contributes its analysis.
4. The results are compared and merged.
5. The final answer includes an explicit execution plan and the rationale for the merged choice.

### 16.7 Live Screen Question

**Spoken request:**

> What is on my screen right now?

**What happens:**

1. Live captures a fresh frame.
2. Meta vision describes the active application, visible content, and actionable elements.
3. The answer is spoken and displayed.
4. No executor tag is produced, so the agent does not click anything.

### 16.8 Artifact from a Single Sentence

**Request:**

> Create an Excel budget for a three-month marketing campaign with channels, spend, and expected return.

**What happens:**

1. Artifact Studio detects `xlsx` and a creation intent.
2. It extracts the title and structured metrics.
3. It writes a styled workbook with headers, rows, and summary formulas.
4. The UI renders an artifact card with Open and Show in Explorer.

### 16.9 Memory Recall

**Request:**

> What did we decide about the BTC risk limits last time?

**What happens:**

1. FAISS recalls related `strategy` and `episode` memories.
2. Muse receives the recalled context.
3. The answer cites the prior decision and the current configured limits.

---

## 17. Verification and Test Coverage

The hackathon suite contains **51 automated checks** in `tests_hackathon/test_agent.py`. It is organized around the behaviors that matter most for a trustworthy agent.

| Test group | Coverage |
|:---|:---|
| **Meta API** | JSON extraction from fenced replies; rejection of non-Muse models; Muse Spark chat; Wonder budget and high effort; per-call fast-model override; truncated-response retry preserving effort; reasoning cleanup that preserves Markdown and removes action tags. |
| **Cerebro output** | Output cleaning and formatting. |
| **FAISS and patching** | Code indexing and lookup; patch guardrails; end-to-end patch and verify. |
| **Android repair** | Task construction with fake ADB and Meta collaborators. |
| **Paper trading** | Position sizing and validation; task opens a paper order and notifies; explicit-order threshold; autonomous analysis below threshold does not trade; explicit order rejects weak confidence; natural-language entry phrases are explicit; explicit order retries HOLD and enters; duplicate-exposure protection. |
| **TradingView GUI** | Paper-panel verification; ticket-value verification; bounded action loop; refusal to submit without the paper panel. |
| **Desktop delegation** | Delegation detection for Android repair and TradingView orders; context persistence. |
| **Office extraction** | Metadata extraction and structured output. |
| **Office artifacts** | Real file generation and artifact metadata. |
| **BMD** | Draft creation, verification, inspection, render, audit, signing, co-signing, property injection/extraction, knowledge pack behavior. |

The native C11 suite adds five engine-level checks:

1. SHA-256.
2. SHA-512.
3. Ed25519.
4. ChaCha20.
5. BMD document lifecycle and tamper detection.

The combination gives three layers of verification:

- **Native layer:** cryptographic primitives and engine lifecycle.
- **Python layer:** orchestration, memory, trading, patching, BMD integration.
- **Product layer:** desktop routing, Live behavior, Simplex delegation, artifacts, and Android companion behavior.

---

## 18. Security Model and Operational Guarantees

### 18.1 Trust Boundaries

| Boundary | Control |
|:---|:---|
| **Model → OS** | The model emits allow-listed tags; the OS executor validates and executes them. |
| **Model → files** | File writes use explicit paths and guarded replacements; patches are backed up and diffed. |
| **Model → trading** | The deterministic risk gate validates every order; the GUI agent verifies the paper panel. |
| **Model → BMD** | Signatures come from device keys; the model cannot type a signature. |
| **Remote → desktop** | Simplex contact allowlist, duplicate suppression, and kill switch. |
| **Android → desktop** | ADB is local; the companion app does not own reasoning or custody. |
| **Memory → model** | FAISS returns retrieved text; the model decides what it means. |

### 18.2 Secrets

- `META_API_KEY` is read from the environment or `.env`.
- The key is never written into source files, logs, or the repository.
- `.env` is excluded from version control.
- Simplex configuration stores contact preferences, not message contents.
- BMD device keys live under `%USERPROFILE%\.bmd\` and are never embedded in documents.

### 18.3 Execution Safety

- The agent loop has hard call, step, and time limits.
- The loop never executes generated Python or shell.
- The OS executor checks permissions before sensitive actions.
- The auto-healer only proposes corrections; the supervisor retries within the configured limit.
- Trading GUI actions are limited to a fixed allowlist and normalized coordinates.
- BMD compilation applies the OS read-only attribute and forbids reverse transitions.

### 18.4 Data Locality

- FAISS memory is local.
- Knowledge Hub ingestion is local.
- BMD cryptography is local and offline.
- Paper-trading state is local.
- Android chat history and settings are local to the device.
- The only required network calls are to the Meta API for reasoning, vision, and ASR, and optional web research.

### 18.5 Operational Guarantees

| Guarantee | Mechanism |
|:---|:---|
| **The desktop shortcut opens maximized.** | VBS window style 3 plus `self.state("zoomed")`. |
| **Explicit paper orders are not silently abandoned.** | HOLD/REJECT removed from the explicit action set; up to three stricter attempts; deterministic gate validates the result. |
| **Paper Trading is verified before an order is opened.** | Muse reading plus deterministic template match plus a second independent ticket check. |
| **No real funds are touched.** | `paper_trading_only=True`; no broker code path. |
| **BMD signatures are authentic.** | Device identity keys; automatic SHA-512 and Ed25519 computation. |
| **Compiled BMD files are immutable.** | `mode: transfer`, read-only attribute, hash interlock, no reverse transition. |
| **BMD records are auditable.** | SHA-256 chained ledger, `previous_hash` linkage, `bmd audit`. |
| **The agent remains responsive.** | Bounded thread pools; UI thread never blocks; Live capture and ASR run on workers. |

---

## 19. Summary: The Agent and Blockchain Markdown

### 19.1 The Orunex Agent

Orunex is a complete desktop agent, not a chat wrapper. It perceives through Live screen capture and microphone input, reasons through Meta Muse, remembers through a persistent 384-dimensional FAISS index, executes through deterministic local subsystems, and reports through a native desktop UI, a neural voice, and an encrypted remote channel.

Its defining qualities are:

- **Deterministic first.** Greetings, screen questions, direct commands, BMD operations, and artifact requests complete before the model is consulted. This makes the product fast, predictable, and demonstrable.
- **Muse-only reasoning.** The model policy is explicit and enforced. FAISS and the bridges never make semantic decisions.
- **Real work.** The agent writes real files, runs real tests, drives real applications, captures real screenshots, places real paper orders in TradingView, and creates real BMD blocks.
- **Bounded autonomy.** Thread pools, tool limits, time budgets, permission gates, risk gates, and GUI verification keep the agent inside a defined operating envelope.
- **Remote continuity.** Simplex lets a paired phone command the desktop, receive progress, and get structured results.
- **Mobile continuity.** The Android companion provides chat history, modes, artifacts, settings, and Simplex pairing in a native WebView shell.
- **Memory continuity.** Code, strategies, episodes, and BMD knowledge persist across sessions and are recalled by namespace.

The agent’s strongest demonstration is the complete loop: a spoken request becomes a delegated task, the task uses vision and memory, the execution produces a file or a paper order, the result is verified, and the outcome is remembered.

### 19.2 Blockchain Markdown

Blockchain Markdown is a complete cryptographic document platform:

- **Format:** human-readable Markdown plus a validated YAML ledger header.
- **Cryptography:** SHA-512 payload hashes, Ed25519 signatures, SHA-256 chained ledger auditing, and ChaCha20 payload encryption.
- **Lifecycle:** `draft` for mutable authoring; `transfer` for immutable sealing. `sign` authenticates in draft; `compile` freezes to transfer.
- **Identity:** device-anchored keys at `%USERPROFILE%\.bmd\`; no manual signatures.
- **Governance:** `max_signatures` supports unilateral, bilateral, multilateral, and unlimited models.
- **Authoring:** in-terminal Redact Studio with preview, frontmatter editing, signature buttons, IP injection, and compile.
- **Verification:** `verify`, `verify --json`, `inspect`, `audit`, and standalone HTML rendering with WebCrypto.
- **Custody:** read-only sealing, no reverse transition, hash interlock, and signature invalidation on tamper.
- **Enterprise:** Office export, property bundles, Merkle trees, and offline operation.
- **Integration:** a 21-entry knowledge pack, a deterministic BMD expert, `[BMD: ...]` tags, artifact cards, and a background CLI path inside Orunex.

The strongest BMD demonstration is the full custody chain: create a draft, sign as Emitter, compile to transfer, verify the hash and signature, send it to a counterparty, co-sign as Receiver, and audit the resulting ledger. Every step is local, cryptographic, and reproducible.

### 19.3 The Combination

Orunex and BMD reinforce each other:

- The agent can draft, sign, compile, verify, render, and audit documents through natural language.
- BMD gives the agent a custody layer that ordinary file generation cannot provide.
- The knowledge pack keeps the agent’s BMD answers precise.
- The deterministic expert keeps BMD operations available even when the model is slow.
- The artifact card keeps the result visible and actionable.
- The read-only seal keeps the final record trustworthy.

The result is an agent that can not only produce work, but also prove what it produced.

---

## 20. Appendix: Complete Inventory of Additions

This appendix records everything this README adds to the project documentation. It is organized by capability so judges can verify coverage quickly.

### 20.1 Documentation Additions

| # | Addition | Location |
|:---|:---|:---|
| 1 | Definitive English product overview | Section 1 |
| 2 | Platform-at-a-glance tables for every surface and runtime layer | Section 2 |
| 3 | Full system topology diagram | Section 3.1 |
| 4 | Component responsibility map for every major file | Section 3.2 |
| 5 | Nine-stage request lifecycle | Section 3.3 |
| 6 | Concurrency model | Section 3.4 |
| 7 | Muse model policy and API behavior | Section 3.5 |
| 8 | Desktop launch and maximized-window guarantee | Section 4.1 |
| 9 | Navigation map | Section 4.2 |
| 10 | Chat workspace element reference | Section 4.3 |
| 11 | Composer control reference | Section 4.4 |
| 12 | Four-mode behavior specification | Section 4.5 |
| 13 | Sequential task list | Section 4.6 |
| 14 | Settings card reference | Section 4.7 |
| 15 | Simplex pairing page reference | Section 4.8 |
| 16 | Saved Memory manager | Section 4.9 |
| 17 | AgentBrain orchestrator API | Section 5.1 |
| 18 | Direct command router | Section 5.2 |
| 19 | Complex-task delegation pipeline | Section 5.3 |
| 20 | Cerebro and Supervisor behavior | Section 5.4 |
| 21 | Two-layer auto-healer | Section 5.5 |
| 22 | Bounded agent loop and tool registry | Section 5.6 |
| 23 | Complete OS tag family table | Section 5.7 |
| 24 | `MAKE_DOC` and `HEADLESS_SEARCH` preservation | Section 5.7 |
| 25 | Permission model | Section 5.8 |
| 26 | Artifact Studio formats and behavior | Section 5.9 |
| 27 | Office Expert capabilities | Section 5.10 |
| 28 | Knowledge Hub ingestion | Section 5.11 |
| 29 | Live session lifecycle | Section 6.1 |
| 30 | Screen observation parameters | Section 6.2 |
| 31 | Screen-question path | Section 6.3 |
| 32 | Microphone and ASR parameters | Section 6.4 |
| 33 | Neural voice and fallback | Section 6.5 |
| 34 | Wake word and conversation window | Section 6.6 |
| 35 | Instant greetings | Section 6.7 |
| 36 | Live routing | Section 6.8 |
| 37 | Live safety | Section 6.9 |
| 38 | FAISS architecture and persistence | Section 7.1 |
| 39 | Deterministic embedding design | Section 7.2 |
| 40 | Namespace reference | Section 7.3 |
| 41 | Codebase indexing parameters | Section 7.4 |
| 42 | 21-entry BMD knowledge pack | Section 7.5 |
| 43 | Episode memory | Section 7.6 |
| 44 | Strategy memory | Section 7.7 |
| 45 | Memory persistence and recovery | Section 7.8 |
| 46 | Simplex bridge protocol | Section 8.1 |
| 47 | Simplex pairing flow | Section 8.1 |
| 48 | Simplex command reference | Section 8.1 |
| 49 | Simplex security controls | Section 8.1 |
| 50 | VS Code bridge capability table | Section 8.2 |
| 51 | Android ADB bridge and repair pipeline | Section 8.3 |
| 52 | TradingView bridge | Section 8.4 |
| 53 | Web, Chrome, and headless search | Section 8.5 |
| 54 | Social and messaging integrations | Section 8.6 |
| 55 | Office and document integrations | Section 8.7 |
| 56 | Paper-trading hard invariants | Section 9.1 |
| 57 | Full trading pipeline | Section 9.2 |
| 58 | Explicit-order guarantee and retries | Section 9.3 |
| 59 | Native TradingView GUI execution | Section 9.4 |
| 60 | Paper account and state model | Section 9.5 |
| 61 | Trading command reference | Section 9.6 |
| 62 | Warm-up behavior | Section 9.7 |
| 63 | Paper-trading design rationale | Section 9.8 |
| 64 | Android project metadata | Section 10.1 |
| 65 | Android architecture | Section 10.2 |
| 66 | Android screens | Section 10.3 |
| 67 | Android chat experience | Section 10.4 |
| 68 | Android modes | Section 10.5 |
| 69 | Android local artifacts | Section 10.6 |
| 70 | Android Simplex UI | Section 10.7 |
| 71 | Android settings | Section 10.8 |
| 72 | Android build and install | Section 10.9 |
| 73 | Android manifest behavior | Section 10.10 |
| 74 | BMD executive summary | Section 11.1 |
| 75 | BMD zero-dependency identity | Section 11.2.1 |
| 76 | BMD draft/transfer lifecycle | Section 11.2.2 |
| 77 | BMD device identity signatures | Section 11.2.3 |
| 78 | BMD signature governance | Section 11.2.4 |
| 79 | BMD cryptographic primitives | Section 11.3.1 |
| 80 | BMD anti-decompilation guarantees | Section 11.3.2 |
| 81 | BMD frontmatter schema | Section 11.4.1 |
| 82 | BMD field dictionary | Section 11.4.2 |
| 83 | BMD typography tags | Section 11.4.3 |
| 84 | BMD structural directives | Section 11.4.3 |
| 85 | BMD complete CLI summary | Section 11.5.1 |
| 86 | BMD detailed command specifications | Section 11.5.2 |
| 87 | BMD Redact Studio interface | Section 11.6.1 |
| 88 | BMD signature button rendering | Section 11.6.2 |
| 89 | BMD studio key actions | Section 11.6.3 |
| 90 | BMD studio command dictionary | Section 11.6.4 |
| 91 | BMD unilateral workflow | Section 11.7 |
| 92 | BMD bilateral workflow | Section 11.7 |
| 93 | BMD IP escrow workflow | Section 11.7 |
| 94 | BMD invoice ledger workflow | Section 11.7 |
| 95 | BMD C11 engine components | Section 11.8.1 |
| 96 | BMD build and native tests | Section 11.8.2 |
| 97 | BMD build artifacts | Section 11.8.3 |
| 98 | BMD enterprise best practices | Section 11.9 |
| 99 | BMD expert capabilities | Section 12.1 |
| 100 | BMD natural-language intents | Section 12.2 |
| 101 | `[BMD: ...]` tag contract | Section 12.3 |
| 102 | BMD knowledge pack integration | Section 12.4 |
| 103 | Professional contract clause library | Section 12.5 |
| 104 | BMD artifact cards | Section 12.6 |
| 105 | BMD CLI entry points | Section 12.7 |
| 106 | BMD Python FFI helpers | Section 12.8 |
| 107 | BMD Office export | Section 12.9 |
| 108 | BMD repository examples | Section 12.10 |
| 109 | Configuration source order | Section 13.1 |
| 110 | Meta Muse configuration table | Section 13.2 |
| 111 | Workspace and Android configuration | Section 13.3 |
| 112 | Memory and autonomy configuration | Section 13.4 |
| 113 | Simplex configuration | Section 13.5 |
| 114 | TradingView and paper configuration | Section 13.6 |
| 115 | Virtual input and Live debug configuration | Section 13.7 |
| 116 | Configuration validation | Section 13.8 |
| 117 | Installation prerequisites | Section 14.1 |
| 118 | Python dependency reference | Section 14.2 |
| 119 | Environment setup | Section 14.3 |
| 120 | BMD engine build | Section 14.4 |
| 121 | Android build | Section 14.5 |
| 122 | Desktop launch | Section 14.6 |
| 123 | Headless flags | Section 14.7 |
| 124 | First-run checklist | Section 14.8 |
| 125 | Desktop shortcut guarantee | Section 14.9 |
| 126 | Full repository map | Section 15 |
| 127 | Nine end-to-end use cases | Section 16 |
| 128 | 51-check test coverage map | Section 17 |
| 129 | Native C11 test coverage | Section 17 |
| 130 | Trust boundary table | Section 18.1 |
| 131 | Secrets handling | Section 18.2 |
| 132 | Execution safety | Section 18.3 |
| 133 | Data locality | Section 18.4 |
| 134 | Operational guarantees | Section 18.5 |
| 135 | Agent summary | Section 19.1 |
| 136 | BMD summary | Section 19.2 |
| 137 | Combined value statement | Section 19.3 |
| 138 | This complete inventory | Section 20 |

### 20.2 Platform Capability Inventory

| Capability | Status | Evidence |
|:---|:---|:---|
| Desktop chat with history, rename, delete | Included | `src/main.py` |
| Animated composer and maximized window | Included | `src/main.py`, VBS launcher |
| Default / Programmer / Deep Research / Agent Swapping | Included | `mode_router.py` |
| Live screen capture with change detection | Included | `live_vision.py` |
| Live microphone ASR | Included | `live_audio.py` |
| Edge neural TTS with SAPI fallback | Included | `live_tts.py` |
| Wake word and conversation window | Included | `src/main.py` |
| Screen questions through Meta vision | Included | `src/main.py`, `live_vision.py` |
| Instant local greetings | Included | `src/main.py` |
| Direct app and URL commands | Included | `os_executor.py`, `intent_router.py` |
| Complex-task delegation | Included | `src/main.py`, `app.py` |
| Android repair pipeline | Included | `bugfix_task.py`, `adb_bridge.py`, `vscode_bridge.py` |
| Paper-trading pipeline | Included | `trading_task.py` |
| Native TradingView GUI execution | Included | `tradingview_gui.py` |
| Explicit-order retries | Included | `trading_task.py` |
| Paper Trading panel verification | Included | `tradingview_gui.py` |
| Duplicate-exposure protection | Included | `trading_task.py` |
| Simplex pairing and QR | Included | `simplex_bridge.py`, `src/main.py` |
| Simplex remote commands | Included | `agent_brain.py`, `simplex_bridge.py` |
| Simplex notifications and heartbeat | Included | `src/_orunex_libs/simplex_bridge.py` |
| Contact allowlist and kill switch | Included | `agent_brain.py` |
| FAISS 384-d memory | Included | `core/faiss_memory.py` |
| Code / strategy / episode / knowledge namespaces | Included | `core/faiss_memory.py` |
| Codebase indexing | Included | `core/faiss_memory.py` |
| BMD 21-entry knowledge pack | Included | `bmd_knowledge.py` |
| Artifact Studio | Included | `artifact_studio.py` |
| Office Expert | Included | `office_expert.py` |
| Knowledge Hub | Included | `knowledge_processor.py`, `src/main.py` |
| OS executor tag system | Included | `os_executor.py` |
| `MAKE_DOC` | Included | `os_executor.py` |
| `HEADLESS_SEARCH` | Included | `os_executor.py`, `headless_web.py` |
| Bounded agent loop | Included | `agentic_loop.py` |
| Auto-healer | Included | `auto_healer.py` |
| Permission gate | Included | `permissions.py` |
| Android companion app | Included | `android/` |
| Android local artifacts | Included | `app.js`, `MainActivity.java` |
| Android Simplex UI | Included | `app.js` |
| BMD C11 engine | Included | `bmd_engine/` |
| BMD CLI v2.1.0 | Included | `bmd_cli.exe` |
| BMD Redact Studio | Included | `bmd redact` |
| BMD sign → draft; compile → transfer | Included | Engine lifecycle |
| BMD Ed25519 device signatures | Included | Engine + `%USERPROFILE%\.bmd\` |
| BMD SHA-512 128-hex hashes | Included | Engine |
| BMD SHA-256 chained ledger | Included | Engine |
| BMD ChaCha20 property encryption | Included | Engine + FFI |
| BMD verify / inspect / audit / render | Included | CLI + expert |
| BMD property inject / extract | Included | CLI + expert |
| BMD Office export | Included | CLI + expert |
| BMD standalone HTML viewer | Included | `bmd_viewer_generator.py` |
| BMD contract clause library | Included | `bmd_expert.py` |
| BMD artifact cards | Included | `src/main.py` |
| Maximized desktop shortcut | Included | `Lanzar_Orunex_Windows.vbs` |

### 20.3 Closing Statement

Orunex is designed to be judged on what it can demonstrate: a spoken request that becomes a real artifact, a remote message that becomes a verified paper order, an Android defect that becomes a tested patch, a research question that becomes a styled deck, and a document that becomes a cryptographically sealed record.

The agent provides the reach. Live mode provides the presence. Simplex provides the remote continuity. FAISS provides the memory. The Android app provides the companion surface. Blockchain Markdown provides the custody.

Every capability described in this README is implemented in the repository and reachable from the desktop application, the headless backend, the Simplex bridge, the Android companion, or the BMD CLI.

For the full BMD specification, continue with [BMD manual.md](BMD%20manual.md).
