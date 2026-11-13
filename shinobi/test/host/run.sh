#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Host tests of the firmware's input logic (see host_tests.c). Needs python3 and a native C compiler ($CC, else
# gcc). Runs in a second or two. Prints PASS or FAIL lines and one TIMING line; exits non-zero on a failure.
# usage: run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
start=$(date +%s)
work="$(mktemp -d)"
result=fail
trap 'echo "TIMING label=host_tests start=$start end=$(date +%s) seconds=$(( $(date +%s) - start )) result=$result"; rm -rf "$work"' EXIT
python3 -I "$here/extract.py" "$here/../../qmk" "$work/extracted.c"
"${CC:-gcc}" -std=gnu11 -O1 -Wall -Werror -Wno-unused-variable -Wno-unused-function -I"$work" -o "$work/host_tests" "$here/host_tests.c"
"$work/host_tests"
result=ok
