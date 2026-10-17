# SPDX-FileCopyrightText: 2026 SKBlacksmith (CrossNetwork)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Qt 6 Widgets interface: an Upscale tab and a Settings tab.

Qt Widgets is used deliberately: on KDE Plasma the platform theme applies the
Breeze style and the application looks native without a QML layer.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __version__, engine
from .runner import Settings, UpscaleRunner

ORG_NAME = "qt-esrgan-upscaler"
APP_KEY = "qt-esrgan-upscaler"

FORMAT_CHOICES = [
    ("Keep source format", ""),
    ("PNG (lossless)", "png"),
    ("JPEG (smaller files)", "jpg"),
    ("WebP (lossless, compact)", "webp"),
]


class PathRow(QWidget):
    """A line edit with a *Browse* button, used for every folder setting."""

    def __init__(self, caption: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.edit = QLineEdit(self)
        self.button = QPushButton("Browse...", self)
        self.button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)
        self._caption = caption

    def _browse(self) -> None:
        start = self.edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, self._caption, start)
        if chosen:
            self.edit.setText(chosen)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(860, 620)

        self.runner = UpscaleRunner(self)
        self.tabs = QTabWidget(self)

        self.tabs.addTab(self._build_upscale_tab(), "Upscale")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.setCentralWidget(self.tabs)

        self._connect_runner()
        self._load_settings()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu = self.menuBar().addMenu("File")
        menu.addAction(quit_action)

    # -- Upscale tab ---------------------------------------------------------

    def _build_upscale_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        self.source_summary = QLabel("Choose the source and result folders in Settings.", page)
        self.source_summary.setWordWrap(True)
        layout.addWidget(self.source_summary)

        buttons = QHBoxLayout()
        self.upscale_button = QPushButton("Upscale", page)
        self.upscale_button.setDefault(True)
        self.upscale_button.clicked.connect(self.start_batch)
        self.stop_button = QPushButton("Stop", page)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.runner.stop)
        buttons.addWidget(self.upscale_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.status_label = QLabel("Idle.", page)
        layout.addWidget(self.status_label)

        self.batch_progress = QProgressBar(page)
        self.batch_progress.setRange(0, 100)
        layout.addWidget(self.batch_progress)

        self.file_progress = QProgressBar(page)
        self.file_progress.setRange(0, 100)
        layout.addWidget(self.file_progress)

        self.log_view = QPlainTextEdit(page)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view, 1)
        return page

    # -- Settings tab --------------------------------------------------------

    def _build_settings_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        model_box = QGroupBox("Model", page)
        model_form = QFormLayout(model_box)
        self.model_dir_row = PathRow("Model folder", model_box)
        self.model_combo = QComboBox(model_box)
        self.model_combo.addItems(sorted(engine.MODEL_NATIVE_SCALE))
        self.scale_combo = QComboBox(model_box)
        for scale in (2, 3, 4):
            self.scale_combo.addItem(f"x{scale}", scale)
        self.tile_spin = QSpinBox(model_box)
        self.tile_spin.setRange(0, 4096)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setSpecialValueText("auto")
        self.tile_spin.setToolTip(
            "Tile size passed to the upscaler. Smaller tiles need less GPU memory."
        )
        self.binary_row = PathRow("Upscaler binary", model_box)
        model_form.addRow("Model folder:", self.model_dir_row)
        model_form.addRow("Model:", self.model_combo)
        model_form.addRow("Upscale factor:", self.scale_combo)
        model_form.addRow("Tile size:", self.tile_spin)
        model_form.addRow("Binary:", self.binary_row)
        layout.addWidget(model_box)

        folders_box = QGroupBox("Folders and output", page)
        folders_form = QFormLayout(folders_box)
        self.source_row = PathRow("Source folder", folders_box)
        self.result_row = PathRow("Result folder", folders_box)
        self.format_combo = QComboBox(folders_box)
        for label, value in FORMAT_CHOICES:
            self.format_combo.addItem(label, value)
        self.format_combo.currentIndexChanged.connect(self._refresh_summary)
        folders_form.addRow("Source folder:", self.source_row)
        folders_form.addRow("Result folder:", self.result_row)
        folders_form.addRow("Output format:", self.format_combo)
        layout.addWidget(folders_box)

        hint = QLabel(
            "Images placed in the source folder are upscaled into the result folder. "
            "Files already processed with the same settings are skipped.",
            page,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(hint)
        layout.addStretch(1)

        for row in (
            self.model_dir_row,
            self.binary_row,
            self.source_row,
            self.result_row,
        ):
            row.edit.textChanged.connect(self._refresh_summary)
        self._refresh_summary()
        return page

    # -- settings persistence ------------------------------------------------

    def _settings(self) -> QSettings:
        return QSettings(ORG_NAME, APP_KEY)

    def _load_settings(self) -> None:
        store = self._settings()
        binary = store.value("binary", shutil.which(engine.DEFAULT_BINARY) or engine.DEFAULT_BINARY)
        if not Path(str(binary)).exists():
            binary = engine.DEFAULT_BINARY
        self.binary_row.setText(str(binary))
        self.model_dir_row.setText(str(store.value("model_dir", engine.DEFAULT_MODEL_DIR)))

        model = str(store.value("model", engine.DEFAULT_MODEL))
        index = self.model_combo.findText(model)
        self.model_combo.setCurrentIndex(index if index >= 0 else 0)

        scale = int(store.value("scale", 4))
        index = self.scale_combo.findData(scale)
        self.scale_combo.setCurrentIndex(index if index >= 0 else self.scale_combo.count() - 1)

        self.tile_spin.setValue(int(store.value("tile_size", 256)))
        self.source_row.setText(str(store.value("source_dir", "")))
        self.result_row.setText(str(store.value("result_dir", "")))

        out_format = str(store.value("out_format", ""))
        index = self.format_combo.findData(out_format)
        self.format_combo.setCurrentIndex(index if index >= 0 else 0)

    def _save_settings(self) -> None:
        store = self._settings()
        store.setValue("binary", self.binary_row.text())
        store.setValue("model_dir", self.model_dir_row.text())
        store.setValue("model", self.model_combo.currentText())
        store.setValue("scale", self.scale_combo.currentData())
        store.setValue("tile_size", self.tile_spin.value())
        store.setValue("source_dir", self.source_row.text())
        store.setValue("result_dir", self.result_row.text())
        store.setValue("out_format", self.format_combo.currentData())
        store.sync()

    def collect_settings(self) -> Settings:
        return Settings(
            binary=self.binary_row.text() or engine.DEFAULT_BINARY,
            model_dir=self.model_dir_row.text() or engine.DEFAULT_MODEL_DIR,
            model=self.model_combo.currentText(),
            scale=int(self.scale_combo.currentData()),
            source_dir=self.source_row.text(),
            result_dir=self.result_row.text(),
            out_format=self.format_combo.currentData() or None,
            tile_size=self.tile_spin.value(),
        )

    # -- batch control -------------------------------------------------------

    def start_batch(self) -> None:
        settings = self.collect_settings()
        problem = self._validate(settings)
        if problem:
            QMessageBox.warning(self, APP_NAME, problem)
            return
        self._save_settings()
        try:
            jobs = engine.build_plan(
                settings.source_dir,
                settings.result_dir,
                settings.scale,
                settings.model,
                settings.out_format,
            )
        except engine.UpscaleError as error:
            QMessageBox.warning(self, APP_NAME, str(error))
            return

        journal = engine.Journal(Path(settings.result_dir) / engine.JOURNAL_NAME)
        journal.forget_missing()
        pending = [
            job
            for job in jobs
            if not journal.is_done(job.source, settings.scale, settings.model, settings.out_format)
        ]
        skipped = len(jobs) - len(pending)
        if skipped:
            self._append(f"Skipping {skipped} file(s) already processed with these settings.")
        self.runner.start(pending, settings)

    def _validate(self, settings: Settings) -> Optional[str]:
        if not settings.source_dir or not Path(settings.source_dir).is_dir():
            return "The source folder does not exist. Choose it in Settings."
        if not settings.result_dir:
            return "The result folder is not set. Choose it in Settings."
        if Path(settings.source_dir).resolve() == Path(settings.result_dir).resolve():
            return "The source and result folders must differ."
        if not Path(settings.model_dir).is_dir():
            return f"The model folder does not exist: {settings.model_dir}"
        if shutil.which(settings.binary) is None and not Path(settings.binary).exists():
            return f"The upscaler binary was not found: {settings.binary}"
        return None

    def _refresh_summary(self) -> None:
        source = self.source_row.text() or "(not set)"
        result = self.result_row.text() or "(not set)"
        scale = self.scale_combo.currentData() if hasattr(self, "scale_combo") else 4
        self.source_summary.setText(
            f"Source: {source}\nResult: {result}\nUpscale factor: x{scale}"
        )

    # -- runner wiring -------------------------------------------------------

    def _connect_runner(self) -> None:
        self.runner.logLine.connect(self._append)
        self.runner.runningChanged.connect(self._on_running_changed)
        self.runner.fileStarted.connect(self._on_file_started)
        self.runner.fileProgress.connect(self._on_file_progress)
        self.runner.fileFinished.connect(self._on_file_finished)
        self.runner.batchFinished.connect(self._on_batch_finished)

    def _append(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_running_changed(self, running: bool) -> None:
        self.upscale_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.tabs.setTabEnabled(1, not running)
        if running:
            self.status_label.setText("Working...")
        else:
            self.batch_progress.setValue(0)
            self.file_progress.setValue(0)

    def _on_file_started(self, index: int, source: str) -> None:
        total = max(1, self.runner.total_jobs)
        self.status_label.setText(f"[{index + 1}/{total}] {Path(source).name}")
        self.batch_progress.setValue(int(index / total * 100))

    def _on_file_progress(self, index: int, percent: float) -> None:
        self.file_progress.setValue(int(percent))

    def _on_file_finished(self, index: int, ok: bool, message: str) -> None:
        self.file_progress.setValue(100 if ok else 0)

    def _on_batch_finished(self, ok: int, failed: int) -> None:
        self.batch_progress.setValue(100)
        self.status_label.setText(f"Finished: {ok} done, {failed} failed.")
        if ok or failed:
            self._save_settings()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        if self.runner.is_running:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "A batch is still running. Stop it and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop()
        self._save_settings()
        event.accept()


def main(argv: Optional[list[str]] = None) -> int:
    application = QApplication(argv if argv is not None else sys.argv)
    application.setApplicationName(APP_NAME)
    application.setOrganizationName(ORG_NAME)
    application.setDesktopFileName(APP_KEY)
    # No applicationDisplayName: KDE appends it to the window title, which
    # already carries the application name and would then appear twice.
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
