#!/usr/bin/env python3
"""
MOV → MP4 Converter for pCloud Streaming
Standalone desktop app — no XAMPP or web server needed.
Double-click run.bat or: python app.py
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_info import (
    APP_TITLE,
    APP_VERSION,
    COPYRIGHT_LINE,
    DEVELOPER_LINE,
    DEVELOPER_NAME,
    DEVELOPER_PHONE,
    APP_DESCRIPTION,
)
from converter_core import (
    RESOLUTION_PRESETS,
    ConversionEngine,
    ConvertSettings,
    find_ffmpeg,
    preview_output_path,
)

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "user_settings.json"
DEFAULTS_FILE = APP_DIR / "config_defaults.json"


def load_defaults() -> dict:
    if DEFAULTS_FILE.is_file():
        return json.loads(DEFAULTS_FILE.read_text(encoding="utf-8"))
    return {}


def load_user_settings() -> dict:
    if CONFIG_FILE.is_file():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return load_defaults()


def save_user_settings(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.minsize(720, 680)
        self.geometry("920x760")

        self.engine = ConversionEngine()
        self._worker: threading.Thread | None = None
        self._install_worker: threading.Thread | None = None
        self.settings_vars: dict = {}

        self._build_ui()
        self._load_settings_into_ui()
        self._check_ffmpeg()
        self.after(800, self._first_run_check)

    def _check_ffmpeg(self) -> None:
        ff = self.engine.ffmpeg_path
        if ff:
            self.ffmpeg_status_var.set(f"FFmpeg: {ff}")
            self.ffmpeg_status.configure(foreground="#2e7d32")
        else:
            self.ffmpeg_status_var.set("FFmpeg not found — click Browse to select ffmpeg.exe")
            self.ffmpeg_status.configure(foreground="#c62828")

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        header = ttk.Frame(self, padding=12)
        header.pack(fill=tk.X)
        ttk.Label(header, text="MOV → MP4 for pCloud Streaming", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Convert videos for fast browser/pCloud playback. Max 10 GB per file. No server required.",
            wraplength=860,
        ).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(header, text=DEVELOPER_LINE, font=("Segoe UI", 9), foreground="#1565c0").pack(anchor=tk.W, pady=(6, 0))

        # FFmpeg row
        ff_row = ttk.Frame(self, padding=(12, 0))
        ff_row.pack(fill=tk.X)
        self.ffmpeg_status_var = tk.StringVar(value="Checking FFmpeg…")
        self.ffmpeg_status = tk.Label(
            ff_row,
            textvariable=self.ffmpeg_status_var,
            anchor=tk.W,
            font=("Segoe UI", 9),
        )
        self.ffmpeg_status.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(ff_row, text="Install / Repair", command=self._run_installer).pack(side=tk.RIGHT, padx=2)
        ttk.Button(ff_row, text="Browse FFmpeg…", command=self._browse_ffmpeg).pack(side=tk.RIGHT, padx=2)

        notebook = ttk.Notebook(self, padding=8)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        tab_convert = ttk.Frame(notebook, padding=10)
        tab_settings = ttk.Frame(notebook, padding=10)
        tab_about = ttk.Frame(notebook, padding=10)
        notebook.add(tab_convert, text="Convert")
        notebook.add(tab_settings, text="Video Settings")
        notebook.add(tab_about, text="About / Setup")

        self._build_convert_tab(tab_convert)
        self._build_settings_tab(tab_settings)
        self._build_about_tab(tab_about)

        # Log
        log_frame = ttk.LabelFrame(self, text="Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Progress
        prog = ttk.Frame(self, padding=(12, 0, 12, 12))
        prog.pack(fill=tk.X)
        self.progress_label = ttk.Label(prog, text="Ready")
        self.progress_label.pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=4)

        btn_row = ttk.Frame(prog)
        btn_row.pack(fill=tk.X)
        self.btn_start = ttk.Button(btn_row, text="Start Conversion", command=self._start_conversion)
        self.btn_start.pack(side=tk.LEFT)
        self.btn_cancel = ttk.Button(btn_row, text="Cancel", command=self._cancel, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="Open Output Folder", command=self._open_output).pack(side=tk.RIGHT)

        footer = ttk.Frame(self, padding=(12, 0, 12, 8))
        footer.pack(fill=tk.X)
        ttk.Label(
            footer,
            text=f"{COPYRIGHT_LINE}  |  {DEVELOPER_PHONE}",
            font=("Segoe UI", 8),
            foreground="#666",
        ).pack(anchor=tk.CENTER)

    def _build_about_tab(self, parent: ttk.Frame) -> None:
        info = ttk.Frame(parent)
        info.pack(fill=tk.BOTH, expand=True)

        lines = [
            (f"{APP_TITLE}", ("Segoe UI", 14, "bold")),
            (f"Version {APP_VERSION}", ("Segoe UI", 10)),
            ("", None),
            (APP_DESCRIPTION, ("Segoe UI", 10)),
            ("", None),
            ("Developer", ("Segoe UI", 11, "bold")),
            (DEVELOPER_NAME, ("Segoe UI", 12, "bold")),
            (DEVELOPER_PHONE, ("Segoe UI", 11)),
            ("", None),
            ("First-time setup", ("Segoe UI", 11, "bold")),
            (
                "1. Double-click install.bat (downloads FFmpeg, creates folders)\n"
                "2. Or click Install / Repair on the Convert screen\n"
                "3. Then use run.bat or Start Conversion",
                ("Segoe UI", 10),
            ),
            ("", None),
            ("Installed components", ("Segoe UI", 11, "bold")),
        ]
        for text, font in lines:
            if not text:
                ttk.Label(info, text="").pack(anchor=tk.W)
                continue
            kw = {"font": font} if font else {}
            ttk.Label(info, text=text, wraplength=820, **kw).pack(anchor=tk.W, pady=2)

        self.setup_status = ttk.Label(info, text="Checking…", font=("Consolas", 9))
        self.setup_status.pack(anchor=tk.W, pady=8)
        ttk.Button(info, text="Run Install / Repair Now", command=self._run_installer).pack(anchor=tk.W, pady=4)
        ttk.Button(info, text="Refresh status", command=self._refresh_setup_status).pack(anchor=tk.W)
        self._refresh_setup_status()

    def _refresh_setup_status(self) -> None:
        try:
            from installer import check_python_version, check_tkinter, ffmpeg_already_installed, find_ffmpeg

            py_ok, py_ver = check_python_version()
            tk_ok, tk_msg = check_tkinter()
            ff_ok = ffmpeg_already_installed()
            ff_path = find_ffmpeg()
            lines = [
                f"Python: {'OK' if py_ok else 'MISSING'} ({py_ver})",
                f"GUI (tkinter): {'OK' if tk_ok else 'MISSING'} — {tk_msg}",
                f"FFmpeg: {'OK' if ff_ok else 'NOT INSTALLED'}",
            ]
            if ff_path:
                lines.append(f"  Path: {ff_path}")
            self.setup_status.configure(text="\n".join(lines))
        except Exception as e:
            self.setup_status.configure(text=f"Status error: {e}")

    def _first_run_check(self) -> None:
        try:
            from installer import is_setup_complete

            if not is_setup_complete():
                if messagebox.askyesno(
                    "First-time setup",
                    "FFmpeg or setup is missing.\n\n"
                    "Run automatic install now?\n"
                    "(Downloads FFmpeg ~90 MB, one time)\n\n"
                    f"{DEVELOPER_NAME}\n{DEVELOPER_PHONE}",
                ):
                    self._run_installer()
        except Exception:
            pass

    def _run_installer(self) -> None:
        if self._install_worker and self._install_worker.is_alive():
            return

        self._log("——— Install / Repair started ———")
        self.btn_start.configure(state=tk.DISABLED)

        def work() -> None:
            from installer import run_full_setup

            def progress(msg: str) -> None:
                self.after(0, lambda m=msg: self._log(m))

            ok = run_full_setup(quiet=True, progress=progress)

            def done() -> None:
                self.btn_start.configure(state=tk.NORMAL)
                self.engine = ConversionEngine()
                self._check_ffmpeg()
                self._refresh_setup_status()
                if ok:
                    messagebox.showinfo(
                        "Setup complete",
                        "All components installed.\nYou can start converting videos.\n\n"
                        f"{DEVELOPER_NAME}\n{DEVELOPER_PHONE}",
                    )
                else:
                    messagebox.showerror(
                        "Setup failed",
                        "Install failed. Try running install.bat as Administrator.\n\n"
                        f"{DEVELOPER_NAME}\n{DEVELOPER_PHONE}",
                    )

            self.after(0, done)

        self._install_worker = threading.Thread(target=work, daemon=True)
        self._install_worker.start()

    def _build_convert_tab(self, parent: ttk.Frame) -> None:
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(APP_DIR / "output"))
        self.recursive = tk.BooleanVar(value=True)

        def folder_row(label: str, var: tk.StringVar, browse_cmd) -> None:
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=6)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            ttk.Button(row, text="Browse…", command=browse_cmd).pack(side=tk.RIGHT)

        folder_row("Input folder", self.input_dir, self._browse_input)
        folder_row("Output folder", self.output_dir, self._browse_output)

        ttk.Checkbutton(parent, text="Include subfolders (.mov)", variable=self.recursive).pack(anchor=tk.W, pady=4)

        layout_frame = ttk.LabelFrame(
            parent,
            text="Course folder layout (recommended)",
            padding=8,
        )
        layout_frame.pack(fill=tk.X, pady=8)
        defaults = load_defaults()
        self.course_layout_var = tk.BooleanVar(value=defaults.get("course_folder_layout", True))
        ttk.Checkbutton(
            layout_frame,
            text="Put MP4 in subject folder as Topic_01.mp4 (no lesson_01 subfolder)",
            variable=self.course_layout_var,
        ).pack(anchor=tk.W)
        prefix_row = ttk.Frame(layout_frame)
        prefix_row.pack(fill=tk.X, pady=6)
        ttk.Label(prefix_row, text="Name prefix:").pack(side=tk.LEFT)
        self.topic_prefix_var = tk.StringVar(value=defaults.get("topic_prefix", "Topic"))
        ttk.Entry(prefix_row, textvariable=self.topic_prefix_var, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Label(
            layout_frame,
            text="Example: anatomy/lesson_01/video.mov  →  anatomy/Topic_01.mp4",
            foreground="#555",
        ).pack(anchor=tk.W)

        preset_frame = ttk.LabelFrame(parent, text="Quick presets", padding=8)
        preset_frame.pack(fill=tk.X, pady=12)
        ttk.Button(preset_frame, text="Best quality (1080p)", command=lambda: self._apply_preset("1080")).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(preset_frame, text="Fast streaming (720p)", command=lambda: self._apply_preset("720")).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(preset_frame, text="Ultra compatible (baseline)", command=lambda: self._apply_preset("baseline")).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(preset_frame, text="Smallest size", command=lambda: self._apply_preset("small")).pack(side=tk.LEFT, padx=4)

        self.file_count_label = ttk.Label(parent, text="No folder selected")
        self.file_count_label.pack(anchor=tk.W, pady=8)
        ttk.Button(parent, text="Scan for .MOV files", command=self._scan_files).pack(anchor=tk.W)

        self.file_list = tk.Listbox(parent, height=10, font=("Segoe UI", 9))
        self.file_list.pack(fill=tk.BOTH, expand=True, pady=8)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        defaults = load_defaults()

        def add_combo(label: str, key: str, values: list, width=20) -> ttk.Combobox:
            row = ttk.Frame(inner)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(defaults.get(key, values[0])))
            self.settings_vars[key] = var
            cb = ttk.Combobox(row, textvariable=var, values=values, width=width, state="readonly")
            cb.pack(side=tk.LEFT)
            return cb

        def add_spin(label: str, key: str, from_, to, default) -> ttk.Spinbox:
            row = ttk.Frame(inner)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(defaults.get(key, default)))
            self.settings_vars[key] = var
            sp = ttk.Spinbox(row, textvariable=var, from_=from_, to=to, width=10)
            sp.pack(side=tk.LEFT)
            return sp

        add_combo("Resolution", "resolution", list(RESOLUTION_PRESETS.keys()) + ["original"])
        add_combo("FPS", "fps_mode", ["keep", "fixed"])
        add_spin("FPS value (if fixed)", "fps_value", 15, 60, 30)
        add_spin("CRF (18=best, 28=small)", "crf", 18, 28, 23)
        add_combo("Encoding preset", "preset", ["ultrafast", "veryfast", "fast", "medium", "slow"])
        add_combo("H.264 profile", "profile", ["high", "baseline"])
        add_spin("Video bitrate kbps (0=CRF)", "video_bitrate_kbps", 0, 20000, 0)
        add_spin("Audio bitrate kbps", "audio_bitrate_kbps", 64, 320, 128)
        add_spin("Max output size GB", "max_output_gb", 1, 10, 10)

        self.faststart_var = tk.BooleanVar(value=defaults.get("faststart", True))
        self.sanitize_var = tk.BooleanVar(value=defaults.get("sanitize_names", True))
        self.hw_var = tk.BooleanVar(value=defaults.get("use_hardware", False))

        for text, var in [
            ("Fast Start / Web optimized (required for pCloud)", self.faststart_var),
            ("Clean file names (spaces → underscores)", self.sanitize_var),
            ("Use NVIDIA hardware encoding (faster, if available)", self.hw_var),
        ]:
            ttk.Checkbutton(inner, text=text, variable=var).pack(anchor=tk.W, pady=2)

        ttk.Button(inner, text="Save settings", command=self._save_settings).pack(anchor=tk.W, pady=12)

    def _load_settings_into_ui(self) -> None:
        data = load_user_settings()
        for key, var in self.settings_vars.items():
            if key in data:
                var.set(str(data[key]))
        if "faststart" in data:
            self.faststart_var.set(data["faststart"])
        if "sanitize_names" in data:
            self.sanitize_var.set(data["sanitize_names"])
        if "use_hardware" in data:
            self.hw_var.set(data["use_hardware"])
        if hasattr(self, "course_layout_var") and "course_folder_layout" in data:
            self.course_layout_var.set(data["course_folder_layout"])
        if hasattr(self, "topic_prefix_var") and "topic_prefix" in data:
            self.topic_prefix_var.set(data["topic_prefix"])

    def _collect_settings(self) -> ConvertSettings:
        def int_val(key: str, default: int = 0) -> int:
            try:
                return int(float(self.settings_vars[key].get()))
            except (KeyError, ValueError):
                return default

        def float_val(key: str, default: float = 10.0) -> float:
            try:
                return float(self.settings_vars[key].get())
            except (KeyError, ValueError):
                return default

        profile = self.settings_vars.get("profile", tk.StringVar(value="high")).get()
        level = "3.0" if profile == "baseline" else "4.1"

        return ConvertSettings(
            resolution=self.settings_vars["resolution"].get(),
            fps_mode=self.settings_vars["fps_mode"].get(),
            fps_value=int_val("fps_value", 30),
            crf=int_val("crf", 23),
            preset=self.settings_vars["preset"].get(),
            profile=profile,
            level=level,
            video_bitrate_kbps=int_val("video_bitrate_kbps", 0),
            audio_bitrate_kbps=int_val("audio_bitrate_kbps", 128),
            max_output_gb=float_val("max_output_gb", 10),
            faststart=self.faststart_var.get(),
            sanitize_names=self.sanitize_var.get(),
            use_hardware=self.hw_var.get(),
            course_folder_layout=self.course_layout_var.get(),
            topic_prefix=self.topic_prefix_var.get().strip() or "Topic",
        )

    def _apply_preset(self, name: str) -> None:
        presets = {
            "1080": {"resolution": "1920x1080", "crf": 22, "preset": "medium", "profile": "high"},
            "720": {"resolution": "1280x720", "crf": 23, "preset": "medium", "profile": "high"},
            "baseline": {"resolution": "1280x720", "crf": 23, "preset": "medium", "profile": "baseline"},
            "small": {"resolution": "1280x720", "crf": 26, "preset": "fast", "profile": "high", "video_bitrate_kbps": 2500},
        }
        p = presets.get(name, {})
        for k, v in p.items():
            if k in self.settings_vars:
                self.settings_vars[k].set(str(v))
        if "profile" in p:
            self.settings_vars["profile"].set(p["profile"])
        self._log(f"Applied preset: {name}")

    def _browse_ffmpeg(self) -> None:
        path = filedialog.askopenfilename(title="Select ffmpeg.exe", filetypes=[("ffmpeg", "ffmpeg.exe"), ("All", "*.*")])
        if path:
            self.engine = ConversionEngine(path)
            os.environ["FFMPEG_PATH"] = path
            self._check_ffmpeg()

    def _browse_input(self) -> None:
        d = filedialog.askdirectory(title="Select folder with .MOV files")
        if d:
            self.input_dir.set(d)
            self._scan_files()

    def _browse_output(self) -> None:
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.output_dir.set(d)

    def _scan_files(self) -> None:
        folder = self.input_dir.get().strip()
        if not folder:
            messagebox.showwarning("Input folder", "Select an input folder first.")
            return
        files = self.engine.list_mov_files(folder, self.recursive.get())
        self.file_list.delete(0, tk.END)
        settings = self._collect_settings()
        out = self.output_dir.get().strip() or str(APP_DIR / "output")
        input_root = Path(folder)
        output_root = Path(out)
        for f in files:
            try:
                rel_in = f.relative_to(input_root)
            except ValueError:
                rel_in = f.name
            preview = preview_output_path(f, input_root, output_root, settings)
            self.file_list.insert(tk.END, f"{rel_in}  →  {preview}")
        self.file_count_label.configure(text=f"Found {len(files)} .MOV file(s)")
        self._scanned_files = files
        self._scan_input_root = folder

    def _log(self, msg: str) -> None:
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _save_settings(self) -> None:
        data = {k: v.get() for k, v in self.settings_vars.items()}
        data["faststart"] = self.faststart_var.get()
        data["sanitize_names"] = self.sanitize_var.get()
        data["use_hardware"] = self.hw_var.get()
        data["course_folder_layout"] = self.course_layout_var.get()
        data["topic_prefix"] = self.topic_prefix_var.get().strip() or "Topic"
        save_user_settings(data)
        messagebox.showinfo("Saved", "Settings saved for next time.")

    def _open_output(self) -> None:
        out = self.output_dir.get().strip()
        if out and Path(out).exists():
            os.startfile(out)
        else:
            messagebox.showinfo("Output", "Output folder does not exist yet.")

    def _start_conversion(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        if not self.engine.is_ready:
            if messagebox.askyesno(
                "FFmpeg required",
                "FFmpeg is not installed.\n\nRun automatic install now?\n"
                "(Or use Install / Repair button)",
            ):
                self._run_installer()
            return

        folder = self.input_dir.get().strip()
        if not folder:
            messagebox.showwarning("Input", "Select an input folder.")
            return

        files = getattr(self, "_scanned_files", None) or self.engine.list_mov_files(folder, self.recursive.get())
        if not files:
            messagebox.showwarning("No files", "No .MOV files found in the input folder.")
            return

        out = self.output_dir.get().strip() or str(APP_DIR / "output")
        self.output_dir.set(out)
        settings = self._collect_settings()
        self._save_settings()

        self.btn_start.configure(state=tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL)
        self.progress_bar["value"] = 0
        self._log("——— Starting batch ———")

        def run() -> None:
            def on_log(m: str) -> None:
                self.after(0, lambda: self._log(m))

            def on_prog(cur: int, total: int, name: str, pct: float) -> None:
                def ui() -> None:
                    overall = ((cur - 1) / total + pct / 100 / total) * 100
                    self.progress_bar["value"] = overall
                    self.progress_label.configure(text=f"File {cur}/{total}: {name} ({pct:.0f}%)")

                self.after(0, ui)

            results = self.engine.convert_batch(
                files, out, folder, settings, on_log=on_log, on_file_progress=on_prog
            )

            def done() -> None:
                self.btn_start.configure(state=tk.NORMAL)
                self.btn_cancel.configure(state=tk.DISABLED)
                self.progress_bar["value"] = 100
                ok = sum(1 for r in results if r.success)
                self.progress_label.configure(text=f"Finished: {ok}/{len(results)} succeeded")
                self._log(f"——— Done: {ok}/{len(results)} ———")
                if ok < len(results):
                    failed = [r for r in results if not r.success]
                    messagebox.showwarning(
                        "Completed with errors",
                        f"{ok} succeeded, {len(failed)} failed.\nSee log for details.",
                    )
                else:
                    messagebox.showinfo("Done", f"All {ok} videos converted.\nOutput: {out}")

            self.after(0, done)

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def _cancel(self) -> None:
        self.engine.cancel()
        self._log("Cancellation requested…")
        self.btn_cancel.configure(state=tk.DISABLED)


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
