#!/bin/bash

echo "================================"
echo "YOLOv5 WebRTC 后端服务器"
echo "================================"
echo ""
echo "正在启动后端服务器..."
echo "端口: 8002"
echo ""

cd "$(dirname "$0")"
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8002
