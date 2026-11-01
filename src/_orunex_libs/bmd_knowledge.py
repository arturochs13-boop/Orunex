"""Verified knowledge pack for the local BMD Engine (Blockchain Markdown).

Every statement in this module was checked against the C11 sources, the FFI
binding, the CLI binary and real executions of ``bmd_engine/bin/bmd_cli.exe``
in this repository.  It is intentionally written as small, self-contained
entries so FAISS can retrieve exactly the fact the agent needs instead of a
single giant document.

The pack is injected into the Orunex Meta FAISS memory under ``kind="bmd"``.
``sync_bmd_knowledge`` is idempotent: it replaces the BMD namespace when the
pack version or its content fingerprint changes, and leaves other namespaces
(code, episodes, strategies, capabilities) untouched.

Important engine facts verified against the C11 sources, the FFI binding, the
CLI binary and real executions:

* the compiled engine reports **v2.1.0**;
* the real digest is **SHA-512** (128 hex chars), as implemented in
  ``bmd_engine.c`` and exposed by ``BMD_HASH_HEX_LEN = 128``;
* v2.1 replaced ``--compile-sign``/``--co-sign``/``freeze``/``accept`` with
  ``sign <file> <seed>`` and ``cosign <file> <seed>``;
* v2.1 added ``max_signatures`` governance, ``read``, ``lock`` and ``redact``;
* ``sign`` and ``cosign`` default to demo seeds when no seed is supplied.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional

BMD_KIND = "bmd"
BMD_KNOWLEDGE_VERSION = "bmd-engine-2.1.0/orunex-pack-3"


# ---------------------------------------------------------------------------
# Knowledge entries
# ---------------------------------------------------------------------------
BMD_KNOWLEDGE: List[Dict[str, Any]] = [
    {
        "knowledge_id": "bmd.overview",
        "title": "BMD Engine: qué es Blockchain Markdown y para qué sirve",
        "tags": [
            "bmd",
            "blockchain markdown",
            "motor",
            "overview",
            "single source of truth",
            "gobernanza",
            "muse-spark",
        ],
        "text": (
            "Blockchain Markdown (.bmd) es un lenguaje documental propietario "
            "implementado por el subproyecto bmd_engine en la raíz de Orunex. "
            "Combina un frontmatter YAML criptográfico con un payload Markdown "
            "legible por humanos. El motor está escrito en C11 puro, se compila "
            "como bmd_engine.dll y se opera con bmd_cli.exe; el binding Python "
            "es bmd_engine/python/bmd_ffi.py. Su objetivo es ser la Fuente Única "
            "de Verdad (Single Source of Truth) para transferir propiedad "
            "intelectual, contratos, actas y documentos financieros con "
            "inmutabilidad matemática, no repudio y trazabilidad. El binario "
            "compilado reporta la versión 2.1.0, que añade gobernanza de firmas "
            "con max_signatures, bloqueo del sistema de archivos y un editor "
            "interactivo redact. Componentes: parser YAML + "
            "Markdown, motor criptográfico Ed25519/SHA-512/ChaCha20, ledger de "
            "bloques con auditoría de cadena, visor HTML standalone, bundles de "
            "propiedad intelectual y exportación para agentes Office. En Orunex "
            "el agente puede crear borradores .bmd válidos, firmarlos, "
            "co-firmarlos, verificarlos, auditarlos y renderizarlos sin salir "
            "de la aplicación."
        ),
    },
    {
        "knowledge_id": "bmd.syntax.frontmatter",
        "title": "Sintaxis .bmd: frontmatter obligatorio, payload y normalización",
        "tags": [
            "bmd",
            "sintaxis",
            "frontmatter",
            "yaml",
            "block_id",
            "previous_hash",
            "current_hash",
            "payload",
        ],
        "text": (
            "Un archivo .bmd tiene dos secciones: (1) frontmatter delimitado por "
            "líneas '---' y (2) payload Markdown después del segundo delimitador. "
            "El parser exige tres claves: block_id, previous_hash y current_hash. "
            "Si falta cualquiera devuelve BMD_ERR_MISSING_REQUIRED_KEY (-5). "
            "Claves reconocidas: block_id (máx. 127 caracteres), previous_hash y "
            "current_hash (128 hex en v2.0), mode ('draft' o 'transfer'), "
            "signer_role ('emisor'/'emitter' o 'receptor'/'receiver'), timestamp "
            "(entero Unix), public_key, signature_layer_2, receiver_public_key, "
            "receiver_signature, payload_encrypted ('true'/'false'), y las "
            "directivas v2.0 document_type, jurisdiction, expiry_timestamp, "
            "witnesses_required, require_cosigner, co_sign_label, max_signatures, "
            "inject_property_path, property_bundle_hash, property_bundle_size y "
            "property_bundle_destroyed. max_signatures es la cuota v2.1: 0 = "
            "ilimitado, 1 = unilateral, 2 = bilateral, N = multipartita. Las "
            "comillas simples o dobles alrededor "
            "del valor son opcionales; los comentarios inline con '#' se "
            "eliminan fuera de comillas. El parser tolera BOM UTF-8 y normaliza "
            "CRLF a LF en el payload para que el hash sea independiente de la "
            "plataforma. Las claves desconocidas se ignoran al leer y se pierden "
            "al guardar: bmd_save_file serializa solo los campos conocidos."
        ),
    },
    {
        "knowledge_id": "bmd.hash.canonical",
        "title": "Hash canónico real: SHA-512 de 128 hex, no SHA-256",
        "tags": [
            "bmd",
            "hash",
            "sha512",
            "sha-512",
            "canonical",
            "integridad",
            "current_hash",
            "previous_hash",
        ],
        "text": (
            "El hash real del motor v2.1.0 es SHA-512 y se representa con 128 "
            "caracteres hexadecimales (BMD_HASH_HEX_LEN = 128). El README y la "
            "spec revisada ya documentan SHA-512; cualquier copia antigua que "
            "mencione SHA-256 de 64 hex está desactualizada. El payload se "
            "normaliza recortando espacios y saltos de línea al inicio y al "
            "final, y se calcula su SHA-512 en hex. Luego se forma la cadena "
            "canónica: block_id|previous_hash|mode|signer_role|"
            "timestamp|public_key|payload_encrypted(0/1)|payload_hex. Si existen "
            "campos extendidos (document_type, jurisdiction, expiry_timestamp, "
            "witnesses_required, require_cosigner, property_bundle_hash o "
            "max_signatures distinto de cero), se añade el sufijo "
            "|document_type|jurisdiction|expiry_timestamp|witnesses_required|"
            "require_cosigner(0/1)|property_bundle_hash|max_signatures. El "
            "SHA-512 de esa cadena es current_hash. Cualquier cambio en el "
            "payload o en esos campos cambia el hash y verify lo marca como "
            "TAMPERED. Los valores de mode y signer_role se canonicalizan a "
            "'draft'/'transfer' y 'emisor'/'receptor'/'unknown' antes de hashear."
        ),
    },
    {
        "knowledge_id": "bmd.modes",
        "title": "Modos draft y transfer: mutabilidad y reglas de verificación",
        "tags": [
            "bmd",
            "draft",
            "transfer",
            "modo",
            "inmutable",
            "estado",
            "sign",
            "transfer",
        ],
        "text": (
            "mode='draft' es la fase editable: se permite recalcular el hash y "
            "la firma es opcional. mode='transfer' es la congelación total de "
            "propiedad: la transición es irreversible y verify exige una firma "
            "Ed25519 válida del emisor; si public_key o signature_layer_2 están "
            "vacíos devuelve BMD_ERR_TRANSFER_VIOLATION (-13). Un draft con el "
            "hash correcto verifica OK sin firma. Para pasar de draft a transfer "
            "se usa el comando v2.1 'sign <archivo> <seed>' o la FFI "
            "transition_to_transfer. Nunca se debe editar a mano un bloque en "
            "transfer: cualquier mutación del payload invalida el hash y la "
            "auditoría de cadena lo rechaza. El co-sign del receptor no cambia "
            "current_hash; añade receiver_public_key y receiver_signature sobre "
            "el mismo hash, pero solo se permite si max_signatures es 0 o "
            "mayor que el número de firmas actuales."
        ),
    },
    {
        "knowledge_id": "bmd.signatures",
        "title": "Firmas Ed25519, roles emisor/receptor y seeds demo",
        "tags": [
            "bmd",
            "firma",
            "firmar",
            "firmo",
            "bloque",
            "ed25519",
            "emisor",
            "receptor",
            "sign",
            "cosign",
            "max_signatures",
            "seed",
            "no repudio",
        ],
        "text": (
            "La firma es Ed25519 (RFC 8032) sobre current_hash. En v2.1 el "
            "emisor usa 'bmd_cli.exe sign archivo.bmd <seed64hex>': calcula el "
            "hash SHA-512, cambia mode a transfer, llena public_key y "
            "signature_layer_2 y aplica el atributo de solo lectura del sistema "
            "de archivos. El receptor usa 'bmd_cli.exe cosign archivo.bmd "
            "<seed64hex>'; solo funciona si el bloque está en transfer, el hash "
            "verifica y max_signatures es 0 o mayor que el número de firmas "
            "actuales. cosign añade receiver_public_key y receiver_signature sin "
            "cambiar current_hash. Si max_signatures es 1, el motor rechaza la "
            "co-firma con BMD_ERR_SIGNATURE_LIMIT_EXCEEDED (30). Las seeds son "
            "32 bytes (64 hex). Sin seed explícita, sign usa 32 bytes 0x42 y "
            "cosign usa 32 bytes 0x99; son seeds de demostración públicas y no "
            "deben usarse en producción. genkey genera un par aleatorio. Los "
            "comandos antiguos --compile-sign, --co-sign, freeze y accept ya no "
            "existen en el dispatch de v2.1; el wrapper de Orunex los traduce a "
            "sign/cosign."
        ),
    },
    {
        "knowledge_id": "bmd.signature.governance",
        "title": "Gobernanza de firmas v2.1: max_signatures, unilateral, bilateral y multipartita",
        "tags": [
            "bmd",
            "max_signatures",
            "gobernanza",
            "firmas",
            "unilateral",
            "bilateral",
            "multipartita",
            "cosign",
            "signature cap",
            "error 30",
        ],
        "text": (
            "max_signatures es la cuota de firmas que introdujo el motor v2.1.0. "
            "Valores: 0 = sin límite; 1 = unilateral, solo firma el emisor y "
            "cosign siempre se rechaza; 2 = bilateral, emisor + receptor; N = "
            "multipartita con N firmas como máximo. El motor cuenta la firma del "
            "emisor como 1 y la del receptor como +1; antes de co-firmar "
            "compara el conteo actual con la cuota y, si current_sig_count >= "
            "max_signatures, devuelve BMD_ERR_SIGNATURE_LIMIT_EXCEEDED (30) con "
            "el mensaje 'Governance Error: max_signatures cap reached — "
            "co-signature rejected'. require_cosigner y co_sign_label son pistas "
            "de interfaz; la regla que realmente aplica el motor es "
            "max_signatures. Un contrato bilateral debe declarar "
            "max_signatures: 2; una declaración unilateral, 1. El campo se "
            "serializa solo cuando es mayor que 0, el parser acepta el valor "
            "entre comillas o sin ellas y, cuando es distinto de 0, forma parte "
            "de la cadena canónica del hash: alterarlo invalida la verificación. "
            "inspect muestra 'Max Signatures' y verify --json distingue "
            "current_state draft, signed o dual_signed. "
            "La cuota es un tope, no una obligación: el motor no verifica que "
            "las partes reales coincidan con N."
        ),
    },
    {
        "knowledge_id": "bmd.contracts",
        "title": "Contratos .bmd como experto: estructura, cláusulas y gobernanza",
        "tags": [
            "bmd",
            "contrato",
            "contratos",
            "contract",
            "licencia",
            "license",
            "nda",
            "confidencialidad",
            "servicios",
            "services",
            "propiedad intelectual",
            "ip_transfer",
            "clausulas",
            "jurisdiccion",
            "firma",
            "max_signatures",
        ],
        "text": (
            "Para redactar un contrato .bmd como experto: (1) elige "
            "document_type (contract, license, nda, services, ip_transfer, "
            "testament, declaration o decree; el motor acepta cualquier cadena "
            "de hasta 63 caracteres); (2) declara jurisdiction, "
            "expiry_timestamp si hay vigencia, witnesses_required si la "
            "formalidad lo exige, require_cosigner y max_signatures (2 para "
            "bilateral, 1 para unilateral); (3) estructura el payload Markdown "
            "con título, partes (emisor y receptor con razón social, ID y "
            "domicilio), antecedentes, definiciones, objeto y alcance, "
            "obligaciones de cada parte, entregables y aceptación, precio y "
            "pago, plazo y terminación, confidencialidad, propiedad "
            "intelectual, declaraciones y garantías, limitación de "
            "responsabilidad, indemnización, fuerza mayor, notificaciones, ley "
            "aplicable y controversias, disposiciones generales y bloque de "
            "firmas; (4) usa las directivas <!-- bmd:parties -->, "
            "<!-- bmd:signatures -->, <!-- bmd:seal --> y "
            "<!-- bmd:clause id=\"...\" title=\"...\" --> para que el visor HTML "
            "presente el contrato; (5) deja entre corchetes los datos que no "
            "conozcas (partes, montos, plazos, jurisdicción) y nunca inventes "
            "cifras, fechas o identidades; (6) firma con sign como emisor y "
            "cosign como receptor; (7) verifica con verify --json y audita la "
            "cadena. Cláusulas mínimas por tipo: licencia (derechos otorgados, "
            "restricciones, regalías, plazo, terminación); NDA (definición de "
            "información confidencial, obligaciones, excepciones, plazo, "
            "devolución); servicios (objeto, entregables, aceptación, precio, "
            "obligaciones, terminación); transferencia de IP (activos, "
            "contraprestación, transferencia de titularidad, declaraciones, "
            "entrega). BMD garantiza integridad, no repudio y trazabilidad, no "
            "validez legal: la revisión de un abogado en la jurisdicción "
            "aplicable sigue siendo necesaria."
        ),
    },
    {
        "knowledge_id": "bmd.cli.reference",
        "title": "Referencia completa de bmd_cli.exe",
        "tags": [
            "bmd",
            "cli",
            "bmd_cli.exe",
            "comandos",
            "inspect",
            "verify",
            "read",
            "redact",
            "sign",
            "cosign",
            "lock",
            "render",
            "audit",
            "export-office",
            "genkey",
        ],
        "text": (
            "CLI real en bmd_engine/bin/bmd_cli.exe, versión 2.1.0. Comandos: "
            "read <file.bmd> o bmd <file.bmd> abre el visor nativo; verify "
            "<file.bmd> valida hash y firmas y devuelve 0 si es íntegro o 2 si "
            "está corrupto; verify --json <file.bmd> o --verify <file.bmd> "
            "devuelve JSON para automatización; inspect <file.bmd> muestra "
            "metadatos, max_signatures, hashes, modo, firmas y validación; "
            "redact [file.bmd] abre el editor de terminal interactivo para crear "
            "o editar un draft; sign <file.bmd> <seed64hex> calcula SHA-512, "
            "pasa a transfer, firma como emisor y aplica solo lectura; cosign "
            "<file.bmd> <seed64hex> co-firma como receptor solo si "
            "max_signatures >= 2; lock <file.bmd> aplica el atributo de solo "
            "lectura; genkey imprime seed y clave pública Ed25519; audit "
            "<b1.bmd> [b2.bmd ...] audita la cadena y devuelve 0 si hay "
            "consenso; render <file.bmd> [out.html] genera HTML standalone; "
            "--export-office <file.bmd> emite JSON de metadatos para Office; "
            "--inject-property <dir> <file.bmd> inyecta y cifra un directorio "
            "con semántica de movimiento; --extract-property <file.bmd> "
            "[--out <dir>] lo extrae. Ejecutar sin argumentos muestra la ayuda "
            "y devuelve 1. Los comandos de v2.0 --compile-sign, --co-sign, "
            "freeze, accept, seal y unseal ya no existen en el dispatch."
        ),
    },
    {
        "knowledge_id": "bmd.workflow.draft",
        "title": "Receta verificada para crear un borrador .bmd válido",
        "tags": [
            "bmd",
            "crear",
            "borrador",
            "draft",
            "workflow",
            "hash",
            "ffi",
            "receta",
        ],
        "text": (
            "Para crear un .bmd válido sin firma: (1) escribe el frontmatter con "
            "block_id único, previous_hash de 128 ceros para el primer bloque (o "
            "el current_hash del bloque padre), current_hash de 128 ceros, "
            "mode: draft, signer_role: emisor, timestamp Unix, max_signatures "
            "(0 = ilimitado, 1 = unilateral, 2 = bilateral, N = multipartita) y "
            "payload Markdown; "
            "(2) carga el archivo con bmd_ffi.BMDWrapper.load_file; (3) llama a "
            "_LIB.bmd_compute_hash(doc._doc, buffer) para obtener el hash real; "
            "(4) escribe ese hash en el campo current_hash del struct con "
            "ctypes.memmove(ctypes.addressof(hdr) + BMDHeader.current_hash.offset, "
            "buffer.value, len+1); (5) guarda con doc.save(path); (6) verifica "
            "con doc.verify() o con bmd_cli.exe verify. El struct BMDHeader del "
            "FFI debe incluir el campo max_signatures de v2.1 entre "
            "co_sign_label e inject_property_path; si falta, los campos "
            "posteriores quedan desalineados. No intentes calcular el "
            "hash en Python puro: la canonicalización exacta vive en el motor "
            "C11. Un draft correcto devuelve 'OK / Cryptographic Integrity "
            "Verified'. Si inspect muestra current_hash en ceros y computed_hash "
            "distinto, el archivo está TAMPERED."
        ),
    },
    {
        "knowledge_id": "bmd.workflow.transfer",
        "title": "Flujo de transferencia: compile-sign, verify, co-sign y auditoría",
        "tags": [
            "bmd",
            "transfer",
            "workflow",
            "firma",
            "cosign",
            "max_signatures",
            "auditoria",
            "cadena",
            "ledger",
        ],
        "text": (
            "Flujo recomendado para transferir propiedad o cerrar un contrato: "
            "(1) crear el draft con max_signatures: 2 si es bilateral, revisar "
            "el payload y completar los campos entre corchetes; (2) ejecutar "
            "'bmd_cli.exe sign archivo.bmd <seed_emisor>' para congelar, "
            "calcular SHA-512 y firmar como emisor; el archivo queda en solo "
            "lectura; (3) verificar con 'bmd_cli.exe verify archivo.bmd' o "
            "'verify --json'; (4) enviar al receptor y ejecutar 'bmd_cli.exe "
            "cosign archivo.bmd <seed_receptor>' (el wrapper de Orunex limpia "
            "el solo lectura antes de escribir); (5) verificar de nuevo: "
            "verify --json debe mostrar current_state dual_signed y hash_valid "
            "true; (6) auditar la cadena con 'bmd_cli.exe audit bloque1.bmd "
            "bloque2.bmd ...'. Si max_signatures es 1, cosign devuelve el error "
            "30. Para encadenar bloques, el previous_hash del hijo debe ser "
            "exactamente el current_hash del padre; el primer bloque usa 128 "
            "ceros. Un audit devuelve POSITIVE CONSENSUS solo si todos los "
            "bloques son válidos y los enlaces coinciden."
        ),
    },
    {
        "knowledge_id": "bmd.ffi",
        "title": "FFI de Python: BMDWrapper, generate_keypair y audit_chain",
        "tags": [
            "bmd",
            "ffi",
            "python",
            "ctypes",
            "bmd_ffi",
            "BMDWrapper",
            "dll",
            "api",
        ],
        "text": (
            "bmd_engine/python/bmd_ffi.py carga bmd_engine/bin/bmd_engine.dll "
            "con ctypes y expone BMDWrapper. Métodos: load_file(path), "
            "from_string(text), save(path), verify() -> (bool, mensaje), "
            "sign(seed32, role), transition_to_transfer(seed32), "
            "cosign_receiver(seed32), seal(key32, nonce12), unseal(key32, "
            "nonce12), y propiedades block_id, previous_hash, current_hash, "
            "mode, signer_role, public_key, signature_layer_2, "
            "receiver_public_key, receiver_signature, payload, document_type, "
            "jurisdiction, require_cosigner, co_sign_label, max_signatures, "
            "property_bundle_hash, property_bundle_size, "
            "property_bundle_destroyed y property_bundle_data. También expone "
            "generate_keypair(seed32=None) -> (public_key32, secret_key64) y "
            "audit_chain(filepaths) -> (bool, dict). Para escribir current_hash "
            "desde Python hay que usar la dirección del struct: "
            "ctypes.addressof(doc._doc.contents.header) + "
            "BMDHeader.current_hash.offset. Asignar doc.current_hash no "
            "funciona porque la propiedad es de solo lectura. El struct "
            "BMDHeader debe declarar max_signatures (ctypes.c_int) entre "
            "co_sign_label e inject_property_path; la DLL v2.1.0 lo añadió y "
            "omitirlo desalinea todos los campos posteriores. La DLL debe "
            "existir; si falta, el import lanza FileNotFoundError."
        ),
    },
    {
        "knowledge_id": "bmd.property",
        "title": "Bundles de propiedad intelectual: inject y extract",
        "tags": [
            "bmd",
            "property",
            "bundle",
            "ip",
            "propiedad intelectual",
            "chacha20",
            "pynacl",
            "inject",
            "extract",
        ],
        "text": (
            "--inject-property <dir> <file.bmd> comprime el directorio con zlib "
            "nivel 9, lo cifra con ChaCha20-Poly1305 mediante PyNaCl, lo codifica "
            "en base64 y lo incrusta en el frontmatter como bloque literal "
            "property_bundle: |. La clave se deriva con BLAKE2b de la seed "
            "privada, el block_id y el timestamp. Aplica semántica de movimiento: "
            "los archivos fuente se eliminan después de la inyección, por lo que "
            "es una operación destructiva que exige confirmación explícita y "
            "respaldo previo. Sin PyNaCl falla. --extract-property <file.bmd> "
            "--out <dir> descifra, descomprime y restaura los archivos; sin la "
            "seed privada correcta el bundle es opaco. Metadatos asociados: "
            "property_bundle_hash (SHA-512 del bundle cifrado), "
            "property_bundle_size y property_bundle_destroyed=true. No usar esta "
            "operación para pruebas rápidas sin una copia de seguridad."
        ),
    },
    {
        "knowledge_id": "bmd.ledger",
        "title": "Ledger y auditoría de cadena: enlaces, genesis y reporte",
        "tags": [
            "bmd",
            "ledger",
            "audit",
            "cadena",
            "genesis",
            "previous_hash",
            "consenso",
            "merkle",
        ],
        "text": (
            "El ledger BMD encadena bloques por previous_hash. El primer bloque "
            "es genesis y usa previous_hash formado solo por ceros; "
            "bmd_is_genesis_previous_hash acepta 64 o 128 ceros y un prefijo 0x. "
            "bmd_ledger_validate_link verifica la integridad del padre, la del "
            "hijo y que child.previous_hash == parent.current_hash. audit recibe "
            "uno o más archivos, produce un bmd_chain_report_t con total_blocks, "
            "valid_blocks, corrupted_blocks, last_valid_hash, failing_block_id, "
            "failure_reason y audit_summary, e imprime POSITIVE CONSENSUS o "
            "REJECTED DUE TO TAMPER/CHAIN BREACH. Código de salida 0 si hay "
            "consenso, 3 si la cadena está rota. La FFI audit_chain devuelve el "
            "mismo reporte como diccionario. Un bloque aislado válido no "
            "garantiza la cadena: hay que auditar el conjunto en orden."
        ),
    },
    {
        "knowledge_id": "bmd.render",
        "title": "Render HTML standalone y directivas del visor",
        "tags": [
            "bmd",
            "render",
            "html",
            "visor",
            "viewer",
            "directivas",
            "bmd:seal",
            "bmd:parties",
        ],
        "text": (
            "'bmd_cli.exe render archivo.bmd [salida.html]' delega en "
            "bmd_engine/python/bmd_viewer_generator.py y genera un HTML "
            "standalone sin dependencias, con tema oscuro, tipografía serif y "
            "sello visual. El payload admite directivas HTML comentadas: "
            "<!-- bmd:rule --> o <!-- bmd:rule double --> para líneas legales, "
            "<!-- bmd:parties --> para tarjetas de emisor y receptor, "
            "<!-- bmd:signatures --> para cajas de firma lado a lado, "
            "<!-- bmd:seal --> para el sello holográfico digital, "
            "<!-- bmd:clause id=\"...\" title=\"...\" --> para cláusulas "
            "formateadas y <!-- bmd:badge label=\"...\" --> para una etiqueta "
            "institucional. Si no se indica salida, el visor elige un nombre "
            "derivado del .bmd. El HTML muestra block_id, modo, integridad, "
            "hash SHA-512, hash ancestral, firmas y claves. Es solo una "
            "representación de lectura: no vuelve inmutable el documento."
        ),
    },
    {
        "knowledge_id": "bmd.office",
        "title": "Exportación Office: JSON del CLI y generador de acta",
        "tags": [
            "bmd",
            "office",
            "excel",
            "word",
            "export",
            "export-office",
            "acta",
            "csv",
        ],
        "text": (
            "--export-office <file.bmd> emite JSON con status "
            "(verified/unverified), block_id, document_type, mode, current_hash, "
            "emitter_pubkey, emitter_signature, receiver_pubkey, "
            "receiver_signature, dual_signed, timestamp y payload_length. No "
            "incluye el payload completo: para el contenido hay que leer el "
            ".bmd o usar bmd_engine/python/bmd_agent_executor.py. Ese script "
            "genera un acta HTML ejecutiva y un CSV de auditoría con campos "
            "BLOCK_ID, CURRENT_HASH_SHA512, PREVIOUS_HASH, OPERATIONAL_MODE, "
            "EMITTER_PUBKEY, EMITTER_SIGNATURE_ED25519, RECEIVER_PUBKEY, "
            "RECEIVER_SIGNATURE_ED25519, DUAL_SIGNED_STATUS, TIMESTAMP y "
            "PAYLOAD_CHAR_COUNT. En Orunex, el módulo office_expert puede tomar "
            "esos datos y producir DOCX/XLSX/PPTX reales con el mismo diseño "
            "profesional que el resto de entregables; no hay que inventar "
            "cifras ni firmas."
        ),
    },
    {
        "knowledge_id": "bmd.errors",
        "title": "Códigos de error y solución de problemas",
        "tags": [
            "bmd",
            "errores",
            "troubleshooting",
            "status",
            "tampered",
            "firma invalida",
            "syntax",
        ],
        "text": (
            "Códigos: 0 OK; -1 parámetro nulo; -2 archivo no encontrado; -3 sin "
            "memoria; -4 frontmatter inválido (faltan '---' o formato YAML); -5 "
            "falta block_id, previous_hash o current_hash; -6 modo inválido; -7 "
            "rol inválido; -8 hash no coincide (TAMPERED); -9 firma Ed25519 "
            "inválida; -10 cadena rota; -11 fallo de cifrado; -12 fallo de "
            "descifrado; -13 violación de transfer (falta firma en modo "
            "transfer); -14 buffer demasiado pequeño. v2.0: 20 ruta de propiedad "
            "no encontrada; 21 fallo de inyección; 22 descompilación bloqueada. "
            "v2.1: 30 límite de firmas alcanzado (max_signatures). "
            "Diagnóstico: si verify falla con -8, el payload o un campo canónico "
            "cambió después de calcular el hash; recalcula el hash en draft o "
            "restaura el original. Si falla con -13, firma el bloque con "
            "'sign <archivo> <seed>'. Si cosign falla con 30, el bloque declara "
            "max_signatures: 1 o ya alcanzó su cuota; crea un draft nuevo con "
            "max_signatures: 2. Si inspect muestra 'unknown' en rol o "
            "modo, el valor del frontmatter no es válido. Si el CLI no abre, "
            "comprueba que exista bmd_engine/bin/bmd_engine.dll y que la ruta "
            "del .bmd no tenga caracteres no representables."
        ),
    },
    {
        "knowledge_id": "bmd.security",
        "title": "Seguridad operativa: seeds, inmutabilidad y respaldos",
        "tags": [
            "bmd",
            "seguridad",
            "seeds",
            "claves",
            "privacidad",
            "inmutabilidad",
            "respaldo",
            "produccion",
        ],
        "text": (
            "Reglas de seguridad: (1) las seeds 0x42... y 0x99... son de "
            "demostración y públicas; nunca usarlas para valor legal o "
            "producción. (2) La seed privada de 32 bytes solo debe vivir en "
            "memoria o en un almacén de secretos, nunca en el frontmatter, en "
            "logs, en capturas o en el chat. (3) sign y cosign aplican el "
            "atributo de solo lectura; para volver a firmar hay que limpiarlo "
            "de forma explícita. (4) Un bloque en transfer es "
            "inmutable: cualquier edición posterior lo invalida; conserva una "
            "copia del draft antes de congelarlo. (5) --inject-property mueve y "
            "elimina los archivos fuente; exige respaldo y confirmación "
            "explícita. (6) Verifica siempre con verify o audit antes de afirmar "
            "que un documento es auténtico; el estado 'verified' del JSON de "
            "--export-office es la única prueba. (7) No confundir el hash "
            "SHA-512 de 128 hex con SHA-256 de 64 hex. (8) El visor HTML es "
            "solo representación: no sustituye la verificación criptográfica."
        ),
    },
    {
        "knowledge_id": "bmd.integration.orunex",
        "title": "Integración BMD dentro de Orunex",
        "tags": [
            "bmd",
            "orunex",
            "integracion",
            "agente",
            "faiss",
            "bmd_expert",
            "tag",
            "artifacts",
        ],
        "text": (
            "Orunex integra BMD con src/_orunex_libs/bmd_expert.py (wrapper de "
            "CLI y FFI, creación de drafts, detección de intención y manejo de "
            "peticiones) y src/_orunex_libs/bmd_knowledge.py (pack verificado e "
            "inyección FAISS bajo kind='bmd'). El agente recibe el conocimiento "
            "en el prompt mediante bmd_context() y puede ejecutar la etiqueta "
            "[BMD: acción | archivo | argumentos] a través de os_executor. La "
            "ruta determinista de main.py reconoce órdenes como 'crea un .bmd', "
            "'verifica este bmd', 'renderiza el bmd' o 'audita la cadena' sin "
            "depender del modelo. Los artefactos .bmd se muestran con la "
            "etiqueta BMD en la tarjeta de chat y se abren con la aplicación "
            "asociada. El wrapper usa los comandos v2.1 sign/cosign, limpia el "
            "atributo de solo lectura antes de co-firmar y expone "
            "max_signatures en create_draft. La búsqueda FAISS filtrada por kind "
            "evita que el conocimiento BMD contamine las decisiones de trading o "
            "de código. Si el índice no existe, sync_bmd_knowledge lo crea; si "
            "está corrupto, se reconstruye solo el namespace BMD."
        ),
    },
    {
        "knowledge_id": "bmd.limits",
        "title": "Límites del motor y diferencias entre README, spec y binario",
        "tags": [
            "bmd",
            "limites",
            "buffer",
            "version",
            "readme",
            "spec",
            "sha256",
            "sha512",
            "v2",
        ],
        "text": (
            "Límites reales: block_id 127 caracteres; previous_hash, "
            "current_hash y property_bundle_hash 128 hex; public_key 128; "
            "signature_layer_2 y receiver_signature 256; document_type 63; "
            "jurisdiction 127; co_sign_label 127; inject_property_path 511. "
            "max_signatures es un entero: 0 ilimitado, 1 unilateral, 2 "
            "bilateral, N multipartita. El parser lee líneas de frontmatter de "
            "hasta 1023 caracteres y la cadena canónica se construye en un "
            "buffer de 8192 bytes. El README y la spec revisada ya declaran "
            "v2.1.0, SHA-512 de 128 hex y max_signatures; las copias antiguas "
            "que decían v1.0.0/SHA-256 de 64 hex están desactualizadas. La spec "
            "original describía un cursor azul que no forma parte del motor "
            "C11. El payload es Markdown libre, pero si se "
            "cifra con la FFI deja de ser legible y pasa a base64. El motor no "
            "valida semántica legal ni cifras: solo integridad, firma y cadena."
        ),
    },
    {
        "knowledge_id": "bmd.recipes",
        "title": "Recetas listas para usar con el CLI y la FFI",
        "tags": [
            "bmd",
            "recetas",
            "ejemplos",
            "comandos",
            "crear",
            "firmar",
            "auditar",
            "render",
        ],
        "text": (
            "Recetas: crear un draft válido -> usar BMDEngine.create_draft() de "
            "bmd_expert.py (escribe el archivo, calcula el hash con la DLL y "
            "verifica). Para un contrato bilateral, pasar require_cosigner=True "
            "y max_signatures=2. Verificar -> 'bmd_cli.exe verify contrato.bmd' "
            "o 'bmd_cli.exe verify --json contrato.bmd'. Inspeccionar -> "
            "'bmd_cli.exe inspect contrato.bmd'. Firmar y congelar -> "
            "'bmd_cli.exe sign contrato.bmd <seed64hex>'. Co-firmar -> "
            "'bmd_cli.exe cosign contrato.bmd <seed64hex>' (solo con "
            "max_signatures >= 2). Auditar -> 'bmd_cli.exe audit bloque1.bmd "
            "bloque2.bmd'. Renderizar -> 'bmd_cli.exe render contrato.bmd "
            "contrato.html'. Exportar metadatos -> 'bmd_cli.exe --export-office "
            "contrato.bmd'. Generar claves -> 'bmd_cli.exe genkey'. Aplicar "
            "solo lectura -> 'bmd_cli.exe lock contrato.bmd'. En Python: "
            "from bmd_ffi import BMDWrapper, generate_keypair; doc = "
            "BMDWrapper.load_file(path); ok, msg = doc.verify(). Para crear "
            "una cadena, el bloque N+1 usa previous_hash = current_hash del "
            "bloque N y un block_id nuevo."
        ),
    },
    {
        "knowledge_id": "bmd.glossary",
        "title": "Glosario BMD y comparación con Git/blockchain",
        "tags": [
            "bmd",
            "glosario",
            "blockchain",
            "git",
            "ledger",
            "ssot",
            "hash",
            "firma",
            "propiedad",
        ],
        "text": (
            "Glosario: bloque = archivo .bmd con frontmatter y payload; "
            "block_id = identificador lógico único; previous_hash = enlace al "
            "bloque padre; current_hash = SHA-512 canónico del bloque; payload = "
            "contenido Markdown o blob cifrado; draft = estado editable; "
            "transfer = estado inmutable y firmado; emisor = autor que transfiere; "
            "receptor = entidad que acepta y co-firma; max_signatures = cuota "
            "de firmas (0 ilimitado, 1 unilateral, 2 bilateral, N "
            "multipartita); ledger = secuencia auditable de bloques enlazados; "
            "property bundle = activo lógico cifrado e incrustado; SSOT = "
            "Single Source of Truth. Comparación: "
            "Git versiona cambios y permite reescribir historia; BMD congela un "
            "contenido con hash y firma, y cualquier cambio se detecta. Una "
            "blockchain tradicional replica bloques en una red; BMD es un ledger "
            "local de archivos verificables sin consenso distribuido. BMD no es "
            "una criptomoneda ni ejecuta contratos inteligentes: es un formato "
            "documental criptográficamente verificable."
        ),
    },
]


# ---------------------------------------------------------------------------
# FAISS synchronization
# ---------------------------------------------------------------------------
def knowledge_fingerprint() -> str:
    """Stable fingerprint of the pack content (detects silent edits)."""
    digest = hashlib.sha256()
    digest.update(BMD_KNOWLEDGE_VERSION.encode("utf-8"))
    for entry in sorted(BMD_KNOWLEDGE, key=lambda item: item["knowledge_id"]):
        digest.update(str(entry.get("knowledge_id", "")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry.get("text", "")).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _memory(memory: Optional[Any] = None) -> Any:
    if memory is not None:
        return memory
    from .faiss_memory import get_memory

    return get_memory()


def _entry_metadata(entry: Mapping[str, Any], fingerprint: str) -> Dict[str, Any]:
    return {
        "kind": BMD_KIND,
        "knowledge_id": str(entry["knowledge_id"]),
        "title": str(entry.get("title", "")),
        "tags": list(entry.get("tags", [])),
        "version": BMD_KNOWLEDGE_VERSION,
        "fingerprint": fingerprint,
        "source": "bmd_engine (verified against C11 sources + CLI)",
    }


def sync_bmd_knowledge(
    memory: Optional[Any] = None,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Insert/refresh the BMD namespace in Meta FAISS.

    Returns a summary with ``ok``, ``added``, ``removed``, ``total`` and
    ``skipped``.  It never raises into the agent: failures are reported in the
    summary so the caller can log them without breaking a task.
    """
    summary: Dict[str, Any] = {
        "ok": False,
        "added": 0,
        "removed": 0,
        "total": 0,
        "skipped": False,
        "error": "",
        "version": BMD_KNOWLEDGE_VERSION,
    }
    try:
        store = _memory(memory)
        fingerprint = knowledge_fingerprint()
        existing = store.entries(kind=BMD_KIND)
        expected_ids = {str(entry["knowledge_id"]) for entry in BMD_KNOWLEDGE}
        existing_ids = {
            str(item.get("knowledge_id", "")) for item in existing
        }
        unchanged = (
            len(existing) == len(BMD_KNOWLEDGE)
            and existing_ids == expected_ids
            and all(
                item.get("version") == BMD_KNOWLEDGE_VERSION
                and item.get("fingerprint") == fingerprint
                for item in existing
            )
        )
        if unchanged and not force:
            summary.update(
                ok=True, total=len(existing), skipped=True
            )
            return summary

        if existing:
            ids = [int(item["id"]) for item in existing if "id" in item]
            summary["removed"] = int(store.remove_ids(ids, persist=False))

        for entry in BMD_KNOWLEDGE:
            store.add_text(
                str(entry["text"]),
                _entry_metadata(entry, fingerprint),
                persist=False,
            )
            summary["added"] += 1

        saved = bool(store.save())
        summary["ok"] = saved
        summary["total"] = len(store.entries(kind=BMD_KIND))
        summary["index_total"] = int(store.count)
        if not saved:
            summary["error"] = str(store.last_error or "FAISS save failed")
        return summary
    except Exception as exc:  # pragma: no cover - defensive integration path
        summary["error"] = f"{type(exc).__name__}: {exc}"
        return summary


_STOPWORDS = {
    "the", "a", "an", "of", "for", "with", "without", "about", "how", "what",
    "is", "are", "and", "or", "to", "in", "on", "de", "del", "la", "el", "los",
    "las", "un", "una", "unos", "unas", "que", "qué", "como", "cómo", "para",
    "por", "con", "sin", "sobre", "es", "son", "y", "o", "en", "al", "se",
}


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{2,}", _normalise(value))
        if token not in _STOPWORDS
    }


def _token_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 4 and len(right) >= 4:
        # Light stemming: firma/firmar/firmo share the stem "firm";
        # crear/crea share "crea"; auditar/auditoría share "audi".
        if left[:4] == right[:4]:
            return True
        return left.startswith(right) or right.startswith(left)
    return False


def _lexical_score(query: str, entry: Mapping[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = _tokens(str(entry.get("title", "")))
    tag_tokens = _tokens(" ".join(str(tag) for tag in entry.get("tags", [])))
    text_tokens = _tokens(str(entry.get("text", "")))
    total = 0.0
    for token in query_tokens:
        if any(_token_match(token, candidate) for candidate in title_tokens):
            total += 3.0
        elif any(_token_match(token, candidate) for candidate in tag_tokens):
            total += 2.0
        elif any(_token_match(token, candidate) for candidate in text_tokens):
            total += 1.0
    score = total / (len(query_tokens) * 3.0)
    phrase = _normalise(query).strip()
    if len(phrase) >= 6 and phrase in _normalise(str(entry.get("text", ""))):
        score += 0.5
    return min(1.0, score)


def search_bmd_knowledge(
    query: str,
    top_k: int = 4,
    *,
    min_score: float = 0.0,
    memory: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Search only the BMD namespace and rerank lexical hits.

    The local FAISS embedder is a deterministic feature-hash vectorizer, so
    vector similarity alone is weak for short technical questions.  Fetching
    the whole BMD namespace (21 entries) and blending vector score with a
    title/tag/text lexical score gives reliable retrieval without adding a
    model dependency.
    """
    try:
        store = _memory(memory)
        # Self-healing: if the BMD namespace is missing (fresh machine,
        # rebuilt index or first run), inject it before searching.
        if not store.entries(kind=BMD_KIND):
            sync_bmd_knowledge(store)
        candidate_k = max(int(top_k) * 6, len(BMD_KNOWLEDGE))
        candidates = store.search_text(
            query,
            top_k=candidate_k,
            min_score=0.0,
            kind=BMD_KIND,
        )
        if not candidates:
            return []
        for hit in candidates:
            metadata = hit.get("metadata") or {}
            vector_score = float(hit.get("score") or 0.0)
            lexical = _lexical_score(query, metadata)
            hit["vector_score"] = vector_score
            hit["lexical_score"] = lexical
            hit["score"] = round(0.30 * vector_score + 0.70 * lexical, 6)
        candidates.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        return [
            hit
            for hit in candidates[: max(1, int(top_k))]
            if float(hit.get("score") or 0.0) >= float(min_score)
        ]
    except Exception:
        return []


def bmd_context(
    query: Optional[str] = None,
    top_k: int = 5,
    *,
    max_chars: int = 7000,
) -> str:
    """Build a bounded prompt block with the most relevant BMD knowledge.

    With no query, a compact overview (the first entries) is returned so the
    model knows the capability exists even before the user asks about BMD.
    """
    if query:
        hits = search_bmd_knowledge(query, top_k=top_k)
        texts = [str(hit.get("text") or "") for hit in hits if hit.get("text")]
        if not texts:
            texts = [str(entry["text"]) for entry in BMD_KNOWLEDGE[:3]]
    else:
        texts = [
            str(entry["text"])
            for entry in BMD_KNOWLEDGE
            if entry["knowledge_id"]
            in {
                "bmd.overview",
                "bmd.syntax.frontmatter",
                "bmd.cli.reference",
                "bmd.workflow.draft",
                "bmd.integration.orunex",
            }
        ]

    lines = [
        "[BMD ENGINE — VERIFIED KNOWLEDGE]",
        (
            "Local Blockchain Markdown engine v2.1.0 (C11 + FFI + CLI). "
            "Hash real: SHA-512 (128 hex). Use bmd_cli.exe for real operations."
        ),
    ]
    used = 0
    for text in texts:
        clean = " ".join(str(text).split())
        if not clean:
            continue
        if used + len(clean) > max_chars:
            break
        lines.append(f"- {clean}")
        used += len(clean)
    return "\n".join(lines)


__all__ = [
    "BMD_KIND",
    "BMD_KNOWLEDGE",
    "BMD_KNOWLEDGE_VERSION",
    "bmd_context",
    "knowledge_fingerprint",
    "search_bmd_knowledge",
    "sync_bmd_knowledge",
]
