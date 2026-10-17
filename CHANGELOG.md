# Changelog

## 0.2.2

- New monochrome application icon: three nested windows, the inner ones anchored
  to the bottom-right corner (1:2:4). Ships as SVG plus PNG at 16-512 px; the
  16-24 px renditions are simplified to two levels so they stay legible.
- The window icon comes from the icon theme when installed, with a source-tree
  fallback for development runs.

## 0.2.1

- Commits and annotated tags are signed with an SSH key; the public key and an
  `allowed_signers` list ship in `keys/`, so history can be verified offline.
- README and `AUTHORS.md` explain what a signature proves and what it does not.

## 0.2.0

- Relicensed from MIT to GPL-3.0-or-later; every source file carries an SPDX
  header.
- Copyright holder named as Sergey Kuznetsov (SKBlacksmith); `AUTHORS.md`
  records what the human author contributes and what the models write.
- Documentation for anonymous HTTPS fetches and for migrating clones that still
  carry an access token in `origin`.

## 0.1.1

- Window title no longer repeats the application name.
- The Arch package is built from a source archive generated from the git tag.

## 0.1.0

- First release: Qt 6 front-end with an Upscale tab and a Settings tab, batch
  processing through `realesrgan-ncnn-vulkan`, EXIF-aware output, an idempotent
  journal, per-file progress and a log pane.
