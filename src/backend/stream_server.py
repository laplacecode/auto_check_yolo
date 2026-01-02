#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 视频流检测服务器

接收前端视频流 -> 缓存帧 -> YOLO 检测 -> 返回带标注的 30 FPS 视频流
"""
import base64
import os
import threading
import time
from collections import deque
from io import BytesIO

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image

# ==================== 应用配置 ====================
app = FastAPI(title="YOLOv5 流式检测服务", version="2.0.0")

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
                print("模型加载成功")
            else:
                print(f"警告: 模型文件不存在 - {MODEL_PATH}")
                _model = None
        except Exception as e:
            print(f"ultralytics 加载失败: {e}")
            _model = None

        if _model is None:
            try:
                import torch
                _model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
                print("通过 torch.hub 加载模型成功")
            except Exception as e:
                print(f"torch.hub 加载失败: {e}")
                _model = None

        return _model


# ==================== 视频流缓冲系统 ====================
class VideoStreamBuffer:
    """视频流缓冲队列"""

    def __init__(self, max_size=60):  # 缓存 60 帧（2 秒 @ 30fps）
        self.input_queue = deque(maxlen=max_size)  # 输入帧队列
        self.output_queue = deque(maxlen=max_size)  # 输出帧队列（带检测标注）
        self.lock = threading.Lock()
        self.running = False
        self.frame_count = 0
        self.last_frame = None  # 保存最后一帧用于填充

    def add_frame(self, frame):
        """添加原始帧到输入队列"""
        with self.lock:
            self.input_queue.append(frame)
            self.frame_count += 1

    def get_processed_frame(self):
        """获取处理后的帧（如果队列为空，返回最后一帧）"""
        with self.lock:
            if len(self.output_queue) > 0:
                return self.output_queue.popleft()
            # 返回最后一帧避免黑屏
            return self.last_frame

    def process_frames(self):
        """后台处理线程：YOLO 检测并标注"""
        model = load_model()
        processed_count = 0

        while self.running:
            # 从输入队列获取帧
            frame = None
            with self.lock:
                if len(self.input_queue) > 0:
                    frame = self.input_queue.popleft()

            if frame is None:
                time.sleep(0.01)  # 等待新帧
                continue

            try:
                # YOLO 检测
                results = model(frame) if model else None

                # 绘制检测框
                annotated_frame = frame.copy()

                if results:
                    r0 = results[0]
                    if hasattr(r0, 'boxes'):
                        data_arr = r0.boxes.data
                        if hasattr(data_arr, 'cpu'):
                            arr = data_arr.cpu().numpy()
                        else:
                            arr = np.array(data_arr)

                        for row in arr:
                            x1, y1, x2, y2, conf, cls = row
                            cls_id = int(cls)
                            cls_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"

                            # 绘制边框
                            cv2.rectangle(annotated_frame,
                                        (int(x1), int(y1)),
                                        (int(x2), int(y2)),
                                        (0, 255, 0), 3)

                            # 绘制标签
                            label = f"{cls_name}: {conf:.2f}"
                            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                            cv2.rectangle(annotated_frame,
                                        (int(x1), int(y1) - label_h - 10),
                                        (int(x1) + label_w, int(y1)),
                                        (0, 255, 0), -1)
                            cv2.putText(annotated_frame, label,
                                      (int(x1), int(y1) - 5),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                # 添加到输出队列
                with self.lock:
                    self.output_queue.append(annotated_frame)
                    self.last_frame = annotated_frame  # 保存用于填充
                    processed_count += 1
                    if processed_count % 30 == 0:
                        print(f"已处理 {processed_count} 帧，输入队列: {len(self.input_queue)}, 输出队列: {len(self.output_queue)}")

            except Exception as e:
                print(f"帧处理错误: {e}")
                # 错误时直接输出原始帧
                with self.lock:
                    self.output_queue.append(frame)

    def start(self):
        """启动处理线程"""
        if not self.running:
            self.running = True
            threading.Thread(target=self.process_frames, daemon=True).start()
            print("视频流处理线程已启动")

    def stop(self):
        """停止处理"""
        self.running = False


# 全局缓冲区
video_buffer = VideoStreamBuffer()


# ==================== API 端点 ====================

@app.on_event("startup")
async def startup_event():
    """启动时加载模型和启动处理线程"""
    print("正在启动服务...")
    load_model()
    video_buffer.start()
    print("服务已就绪")


@app.post("/upload_frame")
async def upload_frame(data: dict):
    """
    接收前端上传的视频帧

    POST /upload_frame
    Body: {"image": "base64_encoded_image"}
    """
    try:
        image_b64 = data.get("image", "")

        # 解码图像
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)
        image = Image.open(BytesIO(image_bytes))

        if image.mode != "RGB":
            image = image.convert("RGB")

        # 转换为 numpy 数组（RGB）
        frame = np.array(image)

        # 添加到缓冲队列
        video_buffer.add_frame(frame)

        return {"status": "ok", "queue_size": len(video_buffer.input_queue)}

    except Exception as e:
        print(f"上传帧失败: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/video_stream")
async def video_stream():
    """
    返回 MJPEG 视频流（30 FPS）

    GET /video_stream
    返回: multipart/x-mixed-replace 视频流
    """
    def generate():
        """生成视频流"""
        print("客户端已连接到视频流")
        frame_interval = 1.0 / 30  # 30 FPS
        frame_count = 0

        while True:
            start_time = time.time()

            # 获取处理后的帧
            frame = video_buffer.get_processed_frame()

            if frame is not None:
                try:
                    # 转换为 JPEG
                    _, jpeg = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                                          [cv2.IMWRITE_JPEG_QUALITY, 85])

                    # 生成 MJPEG 帧
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

                    frame_count += 1
                    if frame_count % 30 == 0:
                        print(f"已发送 {frame_count} 帧到客户端")
                except Exception as e:
                    print(f"编码帧错误: {e}")
            else:
                # 没有帧时发送占位图像
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "Waiting for frames...", (150, 240),
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                _, jpeg = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

            # 控制帧率
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            time.sleep(sleep_time)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "input_queue": len(video_buffer.input_queue),
        "output_queue": len(video_buffer.output_queue),
        "total_frames": video_buffer.frame_count
    }


if __name__ == "__main__":
    print("""
    YOLOv5 视频流检测服务器

    启动命令:
        uvicorn stream_server:app --host 0.0.0.0 --port 8004

    端点:
        POST /upload_frame  - 上传视频帧
        GET  /video_stream  - 获取 MJPEG 视频流（30 FPS）
        GET  /health        - 健康检查

    工作流程:
        前端 -> POST 帧 -> 缓冲队列 -> YOLO 检测 -> 输出队列 -> MJPEG 流 -> 前端显示
    """)
