# LAN Chat & File Sharing

A peer-to-peer LAN messenger with a lightweight **Tkinter GUI by default** and an optional terminal client. Both interfaces use the same UDP discovery, TCP chat and file-transfer protocol. No central server or saved chat history.

## Requirements

- Python **3.10+** on Windows or Linux.
- Two computers on the same LAN, with UDP broadcasts and incoming TCP connections allowed by the firewall.
- `python -m pip install -r requirements.txt` (for the CLI's `prompt_toolkit`).
- Tkinter for GUI mode: usually included with Python on Windows. On Linux install the OS package if missing (`python3-tk` on Debian/Ubuntu, `tk` on Arch/CachyOS).

## Run

Start the app without configuration flags to enter startup settings. The GUI opens
a form with name and TCP port. Expand **Cài đặt nâng cao** to set the broadcast
address and downloads folder. In the terminal, press Enter to accept each optional
default or Ctrl+C to cancel setup.

```bash
# GUI setup (default)
python main.py

# Terminal setup
python main.py --nogui

# Skip setup and open chat directly
python main.py --name Khang
python main.py --nogui --name Huy --port 5001

# Other shared options
python main.py --name Khang --port 5001 --bcast 192.168.1.255 --downloads ./received
```

When passing any configuration flag, include `--name`. Omitted optional flags use
their defaults. `--nogui` selects the terminal interface and still opens setup
when used by itself.

| Argument | Meaning | Default |
| --- | --- | --- |
| `--name NAME` | Display name, 1–60 characters | Required |
| `--port PORT` | TCP listening port | `0` (assigned by the OS) |
| `--bcast ADDRESS` | UDP broadcast destination | `255.255.255.255` |
| `--downloads PATH` | Directory for received files | `downloads` |
| `--nogui` | Force terminal interface | Off |

If Tkinter is unavailable or the display cannot be initialized, the program
falls back to the CLI when an interactive terminal is available. The CLI uses
configuration flags if provided and prompts for settings otherwise.

### GUI

- Select an online peer in the sidebar; the TCP connection is opened in a background worker.
- Type a message and press **Enter** or click **Gửi**.
- Use **Đính kèm** to choose a file. The progress bar shows the most recent transfer for the selected peer.
- The peer list displays online/away status and unread message counts. Offline peers previously seen in this session are shown in gray so you can still inspect their in-memory conversation.
- Close the window to quit and close network connections. Closing during an active transfer cancels it.

Name and network settings are configured at startup. Click the status button in the top right to switch between **Trực tuyến** and **Vắng mặt** during a session.

### CLI commands

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

## Two-machine testing

The OS assigns a free TCP port by default, including when you run two instances on the same computer. To use fixed TCP ports for a same-computer test, choose a different port for each instance:

```bash
python main.py --name Khang --port 5001 --bcast 127.255.255.255
python main.py --nogui --name Huy --port 5002 --bcast 127.255.255.255
```

Multiple UDP listeners bound to port `9999` on the same host depend on the OS's socket reuse semantics. A real two-computer LAN test is recommended. Capture `udp.port == 9999` for discovery broadcasts and `tcp.port == 5001` for the TCP three-way handshake in Wireshark, substituting the actual listening port.

## Networking and storage

- UDP: JSON `HELLO` datagram with `id`, `name`, `port`, `status`; broadcast every **3 seconds** on UDP port **9999**. Peer timeout is **10 seconds**.
- TCP: 4-byte unsigned big-endian JSON frame length followed by UTF-8 JSON. Maximum frame: 256 KiB.
- Chat: TCP `HELLO` handshake, then `MSG` / `BYE` frames.
- Files: independent TCP connection, `FILE_META`, raw bytes, and `FILE_ACK` upon successful save. Received files are written via temporary `.part` files and renamed only when complete. Name collisions get suffixes like `(1)`.
- Peers get a fresh random UUID on each launch. A restarted peer is a **new session**.
- **Messages exist only in RAM. Quitting permanently clears local chat history.** Received files remain in the configured download folder.
- Traffic is not encrypted; this is a LAN networking assignment, not a secure messenger.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py lanchat
```

For the final live demo, verify **GUI ↔ GUI**, **GUI ↔ CLI** and **CLI ↔ CLI** on two machines. Ensure that firewalls allow UDP/9999 and the configured TCP port.

## Packaging

Build on each target OS with PyInstaller; builds are OS-specific:

```bash
python -m pip install pyinstaller
python -m PyInstaller --onefile --name LANChat main.py
```

Use a **console-enabled executable** so command-line arguments, `--nogui` and CLI fallback remain usable. Launch it from a terminal, e.g. `./dist/LANChat --name Khang` (or `dist\\LANChat.exe --name Khang` on Windows). A Windows `--windowed` build cannot provide an interactive CLI fallback.
