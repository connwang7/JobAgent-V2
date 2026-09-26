@echo off
REM JobAgent v2 local launcher (calls the PowerShell script)
REM Usage: scripts\start-local.bat           backend + frontend
REM        scripts\start-local.bat backend   backend only
REM        scripts\start-local.bat frontend  frontend only
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1" %1
