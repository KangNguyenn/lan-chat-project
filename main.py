"""Start LAN Chat in GUI mode by default, or CLI mode with --nogui."""
import argparse
import sys

from lanchat.console import Console, prompt_startup_config
from lanchat.startup import StartupConfig, parse_name, parse_port


class GuiUnavailable(Exception):
    """The graphical environment could not be initialized."""


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
    parser = argparse.ArgumentParser(
        description="LAN Chat & File Sharing",
        epilog="Run without configuration flags to enter startup settings interactively.",
        argument_default=argparse.SUPPRESS,
    )
    parser.add_argument("--name", help="Display name (required when passing configuration flags)")
    parser.add_argument("--port", help=f"TCP listening port (default: {StartupConfig.port}, assigned by the OS)")
    parser.add_argument("--bcast", help=f"UDP broadcast address (default: {StartupConfig.bcast})")
    parser.add_argument("--downloads", help=f"Directory for received files (default: {StartupConfig.downloads})")
    parser.add_argument("--nogui", action="store_true", help="Use the terminal interface")
    options = vars(parser.parse_args(argv))
    nogui = options.pop("nogui", False)

    config = None
    if options:
        if "name" not in options:
            parser.error("--name is required when passing configuration flags")
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
                    parser.exit(1, f"[!] GUI unavailable ({exc}) and no interactive terminal for CLI fallback\n")
                print(f"[!] GUI unavailable ({exc}); starting CLI instead", file=sys.stderr)

        if config is None:
            if not sys.stdin.isatty():
                parser.exit(1, "[!] Startup settings require an interactive terminal or --name\n")
            try:
                config = prompt_startup_config()
            except (EOFError, KeyboardInterrupt):
                print("\nStartup canceled.", file=sys.stderr)
                return
        Console(config.name, config.port, config.bcast, config.downloads).run()
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"[!] Unable to start: {exc}\n")


if __name__ == "__main__":
    main()
