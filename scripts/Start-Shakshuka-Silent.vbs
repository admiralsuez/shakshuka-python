Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)

REM Try to find Shakshuka.exe in different locations
Dim shakshukaPath
shakshukaPath = ""

REM Check if Shakshuka.exe is in the same directory as this script
If fso.FileExists(scriptPath & "\Shakshuka.exe") Then
    shakshukaPath = scriptPath & "\Shakshuka.exe"
REM Check if Shakshuka.exe is in the parent directory
ElseIf fso.FileExists(fso.GetParentFolderName(scriptPath) & "\Shakshuka.exe") Then
    shakshukaPath = fso.GetParentFolderName(scriptPath) & "\Shakshuka.exe"
REM Check Program Files
ElseIf fso.FileExists("C:\Program Files\Shakshuka\Shakshuka.exe") Then
    shakshukaPath = "C:\Program Files\Shakshuka\Shakshuka.exe"
REM Check Desktop
ElseIf fso.FileExists(fso.GetSpecialFolder(0) & "\Desktop\Shakshuka.exe") Then
    shakshukaPath = fso.GetSpecialFolder(0) & "\Desktop\Shakshuka.exe"
End If

If shakshukaPath <> "" Then
    Set WshShell = CreateObject("WScript.Shell")
    WshShell.Run """" & shakshukaPath & """", 0, False
Else
    REM If not found, exit silently
    WScript.Quit 1
End If
