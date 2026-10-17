# SPDX-FileCopyrightText: 2026 Sergey Kuznetsov (SKBlacksmith)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the Pillow-backed helpers (skipped when Pillow is absent)."""

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from esrgan_upscaler import image_ops  # noqa: E402


def _make(path, size=(8, 4), color=(10, 20, 30), orientation=None):
    image = Image.new("RGB", size, color)
    if orientation is not None:
        exif = image.getexif()
        exif[0x0112] = orientation
        image.save(path, exif=exif)
    else:
        image.save(path)
    return path


def test_read_orientation_returns_one_without_exif(tmp_path):
    path = _make(tmp_path / "plain.jpg")
    assert image_ops.read_orientation(path) == 1


def test_read_orientation_reads_the_exif_tag(tmp_path):
    path = _make(tmp_path / "rotated.jpg", orientation=6)
    assert image_ops.read_orientation(path) == 6


def test_read_orientation_tolerates_a_non_image(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"definitely not a png")
    assert image_ops.read_orientation(path) == 1


def test_apply_orientation_rewrites_a_rotated_source(tmp_path):
    source = _make(tmp_path / "src.jpg", size=(8, 4), orientation=6)
    target = _make(tmp_path / "out.jpg", size=(16, 8))

    assert image_ops.apply_orientation(source, target) is True
    assert image_ops.image_size(target) == (8, 16)


def test_apply_orientation_leaves_upright_images_alone(tmp_path):
    source = _make(tmp_path / "src.jpg", size=(8, 4))
    target = _make(tmp_path / "out.jpg", size=(16, 8))

    assert image_ops.apply_orientation(source, target) is False
    assert image_ops.image_size(target) == (16, 8)


def test_downscale_halves_the_pixels(tmp_path):
    path = _make(tmp_path / "big.png", size=(64, 32))

    assert image_ops.downscale(path, 1, 2) == (32, 16)
    assert image_ops.image_size(path) == (32, 16)


def test_downscale_rejects_non_positive_factors(tmp_path):
    path = _make(tmp_path / "big.png")
    with pytest.raises(ValueError):
        image_ops.downscale(path, 1, 0)


def test_downscale_keeps_jpegs_as_jpegs(tmp_path):
    path = _make(tmp_path / "photo.jpg", size=(40, 20))
    image_ops.downscale(path, 1, 2)
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert image.size == (20, 10)
