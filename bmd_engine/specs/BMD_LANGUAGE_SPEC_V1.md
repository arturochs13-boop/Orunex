# ESPECIFICACIÓN FORMAL DEL LENGUAJE BLOCKCHAIN MARKDOWN (.bmd)
**Versión de la Especificación:** 2.1.0-PROPRIETARY (BMD Language V1, revisada para el motor 2.1.0)  
**Estado:** Formal / Normativo  
**Autores:** Arquitectura de Sistemas Embebidos, Criptografía y Compiladores  
**Entorno de Ejecución:** C11 / FFI / Windows Autonomous Agent Runtime (`muse-spark`)

---

## 1. VISIÓN ESTRATÉGICA Y OBJETIVO DE GOBERNANZA

### 1.1 El Problema Fundamental
Los flujos corporativos modernos sufren una desconexión crítica entre:
1. **El repositorio de código / activos lógicos** (Git, scripts, modelos, configuraciones).
2. **La ejecución empresarial y financiera** (auditorías, actas de entrega, facturación, matrices contables de Excel, reportes ejecutivos de Word).

Tradicionalmente, esta sincronización requiere:
- Intervenciones manuales lentas, propensas a errores de transcripción o fraude.
- Emuladores pesados y entornos virtualizados que ralentizan la gobernanza y no garantizan determinismo legal ni firma electrónica verificable en el metal.

### 1.2 La Solución Blockchain Markdown (.bmd)
El lenguaje **Blockchain Markdown (.bmd)** unifica en un solo artefacto liviano:
- La legibilidad humana e interoperabilidad documental de **Markdown**.
- La inmutabilidad matemática, trazabilidad y no-repudio de un **Ledger Criptográfico**.
- La gobernanza de agentes de IA autónomos (`muse-spark`), actuando como el **Single Source of Truth (SSOT)**.

El motor C11 compila y valida la sintaxis, garantiza la consistencia criptográfica en nanosegundos y expone una FFI de alto rendimiento para que `muse-spark` proyecte directamente las decisiones empresariales en documentos corporativos de Microsoft Office (Excel y Word) guiado por un cursor azul autónomo determinista.

---

## 2. ESPECIFICACIÓN SINTÁCTICA FORMAL (EBNF)

Un archivo `.bmd` se compone de dos secciones disjuntas:
1. **Frontmatter Criptográfico**: delimitado por triples guiones (`---`), con pares clave-valor estrictamente tipados.
2. **Payload / Cuerpo Markdown**: texto enriquecido, tablas, especificaciones o ciphertext.

```ebnf
BmdDocument     ::= Frontmatter "\n" Payload
Frontmatter     ::= "---" "\n" HeaderFields "---"
HeaderFields    ::= Field+
Field           ::= BlockIdField
                  | PrevHashField
                  | CurrHashField
                  | ModeField
                  | SignerRoleField
                  | TimestampField
                  | PubKeyField
                  | SigLayer2Field
                  | EncryptedField
                  | DocumentTypeField
                  | JurisdictionField
                  | MaxSignaturesField

BlockIdField    ::= "block_id:" SP '"' [0-9a-zA-Z_\-]+ '"' "\n"
PrevHashField   ::= "previous_hash:" SP '"' [0-9a-fA-F]{128} '"' "\n"
CurrHashField   ::= "current_hash:" SP '"' [0-9a-fA-F]{128} '"' "\n"
ModeField       ::= "mode:" SP '"' ("draft" | "transfer") '"' [SP "#" AnyText] "\n"
SignerRoleField ::= "signer_role:" SP '"' ("emisor" | "receptor") '"' [SP "#" AnyText] "\n"
TimestampField  ::= "timestamp:" SP [0-9]{10,13} "\n"
PubKeyField     ::= "public_key:" SP '"' [0-9a-zA-Z_\+\/\=]{44,128} '"' "\n"
SigLayer2Field  ::= "signature_layer_2:" SP '"' [0-9a-zA-Z_\+\/\=]{64,256} '"' "\n"
EncryptedField  ::= "payload_encrypted:" SP ("true" | "false") "\n"
DocumentTypeField ::= "document_type:" SP '"' AnyText '"' "\n"
JurisdictionField ::= "jurisdiction:" SP '"' AnyText '"' "\n"
MaxSignaturesField ::= "max_signatures:" SP '"' [0-9]+ '"' "\n"

Payload         ::= MarkdownContent | EncryptedBlob
MarkdownContent ::= AnyUTF8String
EncryptedBlob   ::= Base64OrHexArmor
```

---

## 3. SEMÁNTICA DE ESTADOS Y REGLAS DE TRANSICIÓN

### 3.1 Modos Operativos (`mode`)
| Modo | Semántica | Mutabilidad | Validación de Firma |
| :--- | :--- | :--- | :--- |
| `draft` | Fase de redacción, diseño y calibración por el agente o usuario. | **Permitida**. Se permite recalcular hashes locales. | Opcional o firma preliminar. |
| `transfer` | **Congelamiento total de propiedad (IP/Activo/Contrato)**. Transición irreversible. | **Prohibida**. Cualquier mutación corrompe el hash. | **Mandatoria y Estricta**. Verificación de Ed25519 con clave pública del emisor. |

### 3.2 Roles de Firma (`signer_role`)
- **`emisor`**: Dueño original o autor del código/activo. Genera la firma digital (`signature_layer_2`) usando su clave privada Ed25519 sobre el `current_hash`.
- **`receptor`**: Entidad auditora, compradora o corporativa que valida la cadena y estampa su aceptación de posesión.

### 3.3 Gobernanza de Firmas (`max_signatures`)
`max_signatures` limita cuántas firmas admite el bloque: `0` = sin límite,
`1` = unilateral (solo emisor), `2` = bilateral (emisor + receptor),
`N` = multipartita. El motor cuenta la firma del emisor y la del receptor; si
el conteo actual ya alcanzó la cuota, `cosign` devuelve
`BMD_ERR_SIGNATURE_LIMIT_EXCEEDED (30)`. Cuando `max_signatures` es distinto de
cero se incluye en la cadena canónica del hash, por lo que modificarlo invalida
la verificación. `require_cosigner` y `co_sign_label` son metadatos de interfaz;
la regla efectiva es `max_signatures`.

---

## 4. CANONICALIZACIÓN Y CÁLCULO CRIPTOGRÁFICO

Para evitar discrepancias en saltos de línea (CRLF vs LF) y espacios en blanco, el cálculo del hash del bloque se define formalmente como:

$$\text{PayloadDigest} = \text{SHA-512}(\text{trim}(\text{Payload}))$$

$$\text{CanonicalBlock} = \text{block\_id} \parallel "|" \parallel \text{previous\_hash} \parallel "|" \parallel \text{mode} \parallel "|" \parallel \text{signer\_role} \parallel "|" \parallel \text{timestamp} \parallel "|" \parallel \text{public\_key} \parallel "|" \parallel \text{payload\_encrypted} \parallel "|" \parallel \text{PayloadDigest}$$

Si el bloque declara al menos un campo extendido (`document_type`, `jurisdiction`, `expiry_timestamp`, `witnesses_required`, `require_cosigner`, `property_bundle_hash` o `max_signatures` distinto de cero), se calcula:

$$\text{CanonicalBlockExtendido} = \text{CanonicalBlock} \parallel "|" \parallel \text{document\_type} \parallel "|" \parallel \text{jurisdiction} \parallel "|" \parallel \text{expiry\_timestamp} \parallel "|" \parallel \text{witnesses\_required} \parallel "|" \parallel \text{require\_cosigner} \parallel "|" \parallel \text{property\_bundle\_hash} \parallel "|" \parallel \text{max\_signatures}$$

$$\text{current\_hash} = \text{SHA-512}(\text{CanonicalBlockExtendido})$$

Si no hay ningún campo extendido, se usa directamente:

$$\text{current\_hash} = \text{SHA-512}(\text{CanonicalBlock})$$

$$\text{signature\_layer\_2} = \text{Ed25519\_Sign}(\text{PrivateKey}_{\text{signer}}, \text{current\_hash})$$

El digest resultante tiene **128 caracteres hexadecimales** (64 bytes). Si `payload_encrypted == true`, el cuerpo del documento está cifrado mediante **ChaCha20 (RFC 8439)** con una clave de 32 bytes y un nonce de 12 bytes; el motor no añade una etiqueta de autenticación Poly1305, por lo que la integridad del bloque depende del hash y de la firma Ed25519.

---

## 5. GOBERNANZA DE AGENTES (`muse-spark`) Y PROYECCIÓN OFFICE

El Agente Autónomo `muse-spark` opera bajo la siguiente máquina de estados:
1. **Ingestión**: Carga del `.bmd` a través del motor C11 FFI (`bmd_engine.dll`).
2. **Verificación de Inmutabilidad**: Comprobación matemática del bloque y su árbol de ancestros.
3. **Despacho Determinista a Office**:
   - **Excel**: Inyección en libro de trabajo contable con fórmulas, tablas dinámicas y bloqueo de celdas con hash de verificación.
   - **Word**: Generación de acta de transferencia notarial/tecnológica con código de barras / sello de autenticidad y anexos de código.
4. **Ejecución Visual (Cursor Azul)**: El agente proyecta su actividad motriz en la interfaz con cursor azul sin interrumpir al usuario.
