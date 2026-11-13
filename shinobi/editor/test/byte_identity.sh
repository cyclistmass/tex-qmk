#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# The editor's acceptance test: what the page patches into the release image must be byte-identical to a C build of
# the keymap.c it exports.
# usage: byte_identity.sh <release tex_shinobi_vX.bin> <out dir> <qmk_firmware dir>
#   On Windows (Git Bash) the build runs in WSL (TEX_WSL_DISTRO, default Ubuntu-24.04) and <qmk_firmware dir> is a
#   path inside it; on Linux it runs here. The QMK CLI and ARM toolchain must be set up (build_firmware.sh).
# Steps: node identifies the release by its sha256, checks the editor core and writes default_keymap.c, custom_keymap.c and custom_patched.bin; both
# keymaps are compiled with the release's build date; the default must equal the release, the custom one the patch.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
release="$1"; out="$2"; qmk_dir="$3"
mkdir -p "$out"
timing() { echo "TIMING label=$1 start=$2 end=$(date +%s) seconds=$(( $(date +%s) - $2 )) result=$3"; }

t=$(date +%s)
node "$here/make_keymaps.cjs" "$release" "$out"
date_str="$(cat "$out/build_date")"
timing core_checks "$t" ok

to_build_path() { # a path the build side can open
    if command -v wsl >/dev/null 2>&1 && [ "$(uname -o 2>/dev/null)" = Msys ]; then
        local m; m="$(cygpath -m "$1")"; echo "/mnt/$(echo "${m:0:1}" | tr A-Z a-z)${m:2}"
    else echo "$1"; fi
}
build() { # keymap.c -> bin
    local km out_bin; km="$(to_build_path "$1")"; out_bin="$(to_build_path "$2")"
    if command -v wsl >/dev/null 2>&1 && [ "$(uname -o 2>/dev/null)" = Msys ]; then
        local script; script="$(to_build_path "$here/build_wsl.sh")"
        # --exec: wsl.exe would expand $VARS in a command line itself. TEX_QMK_VENV is the QMK CLI's venv bin.
        MSYS_NO_PATHCONV=1 wsl -d "${TEX_WSL_DISTRO:-Ubuntu-24.04}" -u root --exec env \
            PATH="${TEX_QMK_VENV:-/root/qmkenv/bin}:/usr/local/bin:/usr/bin:/bin" \
            bash "$script" "$qmk_dir" "$km" "$date_str" "$out_bin"
    else
        bash "$here/build_wsl.sh" "$qmk_dir" "$km" "$date_str" "$out_bin"
    fi
}
rm -f "$out/default_compiled.bin" "$out/custom_compiled.bin"
build "$out/default_keymap.c" "$out/default_compiled.bin"
build "$out/custom_keymap.c" "$out/custom_compiled.bin"
t=$(date +%s)
fail=0
if cmp -s "$out/default_compiled.bin" "$release"; then echo "PASS exported default keymap.c compiles to the release image"; else echo "FAIL default build differs from the release"; fail=1; fi
if cmp -s "$out/custom_compiled.bin" "$out/custom_patched.bin"; then echo "PASS custom keymap: patched release == compiled keymap.c ($(sha256sum "$out/custom_patched.bin" | cut -c1-16)…)"; else echo "FAIL custom build differs from the patch"; cmp -l "$out/custom_compiled.bin" "$out/custom_patched.bin" | head; fail=1; fi
timing compare "$t" "$([ $fail = 0 ] && echo ok || echo fail)"
exit $fail
