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


def test_encode_webp_lossless_keeps_every_pixel(tmp_path):
    source = _make(tmp_path / "src.png", size=(16, 8), color=(17, 99, 200))
    target = tmp_path / "out.webp"

    size = image_ops.encode_webp(source, target, "lossless")

    assert size > 0
    with Image.open(target) as encoded, Image.open(source) as original:
        assert encoded.format == "WEBP"
        assert list(encoded.convert("RGB").getdata()) == list(original.convert("RGB").getdata())


def test_encode_webp_lossy_profile_actually_loses_something(tmp_path):
    # Size ordering is not a property worth asserting on synthetic images —
    # a flat or tiny picture can compress better lossily than losslessly. What
    # must hold is that the lossy profile changes pixels and lossless does not.
    source = tmp_path / "src.png"
    image = Image.new("RGB", (32, 32))
    image.putdata([((x * 37) % 256, (x * 91) % 256, (x * 57) % 256) for x in range(32 * 32)])
    image.save(source)
    lossless = tmp_path / "lossless.webp"
    small = tmp_path / "small.webp"

    image_ops.encode_webp(source, lossless, "lossless")
    image_ops.encode_webp(source, small, "small")

    with Image.open(source) as original:
        expected = list(original.convert("RGB").getdata())
    with Image.open(lossless) as encoded:
        assert list(encoded.convert("RGB").getdata()) == expected
    with Image.open(small) as encoded:
        assert list(encoded.convert("RGB").getdata()) != expected


def test_encode_webp_rejects_an_unknown_profile(tmp_path):
    source = _make(tmp_path / "src.png")
    with pytest.raises(Exception):
        image_ops.encode_webp(source, tmp_path / "out.webp", "q42")
