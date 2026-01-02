#!/bin/bash
echo "================================"
echo "YOLOv5 实时检测 - All-in-One 版本"
echo "================================"
echo ""
echo "正在启动检测程序..."
echo ""

cd "$(dirname "$0")"
python detector.py
