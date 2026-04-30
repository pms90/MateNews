@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

set "STATE_DIR=%ROOT_DIR%.state"
set "LAST_RUN_FILE=%STATE_DIR%\last_successful_run.txt"
set "LOG_FILE=%STATE_DIR%\runner.log"
set "CHECK_INTERVAL_SECONDS=600"
set "MAX_AGE_HOURS=12"

if not exist "%STATE_DIR%" (
    mkdir "%STATE_DIR%"
)

call :log "MateNews iniciado. Se verificara cada 10 minutos si corresponde ejecutar una publicacion."

:main_loop
call :should_run
if errorlevel 2 (
    call :log "No hay ejecucion reciente. Se inicia build y publish."
    call :run_job
) else (
    call :log "Ya hubo una ejecucion exitosa dentro de las ultimas %MAX_AGE_HOURS% horas."
)

call :log "Esperando 10 minutos para volver a chequear."
timeout /t %CHECK_INTERVAL_SECONDS% /nobreak >nul
goto :main_loop

:should_run
if not exist "%LAST_RUN_FILE%" (
    exit /b 2
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$path = '%LAST_RUN_FILE%';" ^
    "$raw = Get-Content -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1;" ^
    "if ([string]::IsNullOrWhiteSpace($raw)) { exit 2 }" ^
    "try { $lastRun = [datetime]::Parse($raw, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind) } catch { exit 2 }" ^
    "$ageHours = ((Get-Date) - $lastRun).TotalHours;" ^
    "if ($ageHours -ge %MAX_AGE_HOURS%) { exit 2 } else { exit 0 }"
exit /b %errorlevel%

:run_job
call :log "Construyendo sitio..."
call "%PYTHON_EXE%" -m matenews.cli build --output-dir site >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "Fallo la construccion del sitio. Se reintentara en el proximo chequeo."
    exit /b 0
)

call :log "Publicando sitio..."
call "%PYTHON_EXE%" -m matenews.cli publish --source-dir site --target-dir docs --remote origin --branch main >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :log "Fallo la publicacion del sitio. Se reintentara en el proximo chequeo."
    exit /b 0
)

call :log "Sitio construido y publicado correctamente."
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[datetime]::Now.ToString('o') | Set-Content -Path '%LAST_RUN_FILE%' -Encoding ascii"
exit /b 0

:log
echo [%date% %time%] %~1
>> "%LOG_FILE%" echo [%date% %time%] %~1
exit /b 0