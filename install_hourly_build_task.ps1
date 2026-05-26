[CmdletBinding()]
param(
    [string]$TaskName = 'MateNews Hourly Build and Publish',
    [string]$UserId,
    [switch]$InteractiveOnly,
    [switch]$RunNow
)

$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stateDir = Join-Path $rootDir '.state'
$installLogPath = Join-Path $stateDir 'scheduler_install.log'
$vbsPath = Join-Path $rootDir 'launch_build_and_publish_hidden.vbs'
$currentUser = '{0}\{1}' -f $env:USERDOMAIN, $env:USERNAME
$computerUser = '{0}\{1}' -f $env:COMPUTERNAME, $env:USERNAME
$dotUser = '.\{0}' -f $env:USERNAME

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Write-InstallLog {
    param(
        [string]$Message
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $installLogPath -Value ("[{0}] {1}" -f $timestamp, $Message) -Encoding UTF8
}

function Get-PlainTextPassword {
    param(
        [Security.SecureString]$SecurePassword
    )

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Get-UserCandidates {
    param(
        [string]$PreferredUserId
    )

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @($PreferredUserId, $currentUser, $computerUser, $dotUser, $env:USERNAME)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $alreadyAdded = $false
        foreach ($existing in $candidates) {
            if ($existing.Equals($candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
                $alreadyAdded = $true
                break
            }
        }

        if (-not $alreadyAdded) {
            $candidates.Add($candidate)
        }
    }

    return $candidates
}

function Convert-ToTaskXmlSafeText {
    param(
        [string]$Value
    )

    return [System.Security.SecurityElement]::Escape($Value)
}

function New-TaskTriggers {
    param(
        [string]$LogonUser
    )

    return @(
        (New-ScheduledTaskTrigger -Once -At $hourlyStart -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)),
        (New-ScheduledTaskTrigger -AtStartup -RandomDelay (New-TimeSpan -Minutes 2)),
        (New-ScheduledTaskTrigger -AtLogOn -User $LogonUser -RandomDelay (New-TimeSpan -Minutes 2))
    )
}

function Register-InteractiveTaskWithSchtasks {
        param(
                [string]$TaskNameToRegister,
                [string]$LogonUser
        )

        $safeFileName = ($TaskNameToRegister -replace '[^A-Za-z0-9_.-]', '_') + '.xml'
        $xmlPath = Join-Path $stateDir $safeFileName
        $escapedUser = Convert-ToTaskXmlSafeText -Value $LogonUser
        $escapedTaskName = Convert-ToTaskXmlSafeText -Value $TaskNameToRegister
        $escapedCommand = Convert-ToTaskXmlSafeText -Value (Join-Path $env:SystemRoot 'System32\wscript.exe')
        $escapedArguments = Convert-ToTaskXmlSafeText -Value ('"{0}"' -f $vbsPath)
        $escapedWorkingDirectory = Convert-ToTaskXmlSafeText -Value $rootDir
        $startBoundary = $hourlyStart.ToString('s')

        $taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
    <RegistrationInfo>
        <Author>$escapedUser</Author>
        <Description>MateNews build and publish hourly task.</Description>
        <URI>\$escapedTaskName</URI>
    </RegistrationInfo>
    <Triggers>
        <CalendarTrigger>
            <StartBoundary>$startBoundary</StartBoundary>
            <Enabled>true</Enabled>
            <ScheduleByDay>
                <DaysInterval>1</DaysInterval>
            </ScheduleByDay>
            <Repetition>
                <Interval>PT1H</Interval>
                <Duration>P3650D</Duration>
                <StopAtDurationEnd>false</StopAtDurationEnd>
            </Repetition>
        </CalendarTrigger>
        <LogonTrigger>
            <Enabled>true</Enabled>
            <UserId>$escapedUser</UserId>
            <Delay>PT2M</Delay>
        </LogonTrigger>
    </Triggers>
    <Principals>
        <Principal id="Author">
            <UserId>$escapedUser</UserId>
            <LogonType>InteractiveToken</LogonType>
            <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
    </Principals>
    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <IdleSettings>
            <StopOnIdleEnd>false</StopOnIdleEnd>
            <RestartOnIdle>false</RestartOnIdle>
        </IdleSettings>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <RunOnlyIfIdle>false</RunOnlyIfIdle>
        <WakeToRun>true</WakeToRun>
        <ExecutionTimeLimit>PT3H</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>
    <Actions Context="Author">
        <Exec>
            <Command>$escapedCommand</Command>
            <Arguments>$escapedArguments</Arguments>
            <WorkingDirectory>$escapedWorkingDirectory</WorkingDirectory>
        </Exec>
    </Actions>
</Task>
"@

        Set-Content -LiteralPath $xmlPath -Value $taskXml -Encoding Unicode
        try {
                $output = & schtasks.exe /create /tn $TaskNameToRegister /xml $xmlPath /f 2>&1
                if ($LASTEXITCODE -ne 0) {
                        throw "schtasks /create fallo: $($output -join ' ')"
                }

                Write-InstallLog "schtasks creo la tarea interactiva para $LogonUser"
        }
        finally {
                Remove-Item -LiteralPath $xmlPath -Force -ErrorAction SilentlyContinue
        }
}

if (-not (Test-Path -LiteralPath $vbsPath)) {
    throw "No se encontro el launcher VBS: $vbsPath"
}

$hourlyStart = Get-Date
$hourlyStart = Get-Date -Date $hourlyStart.Date.AddHours($hourlyStart.Hour)
if ($hourlyStart -le (Get-Date)) {
    $hourlyStart = $hourlyStart.AddHours(1)
}

$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wscript.exe" -Argument ('"{0}"' -f $vbsPath)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$registeredUserId = $null
$taskSummary = $null

try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        if ($InteractiveOnly) {
            $deleteOutput = & schtasks.exe /delete /tn $TaskName /f 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "schtasks /delete fallo: $($deleteOutput -join ' ')"
            }
        }
        else {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        }

        Write-InstallLog "Se elimino la tarea anterior: $TaskName"
    }

    if ($InteractiveOnly) {
        $registeredUserId = if ([string]::IsNullOrWhiteSpace($UserId)) { $currentUser } else { $UserId }
        Register-InteractiveTaskWithSchtasks -TaskNameToRegister $TaskName -LogonUser $registeredUserId
        $taskSummary = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-InstallLog "Se instalo la tarea en modo interactivo para $registeredUserId"
        Write-Host 'La tarea se instalo en modo interactivo.'
        Write-Host 'Si cerras sesion de Windows, no correra hasta el proximo logon.'
    }
    else {
        $userCandidates = Get-UserCandidates -PreferredUserId $UserId
        Write-Host "Se intentara registrar la tarea para las variantes del usuario local: $($userCandidates -join ', ')"
        Write-Host 'Se pedira la contrasena real de Windows una sola vez. No uses el PIN.'
        $securePassword = Read-Host 'Contrasena de Windows' -AsSecureString
        if (-not $securePassword -or $securePassword.Length -eq 0) {
            throw 'No se ingreso una contrasena. Para evitar el prompt, usa -InteractiveOnly.'
        }

        $plainPassword = Get-PlainTextPassword -SecurePassword $securePassword
        try {
            $attemptErrors = New-Object System.Collections.Generic.List[string]
            foreach ($candidateUser in $userCandidates) {
                try {
                    $triggers = New-TaskTriggers -LogonUser $candidateUser
                    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -User $candidateUser -Password $plainPassword -ErrorAction Stop | Out-Null
                    $taskSummary = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
                    $registeredUserId = $candidateUser
                    break
                }
                catch {
                    $attemptErrors.Add("{0}: {1}" -f $candidateUser, $_.Exception.Message)
                    Write-InstallLog "Fallo el intento de registro para $candidateUser. Error: $($_.Exception.Message)"
                    $partialTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
                    if ($partialTask) {
                        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
                    }
                }
            }

            if (-not $taskSummary) {
                $details = $attemptErrors -join ' | '
                throw "No se pudo registrar la tarea con ninguna variante del usuario. $details"
            }
        }
        finally {
            $plainPassword = $null
        }

        Write-InstallLog "Se instalo la tarea con credenciales guardadas para $registeredUserId"
        Write-Host 'La tarea se instalo para ejecutarse aunque cierres sesion.'
    }

    if ($RunNow) {
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-InstallLog 'Se lanzo la tarea inmediatamente despues de instalarla.'
        Write-Host 'Se lanzo una ejecucion inmediata de la tarea.'
    }

    Write-InstallLog "Instalacion finalizada. Estado actual: $($taskSummary.State)"
    Write-Host "Tarea instalada: $TaskName"
    Write-Host "Usuario: $registeredUserId"
    Write-Host "Launcher: $vbsPath"
    Write-Host "Logs: $stateDir"
}
catch {
    Write-InstallLog "Fallo la instalacion de la tarea. Error: $($_.Exception.Message)"
    throw
}