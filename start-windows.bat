@echo off
cd /d "%~dp0"
if exist "StochasticResonance.exe" (
    start "" "%~dp0StochasticResonance.exe"
    exit /b
)
if exist "dist\StochasticResonance\StochasticResonance.exe" (
    start "" "%~dp0dist\StochasticResonance\StochasticResonance.exe"
    exit /b
)
py -3 main.py
if errorlevel 1 pause
