#!/usr/bin/env bash
set -euo pipefail

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

version=$(python3 -S -c 'from etchlib import __version__; print(__version__)')
archive=${1:-"$scratch/etch-${version}.tar.gz"}
prefix="etch-${version}/"

git archive --format=tar --prefix="$prefix" HEAD | gzip -n > "$archive"
git archive --format=tar --prefix="$prefix" HEAD | gzip -n > "$scratch/rebuilt.tar.gz"
cmp "$archive" "$scratch/rebuilt.tar.gz"

python3 - "$archive" <<'PYTHON'
import hashlib
import pathlib
import sys

archive = pathlib.Path(sys.argv[1])
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name + ".sha256").write_text("{}  {}\n".format(digest, archive.name))
PYTHON

mkdir "$scratch/unpacked" "$scratch/home"
tar -xzf "$archive" -C "$scratch/unpacked"
release_root="$scratch/unpacked/etch-${version}"
(
  cd "$scratch"
  test "$(env -u PYTHONPATH HOME="$scratch/home" python3 -S "$release_root/etch" --version)" = "Etch $version"
  env -u PYTHONPATH HOME="$scratch/home" python3 -S "$release_root/etch" doctor \
    --repo "$release_root/examples/minimal" --profile developer
  env -u PYTHONPATH HOME="$scratch/home" python3 -S "$release_root/etch" plan \
    --repo "$release_root/examples/minimal" --profile developer
)
