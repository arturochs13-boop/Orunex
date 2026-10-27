Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = projectDir
WshShell.Run "pythonw.exe src\main.py", 1, False
