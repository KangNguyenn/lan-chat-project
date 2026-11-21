"""Start LAN Chat in GUI mode by default, or CLI mode with --nogui."""
import argparse
import sys

from lanchat.console import Console


class GuiUnavailable(Exception):
    """The graphical environment could not be initialized."""


def run_gui(args):
    try:
        import tkinter as tk
    except ImportError as exc:
        raise GuiUnavailable(str(exc)) from exc
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise GuiUnavailable(str(exc)) from exc

    try:
        from lanchat.gui.controller import ChatController
        from lanchat.gui.window import LanChatWindow
        controller = ChatController(args.name, args.port, args.bcast, args.downloads)
        LanChatWindow(root, controller)
        try:
            controller.start()
            root.mainloop()
        finally:
            controller.stop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing")
    parser.add_argument("--name", required=True, help="Display name (required for GUI and CLI)")
    parser.add_argument("--port", type=int, default=5000, help="TCP listening port (default: 5000)")
    parser.add_argument("--bcast", default="255.255.255.255", help="UDP broadcast address")
    parser.add_argument("--downloads", default="downloads", help="Directory for received files")
    parser.add_argument("--nogui", action="store_true", help="Use the terminal interface")
    args = parser.parse_args(argv)
    args.name = args.name.strip()
    if not 1 <= len(args.name) <= 60:
        parser.error("--name must contain 1 to 60 characters")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    try:
        if args.nogui:
            Console(args.name, args.port, args.bcast, args.downloads).run()
            return
        try:
            run_gui(args)
        except GuiUnavailable as exc:
            if not sys.stdin.isatty():
                parser.exit(1, f"[!] GUI unavailable ({exc}) and no interactive terminal for CLI fallback\n")
            print(f"[!] GUI unavailable ({exc}); starting CLI instead", file=sys.stderr)
            Console(args.name, args.port, args.bcast, args.downloads).run()
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"[!] Unable to start: {exc}\n")


if __name__ == "__main__":
    main()
