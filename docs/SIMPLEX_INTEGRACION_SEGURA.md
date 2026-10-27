# Simplex Bridge → Orunex Link

**Revisión de seguridad, fiabilidad y diseño de integración**  
**Fecha:** 21 de octubre de 2026  
**Archivo revisado:** `src/_orunex_libs/simplex_bridge.py` (765 líneas)  
**Configuración revisada:** `src/config/simplex.json`  
**Decisión:** mantener Simplex como canal remoto opcional, pero **no** como puerta de ejecución arbitraria. Se reescribe como **Orunex Link**, un canal E2E con emparejamiento explícito, allowlist y aprobaciones.

---

## 1. Por qué conservarlo

Simplex tiene una propiedad que ningún chat corporativo ofrece para este hackathon:

- Es **E2E por diseño** y descentralizado; no depende de WhatsApp, Telegram ni de un servidor propio.
- Permite que el teléfono hable con el desktop **sin abrir puertos** ni depender de la misma red.
- Es un diferenciador real: “tu agente sigue disponible aunque no estés frente al PC”.
- Ya existe un intento funcional en el proyecto: WebSocket al CLI local, envío de mensajes, archivos, screenshots y comandos.

El problema no es Simplex. El problema es cómo el bridge actual convierte **cualquier mensaje de cualquier contacto** en una tarea del agente. La versión nueva debe conservar el canal y eliminar la superficie de ejecución.

---

## 2. Cómo funciona hoy

```text
Teléfono (Simplex)
        │  mensaje E2E
        ▼
Simplex CLI local  ── WebSocket ws://127.0.0.1:5227 ──►  SimplexBridge
                                                          │
                                                          ├─ newChatItems
                                                          ├─ _parse_remote_command()
                                                          ├─ on_command("SIMPLEX_TASK:...")
                                                          └─ main.py → cerebro → os_executor
```

Flujo real:

1. `start_daemon()` descarga/ejecuta `simplex-chat.exe` en el puerto 5227.
2. `SimplexBridge.connect()` abre un WebSocket y espera hasta 45 s.
3. Al conectar, envía `/set auto-accept-member-contacts true`.
4. Al recibir una solicitud de contacto, intenta aceptarla con varias variantes de comando.
5. Al recibir `newChatItems`, toma el `localDisplayName` del contacto, actualiza `_last_contact_name` y procesa el texto.
6. Si el texto no es un comando conocido, crea un hilo y lo pasa al agente como tarea.
7. Los comandos `!archivo`, `!captura`, `!stop` y `!heartbeat` se ejecutan directamente.

La arquitectura es razonable; la política de confianza es invertida: **primero ejecuta, después pregunta**.

---

## 3. Hallazgos

### P0 — críticos

#### S-01 · Auto-aceptación de solicitudes de contacto

- **Líneas:** `simplex_bridge.py:390`, `487-542`
- **Evidencia:** se envía `auto-accept-member-contacts true` y, ante `receivedContactRequest`/`contactRequest`, se prueban `/accept`, `/ac`, `/address accept` y `accept-contact-request` sin intervención del usuario.
- **Impacto:** cualquiera con el enlace de invitación puede convertirse en contacto y, a partir de ahí, enviar comandos.
- **Fix:** el emparejamiento debe ser una acción explícita del usuario. El bridge no acepta nada automáticamente; una solicitud desconocida se registra como `BLOCKED` y se muestra en la UI.

#### S-02 · `auto-accept-new-contacts` persistido

- **Líneas:** `simplex_bridge.py:540`
- **Evidencia:** además del auto-accept de solicitudes, se activa `auto-accept-new-contacts true` y se guarda con `/save`.
- **Impacto:** la configuración queda persistida en el perfil de Simplex; no basta con cerrar la app.
- **Fix:** eliminar el comando; el perfil nuevo debe empezar con `auto-accept-*` desactivado. Documentar cómo auditar el perfil.

#### S-03 · Cualquier mensaje natural se ejecuta como tarea

- **Líneas:** `simplex_bridge.py:280-285`, `592-612`
- **Evidencia:** el `else` de `_parse_remote_command()` crea `threading.Thread(target=self._async_task, args=(text,))`; `_async_task` llama a `on_command(f"SIMPLEX_TASK:{task}")`.
- **Impacto:** “borra mis descargas”, “abre esta URL”, “envía el archivo X” se convierten en una orden del agente sin confirmación. No hay diferencia entre un contacto emparejado y un atacante.
- **Fix:** comandos cerrados por defecto. El modo “operador” (texto libre) es un scope explícito, con confirmación en el desktop y rate limit. Ver §5.3.

#### S-04 · No hay allowlist; el último contacto gana

- **Líneas:** `simplex_bridge.py:599-602`, `321-329`
- **Evidencia:** en cada `newChatItems` se hace `self._last_contact_name = contact_name`; `_send_text()` responde a `_last_contact_name`. No se compara con `last_contact_id` ni con un fingerprint.
- **Impacto:** un contacto no autorizado puede enviar un mensaje y convertirse en el destinatario de la siguiente respuesta, archivo o screenshot. Es un *reply hijack*.
- **Fix:** resolver el remitente por `contactId`, no por nombre; comprobar allowlist; enviar siempre al `contactId` emparejado. El nombre es solo presentación.

#### S-05 · Exfiltración de archivos con `!archivo`

- **Líneas:** `simplex_bridge.py:238-247`
- **Evidencia:** recorre `orunex_outputs` y envía el primer archivo cuyo nombre contenga el texto pedido. No hay autenticación, manifest, checksum ni límite de tamaño.
- **Impacto:** un contacto puede pedir `!archivo: contraseña`, `!archivo: nomina` o `!archivo: .env` y recibir cualquier archivo que esté en ese árbol. Si el agente guarda secretos ahí, es una fuga directa.
- **Fix:** solo artefactos registrados en la misión, por `artifact_id`, con allowlist de MIME, tamaño máximo y checksum. Nunca resolver por substring de nombre.

#### S-06 · Screenshot remoto sin consentimiento

- **Líneas:** `simplex_bridge.py:249-251`, `210-227`
- **Evidencia:** `!captura` llama a `send_screenshot()`; `pyautogui.screenshot()` captura la pantalla completa y la envía.
- **Impacto:** el teléfono puede ver correo, banca, chats y cualquier ventana abierta. Es una fuga de privacidad crítica y un problema de cumplimiento.
- **Fix:** desactivado por defecto; solo con aprobación explícita en el desktop, ventana activa o región seleccionada, marca de agua y caducidad. Nunca capturar pantalla completa por un comando de texto.

#### S-07 · Log crudo de todos los mensajes

- **Líneas:** `simplex_bridge.py:437-438`
- **Evidencia:** cada mensaje recibido se escribe en `simplex_raw_debug.json` sin redacción, rotación ni permisos.
- **Impacto:** el historial E2E queda en claro en disco; cualquiera con acceso al PC puede leerlo. Crecimiento indefinido.
- **Fix:** logging estructurado con redacción, rotación y nivel; por defecto no loguear contenido, solo metadatos (`message_id`, `contact_hash`, `type`, `size`).

#### S-08 · Descarga y ejecución de un binario sin verificación

- **Líneas:** `simplex_bridge.py:635-672`, `674-709`
- **Evidencia:** descarga `simplex-chat-windows-x86-64.exe` desde GitHub, valida solo tamaño > 20 MB y cabecera `MZ`; luego `taskkill /f /im simplex-chat.exe /t` y `Popen(..., shell=True)`.
- **Impacto:** un binario comprometido o una URL manipulada se ejecuta con los privilegios del usuario. `taskkill` mata **todas** las instancias de Simplex, incluidas las del usuario.
- **Fix:** no auto-descargar; exigir instalación del usuario; fijar versión y SHA-256; verificar firma; gestionar solo el PID propio; `argv` sin `shell=True`.

### P1 — fiabilidad y Privacidad

#### S-09 · `_on_close` duplicado

- **Líneas:** `424-432` y `618-620`
- **Evidencia:** la segunda definición reemplaza a la primera. La primera cancelaba el heartbeat, reseteaba `_connecting` y limpiaba `ws`; la segunda solo cambia dos flags.
- **Impacto:** timers vivos, estado inconsistente y reconexiones duplicadas.
- **Fix:** una sola implementación idempotente, con lock y `stop_event`.

#### S-10 · Reconexión infinita y sin control

- **Líneas:** `135-147`
- **Evidencia:** `finally` siempre hace `time.sleep(5)` y lanza `connect()` en otro hilo. `disconnect()` no cancela ese ciclo.
- **Impacto:** después de cerrar la app o desactivar el canal, el bridge puede seguir intentando conectar; se crean instancias y hilos acumulados.
- **Fix:** máquina de estados con `DISABLED`, `PAIRING`, `LINKED`, `DEGRADED`, `LOCKED`; backoff exponencial con jitter y `stop_event`; `disconnect()` detiene el ciclo.

#### S-11 · `connect()` bloquea hasta 45 segundos

- **Líneas:** `89-133`
- **Evidencia:** bucle `for i in range(45): time.sleep(1)`.
- **Impacto:** si se llama desde la UI, congela la app. Aunque el modal actual lo lanza en background, el método no está diseñado para ser no bloqueante.
- **Fix:** `connect()` asíncrono que retorna un `Future`/estado; la UI solo observa el estado.

#### S-12 · Un hilo por mensaje, sin límite

- **Líneas:** `280-285`
- **Evidencia:** `threading.Thread(...).start()` por cada mensaje libre.
- **Impacto:** un contacto puede inundar y agotar memoria/hilos; el agente ejecuta tareas concurrentes sobre el mismo estado.
- **Fix:** cola acotada + worker pool de 1-2; descarte con `BUSY`; rate limit.

#### S-13 · Sin deduplicación, replay ni rate limit

- **Líneas:** `592-612`
- **Evidencia:** no se usa `messageId`, timestamp ni nonce. El cooldown de 10 s (`:594`) descarta mensajes legítimos al inicio y no evita replay posterior.
- **Impacto:** un mensaje repetido puede ejecutar la misma tarea varias veces; un atacante puede hacer fuerza bruta de comandos.
- **Fix:** `message_id` único persistido, ventana de replay, rate limit por contacto y por comando.

#### S-14 · Archivos completos en Base64 sin límite

- **Líneas:** `188-208`
- **Evidencia:** `base64.b64encode(f.read())`; no hay `max_size`, streaming, checksum ni target explícito.
- **Impacto:** un archivo de 500 MB consume RAM y bloquea el WebSocket; el comando `APIFileSend` puede enviarse al contacto equivocado.
- **Fix:** streaming por chunks, máximo 25 MB, `contactId` obligatorio, checksum SHA-256 y estado de transferencia.

#### S-15 · WebSocket local sin autenticación

- **Líneas:** `38-39`, `103-111`
- **Evidencia:** `ws://127.0.0.1:5227`; cualquier proceso local puede conectarse si el puerto está abierto.
- **Impacto:** malware local o un script puede hablar con el CLI y suplantar al bridge. No es el riesgo principal, pero rompe el modelo de confianza.
- **Fix:** puerto efímero o socket con token local; comprobar que el proceso es el CLI esperado; no exponer el puerto en LAN.

#### S-16 · Configuración peligrosa por defecto y persistida

- **Archivo:** `src/config/simplex.json:8-11`
- **Evidencia:** `"remote_commands": true`, `"last_contact_name": "Arturo_1"`, `"last_contact_id": "5"`.
- **Impacto:** el canal arranca en modo ejecución y confía en un contacto persistido. Si el perfil se copia a otra máquina, la confianza viaja con él.
- **Fix:** `remote_commands` false por defecto; el pairing se guarda con fingerprint y expira si cambia el dispositivo; migración explícita.

#### S-17 · Errores silenciados

- **Líneas:** `59-60`, `207-208`, `335-336`, `613-614`, `653-654`, `707-709`, `760-761`
- **Evidencia:** varios `except:`/`except Exception` sin log.
- **Impacto:** el bridge “parece conectado” pero no envía; los fallos de red no se diagnostican.
- **Fix:** excepciones tipadas, logging con `corrId`, estado `DEGRADED` visible en UI.

#### S-18 · Comandos de heartbeat remotos

- **Líneas:** `259-267`, `407-418`
- **Evidencia:** `!heartbeat on/off` puede activar el daemon proactivo; `_start_heartbeat()` envía `/sa` cada 60 s.
- **Impacto:** un contacto puede iniciar ejecuciones periódicas no solicitadas; `/sa` puede competir con la generación del enlace de invitación.
- **Fix:** heartbeat es una preferencia local, no un comando remoto. Solo `/status`, `/stop` y approvals son remotos por defecto.

#### S-19 · Parseo frágil de comandos

- **Líneas:** `231-285`
- **Evidencia:** `!heartbeat` usa `"on" in text`; `!archivo:` corta por índice fijo; los comandos no tienen versión ni JSON schema.
- **Impacto:** falsos positivos (“!heartbeat only”), ambigüedad y difícil testeo.
- **Fix:** protocolo JSON versionado con `type`, `id`, `payload`; parser estricto + tests.

#### S-20 · `send_file()` no verifica el destino ni el estado

- **Líneas:** `188-208`
- **Evidencia:** no comprueba `linked`, no usa `_last_contact_name`, no registra el `corrId`; el `except` devuelve `False` sin detalle.
- **Impacto:** archivos enviados al contacto activo equivocado o silenciosamente perdidos.
- **Fix:** `send_artifact(contact_id, artifact_id)` con confirmación y estado.

#### S-21 · `_clean_simplex_text` puede corromper contenido

- **Líneas:** `17-29`
- **Evidencia:** elimina `{...}` y `[MAYUS:...]`; puede borrar citas, fórmulas o fragmentos de código.
- **Impacto:** el reporte que llega al teléfono no coincide con el artifact.
- **Fix:** no limpiar contenido de artefactos; solo sanear mensajes de estado. Enviar archivos completos, no texto truncado.

#### S-22 · `send_file`/screenshot no tienen cupo ni auditoría

- **Líneas:** `188-227`
- **Evidencia:** no hay `audit_log` de envíos, ni contador, ni consentimiento.
- **Impacto:** no se puede responder “¿qué se envió y cuándo?” en una demo o incidente.
- **Fix:** auditoría append-only con `actor`, `device`, `artifact`, `hash`, `size`, `approval_id`.

#### S-23 · Versión del CLI fijada a v6.4.10

- **Líneas:** `658`
- **Evidencia:** URL y sintaxis asumen una versión concreta; los comandos `/accept`, `/ac`, `/address accept` son intentos a ciegas.
- **Impacto:** una actualización del CLI rompe el bridge; una versión vieja puede tener CVEs.
- **Fix:** adaptador con versión soportada, `--version` check y tests contra un fake server; no “probar comandos” en producción.

#### S-24 · `taskkill` global

- **Líneas:** `685`
- **Evidencia:** `taskkill /f /im simplex-chat.exe /t`.
- **Impacto:** mata sesiones de Simplex del usuario y otros perfiles.
- **Fix:** guardar el PID del proceso propio y terminarlo con `terminate()`/`kill()`; nunca por nombre de imagen.

#### S-25 · Logs y base de datos en el CWD

- **Líneas:** `40`, `437`, `688`, `691`
- **Evidencia:** `config/simplex.json`, `simplex_raw_debug.json`, `simplex_data/` y `simplex_debug.log` cuelgan del directorio de trabajo.
- **Impacto:** si se lanza desde otra carpeta, se crea un perfil nuevo; los datos quedan dispersos y fáciles de commitear por accidente.
- **Fix:** `%LOCALAPPDATA%/Orunex/link/` (o `app_data_dir()`), permisos restrictivos y `.gitignore`.

---

## 4. Modelo de amenazas

| Actor | Capacidad | Activo en riesgo | Mitigación |
|---|---|---|---|
| Contacto Simplex no emparejado | Enviar mensajes y solicitudes | Archivos, pantalla, shell, presupuesto | Allowlist + pairing + default deny |
| Contacto emparejado malicioso | Comandos dentro del canal | Datos, acciones del agente | Scopes, approvals, rate limit, audit |
| Proceso local | Conectarse al WS del CLI | Estado del bridge, comandos | Token local, puerto restringido, verificación de proceso |
| Sitio web/archivo malicioso | Prompt injection en una fuente | Acciones del agente | Tratar contenido como datos, no instrucciones; citation guard |
| Supply chain | Binario CLI comprometido | Ejecución local | Instalación manual + SHA-256/firma |
| Usuario legítimo ausente | Aprobar sin contexto | Acciones de riesgo | Código de aprobación en desktop, expiración, resumen de evidencia |

**Frontera de confianza:** el contenido de un mensaje Simplex es **entrada no confiable**, incluso si viene de un contacto emparejado. El pairing autentica el dispositivo, no la intención de cada mensaje. Toda acción de riesgo debe pasar por la política del runtime.

---

## 5. Diseño propuesto: Orunex Link

### 5.1 Principios

1. **Emparejamiento explícito:** el usuario ve un QR/código y confirma el dispositivo.
2. **Mínimo privilegio:** por defecto solo estado, misiones y artefactos; ejecución es un scope separado.
3. **Aprobación humana:** acciones de riesgo requieren un código de un solo uso mostrado en el desktop.
4. **Permisos por dispositivo:** cada teléfono tiene scopes y puede revocarse.
5. **Auditable:** cada comando, approval y archivo queda en un log append-only.
6. **Reversible:** kill switch y “pausar Link” siempre disponibles.

### 5.2 Máquina de estados

```text
DISABLED ── enable ──► PAIRING ── code verified ──► LINKED
    ▲                    │                           │
    │                    └── timeout/fail ──► LOCKED│
    │                                                │
    └──────────── disable ◄── LOCKED ◄── abuse/error ┘
                                  │
                                  └── degraded network ──► DEGRADED ──► LINKED
```

Estados visibles en desktop y Android:

- `DISABLED`: no hay proceso Simplex ni WebSocket.
- `PAIRING`: se muestra QR + código de 6 dígitos; expira en 5 minutos.
- `LINKED`: un dispositivo autorizado; comandos permitidos según scopes.
- `DEGRADED`: el CLI no responde o el WebSocket cayó; se reintenta con backoff.
- `LOCKED`: se detectó abuso, replay o demasiados fallos; requiere acción local.

### 5.3 Protocolo de comandos

Por defecto, **no hay lenguaje natural remoto**. El protocolo es cerrado y versionado:

| Comando | Scope | Riesgo | Respuesta |
|---|---|---|---|
| `/status` | `read` | SAFE | Estado, misión activa, costo, salud |
| `/missions` | `read` | SAFE | Últimas misiones y estado |
| `/mission <id>` | `read` | SAFE | Plan, pasos, artefactos |
| `/artifacts <mission_id>` | `read` | SAFE | Lista de artefactos registrados |
| `/artifact <artifact_id>` | `artifacts` | ELEVATED | Envía archivo si está en manifest y < 25 MB |
| `/approve <approval_id> <code>` | `approve` | ELEVATED | Aprueba una acción pendiente |
| `/deny <approval_id>` | `approve` | SAFE | Rechaza |
| `/stop` | `control` | SAFE | Kill switch, siempre permitido |
| `/help` | `read` | SAFE | Lista de comandos permitidos |
| `/task <texto>` | `operator` | DANGEROUS | Solo si el scope está activo; requiere confirmación en desktop |

El modo `operator` es opcional y explícito. Para el hackathon se puede mostrar, pero el demo principal usa comandos cerrados y approvals.

**Formato:**

```json
{
  "v": 1,
  "id": "msg_01J...",
  "type": "command",
  "command": "artifact",
  "payload": { "artifact_id": "art_024_pptx" },
  "ts": "2026-10-21T15:04:05Z"
}
```

El bridge valida `v`, `id`, `type`, `command`, `payload` con Pydantic. Un comando desconocido se rechaza y se audita; no se convierte en tarea.

### 5.4 Emparejamiento

1. Desktop genera `pairing_id` aleatorio (128 bits), código de 6 dígitos y QR con `pairing_id`.
2. El usuario escanea el QR desde Simplex; el desktop muestra `pairing_id`, nombre del dispositivo y fingerprint.
3. El teléfono envía `PAIR <pairing_id> <code> <device_name>`.
4. Desktop compara en tiempo constante, verifica expiración y crea el registro:

```json
{
  "device_id": "dev_...",
  "contact_id": "5",
  "contact_fingerprint": "sha256:...",
  "display_name": "Pixel 9 Pro",
  "scopes": ["read", "artifacts", "approve", "control"],
  "paired_at": "2026-10-21T15:00:00Z",
  "last_seen": "2026-10-21T15:04:00Z",
  "status": "LINKED"
}
```

5. El desktop **no** acepta solicitudes de otros contactos. Si llega una, se registra como `BLOCKED_UNKNOWN_CONTACT`.
6. `contact_id` y fingerprint son la identidad; el nombre es solo presentación. Nunca se actualiza `last_contact` por el último mensaje.

### 5.5 Aprobaciones

Para una acción de riesgo:

1. El runtime crea `approval_id` y muestra en el desktop: “Enviar `Q4_Board_Brief.pptx` a Arturo — código 482 913 — expira en 04:59”.
2. El teléfono envía `/approve <approval_id> <code>`.
3. El runtime valida: dispositivo emparejado, scope `approve`, código correcto, no usado, no expirado, misión activa.
4. Se ejecuta la acción y se escribe `APPROVED_BY_DEVICE` en el audit log.
5. Cualquier intento fallido incrementa el contador; 3 fallos → `LOCKED`.

El código de 6 dígitos es un segundo factor local: aunque el teléfono esté comprometido, no puede aprobar sin ver el desktop.

### 5.6 Archivos y screenshots

- Solo se envían **artefactos registrados** en el manifest de la misión.
- `artifact_id` → ruta resuelta dentro de `workspace/artifacts/<mission_id>/`; se verifica `Path.resolve().is_relative_to(...)`.
- Límite: 25 MB por archivo; 3 archivos por minuto.
- Checksum SHA-256 en el mensaje; el teléfono puede verificar.
- Screenshots: desactivados por defecto. Solo `request_screenshot` con aprobación, región/ventana explícita, marca de agua y borrado del temporal.
- Nunca enviar `.env`, claves, DBs de Simplex, logs ni rutas del sistema.

### 5.7 Rate limits y anti-DoS

| Límite | Valor inicial |
|---|---:|
| Comandos por minuto | 10 |
| Comandos por hora | 120 |
| Tareas `operator` por hora | 3 |
| Mensaje de texto | 4 KB |
| Archivo | 25 MB |
| Aprobaciones pendientes | 5 |
| Fallos de pairing | 5 → LOCKED |
| Replay window | 10 minutos + `message_id` persistido |

La cola es acotada; si está llena, responde `BUSY` y no crea hilos.

### 5.8 Fiabilidad

- Un solo `OrunexLinkService` por proceso.
- `start()`/`stop()` idempotentes; `disconnect()` detiene el `stop_event`.
- Reconnect con backoff exponencial: 1s, 2s, 4s, 8s, 30s (máx.), con jitter.
- Heartbeat local cada 30 s; si falla 3 veces → `DEGRADED`.
- WebSocket en un hilo dedicado; procesamiento en worker pool acotado.
- Estado compartido con lock; nunca `last_contact` global.
- Si el CLI no está instalado, `DISABLED` con instrucciones; no auto-descarga.

### 5.9 Persistencia

SQLite WAL en `%LOCALAPPDATA%/Orunex/link/link.db`:

```sql
CREATE TABLE link_devices (
  device_id TEXT PRIMARY KEY,
  contact_id TEXT UNIQUE NOT NULL,
  fingerprint TEXT NOT NULL,
  display_name TEXT NOT NULL,
  scopes TEXT NOT NULL,
  paired_at TEXT NOT NULL,
  last_seen TEXT,
  status TEXT NOT NULL
);

CREATE TABLE link_messages (
  message_id TEXT PRIMARY KEY,
  device_id TEXT,
  direction TEXT NOT NULL,
  command TEXT,
  payload_hash TEXT,
  received_at TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE link_approvals (
  approval_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  status TEXT NOT NULL
);

CREATE TABLE link_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  device_id TEXT,
  event TEXT NOT NULL,
  detail_redacted TEXT NOT NULL
);
```

Nunca guardar el contenido completo del mensaje ni el código de aprobación en claro.

### 5.10 UX del canal

**Desktop**

- Panel “Orunex Link” en la barra lateral: estado, dispositivo, último seen, botón “Pausar”.
- Modal de pairing: QR, código, nombre del dispositivo, fingerprint, expiración.
- Lista de dispositivos con scopes y “Revocar”.
- Bandeja de approvals con evidencia y código.
- Auditoría filtrable.

**Android**

- Tab “Link”: estado, “Pausar canal”, dispositivos, approvals.
- Notificaciones push locales para approvals.
- Nunca mostrar comandos crudos sin contexto; mostrar “Acción: enviar artifact” y “Riesgo: bajo”.

### 5.11 Protocolo de ejemplo

**Pairing**

```text
Phone → Desktop: PAIR pair_7f3a 482913 "Pixel 9 Pro"
Desktop → Phone: PAIRED dev_9c1 scopes=read,artifacts,approve,control
```

**Estado**

```text
Phone → Desktop: {"v":1,"id":"m1","type":"command","command":"status"}
Desktop → Phone: {"v":1,"id":"m1","type":"result","ok":true,
  "data":{"mission":"Q4 Boardroom Brief","state":"RUNNING","cost":1.84}}
```

**Approval**

```text
Desktop: approval_id=apr_42 code=482913 action=send_artifact art_024_pptx
Phone → Desktop: {"v":1,"id":"m2","type":"command","command":"approve",
  "payload":{"approval_id":"apr_42","code":"482913"}}
Desktop → Phone: {"v":1,"id":"m2","type":"result","ok":true,"data":{"status":"APPROVED"}}
```

### 5.12 Test plan

```text
test_pairing_rejects_unknown_contact
test_pairing_code_expires
test_pairing_code_is_single_use
test_unpaired_contact_cannot_execute
test_allowlisted_contact_gets_status
test_replay_is_rejected
test_operator_task_requires_scope_and_approval
test_approval_wrong_code_locks_device
test_artifact_must_be_in_manifest
test_artifact_path_traversal_denied
test_artifact_size_limit
test_screenshot_requires_approval
test_rate_limit_busy
test_reconnect_backoff_and_state
test_kill_switch_always_works
test_cli_missing_does_not_download
test_only_one_service_instance
```

Usar un **fake Simplex WebSocket server** para no depender del CLI en CI. El server emite `newChatItems`, `contactRequest`, `contactAdded`, `subscriptionEnd` y errores.

### 5.13 Demo de 3 minutos

1. Desktop muestra “Orunex Link · no paired”. El usuario escanea el QR.
2. Teléfono: `/status` → devuelve misión y costo.
3. Teléfono: `/artifacts 024` → lista `Q4_Board_Brief.pptx`.
4. Teléfono: `/artifact art_024_pptx` → desktop muestra approval con código.
5. Teléfono: `/approve apr_42 482913` → archivo llega, con hash.
6. Teléfono: `/stop` → misión se detiene; desktop muestra audit.
7. Desktop: “Pausar Link” → el teléfono recibe `LINK_PAUSED`.

Ese flujo demuestra el valor de Simplex sin convertirlo en una puerta trasera.

### 5.14 Migración por fases

| Fase | Cambio | Criterio de salida |
|---|---|---|
| 0 | En el repo nuevo, `remote_commands=false`, sin auto-accept, bridge desactivado | App arranca sin Simplex |
| 1 | Adaptador `OrunexLinkService` + fake server + `/status`, `/missions` | Tests verdes; solo lectura |
| 2 | Pairing + SQLite + `/artifacts` + approval de archivos | Demo de artifact |
| 3 | `/approve`, `/stop`, rate limits, audit | Seguridad verificada |
| 4 | Modo `operator` opcional y app Android directa | Canal primario Android; Simplex fallback |

### 5.15 Criterios de aceptación

- [ ] Un contacto no emparejado no puede ejecutar ni recibir archivos.
- [ ] El pairing requiere acción local y expira.
- [ ] `!archivo` y `!captura` ya no existen como comandos libres.
- [ ] Todo artifact se sirve por ID y manifest, no por path.
- [ ] Las approvals usan código de un solo uso y expiran.
- [ ] Hay rate limit, dedupe y replay protection.
- [ ] El bridge no descarga ni mata procesos ajenos.
- [ ] `disconnect()` detiene reconexión y timers.
- [ ] La UI muestra `DISABLED/PAIRING/LINKED/DEGRADED/LOCKED`.
- [ ] Hay tests con fake server y auditoría consultable.

---

## 6. Conclusión

Simplex puede ser el detalle que hace que Orunex se vea como un producto real: el agente sigue accesible desde el teléfono sin abrir un puerto y sin depender de una nube. Pero el bridge actual confunde **“mensaje recibido”** con **“orden autorizada”**. Orunex Link debe invertir esa relación: identidad explícita, comandos cerrados, approvals y auditoría. Así el canal suma valor en lugar de ser el vector de ataque más obvio del proyecto.
