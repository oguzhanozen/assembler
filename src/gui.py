import tkinter as tk
from tkinter import messagebox
import re
import os
from src.assembler import PicoRVAssembler, opcode_table

class AssemblerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PicoRV32I Assembler IDE")
        self.root.geometry("980x650")
        self.root.minsize(900, 560)

        # Pencere alanını sol (editör) ve sağ (çıktı) paneller arasında daha dengeli böl.
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        
        left_frame = tk.Frame(root, padx=10, pady=10)
        left_frame.grid(row=0, column=0, sticky="nsew")
        
        right_frame = tk.Frame(root, padx=10, pady=10)
        right_frame.grid(row=0, column=1, sticky="nsew")

        # Üst Başlık
        tk.Label(left_frame, text="Assembly Kodunu Buraya Yazın:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 2))
        
        # --- Renk Anahtarı (Legend) Çerçevesi ---
        legend_frame = tk.Frame(left_frame)
        legend_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(legend_frame, text="Renkler:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(legend_frame, text="Opcode", fg="blue", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Label", fg="red", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Direktif", fg="purple", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Register", fg="darkorange", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Sayı", fg="teal", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Yorum", fg="gray", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        # --- Editör Çerçevesi ---
        editor_frame = tk.Frame(left_frame)
        editor_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.scrollbar = tk.Scrollbar(editor_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.line_numbers = tk.Text(editor_frame, width=4, padx=5, takefocus=0, border=0, 
                                    background='#f0f0f0', state='disabled', font=("Courier New", 12))
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        
        self.input_text = tk.Text(editor_frame, wrap=tk.NONE, font=("Courier New", 12, "bold"), 
                                  yscrollcommand=self.sync_scroll_set)
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar.config(command=self.sync_scroll_get)

        self.input_text.tag_config("opcode", foreground="blue")
        self.input_text.tag_config("label", foreground="red")
        self.input_text.tag_config("directive", foreground="purple")
        self.input_text.tag_config("register", foreground="darkorange")
        self.input_text.tag_config("number", foreground="teal")
        self.input_text.tag_config("comment", foreground="gray")

        self.input_text.bind("<KeyRelease>", self.on_text_change)
        self.input_text.bind("<MouseWheel>", self.on_text_change)
        
        self.on_text_change() 

        self.btn_assemble = tk.Button(left_frame, text="Kodu Çevir (Assemble)", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=self.run_assembler)
        self.btn_assemble.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Hata Mesajları:", font=("Arial", 10, "bold"), fg="red").pack(anchor=tk.W)
        self.error_text = tk.Text(right_frame, width=40, height=6, font=("Courier New", 10), bg="#ffe6e6")
        self.error_text.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Symbol Table (Sembol Tablosu):", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.sym_text = tk.Text(right_frame, width=40, height=6, font=("Courier New", 10), bg="#f4f4f4")
        self.sym_text.pack(fill=tk.X, pady=5)

        tk.Label(right_frame, text="Object Code (Makine Kodu):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(5,0))
        self.out_text = tk.Text(right_frame, width=40, height=12, font=("Courier New", 11), bg="#1e1e1e", fg="#00ff00")
        self.out_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def sync_scroll_set(self, *args):
        self.scrollbar.set(*args)
        self.line_numbers.yview_moveto(args[0])

    def sync_scroll_get(self, *args):
        self.input_text.yview(*args)
        self.line_numbers.yview(*args)

    def update_line_numbers(self):
        line_count = self.input_text.get("1.0", tk.END).count('\n')
        display_lines = max(20, line_count)
        line_numbers_string = "\n".join(str(i) for i in range(1, display_lines + 1))
        
        self.line_numbers.config(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", line_numbers_string)
        self.line_numbers.config(state=tk.DISABLED)
        self.line_numbers.yview_moveto(self.input_text.yview()[0])

    def highlight_syntax(self):
        for tag in ["opcode", "label", "directive", "register", "number", "comment"]:
            self.input_text.tag_remove(tag, "1.0", tk.END)

        lines = self.input_text.get("1.0", tk.END).split('\n')
        for i, line in enumerate(lines):
            line_num = i + 1
            comment_idx = line.find('#')
            if comment_idx != -1:
                self.input_text.tag_add("comment", f"{line_num}.{comment_idx}", f"{line_num}.end")
                line = line[:comment_idx]
                
            for match in re.finditer(r'^[ \t]*[a-zA-Z0-9_]+:', line):
                self.input_text.tag_add("label", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r'\.[a-zA-Z_]+', line):
                self.input_text.tag_add("directive", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
                
            opcode_pattern = r'\b(?:' + '|'.join(opcode_table.keys()) + r')\b'
            for match in re.finditer(opcode_pattern, line):
                self.input_text.tag_add("opcode", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
                
            for match in re.finditer(r'\bx[0-9]+\b', line):
                self.input_text.tag_add("register", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
                
            for match in re.finditer(r'\b-?(?:0x[0-9a-fA-F]+|\d+)\b', line):
                self.input_text.tag_add("number", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")

    def on_text_change(self, event=None):
        self.update_line_numbers()
        self.highlight_syntax()

    def save_object_code_to_txt(self, machine_code):
        """Üretilen object code'u çalışma klasörüne text dosyası olarak kaydeder."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_dir = os.path.join(project_root, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "object_code.txt")
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write("\n".join(machine_code) + "\n")
        return output_path

    def save_symbol_table_to_txt(self, sym_table):
        """Üretilen symbol table'ı çalışma klasörüne text dosyası olarak kaydeder."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_dir = os.path.join(project_root, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "symbol_table.txt")
        with open(output_path, "w", encoding="utf-8") as out_file:
            for label, addr in sym_table.items():
                out_file.write(f"{label}:\t0x{addr:04X}\n")
        return output_path

    def run_assembler(self):
        self.sym_text.delete(1.0, tk.END)
        self.out_text.delete(1.0, tk.END)
        self.error_text.delete(1.0, tk.END)
        
        source = self.input_text.get(1.0, tk.END).strip().split('\n')
        if not source or source == [""]:
            messagebox.showwarning("Uyarı", "Lütfen çevrilecek assembly kodunu girin.")
            return

        assembler = PicoRVAssembler()
        machine_code, sym_table, errors = assembler.assemble(source)

        if errors:
            self.error_text.insert(tk.END, "\n".join(errors))
            self.out_text.insert(tk.END, "Düzeltilmesi gereken hatalar var.")
        else:
            try:
                object_path = self.save_object_code_to_txt(machine_code)
                symbol_path = self.save_symbol_table_to_txt(sym_table)
                self.error_text.insert(
                    tk.END,
                    "Sıfır hata. Çeviri başarılı!\n"
                    f"Object code dosyaya kaydedildi: {object_path}\n"
                    f"Symbol table dosyaya kaydedildi: {symbol_path}"
                )
            except OSError as e:
                self.error_text.insert(tk.END, f"Sıfır hata. Çeviri başarılı!\nDosyaya kaydetme hatası: {e}")

            for i, code in enumerate(machine_code):
                self.out_text.insert(tk.END, f"{code}\n")

        for label, addr in sym_table.items():
            self.sym_text.insert(tk.END, f"{label}:\t0x{addr:04X}\n")