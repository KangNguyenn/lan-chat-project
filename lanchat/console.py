"""Responsive command line: one output queue and prompt_toolkit redraw."""
import queue
import threading

from .app import LanChatApp
from .peers import PRESENCE_LABELS
from .protocol import ProtocolError
from .startup import StartupConfig, parse_name, parse_port


def _prompt_value(label, parse, default=""):
    while True:
        value = input(label)
        try:
            return parse(value or default)
        except ValueError as exc:
            print(f"[!] {exc}")


def prompt_startup_config():
    print("LAN Chat — Cấu hình khởi động")
    name = _prompt_value("Tên hiển thị: ", parse_name)
    port = _prompt_value(f"Cổng TCP lắng nghe [{StartupConfig.port}]: ", parse_port, StartupConfig.port)
    bcast = input(f"Địa chỉ quảng bá UDP [{StartupConfig.bcast}]: ") or StartupConfig.bcast
    downloads = input(f"Thư mục lưu tệp nhận [{StartupConfig.downloads}]: ") or StartupConfig.downloads
    return StartupConfig(name, port, bcast, downloads)


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
            raise ValueError("Có nhiều người dùng trùng tên. Hãy dùng /list rồi chọn theo số thứ tự.")
        return found[0] if found else None

    def _process(self, line):
        if not line.startswith("/"):
            if line.strip():
                self.app.send_text(line)
            return True
        cmd, _, param = line.partition(" ")
        cmd, param = cmd.lower(), param.strip()
        if cmd == "/help":
            self.events.put(
                "Các lệnh\n"
                "  /list                   Xem danh sách người dùng và trạng thái.\n"
                "  /chat <tên|số>          Mở cuộc trò chuyện qua TCP.\n"
                "  <tin nhắn>              Gửi tin nhắn cho người đang trò chuyện.\n"
                "  /send <tệp>             Gửi tệp cho người đang trò chuyện.\n"
                "  /leave                  Rời cuộc trò chuyện hiện tại.\n"
                "  /status <online|away>   Đổi trạng thái qua UDP (trực tuyến hoặc vắng mặt).\n"
                "  /help                   Xem các lệnh.\n"
                "  /quit                   Thoát ứng dụng."
            )
        elif cmd == "/list":
            peers = self.app.peers.list()
            if not peers:
                self.events.put("[*] Chưa có người dùng nào trực tuyến.")
            for i, peer in enumerate(peers, 1):
                self.events.put(f"{i}. {peer.name} ({peer.ip}:{peer.port}) - {PRESENCE_LABELS[peer.status]}")
        elif cmd == "/chat":
            peer = self._find_peer(param) if param else None
            if not peer:
                raise ValueError("Không tìm thấy người dùng. Dùng /list để xem danh sách.")
            self.app.select_chat(peer)
        elif cmd == "/send":
            if not param:
                raise ValueError("Cú pháp: /send <tệp>")
            self.app.send_file(param.strip('"').strip("'"))
        elif cmd == "/status":
            self.app.set_status(param)
        elif cmd == "/leave":
            peer_id = self.app.chats.leave()
            if peer_id:
                self.app.connections.close_peer(peer_id)
                self.events.put("[*] Đã rời cuộc trò chuyện.")
            else:
                self.events.put("[*] Bạn chưa mở cuộc trò chuyện nào.")
        elif cmd == "/quit":
            return False
        else:
            raise ValueError("Lệnh không hợp lệ. Dùng /help để xem các lệnh.")
        return True

    def run(self):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
        except ImportError as exc:
            raise RuntimeError("Cần thư viện prompt_toolkit. Hãy cài bằng lệnh python -m pip install -r requirements.txt") from exc
        self.printer = threading.Thread(target=self._print_events, daemon=True)
        self.printer.start()
        try:
            with patch_stdout():
                self.app.start()
                self.events.put("[*] Gõ /help để xem các lệnh.")
                session = PromptSession(erase_when_done=True)
                while True:
                    try:
                        line = session.prompt("> ")
                    except (KeyboardInterrupt, EOFError):
                        break
                    try:
                        if not self._process(line):
                            break
                    except (ValueError, OSError, EOFError, ProtocolError) as exc:
                        self.events.put(f"[!] {exc}")
        finally:
            self.app.stop()
            self.finished.set()
            if self.printer:
                self.printer.join(timeout=2)
