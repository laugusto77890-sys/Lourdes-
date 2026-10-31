@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (py outils\tv_allegement.py tout) || (python outils\tv_allegement.py tout)
pause
