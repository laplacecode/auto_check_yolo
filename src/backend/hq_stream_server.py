#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 高质量视频流服务器

特点：
- 保持原始分辨率和质量
- YOLO 完整识别每一帧
- 稳定 30 FPS 输出
- 允许 2-3 秒延迟
"""
import os
import threading
import time
from collections import deque
from queue import Queue

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from io import BytesIO
from PIL import Image

# ==================== 应用配置 ====================
app = FastAPI(title="YOLOv5 HQ Stream", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 模型管理 ====================
MODEL_PATH = os.environ.get("MODEL_PATH", "../models/yolov5s.pt")
_model = None
_model_lock = threading.Lock()

COCO_CLASSES = [
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


def load_model():
    """加载 YOLOv5 模型"""
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        print(f"正在加载模型: {MODEL_PATH}")
        try:
            from ultralytics import YOLO
            if os.path.exists(MODEL_PATH):
                _model = YOLO(MODEL_PATH)
                print("✓ 模型加载成功")
            else:
                _model = None
        except Exception as e:
            print(f"ultralytics 加载失败: {e}")
            try:
                import torch
                _model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
                print("✓ 通过 torch.hub 加载模型成功")
            except Exception as e2:
                print(f"torch.hub 加载失败: {e2}")
                _model = None

        return _model


# ==================== 高质量帧处理器 ====================
class HighQualityFrameProcessor:
    """
    高质量帧处理器

    特性：
    - 保持原始分辨率（不缩放）
    - 高质量 JPEG (95%)
    - 每帧都进行 YOLO 检测
    - 队列缓冲确保 30 FPS 稳定输出
    """

    def __init__(self, buffer_size=90):  # 3 秒缓冲 @ 30fps
        self.input_queue = Queue(maxsize=buffer_size)
        self.output_queue = Queue(maxsize=buffer_size)
        self.running = False
        self.stats = {
            'received': 0,
            'processed': 0,
            'sent': 0,
            'dropped': 0
        }
        self.lock = threading.Lock()

    def add_frame(self, frame_rgb):
        """添加帧到输入队列"""
        try:
            self.input_queue.put_nowait(frame_rgb)
            with self.lock:
                self.stats['received'] += 1
        except:
            with self.lock:
                self.stats['dropped'] += 1

    def get_frame(self):
        """获取处理后的帧"""
        try:
            return self.output_queue.get(timeout=0.1)
        except:
            return None

    def process_worker(self):
        """处理线程：YOLO 检测 + 标注"""
        model = load_model()
        print("✓ 处理线程已启动")

        while self.running:
            try:
                # 获取输入帧
                frame = self.input_queue.get(timeout=0.1)

                # YOLO 检测
                annotated_frame = frame.copy()

                if model:
                    results = model(frame)
                    r0 = results[0]

                    if hasattr(r0, 'boxes'):
                        data_arr = r0.boxes.data
                        arr = data_arr.cpu().numpy() if hasattr(data_arr, 'cpu') else np.array(data_arr)

                        for row in arr:
                            x1, y1, x2, y2, conf, cls = row
                            cls_id = int(cls)
                            cls_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"

                            # 绘制检测框（更粗、更清晰）
                            cv2.rectangle(annotated_frame,
                                        (int(x1), int(y1)),
                                        (int(x2), int(y2)),
                                        (0, 255, 0), 4)  # 加粗边框到 4px

                            # 绘制标签
                            label = f"{cls_name}: {conf:.2f}"
                            font_scale = 0.8  # 放大字体
                            thickness = 2
                            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

                            cv2.rectangle(annotated_frame,
                                        (int(x1), int(y1) - label_h - 15),
                                        (int(x1) + label_w + 10, int(y1)),
                                        (0, 255, 0), -1)
                            cv2.putText(annotated_frame, label,
                                      (int(x1) + 5, int(y1) - 8),
                                      cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)

                # 输出到队列
                try:
                    self.output_queue.put_nowait(annotated_frame)
                    with self.lock:
                        self.stats['processed'] += 1

                    # 每 30 帧输出统计
                    if self.stats['processed'] % 30 == 0:
                        print(f"✓ 已处理: {self.stats['processed']} 帧 | "
                              f"输入队列: {self.input_queue.qsize()} | "
                              f"输出队列: {self.output_queue.qsize()} | "
                              f"丢帧: {self.stats['dropped']}")
                except:
                    with self.lock:
                        self.stats['dropped'] += 1

            except:
                time.sleep(0.01)

    def start(self):
        """启动处理线程"""
        if not self.running:
            self.running = True
            threading.Thread(target=self.process_worker, daemon=True).start()
            print("✓ 帧处理器已启动")

    def stop(self):
        """停止处理"""
        self.running = False


# 全局处理器
frame_processor = HighQualityFrameProcessor()


# ==================== API 端点 ====================

@app.on_event("startup")
async def startup_event():
    """启动服务"""
    print("\n" + "="*50)
    print("YOLOv5 高质量视频流服务器")
    print("="*50)
    load_model()
    frame_processor.start()
    print("✓ 服务已就绪\n")


@app.post("/upload")
async def upload_frame(data: dict):
    """接收高质量帧"""
    try:
        image_b64 = data.get("image", "")
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)
        image = Image.open(BytesIO(image_bytes))

        if image.mode != "RGB":
            image = image.convert("RGB")

        frame_rgb = np.array(image)
        frame_processor.add_frame(frame_rgb)

        return {"status": "ok"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket 高质量视频流（30 FPS）"""
    await websocket.accept()
    print("✓ 客户端已连接到 WebSocket 流")

    frame_count = 0
    frame_interval = 1.0 / 30  # 30 FPS

    try:
        while True:
            start_time = time.time()

            # 获取处理后的帧
            frame = frame_processor.get_frame()

            if frame is not None:
                # 编码为高质量 JPEG (95%)
                _, jpeg = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                                      [cv2.IMWRITE_JPEG_QUALITY, 95])

                # 发送 base64
                img_b64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
                await websocket.send_json({
                    "frame": img_b64,
                    "frame_count": frame_count,
                    "timestamp": time.time()
                })

                frame_count += 1
                frame_processor.stats['sent'] = frame_count

                if frame_count % 30 == 0:
                    print(f"✓ 已发送: {frame_count} 帧到客户端 (30 FPS)")

            # 控制帧率
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    except Exception as e:
        print(f"WebSocket 断开: {e}")
    finally:
        print("✓ 客户端已断开")


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    return JSONResponse(content=frame_processor.stats)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "buffer": frame_processor.output_queue.qsize()}


if __name__ == "__main__":
    import asyncio
    print("""
    YOLOv5 高质量视频流服务器

    启动命令:
        uvicorn hq_stream_server:app --host 0.0.0.0 --port 8005

    特性:
        ✓ 原始分辨率（无缩放）
        ✓ 高质量 JPEG 95%
        ✓ 每帧完整 YOLO 检测
        ✓ 稳定 30 FPS 输出
        ✓ WebSocket 低延迟传输

    端点:
        POST /upload     - 上传原始帧
        WS   /stream     - WebSocket 视频流
        GET  /stats      - 统计信息
        GET  /health     - 健康检查
    """)
