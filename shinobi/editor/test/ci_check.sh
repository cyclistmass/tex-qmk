#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# CI check for the keymap editor, also runnable by hand on Linux or in WSL.
# usage: ci_check.sh <qmk_firmware dir> <work dir>
#   <qmk_firmware dir> is set up at the pinned commit (build_firmware.sh clones it if missing).
# The editor patches one release image, so it is tested against that release's sources, not HEAD's firmware:
#   1. download the release image named in shinobi_data.js and check its SHA-256;
#   2. unpack the shinobi folder at the release tag and lay this checkout's editor and generator over it;
#   3. regenerate shinobi_data.js there: it must equal the committed one;
#   4. run byte_identity.sh there (the default export compiles to the release; a patched image equals its build).
# Exits non-zero if any step fails. Prints one TIMING line per step.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
shinobi="$(cd "$here/../.." && pwd)"
repo="$(cd "$shinobi/.." && pwd)"
qmk_dir="$1"; work="$2"
timing() { echo "TIMING label=$1 start=$2 end=$(date +%s) seconds=$(( $(date +%s) - $2 )) result=$3"; }
field() { node -e 'require(process.argv[1]); process.stdout.write(String(globalThis.SHINOBI_DATA.release[process.argv[2]]))' "$shinobi/editor/shinobi_data.js" "$1"; }
tag="$(field tag)"; file="$(field file)"; sha="$(field sha256)"; date_str="$(field build_date)"
rm -rf "$work"; mkdir -p "$work/release" "$work/src" "$work/out"

t=$(date +%s)
curl -fsSL --retry 3 -m 120 -o "$work/release/$file" "https://github.com/cyclistmass/tex-qmk/releases/download/$tag/$file"
echo "$sha  $work/release/$file" | sha256sum -c -
timing release_download "$t" ok

t=$(date +%s)
git -C "$repo" archive "$tag" shinobi | tar -x -C "$work/src"
rm -rf "$work/src/shinobi/editor"
cp -r "$shinobi/editor" "$work/src/shinobi/editor"
cp "$shinobi/tools/gen_editor_data.py" "$work/src/shinobi/tools/"
python3 -I "$work/src/shinobi/tools/gen_editor_data.py" "$qmk_dir" "$work/release/$file" "$tag" "$date_str"
if cmp -s "$work/src/shinobi/editor/shinobi_data.js" "$shinobi/editor/shinobi_data.js"; then
    echo "PASS shinobi_data.js matches the $tag sources"; timing data_check "$t" ok
else
    echo "FAIL shinobi_data.js is stale: regenerate it with gen_editor_data.py (see shinobi/editor/README.md)"
    diff "$work/src/shinobi/editor/shinobi_data.js" "$shinobi/editor/shinobi_data.js" | head -20 || true
    timing data_check "$t" fail; exit 1
fi

t=$(date +%s)
bash "$work/src/shinobi/editor/test/byte_identity.sh" "$work/release/$file" "$work/out" "$qmk_dir"
timing byte_identity "$t" ok
