import argparse
import os
import socket
import tempfile
from typing import Dict, Optional
import math
import ray
from tqdm import tqdm
import json
from marker.convert import convert_single_pdf, get_length_of_text
from marker.models import load_all_models
from marker.settings import settings
from marker.logger import configure_logging
import traceback

configure_logging()

def receive_file_from_socket(sock, buffer_size=4096):
    """Receive file data from the socket and write it to a temporary file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        while True:
            data = sock.recv(buffer_size)
            if not data:
                break  # No more data, transfer is complete.
            temp_file.write(data)
    return temp_file.name

@ray.remote(num_cpus=settings.RAY_CORES_PER_WORKER, num_gpus=.05 if settings.CUDA else 0)
def process_single_pdf(fname: str, out_folder: str, model_refs, metadata: Optional[Dict] = None, min_length: Optional[int] = None):
    out_filename = fname.rsplit(".", 1)[0] + ".md"
    out_filename = os.path.join(out_folder, os.path.basename(out_filename))
    out_meta_filename = out_filename.rsplit(".", 1)[0] + "_meta.json"
    if os.path.exists(out_filename):
        return
    try:
        # Skip trying to convert files that don't have a lot of embedded text
        # This can indicate that they were scanned, and not OCRed properly
        # Usually these files are not recent/high-quality
        if min_length:
            length = get_length_of_text(fname)
            if length < min_length:
                return

        full_text, out_metadata = convert_single_pdf(fname, model_refs, metadata=metadata)
        if len(full_text.strip()) > 0:
            with open(out_filename, "w+", encoding='utf-8') as f:
                f.write(full_text)
            with open(out_meta_filename, "w+") as f:
                f.write(json.dumps(out_metadata, indent=4))
        else:
            print(f"Empty file: {fname}.  Could not convert.")
    except Exception as e:
        print(f"Error converting {fname}: {e}")
        print(traceback.format_exc())

def start_socket_server(host, port, out_folder, workers, metadata: Optional[Dict] = None, min_length: Optional[int] = None):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Socket server listening on {host}:{port}")

    model_lst = load_all_models()
    model_refs = ray.put(model_lst)

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Received connection from {addr}")

            fname = receive_file_from_socket(client_socket)
            client_socket.close()

            # Here, immediately queue the file for processing. In a production,
            # you might want to implement some form of rate limiting or queue management!! 😘
            process_single_pdf.remote(
                fname, out_folder, model_refs,
                metadata=metadata, min_length=min_length
            )

    finally:
        server_socket.close()

def main():
    parser = argparse.ArgumentParser(description="Convert received pdfs to markdown over a socket connection.")
    parser.add_argument("host", help="Host to listen on")
    parser.add_argument("port", type=int, help="Port to listen on")
    parser.add_argument("out_folder", help="Output folder")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker processes to use")
    parser.add_argument("--metadata_file", type=str, default=None, help="Metadata json file to use for filtering")
    parser.add_argument("--min_length", type=int, default=None, help="Minimum length of pdf to convert")