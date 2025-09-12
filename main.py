import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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
    "MP4 (H.264/AAC)": (".mp4", ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac"]),

    "MP4 (H.265/HEVC)": (".mp4", ["-c:v", "libx265", "-preset", "medium", "-c:a", "aac"]),
    "MKV (Cópia Direta)": (".mkv", ["-c", "copy"]),
    "WEBM (VP9/Opus)": (".webm", ["-c:v", "libvpx-vp9", "-c:a", "libopus"]),
    "MOV (Apple QuickTime)": (".mov", ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"]),
    "AVI (MPEG-4/MP3)": (".avi", ["-c:v", "mpeg4", "-c:a", "libmp3lame"]),
    "GIF Animado": (".gif", ["-vf", "fps=15,scale=500:-1:flags=lanczos"]),
}


class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Conversor de Vídeo")
        self.root.geometry("600x320")
        self.root.resizable(False, False)

        self.input_file_path = tk.StringVar()
        self.selected_format = tk.StringVar()
        self.last_saved_format = ""
        self.conversion_thread = None

        self.has_nvenc_support = False

        if not self.check_ffmpeg():
            self.root.quit()
            return

        self.detect_gpu_support()

        self.setup_ui()
        self.load_last_format()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)


        input_frame = ttk.LabelFrame(main_frame, text="Arquivo de Entrada")
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.entry_input = ttk.Entry(input_frame, textvariable=self.input_file_path, width=50)
        self.entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        self.btn_browse = ttk.Button(input_frame, text="Procurar...", command=self.browse_file)
        self.btn_browse.pack(side=tk.LEFT, padx=5, pady=5)


        format_frame = ttk.LabelFrame(main_frame, text="Formato de Saída")
        format_frame.pack(fill=tk.X, padx=5, pady=10)

        self.combo_format = ttk.Combobox(format_frame, textvariable=self.selected_format, state="readonly", height=10)
        self.combo_format['values'] = list(FORMATS.keys())
        self.combo_format.pack(fill=tk.X, padx=5, pady=5)
        self.combo_format.bind("<<ComboboxSelected>>", self.format_changed)


        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=10)

        self.btn_convert = ttk.Button(control_frame, text="Converter", command=self.start_conversion)
        self.btn_convert.pack(fill=tk.X, expand=True, pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)

        self.status_label = ttk.Label(main_frame, text="Pronto para converter.")
        self.status_label.pack(fill=tk.X, padx=5, pady=5)

        gpu_status = "GPU NVIDIA (NVENC) detectada!" if self.has_nvenc_support else "GPU NVIDIA (NVENC) não detectada."
        self.gpu_status_label = ttk.Label(main_frame, text=gpu_status, anchor=tk.E)
        self.gpu_status_label.pack(fill=tk.X, padx=5)
        self.license = ttk.Label(main_frame, text='Feito por erosg11', anchor="center", foreground='blue')
        self.license.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/erosg11/auto_convert.git'))
        self.license.pack(fill=tk.X, padx=0, pady=2)

    def check_ffmpeg(self):
        """Verifica se o ffmpeg está no PATH do sistema."""
        if shutil.which("ffmpeg"):
            return True
        else:
            messagebox.showerror("FFmpeg não encontrado",
                                 "O FFmpeg não foi encontrado no PATH do seu sistema. Instale-o e adicione ao PATH para que o programa funcione.")
            webbrowser.open(FFMPEG_DOWNLOAD_URL)
            return False

    def detect_gpu_support(self):
        """Verifica silenciosamente se o ffmpeg tem encoders NVENC."""
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True,
                text=True,
                check=True,
                startupinfo=startupinfo,
                encoding='utf-8'
            )

            output = result.stdout + result.stderr
            if 'hevc_nvenc' in output and 'h264_nvenc' in output:
                self.has_nvenc_support = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.has_nvenc_support = False

    def browse_file(self):
        file_path = filedialog.askopenfilename(title="Selecione um arquivo de vídeo", filetypes=(
            ("Arquivos de Vídeo", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv"), ("Todos os arquivos", "*.*")))
        if file_path:
            self.input_file_path.set(file_path)

    def load_last_format(self):
        try:
            with open(LAST_FORMAT_FILE, "r") as f:
                format_key = f.read().strip()
                if format_key in FORMATS:
                    self.selected_format.set(format_key)
                    self.last_saved_format = format_key
        except FileNotFoundError:
            pass  # Se não encontrar o arquivo, o próximo if cuidará disso.

        if not self.selected_format.get():
            self.combo_format.current(0)
            self.last_saved_format = self.selected_format.get()

    def save_last_format(self, format_key):
        with open(LAST_FORMAT_FILE, "w") as f:
            f.write(format_key)
        self.last_saved_format = format_key

    def format_changed(self, event):
        current_format = self.selected_format.get()
        if current_format != self.last_saved_format:
            self.save_last_format(current_format)
            self.status_label.config(text=f"Formato de saída padrão salvo: {current_format}")

    def toggle_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        self.entry_input.config(state=state)
        self.btn_browse.config(state=state)
        self.btn_convert.config(state=state)
        self.combo_format.config(state=state)

    def start_conversion(self):
        input_path = self.input_file_path.get()
        format_key = self.selected_format.get()

        if not input_path or not os.path.exists(input_path):
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo de vídeo válido.")
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
        self.status_label.config(text=f"Convertendo '{os.path.basename(input_path)}'...")
        self.progress_bar.start()

        self.conversion_thread = threading.Thread(target=self.convert_video_thread, args=(input_path, format_key),
                                                  daemon=True)
        self.conversion_thread.start()
        self.check_thread()

    def convert_video_thread(self, input_path_str, format_key):
        try:
            input_path = pathlib.Path(input_path_str)

            extension, options = FORMATS[format_key]
            options = options.copy()
            output_filename = f"{input_path.stem}-{datetime.now():%Y%m%d%H%M%S}{extension}"
            output_path = input_path.with_name(output_filename)


            if "H.264" in format_key:
                if self.has_nvenc_support:
                    options = ["-c:v", "h264_nvenc", "-preset", "p7", "-cq", "20", "-pix_fmt", "yuv420p"]
                else:
                    options = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]

            elif "H.265" in format_key:
                if self.has_nvenc_support:
                    options = ["-c:v", "hevc_nvenc", "-preset", "p7", "-cq", "22", "-pix_fmt", "yuv420p"]
                else:
                    options = ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]

            command = ["ffmpeg", "-i", str(input_path)] + options + [str(output_path)]

            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.run(command, capture_output=True, text=True, check=True, startupinfo=startupinfo,
                                     encoding='utf-8')
            self.thread_status = ("success", f"Arquivo salvo como: {output_filename}")

        except subprocess.CalledProcessError as e:
            error_message = f"Erro no FFmpeg:\n\n{e.stderr}"
            print(e.stderr)
            self.thread_status = ("error", error_message)
        except Exception as e:
            self.thread_status = ("error", f"Ocorreu um erro inesperado: {e}")

    def check_thread(self):
        if self.conversion_thread.is_alive():
            self.root.after(100, self.check_thread)
        else:
            self.progress_bar.stop()
            self.toggle_controls(enabled=True)

            status, message = self.thread_status
            if status == "success":
                self.status_label.config(text="Conversão concluída com sucesso!")
                messagebox.showinfo("Sucesso", message)
            else:
                self.status_label.config(text="A conversão falhou.")
                messagebox.showerror("Erro de Conversão", message)

            self.status_label.config(text="Pronto para converter.")


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    if 'win' in sys.platform:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    root.mainloop()