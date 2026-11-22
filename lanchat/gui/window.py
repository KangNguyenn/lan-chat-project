"""Compact Tkinter chat interface; all network I/O is delegated to ChatController."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk

from ..peers import PRESENCE_LABELS


ACTION_ERRORS = {
    "connect": "Không thể kết nối với người dùng này.",
    "send message": "Không thể gửi tin nhắn.",
    "send file": "Không thể gửi tệp đã chọn.",
}


class LanChatWindow:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.app = controller.app
        self.selected_id = None
        self.known_peers = {}
        self.transfers = {}
        self.closed = False
        self.stop_thread = None

        root.title(f"LAN Chat — {self.app.name}")
        root.geometry("880x570")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        outer = ttk.Frame(root, padding=(12, 8))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)
        heading = ttk.Frame(outer)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(heading, text="LAN Chat", font=("TkDefaultFont", 16, "bold")).pack(side="left")
        self.presence_button = ttk.Button(heading, width=12,
                                          text=PRESENCE_LABELS[self.app.get_status()],
                                          command=self._toggle_presence)
        self.presence_button.pack(side="right")
        ttk.Label(heading, text=self.app.name).pack(side="right", padx=(8, 8))

        split = ttk.Panedwindow(outer, orient="horizontal")
        split.grid(row=1, column=0, sticky="nsew")
        sidebar = ttk.Frame(split, padding=(0, 2, 6, 0))
        chat = ttk.Frame(split, padding=(9, 2, 0, 0))
        split.add(sidebar, weight=1)
        split.add(chat, weight=3)
        sidebar.rowconfigure(1, weight=1)
        sidebar.columnconfigure(0, weight=1)
        chat.rowconfigure(2, weight=1)
        chat.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="Người dùng", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self.peer_list = ttk.Treeview(sidebar, columns=("status", "unread"),
                                     show="tree headings", selectmode="browse", height=4)
        self.peer_list.heading("#0", text="Tên")
        self.peer_list.heading("status", text="Trạng thái")
        self.peer_list.heading("unread", text="Tin mới")
        self.peer_list.column("#0", minwidth=90, width=125)
        header_font = font.nametofont("TkHeadingFont", root=root)
        status_width = max(map(header_font.measure, ("Trạng thái", *PRESENCE_LABELS.values()))) + 16
        unread_width = header_font.measure("Tin mới") + 16
        self.peer_list.column("status", minwidth=status_width, width=status_width, stretch=False)
        self.peer_list.column("unread", minwidth=unread_width, width=unread_width,
                              stretch=False, anchor="center")
        self.peer_list.tag_configure("offline", foreground="#888888")
        self.peer_list.grid(row=1, column=0, sticky="nsew")
        peer_scroll = ttk.Scrollbar(sidebar, orient="vertical", command=self.peer_list.yview)
        peer_scroll.grid(row=1, column=1, sticky="ns")
        self.peer_list.configure(yscrollcommand=peer_scroll.set)
        self.peer_list.bind("<<TreeviewSelect>>", self._select_peer)

        self.peer_title = tk.StringVar(value="Chọn người dùng để bắt đầu trò chuyện")
        self.peer_address = tk.StringVar(value="")
        ttk.Label(chat, textvariable=self.peer_title,
                  font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, sticky="ew")
        ttk.Label(chat, textvariable=self.peer_address).grid(
            row=1, column=0, sticky="ew", pady=(0, 4))

        transcript = ttk.Frame(chat)
        transcript.grid(row=2, column=0, sticky="nsew")
        transcript.rowconfigure(0, weight=1)
        transcript.columnconfigure(0, weight=1)
        self.messages = tk.Text(transcript, wrap="word", state="disabled", relief="flat",
                                width=1, height=3, padx=12, pady=6,
                                borderwidth=1, highlightthickness=1)
        self.messages.tag_configure("outgoing", justify="right", foreground="#1766bb",
                                     spacing1=8, spacing3=5)
        self.messages.tag_configure("incoming", justify="left", spacing1=8, spacing3=5)
        self.messages.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(transcript, orient="vertical", command=self.messages.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.messages.configure(yscrollcommand=scroll.set)

        transfer = ttk.Frame(chat)
        transfer.grid(row=3, column=0, sticky="ew", pady=(4, 2))
        transfer.columnconfigure(0, weight=1)
        self.transfer_text = tk.StringVar(value="")
        ttk.Label(transfer, textvariable=self.transfer_text).grid(row=0, column=0, sticky="ew")
        self.transfer_bar = ttk.Progressbar(transfer, maximum=100, length=120)
        self.transfer_bar.grid(row=0, column=1)

        controls = ttk.Frame(chat)
        controls.grid(row=4, column=0, sticky="ew", pady=(2, 0))
        controls.columnconfigure(1, weight=1)
        self.attach_button = ttk.Button(controls, text="Đính kèm", command=self._attach,
                                        state="disabled")
        self.attach_button.grid(row=0, column=0)
        self.message_input = ttk.Entry(controls, width=1, state="disabled")
        self.message_input.grid(row=0, column=1, sticky="ew", padx=8)
        self.message_input.bind("<Return>", self._send)
        self.send_button = ttk.Button(controls, text="Gửi", command=self._send,
                                      state="disabled")
        self.send_button.grid(row=0, column=2)

        self.status_text = tk.StringVar(value=f"Đang tìm người dùng trong mạng nội bộ… (TCP {self.app.port})")
        ttk.Label(outer, textvariable=self.status_text).grid(
            row=2, column=0, sticky="ew", pady=(4, 0))
        root.update_idletasks()
        root.minsize(620, root.winfo_reqheight())
        self._tick()

    def _toggle_presence(self):
        status = "away" if self.app.get_status() == "online" else "online"
        self.app.set_status(status)
        self.presence_button.configure(text=PRESENCE_LABELS[status])
        self.status_text.set(f"Trạng thái của bạn: {PRESENCE_LABELS[status]}")

    def _sync_peers(self):
        peers = self.app.peers.list()
        online = {p.peer_id: p for p in peers}
        for peer in peers:
            self.known_peers[peer.peer_id] = (peer.name, peer.ip, peer.port, peer.status)
        unread = self.app.chats.unread_counts()
        for peer_id, (name, ip, port, status) in list(self.known_peers.items()):
            if peer_id not in online:
                status = "offline"
                self.known_peers[peer_id] = (name, ip, port, status)
            values = (PRESENCE_LABELS[status], unread.get(peer_id, 0) or "")
            tags = ("offline",) if status == "offline" else ()
            if self.peer_list.exists(peer_id):
                self.peer_list.item(peer_id, text=name, values=values, tags=tags)
            else:
                self.peer_list.insert("", "end", iid=peer_id, text=name,
                                      values=values, tags=tags)
        self._update_header()

    def _update_header(self):
        if self.selected_id is None:
            return
        peer = self.known_peers.get(self.selected_id)
        if not peer:
            return
        name, ip, port, status = peer
        self.peer_title.set(name)
        self.peer_address.set(f"{ip}:{port}  •  {PRESENCE_LABELS[status]}")
        online = status != "offline"
        self.message_input.configure(state="normal" if online else "disabled")
        self.send_button.configure(state="normal" if online else "disabled")
        self.attach_button.configure(state="normal" if online else "disabled")

    def _select_peer(self, _event=None):
        selection = self.peer_list.selection()
        if not selection:
            return
        self.selected_id = selection[0]
        self.controller.select(self.selected_id)
        self._update_header()
        self._show_messages(scroll=True)
        self._show_transfer()
        if self.known_peers[self.selected_id][3] != "offline":
            self.message_input.focus_set()

    def _show_messages(self, scroll=False):
        if self.selected_id is None:
            return
        near_bottom = self.messages.yview()[1] > 0.96
        history = self.app.chats.snapshot(self.selected_id)
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        for name, message, direction in history:
            label = "Bạn" if direction == "outgoing" else name
            self.messages.insert("end", f"{label}: {message}\n", direction)
        self.messages.configure(state="disabled")
        if scroll or near_bottom:
            self.messages.see("end")

    def _show_transfer(self):
        state = self.transfers.get(self.selected_id)
        if state is None:
            self.transfer_text.set("")
            self.transfer_bar.configure(value=0)
            return
        self.transfer_text.set(state["text"])
        self.transfer_bar.configure(value=state["percent"])

    def _send(self, _event=None):
        if self.selected_id is None or self.app.peers.get(self.selected_id) is None:
            return "break"
        content = self.message_input.get()
        if not content.strip():
            return "break"
        self.message_input.delete(0, "end")
        self.controller.send_message(self.selected_id, content)
        return "break"

    def _attach(self):
        if self.selected_id is None or self.app.peers.get(self.selected_id) is None:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Chọn tệp cần gửi")
        if path:
            self.controller.send_file(self.selected_id, path)

    def _handle_event(self, event):
        kind = event["type"]
        if kind == "peer_status":
            self.status_text.set(f"{event['name']}: {PRESENCE_LABELS[event['status']]}")
        elif kind == "discovery_error":
            self.status_text.set("Không thể gửi gói quảng bá UDP. Hãy kiểm tra địa chỉ quảng bá.")
        elif kind == "incoming_error":
            self.status_text.set(f"Không thể thiết lập kết nối TCP từ {event['ip']}.")
        elif kind in ("message_received", "message_sent"):
            if kind == "message_received" and event["unread"]:
                self.status_text.set(f"{event['name']} có {event['unread']} tin nhắn chưa đọc.")
            if kind == "message_received" and event["peer_id"] == self.selected_id:
                self.app.chats.select(self.selected_id)
            if event["peer_id"] == self.selected_id:
                self._show_messages()
        elif kind in ("transfer_started", "transfer_progress", "transfer_completed", "transfer_failed"):
            peer_id = event["peer_id"]
            previous = self.transfers.get(peer_id, {"percent": 0})
            name = event["name"]
            direction = "Gửi" if event["direction"] == "Sending" else "Nhận"
            if kind == "transfer_started":
                percentage = 0
                text = f"{direction} {name}: 0%"
                active = True
            elif kind == "transfer_progress":
                percentage = event["percent"]
                text = f"{direction} {name}: {percentage}%"
                active = True
            elif kind == "transfer_completed":
                percentage = 100
                text = f"{direction} {name}: hoàn tất"
                self.status_text.set(text)
                active = False
            else:
                percentage = previous["percent"]
                text = f"{direction} {name}: thất bại"
                self.status_text.set(text)
                active = False
            self.transfers[peer_id] = {"percent": percentage, "text": text,
                                        "active": active}
            if peer_id == self.selected_id:
                self._show_transfer()
        elif kind == "action_error":
            self.status_text.set(ACTION_ERRORS[event["action"]])
            if event.get("action") == "send message":
                if (event.get("peer_id") == self.selected_id
                        and not self.message_input.get()):
                    self.message_input.insert(0, event.get("message", ""))
        elif kind == "connection_closed":
            self.status_text.set("Đã đóng kết nối trò chuyện.")

    def _tick(self):
        if self.closed:
            return
        try:
            for _ in range(200):
                try:
                    event = self.controller.events.get_nowait()
                except queue.Empty:
                    break
                self._handle_event(event)
        finally:
            self._sync_peers()
            self.root.after(150, self._tick)

    def close(self):
        if self.closed:
            return
        if any(info["active"] for info in self.transfers.values()):
            if not messagebox.askyesno("Thoát LAN Chat",
                                       "Đang truyền tệp. Bạn có muốn hủy và thoát không?",
                                       parent=self.root):
                return
        self.closed = True
        self.presence_button.state(["disabled"])
        self.message_input.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.attach_button.configure(state="disabled")
        self.status_text.set("Đang đóng các kết nối…")
        self.stop_thread = threading.Thread(target=self.controller.stop, daemon=True)
        self.stop_thread.start()
        self._wait_for_shutdown()

    def _wait_for_shutdown(self):
        if self.stop_thread.is_alive():
            self.root.after(100, self._wait_for_shutdown)
        else:
            self.root.destroy()
