@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0etch.ps1" %*
exit /b %errorlevel%
