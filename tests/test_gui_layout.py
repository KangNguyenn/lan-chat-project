"""Layout regression tests that use a real Tk display when available."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lanchat.peers import ChatStore, PeerStore


class ChatLayoutTests(unittest.TestCase):
    def assert_fits(self, widget):
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight(), str(widget))
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        right = left + widget.winfo_width()
        bottom = top + widget.winfo_height()
        parent = widget.master
        while parent is not None:
            self.assertGreaterEqual(left, parent.winfo_rootx(), str(widget))
            self.assertGreaterEqual(top, parent.winfo_rooty(), str(widget))
            self.assertLessEqual(right, parent.winfo_rootx() + parent.winfo_width(), str(widget))
            self.assertLessEqual(bottom, parent.winfo_rooty() + parent.winfo_height(), str(widget))
            parent = parent.master

    def test_composer_survives_short_windows_at_different_scales(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("Tkinter is unavailable")

        from lanchat.gui.window import LanChatWindow

        for scaling in (4 / 3, 5 / 3, 2):
            with self.subTest(scaling=scaling):
                try:
                    root = tk.Tk()
                except tk.TclError as exc:
                    self.skipTest(f"Tk display unavailable: {exc}")
                try:
                    root.tk.call("tk", "scaling", scaling)
                    app = SimpleNamespace(name="Kang", chats=ChatStore(), peers=PeerStore(Mock()))
                    controller = Mock(app=app)
                    with patch.object(LanChatWindow, "_tick"):
                        window = LanChatWindow(root, controller)
                    controls = (window.attach_button, window.message_input,
                                window.send_button, window.transfer_bar)
                    root.update()
                    tall_transcript = window.messages.winfo_height()
                    root.geometry(f"620x{root.minsize()[1]}")
                    root.update()

                    self.assertLess(window.messages.winfo_height(), tall_transcript)
                    for widget in controls:
                        self.assert_fits(widget)
                    self.assertTrue(window.message_input.instate(["disabled"]))

                    for index in range(40):
                        app.peers.observe(str(index), f"Peer {index}", "127.0.0.1", 5000)
                        app.chats.receive("0", "Peer 0", f"Message {index}")
                    window._sync_peers()
                    window.peer_list.selection_set("0")
                    window._select_peer()
                    window.status_text.set("A long network notice " * 25)
                    window.transfer_text.set("A long file name " * 25)
                    root.update()

                    for widget in controls:
                        self.assert_fits(widget)
                    for widget in (window.messages, window.peer_list):
                        start, end = widget.yview()
                        self.assertLess(end - start, 1)
                        widget.yview_moveto(0.5)
                        self.assertGreater(widget.yview()[0], 0)
                        self.assertLess(widget.yview()[1], 1)
                    window.message_input.insert(0, "Hello")
                    window.send_button.invoke()
                    controller.send_message.assert_called_once_with("0", "Hello")
                finally:
                    root.destroy()
