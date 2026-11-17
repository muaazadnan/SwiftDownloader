"""Local TCP server for receiving downloads from browser extensions."""
import json
import socket
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger("SwiftDownloader.NativeServer")

LISTEN_PORT = 29847


class NativeMessageServer:
    """TCP server that receives download requests from the native messaging host."""

    def __init__(self, on_download_request: Optional[Callable[[str, str], None]] = None):
        self.on_download_request = on_download_request
        self._running = False
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start listening for native messaging connections."""
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the server."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass

    def _listen(self):
        """Main server loop."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(("127.0.0.1", LISTEN_PORT))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)
            logger.info(f"Native message server listening on port {LISTEN_PORT}")

            while self._running:
                try:
                    client, addr = self._server_socket.accept()
                    threading.Thread(
                        target=self._handle_client, args=(client,), daemon=True
                    ).start()
                except socket.timeout:
                    continue
                except OSError:
                    break

        except OSError as e:
            logger.error(f"Server error: {e}")
        finally:
            if self._server_socket:
                self._server_socket.close()

    def _handle_client(self, client: socket.socket):
        """Handle a single client connection."""
        try:
            client.settimeout(5.0)
            data = client.recv(65536)
            if not data:
                return

            msg = json.loads(data.decode("utf-8"))
            if msg.get("action") == "download":
                url = msg.get("url", "")
                filename = msg.get("filename", "")
                if url and self.on_download_request:
                    self.on_download_request(url, filename)
                    response = {"status": "ok", "message": "Download added"}
                else:
                    response = {"status": "error", "message": "Invalid request"}
            else:
                response = {"status": "error", "message": "Unknown action"}

            client.sendall(json.dumps(response).encode("utf-8"))

        except Exception as e:
            logger.error(f"Client handling error: {e}")
        finally:
            client.close()
