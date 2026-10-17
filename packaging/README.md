# Building the Arch package

The package is not published on the AUR. The source repository is public and
can be fetched anonymously over HTTPS; no SSH key or token is needed to pull
updates. The package source archive is generated locally from the selected git
tag so the build uses the exact source revision.

## Build and install

Existing clones created while the repository was private may still embed an
access token in `origin`. Migrate once to anonymous HTTPS fetches (pushes remain
authenticated):

```bash
git remote set-url origin https://github.com/SKBlacksmith/qt-esrgan-upscaler.git
git remote set-url --push origin git@github.com:SKBlacksmith/qt-esrgan-upscaler.git
```

Then build and install:

```bash
# 1. update the working copy
git pull

# 2. (only when the version changed) edit pkgver in PKGBUILD and commit a tag
#    git tag -a v0.2.0 -m v0.2.0 && git push origin v0.2.0

# 3. produce the source archive from that tag
./packaging/make-source.sh

# 4. build and install
cd packaging
makepkg -s          # add -i to install in the same step, or:
sudo pacman -U qt-esrgan-upscaler-*.pkg.tar.zst
```

`makepkg` refuses to run as root; build as a normal user with `sudo` rights.

## Dependencies

- `pyside6`, `python-pillow`, `python` - from the official repositories.
- `realesrgan-ncnn-vulkan` - satisfied by the AUR package
  `realesrgan-ncnn-vulkan-bin` (`provides=realesrgan-ncnn-vulkan`).
- Build only: `python-build`, `python-installer`, `python-setuptools`,
  `python-wheel`.

## What the package installs

| Path | Content |
|---|---|
| `/usr/bin/esrgan-upscaler` | entry point created from the wheel |
| `/usr/lib/python3.*/site-packages/esrgan_upscaler/` | the application |
| `/usr/share/applications/qt-esrgan-upscaler.desktop` | menu entry |
| `/usr/share/icons/hicolor/scalable/apps/qt-esrgan-upscaler.svg` | icon |
| `/usr/share/licenses/qt-esrgan-upscaler/LICENSE` | licence |

The application only writes to the user's `~/.config/qt-esrgan-upscaler/`
(settings) and to the result folder chosen in the interface; the journal lives
in the result folder as `.upscale-journal.json`.

## Removing a development install

If an earlier development copy was installed for the user only, remove it so
that the menu does not list the application twice:

```bash
rm -f ~/.local/bin/esrgan-upscaler \
      ~/.local/share/applications/qt-esrgan-upscaler.desktop \
      ~/.local/share/icons/hicolor/scalable/apps/qt-esrgan-upscaler.svg
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```
