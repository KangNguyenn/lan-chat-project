"""English-only built-in CLI text; user-provided content remains untouched."""
import unittest

from lanchat.console import Console


class EnglishConsoleTests(unittest.TestCase):
    def setUp(self):
        self.console = Console("Alice", 0, "127.255.255.255", "downloads")

    def test_help_shows_all_required_commands_in_english(self):
        self.assertTrue(self.console._process("/help"))
        help_text = self.console.events.get_nowait()
        for command in ("/list", "/chat <name|number>", "<any text>",
                        "/send <file>", "/leave", "/status <online|away>",
                        "/help", "/quit"):
            self.assertIn(command, help_text)
        self.assertIn("Show online users", help_text)
        self.assertIn("Send a file", help_text)
        self.assertTrue(help_text.isascii())

    def test_no_users_and_missing_peer_are_in_english(self):
        self.assertTrue(self.console._process("/list"))
        self.assertEqual(self.console.events.get_nowait(), "[*] No users online")
        with self.assertRaisesRegex(ValueError, "User not found"):
            self.console._process("/chat nobody")
        with self.assertRaisesRegex(ValueError, "Usage: /send <file>"):
            self.console._process("/send")
        with self.assertRaisesRegex(ValueError, "Unknown command"):
            self.console._process("/unknown")

    def test_status_and_leave_messages_are_in_english(self):
        self.assertTrue(self.console._process("/status away"))
        self.assertEqual(self.console.events.get_nowait(), "[*] Status: away")
        self.assertTrue(self.console._process("/leave"))
        self.assertEqual(self.console.events.get_nowait(), "[*] No active chat to leave")


if __name__ == "__main__":
    unittest.main()
