@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta iniciar.bat una vez para crear el entorno.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --quiet pyinstaller || goto :error

set "ASSETS="
if exist "voicechanger\assets\fonts\ZTNature-Regular.otf" set "ASSETS=--add-data voicechanger\assets;voicechanger\assets"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
    --onefile --windowed ^
    --name VoiceChangerRT ^
    %ASSETS% ^
    --collect-data customtkinter ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    main.py || goto :error

echo.
echo Listo: dist\VoiceChangerRT.exe
exit /b 0

:error
echo.
echo No se pudo generar el .exe. Revisa los mensajes de arriba.
pause
exit /b 1
