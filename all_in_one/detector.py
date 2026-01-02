#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 实时检测 - All-in-One 版本

前端直接运行 YOLO 检测，无需后端服务器
提供基于 PyQt5 的图形界面，支持屏幕区域录制、
实时参数调整和可视化红框提示
"""
import sys
import time
import threading
import os
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt5.QtWidgets import (QApplication, QLabel, QPushButton, QVBoxLayout,
                             QWidget, QHBoxLayout, QSpinBox, QGroupBox,
                             QComboBox, QCheckBox)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect, QTimer


# ==================== YOLO 模型管理 ====================

class YOLOModel:
    """YOLO 模型加载和推理"""

    def __init__(self, model_path="yolov5s.pt"):
        self.model = None
        self.model_path = model_path
        self.lock = threading.Lock()

        # COCO 数据集类别名称
        self.class_names = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
            'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
            'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
            'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard',
            'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase',
            'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]

    def load(self):
        """加载 YOLO 模型（线程安全）"""
        with self.lock:
            if self.model is not None:
                return self.model

            print(f"[信息] 正在加载模型: {self.model_path}")

            # 尝试使用 ultralytics 加载
            try:
                from ultralytics import YOLO
                if os.path.exists(self.model_path):
                    self.model = YOLO(self.model_path)
                    print(f"[信息] 模型加载成功（ultralytics）")
                else:
                    print(f"[警告] 模型文件不存在: {self.model_path}")
                    self.model = None
            except Exception as e:
                print(f"[错误] ultralytics 加载失败: {e}")
                self.model = None

            # 如果 ultralytics 失败，尝试 torch.hub
            if self.model is None:
                try:
                    import torch
                    self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
                    print(f"[信息] 模型加载成功（torch.hub）")
                except Exception as e:
                    print(f"[错误] torch.hub 加载失败: {e}")
                    self.model = None

            return self.model

    def detect(self, frame):
        """
        对图像进行检测

        Args:
            frame: numpy 数组格式的图像 (RGB)

        Returns:
            list: 检测结果列表 [{x, y, w, h, cls, conf}, ...]
        """
        if self.model is None:
            # 返回模拟数据用于测试
            h, w = frame.shape[:2]
            return [{
                "x": 50, "y": 50,
                "w": 200, "h": 150,
                "cls": "测试",
                "conf": 0.9
            }]

        try:
            results = self.model(frame)
            detections = []

            # 解析检测结果
            r0 = results[0]
            if hasattr(r0, 'boxes'):
                boxes = r0.boxes
                data_arr = boxes.data

                # 转换为 numpy 数组
                if hasattr(data_arr, 'cpu'):
                    arr = data_arr.cpu().numpy()
                else:
                    arr = np.array(data_arr)

                # 提取每个检测框的信息
                for row in arr:
                    x1, y1, x2, y2, conf, cls = row
                    cls_id = int(cls)
                    cls_name = self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
                    detections.append({
                        "x": int(x1),
                        "y": int(y1),
                        "w": int(x2 - x1),
                        "h": int(y2 - y1),
                        "cls": cls_name,
                        "conf": float(conf),
                    })

            return detections

        except Exception as e:
            print(f"[错误] 检测失败: {e}")
            return []


# ==================== 区域叠加层（红框提示） ====================

class RegionOverlay(QWidget):
    """
    全屏透明叠加层，用于显示录制区域的红色边框
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.region = None
        self.opacity = 1.0
        self.fade_direction = -1

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate)

    def set_region(self, region):
        """设置要高亮的区域"""
        self.region = region
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

    def paintEvent(self, event):
        """绘制红色边框"""
        if not self.region:
            return

        painter = QPainter(self)
        pen = QPen(QColor(255, 0, 0, int(255 * self.opacity)))
        pen.setWidth(4)
        painter.setPen(pen)

        x = self.region['left']
        y = self.region['top']
        w = self.region['width']
        h = self.region['height']

        painter.drawRect(x, y, w, h)

    def animate(self):
        """动画效果：呼吸灯"""
        self.opacity += self.fade_direction * 0.05
        if self.opacity <= 0.3:
            self.opacity = 0.3
            self.fade_direction = 1
        elif self.opacity >= 1.0:
            self.opacity = 1.0
            self.fade_direction = -1

        self.update()

    def start_animation(self):
        """启动动画定时器"""
        self.timer.start(50)

    def stop_animation(self):
        """停止动画定时器"""
        self.timer.stop()


# ==================== 主窗口 ====================

class DetectorClient(QWidget):
    """
    主客户端窗口

    功能：
    - 区域选择和预设配置
    - 本地 YOLO 检测
    - 检测结果显示
    - 红框可视化提示
    - 实时参数调整
    """

    def __init__(self, model_path="../models/yolov5s.pt"):
        super().__init__()

        # ========== YOLO 模型 ==========
        self.yolo = YOLOModel(model_path)

        # ========== UI 组件 ==========
        # 视频显示标签
        self.label = QLabel("点击 '开始检测' 开始屏幕捕获和检测")
        self.label.setMinimumSize(800, 1000)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background-color: #2c3e50; color: white; font-size: 16px;")

        # 开始/停止按钮
        self.btn = QPushButton("开始检测")
        self.btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px;")
        self.btn.clicked.connect(self.toggle)

        # 状态标签
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #3498db; font-size: 12px; padding: 5px;")

        # 检测数量标签
        self.detection_label = QLabel("检测数: 0")
        self.detection_label.setStyleSheet("color: #e74c3c; font-size: 12px; padding: 5px;")

        # ========== 区域选择控件 ==========
        self.region_group = QGroupBox("录制区域 (避免录制自己窗口) - 实时生效")
        self.region_group.setStyleSheet("QGroupBox { font-size: 12px; color: #ecf0f1; font-weight: bold; }")

        region_layout = QHBoxLayout()

        # 预设选择
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "自定义区域",
            "左上角 800x1000",
            "居中 1024x768",
            "右半屏"
        ])
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)

        # X 坐标
        region_layout.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 3840)
        self.x_spin.setValue(0)
        self.x_spin.setStyleSheet("color: black; background: white;")
        region_layout.addWidget(self.x_spin)

        # Y 坐标
        region_layout.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 2160)
        self.y_spin.setValue(0)
        self.y_spin.setStyleSheet("color: black; background: white;")
        region_layout.addWidget(self.y_spin)

        # 宽度
        region_layout.addWidget(QLabel("宽度:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 3840)
        self.width_spin.setValue(800)
        self.width_spin.setStyleSheet("color: black; background: white;")
        region_layout.addWidget(self.width_spin)

        # 高度
        region_layout.addWidget(QLabel("高度:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 2160)
        self.height_spin.setValue(1000)
        self.height_spin.setStyleSheet("color: black; background: white;")
        region_layout.addWidget(self.height_spin)

        region_layout.addWidget(self.preset_combo)
        self.region_group.setLayout(region_layout)

        # 红框显示复选框
        self.show_border_checkbox = QCheckBox("显示录制区域红框")
        self.show_border_checkbox.setStyleSheet("color: #ecf0f1; font-size: 12px;")
        self.show_border_checkbox.setChecked(True)
        self.show_border_checkbox.stateChanged.connect(self.toggle_border)

        # ========== 状态变量 ==========
        self.running = False
        self.sct = mss.mss()
        self.detections = []
        self.last_detection_time = 0
        self.current_frame = None
        self.lock = threading.Lock()

        # 创建叠加层窗口
        self.overlay = RegionOverlay()
        self.overlay_visible = False

        # ========== 布局 ==========
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.region_group)
        layout.addWidget(self.show_border_checkbox)
        layout.addWidget(self.status_label)
        layout.addWidget(self.detection_label)
        layout.addWidget(self.btn)
        self.setLayout(layout)

        self.setWindowTitle("YOLOv5 实时检测 - All-in-One 版本")
        self.resize(900, 800)

    # ========== 辅助方法 ==========

    def apply_preset(self, index):
        """应用预设区域配置"""
        if index == 1:  # 左上角 800x1000
            self.x_spin.setValue(0)
            self.y_spin.setValue(0)
            self.width_spin.setValue(800)
            self.height_spin.setValue(1000)
        elif index == 2:  # 居中 1024x768
            screen = self.sct.monitors[1]
            center_x = (screen['width'] - 1024) // 2
            center_y = (screen['height'] - 768) // 2
            self.x_spin.setValue(center_x)
            self.y_spin.setValue(center_y)
            self.width_spin.setValue(1024)
            self.height_spin.setValue(768)
        elif index == 3:  # 右半屏
            screen = self.sct.monitors[1]
            self.x_spin.setValue(screen['width'] // 2)
            self.y_spin.setValue(0)
            self.width_spin.setValue(screen['width'] // 2)
            self.height_spin.setValue(screen['height'])

    def get_capture_region(self):
        """获取当前录制区域"""
        return {
            "left": self.x_spin.value(),
            "top": self.y_spin.value(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value()
        }

    def toggle_border(self, state):
        """切换红框显示"""
        if state == Qt.Checked:
            region = self.get_capture_region()
            self.overlay.set_region(region)
            self.overlay.show()
            self.overlay.start_animation()
            self.overlay_visible = True
            print("[信息] 红框叠加层已启用")
        else:
            self.overlay.stop_animation()
            self.overlay.hide()
            self.overlay_visible = False
            print("[信息] 红框叠加层已禁用")

    def update_overlay_region(self):
        """更新叠加层区域（如果可见）"""
        if self.overlay_visible:
            region = self.get_capture_region()
            self.overlay.set_region(region)

    # ========== 主要功能 ==========

    def toggle(self):
        """切换检测状态"""
        self.running = not self.running
        if self.running:
            self.btn.setText("停止检测")
            self.btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 正在加载模型...")
            print("[信息] 开始检测")

            # 如果勾选，显示红框
            if self.show_border_checkbox.isChecked():
                region = self.get_capture_region()
                self.overlay.set_region(region)
                self.overlay.show()
                self.overlay.start_animation()
                self.overlay_visible = True

            # 启动 UI 更新定时器（在主线程）
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self.update_display)
            self.update_timer.start(33)  # 30 FPS UI 更新
            print("[信息] UI 更新定时器已启动")

            # 启动后台检测线程
            threading.Thread(target=self.start_detection_thread, daemon=True).start()
        else:
            self.btn.setText("开始检测")
            self.btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 已停止")
            print("[信息] 停止检测")

            # 隐藏红框
            if self.overlay_visible:
                self.overlay.stop_animation()
                self.overlay.hide()
                self.overlay_visible = False

    def start_detection_thread(self):
        """启动检测线程（在后台线程中调用）"""
        # 加载模型
        model = self.yolo.load()
        if model is None:
            self.status_label.setText("状态: 模型加载失败")
            print("[警告] 模型未加载，将使用测试数据")
        else:
            self.status_label.setText("状态: 正在运行检测...")

        # 启动检测循环
        self.detection_thread()

    def detection_thread(self):
        """后台检测线程：只负责检测，不更新UI"""
        frame_count = 0
        print(f"[信息] 检测线程已启动")

        # 为这个线程创建独立的 mss 实例（线程安全）
        sct = mss.mss()

        try:
            while self.running:
                frame_count += 1

                # 捕获屏幕
                current_region = self.get_capture_region()
                img = np.array(sct.grab(current_region))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 保存当前帧（供 UI 线程使用）
                with self.lock:
                    self.current_frame = rgb.copy()

                # 每30帧输出一次调试信息
                if frame_count % 30 == 0:
                    print(f"[调试] 已捕获 {frame_count} 帧，当前帧大小: {rgb.shape}")

                # 每5帧检测一次（降低 CPU 占用）
                if frame_count % 5 == 0:
                    detections = self.yolo.detect(rgb)

                    with self.lock:
                        self.detections = detections
                        self.last_detection_time = time.time()

                    if len(detections) > 0:
                        print(f"[信息] 帧 {frame_count}: 检测到 {len(detections)} 个对象")

                # 控制帧率
                time.sleep(1 / 30)  # 30 FPS 捕获

        except Exception as e:
            print(f"[错误] 检测线程错误: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"状态: 检测错误")
        finally:
            print(f"[信息] 检测线程已结束")

    def update_display(self):
        """UI 更新函数（由 QTimer 调用）"""
        if not self.running:
            # 停止定时器（在 UI 线程中安全）
            if hasattr(self, 'update_timer') and self.update_timer.isActive():
                self.update_timer.stop()
                self.status_label.setText("状态: 已停止")
                print("[信息] UI 更新定时器已停止")
            return

        try:
            # 更新叠加层区域
            self.update_overlay_region()

            # 获取当前帧和检测结果
            with self.lock:
                if self.current_frame is None:
                    return  # 静默等待帧数据

                # 复制帧数据
                frame = self.current_frame.copy()

                # 清除过期检测（超过 2 秒）
                if time.time() - self.last_detection_time > 2.0:
                    self.detections = []

                detection_count = len(self.detections)
                detections_snapshot = self.detections.copy()

            # 绘制所有检测框
            for d in detections_snapshot:
                x, y, wbox, hbox = d.get('x', 0), d.get('y', 0), d.get('w', 0), d.get('h', 0)
                conf = d.get('conf', 0)
                cls = d.get('cls', '?')

                # 绘制边框
                cv2.rectangle(frame, (x, y), (x + wbox, y + hbox), (0, 255, 0), 3)

                # 绘制标签背景（纯英文，避免乱码）
                label = f"{cls}: {conf:.2f}"
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x, y - label_h - 10), (x + label_w, y), (0, 255, 0), -1)
                cv2.putText(frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            # 更新检测数量标签
            self.detection_label.setText(f"检测数: {detection_count}")

            # 转换为 QImage 并显示
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(qimg)
            self.label.setPixmap(pix)

        except Exception as e:
            print(f"[错误] UI 更新错误: {e}")
            import traceback
            traceback.print_exc()


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 查找模型文件
    model_paths = [
        "../models/yolov5s.pt",  # 推荐：项目models目录
        "yolov5s.pt",             # 当前目录
        "../yolov5s.pt",          # 项目根目录（兼容旧版）
    ]

    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break

    if model_path:
        print(f"[信息] 找到模型文件: {model_path}")
    else:
        print(f"[警告] 未找到模型文件，将尝试自动下载")
        model_path = "yolov5s.pt"

    client = DetectorClient(model_path)
    client.resize(820, 680)
    client.show()
    sys.exit(app.exec_())
