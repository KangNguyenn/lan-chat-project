LAN CHAT - QUICK START

INSTALL
1. Install Python 3.10+ (Windows or Linux).
2. Run: python -m pip install -r requirements.txt
3. For GUI on Linux, install Tkinter if needed:
   Ubuntu/Debian: sudo apt install python3-tk
   Arch/CachyOS: sudo pacman -S tk

RUN
GUI setup:      python main.py
Terminal setup: python main.py --nogui
Skip setup:     python main.py --name Alice
Skip setup CLI: python main.py --nogui --name Bob --port 5001
Optional flags: --port 5001 --bcast 192.168.1.255 --downloads ./received
When passing any configuration flag, include --name.
The default TCP port is 0 (assigned by the OS). Use --port to choose a fixed port.

TEST
Automated: python -m unittest discover -s tests -v
Manual: Run two peers on the same LAN; test chat and file transfer
        with GUI-GUI, GUI-CLI, and CLI-CLI.
Wireshark: udp.port == 9999 (discovery)
           tcp.port == 5001 (TCP handshake example; substitute the actual listening port)
Allow UDP 9999 and the chosen TCP port through the firewall.
