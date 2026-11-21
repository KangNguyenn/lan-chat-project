"""Start a peer-to-peer LAN chat instance."""
import argparse

from lanchat.console import Console


def main():
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing (CLI)")
    parser.add_argument("--name", required=True, help="Tên hiển thị")
    parser.add_argument("--port", type=int, default=5000, help="TCP listening port")
    parser.add_argument("--bcast", default="255.255.255.255", help="Địa chỉ UDP broadcast")
    parser.add_argument("--downloads", default="downloads", help="Thư mục file tải về")
    args = parser.parse_args()
    try:
        Console(args.name.strip(), args.port, args.bcast, args.downloads).run()
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"[!] Không thể khởi động: {exc}\n")


if __name__ == "__main__":
    main()
