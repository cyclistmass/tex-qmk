#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the TEX Shinobi firmware against the pinned QMK commit and check the image.
#
# usage: shinobi/tools/build_firmware.sh <qmk_firmware dir> [keymap]
#
# Clones qmk_firmware into the directory if it is not there, checks out the commit in
# qmk_firmware.commit with its submodules, applies tools/patch_qmk_tree.sh, copies
# shinobi/qmk into the tree as keyboards/tex/shinobi and runs qmk compile. Needs git, python3 and the QMK CLI
# with the ARM toolchain (qmk setup, or the ghcr.io/qmk/qmk_cli container).
# The image lands in <qmk_firmware dir>/.build/tex_shinobi_<keymap>.bin and is checked
# against the stock IAP's limits (size, vector table, the record at 0x3BF8).
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
qmk_dir="$1"
keymap="${2:-default}"
commit="$(tr -d '[:space:]' < "$repo/qmk_firmware.commit")"

if [ ! -d "$qmk_dir/.git" ]; then
    git clone --filter=blob:none https://github.com/qmk/qmk_firmware.git "$qmk_dir"
fi
git -C "$qmk_dir" fetch --quiet origin "$commit" || true
git -C "$qmk_dir" checkout --quiet "$commit"
git -C "$qmk_dir" submodule update --init --recursive --quiet
"$repo/tools/patch_qmk_tree.sh" "$qmk_dir"
rm -rf "$qmk_dir/keyboards/tex/shinobi"
mkdir -p "$qmk_dir/keyboards/tex"
cp -r "$repo/qmk" "$qmk_dir/keyboards/tex/shinobi"
(cd "$qmk_dir" && qmk compile -kb tex/shinobi -km "$keymap")

bin="$qmk_dir/.build/tex_shinobi_${keymap}.bin"
python3 -I - "$repo/tools" "$bin" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import build_updater as bu
img = open(sys.argv[2], "rb").read()
sp, reset = bu.check_image(img)
print(f"{sys.argv[2]}: {len(img)} bytes of {bu.SLOT} ({bu.SLOT - len(img)} free), SP {sp:#x}, "
      f"reset {reset:#x}, record at 0x3BF8 present, sha256 {bu.sha(img)}")
PY
