"""Responsive command line: one output queue and prompt_toolkit redraw."""
import queue
import threading

from .app import LanChatApp


class Console:
    def __init__(self, name, port, broadcast, downloads):
        self.events = queue.Queue()
        self.finished = threading.Event()
        self.app = LanChatApp(name, port, broadcast, notify=self.events.put,
                              downloads=downloads)
        self.printer = None

    def _print_events(self):
        while not self.finished.is_set() or not self.events.empty():
            try:
                print(self.events.get(timeout=0.1), flush=True)
            except queue.Empty:
                pass

    def _find_peer(self, target):
        peers = self.app.peers.list()
        if target.isdecimal():
            index = int(target) - 1
            return peers[index] if 0 <= index < len(peers) else None
        found = [peer for peer in peers if peer.name == target]
        if len(found) > 1:
            raise ValueError("Tên bị trùng, hãy chọn bằng số từ /list")
        return found[0] if found else None

    def _process(self, line):
        if not line.startswith("/"):
            if line.strip():
                self.app.send_text(line)
            return True
        cmd, _, param = line.partition(" ")
        cmd, param = cmd.lower(), param.strip()
        if cmd == "/help":
            self.events.put("/list · /chat <tên|số> · /send <file> · /leave · "
                            "/status <online|away> · /help · /quit")
        elif cmd == "/list":
            peers = self.app.peers.list()
            if not peers:
                self.events.put("[*] Chưa có ai online")
            for i, peer in enumerate(peers, 1):
                self.events.put(f"{i}. {peer.name} ({peer.ip}:{peer.port}) - {peer.status}")
        elif cmd == "/chat":
            peer = self._find_peer(param) if param else None
            if not peer:
                raise ValueError("Không tìm thấy peer. Dùng /list để xem danh sách")
            self.app.select_chat(peer)
        elif cmd == "/send":
            if not param:
                raise ValueError("Dùng: /send <đường_dẫn_file>")
            self.app.send_file(param.strip('"').strip("'"))
        elif cmd == "/status":
            self.app.set_status(param)
        elif cmd == "/leave":
            peer_id = self.app.chats.leave()
            if peer_id:
                self.app.connections.close_peer(peer_id)
                self.events.put("[*] Đã rời phiên chat")
            else:
                self.events.put("[*] Bạn chưa mở phiên chat nào")
        elif cmd == "/quit":
            return False
        else:
            raise ValueError("Lệnh không hợp lệ. Dùng /help")
        return True

    def run(self):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
        except ImportError as exc:
            raise RuntimeError("Cần cài prompt_toolkit: pip install -r requirements.txt") from exc
        self.printer = threading.Thread(target=self._print_events, daemon=True)
        self.printer.start()
        try:
            with patch_stdout():
                self.app.start()
                self.events.put("[*] Gõ /help để xem các lệnh")
                session = PromptSession()
                while True:
                    try:
                        line = session.prompt("> ")
                    except (KeyboardInterrupt, EOFError):
                        break
                    try:
                        if not self._process(line):
                            break
                    except (ValueError, OSError, EOFError, ConnectionError) as exc:
                        self.events.put(f"[!] {exc}")
        finally:
            self.app.stop()
            self.finished.set()
            if self.printer:
                self.printer.join(timeout=2)
