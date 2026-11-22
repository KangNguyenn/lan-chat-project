"""Vietnamese terminal interface and command syntax."""
import unittest

from lanchat.console import Console


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.console = Console("Alice", 0, "127.255.255.255", "downloads")

    def test_help_shows_all_required_commands_in_vietnamese(self):
        self.assertTrue(self.console._process("/help"))
        help_text = self.console.events.get_nowait()
        for command in ("/list", "/chat <tên|số>", "<tin nhắn>",
                        "/send <tệp>", "/leave", "/status <online|away>",
                        "/help", "/quit"):
            self.assertIn(command, help_text)
        self.assertIn("Xem danh sách người dùng", help_text)
        self.assertIn("Gửi tệp", help_text)

    def test_no_users_and_missing_peer_are_in_vietnamese(self):
        self.assertTrue(self.console._process("/list"))
        self.assertEqual(self.console.events.get_nowait(), "[*] Chưa có người dùng nào trực tuyến.")
        with self.assertRaisesRegex(ValueError, "Không tìm thấy người dùng"):
            self.console._process("/chat nobody")
        with self.assertRaisesRegex(ValueError, "Cú pháp: /send <tệp>"):
            self.console._process("/send")
        with self.assertRaisesRegex(ValueError, "Lệnh không hợp lệ"):
            self.console._process("/unknown")

    def test_status_and_leave_messages_are_in_vietnamese(self):
        self.assertTrue(self.console._process("/status away"))
        self.assertEqual(self.console.events.get_nowait(), "[*] Trạng thái của bạn: Vắng mặt")
        self.assertTrue(self.console._process("/leave"))
        self.assertEqual(self.console.events.get_nowait(), "[*] Bạn chưa mở cuộc trò chuyện nào.")


if __name__ == "__main__":
    unittest.main()
