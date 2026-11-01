@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set CLI=bmd_engine\bin\bmd_cli.exe
set EXAMPLES=bmd_engine\examples
set PATH=bmd_engine\bin;%PATH%

echo.
echo ╔══════════════════════════════════════════════════════════════════╗
echo ║     BLOCKCHAIN MARKDOWN (.bmd) — DEMO INTERACTIVA COMPLETA     ║
echo ║              Motor Criptografico Ed25519 + SHA-256              ║
echo ╚══════════════════════════════════════════════════════════════════╝
echo.

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 1/6] Generando par de claves Ed25519 para el EMISOR...
echo ─────────────────────────────────────────────────────────────────────
%CLI% genkey > bmd_engine\demo_key.tmp 2>&1
type bmd_engine\demo_key.tmp
echo.

REM Extraer el SEED de la salida
for /f "tokens=4" %%A in ('findstr /C:"SEED PRIVADO" bmd_engine\demo_key.tmp') do set SEED=%%A
for /f "tokens=4" %%A in ('findstr /C:"CLAVE PUBLICA" bmd_engine\demo_key.tmp') do set PUBKEY=%%A
del bmd_engine\demo_key.tmp

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 2/6] Creando un documento .bmd en modo DRAFT...
echo ─────────────────────────────────────────────────────────────────────
(
echo ---
echo block_id: "0xDEMO_CORP_001"
echo previous_hash: "0x0000000000000000000000000000000000000000000000000000000000000000"
echo current_hash: "placeholder"
echo mode: "draft"
echo signer_role: "emisor"
echo timestamp: 1772210000
echo public_key: "PENDING"
echo signature_layer_2: ""
echo payload_encrypted: false
echo ---
echo.
echo # Contrato de Transferencia de Propiedad de Codigo
echo.
echo Este documento certifica la transferencia legal del modulo `bmd_engine`
echo del emisor al receptor, con validez criptografica e inmutabilidad matematica.
echo.
echo ## Terminos del Contrato
echo - Valor: $50,000 USD
echo - Activo: Motor criptografico BMD Engine v1.0 ^(C11, Ed25519^)
echo - Fecha: 2026-10-29
echo - Jurisdiccion: Estandar internacional RFC 8032 / NIST FIPS 180-4
echo.
echo ## Clausulas de Gobernanza del Agente
echo 1. El Agente Autonomo `muse-spark` valida la firma antes de ejecutar
echo 2. Una vez en modo TRANSFER: el documento es INMUTABLE
echo 3. Cualquier modificacion invalida la firma automaticamente
) > %EXAMPLES%\demo_contrato.bmd

echo    Documento creado: demo_contrato.bmd
echo    Modo: DRAFT ^(editable, sin firmar^)
echo.

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 3/6] Inspeccionando el documento DRAFT ^(antes de firmar^)...
echo ─────────────────────────────────────────────────────────────────────
%CLI% inspect %EXAMPLES%\demo_contrato.bmd
echo.

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 4/6] FIRMANDO y CONGELANDO: DRAFT → TRANSFER...
echo    Seed usado: !SEED!
echo ─────────────────────────────────────────────────────────────────────
%CLI% freeze %EXAMPLES%\demo_contrato.bmd !SEED!
echo.

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 5/6] Verificando integridad criptografica del bloque TRANSFER...
echo ─────────────────────────────────────────────────────────────────────
%CLI% verify %EXAMPLES%\demo_contrato.bmd
echo.
%CLI% inspect %EXAMPLES%\demo_contrato.bmd
echo.

REM ─────────────────────────────────────────────────────────────────────
echo [PASO 6/6] PRUEBA DE TAMPER: Modificando el archivo y verificando...
echo ─────────────────────────────────────────────────────────────────────
echo    Modificando el valor de $50,000 a $1 en el documento firmado...
powershell -Command "(Get-Content '%EXAMPLES%\demo_contrato.bmd') -replace '\$50,000', '\$1' | Set-Content '%EXAMPLES%\demo_contrato_tampered.bmd'"
echo    Verificando el archivo ADULTERADO...
%CLI% verify %EXAMPLES%\demo_contrato_tampered.bmd
echo.

echo ╔══════════════════════════════════════════════════════════════════╗
echo ║                    DEMO COMPLETADA                              ║
echo ╚══════════════════════════════════════════════════════════════════╝
del %EXAMPLES%\demo_contrato_tampered.bmd 2>nul
endlocal
