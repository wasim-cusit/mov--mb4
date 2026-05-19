"""
MOV → MP4 converter core (pCloud streaming optimized).
No web server required — used by the desktop GUI.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


MAX_OUTPUT_BYTES_DEFAULT = 10 * 1024**3  # 10 GB

RESOLUTION_PRESETS = {
    "1920x1080": (1920, 1080),
    "1280x720": (1280, 720),
    "original": None,
}

PROFILE_LEVELS = {
    "high": "4.1",
    "baseline": "3.0",
}

# lesson_01 / topic_02 / chapter_3 → Topic_01.mp4
LESSON_FOLDER_RE = re.compile(
    r"^(?:lesson|topic|topice|chapter|unit|lecture|part|module)[_\s\-]*(\d+)\s*$",
    re.IGNORECASE,
)


@dataclass
class ConvertSettings:
    resolution: str = "1280x720"
    fps_mode: str = "keep"  # keep | fixed
    fps_value: int = 30
    crf: int = 23
    preset: str = "medium"
    profile: str = "high"  # high | baseline
    level: str = "4.1"
    video_bitrate_kbps: int = 0  # 0 = CRF mode
    audio_bitrate_kbps: int = 128
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    max_output_gb: float = 10.0
    faststart: bool = True
    sanitize_names: bool = True
    use_hardware: bool = False
    parallel_jobs: int = 1
    course_folder_layout: bool = True
    topic_prefix: str = "Topic"

    @property
    def max_output_bytes(self) -> int:
        return int(self.max_output_gb * 1024**3)


@dataclass
class JobResult:
    input_path: str
    output_path: str
    success: bool
    message: str
    output_size_bytes: int = 0


@dataclass
class BatchProgress:
    total: int = 0
    completed: int = 0
    current_file: str = ""
    current_percent: float = 0.0
    status: str = "idle"  # idle | running | done | error | cancelled
    log_lines: list[str] = field(default_factory=list)
    results: list[JobResult] = field(default_factory=list)


def _install_config_ffmpeg() -> Optional[str]:
    cfg_path = Path(__file__).parent / "install_config.json"
    if not cfg_path.is_file():
        return None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        fp = data.get("ffmpeg_path")
        if fp and Path(fp).is_file():
            return str(Path(fp).resolve())
    except (json.JSONDecodeError, OSError):
        pass
    return None


def find_ffmpeg() -> Optional[str]:
    """Locate ffmpeg executable."""
    env = os.environ.get("FFMPEG_PATH") or os.environ.get("FFMPEG")
    if env and Path(env).is_file():
        return str(Path(env).resolve())

    installed = _install_config_ffmpeg()
    if installed:
        return installed

    found = shutil.which("ffmpeg")
    if found:
        return found

    candidates = [
        Path(__file__).parent / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(__file__).parent / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(__file__).parent / "ffmpeg.exe",
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p.resolve())
    return None


def find_ffprobe(ffmpeg_path: str) -> Optional[str]:
    ffprobe = Path(ffmpeg_path).parent / "ffprobe.exe"
    if ffprobe.is_file():
        return str(ffprobe)
    return shutil.which("ffprobe")


def sanitize_filename(name: str) -> str:
    stem = Path(name).stem
    s = stem.lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "video"


def format_topic_prefix(prefix: str) -> str:
    p = (prefix or "Topic").strip()
    if not p:
        return "Topic"
    if len(p) == 1:
        return p.upper()
    return p[0].upper() + p[1:]


def topic_name_from_folder(folder_name: str, prefix: str = "Topic") -> str:
    """lesson_01 → Topic_01, topic_12 → Topic_12"""
    prefix_clean = format_topic_prefix(prefix)
    name = folder_name.strip()

    m = LESSON_FOLDER_RE.match(name)
    if m:
        return f"{prefix_clean}_{int(m.group(1)):02d}"

    digits = re.findall(r"\d+", name)
    if digits:
        return f"{prefix_clean}_{int(digits[0]):02d}"

    safe = sanitize_filename(name)
    return f"{prefix_clean}_{safe}" if safe else prefix_clean


def _unique_basename(out_dir_key: str, base: str, used_names: dict[str, set[str]]) -> str:
    used = used_names.setdefault(out_dir_key, set())
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    candidate = f"{base}_{n}"
    used.add(candidate)
    return candidate


def resolve_output_path(
    input_path: Path,
    input_root: Path,
    output_root: Path,
    settings: ConvertSettings,
    used_names: Optional[dict[str, set[str]]] = None,
) -> Path:
    """
    Course layout (default):
      in:  courses/anatomy/lesson_01/video.mov
      out: courses/anatomy/Topic_01.mp4   (no lesson_01 subfolder)

    Input root should be the ``courses`` folder (or any parent you select).
    """
    used_names = used_names if used_names is not None else {}
    input_root = input_root.resolve()
    output_root = output_root.resolve()
    input_path = input_path.resolve()

    try:
        rel = input_path.relative_to(input_root)
    except ValueError:
        rel = Path(input_path.name)

    parts = list(rel.parts)
    if not parts:
        parts = [input_path.name]

    file_part = parts[-1]

    if not settings.course_folder_layout:
        if len(parts) > 1:
            out_dir = output_root.joinpath(*parts[:-1])
        else:
            out_dir = output_root
        if settings.sanitize_names:
            base = sanitize_filename(file_part)
        else:
            base = Path(file_part).stem
        out_key = str(out_dir).lower()
        base = _unique_basename(out_key, base, used_names)
        return out_dir / f"{base}.mp4"

    # --- Course layout: flatten lesson/topic folders into subject folder ---
    if len(parts) == 1:
        out_dir = output_root
        base = sanitize_filename(file_part) if settings.sanitize_names else Path(file_part).stem
    elif len(parts) == 2:
        # subject/video.mov  OR  lesson_01/video.mov
        parent = parts[0]
        if LESSON_FOLDER_RE.match(parent) or re.search(r"\d+", parent):
            out_dir = output_root
            base = topic_name_from_folder(parent, settings.topic_prefix)
        else:
            out_dir = output_root / parent
            base = sanitize_filename(file_part) if settings.sanitize_names else Path(file_part).stem
    else:
        # anatomy/lesson_01/video.mov  →  anatomy/Topic_01.mp4
        parent = parts[-2]
        subject_parts = parts[:-2]
        out_dir = output_root.joinpath(*subject_parts) if subject_parts else output_root
        base = topic_name_from_folder(parent, settings.topic_prefix)

    out_key = str(out_dir).lower()
    base = _unique_basename(out_key, base, used_names)
    return out_dir / f"{base}.mp4"


def preview_output_path(
    input_path: Path,
    input_root: Path,
    output_root: Path,
    settings: ConvertSettings,
) -> str:
    """Relative path string for UI preview."""
    p = resolve_output_path(input_path, input_root, output_root, settings, used_names={})
    try:
        return str(p.relative_to(output_root.resolve())).replace("\\", "/")
    except ValueError:
        return p.name


def probe_video(ffprobe: str, path: str) -> dict:
    cmd = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(out.stderr or "ffprobe failed")
    return json.loads(out.stdout)


def get_duration_seconds(probe_data: dict) -> float:
    try:
        return float(probe_data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return 0.0


def get_source_resolution(probe_data: dict) -> tuple[int, int]:
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            w = int(stream.get("width") or 0)
            h = int(stream.get("height") or 0)
            if w and h:
                return w, h
    return 0, 0


def calc_max_video_bitrate_kbps(duration_sec: float, settings: ConvertSettings) -> int:
    """Cap bitrate so output stays under max_output_bytes."""
    if duration_sec <= 0:
        return 3500
    audio_kbps = settings.audio_bitrate_kbps
    total_bits = settings.max_output_bytes * 8
    audio_bits = audio_kbps * 1000 * duration_sec
    video_bits = max(total_bits - audio_bits, total_bits * 0.85)
    video_kbps = int(video_bits / duration_sec / 1000)
    return max(500, min(video_kbps, 20000))


def recommended_bitrate_kbps(resolution: str) -> tuple[int, int]:
    if resolution == "1920x1080":
        return 4000, 6000
    if resolution == "1280x720":
        return 2000, 3500
    return 2000, 4000


def build_ffmpeg_command(
    ffmpeg: str,
    input_path: str,
    output_path: str,
    settings: ConvertSettings,
    duration_sec: float,
    source_w: int,
    source_h: int,
) -> list[str]:
    cmd = [ffmpeg, "-y", "-hide_banner", "-i", input_path]

    # Video filter: scale + optional fps
    vf_parts: list[str] = []
    res = RESOLUTION_PRESETS.get(settings.resolution)
    if res:
        w, h = res
        vf_parts.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        vf_parts.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
    elif settings.resolution == "original" and source_w and source_h:
        pass
    else:
        vf_parts.append("scale=1280:720:force_original_aspect_ratio=decrease")

    if settings.fps_mode == "fixed":
        vf_parts.append(f"fps={settings.fps_value}")

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    # Video codec
    if settings.use_hardware:
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", settings.preset])

    profile = settings.profile
    level = settings.level or PROFILE_LEVELS.get(profile, "4.1")
    cmd.extend(["-profile:v", profile, "-level", str(level), "-pix_fmt", "yuv420p"])

    # Bitrate / quality
    max_kbps = calc_max_video_bitrate_kbps(duration_sec, settings)
    lo, hi = recommended_bitrate_kbps(settings.resolution)
    target_kbps = settings.video_bitrate_kbps
    if target_kbps <= 0:
        target_kbps = min(hi, max(lo, (lo + hi) // 2))
    target_kbps = min(target_kbps, max_kbps)

    if settings.video_bitrate_kbps > 0 or settings.crf <= 0:
        cmd.extend(["-b:v", f"{target_kbps}k", "-maxrate", f"{target_kbps}k", "-bufsize", f"{target_kbps * 2}k"])
    else:
        crf = min(settings.crf, 28)
        cmd.extend(["-crf", str(crf)])
        if max_kbps < 8000:
            cmd.extend(["-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps * 2}k"])

    cmd.extend(["-threads", "0"])

    # Audio
    cmd.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            f"{settings.audio_bitrate_kbps}k",
            "-ar",
            str(settings.audio_sample_rate),
            "-ac",
            str(settings.audio_channels),
        ]
    )

    if settings.faststart:
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(output_path)
    return cmd


def parse_ffmpeg_progress(line: str, duration_sec: float) -> Optional[float]:
    if duration_sec <= 0 or "time=" not in line:
        return None
    m = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d+)", line)
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    current = h * 3600 + mi * 60 + s
    return min(99.9, (current / duration_sec) * 100)


class ConversionEngine:
    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self.ffprobe_path: Optional[str] = None
        if self.ffmpeg_path:
            self.ffprobe_path = find_ffprobe(self.ffmpeg_path)
        self._cancel = threading.Event()
        self.progress = BatchProgress()

    @property
    def is_ready(self) -> bool:
        return bool(self.ffmpeg_path and self.ffprobe_path and Path(self.ffmpeg_path).is_file())

    def cancel(self) -> None:
        self._cancel.set()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def list_mov_files(self, folder: str, recursive: bool = False) -> list[Path]:
        root = Path(folder)
        if not root.is_dir():
            return []
        pattern = "**/*.mov" if recursive else "*.mov"
        files = sorted(root.glob(pattern), key=lambda p: p.name.lower())
        files += sorted(root.glob(pattern.replace("mov", "MOV")), key=lambda p: p.name.lower())
        seen = set()
        unique: list[Path] = []
        for f in files:
            key = str(f.resolve()).lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _log(self, msg: str, on_log: Optional[Callable[[str], None]] = None) -> None:
        self.progress.log_lines.append(msg)
        if on_log:
            on_log(msg)

    def _run_ffmpeg(
        self,
        cmd: list[str],
        duration_sec: float,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> tuple[bool, str]:
        if not self.ffmpeg_path:
            return False, "FFmpeg not found"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            if self._cancel.is_set():
                proc.kill()
                return False, "Cancelled"
            output_lines.append(line.rstrip())
            pct = parse_ffmpeg_progress(line, duration_sec)
            if pct is not None:
                self.progress.current_percent = pct
                if on_progress:
                    on_progress(pct)

        proc.wait()
        tail = "\n".join(output_lines[-15:])
        if proc.returncode != 0:
            return False, tail or f"FFmpeg exited with code {proc.returncode}"
        return True, "OK"

    def convert_one(
        self,
        input_path: Path,
        output_root: Path,
        input_root: Path,
        settings: ConvertSettings,
        used_names: Optional[dict[str, set[str]]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> JobResult:
        if not self.is_ready:
            return JobResult(str(input_path), "", False, "Install FFmpeg and set path in the app.")

        output_path = resolve_output_path(input_path, input_root, output_root, settings, used_names)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            probe = probe_video(self.ffprobe_path, str(input_path))
        except Exception as e:
            return JobResult(str(input_path), str(output_path), False, f"Probe failed: {e}")

        duration = get_duration_seconds(probe)
        sw, sh = get_source_resolution(probe)

        cmd = build_ffmpeg_command(
            self.ffmpeg_path,
            str(input_path),
            str(output_path),
            settings,
            duration,
            sw,
            sh,
        )
        self._log(f"Converting: {input_path.name} → {output_path.name}", on_log)
        self._log(f"Output: {output_path}", on_log)
        self._log(" ".join(cmd), on_log)

        ok, msg = self._run_ffmpeg(cmd, duration, on_progress)
        if not ok:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            return JobResult(str(input_path), str(output_path), False, msg)

        size = output_path.stat().st_size if output_path.exists() else 0
        if size > settings.max_output_bytes:
            self._log(f"Output {size / 1024**3:.2f} GB exceeds limit — re-encoding smaller...", on_log)
            tighter = ConvertSettings(**{**settings.__dict__, "crf": min(settings.crf + 4, 28), "video_bitrate_kbps": calc_max_video_bitrate_kbps(duration, settings) // 2})
            output_path.unlink(missing_ok=True)
            cmd2 = build_ffmpeg_command(self.ffmpeg_path, str(input_path), str(output_path), tighter, duration, sw, sh)
            ok2, msg2 = self._run_ffmpeg(cmd2, duration, on_progress)
            if not ok2:
                return JobResult(str(input_path), str(output_path), False, msg2)
            size = output_path.stat().st_size if output_path.exists() else 0

        if size > settings.max_output_bytes:
            return JobResult(
                str(input_path),
                str(output_path),
                False,
                f"Still too large ({size / 1024**3:.2f} GB). Try 720p, higher CRF, or lower bitrate.",
                size,
            )

        return JobResult(str(input_path), str(output_path), True, f"Done ({size / 1024**2:.1f} MB)", size)

    def convert_batch(
        self,
        files: list[Path],
        output_dir: str,
        input_dir: str,
        settings: ConvertSettings,
        on_log: Optional[Callable[[str], None]] = None,
        on_file_progress: Optional[Callable[[int, int, str, float], None]] = None,
    ) -> list[JobResult]:
        self.reset_cancel()
        out = Path(output_dir)
        inp = Path(input_dir)
        self.progress = BatchProgress(total=len(files), status="running")
        results: list[JobResult] = []
        used_names: dict[str, set[str]] = {}

        for idx, fpath in enumerate(files):
            if self._cancel.is_set():
                self.progress.status = "cancelled"
                break

            self.progress.current_file = fpath.name
            self.progress.current_percent = 0.0

            def _pct(p: float) -> None:
                self.progress.current_percent = p
                if on_file_progress:
                    on_file_progress(idx + 1, len(files), fpath.name, p)

            result = self.convert_one(
                fpath, out, inp, settings, used_names=used_names, on_log=on_log, on_progress=_pct
            )
            results.append(result)
            self.progress.results.append(result)
            self.progress.completed = idx + 1

            if on_file_progress:
                on_file_progress(idx + 1, len(files), fpath.name, 100.0 if result.success else 0.0)

        self.progress.status = "cancelled" if self._cancel.is_set() else "done"
        return results
