// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// Same as keyboards/annepro2: the HT32 SysTick port runs a periodic tick.
#define CH_CFG_ST_FREQUENCY 1000
#define CH_CFG_ST_TIMEDELTA 0
#define CH_CFG_TIME_QUANTUM 20
// Ticks are milliseconds: skip the 64-bit conversion (tools/patch_qmk_tree.sh).
#define TEX_TIME_MS_IDENTITY

#include_next <chconf.h>

// QMK's common chconf.h defines these hooks empty, so replace them here.
// Kick the watchdog from the 1 kHz tick like stock does from its main loop, in
// case the IAP left it running; a kernel halt (panic) goes back to the IAP so
// the updater can still reach the keyboard.
#include "tex_hw.h"
#undef CH_CFG_SYSTEM_TICK_HOOK
#define CH_CFG_SYSTEM_TICK_HOOK()     { TEX_WDT_RELOAD(); }
#undef CH_CFG_SYSTEM_HALT_HOOK
#define CH_CFG_SYSTEM_HALT_HOOK(reason)     {                                           (void)(reason);                         TEX_ENTER_IAP();                    }
