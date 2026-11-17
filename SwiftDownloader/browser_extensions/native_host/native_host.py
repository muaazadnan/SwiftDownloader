#!/usr/bin/env python3
"""
SwiftDownloader Native Messaging Host.
Receives download requests from browser extensions and forwards them
to the running SwiftDownloader instance via a local socket.
"""
import sys
import json
import struct
import socket
import logging
from pathlib import Path

LOG_DIR = Path.home() / "AppData" / "Local" / "SwiftDownloader"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "native_host.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

SOCKET_PORT = 29847  # Local TCP port for communication with SwiftDownloader


def read_message():
    """Read a message from stdin (Chrome native messaging protocol)."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None
    length = struct.unpack("=I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode("utf-8"))


def send_message(msg):
    """Send a message to stdout (Chrome native messaging protocol)."""
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def forward_to_app(msg):
    """Forward a download request to the SwiftDownloader app via TCP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(("127.0.0.1", SOCKET_PORT))
            s.sendall(json.dumps(msg).encode("utf-8"))
            response = s.recv(4096)
            return json.loads(response.decode("utf-8"))
    except (ConnectionRefusedError, socket.timeout):
        logging.warning("SwiftDownloader app not running or not responding")
        return {"status": "error", "message": "SwiftDownloader is not running"}
    except Exception as e:
        logging.error(f"Failed to communicate with SwiftDownloader: {e}")
        return {"status": "error", "message": str(e)}


def main():
    """Main loop — read messages from browser and forward to app."""
    logging.info("Native messaging host started")
    while True:
        msg = read_message()
        if msg is None:
            break
        logging.info(f"Received: {msg}")

        if msg.get("action") == "download":
            result = forward_to_app(msg)
            send_message(result)
        elif msg.get("action") == "ping":
            send_message({"status": "ok", "app": "SwiftDownloader"})
        else:
            send_message({"status": "error", "message": "Unknown action"})

    logging.info("Native messaging host stopped")


if __name__ == "__main__":
    main()
