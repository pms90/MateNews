Option Explicit

Dim shell
Dim fso
Dim rootDir
Dim systemRoot
Dim powershellExe
Dim psScript
Dim command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
systemRoot = shell.ExpandEnvironmentStrings("%SystemRoot%")
powershellExe = fso.BuildPath(systemRoot, "System32\WindowsPowerShell\v1.0\powershell.exe")
psScript = fso.BuildPath(rootDir, "run_scheduled_build_and_publish.ps1")
command = Chr(34) & powershellExe & Chr(34) & " -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & psScript & Chr(34)

shell.Run command, 0, False