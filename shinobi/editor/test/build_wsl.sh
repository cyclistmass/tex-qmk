#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Builds a keymap.c as the "default" keymap with a fixed build date, for the editor's byte-identity test.
# usage (inside WSL or Linux): build_wsl.sh <qmk_firmware dir> <keymap.c> <build date> <out.bin>
# The keymap goes in as "default" because Fn+B types the keymap name: a patched release image says "default" too.
# Prints one timing line: TIMING label=... start=... end=... seconds=... result=...
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
qmk_dir="$1"; keymap_c="$2"; date_str="$3"; out="$4"
start=$(date +%s)
shim="$(mktemp -d)"
trap 'rm -rf "$shim"' EXIT
ln -s "$here/qmk_fixed_date.sh" "$shim/qmk"
export TEX_REAL_QMK="${TEX_REAL_QMK:-$(command -v qmk)}"
export TEX_BUILDDATE="$date_str"
export PATH="$shim:$PATH"
# build_firmware.sh copies shinobi/qmk into the tree; swap the default keymap in a copy of the repo's qmk folder.
work="$(mktemp -d)"
trap 'rm -rf "$shim" "$work"' EXIT
cp -r "$here/../../tools" "$here/../../qmk_firmware.commit" "$work/"
cp -r "$here/../../qmk" "$work/qmk"
cp "$keymap_c" "$work/qmk/keymaps/default/keymap.c"
rm -f "$qmk_dir/.build/tex_shinobi_default.bin"
result=fail
if bash "$work/tools/build_firmware.sh" "$qmk_dir" default > "$work/build.log" 2>&1; then
    cp "$qmk_dir/.build/tex_shinobi_default.bin" "$out"
    result=ok
else
    tail -30 "$work/build.log" >&2
fi
end=$(date +%s)
echo "TIMING label=wsl_build start=$start end=$end seconds=$((end - start)) result=$result"
[ "$result" = ok ]
