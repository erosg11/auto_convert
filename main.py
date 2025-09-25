import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import subprocess
import threading
import pathlib
from datetime import datetime
import webbrowser
import shutil
import sys
import os

LAST_FORMAT_FILE = "last_format.txt"
FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"

FORMATS = {
    "MP4 (H.264/AAC)": (".mp4", ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]),
    "MP4 NVENC (H.264/AAC)": (".mp4", ["-c:v", "h264_nvenc", "-preset", "p7", "-cq", "20", "-pix_fmt", "yuv420p"]),
    "MP4 (H.265/HEVC)": (".mp4", ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]),
    "MP4 NVENC (H.265/HEVC)": (".mp4", ["-c:v", "hevc_nvenc", "-preset", "p7", "-cq", "22", "-pix_fmt", "yuv420p"]),
    "MKV (Cópia Direta)": (".mkv", ["-c", "copy"]),
    "WEBM (VP9/Opus)": (".webm", ["-c:v", "libvpx-vp9", "-c:a", "libopus"]),
    "MOV (Apple QuickTime)": (".mov", ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]),
    "AVI (MPEG-4/MP3)": (".avi", ["-c:v", "mpeg4", "-c:a", "libmp3lame"]),
    "GIF Animado": (".gif", ["-vf", "fps=15,scale=500:-1:flags=lanczos"]),
}

SCALES = {
    'original': [],
    '1080p': ['-vf', 'scale=-1:1080'],
    '720p': ['-vf', 'scale=-1:720'],
    '480p': ['-vf', 'scale=-1:480']
}


class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Conversor de Vídeo")
        self.root.geometry("600x550")
        self.root.resizable(False, False)

        self.file_list = []
        self.selected_format = tk.StringVar()
        self.selected_scale = tk.StringVar()
        self.last_saved_format = ""
        self.conversion_thread = None
        self.conversion_progress = (0, 0, "")  # (current, total, filename)

        self.has_nvenc_support = False

        if not self.check_ffmpeg():
            self.root.quit()
            return

        self.detect_gpu_support()
        if not self.has_nvenc_support:
            to_del = {k for k in FORMATS.keys() if 'NVENC' in k}
            for k in to_del:
                del FORMATS[k]

        self.setup_ui()
        self.load_last_format()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame de entrada com Listbox
        input_frame = ttk.LabelFrame(main_frame, text="Arquivos para Converter")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        listbox_frame = ttk.Frame(input_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind('<<Drop>>', self.on_drop)

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        self.btn_browse = ttk.Button(button_frame, text="Adicionar Arquivos...", command=self.browse_files)
        self.btn_browse.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.btn_remove = ttk.Button(button_frame, text="Remover Selecionados", command=self.remove_selected_files)
        self.btn_remove.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 2))

        self.btn_limpa = ttk.Button(button_frame, text="Limpa lista", command=self.limpa_lista)
        self.btn_limpa.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # Frame de formato
        format_frame = ttk.LabelFrame(main_frame, text="Formato de Saída")
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        self.combo_format = ttk.Combobox(format_frame, textvariable=self.selected_format, state="readonly", height=10)
        self.combo_format['values'] = list(FORMATS.keys())
        self.combo_format.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 2), pady=5)
        self.combo_format.bind("<<ComboboxSelected>>", self.format_changed)

        self.combo_scale = ttk.Combobox(format_frame, textvariable=self.selected_scale, state="readonly", height=10)
        self.combo_scale['values'] = list(SCALES.keys())
        self.combo_scale.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(2, 0), pady=5)
        self.combo_scale.bind("<<ComboboxSelected>>", self.format_changed)

        # Frame de controle
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.btn_convert = ttk.Button(control_frame, text="Converter", command=self.start_conversion)
        self.btn_convert.pack(fill=tk.X, expand=True, pady=2)

        self.progress_label = ttk.Label(main_frame, text="")
        self.progress_label.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.progress_bar = ttk.Progressbar(main_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)

        self.status_label = ttk.Label(main_frame, text="Selecione os arquivos para conversão.")
        self.status_label.pack(fill=tk.X, padx=5, pady=5)

        gpu_status = "GPU NVIDIA (NVENC) detectada!" if self.has_nvenc_support else "GPU NVIDIA (NVENC) não detectada."
        self.gpu_status_label = ttk.Label(main_frame, text=gpu_status, anchor=tk.E)
        self.gpu_status_label.pack(fill=tk.X, padx=5)
        self.license = ttk.Label(main_frame, text='Feito por erosg11', anchor="center", foreground='blue')
        self.license.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/erosg11/auto_convert.git'))
        self.license.pack(fill=tk.X, padx=0, pady=2)

    def on_drop(self, event):
        file_paths = root.tk.splitlist(event.data)
        self.add_files(file_paths)

    def check_ffmpeg(self):
        if shutil.which("ffmpeg"):
            return True
        else:
            messagebox.showerror("FFmpeg não encontrado",
                                 "O FFmpeg não foi encontrado no PATH do seu sistema. Instale-o e adicione ao PATH para que o programa funcione.")
            webbrowser.open(FFMPEG_DOWNLOAD_URL)
            return False

    def detect_gpu_support(self):
        try:
            startupinfo = subprocess.STARTUPINFO() if sys.platform == "win32" else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, check=True,
                                    startupinfo=startupinfo, encoding='utf-8')
            output = result.stdout + result.stderr
            self.has_nvenc_support = 'hevc_nvenc' in output and 'h264_nvenc' in output
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.has_nvenc_support = False

    def browse_files(self):
        file_paths = filedialog.askopenfilenames(title="Selecione um ou mais arquivos de vídeo",
                                                 filetypes=(("Arquivos de Vídeo",
                                                             "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv"),
                                                            ("Todos os arquivos", "*.*")))
        self.add_files(file_paths)

    def add_files(self, file_paths):
        added_count = 0
        for file_path in file_paths:
            if file_path not in self.file_list:
                self.file_list.append(file_path)
                self.listbox.insert(tk.END, os.path.basename(file_path))
                added_count += 1

        if added_count > 0:
            self.update_status_label()

    def remove_selected_files(self):
        selected_indices = self.listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            self.listbox.delete(i)
            del self.file_list[i]
        self.update_status_label()

    def update_status_label(self):
        list_size = len(self.file_list)
        self.status_label.config(text=f"{list_size} arquivo{'s' if list_size != 1 else ''} na lista.")

    def limpa_lista(self):
        self.file_list.clear()
        self.listbox.delete(0, tk.END)
        self.update_status_label()


    def load_last_format(self):
        try:
            with open(LAST_FORMAT_FILE, "r") as f:
                format_key, *scale_key = [x.strip() for x in f.readlines()]
                if format_key in FORMATS:
                    self.selected_format.set(format_key)
                if scale_key and scale_key[0] in SCALES:
                    self.selected_scale.set(scale_key[0])

        except FileNotFoundError:
            pass

        if not self.selected_format.get():
            self.combo_format.current(0)
        if not self.selected_scale.get():
            self.combo_scale.current(0)
        self.last_saved_format = self.selected_format.get(), self.selected_scale.get()

    def save_last_format(self, format_key):
        with open(LAST_FORMAT_FILE, "w") as f:
            print(*format_key, sep='\n', file=f)
        self.last_saved_format = format_key

    def format_changed(self, event):
        current_format = self.selected_format.get(), self.selected_scale.get()
        if current_format != self.last_saved_format:
            self.save_last_format(current_format)
            self.status_label.config(text=f"Formato de saída padrão salvo: {current_format}")

    def toggle_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        self.listbox.config(state=state)
        self.btn_browse.config(state=state)
        self.btn_remove.config(state=state)
        self.btn_convert.config(state=state)
        self.combo_format.config(state=state)
        self.combo_scale.config(state=state)

    def start_conversion(self):
        files_to_convert = self.file_list.copy()
        format_key = self.selected_format.get()

        if not files_to_convert:
            messagebox.showwarning("Aviso", "Por favor, adicione arquivos à lista de conversão.")
            return

        if not format_key:
            messagebox.showwarning("Aviso", "Por favor, selecione um formato de saída.")
            return

        is_h264_or_h265 = "H.264" in format_key or "H.265" in format_key
        if is_h264_or_h265 and not self.has_nvenc_support:
            messagebox.showinfo(
                "Aviso de Desempenho",
                "Aceleração por GPU NVIDIA (NVENC) não foi detectada.\n\nA conversão usará o processador (CPU),"
                " o que pode ser consideravelmente mais lento."
            )

        self.toggle_controls(enabled=False)
        self.progress_bar['maximum'] = len(files_to_convert)
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        self.status_label.config(text="Iniciando conversão...")

        self.conversion_thread = threading.Thread(target=self.convert_video_thread,
                                                  args=(files_to_convert, format_key), daemon=True)
        self.conversion_thread.start()
        self.check_thread()

    def convert_video_thread(self, input_paths, format_key):
        self.thread_status = (None, None)
        total_files = len(input_paths)

        for i, input_path_str in enumerate(input_paths):
            try:
                self.conversion_progress = (i, total_files, os.path.basename(input_path_str))

                input_path = pathlib.Path(input_path_str)
                extension, options = FORMATS[format_key]
                options = options.copy()
                output_filename = f"{input_path.stem}-{datetime.now():%Y%m%d%H%M%S}{extension}"
                output_path = input_path.with_name(output_filename)

                command = (["ffmpeg", "-i", str(input_path)] + options + SCALES[self.selected_scale.get()] +
                           [str(output_path)])

                startupinfo = subprocess.STARTUPINFO() if sys.platform == "win32" else None
                if startupinfo:
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.run(command, capture_output=True, text=True, check=True,
                               startupinfo=startupinfo, encoding='utf-8')

                self.conversion_progress = (i + 1, total_files, os.path.basename(input_path_str))

            except subprocess.CalledProcessError as e:
                error_message = f"Erro ao converter '{os.path.basename(input_path_str)}':\n\n{e.stderr}"
                self.thread_status = ("error", error_message)
                return
            except Exception as e:
                self.thread_status = ("error", f"Ocorreu um erro inesperado: {e}")
                return

        self.thread_status = ("success", f"{total_files} arquivo(s) convertido(s) com sucesso!")

    def check_thread(self):
        if self.conversion_thread.is_alive():
            current, total, filename = self.conversion_progress
            if total > 0:
                self.progress_bar['value'] = current
                self.progress_label.config(text=f"Progresso: {current} de {total}")
                if current < total:
                    self.status_label.config(text=f"Convertendo: {filename}...")
            self.root.after(100, self.check_thread)
        else:
            self.toggle_controls(enabled=True)
            status, message = self.thread_status

            if status == "success":
                final_value = self.progress_bar['maximum']
                self.progress_bar['value'] = final_value
                self.progress_label.config(text=f"Progresso: {final_value} de {final_value}")
                self.status_label.config(text="Conversão concluída com sucesso!")
                messagebox.showinfo("Sucesso", message)
            elif status == "error":
                self.status_label.config(text="A conversão falhou.")
                messagebox.showerror("Erro de Conversão", message)

            self.status_label.config(text="Pronto para converter.")
            self.progress_label.config(text="")
            self.progress_bar['value'] = 0
            self.conversion_progress = (0, 0, "")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = VideoConverterApp(root)
    if 'win' in sys.platform:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    root.mainloop()
