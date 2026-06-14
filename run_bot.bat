@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

title Nexus Vector Demo Runtime
echo ===================================================
echo [Nexus Vector] Starting local AI risk agent runtime...
echo ===================================================

python main.py

pause
