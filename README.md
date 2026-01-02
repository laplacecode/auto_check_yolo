# YOLOv5 实时屏幕检测系统

一个基于 YOLOv5 的实时屏幕区域检测系统,提供两种完整的实现方案。

## 项目简介

本项目提供两种独立的 YOLOv5 实时检测解决方案:

### 方案一: All-in-One 前端集成版 (推荐)
📂 [进入 all_in_one/ 目录查看详情](all_in_one/)

### 方案二: 前后端分离版
📂 [进入 src/ 目录查看详情](src/)

## 环境要求

### 基础依赖

```bash
Python 3.8+
```

### 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包:
- `PyQt5` - 图形界面
- `opencv-python` - 图像处理
- `ultralytics` - YOLOv5 模型
- `mss` - 屏幕捕获
- `numpy` - 数值计算
- `fastapi` - Web 框架(仅前后端分离版)
- `aiortc` - WebRTC 支持(仅前后端分离版)

## 模型文件

项目需要 YOLOv5 模型文件,已放置在 `models/` 目录:

```
models/
├── yolov5s.pt      # 标准小模型 (推荐)
└── yolov5su.pt     # 增强小模型
```

如果模型文件不存在,程序会自动使用 `torch.hub` 下载。