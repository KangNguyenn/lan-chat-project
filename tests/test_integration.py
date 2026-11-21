import hashlib
import pathlib
import socket
import tempfile
import threading
import time
import unittest

from lanchat.app import LanChatApp
from lanchat.protocol import recv_frame, send_frame


def wait_until(predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.events = {"a": [], "b": [], "c": []}
        self.apps = []
        for key in ("a", "b", "c"):
            app = LanChatApp(key.upper(), port=0, broadcast="127.255.255.255",
                             notify=self.events[key].append,
                             downloads=str(pathlib.Path(self.temp.name) / key))
            app.start()
            self.apps.append(app)
        for app in self.apps:
            for other in self.apps:
                if app is not other:
                    app.peers.observe(other.identity, other.name, "127.0.0.1", other.port)

    def tearDown(self):
        for app in self.apps:
            app.stop()
        self.temp.cleanup()

    def test_two_way_and_unread_third_peer(self):
        a, b, c = self.apps
        a.select_chat(a.peers.get(b.identity))
        a.send_text("Hello B")
        self.assertTrue(wait_until(lambda: len(b.chats.unread.get(a.identity, [])) == 1))
        b.select_chat(b.peers.get(a.identity))
        self.assertEqual(b.chats.unread.get(a.identity, []), [])
        b.send_text("Reply A")
        self.assertTrue(wait_until(lambda: ("B", "Reply A") in a.chats.histories.get(b.identity, [])))
        c.select_chat(c.peers.get(b.identity))
        c.send_text("Hello from C")
        self.assertTrue(wait_until(lambda: len(b.chats.unread.get(c.identity, [])) == 1))
        self.assertEqual(b.chats.current, a.identity)
        b.select_chat(b.peers.get(c.identity))
        self.assertFalse(b.chats.unread.get(c.identity))

    def test_simultaneous_connect_deduplicates(self):
        a, b, _ = self.apps
        failures = []
        def f(app, other):
            try:
                app.select_chat(app.peers.get(other.identity))
            except Exception as exc:
                failures.append(exc)
        ts = [threading.Thread(target=f, args=(a, b)), threading.Thread(target=f, args=(b, a))]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertFalse(failures, failures)
        self.assertTrue(wait_until(lambda: a.connections.get(b.identity) is not None and
                                   b.connections.get(a.identity) is not None))
        a.send_text("connected")
        self.assertTrue(wait_until(lambda: ("A", "connected") in b.chats.histories.get(a.identity, [])))

    def test_file_does_not_block_chat_and_integrity(self):
        a, b, _ = self.apps
        source = pathlib.Path(self.temp.name) / "test file.bin"
        source.write_bytes(bytes(range(256)) * 2000)
        a.select_chat(a.peers.get(b.identity))
        a.send_file(str(source))
        a.send_text("Chat during file")
        self.assertTrue(wait_until(lambda: ("A", "Chat during file") in b.chats.histories.get(a.identity, [])))
        dest = pathlib.Path(self.temp.name) / "b" / source.name
        self.assertTrue(wait_until(dest.exists, timeout=8), self.events)
        self.assertEqual(hashlib.sha256(dest.read_bytes()).digest(),
                         hashlib.sha256(source.read_bytes()).digest())
        self.assertTrue(wait_until(lambda: any("Gửi file thành công" in x for x in self.events["a"])))

    def test_interrupted_file_removed(self):
        a, b, _ = self.apps
        sock = socket.create_connection((b"127.0.0.1".decode(), b.port))
        send_frame(sock, a.hello("file"))
        self.assertEqual(recv_frame(sock)["kind"], "file")
        send_frame(sock, {"type": "FILE_META", "name": "broken.txt", "size": 2000,
                          "transfer_id": "t1"})
        sock.sendall(b"only partial")
        sock.close()
        target = pathlib.Path(self.temp.name) / "b"
        self.assertTrue(wait_until(lambda: any("Nhận file thất bại" in x for x in self.events["b"])))
        self.assertFalse(list(target.glob("*.txt")))
        self.assertFalse(list(target.glob(".*.part")))

    def test_unsafe_filename_is_rejected(self):
        a, b, _ = self.apps
        sock = socket.create_connection(("127.0.0.1", b.port))
        send_frame(sock, a.hello("file"))
        self.assertEqual(recv_frame(sock)["kind"], "file")
        send_frame(sock, {"type": "FILE_META", "name": "../escape.txt", "size": 0,
                          "transfer_id": "unsafe"})
        reply = recv_frame(sock)
        sock.close()
        self.assertEqual(reply["type"], "FILE_ACK")
        self.assertFalse(reply["ok"])
        self.assertFalse((pathlib.Path(self.temp.name) / "escape.txt").exists())

    def test_same_name_and_same_ip_have_distinct_identity(self):
        a, b, c = self.apps
        a.peers.observe(b.identity, "Same", "127.0.0.1", b.port)
        a.peers.observe(c.identity, "Same", "127.0.0.1", c.port)
        both = [p for p in a.peers.list() if p.name == "Same"]
        self.assertEqual(len(both), 2)
        self.assertNotEqual(both[0].peer_id, both[1].peer_id)

    def test_disconnect_keeps_app_running(self):
        a, b, _ = self.apps
        a.select_chat(a.peers.get(b.identity))
        b.stop()
        self.assertTrue(wait_until(lambda: a.connections.get(b.identity) is None))
        self.assertIsNone(a.chats.current)
