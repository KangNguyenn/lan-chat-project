LAN CHAT - QUICK START

INSTALL
1. Install Python 3.10+ (Windows or Linux).
2. Run: python -m pip install -r requirements.txt
3. For GUI on Linux, install Tkinter if needed:
   Ubuntu/Debian: sudo apt install python3-tk
   Arch/CachyOS: sudo pacman -S tk

RUN
GUI (default): python main.py --name Alice
CLI:           python main.py --name Bob --nogui
Optional flags: --port 5001 --bcast 192.168.1.255 --downloads ./received
--name is required. Use different TCP ports for two instances on one PC.

TEST
Automated: python -m unittest discover -s tests -v
Manual: Run two peers on the same LAN; test chat and file transfer
        with GUI-GUI, GUI-CLI, and CLI-CLI.
Wireshark: udp.port == 9999 (discovery)
           tcp.port == 5000 (TCP handshake; adjust if using --port)
Allow UDP 9999 and the chosen TCP port through the firewall.
