#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Checks divsi3.S as linked: in the firmware ELF, __aeabi_idiv is a Thumb function, every call to it lands on its
# first instruction, libgcc's own _divsi3.o is not linked, and the routine divides correctly when run
# (thumb_div.py); __aeabi_idivmod, which the firmware doesn't use today, is checked the same way in a small link
# with libgcc. Needs the ARM toolchain and python3. Takes a few seconds.
# usage: div_asm.sh <firmware .elf> [<its .map>]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
elf="$1"; map="${2:-${1%.elf}.map}"
start=$(date +%s)
work="$(mktemp -d)"
result=fail
trap 'echo "TIMING label=div_asm start=$start end=$(date +%s) seconds=$(( $(date +%s) - start )) result=$result"; rm -rf "$work"' EXIT
sym="$(arm-none-eabi-readelf -sW "$elf" | awk '$8 == "__aeabi_idiv" {print $2, $4}')"
read -r value type <<< "$sym"
[ "$type" = FUNC ] && (( 0x$value & 1 )) || { echo "FAIL __aeabi_idiv is '$sym', want a FUNC with an odd value"; exit 1; }
target=$(printf '%x' $(( 0x$value & ~1 )))
arm-none-eabi-objdump -d --no-show-raw-insn "$elf" > "$work/dis.txt"
calls=$(grep -cE "bl[[:space:]]+[0-9a-f]+ <__(aeabi_idiv|divsi3)>" "$work/dis.txt" || true)
wrong=$(grep -E "bl[[:space:]]+[0-9a-f]+ <__(aeabi_idiv|divsi3)>" "$work/dis.txt" | grep -vcE "bl[[:space:]]+$target " || true)
first=$(grep -A1 -E "^0*$target <" "$work/dis.txt" | tail -1)
[ "$wrong" = 0 ] && [[ "$first" == *"push"*"{r4, lr}"* ]] || { echo "FAIL calls: $calls, $wrong elsewhere; first instruction: $first"; exit 1; }
if grep -q "libgcc.a(_divsi3.o)" "$map"; then echo "FAIL libgcc's _divsi3.o is linked"; exit 1; fi
echo "PASS __aeabi_idiv: FUNC at 0x$value, $calls calls land on 0x$target ($first), libgcc's _divsi3.o not linked"
python3 -I "$here/thumb_div.py" "$elf" __aeabi_idiv
printf 'int caller_div(int a, int b) { return a / b; }\nint caller_mod(int a, int b) { return a %% b; }\n' > "$work/caller.c"
arm-none-eabi-gcc -mcpu=cortex-m0 -mthumb -Os -nostdlib -nostartfiles -Wl,-e,caller_div -Wl,-Ttext=0x1000 \
    "$work/caller.c" "$here/../../qmk/divsi3.S" -lgcc -o "$work/small.elf"
python3 -I "$here/thumb_div.py" "$work/small.elf" __aeabi_idiv __aeabi_idivmod
result=ok
