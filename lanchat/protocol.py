"""A small, explicitly bounded length-prefixed JSON protocol for TCP."""
import json
import struct

MAX_FRAME = 256 * 1024


class ProtocolError(Exception):
    pass


def recv_exact(sock, count):
    if count < 0:
        raise ProtocolError("Độ dài dữ liệu không được âm.")
    data = bytearray()
    while len(data) < count:
        part = sock.recv(min(65536, count - len(data)))
        if not part:
            raise EOFError("Kết nối đã đóng trước khi nhận đủ dữ liệu.")
        data.extend(part)
    return bytes(data)


def send_frame(sock, value, lock=None):
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ProtocolError("Khung dữ liệu phải là một đối tượng có trường type.")
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not 0 < len(raw) <= MAX_FRAME:
        raise ProtocolError("Khung dữ liệu vượt quá kích thước tối đa.")
    packet = struct.pack("!I", len(raw)) + raw
    if lock is None:
        sock.sendall(packet)
    else:
        with lock:
            sock.sendall(packet)


def recv_frame(sock):
    try:
        header = recv_exact(sock, 4)
    except EOFError:
        raise
    length = struct.unpack("!I", header)[0]
    if not 0 < length <= MAX_FRAME:
        raise ProtocolError("Độ dài khung dữ liệu không hợp lệ.")
    try:
        value = json.loads(recv_exact(sock, length).decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError("Khung dữ liệu chứa JSON không hợp lệ.") from exc
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ProtocolError("Đối tượng trong khung dữ liệu không hợp lệ.")
    return value
