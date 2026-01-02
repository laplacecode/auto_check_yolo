#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YOLOv5 实时检测 WebRTC 后端服务器

提供基于 WebRTC 的视频流接收和 YOLOv5 目标检测功能
"""
import asyncio
import base64
import json
import os
import threading
from io import BytesIO

import numpy as np
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image

# ==================== 应用配置 ====================
app = FastAPI(title="YOLOv5 WebRTC 检测服务", version="1.0.0")

# 启用 CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebRTC 连接池
pcs = set()

# WebSocket 连接管理
websocket_clients = set()

# ==================== 模型管理 ====================
# 模型路径（从环境变量读取，默认为 models/yolov5s.pt）
MODEL_PATH = os.environ.get("MODEL_PATH", "../models/yolov5s.pt")
_model = None
_model_lock = threading.Lock()


def load_model():
    """
    加载 YOLOv5 模型（线程安全）

    尝试顺序：
    1. 从 MODEL_PATH 加载 ultralytics YOLO 模型
    2. 使用 torch.hub 加载预训练的 yolov5s

    Returns:
        object: 加载成功的模型对象，失败返回 None
    """
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        print(f"正在加载模型: {MODEL_PATH}")

        # 尝试使用 ultralytics 加载
        try:
            from ultralytics import YOLO as ULTRA_YOLO
            if os.path.exists(MODEL_PATH):
                _model = ULTRA_YOLO(MODEL_PATH)
                print("模型加载成功")
            else:
                print(f"警告: 模型文件不存在 - {MODEL_PATH}")
                _model = None
        except Exception as e:
            print(f"ultralytics 加载失败: {e}")
            _model = None

        # 如果 ultralytics 失败，尝试 torch.hub
        if _model is None:
            try:
                import torch
                _model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
                print("通过 torch.hub 加载模型成功")
            except Exception as e:
                print(f"torch.hub 加载失败: {e}")
                _model = None

        return _model


def run_detection(frame_array):
    """
    在视频帧上运行 YOLO 检测

    Args:
        frame_array (numpy.ndarray): numpy 数组格式的视频帧 (RGB)

    Returns:
        dict: 包含检测结果的字典，包含以下键：
            - detections (list): 检测框列表 [{x, y, w, h, cls, conf}, ...]
            - w (int): 图像宽度
            - h (int): 图像高度
            - note (str, 可选): 注释信息（如 fallback）
            - error (str, 可选): 错误信息
    """
    model = load_model()

    # 获取图像尺寸
    img = Image.fromarray(frame_array)
    w, h = img.size

    # 模型未加载时的降级处理
    if model is None:
        return {
            "detections": [{
                "x": 50,
                "y": 50,
                "w": 200,
                "h": 150,
                "cls": "defect",
                "conf": 0.9
            }],
            "w": w,
            "h": h,
            "note": "fallback"
        }

    # 执行检测
    try:
        results = model(frame_array)
        detections = []

        # 解析检测结果
        r0 = results[0]
        if hasattr(r0, 'boxes'):
            data_arr = getattr(r0, 'boxes').data
            # 转换为 numpy 数组
            if hasattr(data_arr, 'cpu'):
                arr = data_arr.cpu().numpy()
            else:
                arr = np.array(data_arr)

            # 提取每个检测框的信息
            for row in arr:
                x1, y1, x2, y2, conf, cls = row
                detections.append({
                    "x": int(x1),
                    "y": int(y1),
                    "w": int(x2 - x1),
                    "h": int(y2 - y1),
                    "cls": str(int(cls)),
                    "conf": float(conf),
                })

        return {"detections": detections, "w": w, "h": h}

    except Exception as e:
        print(f"检测失败: {e}")
        return {"detections": [], "w": w, "h": h, "error": str(e)}


# ==================== WebRTC 端点 ====================

@app.post("/offer")
async def offer(request: Request):
    """
    处理 WebRTC 信令 offer

    接收客户端的 SDP offer，建立 WebRTC 连接，
    并返回服务端的 SDP answer

    Args:
        request (Request): FastAPI 请求对象

    Returns:
        JSONResponse: 包含 SDP answer 的响应
    """
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # 创建对等连接（添加 STUN 服务器配置）
    configuration = RTCConfiguration(
        iceServers=[
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]
    )
    pc = RTCPeerConnection(configuration=configuration)
    pcs.add(pc)
    print("已创建 RTCPeerConnection，配置了 STUN 服务器")

    # 在服务端创建数据通道（用于发送检测结果）
    data_channel = pc.createDataChannel("detections")
    print(f"已创建数据通道: {data_channel.label}")

    frame_count = [0]
    message_queue = []
    queue_flushed = [False]

    def try_flush_queue():
        """尝试刷新消息队列"""
        if queue_flushed[0]:
            return
        if data_channel and data_channel.readyState == "open" and len(message_queue) > 0:
            print(f"数据通道已打开，开始发送缓存的 {len(message_queue)} 条消息")
            queue_flushed[0] = True
            while message_queue:
                msg = message_queue.pop(0)
                try:
                    data_channel.send(msg)
                except Exception as e:
                    print(f"发送缓存消息失败: {e}")
            print("队列刷新完成")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        """连接状态变化处理"""
        print(f"连接状态变化: {pc.connectionState}")
        if pc.connectionState == "connected":
            print(f"ICE 连接已建立，数据通道状态: {data_channel.readyState}")

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        """ICE 连接状态变化处理"""
        print(f"ICE 连接状态: {pc.iceConnectionState}")

    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange():
        """ICE 收集状态变化处理"""
        print(f"ICE 收集状态: {pc.iceGatheringState}")

    @pc.on("track")
    def on_track(track):
        """
        处理接收到的媒体轨道（视频流）

        Args:
            track: WebRTC 媒体轨道对象
        """
        print(f"收到 {track.kind} 轨道")

        async def run_track():
            """异步处理视频帧"""
            try:
                while True:
                    # 接收视频帧
                    frame = await track.recv()
                    frame_count[0] += 1

                    # 每 5 帧处理一次（性能优化）
                    if frame_count[0] % 5 == 0:
                        # 转换为 numpy 数组
                        frame_array = frame.to_ndarray(format="rgb24")

                        # 在线程池中运行检测（避免阻塞）
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, run_detection, frame_array)
                        result["frame"] = frame_count[0]

                        # 通过 WebSocket 广播检测结果
                        await broadcast_detection_result(result)

                        # 通过数据通道发送结果（备用）
                        if data_channel:
                            message = json.dumps(result)
                            try_flush_queue()

                            if data_channel.readyState == "open":
                                try:
                                    data_channel.send(message)
                                    det_count = len(result.get('detections', []))
                                    print(f"帧 {frame_count[0]}: 通过数据通道发送 {det_count} 个检测结果")
                                except Exception as e:
                                    print(f"数据通道发送失败: {e}")
                            else:
                                # 数据通道未打开，将消息加入队列
                                message_queue.append(message)
                                if frame_count[0] % 25 == 0:
                                    print(f"数据通道状态: {data_channel.readyState}，队列长度: {len(message_queue)}")

            except Exception as e:
                print(f"轨道处理错误: {e}")

        asyncio.ensure_future(run_track())

    # 设置远程描述并创建应答
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JSONResponse(content={
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })


@app.post("/detect")
async def detect_image(request: Request):
    """
    检测单张图像

    Args:
        request (Request): FastAPI 请求对象，包含 JSON 数据：
            - image (str): base64 编码的图像数据
            - format (str, 可选): 图像格式（png 或 jpg）

    Returns:
        JSONResponse: 包含检测结果的响应：
            - detections (list): 检测框列表
            - w (int): 图像宽度
            - h (int): 图像高度
            - error (str, 可选): 错误信息
    """
    try:
        data = await request.json()
        image_b64 = data.get("image", "")

        # 解码 base64 图像
        if "," in image_b64:
            # 移除 data:image/png;base64, 前缀
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)
        image = Image.open(BytesIO(image_bytes))

        # 转换为 RGB numpy 数组
        if image.mode != "RGB":
            image = image.convert("RGB")
        frame_array = np.array(image)

        # 运行检测
        result = run_detection(frame_array)

        return JSONResponse(content=result)

    except Exception as e:
        print(f"图像检测失败: {e}")
        return JSONResponse(
            content={"error": str(e), "detections": [], "w": 0, "h": 0},
            status_code=400
        )


@app.get("/health")
async def health():
    """
    健康检查端点

    Returns:
        dict: 状态信息
    """
    return {"status": "ok"}


@app.on_event("shutdown")
async def on_shutdown():
    """应用关闭时清理资源"""
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


# ==================== WebSocket 端点 ====================

async def broadcast_detection_result(result):
    """
    通过 WebSocket 广播检测结果到所有客户端

    Args:
        result (dict): 检测结果字典
    """
    if not websocket_clients:
        return

    message = json.dumps(result)
    disconnected = set()

    for client in websocket_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            print(f"WebSocket 发送失败: {e}")
            disconnected.add(client)

    # 移除断开的客户端
    for client in disconnected:
        websocket_clients.discard(client)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 连接端点，用于推送检测结果

    Args:
        websocket (WebSocket): WebSocket 连接对象
    """
    await websocket.accept()
    websocket_clients.add(websocket)
    print(f"WebSocket 客户端已连接，当前连接数: {len(websocket_clients)}")

    try:
        # 保持连接并处理客户端消息
        while True:
            data = await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket 连接断开: {e}")
    finally:
        websocket_clients.discard(websocket)
        print(f"WebSocket 客户端已断开，当前连接数: {len(websocket_clients)}")


# ==================== 启动说明 ====================
if __name__ == "__main__":
    print("""
    YOLOv5 WebRTC 检测服务器

    启动命令:
        uvicorn server:app --host 0.0.0.0 --port 8002

    环境变量:
        MODEL_PATH - YOLOv5 模型路径（默认: yolov5s.pt）

    端点:
        POST /offer  - WebRTC 信令
        POST /detect - 单张图像检测
        GET  /health - 健康检查
        WS   /ws     - WebSocket 检测结果推送
    """)
