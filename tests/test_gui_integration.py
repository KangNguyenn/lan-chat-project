"""Headless tests for the GUI's shared backend and startup policy."""
import queue
import tempfile
import time
import unittest
from unittest.mock import patch

import main
from lanchat.gui.controller import ChatController
from lanchat.peers import ChatStore


class EntryPointTests(unittest.TestCase):
    def test_gui_by_default_and_shared_arguments(self):
        with patch("main.run_gui") as gui:
            main.main(["--name", "Alice", "--port", "5050", "--downloads", "received"])
        options = gui.call_args.args[0]
        self.assertEqual((options.name, options.port, options.downloads),
                         ("Alice", 5050, "received"))

    def test_nogui_never_attempts_to_start_gui(self):
        with patch("main.run_gui") as gui, patch("main.Console") as console:
            main.main(["--name", "Alice", "--nogui"])
        gui.assert_not_called()
        console.assert_called_once_with("Alice", 0, "255.255.255.255", "downloads")
        console.return_value.run.assert_called_once()

    def test_no_flags_opens_gui_setup(self):
        with patch("main.run_gui") as gui, patch("main.prompt_startup_config") as prompt:
            main.main([])
        gui.assert_called_once_with(None)
        prompt.assert_not_called()

    def test_config_flags_require_name(self):
        for flag, value in (("--port", "0"), ("--bcast", "255.255.255.255"),
                            ("--downloads", "downloads")):
            with self.subTest(flag=flag), patch("main.run_gui") as gui:
                with self.assertRaises(SystemExit) as caught:
                    main.main([flag, value])
                self.assertEqual(caught.exception.code, 2)
                gui.assert_not_called()

    def test_nogui_alone_prompts_and_retries_invalid_fields(self):
        with patch("main.run_gui") as gui, patch("main.Console") as console, \
                patch("main.sys.stdin.isatty", return_value=True), \
                patch("builtins.input", side_effect=[" ", " Alice ", "65536", "0", "", "received"]) as read:
            main.main(["--nogui"])
        gui.assert_not_called()
        self.assertEqual(read.call_count, 6)
        console.assert_called_once_with("Alice", 0, "255.255.255.255", "received")
        console.return_value.run.assert_called_once()

    def test_nogui_setup_can_be_canceled(self):
        with patch("main.sys.stdin.isatty", return_value=True), \
                patch("builtins.input", side_effect=KeyboardInterrupt), patch("main.Console") as console:
            main.main(["--nogui"])
        console.assert_not_called()

    def test_nogui_setup_requires_interactive_terminal(self):
        with patch("main.sys.stdin.isatty", return_value=False), \
                patch("main.prompt_startup_config") as prompt:
            with self.assertRaises(SystemExit) as caught:
                main.main(["--nogui"])
        self.assertEqual(caught.exception.code, 1)
        prompt.assert_not_called()

    def test_gui_fallback_prompts_when_no_configuration_was_passed(self):
        with patch("main.run_gui", side_effect=main.GuiUnavailable("no display")), \
                patch("main.sys.stdin.isatty", return_value=True), \
                patch("builtins.input", side_effect=["Alice", "", "", ""]), patch("main.Console") as console:
            main.main([])
        console.assert_called_once_with("Alice", 0, "255.255.255.255", "downloads")

    def test_gui_unavailable_falls_back_only_with_terminal(self):
        with patch("main.run_gui", side_effect=main.GuiUnavailable("no display")), \
                patch("main.sys.stdin.isatty", return_value=True), \
                patch("main.Console") as console:
            main.main(["--name", "Alice"])
        console.return_value.run.assert_called_once()
        with patch("main.run_gui", side_effect=main.GuiUnavailable("no display")), \
                patch("main.sys.stdin.isatty", return_value=False), \
                patch("main.Console") as console:
            with self.assertRaises(SystemExit) as caught:
                main.main(["--name", "Alice"])
        self.assertEqual(caught.exception.code, 1)
        console.assert_not_called()


class ChatStateTests(unittest.TestCase):
    def test_direction_is_not_based_on_duplicate_usernames(self):
        chats = ChatStore()
        chats.receive("peer", "SameName", "incoming")
        chats.sent("peer", "SameName", "outgoing")
        self.assertEqual(chats.snapshot("peer"), [
            ("SameName", "incoming", "incoming"),
            ("SameName", "outgoing", "outgoing")])
        self.assertEqual(chats.unread_counts(), {"peer": 1})
        chats.select("peer")
        self.assertEqual(chats.unread_counts(), {})

    def test_gui_controller_and_cli_backend_can_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            alice = ChatController("Alice", 0, "127.255.255.255", directory)
            bob = ChatController("Bob", 0, "127.255.255.255", directory)
            try:
                alice.start()
                bob.start()
                alice.app.peers.observe(bob.app.identity, "Bob", "127.0.0.1", bob.app.port)
                bob.app.peers.observe(alice.app.identity, "Alice", "127.0.0.1", alice.app.port)
                alice.select(bob.app.identity)
                alice.send_message(bob.app.identity, "Hello Bob")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if ("Alice", "Hello Bob") in bob.app.chats.histories.get(alice.app.identity, ()):
                        break
                    time.sleep(0.02)
                self.assertIn(("Alice", "Hello Bob"),
                              bob.app.chats.histories.get(alice.app.identity, ()))
                events = []
                while True:
                    try:
                        events.append(alice.events.get_nowait())
                    except queue.Empty:
                        break
                self.assertTrue(any(e["type"] == "message_sent" for e in events))
            finally:
                alice.stop()
                bob.stop()


if __name__ == "__main__":
    unittest.main()
