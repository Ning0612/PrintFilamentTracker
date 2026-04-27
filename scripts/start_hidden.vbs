Dim shell, batPath
Set shell = CreateObject("WScript.Shell")
batPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\start_server.bat"
shell.Run """" & batPath & """", 0, True
Set shell = Nothing