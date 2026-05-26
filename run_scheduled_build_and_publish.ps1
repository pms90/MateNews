$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir = Join-Path $rootDir '.state'
$runnerLogPath = Join-Path $stateDir 'scheduler_runner.log'
$lockPath = Join-Path $stateDir 'running.lock'
$runLogsDir = Join-Path $stateDir 'run_logs'
$batchPath = Join-Path $rootDir 'build_and_publish_now.bat'
$minRunInterval = [TimeSpan]::FromHours(6)

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
New-Item -ItemType Directory -Force -Path $runLogsDir | Out-Null

function Write-RunnerLog {
    param(
        [string]$Message
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $runnerLogPath -Value ("[{0}] {1}" -f $timestamp, $Message) -Encoding UTF8
}

function Get-ProcessSignature {
    param(
        [int]$ProcessId
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return $null
    }

    return [pscustomobject]@{
        Id = $process.Id
        StartedAt = $process.StartTime.ToString('o')
        Name = $process.ProcessName
    }
}

function Read-LockFile {
    if (-not (Test-Path -LiteralPath $lockPath)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-RunnerLog "No se pudo leer el lock existente; se tratara como stale. Error: $($_.Exception.Message)"
        return $null
    }
}

function Is-LockActive {
    param(
        [psobject]$LockInfo
    )

    if (-not $LockInfo) {
        return $false
    }

    if ($LockInfo.child_pid -and $LockInfo.child_started_at) {
        $child = Get-Process -Id ([int]$LockInfo.child_pid) -ErrorAction SilentlyContinue
        if ($child -and $child.StartTime.ToString('o') -eq $LockInfo.child_started_at) {
            return $true
        }
    }

    if ($LockInfo.runner_pid -and $LockInfo.runner_started_at) {
        $runner = Get-Process -Id ([int]$LockInfo.runner_pid) -ErrorAction SilentlyContinue
        if ($runner -and $runner.StartTime.ToString('o') -eq $LockInfo.runner_started_at) {
            return $true
        }
    }

    return $false
}

function Write-LockFile {
    param(
        [hashtable]$LockInfo
    )

    $LockInfo | ConvertTo-Json | Set-Content -LiteralPath $lockPath -Encoding UTF8
}

function Acquire-Lock {
    $runnerSignature = Get-ProcessSignature -ProcessId $PID
    if (-not $runnerSignature) {
        throw 'No se pudo obtener la firma del proceso runner actual.'
    }

    $initialLock = @{
        runner_pid = $runnerSignature.Id
        runner_started_at = $runnerSignature.StartedAt
        runner_name = $runnerSignature.Name
        acquired_at = (Get-Date).ToString('o')
        host = $env:COMPUTERNAME
        child_pid = $null
        child_started_at = $null
        child_name = $null
    }

    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        try {
            $lockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                $writer = New-Object System.IO.StreamWriter($lockStream, $utf8NoBom)
                $writer.Write(($initialLock | ConvertTo-Json))
                $writer.Flush()
            }
            finally {
                if ($writer) {
                    $writer.Dispose()
                }
                $lockStream.Dispose()
            }

            return $initialLock
        }
        catch [System.IO.IOException] {
            $existingLock = Read-LockFile
            if (Is-LockActive -LockInfo $existingLock) {
                Write-RunnerLog "Se omitio una ejecucion porque ya hay otra en curso. runner_pid=$($existingLock.runner_pid) child_pid=$($existingLock.child_pid)"
                return $null
            }

            Write-RunnerLog 'Se detecto un lock stale; se elimina para continuar.'
            Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
        }
    }

    throw 'No se pudo adquirir el lock de ejecucion.'
}

function Release-Lock {
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
}

function Read-ExecutionTimestamp {
    param(
        [string[]]$CandidatePaths
    )

    foreach ($candidatePath in $CandidatePaths) {
        if (-not (Test-Path -LiteralPath $candidatePath)) {
            continue
        }

        try {
            $rawValue = (Get-Content -LiteralPath $candidatePath -Raw -Encoding ASCII).Trim()
            if (-not [string]::IsNullOrWhiteSpace($rawValue)) {
                return [DateTimeOffset]::Parse($rawValue)
            }
        }
        catch {
            Write-RunnerLog "No se pudo interpretar la marca de tiempo en $candidatePath. Error: $($_.Exception.Message)"
        }
    }

    return $null
}

if (-not (Test-Path -LiteralPath $batchPath)) {
    Write-RunnerLog "No se encontro el batch esperado: $batchPath"
    throw "No se encontro el batch esperado: $batchPath"
}

$lockInfo = Acquire-Lock
if (-not $lockInfo) {
    exit 0
}

$runStamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$runLogPath = Join-Path $runLogsDir ("run_{0}.log" -f $runStamp)
$stdoutPath = Join-Path $runLogsDir ("run_{0}.stdout.log" -f $runStamp)
$stderrPath = Join-Path $runLogsDir ("run_{0}.stderr.log" -f $runStamp)
$lastAttemptPath = Join-Path $stateDir 'last_run_attempt.txt'
$lastSuccessPath = Join-Path $stateDir 'last_successful_run.txt'

$lastExecution = Read-ExecutionTimestamp -CandidatePaths @($lastAttemptPath, $lastSuccessPath)
if ($lastExecution) {
    $elapsed = [DateTimeOffset]::Now - $lastExecution
    if ($elapsed -lt $minRunInterval) {
        $remaining = $minRunInterval - $elapsed
        Write-RunnerLog "Se omitio la ejecucion porque la ultima corrida fue hace menos de 6 horas. Ultima=$($lastExecution.ToString('o')) Restante=$($remaining.ToString())"
        Release-Lock
        exit 0
    }
}

Write-RunnerLog "Inicio de ejecucion programada. Log: $runLogPath"
Set-Content -LiteralPath $lastAttemptPath -Value ([DateTimeOffset]::Now.ToString('o')) -Encoding ASCII

try {
    $env:MATENEWS_NO_PAUSE = '1'
    $process = Start-Process -FilePath $env:ComSpec `
        -ArgumentList '/d', '/c', ('"{0}"' -f $batchPath) `
        -WorkingDirectory $rootDir `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    if (-not $process.HasExited) {
        $lockInfo.child_pid = $process.Id
        $lockInfo.child_started_at = $process.StartTime.ToString('o')
        $lockInfo.child_name = $process.ProcessName
        Write-LockFile -LockInfo $lockInfo
    }

    $process.WaitForExit()
    $exitCode = $process.ExitCode

    $combinedLines = @(
        "Run started at: $($lockInfo.acquired_at)",
        "Run finished at: $((Get-Date).ToString('o'))",
        "Exit code: $exitCode",
        '',
        '=== STDOUT ==='
    )

    if (Test-Path -LiteralPath $stdoutPath) {
        $combinedLines += Get-Content -LiteralPath $stdoutPath
    }

    $combinedLines += @('', '=== STDERR ===')

    if (Test-Path -LiteralPath $stderrPath) {
        $combinedLines += Get-Content -LiteralPath $stderrPath
    }

    Set-Content -LiteralPath $runLogPath -Value $combinedLines -Encoding UTF8
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    if ($exitCode -eq 0) {
        Set-Content -LiteralPath $lastSuccessPath -Value ((Get-Date).ToString('o')) -Encoding ASCII
        Write-RunnerLog 'La ejecucion termino correctamente.'
        exit 0
    }

    Write-RunnerLog "La ejecucion termino con error. ExitCode=$exitCode. Ver $runLogPath"
    exit $exitCode
}
finally {
    Release-Lock
}