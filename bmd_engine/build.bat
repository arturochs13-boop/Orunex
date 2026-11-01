@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo   COMPILANDO MOTOR CRIPTOGRAFICO C11 - BLOCKCHAIN MARKDOWN (.bmd)
echo ======================================================================

set VCVARS="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist %VCVARS% (
    echo [!] No se encontro vcvars64.bat en la ruta estandar de Visual Studio 2022.
    exit /b 1
)

call %VCVARS% > nul
if errorlevel 1 (
    echo [!] Fallo al inicializar el entorno de desarrollo MSVC x64.
    exit /b 1
)

set "LIB=C:\Program Files\Microsoft Visual Studio\2022\Community\SDK\ScopeCppSDK\vc15\SDK\lib;!LIB!"

cd /d "%~dp0"
if not exist "bin" mkdir "bin"

echo [*] Compilando bmd_engine.dll (C11 Core Library)...
cl /nologo /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS /DBMD_BUILD_DLL /Iinclude /Icompat ^
   src\bmd_crypto.c src\bmd_parser.c src\bmd_engine.c src\bmd_ledger.c ^
   /LD /Fe:bin\bmd_engine.dll /Fo:bin\ legacy_stdio_definitions.lib
if errorlevel 1 (
    echo [!] Error compilando bmd_engine.dll
    exit /b 1
)

echo [*] Compilando bmd_cli.exe (Herramienta de Linea de Comandos)...
cl /nologo /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS /Iinclude /Icompat ^
   src\bmd_main.c /Fe:bin\bmd_cli.exe /Fo:bin\ /link bin\bmd_engine.lib legacy_stdio_definitions.lib
if errorlevel 1 (
    echo [!] Error compilando bmd_cli.exe
    exit /b 1
)

echo [*] Compilando test_engine.exe (Suite de Pruebas Nativas C11)...
cl /nologo /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS /Iinclude /Icompat ^
   tests\test_engine.c /Fe:bin\test_engine.exe /Fo:bin\ /link bin\bmd_engine.lib legacy_stdio_definitions.lib
if errorlevel 1 (
    echo [!] Error compilando test_engine.exe
    exit /b 1
)

echo.
echo ======================================================================
echo [OK] COMPILACION NATIVA C11 COMPLETADA CON EXITO
echo      - DLL Nucleo : bin\bmd_engine.dll
echo      - CLI Engine : bin\bmd_cli.exe
echo      - Test Suite : bin\test_engine.exe
echo ======================================================================

echo [*] Ejecutando pruebas unitarias nativas...
set "PATH=bin;!PATH!"
bin\test_engine.exe
