# Changelog

## 0.2.5

- JPEG output goes through the same path as WebP: the upscaler writes a
  lossless PNG and the application encodes the final JPEG at quality 95 with
  4:4:4 chroma. Before this, a JPEG written at the model's native x4 carried
  the upscaler's own quality while the "quality 95" label suggested otherwise.
- With that, every label in the format selector states what actually happens.

## 0.2.4

- WebP output is now encoded once, at a quality you choose: `Lossless`
  (default), `High q95`, `Balanced q90` or `Small q80`.
- Fixed a silent double compression: the upscaler wrote WebP with its own fixed
  settings and the post-processing step then re-encoded the file through
  Pillow's default, which is lossy quality 80. The tool is now asked for a
  lossless PNG and the single WebP encode happens at the end.
- On a 25.7-megapixel photographic scan, lossless WebP is about 30 % smaller
  than PNG (17.0 MB against 24.5 MB) with identical pixels.
- The misleading "WebP (lossless, compact)" format label is gone, and the
  encoding profile is part of the journal key: changing it redoes the batch.

## 0.2.3

- New models in the selector: `realesr-general-x4v3` and its denoise-tuned
  sibling `realesr-general-wdn-x4v3`. Both are native x4 SRVGGNetCompact
  networks aimed at ordinary photographs rather than anime, and both are
  lighter on VRAM and time than `realesrgan-x4plus`.
- The ncnn binary takes no `-dn` flag, so denoise strength is a model choice,
  not a number; the selector exposes the wdn variant for that reason.
- The `.bin`/`.param` pairs are not in the official 0.2.5.0 archive and are
  installed into the shared model folder separately.

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
