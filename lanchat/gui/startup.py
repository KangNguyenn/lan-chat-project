"""Tkinter startup settings shown before opening the chat window."""
import tkinter as tk
from tkinter import filedialog, ttk

from ..startup import StartupConfig, parse_name, parse_port


class StartupForm(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=24)
        self.root = root
        self.config = None
        self.name = tk.StringVar(master=root)
        self.port = tk.StringVar(master=root, value=str(StartupConfig.port))
        self.bcast = tk.StringVar(master=root, value=StartupConfig.bcast)
        self.downloads = tk.StringVar(master=root, value=StartupConfig.downloads)
        self.error = tk.StringVar(master=root)

        root.title("LAN Chat")
        root.minsize(480, 1)
        root.protocol("WM_DELETE_WINDOW", self.cancel)
        root.bind("<Escape>", self.cancel)
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Khởi động LAN Chat", font=("TkDefaultFont", 18, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 16))
        self.name_entry = self._add_entry(self, 1, "Tên hiển thị", self.name)
        self.port_entry = self._add_entry(self, 3, "Cổng TCP lắng nghe", self.port)
        ttk.Label(self, text="Nhập 0 để tự động chọn cổng.").grid(
            row=5, column=0, sticky="w")

        self.advanced_button = ttk.Button(self, text="▸ Cài đặt nâng cao", command=self._toggle_advanced)
        self.advanced_button.grid(row=6, column=0, sticky="w", pady=(16, 8))
        self.advanced = ttk.Frame(self, padding=(12, 4))
        self.advanced.columnconfigure(0, weight=1)
        self.advanced.grid(row=7, column=0, sticky="ew")
        self._add_entry(self.advanced, 0, "Địa chỉ quảng bá UDP", self.bcast)
        self._add_entry(self.advanced, 2, "Thư mục lưu tệp nhận", self.downloads)
        ttk.Button(self.advanced, text="Chọn…", command=self._browse).grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(3, 8))
        self.advanced.grid_remove()

        ttk.Label(self, textvariable=self.error, foreground="#b3261e", wraplength=420).grid(
            row=8, column=0, sticky="w")
        actions = ttk.Frame(self)
        actions.grid(row=9, column=0, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Hủy", command=self.cancel).pack(side="left")
        ttk.Button(actions, text="Bắt đầu", command=self._submit).pack(side="left", padx=(8, 0))
        self.name_entry.focus_set()

    def _add_entry(self, parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row + 1, column=0, sticky="ew", pady=(3, 8))
        entry.bind("<Return>", self._submit)
        return entry

    def _toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.grid_remove()
            self.advanced_button.configure(text="▸ Cài đặt nâng cao")
        else:
            self.advanced.grid()
            self.advanced_button.configure(text="▾ Cài đặt nâng cao")

    def _browse(self):
        directory = filedialog.askdirectory(parent=self.root, title="Chọn thư mục lưu tệp nhận")
        if directory:
            self.downloads.set(directory)

    def show_error(self, message):
        self.error.set(message)

    def _submit(self, event=None):
        try:
            name = parse_name(self.name.get())
        except ValueError as exc:
            self.show_error(str(exc))
            self.name_entry.focus_set()
            return
        try:
            port = parse_port(self.port.get() or StartupConfig.port)
        except ValueError as exc:
            self.show_error(str(exc))
            self.port_entry.focus_set()
            return

        self.config = StartupConfig(
            name, port,
            self.bcast.get() or StartupConfig.bcast,
            self.downloads.get() or StartupConfig.downloads,
        )
        self.root.quit()

    def cancel(self, event=None):
        self.config = None
        self.root.quit()

    def destroy(self):
        self.root.unbind("<Escape>")
        super().destroy()
