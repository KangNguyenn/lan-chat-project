"""Dedicated TCP stream per file, without blocking chat messages."""
import os
import pathlib
import socket
import threading
import time
import uuid

from .protocol import ProtocolError, recv_exact, recv_frame, send_frame

CHUNK_SIZE = 64 * 1024
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


class TransferManager:
    def __init__(self, app, downloads="downloads"):
        self.app = app
        self.downloads = pathlib.Path(downloads)
        self.lock = threading.RLock()
        self.sockets = set()
        self.threads = set()

    def _add_sock(self, sock):
        with self.lock:
            self.sockets.add(sock)

    def _remove_sock(self, sock):
        with self.lock:
            self.sockets.discard(sock)
        try:
            sock.close()
        except OSError:
            pass

    def send_file(self, peer, path):
        path = pathlib.Path(path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy tệp: {path}")
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ValueError("Tệp vượt quá giới hạn 2 GiB.")
        thread = threading.Thread(target=self._send_worker, args=(peer, path, size), daemon=True)
        with self.lock:
            self.threads.add(thread)
        thread.start()

    def _progress(self, peer_id, direction, name, done, size, state):
        percent = 100 if size == 0 else int(done * 100 / size)
        now = time.monotonic()
        if percent == 100 or percent >= state[0] + 10 or now - state[1] > 1:
            state[:] = [percent, now]
            label = "Đang gửi" if direction == "Sending" else "Đang nhận"
            self.app.notice(f"[*] {label} {name}: {percent}% ({done}/{size} byte)")
            self.app.emit("transfer_progress", peer_id=peer_id, direction=direction,
                          name=name, done=done, size=size, percent=percent)

    def _send_worker(self, peer, path, size):
        sock = None
        try:
            self.app.emit("transfer_started", peer_id=peer.peer_id, direction="Sending",
                          name=path.name, size=size)
            sock = socket.create_connection((peer.ip, peer.port), timeout=5)
            self._add_sock(sock)
            sock.settimeout(8)
            send_frame(sock, self.app.hello("file"))
            reply = recv_frame(sock)
            self.app.validate_hello(reply, expected_id=peer.peer_id, kind="file")
            transfer_id = uuid.uuid4().hex
            send_frame(sock, {"type": "FILE_META", "name": path.name,
                              "size": size, "transfer_id": transfer_id})
            # Allow long transfers with a blocking socket; closing it cancels the transfer.
            sock.settimeout(None)
            progress = [-10, time.monotonic()]
            sent = 0
            with path.open("rb") as stream:
                while True:
                    data = stream.read(CHUNK_SIZE)
                    if not data:
                        break
                    sock.sendall(data)
                    sent += len(data)
                    self._progress(peer.peer_id, "Sending", path.name, sent, size, progress)
            if sent != size:
                raise OSError("Tệp đã thay đổi trong khi gửi.")
            # A receiving peer must acknowledge saving the complete file.
            sock.settimeout(15)
            ack = recv_frame(sock)
            if ack.get("type") != "FILE_ACK" or ack.get("transfer_id") != transfer_id or not ack.get("ok"):
                raise OSError(f"Bên nhận chưa xác nhận đã lưu tệp: {ack.get('error', 'lỗi chưa xác định')}")
            self.app.notice(f"[*] Đã gửi tệp: {path.name}")
            self.app.emit("transfer_completed", peer_id=peer.peer_id, direction="Sending",
                          name=path.name, size=size)
        except (OSError, EOFError, ValueError, ProtocolError) as exc:
            self.app.notice(f"[!] Không thể gửi {path.name}: {exc}")
            self.app.emit("transfer_failed", peer_id=peer.peer_id, direction="Sending",
                          name=path.name, error=str(exc))
        finally:
            if sock is not None:
                self._remove_sock(sock)
            with self.lock:
                self.threads.discard(threading.current_thread())

    def receive_file(self, sock, hello):
        self._add_sock(sock)
        partial = None
        transfer_id = None
        try:
            sock.settimeout(10)
            meta = recv_frame(sock)
            if meta.get("type") != "FILE_META":
                raise ProtocolError("Thiếu bản tin FILE_META.")
            name, size = meta.get("name"), meta.get("size")
            transfer_id = meta.get("transfer_id")
            if (not isinstance(name, str) or not name or name in (".", "..")
                    or len(name) > 200 or any(ord(char) < 32 for char in name)
                    or any(char in name for char in '/\\<>:"|?*')):
                raise ProtocolError("Tên tệp không an toàn.")
            if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_FILE_SIZE:
                raise ProtocolError("Kích thước tệp không hợp lệ.")
            if not isinstance(transfer_id, str) or len(transfer_id) > 80:
                raise ProtocolError("Mã phiên truyền tệp không hợp lệ.")
            self.downloads.mkdir(parents=True, exist_ok=True)
            partial = self.downloads / ("." + uuid.uuid4().hex + ".part")
            self.app.notice(f"[*] Đang nhận tệp {name} ({size} byte)")
            self.app.emit("transfer_started", peer_id=hello["id"], direction="Receiving",
                          name=name, size=size)
            progress = [-10, time.monotonic()]
            received = 0
            sock.settimeout(30)
            with partial.open("xb") as stream:
                while received < size:
                    data = recv_exact(sock, min(CHUNK_SIZE, size - received))
                    stream.write(data)
                    received += len(data)
                    self._progress(hello["id"], "Receiving", name, received, size, progress)
            with self.lock:
                final = self.downloads / name
                suffix = 1
                while final.exists():
                    final = self.downloads / f"{pathlib.Path(name).stem} ({suffix}){pathlib.Path(name).suffix}"
                    suffix += 1
                partial.replace(final)
            partial = None
            send_frame(sock, {"type": "FILE_ACK", "transfer_id": transfer_id, "ok": True})
            self.app.notice(f"[*] Đã nhận tệp: {final}")
            self.app.emit("transfer_completed", peer_id=hello["id"], direction="Receiving",
                          name=name, size=size, path=str(final))
        except (OSError, EOFError, ValueError, ProtocolError) as exc:
            self.app.notice(f"[!] Nhận tệp thất bại: {exc}")
            self.app.emit("transfer_failed", peer_id=hello["id"], direction="Receiving",
                          name=locals().get("name", "file"), error=str(exc))
            if transfer_id:
                try:
                    send_frame(sock, {"type": "FILE_ACK", "transfer_id": transfer_id,
                                      "ok": False, "error": str(exc)[:120]})
                except OSError:
                    pass
        finally:
            if partial is not None:
                try:
                    partial.unlink(missing_ok=True)
                except OSError:
                    pass
            self._remove_sock(sock)

    def stop(self):
        with self.lock:
            sockets = list(self.sockets)
            threads = list(self.threads)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._remove_sock(sock)
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(timeout=1)
