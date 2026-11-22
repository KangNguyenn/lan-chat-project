"""Thread-safe adapter between the Tkinter UI and the shared networking backend."""
import logging
import queue
import threading

from ..app import LanChatApp
from ..protocol import ProtocolError


class ChatController:
    def __init__(self, name, port, broadcast, downloads):
        self.events = queue.Queue()
        self.app = LanChatApp(name, port, broadcast, notify=logging.getLogger(__name__).debug,
                              downloads=downloads, event_sink=self.events.put)
        self.closing = threading.Event()
        self.workers = set()
        self.workers_lock = threading.Lock()

    def start(self):
        self.app.start()

    def _background(self, action, func, *args, **extra):
        if self.closing.is_set():
            return

        def task():
            try:
                func(*args)
            except (OSError, EOFError, ValueError, ProtocolError) as exc:
                logging.getLogger(__name__).debug("GUI action failed: %s", exc)
                if not self.closing.is_set():
                    self.events.put({"type": "action_error", "action": action,
                                     "error": str(exc), **extra})
            finally:
                with self.workers_lock:
                    self.workers.discard(threading.current_thread())

        thread = threading.Thread(target=task, name=f"gui-{action}", daemon=True)
        with self.workers_lock:
            self.workers.add(thread)
        thread.start()

    def select(self, peer_id):
        self.app.chats.select(peer_id)
        peer = self.app.peers.get(peer_id)
        if peer is not None:
            self._background("connect", self.app.connections.connect, peer)

    def send_message(self, peer_id, message):
        self._background("send message", self.app.send_text_to, peer_id, message,
                         peer_id=peer_id, message=message)

    def send_file(self, peer_id, path):
        self._background("send file", self.app.send_file_to, peer_id, path)

    def stop(self):
        if self.closing.is_set():
            return
        self.closing.set()
        self.app.stop()
        with self.workers_lock:
            pending = list(self.workers)
        for thread in pending:
            if thread is not threading.current_thread():
                thread.join(timeout=0.2)
