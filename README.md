# YOLOv5 实时屏幕检测系统

一个基于 YOLOv5 的实时屏幕区域检测系统,提供两种完整的实现方案。

## 📋 项目简介

本项目提供两种独立的 YOLOv5 实时检测解决方案:

### 🚀 方案一: All-in-One 前端集成版 (推荐)

**特点:**
- ✅ 单文件应用,开箱即用
- ✅ 前端本地运行 YOLO,零网络延迟
- ✅ 高性能,30 FPS 流畅显示
- ✅ 一键启动,无需配置

**适用场景:** 快速原型开发、单机检测、性能要求高的场景

📂 [进入 all_in_one/ 目录查看详情](all_in_one/)

### 🏗️ 方案二: 前后端分离版

**特点:**
- ✅ 前后端独立部署
- ✅ WebRTC 视频流传输
- ✅ WebSocket 实时通信
- ✅ 支持分布式架构
- ✅ 易于扩展和维护

**适用场景:** 生产环境、分布式部署、多客户端场景

📂 [进入 src/ 目录查看详情](src/)

## 🎯 快速选择

| 需求 | 推荐方案 | 目录 |
|------|---------|------|
| 快速体验、单机使用 | All-in-One | [all_in_one/](all_in_one/) |
| 生产部署、远程检测 | 前后端分离 | [src/](src/) |
| 学习 YOLO 应用 | All-in-One | [all_in_one/](all_in_one/) |
| 架构研究、二次开发 | 前后端分离 | [src/](src/) |

## 🔧 环境要求

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

## 📦 模型文件

项目需要 YOLOv5 模型文件,已放置在 `models/` 目录:

```
models/
├── yolov5s.pt      # 标准小模型 (推荐)
└── yolov5su.pt     # 增强小模型
```

如果模型文件不存在,程序会自动使用 `torch.hub` 下载。

## 🚀 快速开始

### 方案一: All-in-One (推荐新手)

```bash
# Windows
cd all_in_one
start.bat

# Linux/Mac
cd all_in_one
chmod +x start.sh
./start.sh
```

### 方案二: 前后端分离

#### 1. 启动后端服务器

```bash
# Windows
cd src
start_backend.bat

# Linux/Mac
cd src
chmod +x start_backend.sh
./start_backend.sh
```

#### 2. 启动前端客户端

```bash
# Windows
cd src
start_frontend.bat

# Linux/Mac
cd src
chmod +x start_frontend.sh
./start_frontend.sh
```

## 📊 性能对比

| 指标 | All-in-One | 前后端分离 |
|------|-----------|----------|
| **延迟** | ~7ms | ~50-200ms |
| **帧率** | 30 FPS | 15 FPS |
| **启动复杂度** | ⭐ | ⭐⭐⭐ |
| **部署灵活性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **资源占用** | 低 | 中等 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 📁 项目结构

```
auto_check/
├── README.md                   # 项目总体说明(本文件)
├── requirements.txt            # 依赖列表
├── REFACTOR_PLAN.md           # 重构优化方案
│
├── all_in_one/                # 【方案一】前端集成版
│   ├── README.md              # 使用说明
│   ├── detector.py            # 核心检测程序
│   ├── start.bat              # Windows 启动
│   └── start.sh               # Linux/Mac 启动
│
├── src/                       # 【方案二】前后端分离版
│   ├── README.md              # 使用说明
│   ├── backend/
│   │   └── server.py          # 后端服务器
│   ├── frontend/
│   │   └── client.py          # 前端客户端
│   ├── start_backend.bat      # Windows 后端启动
│   ├── start_backend.sh       # Linux/Mac 后端启动
│   ├── start_frontend.bat     # Windows 前端启动
│   └── start_frontend.sh      # Linux/Mac 前端启动
│
├── models/                    # 模型文件目录
│   ├── yolov5s.pt
│   └── yolov5su.pt
│
├── config/                    # 配置文件
│   └── settings.py
│
├── docs/                      # 文档目录
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── PROJECT_SUMMARY.md
│   └── QUICKSTART.md
│
└── specs/                     # 规范文档
    └── APIs.md
```

## 🎮 使用说明

### All-in-One 版本

1. 运行启动脚本
2. 在界面中配置捕获区域(可选择预设或手动设置)
3. 点击"开始检测"
4. 实时查看检测结果

详细说明: [all_in_one/README.md](all_in_one/README.md)

### 前后端分离版本

1. 先启动后端服务器(默认端口 8002)
2. 启动前端客户端
3. 配置捕获区域
4. 点击"开始检测"建立 WebRTC 连接
5. 实时查看检测结果

详细说明: [src/README.md](src/README.md)

## 🔧 配置说明

### 捕获区域设置

- **自定义区域**: 手动设置 X, Y, 宽度, 高度
- **预设区域**:
  - 左上角 800x1000
  - 居中 1024x768
  - 右半屏

### 性能调优

**All-in-One 版本:**
- 检测频率: 每 5 帧检测一次(可在代码中调整)
- 显示帧率: 30 FPS
- 模型选择: yolov5s(最快)

**前后端分离版本:**
- 视频帧率: 15 FPS
- WebRTC 视频编码: VP8
- 检测间隔: 实时

## 🐛 常见问题

### Q1: 模型加载失败?
**A:** 确保 `models/yolov5s.pt` 存在,或等待程序自动下载(需要网络)。

### Q2: 检测卡顿?
**A:**
- All-in-One: 调整检测频率(`frame_count % 5`)
- 前后端分离: 降低视频帧率

### Q3: 前后端分离版无法连接?
**A:**
- 检查后端是否正常启动(端口 8002)
- 检查防火墙设置
- 尝试使用 All-in-One 版本

### Q4: 窗口无画面?
**A:**
- 检查捕获区域设置是否正确
- 确保 PyQt5 正确安装
- 更新显卡驱动

### Q5: 标签显示乱码?
**A:** 已在最新版本中修复,标签使用纯英文显示。

## 📚 技术栈

- **计算机视觉**: YOLOv5 (Ultralytics)
- **图形界面**: PyQt5
- **屏幕捕获**: MSS
- **图像处理**: OpenCV, NumPy
- **Web 框架**: FastAPI (前后端分离版)
- **实时通信**: WebRTC, WebSocket (前后端分离版)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📄 许可证

MIT License

## 📮 联系方式

如有问题或建议,请提交 Issue。

---

**推荐从 All-in-One 版本开始体验!** 🚀

详细文档:
- [All-in-One 使用指南](all_in_one/README.md)
- [前后端分离使用指南](src/README.md)
- [快速开始指南](docs/QUICKSTART.md)
