# SPDX-FileCopyrightText: 2026 Sergey Kuznetsov (SKBlacksmith)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pure-Python core of the batch upscaler.

Nothing in this module imports Qt: the scale strategy, file discovery,
command construction, progress parsing and the processing journal are all
plain Python so that they can be tested without a desktop session.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

DEFAULT_BINARY = "realesrgan-ncnn-vulkan"
DEFAULT_MODEL_DIR = "/usr/share/realesrgan-ncnn-vulkan/models"
DEFAULT_MODEL = "realesrgan-x4plus"

#: Models shipped with realesrgan-ncnn-vulkan 0.2.5.0 and the scale each one
#: is trained for. A model is *native* at exactly this factor.
MODEL_NATIVE_SCALE = {
    "realesrgan-x4plus": 4,
    "realesrgan-x4plus-anime": 4,
    "realesrnet-x4plus": 4,
    "realesr-animevideov3-x2": 2,
    "realesr-animevideov3-x3": 3,
    "realesr-animevideov3-x4": 4,
}

INPUT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

#: Accepted values of the "output format" setting, mapped to the extension and
#: to the ``-f`` flag understood by the tool.
OUTPUT_FORMATS = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp"}

SUPPORTED_SCALES = (1, 2, 3, 4)

#: The tool prints one percentage per line while it works.
PROGRESS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

#: Name of the journal file stored inside the result folder.
JOURNAL_NAME = ".upscale-journal.json"


class UpscaleError(Exception):
    """Base class for errors raised by this module."""


class UnsupportedScaleError(UpscaleError):
    """The requested scale factor is not supported."""


class UnsupportedFormatError(UpscaleError):
    """The requested output format is not supported."""


class UnknownModelError(UpscaleError):
    """The model is not one of the known Real-ESRGAN ncnn models."""


@dataclass(frozen=True)
class Strategy:
    """How a requested scale factor is actually produced."""

    requested: int
    run_scale: int
    downscale_to: Optional[int]
    native: bool


@dataclass(frozen=True)
class Job:
    """One source image and the file it must produce."""

    source: Path
    target: Path


def native_scale(model: str) -> Optional[int]:
    """Return the scale the model was trained for, or ``None`` if unknown."""
    return MODEL_NATIVE_SCALE.get(model)


def plan_strategy(model: str, requested: int) -> Strategy:
    """Work out how to reach ``requested`` with ``model``.

    The networks are trained for one fixed factor. Asking an x4 network for x2
    directly produces a broken mosaic (verified on hardware), so a smaller
    factor is produced by running the native scale and resizing the result
    down afterwards.
    """
    if not isinstance(requested, int) or requested not in SUPPORTED_SCALES:
        raise UnsupportedScaleError(f"scale x{requested} is not supported")

    model_scale = native_scale(model)
    if model_scale is None:
        raise UnknownModelError(f"unknown model: {model}")

    if requested == model_scale:
        return Strategy(requested, model_scale, None, True)
    if requested < model_scale:
        return Strategy(requested, model_scale, requested, False)
    raise UnsupportedScaleError(
        f"{model} is trained for x{model_scale} and cannot reach x{requested}"
    )


def normalise_format(value: Optional[str]) -> Optional[str]:
    """Map a user-supplied format string onto ``png``/``jpg``/``webp``."""
    if value is None:
        return None
    cleaned = str(value).strip().lower().lstrip(".")
    if not cleaned or cleaned == "keep":
        return None
    if cleaned not in OUTPUT_FORMATS:
        raise UnsupportedFormatError(f"unsupported output format: {value}")
    return OUTPUT_FORMATS[cleaned]


def output_name(source_name: str, scale: int, out_format: Optional[str]) -> str:
    """Build the result file name for one source file."""
    stem = Path(source_name).stem
    fmt = normalise_format(out_format)
    if fmt is None:
        extension = Path(source_name).suffix.lstrip(".").lower()
        if extension not in {ext.lstrip(".") for ext in INPUT_EXTENSIONS}:
            raise UnsupportedFormatError(
                f"cannot keep the extension of {source_name!r}; choose a format"
            )
    else:
        extension = fmt
    return f"{stem}_x{scale}.{extension}"


def iter_inputs(
    directory: os.PathLike | str,
    exclude_dirs: Iterable[os.PathLike | str] = (),
) -> list[Path]:
    """List the images in ``directory`` (non-recursive), sorted by name.

    Directories that must never be scanned (typically the result folder when it
    lives inside the source folder) are skipped.
    """
    root = Path(directory)
    if not root.is_dir():
        return []

    excluded = {Path(item).resolve() for item in exclude_dirs}
    found: list[Path] = []
    for entry in root.iterdir():
        if entry.is_dir():
            continue
        if entry.suffix.lower() not in INPUT_EXTENSIONS:
            continue
        if entry.resolve().parent in excluded:
            continue
        found.append(entry)
    return sorted(found, key=lambda path: path.name.lower())


def build_command(
    binary: str,
    model_dir: str,
    model: str,
    run_scale: int,
    source: os.PathLike | str,
    target: os.PathLike | str,
    out_format: Optional[str] = None,
    tile_size: Optional[int] = None,
) -> list[str]:
    """Assemble the argv for one file."""
    argv = [
        binary,
        "-i", str(source),
        "-o", str(target),
        "-s", str(run_scale),
        "-n", model,
        "-m", model_dir,
    ]
    fmt = normalise_format(out_format)
    if fmt is not None:
        argv += ["-f", fmt]
    if tile_size:
        argv += ["-t", str(tile_size)]
    return argv


def parse_progress(line: str) -> Optional[float]:
    """Extract the percentage from one line of the tool's output."""
    if not line:
        return None
    match = PROGRESS_RE.search(line)
    if match is None:
        return None
    return float(match.group(1))


def build_plan(
    source_dir: os.PathLike | str,
    result_dir: os.PathLike | str,
    scale: int,
    model: str,
    out_format: Optional[str],
) -> list[Job]:
    """Pair every source image with the file it must produce."""
    result_root = Path(result_dir)
    jobs: list[Job] = []
    for source in iter_inputs(source_dir, exclude_dirs=[result_root]):
        name = output_name(source.name, scale, out_format)
        jobs.append(Job(source=source, target=result_root / name))
    return jobs


class Journal:
    """Remembers which files were already processed.

    Entries are keyed by absolute source path plus the settings that produced
    the result, and store the source size and mtime: a file that changed after
    being processed is picked up again.
    """

    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._entries = {}
            return
        entries = raw.get("entries") if isinstance(raw, dict) else None
        self._entries = entries if isinstance(entries, dict) else {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "entries": self._entries}, indent=2)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent,
            prefix=self.path.name, suffix=".tmp", delete=False,
        )
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self.path)

    # -- queries -------------------------------------------------------------

    @staticmethod
    def _key(source: os.PathLike | str, scale: int, model: str, out_format: Optional[str]) -> str:
        fmt = normalise_format(out_format) or "keep"
        return f"{Path(source).resolve()}|x{scale}|{model}|{fmt}"

    @staticmethod
    def _fingerprint(source: os.PathLike | str) -> Optional[dict]:
        try:
            stat = os.stat(source)
        except OSError:
            return None
        return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    def is_done(
        self,
        source: os.PathLike | str,
        scale: int,
        model: str,
        out_format: Optional[str],
    ) -> bool:
        entry = self._entries.get(self._key(source, scale, model, out_format))
        if not entry:
            return False
        fingerprint = self._fingerprint(source)
        if fingerprint is None:
            return False
        if entry.get("size") != fingerprint["size"] or entry.get("mtime_ns") != fingerprint["mtime_ns"]:
            return False
        # A result that was deleted by hand belongs back in the batch.
        recorded_target = entry.get("target")
        if recorded_target and not Path(recorded_target).exists():
            return False
        return True

    def mark_done(
        self,
        source: os.PathLike | str,
        scale: int,
        model: str,
        out_format: Optional[str],
        target: Optional[os.PathLike | str] = None,
    ) -> None:
        fingerprint = self._fingerprint(source)
        if fingerprint is None:
            return
        entry = dict(fingerprint)
        entry["target"] = str(target) if target is not None else None
        self._entries[self._key(source, scale, model, out_format)] = entry

    def forget_missing(self) -> None:
        """Drop entries whose source file no longer exists."""
        for key in list(self._entries):
            path = key.split("|", 1)[0]
            if not Path(path).exists():
                del self._entries[key]
