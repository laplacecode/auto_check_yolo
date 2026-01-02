#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 UDP 检测服务器（超低延迟版本）

使用 UDP 协议降低网络延迟，适合实时检测场景
"""
import base64
import json
import os
import socket
import threading
from io import BytesIO

import numpy as np
from PIL import Image

# ==================== 模型管理 ====================
MODEL_PATH = os.environ.get("MODEL_PATH", "../models/yolov5s.pt")
_model = None
_model_lock = threading.Lock()

# COCO 数据集类别名称
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
                print("模型加载成功（ultralytics）")
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
                print("模型加载成功（torch.hub）")
            except Exception as e:
                print(f"torch.hub 加载失败: {e}")
                _model = None

        return _model


def run_detection(frame_array):
    """运行 YOLO 检测"""
    model = load_model()

    img = Image.fromarray(frame_array)
    w, h = img.size

    if model is None:
        return {"detections": [], "w": w, "h": h}

    try:
        results = model(frame_array)
        detections = []

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
                detections.append({
                    "x": int(x1),
                    "y": int(y1),
                    "w": int(x2 - x1),
                    "h": int(y2 - y1),
                    "cls": cls_name,
                    "cls_id": cls_id,
                    "conf": float(conf),
                })

        return {"detections": detections, "w": w, "h": h}

    except Exception as e:
        print(f"检测失败: {e}")
        return {"detections": [], "w": w, "h": h, "error": str(e)}


def start_udp_server(host='0.0.0.0', port=8003):
    """启动 UDP 服务器"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))

    # 设置接收缓冲区大小（允许较大的图像数据）
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536 * 16)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536 * 4)

    print(f"UDP 检测服务器运行在 {host}:{port}")
    print("等待客户端连接...")

    frame_count = 0

    while True:
        try:
            # 接收数据（最大 64KB）
            data, addr = sock.recvfrom(65536)
            frame_count += 1

            # 解析 JSON 数据
            request = json.loads(data.decode('utf-8'))
            image_b64 = request.get("image", "")

            # 解码图像
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]

            image_bytes = base64.b64decode(image_b64)
            image = Image.open(BytesIO(image_bytes))

            if image.mode != "RGB":
                image = image.convert("RGB")
            frame_array = np.array(image)

            # 运行检测
            result = run_detection(frame_array)

            # 发送结果回客户端
            response = json.dumps(result).encode('utf-8')

            # UDP 有大小限制，如果结果太大需要分片
            if len(response) < 65000:
                sock.sendto(response, addr)
                if frame_count % 10 == 0:
                    det_count = len(result.get('detections', []))
                    print(f"帧 {frame_count}: 检测到 {det_count} 个对象，发送到 {addr}")
            else:
                # 结果太大，只发送检测数量
                simple_result = {"detections": [], "w": result["w"], "h": result["h"], "count": len(result["detections"])}
                sock.sendto(json.dumps(simple_result).encode('utf-8'), addr)
                print(f"警告: 结果太大，已简化")

        except Exception as e:
            print(f"处理请求错误: {e}")
            # 发送错误响应
            try:
                error_response = json.dumps({"detections": [], "w": 0, "h": 0, "error": str(e)}).encode('utf-8')
                sock.sendto(error_response, addr)
            except:
                pass


if __name__ == "__main__":
    print("""
    YOLOv5 UDP 检测服务器（超低延迟版本）

    启动命令:
        python udp_server.py

    环境变量:
        MODEL_PATH - YOLOv5 模型路径（默认: ../models/yolov5s.pt）

    优势:
        - UDP 协议，无需 TCP 握手
        - 零延迟连接建立
        - 适合实时检测场景
    """)

    start_udp_server()
