"""Orchestrates UDP discovery, TCP chat and file worker threads."""
import socket
import threading
import uuid

from .connections import ConnectionManager
from .discovery import Discovery
from .peers import ChatStore, PeerStore
from .protocol import ProtocolError, recv_frame, send_frame
from .transfer import TransferManager


class LanChatApp:
    def __init__(self, name, port=5000, broadcast="255.255.255.255", notify=print,
                 downloads="downloads", event_sink=None):
        if not name or len(name) > 60:
            raise ValueError("Display name must be between 1 and 60 characters")
        self.identity = uuid.uuid4().hex
        self.name = name
        self.port = port
        self.broadcast = broadcast
        self.notice = notify
        self.event_sink = event_sink
        self.stop_event = threading.Event()
        self.status_lock = threading.Lock()
        self._status = "online"
        self.peers = PeerStore(notify)
        self.chats = ChatStore()
        self.connections = ConnectionManager(self)
        self.transfers = TransferManager(self, downloads)
        self.listener = None
        self.discovery = None
        self.accept_thread = None
        self.workers = set()
        self.workers_lock = threading.Lock()

    def emit(self, event_type, **data):
        if self.event_sink is not None:
            self.event_sink({"type": event_type, **data})

    def get_status(self):
        with self.status_lock:
            return self._status

    def set_status(self, status):
        if status not in ("online", "away"):
            raise ValueError("Status must be online or away")
        with self.status_lock:
            self._status = status
        self.notice(f"[*] Status: {status}")

    def hello(self, kind):
        return {"type": "HELLO", "version": 1, "id": self.identity,
                "name": self.name, "port": self.port, "kind": kind}

    @staticmethod
    def validate_hello(value, expected_id=None, kind=None):
        if (value.get("type") != "HELLO" or value.get("version") != 1
                or value.get("kind") not in ("chat", "file")
                or not isinstance(value.get("id"), str) or not 1 <= len(value["id"]) <= 80
                or not isinstance(value.get("name"), str) or not 1 <= len(value["name"]) <= 60
                or not isinstance(value.get("port"), int)
                or isinstance(value.get("port"), bool) or not 1 <= value["port"] <= 65535):
            raise ProtocolError("Invalid HELLO handshake")
        if expected_id is not None and value["id"] != expected_id:
            raise ProtocolError("Peer ID does not match discovery")
        if kind is not None and value["kind"] != kind:
            raise ProtocolError("Unexpected TCP connection type")

    def start(self):
        if self.listener:
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("", self.port))
            server.listen(16)
            server.settimeout(1)
            self.port = server.getsockname()[1]
            self.listener = server
            self.discovery = Discovery(self.identity, self.name, self.port, self.get_status,
                                       self.peers, self.notice, self.broadcast, self.stop_event)
            self.discovery.start()
            self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.accept_thread.start()
        except Exception:
            server.close()
            self.stop()
            raise
        self.notice(f"[*] {self.name}: TCP {self.port}, UDP 9999, broadcast {self.broadcast}")

    def _accept_loop(self):
        while not self.stop_event.is_set():
            try:
                conn, addr = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(target=self._incoming, args=(conn, addr), daemon=True)
            with self.workers_lock:
                self.workers.add(thread)
            thread.start()

    def _incoming(self, sock, addr):
        owned = True
        try:
            sock.settimeout(6)
            hello = recv_frame(sock)
            self.validate_hello(hello)
            if hello["id"] == self.identity:
                raise ProtocolError("Cannot connect to yourself")
            known = self.peers.get(hello["id"])
            status = known.status if known else "online"
            self.peers.observe(hello["id"], hello["name"], addr[0], hello["port"], status)
            send_frame(sock, self.hello(hello["kind"]))
            sock.settimeout(None)
            if hello["kind"] == "chat":
                owned = False
                self.connections.accept(sock, hello, addr)
            else:
                owned = False
                self.transfers.receive_file(sock, hello)
        except (OSError, EOFError, ProtocolError) as exc:
            if not self.stop_event.is_set():
                self.notice(f"[!] Invalid TCP connection from {addr[0]}: {exc}")
        finally:
            if owned:
                sock.close()
            with self.workers_lock:
                self.workers.discard(threading.current_thread())

    def select_chat(self, peer):
        self.connections.connect(peer)
        unseen = self.chats.select(peer.peer_id)
        self.notice(f"[*] Chatting with {peer.name} ({peer.ip}:{peer.port})")
        if unseen:
            self.notice(f"[*] {len(unseen)} unread message(s):")
            for name, msg in unseen:
                self.notice(f"[{name}] {msg}")

    def send_text_to(self, peer_id, text):
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise ValueError("Message is too long (maximum 64 KiB)")
        if not text.strip():
            raise ValueError("Message cannot be empty")
        self.connections.send_message(peer_id, text)
        self.chats.sent(peer_id, self.name, text)
        self.emit("message_sent", peer_id=peer_id, name=self.name, text=text)
        self.notice(f"[{self.name}] {text}")

    def send_text(self, text):
        with self.chats.lock:
            peer_id = self.chats.current
        if peer_id is None:
            raise ValueError("No chat selected. Use /chat <name|number>.")
        self.send_text_to(peer_id, text)

    def send_file_to(self, peer_id, path):
        peer = self.peers.get(peer_id)
        if peer is None:
            raise ValueError("Peer is offline")
        self.transfers.send_file(peer, path)

    def send_file(self, path):
        with self.chats.lock:
            peer_id = self.chats.current
        if peer_id is None:
            raise ValueError("No chat selected. Use /chat first.")
        self.send_file_to(peer_id, path)

    def stop(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        if self.discovery:
            self.discovery.stop()
        if self.listener:
            self.listener.close()
            self.listener = None
        self.connections.stop()
        self.transfers.stop()
        if self.accept_thread:
            self.accept_thread.join(timeout=1.5)
        with self.workers_lock:
            workers = list(self.workers)
        for thread in workers:
            if thread is not threading.current_thread():
                thread.join(timeout=1)
