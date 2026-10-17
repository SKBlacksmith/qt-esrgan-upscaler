# SPDX-FileCopyrightText: 2026 Sergey Kuznetsov (SKBlacksmith)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pixel-level helpers around the upscaler (Pillow based).

Real-ESRGAN works on raw pixels: it neither reads EXIF orientation nor writes
any metadata back. These helpers put the orientation back into the result and
perform the Lanczos reduction that turns a native x4 output into a real x2/x3.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

#: EXIF orientation tag numbers mapped onto :meth:`PIL.Image.Image.transpose`.
ORIENTATION_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

_JPEG_QUALITY = 95

#: Pillow refuses to guess a format from the ``.tmp`` name we write through, so
#: the format is always stated explicitly.
SAVE_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


def read_orientation(path: os.PathLike | str) -> int:
    """Return the EXIF orientation of ``path`` (1 when absent or unreadable)."""
    try:
        with Image.open(path) as image:
            exif = image.getexif()
    except (OSError, ValueError):
        return 1
    try:
        return int(exif.get(0x0112, 1) or 1)
    except (TypeError, ValueError):
        return 1


def matches_orientation(source: os.PathLike | str, target: os.PathLike | str) -> bool:
    """True when the result must be rotated to look like the source."""
    return read_orientation(source) != 1 and read_orientation(target) == 1


def apply_orientation(source: os.PathLike | str, target: os.PathLike | str) -> bool:
    """Bake the source's EXIF orientation into the upscaled ``target``.

    Returns ``True`` when the file was rewritten.
    """
    orientation = read_orientation(source)
    if orientation == 1:
        return False
    transpose = ORIENTATION_TRANSPOSE.get(orientation)
    if transpose is None:
        return False
    _rewrite(target, lambda image: image.transpose(transpose))
    return True


def downscale(
    path: os.PathLike | str,
    numerator: int,
    denominator: int,
    *,
    quality: int = _JPEG_QUALITY,
) -> tuple[int, int]:
    """Resize ``path`` in place by ``numerator / denominator`` (Lanczos).

    Returns the new pixel size. Used to turn the native x4 output of a
    photographic model into an exact x2/x3, which the tool itself cannot do
    reliably (running ``-s 2`` on an x4 network produced a broken mosaic).
    """
    if numerator <= 0 or denominator <= 0:
        raise ValueError("scale factors must be positive")

    def resized(image: Image.Image) -> Image.Image:
        width = max(1, round(image.width * numerator / denominator))
        height = max(1, round(image.height * numerator / denominator))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    return _rewrite(path, resized, quality=quality)


def image_size(path: os.PathLike | str) -> Optional[tuple[int, int]]:
    """Pixel size of an image, or ``None`` when it cannot be read."""
    try:
        with Image.open(path) as image:
            return image.size
    except (OSError, ValueError):
        return None


def _rewrite(path, transform, quality: int = _JPEG_QUALITY) -> tuple[int, int]:
    """Apply ``transform`` to the image at ``path`` and save it back."""
    target = Path(path)
    suffix = target.suffix.lower()
    save_format = SAVE_FORMATS.get(suffix)
    if save_format is None:
        raise ValueError(f"cannot rewrite {target.name}: unsupported extension")
    with Image.open(target) as original:
        original.load()
        image = transform(original)
        save_kwargs = {}
        if save_format == "JPEG":
            save_kwargs = {"quality": quality, "subsampling": 0, "optimize": True}
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
        temporary = target.with_name(target.name + ".tmp")
        image.save(temporary, format=save_format, **save_kwargs)
        size = image.size
    os.replace(temporary, target)
    return size
