@echo off
setlocal
cd /d "c:\Users\Hp\Downloads\Project_Orunex\bmd_engine"
set "PATH=%CD%\bin;%PATH%"
echo [*] Iniciando BMD Studio Mini-IDE (SHA-512 + Ed25519)...
python python\bmd_studio_app.py
endlocal
