import socket
import struct
import threading
import unittest

from lanchat.protocol import ProtocolError, recv_exact, recv_frame, send_frame


class ProtocolTests(unittest.TestCase):
    def test_fragmented_multibyte_payload(self):
        a, b = socket.socketpair()
        try:
            def send():
                raw = '{"type":"MSG","text":"Hello 👋"}'.encode()
                data = struct.pack("!I", len(raw)) + raw
                for byte in data:
                    a.sendall(bytes([byte]))
            t = threading.Thread(target=send)
            t.start()
            self.assertEqual(recv_frame(b)["text"], "Hello 👋")
            t.join()
        finally:
            a.close()
            b.close()

    def test_back_to_back_frames(self):
        a, b = socket.socketpair()
        try:
            send_frame(a, {"type": "MSG", "text": "one"})
            send_frame(a, {"type": "MSG", "text": "two"})
            self.assertEqual(recv_frame(b)["text"], "one")
            self.assertEqual(recv_frame(b)["text"], "two")
        finally:
            a.close()
            b.close()

    def test_truncated_frame_and_bad_length(self):
        a, b = socket.socketpair()
        try:
            a.sendall(struct.pack("!I", 100) + b"abc")
            a.shutdown(socket.SHUT_WR)
            with self.assertRaises(EOFError):
                recv_frame(b)
        finally:
            a.close()
            b.close()
        a, b = socket.socketpair()
        try:
            a.sendall(struct.pack("!I", 10**8))
            with self.assertRaises(ProtocolError):
                recv_frame(b)
        finally:
            a.close()
            b.close()

    def test_recv_exact_rejects_negative(self):
        with self.assertRaises(ProtocolError):
            recv_exact(None, -1)
