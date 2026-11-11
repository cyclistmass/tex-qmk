// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "nvic.h"

#define HT32F52352_MCUCONF

// No crystal: stock runs the PLL from the 8 MHz HSI (GCFGR PLLSRC = HSI,
// PLLCFGR FBDIV 6, FUN_34ec). board.c adds the stock HSI auto-trim.
#define HT32_CKCU_SW CKCU_GCCR_SW_PLL
#define HT32_PLL_USE_HSE FALSE
#define HT32_PLL_FBDIV 6 // 8 MHz -> 48 MHz
#define HT32_PLL_OTDIV 0
#define HT32_AHB_PRESCALER 1
#define HT32_USART_PRESCALER 1
#define HT32_USB_PRESCALER 1
#define HT32_ST_USE_HCLK TRUE

#define HT32_USB_USE_USB0 TRUE
#define HT32_USB_USB0_IRQ_PRIORITY 5

// BFTM0 times wait_us() (config.h WAIT_US_TIMER); SysTick stays the system tick.
#define HT32_GPT_USE_BFTM0 TRUE

// USART0 (B0 TX, B1 RX) to the BLE module, 500 kbaud from the 48 MHz CK_USART.
#define HT32_SERIAL_USE_USART0 TRUE
#define HT32_USART0_IRQ_PRIORITY 6
