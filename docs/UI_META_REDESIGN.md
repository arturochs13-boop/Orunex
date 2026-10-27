# Orunex UI — Light Desktop Direction

**Status:** implemented in `src/main.py`  
**Theme:** light only — white surfaces on a near-white canvas with Meta blue accents  
**Language:** all visible desktop copy is English  
**Date:** 22 October 2026

---

## 1. Decision

The existing Orunex desktop shell and execution pipeline were kept and
simplified. The redesign is a focused desktop surface, not a new dashboard.

- The agent runner, task pipeline, local chat store, and Simplex Bridge remain
  in place.
- Alternate screens open inside the main window. Simplex Bridge, Settings and
  Saved memory are pages of the single application window.
- The upper-right corner contains only `Powered by Meta`.
- VS Code, Copilot mode, Integrations, Automations, Voice, Swarm and Tasks are
  not exposed in the current navigation or composer.
- The desktop window is independent of Android; there is no Android panel, ADB
  control, device preview or simulated device state.
- The approved Orunex gradient wordmark is used in the desktop sidebar.
- No example conversations, fake metrics, invented approvals or simulated
  artifacts are rendered.

---

## 2. Desktop structure

```text
+--------------------------------------------------------------------------------+
| Orunex        | Chat                                      Powered by Meta       |
|               +--------------------------------------------------------------+
| + New chat    |                                                              |
| Chats         |  New chat                                      Ready         |
|               |  Ask Orunex anything or describe a task.                     |
| No saved      |                                                              |
| chats yet     |                 Hello, User                                  |
|               |                 How can I help you today?                    |
|               |                                                              |
| Menu          |     [Plan a task]       [Summarize a file]                   |
| Chat          |     [Automate desktop]  [Check system status]                |
| Simplex Bridge|                                                              |
| Settings      |  +------------------------------------------------------+    |
|               |  | Attach   Ask Orunex or describe a task...     [Send] |    |
| Simplex·Paired|  +------------------------------------------------------+    |
+--------------------------------------------------------------------------------+
```

### 2.1 Sidebar

- Orunex gradient wordmark and a collapsible navigation rail.
- `New chat` creates a local conversation and focuses the composer.
- Saved chats are loaded from `src/config/chats.json` and can be reopened.
- Menu: `Chat`, `Simplex Bridge`, `Settings`.
- The live bridge state is shown in the sidebar footer (`Simplex · Paired`,
  `Simplex · Online` or `Simplex offline`).

### 2.2 Header

- The current page name appears at the top-left.
- The upper-right area intentionally contains only `Powered by Meta`.
- There is no header `Stop Agent` or settings gear.

### 2.3 Chat workspace

- The conversation card shows the current chat title, a quiet activity line, a
  real status pill and the actual message list.
- Empty chats show a greeting and four real capability prompts. These are
  prompts, not simulated messages.
- User messages align right; Orunex responses align left and keep the existing
  copy/action handling.

### 2.4 Composer

One row: `Attach`, the prompt entry, and `Send`.

The border is a Magic UI / Aceternity-inspired animated mesh-gradient rim with a
soft outer glow. It is rendered natively with Pillow and a Tk canvas — there is
no web view or React runtime.

`Pause` appears only while a real execution is running. The existing pause,
cancel and task-execution code paths are unchanged.

### 2.5 Simplex Bridge page

- Real bridge state and paired contact (`Arturo_1` when paired).
- `Generate pairing link`, `Disconnect`, QR/link area and bridge preferences.
- Pairing and remote commands continue to use the local Simplex CLI
  (`simplex_bin/simplex-chat.exe`).
- Startup is silent: a successful reconnect refreshes the page state but does
  not add a chat-history message.

### 2.6 Settings page

- Profile, display name and saved-memory management.
- Appearance: light theme, English language, interface scale.
- Engine: recovery, task memory, screen glow, retries and context window.
- Knowledge Hub: JSON/PDF ingestion.
- Connections: shortcut to the in-window Simplex Bridge.
- `Manage saved memory` opens an in-window page with individual Forget actions.

---

## 3. Android interface

Android remains a separate client. It is not embedded in the desktop window.

The standalone reference is `docs/ui/mockup-android.html`; the desktop window
does not contain Android previews, ADB state or remote-device controls.

---

## 4. Visual system

| Token | Value |
|---|---|
| App background | `#F8F9FA` |
| Surface | `#FFFFFF` |
| Soft surface | `#F8F9FA` |
| Muted surface | `#F2F4F7` |
| Border | `#E6E9EE` |
| Strong border | `#D9DEE6` |
| Primary text | `#111318` |
| Secondary text | `#667085` |
| Muted text | `#98A2B3` |
| Meta blue | `#0668E1` |
| Meta blue hover | `#0059C7` |
| Meta blue soft | `#EDF4FF` |
| Meta blue border | `#CFE2FF` |
| Stop / error | `#E15241` |
| Stop soft | `#FEF1EF` |
| Typography | Segoe UI / Inter / system sans |
| Radii | 8–16 px controls; 18 px conversation card |

The only saturated decoration is the composer gradient rim and its glow. The
rest of the interface stays calm and light.

---

## 5. Content rules

1. No simulated messages, tasks, approvals, metrics or device state.
2. Empty states are real empty states.
3. Simplex displays `Paired` only when a contact is actually linked.
4. `Running`, `Paused` and `Stopped` appear only during real execution.
5. Every visible label, placeholder, state and custom dialog is English.
6. The approved Orunex gradient wordmark is used for branding.

---

## 6. Implementation notes

- `show_view` switches pages inside `view_host`; it never creates a new window
  for Chat, Simplex Bridge, Settings or Saved memory.
- `_build_composer` draws the mesh rim and glow with Pillow; `_animate_composer_glow`
  only runs while the workspace is visible and Orunex is in the foreground.
- The main window is constrained to the Windows work area, so the composer and
  footer remain above the taskbar.
- `SIMPLEX_CONNECTED_EVENT` refreshes the bridge page without adding a history
  message.
- Settings persist through `_orunex_libs.config_manager`; language and light mode
  are fixed to English/light for this interface.
- Native confirmation dialogs and OS file pickers remain native dialogs; they
  are not alternate application screens.

---

## 7. Files

- `src/main.py` — desktop shell, sidebar, in-window pages, composer glow,
  chat workspace and settings.
- `src/agents/cerebro.py` — local core responses, including English error text.
- `src/_orunex_libs/simplex_bridge.py` — Simplex pairing and bridge state.
- `src/_orunex_libs/chat_store.py` — local chat persistence.
- `src/_orunex_libs/config_manager.py` — persisted settings.
- `src/assets/orunex-wordmark.png` — approved Orunex gradient wordmark.
- `docs/ui/current-desktop.png` — current desktop capture.
- `docs/ui/mockup-desktop.html` — desktop visual reference (design archive).
- `docs/ui/mockup-android.html` — standalone Android reference.
- `docs/ui/theme.tokens.json` — shared light tokens.
