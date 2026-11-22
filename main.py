"""Start LAN Chat in GUI mode by default, or CLI mode with --nogui."""
import argparse
import sys

from lanchat.console import Console, prompt_startup_config
from lanchat.startup import StartupConfig, parse_name, parse_port


class GuiUnavailable(Exception):
    """The graphical environment could not be initialized."""


class VietnameseHelpFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "Cách dùng: ")


class VietnameseArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: lỗi tham số: {message}\n")


def run_gui(config):
    try:
        import tkinter as tk
    except ImportError as exc:
        raise GuiUnavailable(str(exc)) from exc
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise GuiUnavailable(str(exc)) from exc

    controller = None
    try:
        from lanchat.gui.controller import ChatController
        from lanchat.gui.window import LanChatWindow

        form = None
        if config is None:
            from lanchat.gui.startup import StartupForm

            form = StartupForm(root)

        while True:
            if form is not None:
                root.mainloop()
                config = form.config
                if config is None:
                    return

            controller = ChatController(config.name, config.port, config.bcast, config.downloads)
            try:
                controller.start()
            except OSError as exc:
                if form is None:
                    raise
                controller.stop()
                controller = None
                form.show_error("Không thể khởi động. Hãy kiểm tra cổng TCP và thử lại. "
                                f"({exc})")
            else:
                break

        if form is not None:
            form.destroy()
        LanChatWindow(root, controller)
        root.mainloop()
    finally:
        try:
            if controller is not None:
                controller.stop()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass


def main(argv=None):
    parser = VietnameseArgumentParser(
        description="LAN Chat — Nhắn tin và chia sẻ tệp trong mạng nội bộ",
        epilog="Chạy mà không truyền tùy chọn cấu hình để nhập thiết lập khi khởi động.",
        argument_default=argparse.SUPPRESS,
        formatter_class=VietnameseHelpFormatter,
        add_help=False,
    )
    flags = parser.add_argument_group("Tùy chọn")
    flags.add_argument("-h", "--help", action="help", help="Hiển thị hướng dẫn này.")
    flags.add_argument("--name", metavar="TÊN", help="Tên hiển thị. Bắt buộc khi truyền tùy chọn cấu hình.")
    flags.add_argument("--port", metavar="CỔNG",
                       help=f"Cổng TCP lắng nghe. Mặc định {StartupConfig.port} để hệ điều hành tự cấp cổng.")
    flags.add_argument("--bcast", metavar="IP", help=f"Địa chỉ quảng bá UDP (mặc định {StartupConfig.bcast}).")
    flags.add_argument("--downloads", metavar="THƯ_MỤC",
                       help=f"Thư mục lưu tệp nhận (mặc định {StartupConfig.downloads}).")
    flags.add_argument("--nogui", action="store_true", help="Sử dụng giao diện dòng lệnh.")
    options = vars(parser.parse_args(argv))
    nogui = options.pop("nogui", False)

    config = None
    if options:
        if "name" not in options:
            parser.error("Cần --name khi truyền tùy chọn cấu hình.")
        try:
            options["name"] = parse_name(options["name"])
            if "port" in options:
                options["port"] = parse_port(options["port"])
        except ValueError as exc:
            parser.error(str(exc))
        config = StartupConfig(**options)

    try:
        if not nogui:
            try:
                run_gui(config)
                return
            except GuiUnavailable as exc:
                if not sys.stdin.isatty():
                    parser.exit(1, f"[!] Không thể mở GUI ({exc}) và không có terminal tương tác để chạy CLI.\n")
                print(f"[!] Không thể mở GUI ({exc}). Đang chuyển sang chế độ dòng lệnh.", file=sys.stderr)

        if config is None:
            if not sys.stdin.isatty():
                parser.exit(1, "[!] Để chạy, hãy dùng terminal tương tác hoặc truyền --name.\n")
            try:
                config = prompt_startup_config()
            except (EOFError, KeyboardInterrupt):
                print("\nĐã hủy khởi động.", file=sys.stderr)
                return
        Console(config.name, config.port, config.bcast, config.downloads).run()
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"[!] Không thể khởi động: {exc}\n")


if __name__ == "__main__":
    main()
