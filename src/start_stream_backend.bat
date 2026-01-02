@echo off
chcp 65001
echo ====================================
echo YOLOv5 视频流检测服务器
echo ====================================
echo.
cd /d "%~dp0"
python -m uvicorn backend.stream_server:app --host 0.0.0.0 --port 8004
pause
