import argparse
import json
import socket
import tempfile
from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models

configure_logging()

def receive_file_from_socket(sock, buffer_size=1024):
    """Receive file data from the socket and write it to a temporary file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        file_name = temp_file.name
        while True:
            data = sock.recv(buffer_size)
            if not data:
                break  # No more data, transfer is complete.
            temp_file.write(data)
    return file_name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Host to listen on")
    parser.add_argument("port", type=int, help="Port to listen on")
    parser.add_argument("output", help="Output file name")
    parser.add_argument("--max_pages", type=int, default=None, help="Maximum number of pages to parse")
    parser.add_argument("--parallel_factor", type=int, default=1, help="How much to multiply default parallel OCR workers and model batch sizes by.")
    args = parser.parse_args()

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to the address given on the command line
    server_address = (args.host, args.port)
    sock.bind(server_address)
    sock.listen(1)

    print(f"Listening for incoming connections on {args.host}:{args.port}")

    while True:
        print("Waiting for a connection")
        connection, client_address = sock.accept()
        try:
            print("Connection from", client_address)

            # Receive the file over the socket
            fname = receive_file_from_socket(connection)

            # Load models and convert PDF
            model_lst = load_all_models()
            full_text, out_meta = convert_single_pdf(fname, model_lst, max_pages=args.max_pages, parallel_factor=args.parallel_factor)

            with open(args.output, "w+", encoding='utf-8') as f:
                f.write(full_text)

            out_meta_filename = args.output.rsplit(".", 1)[0] + "_meta.json"
            with open(out_meta_filename, "w+") as f:
                f.write(json.dumps(out_meta, indent=4))

        finally:
            # Clean up the connection
            connection.close()

if __name__ == "__main__":
    main()
