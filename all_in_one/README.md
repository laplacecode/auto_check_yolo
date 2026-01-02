# YOLOv5 实时检测 - All-in-One 版本

## 📋 简介

这是一个独立的、单文件的 YOLOv5 实时检测程序，**无需后端服务器**，前端直接运行 YOLO 检测。

### ✨ 特点

- **🚀 零延迟**：前端本地检测，无网络传输延迟
- **📦 单文件**：所有功能集成在一个文件中
- **🎯 易用**：只需运行一个脚本即可启动
- **⚡ 高性能**：比 HTTP POST 方案快得多，不卡顿
- **🖼️ 实时预览**：屏幕捕获和检测结果实时显示

## 🔧 依赖安装

```bash
pip install PyQt5 opencv-python numpy mss pillow ultralytics
```

或使用项目根目录的 requirements.txt：

```bash
pip install -r ../requirements.txt
```

## 📦 模型文件

程序会自动查找以下位置的模型文件：
- `../models/yolov5s.pt`（推荐，项目models目录）
- `yolov5s.pt`（当前目录）
- `../yolov5s.pt`（项目根目录）

如果找不到模型文件，程序会尝试使用 `torch.hub` 自动下载。

## 🚀 使用方法

### Windows
```bash
start.bat
```

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

或直接运行：
```bash
python detector.py
```

## 🎮 操作说明

1. **启动程序**：双击 `start.bat`（Windows）或运行 `start.sh`（Linux/Mac）

2. **配置录制区域**：
   - 使用预设选项（左上角、居中、右半屏）
   - 或手动设置 X、Y、宽度、高度

3. **开始检测**：
   - 点击"开始检测"按钮
   - 程序会加载 YOLO 模型（首次加载需要几秒钟）
   - 开始捕获屏幕并实时检测

4. **查看结果**：
   - 绿色边框显示检测到的对象
   - 标签显示类别和置信度
   - 窗口底部显示检测数量

5. **停止检测**：点击"停止检测"按钮

## ⚙️ 性能优化

- **检测频率**：每 5 帧检测一次（可在代码中调整 `frame_count % 5`）
- **显示帧率**：30 FPS（可在代码中调整 `time.sleep(1 / 30)`）
- **UI 更新**：30 FPS，独立于检测线程
- **模型选择**：使用 `yolov5s`（最快），也可替换为 `yolov5m`、`yolov5l` 等

## 📊 与其他方案对比

| 方案 | 延迟 | 卡顿 | 复杂度 | 推荐度 |
|------|------|------|--------|--------|
| **All-in-One (本方案)** | ⭐⭐⭐⭐⭐ | 无 | 低 | ⭐⭐⭐⭐⭐ |
| HTTP POST | ⭐⭐ | 严重 | 高 | ⭐ |
| WebRTC | ⭐⭐⭐ | 无法连接 | 很高 | ❌ |

## 🐛 故障排除

### 模型加载失败
- 确保 `yolov5s.pt` 文件存在
- 或等待程序自动下载（需要网络连接）

### 检测卡顿
- 调整检测频率（增加 `frame_count % 5` 中的数字，如改为 10）
- 降低捕获分辨率
- 使用更小的模型

### 窗口显示问题
- 确保 PyQt5 正确安装
- 更新显卡驱动

## 📝 代码结构

```
detector.py
├── YOLOModel          # YOLO 模型加载和推理
├── RegionOverlay      # 红框叠加层
├── DetectorClient     # 主窗口（GUI + 检测循环）
└── main               # 程序入口
```

## 📄 许可证

本项目使用与主项目相同的许可证。
