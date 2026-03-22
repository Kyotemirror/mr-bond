import json
import os
import socket
import threading

# Unix domain socket path (local only, fast, safe)
SOCK_PATH = "/tmp/bond.sock"


class BondIPCServer:
    """
    Simple IPC server for Bond Core.

    - Listens on a Unix domain socket
    - Receives newline-delimited JSON messages
    - Passes parsed messages to a handler callback
    """

    def __init__(self, handler):
        """
        handler: callable(dict) -> None
        """
        self.handler = handler
        self._stop_event = threading.Event()
        self._server = None
        self._thread = None

    # -----------------------------
    # Start server
    # -----------------------------
    def start(self):
        # Remove stale socket file if it exists
        try:
            if os.path.exists(SOCK_PATH):
                os.remove(SOCK_PATH)
        except Exception:
            pass

        # Create Unix domain socket
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(SOCK_PATH)
        self._server.listen(5)

        # Restrict socket access to current user
        try:
            os.chmod(SOCK_PATH, 0o600)
        except Exception:
            pass

        # Run server loop in background thread
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self._thread.start()

    # -----------------------------
    # Stop server
    # -----------------------------
    def stop(self):
        self._stop_event.set()

        try:
            if self._server:
                self._server.close()
        except Exception:
            pass

        try:
            if os.path.exists(SOCK_PATH):
                os.remove(SOCK_PATH)
        except Exception:
            pass

    # -----------------------------
    # Main accept loop
    # -----------------------------
    def _loop(self):
        while not self._stop_event.is_set():
            try:
                conn, _ = self._server.accept()
            except Exception:
                continue

            try:
                buffer = b""

                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buffer += data

                # Process newline-delimited JSON
                for line in buffer.split(b"\n"):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self.handler(msg)
                    except Exception:
                        # Ignore malformed messages
                        pass

            finally:
                try:
                    conn.close()
                except Exception:
                    pass
