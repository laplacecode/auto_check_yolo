@echo off
chcp 65001 > nul
echo ================================
echo YOLOv5 实时检测 - All-in-One 版本
echo ================================
echo.
echo 正在启动检测程序...
echo.

cd /d "%~dp0"
python detector.py

pause
