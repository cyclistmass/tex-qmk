#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Stands in for the qmk CLI so a build can carry a chosen QMK_BUILDDATE: Fn+B types the build date, so without this
# no two builds are byte-identical. `qmk compile` runs make with QMK_BIN="qmk", so this has to be found as `qmk` on
# PATH (build_wsl.sh links it into a temporary directory); everything goes to TEX_REAL_QMK unchanged.
# usage: TEX_BUILDDATE=2026-11-04-12:22:53 TEX_REAL_QMK=/root/qmkenv/bin/qmk PATH=<dir with qmk -> this>:$PATH ...
set -u
"$TEX_REAL_QMK" "$@"
rc=$?
if [ "$rc" -eq 0 ] && [ "${1:-}" = generate-version-h ] && [ -n "${TEX_BUILDDATE:-}" ]; then
    out=""
    prev=""
    for a in "$@"; do
        [ "$prev" = "-o" ] && out="$a"
        prev="$a"
    done
    [ -n "$out" ] || { echo "qmk_fixed_date.sh: no -o file" >&2; exit 1; }
    sed -i "s|^#define QMK_BUILDDATE .*|#define QMK_BUILDDATE \"$TEX_BUILDDATE\"|" "$out"
    grep -q "QMK_BUILDDATE \"$TEX_BUILDDATE\"" "$out" || { echo "qmk_fixed_date.sh: date not set" >&2; exit 1; }
fi
exit $rc
