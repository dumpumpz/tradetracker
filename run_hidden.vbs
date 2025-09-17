' Old line:
' WshShell.Run "cmd /c ""C:\Users\River\tradetracker\run-codes.bat""", 0, True

' New line (for debugging):
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""C:\Users\River\tradetracker\run-codes.bat > C:\Users\River\tradetracker\run_log.txt 2>&1""", 0, True