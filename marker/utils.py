import torch
from marker.settings import settings
import requests
import traceback
from typing import Any
import threading


def flush_cuda_memory():
    if settings.TORCH_DEVICE_MODEL == "cuda":
        torch.cuda.empty_cache()


def send_callback(callback_url: str, result: Any):
    threading.Thread(target=send_callback_inner, args=(callback_url, result)).start()


def send_callback_inner(url: str, result: Any):
    try:
        print('callback url: ', url, flush=True)
        response = requests.post(url, json=result)
        print(f"Callback response status: {response.text}", flush=True)
    except Exception as e:
        traceback.print_exc()
        print(f"Callback failed: {e}", flush=True)
