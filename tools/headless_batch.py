# SPDX-FileCopyrightText: 2026 SKBlacksmith (CrossNetwork)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Drive a batch through the real Qt runner without a display.

This is the smoke test for the runtime path (QProcess, journal, post
processing). Run it on the machine that owns the GPU:

    QT_QPA_PLATFORM=offscreen python tools/headless_batch.py \
        --source ~/UpscaleTest/in --result ~/UpscaleTest/out --scale 2

Exit code 0 means every planned file was produced; running it twice must
report nothing pending, which is how the idempotent batch design is checked.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from esrgan_upscaler import engine  # noqa: E402
from esrgan_upscaler.runner import Settings, UpscaleRunner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--model", default=engine.DEFAULT_MODEL)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--format", dest="out_format", default=None)
    parser.add_argument("--tile-size", type=int, default=256)
    parser.add_argument("--binary", default=engine.DEFAULT_BINARY)
    parser.add_argument("--model-dir", default=engine.DEFAULT_MODEL_DIR)
    args = parser.parse_args()

    application = QCoreApplication(sys.argv)

    settings = Settings(
        binary=args.binary,
        model_dir=args.model_dir,
        model=args.model,
        scale=args.scale,
        source_dir=args.source,
        result_dir=args.result,
        out_format=args.out_format,
        tile_size=args.tile_size,
    )

    jobs = engine.build_plan(args.source, args.result, args.scale, args.model, args.out_format)
    journal = engine.Journal(Path(args.result) / engine.JOURNAL_NAME)
    pending = [
        job
        for job in jobs
        if not journal.is_done(job.source, args.scale, args.model, args.out_format)
    ]
    print(f"planned={len(jobs)} pending={len(pending)}", flush=True)

    runner = UpscaleRunner()
    runner.logLine.connect(lambda line: print(f"  {line}", flush=True))
    runner.fileProgress.connect(lambda index, percent: print(f"  [{index}] {percent:.0f}%", flush=True))

    result = {"ok": 0, "failed": 0}

    def finished(ok: int, failed: int) -> None:
        result["ok"] = ok
        result["failed"] = failed
        application.quit()

    runner.batchFinished.connect(finished)
    QTimer.singleShot(0, lambda: runner.start(pending, settings))
    application.exec()

    print(f"RESULT ok={result['ok']} failed={result['failed']} expected={len(pending)}", flush=True)
    return 0 if result["failed"] == 0 and result["ok"] == len(pending) else 1


if __name__ == "__main__":
    raise SystemExit(main())
