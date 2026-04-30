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
echo Precione una tecla para continuar
pause >nul
exit /b 0