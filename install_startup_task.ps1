$ErrorActionPreference = "Stop"

$taskName = "MateNews Auto Publish"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherPath = Join-Path $rootDir "launch_build_and_publish_hidden.vbs"

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "No se encontro el lanzador oculto en: $launcherPath"
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"{0}"' -f $launcherPath) -WorkingDirectory $rootDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Tarea programada creada o actualizada: $taskName"
Write-Host "Se ejecutara al iniciar sesion del usuario actual en modo oculto."
Write-Host "Lanzador: $launcherPath"