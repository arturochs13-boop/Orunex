# Orunex UI — light direction

The desktop shell keeps the original Orunex component flow and moves it to a
light, English-only interface. Android is a separate client and is not embedded
in the desktop window.

## View the mockups

Open these files directly in a browser:

- `mockup-desktop.html` — earlier 1240×840 desktop visual reference. The
  implemented sidebar and in-window pages are authoritative; see
  `current-desktop.png`.
- `mockup-android.html` — 390×844 standalone Android reference.

If the browser blocks local resources, serve the folder:

```powershell
cd docs/ui
python -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/mockup-desktop.html` and
`http://127.0.0.1:8765/mockup-android.html`.

## Files

| File | Purpose |
|---|---|
| `mockup-desktop.html` | Desktop visual reference. |
| `mockup-android.html` | Standalone Android visual reference. |
| `orunex-wordmark.png` | Approved Orunex gradient wordmark. |
| `theme.tokens.json` | Light tokens for CustomTkinter and Compose. |
| `current-desktop.png` | Capture of the current desktop app. |
| `../UI_META_REDESIGN.md` | Rationale, component map, and content rules. |

## Notes

- The mockups contain empty states only; they do not simulate conversations,
  device sessions, metrics, or approvals.
- The approved Orunex gradient wordmark is the current brand asset.
- All visible UI labels, placeholders, and dialogs are English.
- The rejected dark “Mission Control” mockups and brand board have been removed.
