import json
import os
import re
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.assembler import PicoRVAssembler, opcode_table
from src.linker import PicoRVLinker


@dataclass
class EditorTab:
    frame: tk.Frame
    editor: tk.Text
    line_numbers: tk.Text
    scrollbar: tk.Scrollbar
    file_path: Optional[str]
    title: str
    dirty: bool = False
    error_output: str = ""
    symbol_output: str = ""
    object_output: str = ""


class AssemblerApp:
    def __init__(self, root):
        self.root = root
        self.editor_tabs = {}
        self.close_button_element = "CloseButton"
        self.root.title("PicoRV32I Assembler IDE")
        self.root.geometry("980x650")
        self.root.minsize(900, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.style = ttk.Style(self.root)
        self.setup_closable_tabs()

        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Yeni", command=self.new_file)
        file_menu.add_command(label="Aç (.asm)...", command=self.load_asm_file)
        file_menu.add_command(label="Kaydet", command=self.save_asm_file)
        file_menu.add_command(label="Farklı Kaydet...", command=self.save_asm_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.close_app)
        menubar.add_cascade(label="Dosya", menu=file_menu)

        linker_menu = tk.Menu(menubar, tearoff=0)
        linker_menu.add_command(label="Object Dosyalarını Linkle...", command=self.link_object_files)
        menubar.add_cascade(label="Linker", menu=linker_menu)

        self.root.config(menu=menubar)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)

        left_frame = tk.Frame(root, padx=10, pady=10)
        left_frame.grid(row=0, column=0, sticky="nsew")

        right_frame = tk.Frame(root, padx=10, pady=10)
        right_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(
            left_frame,
            text="Assembly Kodunu Buraya Yazın:",
            font=("Arial", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 2))

        legend_frame = tk.Frame(left_frame)
        legend_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(legend_frame, text="Renkler:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(legend_frame, text="Opcode", fg="blue", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Label", fg="red", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Direktif", fg="purple", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Register", fg="darkorange", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Sayı", fg="teal", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Yorum", fg="gray", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        self.tab_frame = tk.Frame(left_frame)
        self.tab_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.notebook = ttk.Notebook(self.tab_frame, style="Closable.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.notebook.bind("<Button-1>", self.on_notebook_click)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_assemble = tk.Button(
            btn_frame,
            text="Kodu Çevir (Assemble)",
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            command=self.run_assembler,
        )
        self.btn_assemble.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Hata Mesajları:", font=("Arial", 10, "bold"), fg="red").pack(anchor=tk.W)
        self.error_text = tk.Text(right_frame, width=40, height=6, font=("Courier New", 10), bg="#ffe6e6")
        self.error_text.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Symbol Table (Sembol Tablosu):", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.sym_text = tk.Text(right_frame, width=40, height=6, font=("Courier New", 10), bg="#f4f4f4")
        self.sym_text.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Object Code (Makine Kodu):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(5, 0))
        self.out_text = tk.Text(right_frame, width=40, height=12, font=("Courier New", 11), bg="#1e1e1e", fg="#00ff00")
        self.out_text.pack(fill=tk.BOTH, expand=True, pady=5)

        self.create_editor_tab()

    def setup_closable_tabs(self):
        self.close_button_images = {
            "normal": self.create_close_button_image("#ececec", "#b8b8b8", "#555555"),
            "active": self.create_close_button_image("#f7f7f7", "#8f8f8f", "#222222"),
            "pressed": self.create_close_button_image("#d6d6d6", "#777777", "#111111"),
        }

        if self.close_button_element not in self.style.element_names():
            self.style.element_create(
                self.close_button_element,
                "image",
                self.close_button_images["normal"],
                ("active", self.close_button_images["active"]),
                ("pressed", self.close_button_images["pressed"]),
                border=8,
                sticky="",
            )

        self.style.layout(
            "Closable.TNotebook.Tab",
            [
                (
                    "Notebook.tab",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Notebook.padding",
                                {
                                    "side": "top",
                                    "sticky": "nswe",
                                    "children": [
                                        (
                                            "Notebook.focus",
                                            {
                                                "side": "top",
                                                "sticky": "nswe",
                                                "children": [
                                                    ("Notebook.label", {"side": "left", "sticky": ""}),
                                                    (self.close_button_element, {"side": "left", "sticky": ""}),
                                                ],
                                            },
                                        )
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )
        self.style.configure("Closable.TNotebook.Tab", padding=(8, 3, 5, 3))

    def create_close_button_image(self, fill, border, mark):
        image = tk.PhotoImage(width=16, height=16)
        image.put(fill, to=(0, 0, 16, 16))

        for x in range(16):
            image.put(border, to=(x, 0))
            image.put(border, to=(x, 15))
        for y in range(16):
            image.put(border, to=(0, y))
            image.put(border, to=(15, y))

        for offset in range(2):
            for i in range(5, 11):
                image.put(mark, to=(i, i + offset))
                image.put(mark, to=(i, 15 - i - offset))
        return image

    def normalize_file_path(self, file_path):
        if not file_path:
            return None
        return os.path.normcase(os.path.abspath(file_path))

    def get_current_tab_id(self):
        selected = self.notebook.select()
        return selected if selected else None

    def get_current_tab_data(self):
        tab_id = self.get_current_tab_id()
        return self.editor_tabs.get(tab_id) if tab_id else None

    def get_tab_data(self, tab_id):
        return self.editor_tabs.get(str(tab_id)) if tab_id else None

    def is_active_tab(self, tab_data):
        return bool(tab_data and self.get_current_tab_id() == str(tab_data.frame))

    def find_tab_by_file_path(self, file_path):
        normalized_path = self.normalize_file_path(file_path)
        if not normalized_path:
            return None

        for tab_data in self.editor_tabs.values():
            if tab_data.file_path and self.normalize_file_path(tab_data.file_path) == normalized_path:
                return tab_data
        return None

    def get_next_untitled_title(self):
        used_numbers = set()
        for tab_data in self.editor_tabs.values():
            match = re.fullmatch(r"Untitled-(\d+)", tab_data.title)
            if match:
                used_numbers.add(int(match.group(1)))

        next_number = 1
        while next_number in used_numbers:
            next_number += 1
        return f"Untitled-{next_number}"

    def create_editor_tab(self, content="", file_path=None, title=None):
        normalized_path = os.path.abspath(file_path) if file_path else None
        tab = tk.Frame(self.notebook)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        editor_frame = tk.Frame(tab)
        editor_frame.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(editor_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        line_numbers = tk.Text(
            editor_frame,
            width=4,
            padx=5,
            takefocus=0,
            border=0,
            background="#f0f0f0",
            state="disabled",
            font=("Courier New", 12),
        )
        line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        input_text = tk.Text(
            editor_frame,
            wrap=tk.NONE,
            font=("Courier New", 12, "bold"),
            yscrollcommand=lambda *args, ln=line_numbers, sb=scrollbar: self.sync_scroll_set(ln, sb, *args),
        )
        input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=lambda *args, ed=input_text, ln=line_numbers: self.sync_scroll_get(ed, ln, *args))

        self.configure_editor_tags(input_text)
        input_text.insert("1.0", content)
        input_text.edit_modified(False)

        tab_title = title or (os.path.basename(normalized_path) if normalized_path else self.get_next_untitled_title())

        tab_data = EditorTab(
            frame=tab,
            editor=input_text,
            line_numbers=line_numbers,
            scrollbar=scrollbar,
            file_path=normalized_path,
            title=tab_title,
        )

        tab_id = str(tab)
        self.editor_tabs[tab_id] = tab_data
        input_text.bind("<<Modified>>", lambda event, key=tab_id: self.on_editor_modified(key))

        self.notebook.add(tab, text=self.get_display_tab_title(tab_data))
        self.notebook.select(tab)
        self.update_tab_editor(tab_id)
        self.render_tab_output(tab_data)
        self.refresh_window_title()
        return tab

    def configure_editor_tags(self, editor):
        editor.tag_config("opcode", foreground="blue")
        editor.tag_config("label", foreground="red")
        editor.tag_config("directive", foreground="purple")
        editor.tag_config("register", foreground="darkorange")
        editor.tag_config("number", foreground="teal")
        editor.tag_config("comment", foreground="gray")

    def sync_scroll_set(self, line_numbers, scrollbar, *args):
        scrollbar.set(*args)
        if args:
            line_numbers.yview_moveto(args[0])

    def sync_scroll_get(self, editor, line_numbers, *args):
        editor.yview(*args)
        line_numbers.yview(*args)

    def update_tab_editor(self, tab_id):
        tab_data = self.get_tab_data(tab_id)
        if not tab_data:
            return
        self.update_line_numbers(tab_data.editor, tab_data.line_numbers)
        self.highlight_syntax(tab_data.editor)

    def get_display_tab_title(self, tab_data):
        base_title = tab_data.title if tab_data else ""
        if tab_data and tab_data.dirty:
            base_title = f"*{base_title}"
        return base_title

    def update_tab_title(self, tab_data):
        if not tab_data:
            return
        try:
            self.notebook.tab(tab_data.frame, text=self.get_display_tab_title(tab_data))
        except tk.TclError:
            return
        self.refresh_window_title()

    def refresh_window_title(self):
        tab_data = self.get_current_tab_data()
        if not tab_data:
            self.root.title("PicoRV32I Assembler IDE")
            return

        dirty_prefix = "*" if tab_data.dirty else ""
        self.root.title(f"PicoRV32I Assembler IDE - {dirty_prefix}{tab_data.title}")

    def update_line_numbers(self, input_text, line_numbers):
        line_count = input_text.get("1.0", tk.END).count("\n")
        display_lines = max(20, line_count)
        line_numbers_string = "\n".join(str(i) for i in range(1, display_lines + 1))

        line_numbers.config(state=tk.NORMAL)
        line_numbers.delete("1.0", tk.END)
        line_numbers.insert("1.0", line_numbers_string)
        line_numbers.config(state=tk.DISABLED)
        line_numbers.yview_moveto(input_text.yview()[0])

    def highlight_syntax(self, input_text):
        for tag in ["opcode", "label", "directive", "register", "number", "comment"]:
            input_text.tag_remove(tag, "1.0", tk.END)

        opcode_pattern = r"\b(?:" + "|".join(opcode_table.keys()) + r")\b"
        lines = input_text.get("1.0", tk.END).split("\n")
        for i, line in enumerate(lines):
            line_num = i + 1
            comment_idx = line.find("#")
            if comment_idx != -1:
                input_text.tag_add("comment", f"{line_num}.{comment_idx}", f"{line_num}.end")
                line = line[:comment_idx]

            for match in re.finditer(r"^[ \t]*[a-zA-Z0-9_]+:", line):
                input_text.tag_add("label", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r"\.[a-zA-Z_]+", line):
                input_text.tag_add("directive", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(opcode_pattern, line):
                input_text.tag_add("opcode", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r"\bx[0-9]+\b", line):
                input_text.tag_add("register", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r"\b-?(?:0x[0-9a-fA-F]+|\d+)\b", line):
                input_text.tag_add("number", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")

    def on_editor_modified(self, tab_id):
        tab_data = self.get_tab_data(tab_id)
        if not tab_data or not tab_data.editor.edit_modified():
            return

        self.update_tab_editor(tab_id)
        tab_data.editor.edit_modified(False)
        if not tab_data.dirty:
            tab_data.dirty = True
            self.update_tab_title(tab_data)

    def on_tab_changed(self, event=None):
        tab_data = self.get_current_tab_data()
        if not tab_data:
            self.refresh_window_title()
            return

        self.update_tab_editor(str(tab_data.frame))
        self.update_tab_title(tab_data)
        self.render_tab_output(tab_data)
        self.refresh_window_title()

    def render_tab_output(self, tab_data=None):
        tab_data = tab_data or self.get_current_tab_data()
        self.error_text.delete("1.0", tk.END)
        self.sym_text.delete("1.0", tk.END)
        self.out_text.delete("1.0", tk.END)

        if not tab_data:
            return

        self.error_text.insert(tk.END, tab_data.error_output)
        self.sym_text.insert(tk.END, tab_data.symbol_output)
        self.out_text.insert(tk.END, tab_data.object_output)

    def set_tab_output(self, tab_data, error_output="", symbol_output="", object_output=""):
        if not tab_data:
            return

        tab_data.error_output = error_output
        tab_data.symbol_output = symbol_output
        tab_data.object_output = object_output
        if self.is_active_tab(tab_data):
            self.render_tab_output(tab_data)

    def on_notebook_click(self, event):
        try:
            clicked_index = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return None

        clicked_element = self.notebook.identify(event.x, event.y)
        if self.close_button_element in clicked_element:
            tab_id = self.notebook.tabs()[clicked_index]
            self.close_editor_tab(tab_id)
            return "break"
        return None

    def close_editor_tab(self, tab_id):
        tab_data = self.get_tab_data(tab_id)
        if not tab_data or not self.confirm_tab_close(tab_data):
            return False

        try:
            closed_index = self.notebook.index(tab_data.frame)
        except tk.TclError:
            closed_index = 0

        was_active = self.is_active_tab(tab_data)
        self.notebook.forget(tab_data.frame)
        self.editor_tabs.pop(str(tab_data.frame), None)

        remaining_tabs = self.notebook.tabs()
        if not remaining_tabs:
            self.create_editor_tab()
        elif was_active:
            next_index = min(closed_index, len(remaining_tabs) - 1)
            self.notebook.select(remaining_tabs[next_index])

        current_tab = self.get_current_tab_data()
        self.render_tab_output(current_tab)
        self.refresh_window_title()
        return True

    def confirm_tab_close(self, tab_data):
        if not tab_data.dirty:
            return True

        response = messagebox.askyesnocancel(
            "Sekmeyi Kapat",
            f"{tab_data.title} üzerinde kaydedilmemiş değişiklikler var. Kaydedilsin mi?",
        )
        if response is None:
            return False
        if response:
            return self.save_asm_file(tab_data)
        return True

    def close_app(self):
        for tab_id in list(self.notebook.tabs()):
            tab_data = self.get_tab_data(tab_id)
            if not tab_data:
                continue

            if tab_data.dirty:
                self.notebook.select(tab_data.frame)
                self.render_tab_output(tab_data)
                self.refresh_window_title()
                if not self.confirm_tab_close(tab_data):
                    return

        self.root.destroy()

    def load_asm_file(self):
        file_path = filedialog.askopenfilename(
            title=".asm Dosyası Seç",
            filetypes=[("Assembly Files", "*.asm"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        existing_tab = self.find_tab_by_file_path(file_path)
        if existing_tab:
            self.notebook.select(existing_tab.frame)
            self.render_tab_output(existing_tab)
            self.refresh_window_title()
            return

        try:
            normalized_path = os.path.abspath(file_path)
            with open(normalized_path, "r", encoding="utf-8") as asm_file:
                content = asm_file.read()

            self.create_editor_tab(content=content, file_path=normalized_path, title=os.path.basename(normalized_path))
        except OSError as e:
            messagebox.showerror("Dosya Açma Hatası", f"ASM dosyası açılamadı:\n{e}")

    def new_file(self):
        self.create_editor_tab()

    def save_asm_file_as(self, tab_data=None):
        tab_data = tab_data or self.get_current_tab_data()
        if not tab_data:
            return False

        save_path = filedialog.asksaveasfilename(
            title="Farklı Kaydet (.asm)",
            defaultextension=".asm",
            filetypes=[("Assembly Files", "*.asm"), ("All Files", "*.*")],
            initialfile=tab_data.title if tab_data.title else "program.asm",
        )
        if not save_path:
            return False
        return self.write_tab_to_file(tab_data, save_path)

    def save_asm_file(self, tab_data=None):
        tab_data = tab_data or self.get_current_tab_data()
        if not tab_data:
            return False

        save_path = tab_data.file_path
        if not save_path:
            save_path = filedialog.asksaveasfilename(
                title=".asm Olarak Kaydet",
                defaultextension=".asm",
                filetypes=[("Assembly Files", "*.asm"), ("All Files", "*.*")],
                initialfile=tab_data.title if tab_data.title else "program.asm",
            )
            if not save_path:
                return False

        return self.write_tab_to_file(tab_data, save_path)

    def write_tab_to_file(self, tab_data, save_path):
        try:
            normalized_path = os.path.abspath(save_path)
            content = tab_data.editor.get("1.0", "end-1c")
            with open(normalized_path, "w", encoding="utf-8") as asm_file:
                asm_file.write(content)
                asm_file.write("\n")

            tab_data.file_path = normalized_path
            tab_data.title = os.path.basename(normalized_path)
            tab_data.dirty = False
            tab_data.editor.edit_modified(False)
            self.update_tab_title(tab_data)
            if self.is_active_tab(tab_data):
                self.render_tab_output(tab_data)
            return True
        except OSError as e:
            messagebox.showerror("Dosya Kaydetme Hatası", f"ASM dosyası kaydedilemedi:\n{e}")
            return False

    def run_assembler(self):
        tab_data = self.get_current_tab_data()
        if not tab_data:
            messagebox.showwarning("Uyarı", "Açık bir sekme yok.")
            return

        if not tab_data.file_path:
            should_save = messagebox.askyesno(
                "ASM Kaydet",
                "Object code'un .o adı için önce kodu .asm olarak kaydetmek ister misiniz?",
            )
            if should_save and not self.save_asm_file(tab_data):
                return

        source_text = tab_data.editor.get("1.0", tk.END).strip()
        if not source_text:
            self.set_tab_output(tab_data, error_output="Lütfen çevrilecek assembly kodunu girin.")
            messagebox.showwarning("Uyarı", "Lütfen çevrilecek assembly kodunu girin.")
            return

        assembler = PicoRVAssembler()
        obj_file, errors = assembler.assemble(source_text.split("\n"))

        error_output = ""
        object_output = ""
        symbol_output = self.format_symbol_output(obj_file)

        if errors:
            error_output = "\n".join(errors)
            object_output = "Düzeltilmesi gereken hatalar var."
        else:
            error_output = self.save_object_file(tab_data, obj_file)
            object_output = self.format_object_output(obj_file)

        self.set_tab_output(tab_data, error_output=error_output, symbol_output=symbol_output, object_output=object_output)

    def save_object_file(self, tab_data, obj_file):
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            output_dir = os.path.join(project_root, "outputs")
            os.makedirs(output_dir, exist_ok=True)

            asm_base_name = "output"
            if tab_data.file_path:
                asm_base_name = os.path.splitext(os.path.basename(tab_data.file_path))[0]
            object_path = os.path.join(output_dir, f"{asm_base_name}.o")

            with open(object_path, "w", encoding="utf-8") as out_file:
                json.dump(obj_file, out_file, indent=4)

            return (
                "Sıfır hata. Çeviri başarılı!\n"
                f"Linker için .o meta-dosyası kaydedildi: {object_path}\n"
            )
        except OSError as e:
            return f"Sıfır hata. Çeviri başarılı!\nDosyaya kaydetme hatası: {e}"

    def link_object_files(self):
        object_paths = filedialog.askopenfilenames(
            title="Object Dosyalarını Seç",
            filetypes=[("Object Files", "*.o"), ("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if not object_paths:
            return

        linker = PicoRVLinker()
        linked_object, errors = linker.link(object_paths)
        if errors:
            self.show_linker_output(
                error_output="Linker hataları:\n" + "\n".join(errors),
                symbol_output="",
                object_output="",
            )
            return

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_prefix = os.path.join(project_root, "outputs", "program")
        try:
            output_paths = linker.write_outputs(linked_object, output_prefix)
        except OSError as e:
            self.show_linker_output(
                error_output=f"Link başarılı, çıktı dosyası yazılamadı:\n{e}",
                symbol_output=self.format_linked_symbols(linked_object),
                object_output=self.format_linked_layout(linked_object),
            )
            return

        error_output = (
            "Link başarılı.\n"
            f"Girdi object sayısı: {len(object_paths)}\n"
            f"HEX çıktı: {output_paths['hex']}\n"
            f"JSON çıktı: {output_paths['json']}\n"
        )
        self.show_linker_output(
            error_output=error_output,
            symbol_output=self.format_linked_symbols(linked_object),
            object_output=self.format_linked_layout(linked_object),
        )

    def show_linker_output(self, error_output, symbol_output, object_output):
        tab_data = self.get_current_tab_data()
        if tab_data:
            self.set_tab_output(tab_data, error_output=error_output, symbol_output=symbol_output, object_output=object_output)
            return

        self.error_text.delete("1.0", tk.END)
        self.sym_text.delete("1.0", tk.END)
        self.out_text.delete("1.0", tk.END)
        self.error_text.insert(tk.END, error_output)
        self.sym_text.insert(tk.END, symbol_output)
        self.out_text.insert(tk.END, object_output)

    def format_linked_symbols(self, linked_object):
        lines = []
        for name, info in linked_object["symbols"].items():
            lines.append(f"{name} ({info['object']}):\t[{info['section']}] 0x{info['address']:08X}")
        return "\n".join(lines) + ("\n" if lines else "")

    def format_linked_layout(self, linked_object):
        layout = linked_object["layout"]
        lines = [
            f"Entry: 0x{linked_object['entry']:08X}",
            f"Text base: 0x{layout['text_base']:08X}",
            f"Data base: 0x{layout['data_base']:08X}",
            "",
            "--- OBJECT LAYOUT ---",
        ]
        for obj in layout["objects"]:
            lines.append(
                f"{obj['name']}: text=0x{obj['text_base']:08X}+{obj['text_size']} "
                f"data=0x{obj['data_base']:08X}+{obj['data_size']}"
            )
        lines.append("")
        lines.append("--- RELOCATIONS ---")
        if linked_object["applied_relocations"]:
            for relocation in linked_object["applied_relocations"]:
                lines.append(
                    f"{relocation['object']} 0x{relocation['patch_address']:08X} "
                    f"{relocation['type']} {relocation['symbol']} -> {relocation['patched']}"
                )
        else:
            lines.append("Relocation yok.")
        return "\n".join(lines) + "\n"

    def format_symbol_output(self, obj_file):
        lines = []
        for label, info in obj_file["symbols"].items():
            lines.append(f"{label} ({info['visibility']}):\t[{info['section']}] 0x{info['offset']:04X}")
        return "\n".join(lines) + ("\n" if lines else "")

    def format_object_output(self, obj_file):
        lines = ["--- .TEXT SECTION ---"]
        for i, code in enumerate(obj_file["text"]):
            lines.append(f"0x{(i * 4):08X}: {code}")

        if obj_file["data"]:
            lines.append("")
            lines.append("--- .DATA SECTION ---")
            for i, code in enumerate(obj_file["data"]):
                lines.append(f"0x{i:08X}: {code}")

        return "\n".join(lines) + "\n"
