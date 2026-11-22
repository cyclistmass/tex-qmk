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

# ChibiOS converts ticks to milliseconds through a 64-bit product (time_conv_t), which links
# libgcc's 64-bit division (__udivmoddi4, ~400 B) into timer_read32() and the USB idle timers.
# At the Shinobi's 1 kHz tick the conversion is the identity, so let a keyboard opt out of it by
# defining TEX_TIME_MS_IDENTITY in its chconf.h. Builds that don't define it are unchanged.
t="$1/lib/chibios/os/rt/include/chtime.h"
if ! grep -q 'TEX_TIME_MS_IDENTITY' "$t"; then
    perl -0pi -e 's/(#define TIME_I2MS\(interval\).*?\(time_conv_t\)CH_CFG_ST_FREQUENCY\)\n)/#if defined(TEX_TIME_MS_IDENTITY) && CH_CFG_ST_FREQUENCY == 1000\n#define TIME_I2MS(interval) ((time_msecs_t)(interval))\n#else\n$1#endif\n/s; s/(static inline time_msecs_t chTimeI2MS\(sysinterval_t interval\) \{\n)/$1#if defined(TEX_TIME_MS_IDENTITY) && CH_CFG_ST_FREQUENCY == 1000\n  return (time_msecs_t)interval;\n#endif\n/' "$t"
fi
[ "$(grep -c 'TEX_TIME_MS_IDENTITY' "$t")" = 2 ] || { echo "TIME_I2MS patch did not apply to $t" >&2; exit 1; }

# Every USB IN endpoint keeps its last report for GET_REPORT and idle repeats in a usb_fs_report_t with a 64-byte
# buffer, all copied from flash at boot. Let a keyboard size that buffer (TEX_USB_REPORT_DATA_SIZE, the largest
# report it sends) and keep no report for raw HID (TEX_RAW_NO_REPORT_STORAGE): usb_driver.c and
# usb_report_handling.c already handle an endpoint whose report_storage is NULL. Builds that define neither are
# unchanged.
r="$1/tmk_core/protocol/chibios/usb_report_handling.h"
if ! grep -q 'TEX_USB_REPORT_DATA_SIZE' "$r"; then
    perl -0pi -e 's/(typedef struct \{\n    time_msecs_t idle_rate;\n    systime_t    last_report;\n    uint8_t      data\[)64(\];)/#ifndef TEX_USB_REPORT_DATA_SIZE\n#    define TEX_USB_REPORT_DATA_SIZE 64\n#endif\n\n$1TEX_USB_REPORT_DATA_SIZE$2/' "$r"
fi
[ "$(grep -c 'TEX_USB_REPORT_DATA_SIZE' "$r")" = 3 ] || { echo "report buffer patch did not apply to $r" >&2; exit 1; }
e="$1/tmk_core/protocol/chibios/usb_endpoints.c"
if ! grep -q 'TEX_RAW_NO_REPORT_STORAGE' "$e"; then
    perl -0pi -e 's/(#if defined\(RAW_ENABLE\)\n)(.*?)(\n#endif)/my ($a,$b,$c)=($1,$2,$3); (my $n=$b) =~ s{QMK_USB_REPORT_STORAGE_DEFAULT\(RAW_EPSIZE\)}{NULL}g; "$a#    if defined(TEX_RAW_NO_REPORT_STORAGE)\n$n\n#    else\n$b\n#    endif$c"/se' "$e"
fi
grep -q 'TEX_RAW_NO_REPORT_STORAGE' "$e" || { echo "raw report storage patch did not apply to $e" >&2; exit 1; }
