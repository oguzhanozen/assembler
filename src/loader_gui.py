import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.host_loader import (
    HostLoader,
    HostLoaderError,
    list_serial_ports,
    open_serial,
    validate_target_image,
)
from src.loader_image import LoaderImageError, read_loader_image
from src.loader_protocol import ProtocolError
from src.project_paths import FPGA_OUTPUT_DIR, LOADER_OUTPUT_DIR


class LoaderWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("PicoRV FPGA UART Loader")
        self.window.geometry("680x470")
        self.window.minsize(620, 420)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.events = queue.Queue()
        self.busy = False
        self.closed = False

        self.port_var = tk.StringVar()
        self.image_var = tk.StringVar(value=self.default_image_path())
        self.status_var = tk.StringVar(value="Hazır")
        self.progress_var = tk.IntVar(value=0)

        self.build_ui()
        self.refresh_ports()
        self.window.after(50, self.process_events)

    def default_image_path(self):
        image_path = os.path.join(LOADER_OUTPUT_DIR, "program.picoimg")
        return image_path if os.path.exists(image_path) else ""

    def build_ui(self):
        content = ttk.Frame(self.window, padding=12)
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(6, weight=1)

        info = (
            "Not: Kart yeniden takıldıysa önce Gowin Programmer ile "
            "outputs/fpga/picorv_loader.fs dosyasını SRAM'e yükleyin."
        )
        ttk.Label(content, text=info, foreground="#8a4b08", wraplength=620).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        ttk.Label(content, text="Seri Port:").grid(row=1, column=0, sticky="w", pady=5)
        self.port_combo = ttk.Combobox(content, textvariable=self.port_var, state="readonly")
        self.port_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        self.refresh_button = ttk.Button(content, text="Portları Yenile", command=self.refresh_ports)
        self.refresh_button.grid(row=1, column=2, sticky="ew", pady=5)

        ttk.Label(content, text="Loader Image:").grid(row=2, column=0, sticky="w", pady=5)
        self.image_entry = ttk.Entry(content, textvariable=self.image_var)
        self.image_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=5)
        self.browse_button = ttk.Button(content, text="Seç...", command=self.select_image)
        self.browse_button.grid(row=2, column=2, sticky="ew", pady=5)

        actions = ttk.Frame(content)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 5))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.ping_button = ttk.Button(actions, text="Bağlantıyı Test Et", command=self.start_ping)
        self.ping_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.load_button = ttk.Button(actions, text="FPGA'ya Yükle ve Çalıştır", command=self.start_load)
        self.load_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.progress = ttk.Progressbar(content, variable=self.progress_var, maximum=100)
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 3))
        ttk.Label(content, textvariable=self.status_var).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        log_frame = ttk.LabelFrame(content, text="İşlem Günlüğü", padding=6)
        log_frame.grid(row=6, column=0, columnspan=3, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def refresh_ports(self):
        try:
            ports = list_serial_ports()
        except HostLoaderError as exc:
            self.log(f"Portlar listelenemedi: {exc}")
            return

        current = self.port_var.get()
        port_names = [port.device for port in ports]
        self.port_combo["values"] = port_names
        if current in port_names:
            self.port_var.set(current)
        elif port_names:
            self.port_var.set(port_names[0])
        else:
            self.port_var.set("")
        descriptions = ", ".join(f"{port.device} ({port.description})" for port in ports)
        self.log(f"Seri portlar: {descriptions or 'bağlı port bulunamadı'}")

    def select_image(self):
        selected = filedialog.askopenfilename(
            parent=self.window,
            title="Loader Image Seç",
            initialdir=LOADER_OUTPUT_DIR,
            filetypes=[("PicoRV Loader Image", "*.picoimg"), ("All Files", "*.*")],
        )
        if selected:
            self.image_var.set(os.path.abspath(selected))
            self.log(f"Image seçildi: {selected}")

    def start_ping(self):
        self.start_operation("Bağlantı test ediliyor...", self.ping_worker)

    def start_load(self):
        image_path = self.image_var.get().strip()
        if not image_path:
            messagebox.showwarning("Loader Image", "Yüklenecek .picoimg dosyasını seçin.", parent=self.window)
            return
        self.start_operation("Image doğrulanıyor ve yükleniyor...", self.load_worker, image_path)

    def start_operation(self, status, worker, *args):
        if self.busy:
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Seri Port", "Kullanılacak seri portu seçin.", parent=self.window)
            return
        self.set_busy(True)
        self.progress_var.set(0)
        self.status_var.set(status)
        self.log(status)
        threading.Thread(target=worker, args=(port, *args), daemon=True).start()

    def ping_worker(self, port):
        try:
            with open_serial(port, 115200, 1.0) as stream:
                HostLoader(stream).ping()
            self.events.put(("success", f"{port} bağlantısı hazır. PING ACK alındı."))
        except (HostLoaderError, LoaderImageError, ProtocolError, OSError, ValueError) as exc:
            self.events.put(("error", str(exc)))

    def load_worker(self, port, image_path):
        try:
            image = read_loader_image(image_path)
            validate_target_image(image)
            total = sum(len(segment["data"]) for segment in image["segments"])
            self.events.put(
                (
                    "log",
                    f"Image geçerli: {len(image['segments'])} segment, "
                    f"{total} byte, entry=0x{image['entry']:08X}",
                )
            )
            with open_serial(port, 115200, 1.0) as stream:
                loader = HostLoader(
                    stream,
                    progress=lambda sent, size: self.events.put(("progress", sent, size)),
                )
                loader.ping()
                result = loader.load_image(image)
            self.events.put(
                (
                    "success",
                    f"Yükleme tamamlandı: {result['bytes_sent']} byte, "
                    f"{result['segments']} segment, entry=0x{result['entry']:08X}",
                )
            )
        except (HostLoaderError, LoaderImageError, ProtocolError, OSError, ValueError) as exc:
            self.events.put(("error", str(exc)))

    def process_events(self):
        if self.closed:
            return
        try:
            while True:
                event = self.events.get_nowait()
                event_type = event[0]
                if event_type == "log":
                    self.log(event[1])
                elif event_type == "progress":
                    sent, total = event[1], event[2]
                    percent = int(sent * 100 / total) if total else 100
                    self.progress_var.set(percent)
                    self.status_var.set(f"Gönderiliyor: {sent}/{total} byte")
                elif event_type == "success":
                    self.progress_var.set(100)
                    self.status_var.set(event[1])
                    self.log(event[1])
                    self.set_busy(False)
                elif event_type == "error":
                    message = self.explain_error(event[1])
                    self.status_var.set("İşlem başarısız.")
                    self.log(f"HATA: {message}")
                    self.set_busy(False)
                    messagebox.showerror("FPGA Loader Hatası", message, parent=self.window)
        except queue.Empty:
            pass
        if not self.closed:
            self.window.after(50, self.process_events)

    def set_busy(self, busy):
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.refresh_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.ping_button.configure(state=state)
        self.load_button.configure(state=state)
        self.port_combo.configure(state="disabled" if busy else "readonly")
        self.image_entry.configure(state=state)

    def explain_error(self, message):
        if "UART yanıtı beklenirken timeout oluştu" in message:
            return (
                f"{message}\n\n"
                "COM port açıldı ancak FPGA loader yanıt vermedi. Kart yeniden takıldıysa "
                "SRAM bitstreami silinmiştir. Önce Gowin Programmer ile "
                f"'{os.path.join(FPGA_OUTPUT_DIR, 'picorv_loader.fs')}' dosyasını SRAM'e yükleyin, "
                "sonra bağlantıyı tekrar test edin."
            )
        return message

    def log(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def focus(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self):
        if self.busy:
            messagebox.showwarning(
                "İşlem Devam Ediyor",
                "UART işlemi tamamlanmadan loader penceresi kapatılamaz.",
                parent=self.window,
            )
            return
        self.closed = True
        self.window.destroy()
