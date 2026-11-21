"""Bidirectional chat connections, handshake and deterministic deduplication."""
import socket
import threading

from .protocol import ProtocolError, recv_frame, send_frame


class ChatConnection:
    def __init__(self, peer_id, sock, direction):
        self.peer_id = peer_id
        self.sock = sock
        self.direction = direction
        self.lock = threading.Lock()
        self.closed = False

    def send(self, frame):
        if self.closed:
            raise ConnectionError("Chat connection already closed")
        send_frame(self.sock, frame, self.lock)

    def close(self, goodbye=False):
        if self.closed:
            return
        self.closed = True
        if goodbye:
            try:
                send_frame(self.sock, {"type": "BYE"}, self.lock)
            except OSError:
                pass
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class ConnectionManager:
    def __init__(self, app):
        self.app = app
        self.lock = threading.RLock()
        self.connections = {}

    def get(self, peer_id):
        with self.lock:
            session = self.connections.get(peer_id)
            return session if session and not session.closed else None

    def _register(self, conn):
        with self.lock:
            existing = self.connections.get(conn.peer_id)
            if existing and not existing.closed:
                # Each side chooses the SAME physical socket if both connected at once.
                preferred = "outgoing" if self.app.identity < conn.peer_id else "incoming"
                if existing.direction == preferred or conn.direction != preferred:
                    conn.close()
                    return False
                self.connections[conn.peer_id] = conn
                existing.close()
            else:
                self.connections[conn.peer_id] = conn
        return True

    def _on_disconnect(self, conn):
        removed = False
        with self.lock:
            if self.connections.get(conn.peer_id) is conn:
                self.connections.pop(conn.peer_id, None)
                removed = True
        conn.close()
        if removed and self.app.chats.reset_if_current(conn.peer_id):
            p = self.app.peers.get(conn.peer_id)
            self.app.notice(f"[*] Disconnected from {p.name if p else conn.peer_id}. Returned to the main prompt.")

    def _read_loop(self, conn):
        try:
            while not self.app.stop_event.is_set():
                frame = recv_frame(conn.sock)
                if frame["type"] == "BYE":
                    break
                if frame["type"] == "MSG":
                    text = frame.get("text")
                    if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
                        raise ProtocolError("Invalid message text")
                    peer = self.app.peers.get(conn.peer_id)
                    name = peer.name if peer else conn.peer_id[:8]
                    active, count = self.app.chats.receive(conn.peer_id, name, text)
                    if active:
                        self.app.notice(f"[{name}] {text}")
                    else:
                        self.app.notice(f"[*] New message from {name} ({count} unread)")
                else:
                    raise ProtocolError("Unexpected chat frame")
        except (EOFError, OSError, ProtocolError) as exc:
            if not self.app.stop_event.is_set() and self.get(conn.peer_id) is conn:
                self.app.notice(f"[!] Chat connection lost: {exc}")
        finally:
            self._on_disconnect(conn)

    def accept(self, sock, hello, addr):
        peer_id = hello["id"]
        conn = ChatConnection(peer_id, sock, "incoming")
        if self._register(conn):
            self._read_loop(conn)  # already on TCP accept worker

    def connect(self, peer):
        old = self.get(peer.peer_id)
        if old:
            return old
        sock = socket.create_connection((peer.ip, peer.port), timeout=4)
        try:
            sock.settimeout(5)
            send_frame(sock, self.app.hello("chat"))
            response = recv_frame(sock)
            self.app.validate_hello(response, expected_id=peer.peer_id, kind="chat")
            sock.settimeout(None)
            conn = ChatConnection(peer.peer_id, sock, "outgoing")
            if self._register(conn):
                threading.Thread(target=self._read_loop, args=(conn,), daemon=True).start()
                return conn
            return self.get(peer.peer_id) or self.connect(peer)
        except Exception:
            sock.close()
            raise

    def send_message(self, peer_id, text):
        conn = self.get(peer_id)
        if not conn:
            peer = self.app.peers.get(peer_id)
            if not peer:
                raise ConnectionError("Peer is offline")
            conn = self.connect(peer)
        conn.send({"type": "MSG", "text": text})

    def close_peer(self, peer_id):
        conn = self.get(peer_id)
        if conn:
            # Graceful application-layer close; avoid a stray error on the peer.
            try:
                conn.send({"type": "BYE"})
            except OSError:
                pass
            self._on_disconnect(conn)

    def stop(self):
        with self.lock:
            sessions = list(self.connections.values())
            self.connections.clear()
        for session in sessions:
            session.close()
