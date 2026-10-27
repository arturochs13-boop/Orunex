# Análisis adicional de errores — Project_Orunex

**Fecha:** 21 de octubre de 2026  
**Alcance:** `src/main.py`, `src/agents/`, `src/_orunex_libs/`, `src/config/` y assets.  
**Método:** revisión manual + `compileall` + Ruff (`F821`, `F811`, `E722`, `F401`, `F841`, `S`, `B`) + pruebas de importación controladas.  
**Estado:** análisis local. No se ha creado repositorio ni commit alguno.

---

## 1. Resumen ejecutivo

La auditoría anterior ya había identificado que el proyecto no arranca. Este análisis profundiza en los errores que quedan **después** de instalar dependencias: fallos silenciosos, llamadas con argumentos incorrectos, métodos duplicados, condiciones de carrera y agujeros de seguridad que no aparecen en una simple prueba de arranque.

| Señal | Resultado |
|---|---:|
| Archivos Python | 70 |
| Líneas de Python | ~15.000 |
| `compileall` | Pasa (sintaxis válida) |
| Ruff `F821/F811/E722` | **110** hallazgos |
| Ruff `F401/F841` | **141** hallazgos |
| Ruff `S` (seguridad) | **160** hallazgos |
| Ruff `B` (bugbear) | **12** hallazgos |
| Errores nuevos P0/P1 de runtime o lógica | **14** |
| Repositorio Git | No existe |

**Veredicto:** el código compila, pero no es un producto ejecutable ni seguro. El problema no es solo “faltan dependencias”: hay código que **nunca se ejecuta**, código que se ejecuta con la firma equivocada y código que ejecuta acciones peligrosas por defecto. Reparar `main.py` sería más caro que construir el runtime nuevo con guardrails desde el primer commit.

---

## 2. Evidencia reproducible

### 2.1 Arranque de la app

```powershell
python -c "import sys; sys.path.insert(0,'src'); import main"
```

```text
File "src/main.py", line 13, in <module>
    from faster_whisper import WhisperModel
ModuleNotFoundError: No module named 'faster_whisper'
```

El import está fuera de cualquier `try/except`, antes de la comprobación de dependencias de la UI. La app muere sin mensaje útil.

### 2.2 Automatización de escritorio

```powershell
python -c "import sys; sys.path.insert(0,'src'); import _orunex_libs.os_executor"
```

```text
File "src/_orunex_libs/os_executor.py", line 2, in <module>
    import pyautogui
ModuleNotFoundError: No module named 'pyautogui'
```

### 2.3 Motor local

```powershell
python -c "import sys; sys.path.insert(0,'src'); from _orunex_libs.ollama_client import get_model; get_model()"
```

```text
File "src/_orunex_libs/ollama_client.py", line 13, in get_model
FileNotFoundError: Model GGUF file not found at:
C:\Users\artur\Downloads\Project_Orunex\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q4_K_M.gguf
```

La ruta pertenece a otro usuario. Aunque se instale `llama-cpp-python`, el motor no encuentra el modelo.

### 2.4 Ruff

```powershell
python -m ruff check src --select F821,F811,E722 --statistics
# 103 E722, 5 F811, 2 F821 — 110 errors

python -m ruff check src --select F401,F841 --statistics
# 109 F401, 32 F841 — 141 errors

python -m ruff check src --select S --statistics
# 96 S110, 18 S602, 15 S607, 11 S603, 8 S606, 4 S101, ...
# 160 errors

python -m ruff check src --select B --statistics
# 7 B007, 1 B033, 1 B008, 1 B023, 1 B010, 1 B905
```

---

## 3. Hallazgos nuevos priorizados

### P0 — bloquean el producto o permiten abuso

#### E-01 · `faster_whisper` bloquea el arranque antes de todo

- **Archivo:** `src/main.py:13`
- **Evidencia:** `from faster_whisper import WhisperModel` en el nivel superior.
- **Impacto:** la app no llega a mostrar la UI ni el diálogo de dependencias. Cualquier demo falla en el primer segundo.
- **Fix:** eliminar el import del arranque; cargar Whisper de forma perezosa dentro del módulo de voz; validar dependencias con un `startup_check()` que muestre un resumen y permita modo degradado.

#### E-02 · El sistema de permisos aprueba por defecto

- **Archivo:** `src/_orunex_libs/permissions.py:59-77`
- **Evidencia:**

```python
level = TAG_PERMISSIONS.get(tag.upper(), PermLevel.ELEVATED)
...
strict_perm = os.environ.get("ORUNEX_STRICT_PERM", "0")
if level == PermLevel.DANGEROUS and strict_perm == "1":
    ... confirmar ...
log_entry(... status="APPROVED")
return True
```

- **Impacto:** un tag desconocido se trata como `ELEVATED`; `DEL`, `SOCIAL` y cualquier tag no listado se aprueban sin diálogo salvo que el usuario configure una variable de entorno. El callback modal existe, pero está desactivado por defecto.
- **Fix:** política *default deny*; tags desconocidos = `DANGEROUS`; `ELEVATED` requiere confirmación contextual; `DANGEROUS` requiere aprobación explícita con nonce y caducidad. Nunca depender de una variable de entorno para activar la seguridad.

#### E-03 · Simplex acepta contactos y ejecuta mensajes arbitrarios

- **Archivo:** `src/_orunex_libs/simplex_bridge.py:390`, `487-542`, `592-612`
- **Evidencia:** `auto-accept-member-contacts true`, `auto-accept-new-contacts true`, y cualquier `newChatItems` de cualquier contacto se pasa a `_parse_remote_command()`. Si el mensaje no es un comando conocido, se crea un hilo y se ejecuta como tarea del agente (`:280-285`).
- **Impacto:** un tercero que consiga el enlace de invitación puede auto-unirse, enviar “borra X” o “abre esta web” y el agente lo ejecuta. No hay allowlist, firma, rate limit ni confirmación.
- **Fix:** emparejamiento explícito, allowlist por `contactId` + fingerprint, comandos cerrados, aprobación para acciones de riesgo y modo “solo notificaciones” por defecto. Ver `docs/SIMPLEX_INTEGRACION_SEGURA.md`.

#### E-04 · Shell arbitrario y borrado de rutas absolutas

- **Archivo:** `src/_orunex_libs/os_executor.py:68-71`, `657-680`, `1582-1599`
- **Evidencia:** `subprocess.run(cmd, shell=True, ...)`, `subprocess.Popen(cmd_val, shell=True, ...)`, y `[DEL: C:\ruta\absoluta]` usa `safe_path = filepath` si existe, sin comprobar que esté dentro de un workspace.
- **Impacto:** una alucinación del modelo o un mensaje remoto puede ejecutar comandos de shell o borrar archivos fuera del proyecto. `check_permission("DEL")` no protege porque E-02 lo aprueba por defecto.
- **Fix:** ejecutar con `argv` y allowlist de binarios; prohibir `shell=True`; resolver rutas con `Path.resolve()` y comprobar `is_relative_to(workspace)`; papelera en lugar de borrado definitivo; confirmación con vista previa del comando.

#### E-05 · Confirmación modal de Tkinter desde hilos de trabajo

- **Archivo:** `src/main.py:1842-1844` + `src/_orunex_libs/permissions.py:65-71`
- **Evidencia:** `ui_confirm_dangerous_action()` llama a `messagebox.askyesno()` directamente. `check_permission()` se invoca desde `os_executor` en hilos de fondo.
- **Impacto:** si se activara `ORUNEX_STRICT_PERM=1`, Tkinter sería llamado desde un hilo que no es el principal. Puede bloquear, lanzar `RuntimeError` o corromper el estado de la UI.
- **Fix:** el motor de approvals no debe tocar la UI. Debe publicar una solicitud en el event bus; la UI la muestra en el hilo principal y responde con un `Future`/`Event`.

---

### P1 — fallos funcionales silenciosos

#### E-06 · `ImageTk` no está importado: el splash nunca muestra el logo

- **Archivo:** `src/main.py:830`
- **Evidencia:** el import de PIL es `from PIL import Image, ImageDraw` (`:30`), pero se usa `ImageTk.PhotoImage`.
- **Impacto:** `NameError` capturado por `except Exception`; se muestra el texto “ORUNEX” en lugar del logo. El bug es invisible porque el fallback está dentro del mismo `try`.
- **Fix:** `from PIL import ImageTk` o usar `CTkImage` directamente. Añadir test de humo que verifique que el splash carga una imagen.

#### E-07 · `lambda` captura una variable de excepción que ya no existe

- **Archivo:** `src/main.py:1229-1230`
- **Evidencia:** `except Exception as e: self.after(0, lambda: self.write_real_time(f"... {e}", "error"))`. Python borra `e` al salir del bloque `except`.
- **Impacto:** el callback se ejecuta después y lanza `NameError`; el error original se pierde y la UI no muestra nada.
- **Fix:** `lambda err=str(e): ...` o `functools.partial`.

#### E-08 · Copiloto proactivo llama a `call_ollama` con la firma equivocada

- **Archivo:** `src/main.py:662`
- **Evidencia:** `call_ollama(prompt, model=self.thinker_model_var.get())`, pero la firma es `call_ollama(model, prompt, ...)`. Además `self.thinker_model_var` no se define en la clase.
- **Impacto:** `AttributeError`/`TypeError` dentro de un `try/except` vacío. El copiloto “existe” pero nunca sugiere nada.
- **Fix:** `call_ollama("orunex_v37", prompt)` con el cliente nuevo; eliminar la variable inexistente; test con un proveedor mock.

#### E-09 · `memory_gc` tampoco respeta la firma

- **Archivo:** `src/_orunex_libs/memory_gc.py:51`
- **Evidencia:** `call_ollama(compact_prompt, system=...)` pasa el prompt como `model` y no pasa `prompt`.
- **Impacto:** la compactación de contexto falla siempre y se traga la excepción (`:58-60`). La memoria crece sin control.
- **Fix:** `call_ollama("orunex_v37", compact_prompt, system=...)`; validar con test unitario.

#### E-10 · `_on_close` duplicado en Simplex: el primero es código muerto

- **Archivo:** `src/_orunex_libs/simplex_bridge.py:424-432` y `618-620`
- **Evidencia:** la segunda definición reemplaza a la primera. La primera cancelaba el heartbeat, reseteaba `_connecting` y limpiaba `ws`; la segunda solo pone `connected=False` y `linked=False`.
- **Impacto:** tras una desconexión queda un `threading.Timer` vivo, `_connecting` puede quedar en `True` y el estado del WebSocket no se limpia. Los reintentos se comportan de forma errática.
- **Fix:** una sola implementación idempotente, con lock, `stop_event` y cancelación de timers; test de reconexión.

#### E-11 · El bridge se reinicializa y se reemplaza el callback

- **Archivo:** `src/main.py:152` y `src/main.py:908`
- **Evidencia:** al arrancar se registra `handle_simplex_command`; al abrir el modal se llama `simplex.init_bridge(on_command_callback=handle_remote_task, force_enable=True)`, que crea una instancia nueva de `SimplexBridge`.
- **Impacto:** la instancia anterior puede seguir reconectándose; la nueva no maneja `SIMPLEX_CONNECTED_EVENT`, `SIMPLEX_DISCONNECTED_EVENT` ni los comandos de voz. El estado de la UI y el bridge se desincronizan.
- **Fix:** un único `OrunexLinkService` con ciclo de vida controlado; `connect()` no debe crear otra instancia; callbacks registrados una vez.

#### E-12 · Métodos duplicados con comportamientos distintos

- **Archivo:** `src/main.py:676` vs `880` (`toggle_fullscreen`), `src/main.py:2153` vs `2499` (`refresh_ui_text`); `os_executor.py:19` (`threading`), `:813` (`search_youtube`); `cerebro.py:396` (`call_ollama`).
- **Impacto:** la segunda definición gana. El binding de F11 conserva la primera función, pero las llamadas posteriores usan la segunda; los atributos (`fullscreen_state` vs `is_fullscreen`) pueden quedar inconsistentes. El cambio de idioma deja de actualizar varios botones.
- **Fix:** eliminar duplicados, unificar estado y añadir lint en CI (`F811` como error).

#### E-13 · Gateway remoto duplicado y parcialmente muerto

- **Archivo:** `src/main.py:1159-1171` (`handle_remote_command`) vs `1846-1881` (`handle_simplex_command`)
- **Evidencia:** `grep` solo encuentra la definición de `handle_remote_command`; no se registra como callback. El callback real es `handle_simplex_command`, y el modal instala otro callback local.
- **Impacto:** hay tres caminos de entrada con comportamientos distintos; es fácil que un comando funcione en un camino y no en otro.
- **Fix:** un solo `RemoteCommandRouter` con comandos declarativos y tests de contrato.

#### E-14 · La “visión” no usa visión

- **Archivo:** `src/_orunex_libs/os_executor.py:1092-1096`
- **Evidencia:** se llama `call_ollama(model="moondream", prompt=..., images=[...])`, pero `ollama_client.call_ollama` ignora `images` y solo sabe generar texto con el GGUF local.
- **Impacto:** el agente dice “Vision Activa” y luego alucina coordenadas o falla; no hay grounding visual real.
- **Fix:** usar un proveedor multimodal real (SAM/Muse) o eliminar la función del MVP. No simular capabilities.

#### E-15 · Rutas hardcodeadas de otro usuario

- **Archivo:** `src/main.py:417`, `src/_orunex_libs/ollama_client.py:6`
- **Evidencia:** `C:\Users\artur\...` en VSCode y en el modelo GGUF.
- **Impacto:** funciones que nunca encuentran el recurso. El launcher VBS también apunta a `main_av.py`.
- **Fix:** `Path.home()`, variables de entorno, configuración validada al arrancar; test de “home distinto”.

#### E-16 · El “DAG paralelo” no es un DAG

- **Archivo:** `src/_orunex_libs/project_manager.py:57-85`
- **Evidencia:** `is_independent_doc = any(...) or not has_dep`; cualquier paso sin palabras de dependencia se considera independiente y se agrega al batch. `current_idx` y `context_accumulator` se modifican fuera del lock en otras rutas.
- **Impacto:** pasos que deberían ser secuenciales corren en paralelo; el contexto se pisa; el estado del proyecto no es durable.
- **Fix:** DAG explícito con `depends_on`, scheduler con `asyncio`/`TaskGroup`, estado persistido en SQLite y eventos.

#### E-17 · Configuración que falla en silencio y devuelve el objeto global

- **Archivo:** `src/_orunex_libs/config_manager.py:25-43`
- **Evidencia:** si el JSON está corrupto, retorna `DEFAULT_CONFIG` (el mismo dict global); `save_config` se traga cualquier excepción.
- **Impacto:** cambios accidentales en los defaults; el usuario cree que guardó y no se guardó; no hay migración de esquema.
- **Fix:** Pydantic Settings, escritura atómica (`tmp` + `os.replace`), backups y errores visibles.

#### E-18 · Investigación web sin citas verificables ni control de calidad

- **Archivo:** `src/_orunex_libs/headless_web.py:21-36`, `38-70`
- **Evidencia:** `requests.get(..., timeout=5)`, `BeautifulSoup` puede ser `None`, `except:` devuelve `""`, y el corpus se construye con snippets sin verificación de fuente.
- **Impacto:** el agente puede afirmar datos sin fuente o con una fuente que no respalda la afirmación. Para un “boardroom brief” es un fallo crítico.
- **Fix:** pipeline con `httpx`, extracción estructurada, `source_id`, `quote`, `span`, verificación de entailment y un `CitationGuard` que bloquee claims sin evidencia.

#### E-19 · Generación de documentos que oculta fallos del modelo

- **Archivo:** `src/_orunex_libs/doc_factory.py:70-84` y similares
- **Evidencia:** `res.get("response", "{}")`; si el cliente devuelve `{"error": ...}`, se usa `"{}"` y se cae al fallback. El documento se genera, pero con contenido genérico.
- **Impacto:** el usuario recibe un artefacto “listo” que no contiene los datos de la misión. Es peor que un error visible.
- **Fix:** validar el resultado del modelo con Pydantic; si falla, marcar el artefacto como `DEGRADED` y mostrar la causa; nunca silenciar.

#### E-20 · UI: hilos, emojis y un header que no escala

- **Archivo:** `src/main.py:389-482`, `630-669`, `1842-1844`
- **Evidencia:** header con 6 botones y un logo, todos con emojis; `start_proactive_copilot` corre un `while True` sin stop; `messagebox` desde worker; `self.after` desde hilos.
- **Impacto:** la UI se congela o se rompe en Windows con fuentes que no renderizan emojis; el logo se recorta en un círculo de 46 px; el copiloto sigue vivo tras cerrar la ventana.
- **Fix:** shell de UI con navegación lateral, iconos SVG, event bus thread-safe y cierre cooperativo. Ver `docs/UI_META_REDESIGN.md`.

---

## 4. Tabla consolidada

| ID | Prio | Archivo:línea | Hallazgo | Impacto | Fix |
|---|---|---|---|---|---|
| E-01 | P0 | `src/main.py:13` | `faster_whisper` en top-level | No arranca | Import perezoso + startup check |
| E-02 | P0 | `permissions.py:59-77` | Default allow / strict off | Acciones peligrosas sin aprobación | Default deny + approval service |
| E-03 | P0 | `simplex_bridge.py:390,487-612` | Auto-accept + tareas arbitrarias | Ejecución remota no autorizada | Pairing + allowlist + comandos cerrados |
| E-04 | P0 | `os_executor.py:68-71,657-680,1582-1599` | `shell=True`, `DEL` absoluto | RCE / borrado fuera del workspace | `argv`, sandbox de rutas, papelera |
| E-05 | P0 | `main.py:1842` + `permissions.py:65` | Tkinter desde worker | Crash/bloqueo de UI | Approval en hilo principal vía event bus |
| E-06 | P1 | `main.py:830` | `ImageTk` no importado | Splash sin logo | Import correcto / `CTkImage` |
| E-07 | P1 | `main.py:1230` | `e` late-bound en lambda | `NameError`, error perdido | `err=str(e)` |
| E-08 | P1 | `main.py:662` | `call_ollama` args invertidos + attr inexistente | Copiloto muerto | Firma correcta + mock test |
| E-09 | P1 | `memory_gc.py:51` | `call_ollama` args invertidos | Memoria sin compactar | Firma correcta + test |
| E-10 | P1 | `simplex_bridge.py:424/618` | `_on_close` duplicado | Timers y reconexión rotos | Una implementación idempotente |
| E-11 | P1 | `main.py:152/908` | Bridge reinicializado | Callback/estado inconsistente | Servicio único con lifecycle |
| E-12 | P1 | `main.py:676/880,2153/2499`; `os_executor.py:19/813`; `cerebro.py:396` | Duplicados | Comportamiento impredecible | Eliminar + CI `F811` |
| E-13 | P1 | `main.py:1159/1846` | Gateways remotos duplicados | Comandos inconsistentes | Router único |
| E-14 | P1 | `os_executor.py:1092` | `images` ignorado | Visión falsa | Proveedor multimodal real |
| E-15 | P1 | `main.py:417`; `ollama_client.py:6` | Rutas de otro usuario | Recursos no encontrados | `Path.home()` + config |
| E-16 | P1 | `project_manager.py:57-85` | Falso DAG | Paralelismo incorrecto | DAG explícito + persistencia |
| E-17 | P1 | `config_manager.py:25-43` | Fallback silencioso | Config perdida | Pydantic + atomic write |
| E-18 | P1 | `headless_web.py:21-70` | Sin citas verificables | Brief no defendible | Citation guard + entailment |
| E-19 | P1 | `doc_factory.py:70-84` | Error del LLM oculto | Artefacto genérico | Validación + estado `DEGRADED` |
| E-20 | P1 | `main.py:389-482` | UI frágil | Mala demo | Shell nuevo + iconos SVG |

---

## 5. Deuda técnica que no debe cruzar al repo nuevo

| Deuda | Evidencia | Regla para el repo nuevo |
|---|---|---|
| `except:` desnudo | **103** ocurrencias | `except Exception` con logging estructurado; ruff `E722` bloqueante |
| `try/except/pass` | **96** ocurrencias | Prohibido en rutas críticas; usar `Result`/excepción explícita |
| `shell=True` | **18** ocurrencias | Prohibido; `subprocess.run([...])` con allowlist |
| Imports sin usar | **109** | `ruff F401` bloqueante |
| Variables sin usar | **32** | `ruff F841` bloqueante |
| `assert` para control | **4** | `assert` solo en tests; usar excepciones |
| Logs sin rotación | `simplex_raw_debug.json`, `simplex_debug.log` | logging JSONL con redacción y rotación |
| Rutas relativas al CWD | `permissions.py:38`, `heartbeat.py:11`, `document_engine.py:6` | `app_data_dir()` explícito |
| Sin tests | 0 | pytest + contract tests desde el primer commit |

---

## 6. Qué significa para Orunex Mission Control

El repo nuevo no debe “heredar” estos patrones. La arquitectura mínima debe incluir:

1. **Arranque verificable:** un `doctor` que valide Python, dependencias, modelo/proveedor y permisos; la UI arranca en modo degradado si falta algo.
2. **Proveedor de modelos abstracto:** `MetaProvider` real + `MockProvider` para desarrollo; nunca llamadas directas a un GGUF desde la UI.
3. **Política default deny:** cada tool declara `risk`, `scopes`, `requires_approval`; el runtime pide aprobación y la UI la muestra.
4. **Sandbox:** workspace raíz, `Path.resolve()`, allowlist de comandos, sin `shell=True`, papelera.
5. **Estado durable:** SQLite WAL + event log; misiones reanudables tras cerrar la app.
6. **Contratos tipados:** Pydantic para tools, misiones, artefactos, approvals y mensajes de Simplex.
7. **Observabilidad:** trace por misión, costo, latencia, fuentes y decisiones; logs redactados.
8. **Tests:** unitarios de políticas, contract tests de proveedores, tests de reconexión y un smoke test de UI.

---

## 7. Pruebas que deben existir antes de la demo

```text
tests/test_startup.py
  - la app arranca sin Meta key usando MockProvider
  - falta una dependencia -> mensaje claro, no traceback

tests/test_permissions.py
  - tag desconocido -> DENY
  - DEL fuera del workspace -> DENY
  - approval expirado -> DENY
  - approval desde UI thread -> OK

tests/test_tools.py
  - shell=True no existe en el código
  - path traversal -> DENY
  - comando no allowlisted -> DENY

tests/test_missions.py
  - pausa/reanudación tras reinicio
  - artefacto degradado si el modelo falla
  - citation guard bloquea claim sin fuente

tests/test_simplex.py
  - contacto no emparejado -> ignora
  - replay -> ignora
  - archivo > límite -> rechaza
  - reconnect -> estado consistente
```

---

## 8. Conclusión

Los errores más peligrosos no son los que impiden arrancar: son los que **parecen funcionar**. El copiloto que nunca sugiere, la memoria que nunca compacta, el splash que cae al fallback, la visión que no ve y los permisos que dicen “aprobado” sin preguntar. Para el hackathon, la historia debe ser la contraria: cada capacidad debe ser visible, verificable y reversible.

La decisión recomendada sigue siendo construir `orunex-mission-control` como un runtime nuevo, con `MockProvider` desde el día uno y un `PolicyEngine` que haga imposible repetir E-02/E-03/E-04.
