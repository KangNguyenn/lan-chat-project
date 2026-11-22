"""Responsive command line: one output queue and prompt_toolkit redraw."""
import queue
import threading

from .app import LanChatApp
from .startup import StartupConfig, parse_name, parse_port


def _prompt_value(label, parse, default=""):
    while True:
        value = input(label)
        try:
            return parse(value or default)
        except ValueError as exc:
            print(f"[!] {exc}")


def prompt_startup_config():
    print("LAN Chat — Startup configuration")
    name = _prompt_value("Display name: ", parse_name)
    port = _prompt_value(f"TCP listening port [{StartupConfig.port}]: ", parse_port, StartupConfig.port)
    bcast = input(f"UDP broadcast address [{StartupConfig.bcast}]: ") or StartupConfig.bcast
    downloads = input(f"Downloads folder [{StartupConfig.downloads}]: ") or StartupConfig.downloads
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
            raise ValueError("Multiple users have this name. Select one by number from /list")
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
                "Commands:\n"
                "  /list                  Show online users with number, name, IP and status\n"
                "  /chat <name|number>    Open a chat with the selected user (TCP connection)\n"
                "  <any text>             Send a message to the current chat partner\n"
                "  /send <file>           Send a file to the current chat partner\n"
                "  /leave                 Close the current chat\n"
                "  /status <online|away>  Change your status (sent via UDP)\n"
                "  /help                  Show all commands\n"
                "  /quit                  Exit the program"
            )
        elif cmd == "/list":
            peers = self.app.peers.list()
            if not peers:
                self.events.put("[*] No users online")
            for i, peer in enumerate(peers, 1):
                self.events.put(f"{i}. {peer.name} ({peer.ip}:{peer.port}) - {peer.status}")
        elif cmd == "/chat":
            peer = self._find_peer(param) if param else None
            if not peer:
                raise ValueError("User not found. Use /list to see available users")
            self.app.select_chat(peer)
        elif cmd == "/send":
            if not param:
                raise ValueError("Usage: /send <file>")
            self.app.send_file(param.strip('"').strip("'"))
        elif cmd == "/status":
            self.app.set_status(param)
        elif cmd == "/leave":
            peer_id = self.app.chats.leave()
            if peer_id:
                self.app.connections.close_peer(peer_id)
                self.events.put("[*] Left the current chat")
            else:
                self.events.put("[*] No active chat to leave")
        elif cmd == "/quit":
            return False
        else:
            raise ValueError("Unknown command. Use /help to see available commands")
        return True

    def run(self):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
        except ImportError as exc:
            raise RuntimeError("prompt_toolkit is required. Install dependencies: python -m pip install -r requirements.txt") from exc
        self.printer = threading.Thread(target=self._print_events, daemon=True)
        self.printer.start()
        try:
            with patch_stdout():
                self.app.start()
                self.events.put("[*] Type /help to see available commands")
                session = PromptSession(erase_when_done=True)
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
