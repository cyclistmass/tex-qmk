// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// TrackPoint: stock reads DATA on B4 (SPI0 slave input) and drives it through
// open-drain B5, which the schematic joins to TP_DATA via R2. The bit-banged driver
// uses one pin, so B5 (keyboard.json) does both and B4 stays a high-impedance
// input. The stick runs in stream mode (ps2_vendor.c says why).
// Both axes came out reversed (Mauro, 2026-11-03): the stick reads as turned 180 degrees.
#define PS2_MOUSE_ROTATE 180

// The six DIP switches: matrix column 14 (C13), rows 0-5 (stock FUN_4c74, FUN_8598).
#define PROFILE_SWITCH_COL 14

// Stock vendor interface (report descriptor at 0x9B94): usage page 0xFF00,
// usage 1, 64-byte reports, no report IDs. The stock updater opens the keyboard
// by exactly that, so QMK's raw HID takes its shape. RAW_EPSIZE is a plain
// #define in QMK; tools/patch_qmk_tree.sh makes it overridable.
#define RAW_USAGE_PAGE 0xFF00
#define RAW_USAGE_ID 0x01
#define RAW_EPSIZE 64

// wait_us() needs a hardware timer here: the M0+ has no cycle counter, so QMK's
// fallback sleeps whole 1 ms system ticks, and the PS/2 driver's 1 us polling
// steps turned its 10 ms timeouts into 10-20 s stalls of the main loop.
#define WAIT_US_TIMER GPTD_BFTM0

// Middle button + stick scrolls one notch per this many stick counts. QMK's
// default of 2 scrolled far too fast (Mauro, 2026-11-03). The counts already
// grow with Fn+1..9 (0.8x-2x); the divisor shrinks with the level too, so
// Fn+1 scrolls slowest and Fn+9 fastest.
#ifndef __ASSEMBLER__
extern unsigned char tp_level;
extern unsigned char tex_dip;
#endif
// DIP switch 5 reverses vertical scrolling (stock FUN_5cc8): a negative divisor flips the notches and keeps
// ps2_mouse.c's remainder arithmetic exact.
#ifndef TEX_NO_DIP5
#    define PS2_MOUSE_SCROLL_DIVISOR_V (tex_dip & (1 << 4) ? tp_level - 14 : 14 - tp_level)
#else
#    define PS2_MOUSE_SCROLL_DIVISOR_V (14 - tp_level)
#endif
#define PS2_MOUSE_SCROLL_DIVISOR_H (14 - tp_level)

// This port's version, typed by Fn+B with the keymap and build date.
#define TEX_FW_VERSION "1.1"
