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
        raise ValueError("Display name must contain 1 to 60 characters")
    return name


def parse_port(value):
    try:
        port = int(value)
    except ValueError:
        raise ValueError("TCP port must be an integer between 0 and 65535") from None
    if not 0 <= port <= 65535:
        raise ValueError("TCP port must be between 0 and 65535")
    return port
