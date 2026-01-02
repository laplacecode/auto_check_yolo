#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 视频流客户端

推送屏幕帧到后端 + 接收并显示 MJPEG 视频流
"""
import base64
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


# ==================== 区域叠加层 ====================

class RegionOverlay(QWidget):
    """红框叠加层"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.region = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)

    def set_region(self, region):
        self.region = region
        screen = QApplication.desktop().screenGeometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

    def paintEvent(self, event):
        if not self.region:
            return
        painter = QPainter(self)
        pen = QPen(QColor(255, 0, 0), 4, Qt.SolidLine)
        painter.setPen(pen)
        rect = QRect(self.region["left"], self.region["top"],
                    self.region["width"], self.region["height"])
        painter.drawRect(rect)

        # 标签
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setBrush(QColor(255, 0, 0, 180))
        label_rect = QRect(self.region["left"], self.region["top"] - 25, 150, 25)
        painter.drawRect(label_rect)
        painter.drawText(label_rect, Qt.AlignCenter, "Recording Area")

    def start_animation(self):
        self.timer.start(100)

    def stop_animation(self):
        self.timer.stop()


# ==================== 主窗口 ====================

class StreamClient(QWidget):
    """视频流客户端"""

    def __init__(self):
        super().__init__()

        # UI 组件
        self.label = QLabel("点击 '开始检测' 启动视频流")
        self.label.setMinimumSize(800, 1000)
        self.label.setScaledContents(True)
        self.label.setStyleSheet("background-color: #2c3e50; color: white; font-size: 16px;")

        self.btn = QPushButton("开始检测")
        self.btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px;")
        self.btn.clicked.connect(self.toggle)

        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #3498db; font-size: 12px; padding: 5px;")

        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #e74c3c; font-size: 12px; padding: 5px;")

        # 区域选择
        self.region_group = QGroupBox("录制区域")
        region_layout = QHBoxLayout()

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["自定义区域", "左上角 800x1000", "居中 1024x768", "右半屏"])
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)

        region_layout.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 3840)
        self.x_spin.setValue(0)
        region_layout.addWidget(self.x_spin)

        region_layout.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 2160)
        self.y_spin.setValue(0)
        region_layout.addWidget(self.y_spin)

        region_layout.addWidget(QLabel("宽度:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 3840)
        self.width_spin.setValue(800)
        region_layout.addWidget(self.width_spin)

        region_layout.addWidget(QLabel("高度:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 2160)
        self.height_spin.setValue(1000)
        region_layout.addWidget(self.height_spin)

        region_layout.addWidget(self.preset_combo)
        self.region_group.setLayout(region_layout)

        # 红框显示
        self.show_border_checkbox = QCheckBox("显示录制区域红框")
        self.show_border_checkbox.setChecked(True)
        self.show_border_checkbox.stateChanged.connect(self.toggle_border)

        # 状态变量
        self.running = False
        self.sct = mss.mss()
        self.overlay = RegionOverlay()
        self.overlay_visible = False

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.region_group)
        layout.addWidget(self.show_border_checkbox)
        layout.addWidget(self.status_label)
        layout.addWidget(self.fps_label)
        layout.addWidget(self.btn)
        self.setLayout(layout)

        self.setWindowTitle("YOLOv5 视频流检测")
        self.resize(900, 800)

        # 窗口位置：x 居中，y = 10
        screen = QApplication.desktop().screenGeometry()
        window_x = (screen.width() - 900) // 2
        window_y = 10
        self.move(window_x, window_y)

    def apply_preset(self, index):
        """应用预设区域"""
        if index == 1:
            self.x_spin.setValue(0)
            self.y_spin.setValue(0)
            self.width_spin.setValue(800)
            self.height_spin.setValue(1000)
        elif index == 2:
            screen = self.sct.monitors[1]
            self.x_spin.setValue((screen['width'] - 1024) // 2)
            self.y_spin.setValue((screen['height'] - 768) // 2)
            self.width_spin.setValue(1024)
            self.height_spin.setValue(768)
        elif index == 3:
            screen = self.sct.monitors[1]
            self.x_spin.setValue(screen['width'] // 2)
            self.y_spin.setValue(0)
            self.width_spin.setValue(screen['width'] // 2)
            self.height_spin.setValue(screen['height'])

    def get_capture_region(self):
        """获取录制区域"""
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
        else:
            self.overlay.stop_animation()
            self.overlay.hide()
            self.overlay_visible = False

    def update_overlay_region(self):
        """更新叠加层区域"""
        if self.overlay_visible:
            region = self.get_capture_region()
            self.overlay.set_region(region)

    def toggle(self):
        """切换检测状态"""
        self.running = not self.running
        if self.running:
            self.btn.setText("停止检测")
            self.btn.setStyleSheet("background-color: #e74c3c; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 正在启动...")

            if self.show_border_checkbox.isChecked():
                region = self.get_capture_region()
                self.overlay.set_region(region)
                self.overlay.show()
                self.overlay.start_animation()
                self.overlay_visible = True

            # 启动上传线程
            threading.Thread(target=self.upload_loop, daemon=True).start()
            # 启动视频流接收
            threading.Thread(target=self.receive_stream, daemon=True).start()
        else:
            self.btn.setText("开始检测")
            self.btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px;")
            self.status_label.setText("状态: 已停止")

            if self.overlay_visible:
                self.overlay.stop_animation()
                self.overlay.hide()
                self.overlay_visible = False

    def upload_loop(self):
        """上传帧循环"""
        upload_url = "http://127.0.0.1:8004/upload_frame"
        frame_count = 0
        sct = mss.mss()

        print(f"开始上传帧到: {upload_url}")

        try:
            while self.running:
                frame_count += 1

                # 捕获屏幕
                current_region = self.get_capture_region()
                self.update_overlay_region()

                img = np.array(sct.grab(current_region))
                rgb = img[:, :, [2, 1, 0]]  # BGRA -> RGB

                # 每帧都上传（30 FPS 上传，确保流畅）
                try:
                    # 编码为 JPEG
                    pil_img = Image.fromarray(rgb)
                    buffer = BytesIO()
                    pil_img.save(buffer, format="JPEG", quality=75)
                    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                    # 异步上传（不等待响应）
                    threading.Thread(
                        target=lambda: requests.post(upload_url, json={"image": img_b64}, timeout=0.3),
                        daemon=True
                    ).start()

                    if frame_count % 30 == 0:
                        print(f"已上传 {frame_count} 帧")

                except Exception as e:
                    if frame_count % 30 == 0:
                        print(f"上传错误: {e}")

                time.sleep(1 / 30)  # 30 FPS 捕获

        except Exception as e:
            print(f"上传循环错误: {e}")

    def receive_stream(self):
        """接收 MJPEG 视频流"""
        stream_url = "http://127.0.0.1:8004/video_stream"

        # 等待一下，让上传线程先启动
        time.sleep(1)

        print(f"开始接收视频流: {stream_url}")
        self.status_label.setText("状态: 正在接收视频流...")

        try:
            resp = requests.get(stream_url, stream=True, timeout=10)

            if resp.status_code != 200:
                print(f"视频流连接失败: HTTP {resp.status_code}")
                return

            bytes_data = bytes()
            frame_count = 0
            start_time = time.time()

            for chunk in resp.iter_content(chunk_size=4096):  # 增大缓冲区
                if not self.running:
                    break

                bytes_data += chunk

                # 查找完整的 JPEG 帧
                while True:
                    a = bytes_data.find(b'\xff\xd8')  # JPEG 起始
                    b = bytes_data.find(b'\xff\xd9')  # JPEG 结束

                    if a != -1 and b != -1 and b > a:
                        jpg = bytes_data[a:b+2]
                        bytes_data = bytes_data[b+2:]

                        try:
                            # 解码并显示
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                            if frame is not None:
                                frame_count += 1

                                # 转换为 RGB 并显示
                                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                h, w, ch = rgb.shape
                                bytes_per_line = ch * w
                                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                                pix = QPixmap.fromImage(qimg).scaled(800, 1000, Qt.KeepAspectRatio)
                                self.label.setPixmap(pix)

                                # 计算 FPS
                                if frame_count % 30 == 0:
                                    elapsed = time.time() - start_time
                                    fps = 30 / elapsed if elapsed > 0 else 0
                                    self.fps_label.setText(f"FPS: {fps:.1f}")
                                    print(f"接收 FPS: {fps:.1f}")
                                    start_time = time.time()

                                QApplication.processEvents()
                        except Exception as decode_error:
                            print(f"帧解码错误: {decode_error}")
                    else:
                        break  # 没有完整帧，等待更多数据

        except Exception as e:
            print(f"视频流接收错误: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"状态: 视频流错误 - {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = StreamClient()
    client.show()
    sys.exit(app.exec_())
