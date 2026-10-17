# SPDX-FileCopyrightText: 2026 Sergey Kuznetsov (SKBlacksmith)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Qt-side execution of the upscaling queue.

One file at a time is handed to ``realesrgan-ncnn-vulkan`` through a
``QProcess``; the tool's output is streamed back so the interface can show a
live percentage. Post-processing (Lanczos reduction and EXIF orientation) runs
in a worker thread, because it touches files that can be hundreds of megabytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QObject, QRunnable, QProcess, QThreadPool, Signal

from . import engine, image_ops


@dataclass
class Settings:
    """Everything the runner needs, mirroring the Settings tab."""

    binary: str = engine.DEFAULT_BINARY
    model_dir: str = engine.DEFAULT_MODEL_DIR
    model: str = engine.DEFAULT_MODEL
    scale: int = 4
    source_dir: str = ""
    result_dir: str = ""
    out_format: Optional[str] = None  # None keeps the source extension
    tile_size: int = 256  # 0 lets the tool choose


class _PostProcessSignals(QObject):
    finished = Signal(int, bool, str)


class _PostProcessTask(QRunnable):
    """Downscale and/or fix the orientation of a finished result."""

    def __init__(self, index: int, source: Path, target: Path, strategy: engine.Strategy):
        super().__init__()
        self.index = index
        self.source = source
        self.target = target
        self.strategy = strategy
        self.signals = _PostProcessSignals()

    def run(self) -> None:  # pragma: no cover - exercised on the target host
        try:
            if self.strategy.downscale_to is not None:
                image_ops.downscale(
                    self.target, self.strategy.downscale_to, self.strategy.run_scale
                )
            rotated = image_ops.apply_orientation(self.source, self.target)
            note = "orientation applied" if rotated else ""
            self.signals.finished.emit(self.index, True, note)
        except Exception as error:  # noqa: BLE001 - reported to the user as text
            self.signals.finished.emit(self.index, False, str(error))


class UpscaleRunner(QObject):
    """Sequentially drives one QProcess at a time over a list of jobs."""

    batchStarted = Signal(int)
    fileStarted = Signal(int, str)
    fileProgress = Signal(int, float)
    fileFinished = Signal(int, bool, str)
    batchFinished = Signal(int, int)
    logLine = Signal(str)
    runningChanged = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._jobs: list[engine.Job] = []
        self._index = 0
        self._ok = 0
        self._failed = 0
        self._strategy: Optional[engine.Strategy] = None
        self._settings = Settings()
        self._journal: Optional[engine.Journal] = None
        self._running = False
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    # -- public API ----------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def total_jobs(self) -> int:
        """Number of files in the batch currently being processed."""
        return len(self._jobs)

    def start(self, jobs: Sequence[engine.Job], settings: Settings) -> None:
        if self._running:
            return
        if not jobs:
            self.logLine.emit("Nothing to do: the source folder has no new images.")
            self.batchFinished.emit(0, 0)
            return

        self._jobs = list(jobs)
        self._settings = settings
        self._index = 0
        self._ok = 0
        self._failed = 0
        self._strategy = engine.plan_strategy(settings.model, settings.scale)
        self._journal = engine.Journal(Path(settings.result_dir) / engine.JOURNAL_NAME)
        Path(settings.result_dir).mkdir(parents=True, exist_ok=True)

        if not self._strategy.native:
            self.logLine.emit(
                f"{settings.model} is a native x{self._strategy.run_scale} model: "
                f"each file is upscaled x{self._strategy.run_scale} and then reduced "
                f"to x{self._strategy.downscale_to}."
            )

        self._set_running(True)
        self.batchStarted.emit(len(self._jobs))
        self._start_next()

    def stop(self) -> None:
        """Stop after the current file; the running process is terminated."""
        if not self._running:
            return
        self.logLine.emit("Stopping: finishing the current file, then quitting the batch.")
        self._jobs = self._jobs[: self._index + 1]
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(5000):
                self._process.kill()

    # -- internals -----------------------------------------------------------

    def _set_running(self, value: bool) -> None:
        if self._running != value:
            self._running = value
            self.runningChanged.emit(value)

    def _start_next(self) -> None:
        if self._index >= len(self._jobs):
            self._finish_batch()
            return

        job = self._jobs[self._index]
        if self._strategy is None:
            return
        argv = engine.build_command(
            binary=self._settings.binary,
            model_dir=self._settings.model_dir,
            model=self._settings.model,
            run_scale=self._strategy.run_scale,
            source=job.source,
            target=job.target,
            out_format=self._settings.out_format,
            tile_size=self._settings.tile_size or None,
        )

        self.fileStarted.emit(self._index, str(job.source))
        self.logLine.emit("$ " + " ".join(argv))

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self._read_output(process))
        process.finished.connect(lambda code, status: self._on_process_finished(code, status))
        process.errorOccurred.connect(lambda error: self._on_process_error(error))
        self._process = process
        process.start(argv[0], argv[1:])

    def _read_output(self, process: QProcess) -> None:
        raw = bytes(process.readAllStandardOutput())
        text = raw.decode("utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            percent = engine.parse_progress(stripped)
            if percent is not None:
                self.fileProgress.emit(self._index, percent)
            else:
                self.logLine.emit(stripped)

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self.logLine.emit(
                f"Cannot start {self._settings.binary!r}: check the binary path in Settings."
            )
            self._failed += 1
            self.fileFinished.emit(self._index, False, "failed to start")
            self._index += 1
            self._start_next()

    def _on_process_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        job = self._jobs[self._index]
        self._process = None
        if status == QProcess.CrashExit:
            self.logLine.emit(f"Cancelled: {job.source.name}")
            self.fileFinished.emit(self._index, False, "cancelled")
            self._finish_batch()
            return
        if code != 0:
            self.logLine.emit(f"{job.source.name}: the upscaler exited with code {code}")
            self._failed += 1
            self.fileFinished.emit(self._index, False, f"exit code {code}")
            self._index += 1
            self._start_next()
            return

        task = _PostProcessTask(self._index, job.source, job.target, self._strategy)
        task.signals.finished.connect(self._on_post_processed)
        self._pool.start(task)

    def _on_post_processed(self, index: int, ok: bool, message: str) -> None:
        job = self._jobs[index]
        if ok:
            self._ok += 1
            if self._journal is not None:
                self._journal.mark_done(
                    job.source,
                    self._settings.scale,
                    self._settings.model,
                    self._settings.out_format,
                    target=job.target,
                )
                self._journal.save()
            detail = f" ({message})" if message else ""
            self.logLine.emit(f"Done: {job.target.name}{detail}")
        else:
            self._failed += 1
            self.logLine.emit(f"{job.target.name}: post-processing failed: {message}")
        self.fileFinished.emit(index, ok, message)
        self._index += 1
        if self._index >= len(self._jobs):
            self._finish_batch()
        else:
            self._start_next()

    def _finish_batch(self) -> None:
        self._process = None
        self._set_running(False)
        self.logLine.emit(f"Batch finished: {self._ok} done, {self._failed} failed.")
        self.batchFinished.emit(self._ok, self._failed)
