import socket
import threading
import time
import unittest

from lanchat.app import LanChatApp
from lanchat.peers import PeerStore


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.05)
    return predicate()


class DiscoveryTests(unittest.TestCase):
    def test_presence_on_loopback_and_away_status(self):
        a = LanChatApp("Ann", port=0, broadcast="127.255.255.255", notify=lambda _: None)
        b = LanChatApp("Bob", port=0, broadcast="127.255.255.255", notify=lambda _: None)
        try:
            a.start()
            b.start()
            self.assertTrue(wait_for(lambda: a.peers.get(b.identity) is not None))
            b.set_status("away")
            self.assertTrue(wait_for(lambda: (a.peers.get(b.identity) is not None and
                                             a.peers.get(b.identity).status == "away")))
        finally:
            a.stop()
            b.stop()

    def test_timeout_and_malformed_peer_validation(self):
        events = []
        store = PeerStore(events.append)
        store.observe("p", "name", "127.0.0.1", 5000, "online")
        store.observe("bad", "name", "127.0.0.1", -1, "online")
        self.assertIsNone(store.get("bad"))
        store.expire(timeout=-1)
        self.assertIsNone(store.get("p"))
        self.assertTrue(any("offline" in x for x in events))

    def test_two_listeners_cannot_bind_same_tcp_port(self):
        a = LanChatApp("Ann", port=0, broadcast="127.255.255.255", notify=lambda _: None)
        a.start()
        b = LanChatApp("Bob", port=a.port, broadcast="127.255.255.255", notify=lambda _: None)
        try:
            with self.assertRaises(OSError):
                b.start()
        finally:
            a.stop()
            b.stop()
