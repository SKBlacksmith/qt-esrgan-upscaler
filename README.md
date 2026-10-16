# qt-esrgan-upscaler

A native Qt 6 / KDE desktop front-end for batch image upscaling with
[Real-ESRGAN ncnn Vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan).

Drop images into a source folder, press **Upscale**, and the upscaled copies
appear in the result folder. Settings (model folder, model, upscale factor,
source folder, result folder, output format) live in a separate tab and are
remembered between runs.

## Why this exists

Real-ESRGAN ships as a command-line tool only. This application wraps it in a
small, native-looking KDE/Qt 6 shell so that batch upscaling does not require
remembering flags, hand-writing loops over files, or converting between
formats by hand.

## Features

- **Native KDE look** - Qt 6 Widgets with the system Breeze style, no Electron
  or web runtime.
- **Batch by folder** - every image in the source folder is processed into the
  result folder; sub-folders and the result folder itself are skipped.
- **Settings tab** - model folder, model selection, upscale factor (x1-x4),
  source folder, result folder, output format (keep / PNG / JPEG / WebP) and
  tile size for GPU memory control.
- **Honest scale factors** - Real-ESRGAN models are native x4. Requesting x2 on
  a photographic model runs the native x4 network and then resizes the output
  down with a Lanczos filter, which is the only correct way to get a real x2
  from an x4 network.
- **Idempotent batches** - a journal in the result folder remembers what has
  already been processed, so pressing *Upscale* twice does not redo finished
  work.
- **EXIF orientation is preserved** - JPEGs shot in portrait do not come out
  sideways.
- **Progress and log view** - per-file percentage taken from the tool's own
  output, plus a log pane for the full command output.

## Requirements

- Arch Linux (or any distribution with Qt 6 and Python 3.11+)
- `realesrgan-ncnn-vulkan` with its model files
  (`/usr/share/realesrgan-ncnn-vulkan/models` in the Arch package)
- A Vulkan-capable GPU

## Install (Arch Linux)

Build the package from `packaging/PKGBUILD`, or run from a checkout:

```bash
python -m venv .venv && .venv/bin/pip install PySide6 Pillow
.venv/bin/python -m esrgan_upscaler
```

With the distribution packages already present on the host:

```bash
python -m esrgan_upscaler
```

## Usage

1. Open the **Settings** tab.
2. Set the model folder (defaults to `/usr/share/realesrgan-ncnn-vulkan/models`)
   and pick a model.
3. Pick the upscale factor: 2, 3 or 4.
4. Pick the source folder and the result folder.
5. Optionally choose the output format; *keep* preserves the source extension.
6. Go back to the **Upscale** tab and press **Upscale**.

Result files are named `<name>_x<factor>.<ext>`, for example `portrait_x4.png`.

## Development

The project is split so that the logic can be tested without a desktop session:

- `src/esrgan_upscaler/engine.py` - pure Python: scale strategy, file
  discovery, command construction, progress parsing, journal. No Qt imports.
- `src/esrgan_upscaler/runner.py` - Qt `QProcess` queue that drives the engine.
- `src/esrgan_upscaler/gui.py` - the Qt 6 Widgets interface.

Run the tests:

```bash
python -m pytest tests/ -q
```

## License

MIT
