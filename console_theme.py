"""
Aligned console UI for install/run — progress bars, steps, download %.
Developer: MUHAMMAD WASIM | +923257627554
"""

from __future__ import annotations

import sys
from typing import Optional

from app_info import APP_NAME, APP_VERSION, DEVELOPER_NAME, DEVELOPER_PHONE

# Layout (must match console_ui.ps1)
INNER = 58
MARGIN = "  "
BAR_W = 44

_C = "\033[0m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_MAGENTA = "\033[95m"
_BLUE = "\033[94m"
_DIM = "\033[90m"
_WHITE = "\033[97m"
_BOLD = "\033[1m"

_last_progress_len = 0


def enable_ansi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            k = ctypes.windll.kernel32  # type: ignore[attr-defined]
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _pad(text: str, width: int = INNER, align: str = "left") -> str:
    t = text[:width]
    if align == "center":
        return t.center(width)
    if align == "right":
        return t.rjust(width)
    return t.ljust(width)


def _box_top(char: str = "═") -> None:
    print(f"{MARGIN}╔{'═' * INNER}╗", flush=True)


def _box_mid() -> None:
    print(f"{MARGIN}╠{'═' * INNER}╣", flush=True)


def _box_bot() -> None:
    print(f"{MARGIN}╚{'═' * INNER}╝", flush=True)


def _box_line(text: str, color: str = _WHITE, align: str = "left") -> None:
    padded = _pad(text[:INNER], INNER, align)
    print(f"{MARGIN}║{color}{padded}{_C}║", flush=True)


def _box_empty() -> None:
    print(f"{MARGIN}║{' ' * INNER}║", flush=True)


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / 1024**2:.1f} MB"
    return f"{n / 1024**3:.2f} GB"


def print_banner(mode: str = "install") -> None:
    """Full header box — aligned."""
    enable_ansi()
    print(flush=True)
    _box_top()
    _box_empty()
    _box_line("MOV  ──►  MP4", _MAGENTA, "center")
    _box_line("pCloud Streaming Converter", _CYAN, "center")
    _box_empty()
    if mode == "install":
        _box_line("FULL SETUP  •  Installing all components", _YELLOW, "center")
    else:
        _box_line("LAUNCH  •  Video Converter Ready", _YELLOW, "center")
    _box_line(f"Version {APP_VERSION}", _DIM, "center")
    _box_mid()
    _box_line(f"Developer : {DEVELOPER_NAME}", _WHITE)
    _box_line(f"Contact   : {DEVELOPER_PHONE}", _GREEN)
    _box_bot()
    print(flush=True)


def print_section(title: str) -> None:
    print(f"{MARGIN}{_CYAN}{_BOLD}▸ {title}{_C}", flush=True)
    print(f"{MARGIN}{_DIM}{'─' * INNER}{_C}", flush=True)


def print_planned_steps() -> None:
    print_section("Installation plan")
    steps = [
        "Python environment",
        "Application folders",
        "Python packages (pip)",
        "FFmpeg download (~90 MB)",
    ]
    for i, s in enumerate(steps, 1):
        print(f"{MARGIN}  {_DIM}[{i}/4]{_C} {s}", flush=True)
    print(flush=True)


def print_step(num: int, total: int, label: str, status: str = "run") -> None:
    """status: run | ok | fail | skip"""
    icons = {"run": f"{_YELLOW}◌{_C}", "ok": f"{_GREEN}✔{_C}", "fail": f"{_RED}✖{_C}", "skip": f"{_DIM}○{_C}"}
    icon = icons.get(status, icons["run"])
    prefix = f"[{num}/{total}]"
    print(f"{MARGIN}  {icon} {_DIM}{prefix:<8}{_C} {label}", flush=True)


def print_progress_bar(
    percent: float,
    label: str,
    detail: str = "",
    *,
    inline: bool = True,
) -> None:
    """Draw aligned progress bar. inline=True updates same line."""
    global _last_progress_len
    pct = max(0.0, min(100.0, percent))
    filled = int(BAR_W * pct / 100)
    bar = f"{_GREEN}{'█' * filled}{_DIM}{'░' * (BAR_W - filled)}{_C}"
    pct_s = f"{pct:5.1f}%"
    line = f"{MARGIN}  {label:<22} [{bar}] {pct_s}"
    if detail:
        line += f"  {_DIM}{detail}{_C}"

    if inline:
        pad = max(0, _last_progress_len - len(line) + 20)
        sys.stdout.write("\r" + line + " " * min(pad, 40))
        sys.stdout.flush()
        _last_progress_len = len(line) + 20
    else:
        print(line, flush=True)


def progress_done() -> None:
    """End inline progress line."""
    global _last_progress_len
    print(flush=True)
    _last_progress_len = 0


def print_download_progress(
    downloaded: int,
    total: int,
    phase: str = "Downloading FFmpeg",
) -> None:
    if total > 0:
        pct = downloaded * 100.0 / total
        detail = f"{format_bytes(downloaded)} / {format_bytes(total)}"
    else:
        pct = 0.0
        detail = format_bytes(downloaded)
    print_progress_bar(pct, phase, detail, inline=True)


def print_extract_progress(percent: float = 50.0) -> None:
    print_progress_bar(percent, "Extracting FFmpeg", "Please wait…", inline=True)


def print_success(mode: str = "install") -> None:
    progress_done()
    print(flush=True)
    _box_top()
    if mode == "install":
        _box_line("✔  SETUP COMPLETED SUCCESSFULLY", _GREEN, "center")
    else:
        _box_line("✔  ALL COMPONENTS READY", _GREEN, "center")
    _box_bot()
    print(f"{MARGIN}{_YELLOW}Next:{_C} Double-click  {_BOLD}run.bat{_C}  to open the converter.", flush=True)
    print(f"{MARGIN}{_DIM}{DEVELOPER_NAME}  •  {DEVELOPER_PHONE}{_C}", flush=True)
    print(flush=True)


def print_error(message: str) -> None:
    progress_done()
    print(flush=True)
    _box_top()
    _box_line("✖  SETUP FAILED", _RED, "center")
    _box_mid()
    for chunk in _wrap(message, INNER - 4):
        _box_line(chunk, _YELLOW)
    _box_bot()
    print(f"{MARGIN}{_DIM}Contact: {DEVELOPER_NAME}  •  {DEVELOPER_PHONE}{_C}", flush=True)
    print(flush=True)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text[:width]]


enable_ansi()
