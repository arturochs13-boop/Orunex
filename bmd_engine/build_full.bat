@echo off
setlocal enabledelayedexpansion

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
set "LIB=C:\Program Files\Microsoft Visual Studio\2022\Community\SDK\ScopeCppSDK\vc15\SDK\lib;%LIB%"

cd /d "c:\Users\Hp\Downloads\Project_Orunex"

echo [1/4] Compilando DLL bmd_engine...
cl /nologo /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS /DBMD_BUILD_DLL ^
   /Ibmd_engine\include /Ibmd_engine\compat ^
   bmd_engine\src\bmd_crypto.c ^
   bmd_engine\src\bmd_parser.c ^
   bmd_engine\src\bmd_engine.c ^
   bmd_engine\src\bmd_ledger.c ^
   /LD /Febmd_engine\bin\bmd_engine.dll /Fobmd_engine\bin\ ^
   legacy_stdio_definitions.lib
if errorlevel 1 ( echo [FAIL] DLL compilation failed & exit /b 1 )
echo [OK] DLL compilada correctamente.

echo [2/4] Compilando test_engine.exe...
cl /nologo /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS ^
   /Ibmd_engine\include /Ibmd_engine\compat ^
   bmd_engine\tests\test_engine.c ^
   /Febmd_engine\bin\test_engine.exe /Fobmd_engine\bin\ ^
   /link bmd_engine\bin\bmd_engine.lib legacy_stdio_definitions.lib
if errorlevel 1 ( echo [FAIL] test_engine.exe compilation failed & exit /b 1 )
echo [OK] test_engine.exe compilado.

echo [3/4] Compilando bmd_cli.exe y bmd.exe...
cl /nologo /O2 /MD /W3 /utf-8 /D_CRT_SECURE_NO_WARNINGS ^
   /Ibmd_engine\include /Ibmd_engine\compat ^
   bmd_engine\src\bmd_main.c ^
   /Febmd_engine\bin\bmd_cli.exe /Fobmd_engine\bin\ ^
   /link bmd_engine\bin\bmd_engine.lib legacy_stdio_definitions.lib
if errorlevel 1 ( echo [FAIL] bmd_cli.exe compilation failed & exit /b 1 )
copy /Y bmd_engine\bin\bmd_cli.exe bmd_engine\bin\bmd.exe >nul
copy /Y bmd_engine\bin\bmd_cli.exe bmd.exe >nul
copy /Y bmd_engine\bin\bmd.exe "%LOCALAPPDATA%\Microsoft\WindowsApps\bmd.exe" >nul
copy /Y bmd_engine\bin\bmd_engine.dll "%LOCALAPPDATA%\Microsoft\WindowsApps\bmd_engine.dll" >nul
if not exist "%USERPROFILE%\.bmd\python" mkdir "%USERPROFILE%\.bmd\python"
copy /Y bmd_engine\python\*.py "%USERPROFILE%\.bmd\python\" >nul
echo [OK] bmd_cli.exe y bmd.exe compilados e instalados en PATH correctamente.

echo [4/4] Ejecutando tests nativos C11...
set "PATH=bmd_engine\bin;%PATH%"
bmd_engine\bin\test_engine.exe
if errorlevel 1 ( echo [FAIL] Native tests FAILED & exit /b 1 )

echo.
echo ==========================================
echo  BUILD Y TESTS COMPLETADOS EXITOSAMENTE
echo ==========================================
endlocal
