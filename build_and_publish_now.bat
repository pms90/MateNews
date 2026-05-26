@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo Construyendo sitio...
call "%PYTHON_EXE%" -m matenews.cli build --output-dir site
if errorlevel 1 (
    echo.
    echo Fallo la construccion del sitio.
    exit /b 1
)

echo.
echo Publicando sitio...
call "%PYTHON_EXE%" -m matenews.cli publish --source-dir site --target-dir docs --remote origin --branch main
if errorlevel 1 (
    echo.
    echo Fallo la publicacion del sitio.
    exit /b 1
)

echo.
echo Sitio construido y publicado correctamente.
@REM Si se quiere actualizar el archivo de última ejecución exitosa:
@REM powershell -NoProfile -ExecutionPolicy Bypass -Command "[datetime]::Now.ToString('o') | Set-Content -Path '%ROOT_DIR%.state\last_successful_run.txt' -Encoding ascii"
if defined MATENEWS_NO_PAUSE (
    exit /b 0
)
exit /b 0