#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统配置文件

包含所有可配置的参数
"""
import os

# ==================== 后端配置 ====================

# 服务器配置
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8002"))

# 模型配置
MODEL_PATH = os.environ.get("MODEL_PATH", "yolov5s.pt")

# 检测配置
DETECTION_INTERVAL = 5  # 每 N 帧检测一次
CONFIDENCE_THRESHOLD = 0.25  # 置信度阈值

# ==================== 前端配置 ====================

# WebRTC 信令服务器地址
SIGNALING_URL = f"http://127.0.0.1:{SERVER_PORT}/offer"

# UI 配置
DEFAULT_REGION = {
    "left": 0,
    "top": 0,
    "width": 800,
    "height": 1000
}

# 显示配置
VIDEO_FPS = 25  # 视频帧率
DISPLAY_WIDTH = 800  # 显示宽度
DISPLAY_HEIGHT = 1000  # 显示高度

# 检测框过期时间（秒）
DETECTION_EXPIRE_TIME = 2.0

# 红框配置
BORDER_COLOR = (255, 0, 0)  # RGB 红色
BORDER_WIDTH = 4  # 边框宽度（像素）
OVERLAY_REFRESH_MS = 100  # 叠加层刷新间隔（毫秒）

# ==================== 预设区域 ====================

PRESETS = {
    "左上角 800x1000": {"left": 0, "top": 0, "width": 800, "height": 1000},
    "居中 1024x768": "auto",  # 自动计算
    "右半屏": "auto"  # 自动计算
}
