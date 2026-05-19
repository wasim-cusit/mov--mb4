#!/usr/bin/env python3
"""
One-time setup: folders, pip check, FFmpeg download (Windows).
Run: python installer.py
      python installer.py --quiet
      python installer.py --no-banner
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from typing import Callable, Optional
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlretrieve

from app_info import APP_NAME, APP_VERSION, DEVELOPER_NAME, DEVELOPER_PHONE

try:
    from console_theme import (
        format_bytes,
        print_download_progress,
        print_error,
        print_extract_progress,
        print_planned_steps,
        print_progress_bar,
        print_step,
        print_success,
        progress_done,
    )
except ImportError:
    # Fallback if console_theme missing
    def format_bytes(n: int) -> str:
        return f"{n / 1024**2:.1f} MB" if n >= 1024**2 else f"{n} B"

    def print_step(n, t, label, status="run"):
        print(f"  [{n}/{t}] {label}")

    def print_download_progress(d, total, phase="Downloading"):
        pct = int(d * 100 / total) if total else 0
        print(f"\r  {phase} {pct}%", end="", flush=True)

    def progress_done():
        print()

    def print_extract_progress(p=50):
        print(f"  Extracting… {p:.0f}%")

    def print_planned_steps():
        pass

    def print_success(mode="install"):
        print("Done.")

    def print_error(msg):
        print(f"Error: {msg}")

    def print_progress_bar(*a, **k):
        pass

APP_DIR = Path(__file__).resolve().parent
INSTALL_CONFIG = APP_DIR / "install_config.json"
TOOLS_DIR = APP_DIR / "tools"
FFMPEG_DIR = TOOLS_DIR / "ffmpeg"
FFMPEG_BIN = FFMPEG_DIR / "bin"
FFMPEG_EXE = FFMPEG_BIN / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_BIN / "ffprobe.exe"
OUTPUT_DIR = APP_DIR / "output"

FFMPEG_ZIP_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
FFMPEG_ZIP_PATH = TOOLS_DIR / "ffmpeg_download.zip"

TOTAL_STEPS = 4


def load_install_config() -> dict:
    if INSTALL_CONFIG.is_file():
        try:
            return json.loads(INSTALL_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_install_config(ffmpeg_path: str, ffprobe_path: str, extra: dict | None = None) -> None:
    data = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "developer": DEVELOPER_NAME,
        "developer_phone": DEVELOPER_PHONE,
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
    }
    if extra:
        data.update(extra)
    INSTALL_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_python_version() -> tuple[bool, str]:
    if sys.version_info < (3, 9):
        return False, f"Python 3.9+ required. You have {sys.version.split()[0]}."
    return True, sys.version.split()[0]


def check_tkinter() -> tuple[bool, str]:
    try:
        import tkinter  # noqa: F401

        return True, "GUI (tkinter) ready"
    except ImportError:
        return False, "tkinter missing — reinstall Python with tcl/tk enabled"


def ensure_directories() -> None:
    for d in (TOOLS_DIR, FFMPEG_BIN, OUTPUT_DIR, APP_DIR / "logs"):
        d.mkdir(parents=True, exist_ok=True)


def run_pip_install(quiet: bool = False) -> tuple[bool, str]:
    req = APP_DIR / "requirements.txt"
    if not req.is_file():
        return True, "No extra packages required"
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req), "--upgrade"]
    if quiet:
        cmd.append("-q")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "pip failed")[-300:]
        return True, "Python packages installed"
    except subprocess.TimeoutExpired:
        return False, "pip timed out"
    except Exception as e:
        return False, str(e)


def _find_ffmpeg_in_dir(root: Path) -> Path | None:
    for p in root.rglob("ffmpeg.exe"):
        if p.is_file():
            return p
    return None


def _find_ffprobe_near(ffmpeg: Path) -> Path | None:
    probe = ffmpeg.parent / "ffprobe.exe"
    return probe if probe.is_file() else None


def ffmpeg_already_installed() -> bool:
    if FFMPEG_EXE.is_file() and FFPROBE_EXE.is_file():
        return True
    cfg = load_install_config()
    fp = cfg.get("ffmpeg_path")
    if fp and Path(fp).is_file():
        return True
    return find_ffmpeg() is not None


def find_ffmpeg() -> Path | None:
    if FFMPEG_EXE.is_file():
        return FFMPEG_EXE
    cfg = load_install_config()
    if cfg.get("ffmpeg_path"):
        p = Path(cfg["ffmpeg_path"])
        if p.is_file():
            return p
    w = shutil.which("ffmpeg")
    return Path(w) if w else None


def download_ffmpeg(
    *,
    show_progress: bool = True,
    on_progress: Optional[Callable[[str], None]] = None,
) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Auto-download is for Windows. Install ffmpeg manually."

    if ffmpeg_already_installed() and FFMPEG_EXE.is_file():
        save_install_config(str(FFMPEG_EXE), str(FFPROBE_EXE))
        return True, "FFmpeg already installed"

    ensure_directories()

    if on_progress:
        on_progress("Downloading FFmpeg (~90 MB)…")

    last_pct = -1.0

    def reporthook(block_num: int, block_size: int, total_size: int) -> None:
        nonlocal last_pct
        downloaded = block_num * block_size
        if total_size > 0:
            pct = downloaded * 100.0 / total_size
            if pct - last_pct >= 0.3 or pct >= 99.9:
                last_pct = pct
                if on_progress:
                    on_progress(
                        f"Downloading FFmpeg: {pct:.0f}% "
                        f"({format_bytes(downloaded)} / {format_bytes(total_size)})"
                    )
                elif show_progress:
                    print_download_progress(downloaded, total_size, "Downloading FFmpeg")
        elif on_progress:
            on_progress(f"Downloading FFmpeg: {format_bytes(downloaded)}…")
        elif show_progress:
            print_download_progress(downloaded, 0, "Downloading FFmpeg")

    try:
        urlretrieve(FFMPEG_ZIP_URL, FFMPEG_ZIP_PATH, reporthook=reporthook)
    except Exception as e:
        progress_done()
        return False, f"Download failed: {e}"

    if on_progress:
        on_progress("Download complete. Extracting FFmpeg…")
    elif show_progress:
        print_download_progress(1, 1, "Downloading FFmpeg")
        progress_done()
        print("       ✔ Download complete", flush=True)
        print("       ◌ Extracting FFmpeg…", flush=True)

    extract_tmp = TOOLS_DIR / "ffmpeg_extract"
    if extract_tmp.exists():
        shutil.rmtree(extract_tmp, ignore_errors=True)
    extract_tmp.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(FFMPEG_ZIP_PATH, "r") as zf:
            members = zf.namelist()
            total = len(members) or 1
            for i, member in enumerate(members):
                zf.extract(member, extract_tmp)
                if i % max(1, total // 20) == 0:
                    pct = (i + 1) * 100.0 / total
                    if on_progress:
                        on_progress(f"Extracting FFmpeg: {pct:.0f}%")
                    elif show_progress:
                        print_extract_progress(min(99, pct))
    except Exception as e:
        progress_done()
        return False, f"Extract failed: {e}"

    if show_progress:
        print_extract_progress(100)
        progress_done()

    found = _find_ffmpeg_in_dir(extract_tmp)
    if not found:
        return False, "ffmpeg.exe not found in archive"

    probe = _find_ffprobe_near(found)
    if not probe:
        return False, "ffprobe.exe not found in archive"

    if FFMPEG_DIR.exists():
        shutil.rmtree(FFMPEG_DIR, ignore_errors=True)
    FFMPEG_BIN.mkdir(parents=True, exist_ok=True)
    shutil.copy2(found, FFMPEG_EXE)
    shutil.copy2(probe, FFPROBE_EXE)

    try:
        FFMPEG_ZIP_PATH.unlink(missing_ok=True)
        shutil.rmtree(extract_tmp, ignore_errors=True)
    except OSError:
        pass

    save_install_config(str(FFMPEG_EXE), str(FFPROBE_EXE), {"ffmpeg_source": "auto_download"})
    os.environ["FFMPEG_PATH"] = str(FFMPEG_EXE)
    return True, "FFmpeg installed successfully"


def verify_ffmpeg() -> tuple[bool, str]:
    ff = find_ffmpeg()
    if not ff:
        return False, "FFmpeg not found"
    try:
        r = subprocess.run(
            [str(ff), "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if r.returncode != 0:
            return False, "ffmpeg -version failed"
        line = (r.stdout or "").splitlines()[0] if r.stdout else "FFmpeg verified"
        probe = ff.parent / "ffprobe.exe"
        save_install_config(str(ff), str(probe) if probe.is_file() else str(ff))
        return True, line[:65]
    except Exception as e:
        return False, str(e)


def is_setup_complete() -> bool:
    ok_py, _ = check_python_version()
    ok_tk, _ = check_tkinter()
    ok_ff = ffmpeg_already_installed()
    return ok_py and ok_tk and ok_ff


def run_full_setup(
    *,
    quiet: bool = False,
    show_banner: bool = True,
    progress: Optional[Callable[[str], None]] = None,
) -> bool:
    use_console = not quiet and progress is None

    if show_banner and use_console:
        from console_theme import print_banner

        print_banner("install")
        print_planned_steps()

    def report(msg: str) -> None:
        if progress:
            progress(msg)

    def begin(num: int, label: str) -> None:
        report(f"[{num}/{TOTAL_STEPS}] {label}")
        if use_console:
            print_step(num, TOTAL_STEPS, label, "run")

    def finish(num: int, label: str, ok: bool = True) -> None:
        report(f"[{num}/{TOTAL_STEPS}] ✔ {label}")
        if use_console:
            print_step(num, TOTAL_STEPS, label, "ok" if ok else "fail")

    # [1/4] Python + GUI
    begin(1, "Checking Python and GUI…")
    ok, ver = check_python_version()
    if not ok:
        if use_console:
            print_error(ver)
        elif progress:
            progress(f"Error: {ver}")
        return False
    ok, tk_msg = check_tkinter()
    if not ok:
        if use_console:
            print_error(tk_msg)
        elif progress:
            progress(f"Error: {tk_msg}")
        return False
    finish(1, f"Python {ver} — {tk_msg}")

    # [2/4] Folders
    begin(2, "Creating application folders…")
    ensure_directories()
    finish(2, "Folders ready (output, tools, logs)")

    # [3/4] pip
    begin(3, "Installing Python packages…")
    if use_console:
        print_progress_bar(15, "pip", "Connecting…", inline=True)
    elif progress:
        progress("Installing Python packages…")
    ok, msg = run_pip_install(quiet=quiet or progress is not None)
    if use_console:
        print_progress_bar(100 if ok else 0, "pip", msg[:28], inline=True)
        progress_done()
    if not ok:
        if use_console:
            print_error(msg)
        elif progress:
            progress(f"Error: {msg}")
        return False
    finish(3, msg)

    # [4/4] FFmpeg
    begin(4, "Downloading and installing FFmpeg…")
    if not ffmpeg_already_installed():
        ok, msg = download_ffmpeg(
            show_progress=use_console,
            on_progress=progress,
        )
        if not ok:
            if use_console:
                print_error(msg)
            elif progress:
                progress(f"Error: {msg}")
            return False
        finish(4, msg)
    else:
        if use_console:
            progress_done()
        finish(4, "FFmpeg already installed")

    ok, msg = verify_ffmpeg()
    if not ok:
        if use_console:
            print_error(msg)
        elif progress:
            progress(f"Error: {msg}")
        return False
    report(f"Verified: {msg[:52]}")
    if use_console:
        print(f"       ✔ Verified: {msg[:52]}", flush=True)

    if use_console:
        print_success("install")
    elif progress:
        progress("Setup complete — all components ready.")
    return True


def main() -> int:
    quiet = "--quiet" in sys.argv or "-q" in sys.argv
    no_banner = "--no-banner" in sys.argv or quiet
    ok = run_full_setup(quiet=quiet, show_banner=not no_banner)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
