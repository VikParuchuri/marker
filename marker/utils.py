import torch
from marker.settings import settings
import os
import requests
import traceback
import time
from typing import Any
import threading
from tracing import get_propagation_headers


def flush_cuda_memory():
    if settings.TORCH_DEVICE_MODEL == "cuda":
        torch.cuda.empty_cache()


def send_callback(callback_url: str, result: Any):
    headers = get_propagation_headers()
    threading.Thread(target=send_callback_inner, args=(callback_url, result, headers)).start()


def send_callback_inner(url: str, result: Any, headers: dict[str, str]):
    # 回调是文档结果入库的唯一通道：连接性/瞬时 5xx 重试，防止 rg 回调端
    # 瞬时 ConnectionReset/重启 导致解析结果丢失（观测：10.25.10.41:5679 曾批量 reset）。
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            print('callback url: ', url, flush=True)
            token = os.getenv("MARKER_PARSE_CALLBACK_TOKEN", "") or ""
            hdrs = dict(headers or {})
            if token:
                hdrs["X-Callback-Token"] = token
            response = requests.post(url, json=result, headers=hdrs, timeout=30)
            # 5xx / 429 视为可重试；2xx/4xx 直接返回
            if 200 <= response.status_code < 300:
                print(f"Callback response status: {response.text}", flush=True)
                return
            if response.status_code not in (429,) and not (500 <= response.status_code < 600):
                print(f"Callback response status: {response.text}", flush=True)
                return
            print(f"Callback attempt {attempt} got HTTP {response.status_code}; retrying...", flush=True)
        except Exception as e:
            if attempt < max_attempts:
                print(f"Callback attempt {attempt} failed: {e}; retrying in {attempt * 2}s", flush=True)
                time.sleep(attempt * 2)
            else:
                traceback.print_exc()
                print(f"Callback failed after {max_attempts} attempts: {e}", flush=True)
    # 至少已打全部失败日志；失败不回抛（回调是尽力而为，不阻塞解析主流程）
