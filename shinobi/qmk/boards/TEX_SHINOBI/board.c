// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#include "hal.h"

// Pins as the stock firmware configures them. Every pin used here is switched
// to AFIO_GPIO (stock FUN_78c8 does the same; on B10-B14 the reset function is
// not GPIO). A12/A13 keep their reset function, SWD. The BLE board on J3 (B0/B1
// USART0, B10 TO_MCU, D1 FROM_MCU, C1 RESET_N, C4/C5 LEDs), the A0 battery
// divider, the B12 wake line and SPI memory (C2/C3/B6, CS B7) are left at reset.

// Matrix: rows A1-A8, columns D2 B8 B11 D0 B13 B14 A15 A14 A10 C14 C15 B15 C0
// A11 C13. Inputs with pull-ups until QMK's matrix code takes over.
#define A_MATRIX 0xCDFEU // A1-A8, A10, A11, A14, A15
#define B_MATRIX 0xE900U // B8, B11, B13, B14, B15
#define C_MATRIX 0xE001U // C0, C13, C14, C15
#define D_MATRIX 0x0005U // D0, D2

// TrackPoint CLK B3, DATA in B4, DATA out B5: inputs, no internal pull
// (stock enables none, so the pull-ups are external [I]).
#define B_PS2 0x0038U

// C8 TrackPoint power (active low, on at reset) and C10 Caps Lock LED (active
// low, off at reset): push-pull outputs.
#define C_OUT 0x0500U
#define C_OUT_HIGH 0x0400U

// AFIO config register N covers pads 8N..8N+7, one nibble each.
#define AF_NIBBLE(BITS, N, P) ((((BITS) >> (8 * (N) + (P))) & 1U) * ((uint32_t)AFIO_GPIO << (4 * (P))))
#define AF_GPIO(BITS, N) \
    (AF_NIBBLE(BITS, N, 0) | AF_NIBBLE(BITS, N, 1) | AF_NIBBLE(BITS, N, 2) | AF_NIBBLE(BITS, N, 3) | \
     AF_NIBBLE(BITS, N, 4) | AF_NIBBLE(BITS, N, 5) | AF_NIBBLE(BITS, N, 6) | AF_NIBBLE(BITS, N, 7))

#define PORT_SETUP(PULLUP, INPUT, OUTPUT, HIGH)          \
    {                                                    \
        .DIR    = (OUTPUT),                              \
        .INE    = (PULLUP) | (INPUT),                    \
        .PU     = (PULLUP),                              \
        .PD     = 0x0000,                                \
        .OD     = 0x0000,                                \
        .DRV    = 0x0000,                                \
        .LOCK   = 0x0000,                                \
        .OUT    = (HIGH),                                \
        .CFG[0] = AF_GPIO((PULLUP) | (INPUT) | (OUTPUT), 0), \
        .CFG[1] = AF_GPIO((PULLUP) | (INPUT) | (OUTPUT), 1), \
    }

const PALConfig pal_default_config = {
    .setup[0] = PORT_SETUP(A_MATRIX, 0, 0, 0),
    .setup[1] = PORT_SETUP(B_MATRIX, B_PS2, 0, 0),
    .setup[2] = PORT_SETUP(C_MATRIX, 0, C_OUT, C_OUT_HIGH),
    .setup[3] = PORT_SETUP(D_MATRIX, 0, 0, 0),
    .ESSR[0]  = 0x00000000,
    .ESSR[1]  = 0x00000000,
};

// Any fault goes back to the stock IAP instead of ChibiOS's endless loop, so a
// crash can't take the updater path away. Runs from the app's vector table:
// crt0 points VTOR at 0x3200 before __early_init.
void HardFault_Handler(void);
void HardFault_Handler(void) {
    TEX_ENTER_IAP();
}

void __early_init(void) {
    TEX_WDT_RELOAD();
#ifdef TEX_CANARY
    // Test build (keymap "canary"): prove the IAP starts this image at 0x3200
    // and takes the hand-off, before anything that could hang. Lands in 1407.
#    ifdef TEX_CANARY_SPIN
    // Keymap "canary_slow": stay off USB for a few seconds first. An IAP with
    // no app to start re-enumerates within ~1 s, so a longer gap after `11 01`
    // can only come from this code.
    for (volatile uint32_t i = 0; i < TEX_CANARY_SPIN; i++) {
        TEX_WDT_RELOAD();
    }
#    endif
    TEX_ENTER_IAP();
#endif
    ht32_clock_init();
}

void boardInit(void) {
    // No crystal. Stock enables the HSI auto-trim this way when it starts USB
    // (FUN_9358 -> FUN_3938(0x20)): clear bits 4-5, set 0x20 | 0x03. Field
    // meanings (reference select, TRIMEN, ATCEN) are inferred.
    CKCU->HSICR = (CKCU->HSICR & ~0x30U) | 0x23U;
}
