"""Presence announcements over UDP broadcast."""
import json
import socket
import threading

UDP_PORT = 9999


class Discovery:
    def __init__(self, identity, name, port, status, peers, notify, broadcast, stop_event):
        self.identity = identity
        self.name = name
        self.port = port
        self.status = status
        self.peers = peers
        self.notify = notify
        self.broadcast = broadcast
        self.stop_event = stop_event
        self.sock = None
        self.threads = []

    def start(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        try:
            listener.bind(("", UDP_PORT))
        except OSError:
            listener.close()
            raise
        listener.settimeout(1)
        self.sock = listener
        for fn in (self._listen, self._broadcast):
            thread = threading.Thread(target=fn, daemon=True)
            thread.start()
            self.threads.append(thread)

    def _broadcast(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self.stop_event.is_set():
                payload = {"type": "HELLO", "id": self.identity, "name": self.name,
                           "port": self.port, "status": self.status()}
                try:
                    sock.sendto(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                (self.broadcast, UDP_PORT))
                except OSError as exc:
                    self.notify(f"[!] Failed to send UDP broadcast: {exc}")
                self.stop_event.wait(3)

    def _listen(self):
        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
                obj = json.loads(data.decode("utf-8"))
                if not isinstance(obj, dict) or obj.get("type") != "HELLO":
                    continue
                if obj.get("id") == self.identity:
                    continue
                self.peers.observe(obj.get("id"), obj.get("name"), addr[0],
                                   obj.get("port"), obj.get("status"))
            except socket.timeout:
                pass
            except (ValueError, UnicodeError, TypeError):
                pass  # Malformed untrusted datagram: discard.
            except OSError:
                if self.stop_event.is_set():
                    break
            self.peers.expire()

    def stop(self):
        if self.sock:
            self.sock.close()
        for thread in self.threads:
            thread.join(timeout=1.5)
