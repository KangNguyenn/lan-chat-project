# LAN Chat & File Sharing (CLI)

Peer-to-peer LAN chat using native Python TCP and UDP sockets. No central server and no GUI.

## Requirements

- Python **3.10+** on Windows or Linux
- Machines on the same LAN/Wi-Fi with UDP broadcasts and TCP connections permitted by the firewall
- Install the only CLI dependency: `python -m pip install -r requirements.txt`

## Run

On different computers, **the same TCP port is fine**, because each has a different IP:

```bash
python main.py --name Khang --port 5000
python main.py --name Minh --port 5000
```

On one computer, use **different TCP ports**, for example:

```bash
python main.py --name Khang --port 5001 --bcast 127.255.255.255
python main.py --name Minh --port 5002 --bcast 127.255.255.255
```

A single machine with several UDP sockets bound to `9999` depends on OS socket reuse semantics; test the behavior on your OS. Use the same LAN and two real computers for the final demo.

UDP discovery sends JSON presence every **3 seconds** to UDP port **9999**. Peers disappear after **10 seconds** without a heartbeat.

## Console commands

| Command | Description |
| --- | --- |
| `/list` | Show online users with number, name, IP and status |
| `/chat <name\|number>` | Open a chat with the selected user (TCP connection) |
| `<any text>` | Send a message to the current chat partner |
| `/send <file>` | Send a file to the current chat partner |
| `/leave` | Close the current chat |
| `/status <online\|away>` | Change your status (sent via UDP) |
| `/help` | Show all commands |
| `/quit` | Exit the program |

All built-in CLI messages, help text, status notifications, and errors are in English. User messages and display names are transmitted without translation. The CLI uses `prompt_toolkit` to redraw an unfinished input line when notifications arrive. Messages from other peers are retained with unread counts until you select that chat.

Downloaded files are written in `downloads/`. Transfers use unique temporary `.part` files and only publish a completed file. If a filename already exists, `(1)`, `(2)` etc. is appended.

## Protocol

- UDP: one JSON datagram with `{type:"HELLO",id,name,port,status}`; `id` is a random per-instance ID so two peers can have the same name or IP.
- TCP: 4-byte unsigned big-endian JSON payload length + UTF-8 JSON object. The maximum JSON frame is 256 KiB.
- TCP chat session: `HELLO` handshake identifying peer ID and kind `chat`, then `MSG`, `BYE`.
- TCP file session: separate TCP connection to the same listening port; `HELLO` with kind `file`, `FILE_META` JSON, raw file stream of exactly the announced size, `FILE_ACK` upon successful save.
- Every peer listens for inbound TCP connections; no central chat server is used.

## Tests

Run local automated tests:

```bash
python -m unittest discover -s tests -v
```

For the required live demo, test **two real computers** on the same Wi-Fi/LAN, while capturing UDP broadcast traffic and TCP 3-way handshake in Wireshark. Windows Firewall (or Linux firewall) must allow inbound UDP/9999 and TCP on your selected port.

## Known constraints

- A LAN assignment, not secure against malicious LAN peers; data is not encrypted.
- Does not relay traffic across routers, NATs, VPNs, or isolated Wi-Fi clients.
- Each process requires its own listening TCP port if they share a host/IP. Two different computers can use port `5000` simultaneously.
- Discovery on one host using `127.255.255.255` is platform dependent. Use two actual computers for final verification.
- Terminal UI requires `prompt_toolkit` (installed above). No GUI is included.

## Project report checklist

Include architecture and threading diagrams, UDP/TCP message formats, troubleshooting decisions, test scenarios, Wireshark screenshots for UDP broadcast and TCP handshake, and a 10-minute demo using two computers.
