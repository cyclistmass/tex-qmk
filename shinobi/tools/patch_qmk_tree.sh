#!/bin/bash
# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
# Make QMK's raw HID report size overridable: it is a plain "#define RAW_EPSIZE 32"
# in tmk_core/protocol/usb_descriptor.h. The TEX updater needs 64-byte reports,
# which the keyboard's config.h sets once this guard is in place. Idempotent.
#
# usage: patch_qmk_tree.sh /path/to/qmk_firmware
set -euo pipefail
f="$1/tmk_core/protocol/usb_descriptor.h"
if ! grep -q '^#ifndef RAW_EPSIZE' "$f"; then
    sed -i 's/^#define RAW_EPSIZE 32$/#ifndef RAW_EPSIZE\n#    define RAW_EPSIZE 32\n#endif/' "$f"
fi
grep -q '^#ifndef RAW_EPSIZE' "$f" || { echo "RAW_EPSIZE define not found in $f" >&2; exit 1; }

# ChibiOS-Contrib puts RSTCU at 0x40088000, but its registers start at offset 0x100
# (HT32F52342/52352 UM v1.60, table 19): usb_lld_stop()'s RSTCU->AHBPRSTR = USBRST
# wrote 0x20 into CKCU GCCR, clearing HSIEN while the PLL runs from HSI.
h="$1/lib/chibios-contrib/os/common/ext/CMSIS/HT32/HT32F523xx/ht32f523x2.h"
sed -i 's/^#define RSTCU_BASE              ((uint32_t)0x40088000)$/#define RSTCU_BASE              ((uint32_t)0x40088100)/' "$h"
grep -q '^#define RSTCU_BASE              ((uint32_t)0x40088100)$' "$h" || { echo "RSTCU_BASE define not found in $h" >&2; exit 1; }
