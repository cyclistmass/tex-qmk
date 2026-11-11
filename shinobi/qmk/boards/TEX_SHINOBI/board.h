// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "tex_hw.h"

#define BOARD_NAME "TEX Shinobi"

// TEX names an LQFP-64 "HT50F52352" (read as HT32F52352), and stock's stack at
// 0x20003FE0 (16 KB SRAM) agrees. Still read the chip ID over SWD before flashing.
#define HT32F52352

// App region after the stock IAP. Sized for the 64 KB HT32F52342 until the
// part is confirmed.
#define FLASH_SIZE (0x10000 - 0x3200)

#if !defined(_FROM_ASM_)
#    ifdef __cplusplus
extern "C" {
#    endif
void boardInit(void);
#    ifdef __cplusplus
}
#    endif
#endif /* _FROM_ASM_ */
