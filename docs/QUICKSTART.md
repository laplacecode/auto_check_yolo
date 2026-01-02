# 快速开始

## 一键启动

### Windows

```bash
# 1. 检查环境
python check_setup.py

# 2. 启动后端
start_backend.bat

# 3. 启动前端（新命令行窗口）
start_frontend.bat
```

### Linux / macOS

```bash
# 1. 检查环境
python check_setup.py

# 2. 启动后端
./start_backend.sh

# 3. 启动前端（新终端）
./start_frontend.sh
```

## 第一次使用

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **检查环境**
   ```bash
   python check_setup.py
   ```

3. **启动系统** (按上面的步骤)

4. **配置录制区域**
   - 在前端窗口设置 X, Y, Width, Height
   - 或选择预设配置

5. **启用红框**
   - 勾选"显示录制区域红框"
   - 观察红框位置

6. **移动前端窗口**
   - 确保前端窗口不在红框内

7. **开始检测**
   - 点击 "Start WebRTC Detection"

## 详细文档

查看 [README.md](README.md) 获取完整说明。
