@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual e instalando dependencias...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:error
echo.
echo No se pudo preparar el entorno. Verifica que Python 3.10+ este instalado
echo y que se haya marcado "Add Python to PATH" durante la instalacion.
pause
