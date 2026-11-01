@echo off
setlocal
cd /d "%~dp0"
echo ====================================================================
echo   BLOCKCHAIN MARKDOWN (.bmd) NATIVE STANDALONE VIEWER
echo   Zero HTML, Zero Browser, 100%% Independent Executable Document
echo ====================================================================
echo.
echo Launching standalone native executive desktop window...
echo Document: examples\proof_of_concept_FINAL.bmd
echo.
python python\bmd_native_viewer.py examples\proof_of_concept_FINAL.bmd
endlocal
