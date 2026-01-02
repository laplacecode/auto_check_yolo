#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 实时检测前端客户端

提供基于 PyQt5 的图形界面，支持屏幕区域录制、
实时参数调整和可视化红框提示
"""
import base64
import json
import socket
import sys
import threading
import time
from io import BytesIO

import cv2
import mss
import numpy as np
import requests
from PIL import Image
from PyQt5.QtCore import QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton, QSpinBox,
                             QVBoxLayout, QWidget)

# 创建一个持久的 requests session（连接池复用，避免每次请求重新建立 TCP 连接）
detection_session = requests.Session()
detection_session.headers.update({'Connection': 'keep-alive'})
# 设置连接池大小和重试策略
adapter = requests.adapters.HTTPAdapter(
    pool_connections=1,
    pool_maxsize=1,
    max_retries=0
)
detection_session.mount('http://', adapter)


# ==================== 区域叠加层（红框提示） ====================

class RegionOverlay(QWidget):
    """
    透明叠加窗口，用于显示录制区域的红色边框

    特性：
    - 全屏透明窗口
    - 红色边框标示录制区域
    - 鼠标事件穿透（不阻挡操作）
    - 置顶显示

    Attributes:
        region (dict): 录制区域坐标 {left, top, width, height}
        timer (QTimer): 用于更新显示的定时器
    """

    def __init__(self):
        """初始化叠加层窗口"""
        super().__init__()
        self.region = {"left": 0, "top": 0, "width": 800, "height": 1000}

        # 设置窗口属性：置顶、无边框、工具窗口
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        # 设置透明背景和鼠标穿透
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # 定时器用于更新显示
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)

    def set_region(self, region):
        """
        更新要显示的区域

        Args:
            region (dict): 区域坐标字典，包含 left, top, width, height
        """
        self.region = region
        # 设置窗口覆盖整个屏幕
        screen = QApplication.desktop().screenGeometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        self.update()

    def paintEvent(self, _event):
        """
        绘制红色边框和标签

        Args:
            _event: Qt 绘制事件对象
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制红色边框
        pen = QPen(QColor(255, 0, 0), 4, Qt.SolidLine)
        painter.setPen(pen)

        rect = QRect(
            self.region["left"],
            self.region["top"],
            self.region["width"],
            self.region["height"]
        )
        painter.drawRect(rect)

        # 绘制半透明标签
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setBrush(QColor(255, 0, 0, 180))
        label_rect = QRect(
            self.region["left"],
            self.region["top"] - 25,
            150,
            25
        )
        painter.drawRect(label_rect)
        painter.drawText(label_rect, Qt.AlignCenter, "Recording Area")

    def start_animation(self):
        """启动动画定时器，每 100ms 更新一次"""
        self.timer.start(100)

    def stop_animation(self):
        """停止动画定时器"""
        self.timer.stop()


# ==================== 主窗口 ====================

class VideoClient(QWidget):
    """
    主客户端窗口

    功能：
    - 区域选择和预设配置
    - 检测结果显示
    - 红框可视化提示
    - 实时参数调整

    Attributes:
        label (QLabel): 视频显示标签
        btn (QPushButton): 开始/停止按钮
        status_label (QLabel): 状态显示标签
        detection_label (QLabel): 检测数量标签
        running (bool): 检测运行状态
        sct (mss.mss): 屏幕截图工具
        detections (list): 当前检测结果列表
        last_detection_time (float): 上次检测时间戳
        lock (threading.Lock): 线程锁
        overlay (RegionOverlay): 红框叠加层窗口
        overlay_visible (bool): 叠加层显示状态
    """

    def __init__(self):
        """初始化客户端窗口"""
        super().__init__()

        # ========== UI 组件 ==========
        # 视频显示标签
        self.label = QLabel("点击 'Start' 开始屏幕捕获和检测")
        self.label.setMinimumSize(800, 1000)
        self.label.setScaledContents(True)
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
        self.lock = threading.Lock()
        self.detection_in_progress = False  # 标记是否有检测正在进行

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

        self.setWindowTitle("YOLOv5 实时检测 - 屏幕捕获")
        self.resize(900, 800)

        # 设置窗口位置：x 居中，y = 10
        screen = QApplication.desktop().screenGeometry()
        window_x = (screen.width() - 900) // 2
        window_y = 10
        self.move(window_x, window_y)

    # ========== 辅助方法 ==========

    def apply_preset(self, index):
        """
        应用预设区域配置

        Args:
            index (int): 预设索引
                0 - 自定义区域
                1 - 左上角 800x1000
                2 - 居中 1024x768
                3 - 右半屏
        """
        if index == 1:
            self.x_spin.setValue(0)
            self.y_spin.setValue(0)
            self.width_spin.setValue(800)
            self.height_spin.setValue(1000)
        elif index == 2:
            screen = self.sct.monitors[1]
            center_x = (screen['width'] - 1024) // 2
            center_y = (screen['height'] - 768) // 2
            self.x_spin.setValue(center_x)
            self.y_spin.setValue(center_y)
            self.width_spin.setValue(1024)
            self.height_spin.setValue(768)
        elif index == 3:
            screen = self.sct.monitors[1]
            self.x_spin.setValue(screen['width'] // 2)
            self.y_spin.setValue(0)
            self.width_spin.setValue(screen['width'] // 2)
            self.height_spin.setValue(screen['height'])

    def get_capture_region(self):
        """
        获取当前录制区域

        Returns:
            dict: 录制区域坐标 {left, top, width, height}
        """
        return {
            "left": self.x_spin.value(),
            "top": self.y_spin.value(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value()
        }

    def toggle_border(self, state):
        """
        切换红框显示

        Args:
            state (Qt.CheckState): 复选框状态
        """
        if state == Qt.Checked:
            region = self.get_capture_region()
            self.overlay.set_region(region)
            self.overlay.show()
            self.overlay.start_animation()
            self.overlay_visible = True
            print("红框叠加层已启用")
        else:
            self.overlay.stop_animation()
            self.overlay.hide()
            self.overlay_visible = False
            print("红框叠加层已禁用")

    def update_overlay_region(self):
        """更新叠加层区域（如果可见）"""
        if self.overlay_visible:
            region = self.get_capture_region()
            self.overlay.set_region(region)

    # ========== 主要功能 ==========

    def async_detection(self, rgb, frame_count):
        """
        异步检测方法（在后台线程中运行）- 使用 UDP 协议

        Args:
            rgb: RGB 图像数组
            frame_count: 当前帧数
        """
        udp_host = "127.0.0.1"
        udp_port = 8003

        try:
            # 将图像编码为 JPEG base64（极低质量和分辨率以提升速度）
            h_img, w_img = rgb.shape[:2]
            scale_factor = 1.0

            # 更激进的缩放 - 限制在 480px
            if w_img > 480:
                scale_factor = w_img / 480
                new_w, new_h = 480, int(h_img / scale_factor)
                pil_img = Image.fromarray(rgb).resize((new_w, new_h), Image.BILINEAR)
            else:
                pil_img = Image.fromarray(rgb)

            buffer = BytesIO()
            pil_img.save(buffer, format="JPEG", quality=35)  # 极低质量 35
            img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # 创建 UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.5)  # 500ms 超时

            # 发送检测请求
            request_data = json.dumps({"image": img_b64}).encode('utf-8')

            # 检查数据大小（UDP 限制 64KB）
            if len(request_data) < 65000:
                sock.sendto(request_data, (udp_host, udp_port))

                # 接收响应
                response_data, _ = sock.recvfrom(65536)
                result = json.loads(response_data.decode('utf-8'))

                detections = result.get("detections", [])

                # 如果图像被缩放，需要将检测框坐标放大回原始尺寸
                if scale_factor > 1.0:
                    for det in detections:
                        det['x'] = int(det['x'] * scale_factor)
                        det['y'] = int(det['y'] * scale_factor)
                        det['w'] = int(det['w'] * scale_factor)
                        det['h'] = int(det['h'] * scale_factor)

                with self.lock:
                    self.detections = detections
                    self.last_detection_time = time.time()

                det_count = len(self.detections)
                if det_count > 0:
                    print(f"帧 {frame_count}: 检测到 {det_count} 个对象 (UDP)")
            else:
                print(f"警告: 图像数据过大 ({len(request_data)} bytes)，跳过检测")

            sock.close()

        except socket.timeout:
            print("UDP 检测请求超时")
        except Exception as e:
            print(f"UDP 检测请求失败: {e}")
        finally:
            # 释放检测锁，允许下次检测
            self.detection_in_progress = False

    def toggle(self):
        """切换检测状态"""
        self.running = not self.running
        if self.running:
            self.btn.setText("停止检测")
            self.btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 正在启动...")

            # 如果勾选，显示红框
            if self.show_border_checkbox.isChecked():
                region = self.get_capture_region()
                self.overlay.set_region(region)
                self.overlay.show()
                self.overlay.start_animation()
                self.overlay_visible = True

            threading.Thread(target=self.detection_loop, daemon=True).start()
        else:
            self.btn.setText("开始检测")
            self.btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 已停止")

            # 隐藏红框
            if self.overlay_visible:
                self.overlay.stop_animation()
                self.overlay.hide()
                self.overlay_visible = False

    def detection_loop(self):
        """
        检测循环：捕获屏幕、发送到后端检测、显示结果

        循环执行以下步骤：
        1. 捕获指定区域的屏幕
        2. 每 5 帧发送图像到后端进行检测
        3. 接收检测结果并绘制边框
        4. 更新 UI 显示
        """
        detect_url = "http://127.0.0.1:8002/detect"
        frame_count = 0

        self.status_label.setText("状态: 正在运行检测...")
        print(f"开始检测循环，后端地址: {detect_url}")

        # 为此线程创建独立的 mss 实例（线程安全）
        sct = mss.mss()

        try:
            while self.running:
                frame_count += 1

                # 动态获取当前区域（实现实时调整）
                current_region = self.get_capture_region()

                # 实时更新叠加层区域
                self.update_overlay_region()

                # 捕获屏幕 - 使用 numpy 数组切片而不是 cv2.cvtColor（避免线程安全问题）
                img = np.array(sct.grab(current_region))
                # 直接通过数组切片转换 BGRA -> RGB（避免 cv2 线程问题）
                rgb = img[:, :, [2, 1, 0]]  # BGR to RGB

                # 异步发送检测请求（非阻塞）- 每 15 帧检测一次，且仅在上次检测完成后才发送新请求
                if frame_count % 15 == 0 and not self.detection_in_progress:
                    self.detection_in_progress = True
                    # 在后台线程中发送检测请求，避免阻塞主循环
                    threading.Thread(
                        target=self.async_detection,
                        args=(rgb.copy(), frame_count),
                        daemon=True
                    ).start()

                # 绘制检测框（使用锁获取一致的快照）
                detection_count = 0
                detections_snapshot = []
                with self.lock:
                    # 清除过期检测（超过 2 秒）
                    if time.time() - self.last_detection_time > 2.0:
                        self.detections = []

                    detection_count = len(self.detections)
                    detections_snapshot = self.detections.copy()

                # 创建一个副本用于绘制（避免修改原始数据）
                display_frame = rgb.copy()

                # 绘制所有检测框
                for d in detections_snapshot:
                    x, y, wbox, hbox = d.get('x', 0), d.get('y', 0), d.get('w', 0), d.get('h', 0)
                    conf = d.get('conf', 0)
                    cls = d.get('cls', '?')

                    # 绘制边框
                    cv2.rectangle(display_frame, (x, y), (x + wbox, y + hbox), (0, 255, 0), 3)

                    # 绘制标签背景（纯英文，避免中文乱码）
                    label = f"{cls}: {conf:.2f}"
                    (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(display_frame, (x, y - label_h - 10), (x + label_w, y), (0, 255, 0), -1)
                    cv2.putText(display_frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                # 更新检测数量标签
                self.detection_label.setText(f"检测数: {detection_count}")

                # 转换为 QImage 并显示
                h, w, ch = display_frame.shape
                bytes_per_line = ch * w
                qimg = QImage(display_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                pix = QPixmap.fromImage(qimg).scaled(800, 1000, Qt.KeepAspectRatio)
                self.label.setPixmap(pix)
                QApplication.processEvents()

                time.sleep(1 / 30)  # 提升到 30 FPS

        except Exception as e:
            print(f"检测循环错误: {e}")
            self.status_label.setText("状态: 检测循环错误")
        finally:
            self.status_label.setText("状态: 已停止")


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    """
    主程序入口

    创建 PyQt5 应用并启动客户端窗口
    """
    app = QApplication(sys.argv)
    client = VideoClient()
    client.resize(820, 680)
    client.show()
    sys.exit(app.exec_())
