// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

// GPT for wait_us() (config.h WAIT_US_TIMER).
#define HAL_USE_GPT TRUE

// USART0 to the BLE module (ble.c).
#define HAL_USE_SERIAL TRUE

#include_next <halconf.h>
