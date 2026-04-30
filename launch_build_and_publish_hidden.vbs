Set shell = CreateObject("WScript.Shell")
scriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\build_and_publish.bat"
shell.Run Chr(34) & scriptPath & Chr(34), 0, False