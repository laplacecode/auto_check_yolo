#!/bin/bash

echo "================================"
echo "YOLOv5 WebRTC 前端客户端"
echo "================================"
echo ""
echo "正在启动前端应用..."
echo ""

cd "$(dirname "$0")"
python frontend/client.py
