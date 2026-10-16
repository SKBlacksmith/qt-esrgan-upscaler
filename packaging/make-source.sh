#!/bin/bash
# Build the source archive the PKGBUILD consumes from this git repository.
#
# The GitHub repository is private, so makepkg cannot download the release
# tarball anonymously. This script produces the same layout from the local
# checkout: qt-esrgan-upscaler-<version>.tar.gz with a single top-level
# directory, which is exactly what the PKGBUILD expects.
#
# Usage:  ./packaging/make-source.sh [tag]
#         (no argument: the tag v<version from PKGBUILD>, falling back to HEAD)

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"

pkgver="$(sed -n 's/^pkgver=//p' "$here/PKGBUILD")"
pkgname="$(sed -n 's/^pkgname=//p' "$here/PKGBUILD")"
tag="${1:-v$pkgver}"

if ! git -C "$repo" rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  echo "tag $tag not found; archiving HEAD instead" >&2
  tag="HEAD"
fi

archive="$here/$pkgname-$pkgver.tar.gz"
rm -f "$archive"
git -C "$repo" archive --format=tar.gz --prefix="$pkgname-$pkgver/" -o "$archive" "$tag"

echo "archive: $archive"
echo "size:    $(stat -c %s "$archive") bytes"
echo "sha256:  $(sha256sum "$archive" | cut -d' ' -f1)"
echo
echo "Next: cd $here && makepkg -si"
