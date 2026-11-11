// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// Plain macros, so chconf.h can use them before any HAL header is included.
// chconf.h and board.h are also read by assembly files; only C sees stdint.h.
#if !defined(_FROM_ASM_)
#    include <stdint.h>
#endif

// Stock IAP hand-off (FUN_6528): magic word at the top of SRAM, then reset.
// FAF5 keeps the IAP running (USB 04D9:1407, updater command 11 00); FAF0
// runs the app (11 01). The linker script keeps RAM below this word.
#define IAP_MAGIC_ADDR 0x20003FFCU
#define IAP_MAGIC_VALUE 0x55AAFAF5U
#define IAP_MAGIC_RUN_APP 0x55AAFAF0U

// Watchdog reload: stock writes this key to WDT CR on every main-loop pass
// (0x958c, 0x95da) and in its sleep loop (0x7734), and never writes the WDT
// protection key, so the IAP or the reset default may leave the watchdog
// running. Reloading a stopped watchdog does nothing.
#define TEX_WDT_RELOAD() (*(volatile uint32_t *)0x40068000U = 0x5FA00001U)

// Back to the stock IAP from anywhere, even before the C runtime is set up:
// the magic word, then a system reset through AIRCR as stock does. USB is left
// alone; the reset drops it and the IAP enumerates as 04D9:1407.
#define TEX_ENTER_IAP()                                          \
    do {                                                         \
        *(volatile uint32_t *)IAP_MAGIC_ADDR = IAP_MAGIC_VALUE;  \
        __asm volatile("dsb" ::: "memory");                      \
        *(volatile uint32_t *)0xE000ED0CU = 0x05FA0004U;         \
        __asm volatile("dsb" ::: "memory");                      \
        for (;;) {                                               \
        }                                                        \
    } while (0)
