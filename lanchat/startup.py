"""Configuration shared by the command line and both startup interfaces."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StartupConfig:
    name: str
    port: int = 0
    bcast: str = "255.255.255.255"
    downloads: str = "downloads"


def parse_name(value):
    name = value.strip()
    if not 1 <= len(name) <= 60:
        raise ValueError("Tên hiển thị phải có từ 1 đến 60 ký tự.")
    return name


def parse_port(value):
    try:
        port = int(value)
    except ValueError:
        raise ValueError("Cổng TCP phải là số nguyên từ 0 đến 65535.") from None
    if not 0 <= port <= 65535:
        raise ValueError("Cổng TCP phải nằm trong khoảng từ 0 đến 65535.")
    return port
