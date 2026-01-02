# YOLOv5 前后端分离版

基于 WebRTC 和 WebSocket 的分布式 YOLOv5 实时检测系统。

## 📋 简介

这是一个前后端分离的 YOLOv5 实时检测方案,支持:
- **WebRTC 视频流传输** - 低延迟实时视频
- **WebSocket 数据通信** - 实时检测结果推送
- **分布式部署** - 前后端独立运行
- **易于扩展** - 模块化架构设计

## 🏗️ 架构设计

```
┌─────────────┐                    ┌─────────────┐
│   Frontend  │  ◄──WebRTC Video─► │   Backend   │
│  (client.py)│                    │ (server.py) │
│             │  ◄──WebSocket───►  │             │
│  PyQt5 GUI  │  Detection Results │ YOLO Model  │
│  Screen Cap │                    │  FastAPI    │
└─────────────┘                    └─────────────┘
```

### 组件说明

**后端 (backend/server.py)**
- FastAPI Web 服务器
- WebRTC 连接管理
- YOLOv5 模型加载和推理
- WebSocket 实时数据推送
- HTTP POST 检测 API

**前端 (frontend/client.py)**
- PyQt5 图形界面
- 屏幕区域捕获
- WebRTC 视频发送
- 检测结果接收和显示
- 实时参数调整

## 🚀 快速开始

### 1. 安装依赖

```bash
# 从项目根目录安装
cd ..
pip install -r requirements.txt
```

### 2. 启动后端服务器

```bash
# Windows
start_backend.bat

# Linux/Mac
chmod +x start_backend.sh
./start_backend.sh
```

后端将在 `http://localhost:8002` 启动。

### 3. 启动前端客户端

```bash
# Windows
start_frontend.bat

# Linux/Mac
chmod +x start_frontend.sh
./start_frontend.sh
```

## 🎮 使用说明

### 配置捕获区域

1. **使用预设区域**:
   - 左上角 800x1000
   - 居中 1024x768
   - 右半屏

2. **自定义区域**:
   - 手动设置 X, Y 坐标
   - 调整宽度和高度
   - 实时生效,无需重启

### 开始检测

1. 点击"开始检测"按钮
2. 等待 WebRTC 连接建立(状态: 连接中 → 已连接)
3. 查看实时检测结果
4. 检测框和标签会显示在视频预览中

### 可选功能

- **显示红框**: 勾选后在屏幕上显示捕获区域边框
- **实时参数调整**: 运行中可修改捕获区域
- **检测数量**: 实时显示检测到的对象数量

## ⚙️ 配置说明

### 后端配置

编辑 `backend/server.py` 或使用环境变量:

```python
# 模型路径
MODEL_PATH = os.environ.get("MODEL_PATH", "../models/yolov5s.pt")

# 服务器端口
# 启动命令: uvicorn server:app --port 8002
```

### 前端配置

编辑 `frontend/client.py`:

```python
# 后端地址
BACKEND_URL = "http://localhost:8002"

# 视频帧率
FPS = 15  # 每秒15帧

# 检测频率
DETECT_EVERY = 5  # 每5帧检测一次
```

## 📡 API 接口

### WebRTC Signaling

**POST /offer**
- 接收 WebRTC offer
- 返回 WebRTC answer
- 建立点对点连接

```json
{
  "sdp": "...",
  "type": "offer"
}
```

### WebSocket

**WS /ws**
- 实时检测结果推送
- 双向消息通信

消息格式:
```json
{
  "type": "detection",
  "detections": [
    {
      "x": 100,
      "y": 50,
      "w": 200,
      "h": 150,
      "cls": "person",
      "conf": 0.87
    }
  ]
}
```

### HTTP检测

**POST /detect**
- 单张图片检测
- Base64 编码图片

请求:
```json
{
  "image": "data:image/jpeg;base64,..."
}
```

响应:
```json
{
  "detections": [...],
  "w": 800,
  "h": 1000
}
```

## 🔧 性能优化

### 后端优化

1. **模型选择**:
   - `yolov5s` - 最快,推荐
   - `yolov5m` - 平衡
   - `yolov5l` - 最准确

2. **异步处理**:
   - 使用 FastAPI 异步接口
   - 非阻塞模型推理

3. **资源管理**:
   - GPU 加速(如果可用)
   - 模型缓存机制

### 前端优化

1. **帧率控制**:
   - 降低发送帧率(15 FPS)
   - 减少网络带宽

2. **检测频率**:
   - 每 N 帧检测一次
   - 降低 CPU 占用

3. **视频编码**:
   - VP8 编码
   - 质量与速度平衡

## 🐛 故障排除

### 连接问题

**问题**: WebRTC 连接失败
**解决**:
1. 检查后端是否正常启动
2. 确认端口 8002 未被占用
3. 检查防火墙设置
4. Windows 环境下 aiortc 可能有兼容性问题,考虑使用 all_in_one 版本

**问题**: WebSocket 连接断开
**解决**:
1. 检查网络连接
2. 查看后端日志
3. 重启前后端服务

### 性能问题

**问题**: 视频卡顿
**解决**:
1. 降低视频帧率
2. 减小捕获区域
3. 关闭不必要的应用程序

**问题**: 检测延迟高
**解决**:
1. 使用更快的模型(yolov5s)
2. 增加检测间隔
3. 考虑使用 all_in_one 版本(零网络延迟)

### 模型问题

**问题**: 模型加载失败
**解决**:
1. 检查模型文件路径: `../models/yolov5s.pt`
2. 确保模型文件完整
3. 等待自动下载(需要网络)

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| **视频帧率** | 15 FPS |
| **检测延迟** | 50-200ms |
| **网络带宽** | 1-3 Mbps |
| **CPU 占用** | 30-50% |
| **内存占用** | 500-800 MB |

## 🔄 与 All-in-One 版本对比

| 特性 | 前后端分离版 | All-in-One 版 |
|------|------------|--------------|
| **架构** | 分布式 | 单体应用 |
| **延迟** | 50-200ms | ~7ms |
| **帧率** | 15 FPS | 30 FPS |
| **部署** | 复杂 | 简单 |
| **扩展性** | 优秀 | 一般 |
| **适用场景** | 生产环境 | 快速开发 |

**建议**: 如果不需要远程检测功能,推荐使用 [all_in_one 版本](../all_in_one/),性能更好,使用更简单。

## 📁 文件结构

```
src/
├── README.md                  # 本文件
├── backend/
│   ├── __init__.py
│   └── server.py              # 后端服务器 (402行)
├── frontend/
│   ├── __init__.py
│   └── client.py              # 前端客户端 (420行)
├── start_backend.bat          # Windows 后端启动
├── start_backend.sh           # Linux/Mac 后端启动
├── start_frontend.bat         # Windows 前端启动
└── start_frontend.sh          # Linux/Mac 前端启动
```

## 📚 技术栈

**后端**:
- FastAPI - 现代 Web 框架
- aiortc - Python WebRTC 实现
- Ultralytics - YOLOv5 模型
- WebSocket - 实时通信

**前端**:
- PyQt5 - 图形界面框架
- OpenCV - 图像处理
- MSS - 屏幕捕获
- aiortc - WebRTC 客户端

## 🔗 相关链接

- [项目主页](../README.md)
- [All-in-One 版本](../all_in_one/README.md)
- [快速开始指南](../docs/QUICKSTART.md)
- [架构设计文档](../docs/IMPLEMENTATION_SUMMARY.md)

## 📝 开发说明

### 修改后端

编辑 `backend/server.py`:
- 修改模型路径
- 调整检测参数
- 添加新的 API 端点

### 修改前端

编辑 `frontend/client.py`:
- 调整 UI 布局
- 修改捕获参数
- 添加新功能

### 调试技巧

1. **查看后端日志**:
   ```bash
   # 直接运行查看详细日志
   uvicorn backend.server:app --port 8002 --reload
   ```

2. **查看前端日志**:
   ```bash
   # 直接运行 Python 脚本
   python frontend/client.py
   ```

3. **WebRTC 调试**:
   - 检查 ICE 连接状态
   - 查看 DataChannel 消息
   - 监控视频轨道

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📄 许可证

MIT License
