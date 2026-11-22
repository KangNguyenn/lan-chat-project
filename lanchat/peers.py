"""Thread-safe peer discovery state and chat/unread history."""
import threading
import time
from dataclasses import dataclass


@dataclass
class Peer:
    peer_id: str
    name: str
    ip: str
    port: int
    status: str = "online"
    last_seen: float = 0.0


class PeerStore:
    def __init__(self, notify, emit=None):
        self._peers = {}
        self._lock = threading.RLock()
        self._notify = notify
        self._emit = emit

    def observe(self, peer_id, name, ip, port, status="online"):
        if not isinstance(peer_id, str) or not 1 <= len(peer_id) <= 80:
            return
        if not isinstance(name, str) or not 1 <= len(name) <= 60:
            return
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            return
        if status not in ("online", "away"):
            return
        change = None
        with self._lock:
            prev = self._peers.get(peer_id)
            if prev is None:
                change = f"[*] {name} is online ({ip}:{port})"
            elif prev.status != status:
                change = f"[*] {name} changed status to {status}"
            self._peers[peer_id] = Peer(peer_id, name, ip, port, status, time.monotonic())
        if change:
            self._notify(change)
            if self._emit is not None:
                self._emit("peer_status", name=name, status=status)

    def expire(self, timeout=10):
        now = time.monotonic()
        with self._lock:
            gone = [p for p in self._peers.values() if now - p.last_seen > timeout]
            for p in gone:
                self._peers.pop(p.peer_id, None)
        for p in gone:
            self._notify(f"[*] {p.name} is offline (timeout)")
            if self._emit is not None:
                self._emit("peer_status", name=p.name, status="offline")

    def get(self, peer_id):
        with self._lock:
            p = self._peers.get(peer_id)
            return Peer(**vars(p)) if p else None

    def list(self):
        with self._lock:
            return [Peer(**vars(p)) for p in self._peers.values()]


class ChatStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.current = None
        self.histories = {}
        self.directions = {}
        self.unread = {}

    def select(self, peer_id):
        with self.lock:
            self.current = peer_id
            unseen = self.unread.pop(peer_id, [])
        return unseen

    def leave(self):
        with self.lock:
            peer = self.current
            self.current = None
            return peer

    def receive(self, peer_id, name, text):
        with self.lock:
            self.histories.setdefault(peer_id, []).append((name, text))
            self.directions.setdefault(peer_id, []).append("incoming")
            if len(self.histories[peer_id]) > 1000:
                del self.histories[peer_id][:-1000]
                del self.directions[peer_id][:-1000]
            active = self.current == peer_id
            if not active:
                inbox = self.unread.setdefault(peer_id, [])
                inbox.append((name, text))
                return False, len(inbox)
            return True, 0

    def sent(self, peer_id, name, text):
        with self.lock:
            self.histories.setdefault(peer_id, []).append((name, text))
            self.directions.setdefault(peer_id, []).append("outgoing")
            if len(self.histories[peer_id]) > 1000:
                del self.histories[peer_id][:-1000]
                del self.directions[peer_id][:-1000]

    def snapshot(self, peer_id):
        with self.lock:
            history = self.histories.get(peer_id, ())
            directions = self.directions.get(peer_id, ())
            return [(name, message, direction) for (name, message), direction
                    in zip(history, directions)]

    def unread_counts(self):
        with self.lock:
            return {peer_id: len(messages) for peer_id, messages in self.unread.items()}

    def reset_if_current(self, peer_id):
        with self.lock:
            if self.current == peer_id:
                self.current = None
                return True
            return False
