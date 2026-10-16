"""Behaviour tests for the pure-Python upscaling core.

The core has no Qt imports on purpose: it can be tested on any machine with
plain CPython, while the GUI layer is exercised on the target host.
"""

import json
from pathlib import Path

import pytest

from esrgan_upscaler import engine


# --- scale strategy ---------------------------------------------------------


def test_x4plus_is_a_native_x4_model():
    assert engine.native_scale("realesrgan-x4plus") == 4


def test_unknown_model_has_no_native_scale():
    assert engine.native_scale("nope-not-a-model") is None


def test_x2_on_a_native_x4_model_runs_x4_then_downscales():
    strategy = engine.plan_strategy("realesrgan-x4plus", 2)
    assert strategy.run_scale == 4
    assert strategy.downscale_to == 2
    assert strategy.native is False


def test_x4_on_a_native_x4_model_needs_no_downscale():
    strategy = engine.plan_strategy("realesrgan-x4plus", 4)
    assert strategy.run_scale == 4
    assert strategy.downscale_to is None
    assert strategy.native is True


def test_x2_on_an_anime_x2_model_is_native():
    strategy = engine.plan_strategy("realesr-animevideov3-x2", 2)
    assert strategy.run_scale == 2
    assert strategy.downscale_to is None
    assert strategy.native is True


def test_unsupported_scale_is_rejected():
    with pytest.raises(engine.UnsupportedScaleError):
        engine.plan_strategy("realesrgan-x4plus", 5)


# --- output naming ----------------------------------------------------------


def test_output_name_appends_scale_and_format():
    assert engine.output_name("portrait.png", 4, "png") == "portrait_x4.png"


def test_output_name_keeps_stem_of_names_with_dots():
    assert engine.output_name("scan.1998.final.jpg", 2, "jpg") == "scan.1998.final_x2.jpg"


def test_output_name_uses_source_extension_when_format_is_keep():
    assert engine.output_name("photo.jpeg", 4, None) == "photo_x4.jpeg"


def test_unknown_format_is_rejected():
    with pytest.raises(engine.UnsupportedFormatError):
        engine.output_name("photo.png", 4, "gif")


def test_normalise_format_maps_jpeg_to_jpg():
    assert engine.normalise_format("JPEG") == "jpg"
    assert engine.normalise_format("") is None
    assert engine.normalise_format(None) is None


# --- source discovery -------------------------------------------------------


def _touch(path: Path) -> Path:
    path.write_bytes(b"x")
    return path


def test_iter_inputs_returns_images_only_sorted(tmp_path):
    _touch(tmp_path / "b.png")
    _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "notes.txt")
    (tmp_path / "sub").mkdir()
    _touch(tmp_path / "sub" / "c.png")

    names = [p.name for p in engine.iter_inputs(tmp_path)]

    assert names == ["a.jpg", "b.png"]


def test_iter_inputs_skips_the_output_directory(tmp_path):
    src = tmp_path / "src"
    out = src / "upscaled"
    out.mkdir(parents=True)
    _touch(src / "keep.png")
    _touch(out / "already_x4.png")

    names = [p.name for p in engine.iter_inputs(src, exclude_dirs=[out])]

    assert names == ["keep.png"]


# --- command construction ---------------------------------------------------


def test_command_contains_model_directory_and_name():
    argv = engine.build_command(
        binary="/usr/bin/realesrgan-ncnn-vulkan",
        model_dir="/usr/share/realesrgan-ncnn-vulkan/models",
        model="realesrgan-x4plus",
        run_scale=4,
        source="/in/a.png",
        target="/out/a_x4.png",
        out_format="png",
        tile_size=256,
    )

    assert argv[0] == "/usr/bin/realesrgan-ncnn-vulkan"
    assert "-m" in argv and argv[argv.index("-m") + 1] == "/usr/share/realesrgan-ncnn-vulkan/models"
    assert "-n" in argv and argv[argv.index("-n") + 1] == "realesrgan-x4plus"
    assert argv[argv.index("-s") + 1] == "4"
    assert argv[argv.index("-i") + 1] == "/in/a.png"
    assert argv[argv.index("-o") + 1] == "/out/a_x4.png"
    assert argv[argv.index("-f") + 1] == "png"
    assert argv[argv.index("-t") + 1] == "256"


def test_command_omits_format_and_tile_when_not_requested():
    argv = engine.build_command(
        binary="realesrgan-ncnn-vulkan",
        model_dir="/m",
        model="realesrgan-x4plus",
        run_scale=4,
        source="/in/a.png",
        target="/out/a_x4.png",
        out_format=None,
        tile_size=None,
    )

    assert "-f" not in argv
    assert "-t" not in argv


# --- progress parsing -------------------------------------------------------


@pytest.mark.parametrize(
    "line,expected",
    [
        ("0.00%", 0.0),
        ("57.31%", 57.31),
        ("100.00%", 100.0),
        (" 12.5%", 12.5),
    ],
)
def test_parse_progress_reads_percentages(line, expected):
    assert engine.parse_progress(line) == pytest.approx(expected)


def test_parse_progress_ignores_other_output():
    assert engine.parse_progress("Usage: realesrgan-ncnn-vulkan -i infile") is None
    assert engine.parse_progress("") is None


# --- journal (idempotent batches) -------------------------------------------


def test_journal_marks_a_processed_file(tmp_path):
    src = _touch(tmp_path / "a.png")
    journal_path = tmp_path / "state.json"
    journal = engine.Journal(journal_path)

    assert journal.is_done(src, 4, "realesrgan-x4plus", "png") is False
    journal.mark_done(src, 4, "realesrgan-x4plus", "png")
    journal.save()

    reloaded = engine.Journal(journal_path)
    assert reloaded.is_done(src, 4, "realesrgan-x4plus", "png") is True


def test_journal_reprocesses_a_changed_source(tmp_path):
    src = _touch(tmp_path / "a.png")
    journal = engine.Journal(tmp_path / "state.json")
    journal.mark_done(src, 4, "realesrgan-x4plus", "png")

    src.write_bytes(b"much bigger payload")

    assert journal.is_done(src, 4, "realesrgan-x4plus", "png") is False


def test_journal_reprocesses_when_scale_changes(tmp_path):
    src = _touch(tmp_path / "a.png")
    journal = engine.Journal(tmp_path / "state.json")
    journal.mark_done(src, 4, "realesrgan-x4plus", "png")

    assert journal.is_done(src, 2, "realesrgan-x4plus", "png") is False


def test_journal_reprocesses_when_the_result_file_is_gone(tmp_path):
    """Removing a result by hand must bring the file back into the batch."""
    src = _touch(tmp_path / "a.png")
    out = tmp_path / "out"
    out.mkdir()
    target = _touch(out / "a_x4.png")
    journal = engine.Journal(tmp_path / "state.json")
    journal.mark_done(src, 4, "realesrgan-x4plus", "png", target=target)

    assert journal.is_done(src, 4, "realesrgan-x4plus", "png") is True

    target.unlink()

    assert journal.is_done(src, 4, "realesrgan-x4plus", "png") is False


def test_journal_survives_a_corrupt_state_file(tmp_path):
    journal_path = tmp_path / "state.json"
    journal_path.write_text("{not json at all", encoding="utf-8")

    journal = engine.Journal(journal_path)

    assert journal.is_done(tmp_path / "a.png", 4, "realesrgan-x4plus", "png") is False


def test_journal_writes_json_on_disk(tmp_path):
    src = _touch(tmp_path / "a.png")
    journal_path = tmp_path / "state.json"
    journal = engine.Journal(journal_path)
    journal.mark_done(src, 4, "realesrgan-x4plus", "png")
    journal.save()

    data = json.loads(journal_path.read_text(encoding="utf-8"))
    assert data["entries"], "journal must persist at least one entry"


# --- plan -------------------------------------------------------------------


def test_build_plan_pairs_every_source_with_a_target(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    _touch(src_dir / "a.png")
    _touch(src_dir / "b.jpg")
    out_dir = tmp_path / "out"

    plan = engine.build_plan(src_dir, out_dir, 4, "realesrgan-x4plus", "png")

    assert [job.target.name for job in plan] == ["a_x4.png", "b_x4.png"]
    assert all(job.target.parent == out_dir for job in plan)
