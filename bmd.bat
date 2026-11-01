@echo off
setlocal
cd /d "%~dp0"
bmd_engine\bin\bmd.exe %*
endlocal
