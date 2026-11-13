// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#include <string.h>
#include "shinobi.h"
#include "ps2.h"
#include "ps2_mouse.h"
#include "raw_hid.h"

// Stock sensitivity levels for Fn+1..9 (table 0x9730); stock starts at level 3.
static const uint8_t tp_sensitivity[] = {0x66, 0x73, 0x80, 0x8F, 0xA0, 0xB3, 0xC9, 0xE1, 0xFC};
uint8_t              tp_level         = 2; // index into tp_sensitivity; config.h scales scrolling by it

static void tp_send_sensitivity(void) {
    // TrackPoint RAM write E2 81 <addr> <value>; 0x4A is sensitivity, as stock sends it.
    ps2_host_send(0xE2);
    ps2_host_send(0x81);
    ps2_host_send(0x4A);
    ps2_host_send(tp_sensitivity[tp_level]);
}

// QMK has no _kb hook here; ps2_mouse_init() calls this after reset and BAT.
void ps2_mouse_init_user(void) {
    tp_send_sensitivity();
}

// TrackPoint power, C8 active low (Q2 switches TPM_PWR). Off while the board
// sleeps. Power-on reset takes 600 ms +-20 % (TrackPoint spec v4.0); until
// then the lines stay inhibited, so the stick holds its BAT bytes.
#define TP_POR_MS 1000
#define TP_SETUP_RETRY_MS 200
static uint16_t tp_setup_at;
static uint8_t  tp_setup_tries; // nonzero while a setup after power-on is due

void tp_power_off(void) {
    ps2_stream_paused = true;
    // Released, not inhibited: a clock held low would feed the external
    // pull-up's current into the unpowered stick.
    palSetLineMode(PS2_CLOCK_PIN, PAL_MODE_INPUT);
    palSetLineMode(PS2_DATA_PIN, PAL_MODE_INPUT);
    palSetLine(C8);
}

void tp_power_on(void) {
    palClearLine(C8);
    ps2_host_resume();
    tp_setup_at    = timer_read() + TP_POR_MS;
    tp_setup_tries = 5;
}

// What ps2_mouse_init() sends after its reset, without the reset and its
// blocking wait: power-on left the stick in the reset state. F5 makes it drop
// the BAT bytes it holds.
static void tp_setup_task(void) {
    if (!tp_setup_tries || (int16_t)(timer_read() - tp_setup_at) < 0) return;
    if (ps2_host_send(0xF5) == PS2_ACK && ps2_host_send(0xEA) == PS2_ACK && ps2_host_send(0xF4) == PS2_ACK) {
        tp_send_sensitivity();
        tp_setup_tries = 0;
    } else {
        tp_setup_tries--;
        tp_setup_at = timer_read() + TP_SETUP_RETRY_MS;
    }
    ps2_stream_paused = tp_setup_tries != 0;
    ps2_last_packet   = timer_read32(); // the watch counts from setup, not from boot
}

// The stick stopped reporting once while awake, on USB, and came back only
// with a power cycle (Mauro, 2026-11-03). After TP_PROBE_MS without a packet,
// F4 (enable reporting) checks that it still answers: a stick that reset
// itself acks, reports again and gets its sensitivity back; one that doesn't
// ack twice running is switched off and on, and tp_setup_task() sets it up
// again. One miss is retried: every boot counted a power cycle, though the
// stick worked (Mauro, 2026-11-04).
#define TP_PROBE_MS 3000
#define TP_CYCLE_OFF_MS 100
static uint8_t tp_misses;

static void tp_watch_task(void) {
    if (tp_setup_tries || ps2_stream_paused || timer_elapsed32(ps2_last_packet) < TP_PROBE_MS) return;
    if (ps2_host_send(0xF4) == PS2_ACK) {
        tp_misses = 0;
        tp_send_sensitivity();
    } else if (++tp_misses >= 2) {
        tp_misses = 0;
        tp_power_off();
        wait_ms(TP_CYCLE_OFF_MS);
        tp_power_on();
    }
    ps2_last_packet = timer_read32();
}

// Every USB plug and unplug cuts the board's power (Mauro, 2026-11-04), so the
// TrackPoint level and sleep time live in flash page 254; page 255 holds the
// option bytes (UM v1.60 table 4). Stock never uses the flash controller.
// Erased flash reads all ones and fails the key: defaults.
#define SETTINGS_ADDR 0x1FC00U
#define SETTINGS_KEY 0x5E770000U
static uint8_t  sleep_choice = 0xFF; // index into power.c's sleep_minutes; 0xFF = the build's default
static uint32_t settings_word;       // what the page holds; reading it back could hit the flash prefetch buffer

static void fmc_run(uint32_t command) {
    FMC->TADR = SETTINGS_ADDR;
    FMC->OCMR = command;
    FMC->OPCR = FMC_OPCR_OPM_COMMIT;
    // OPM reads 0xE or 0xF once the operation is over (UM v1.60 ch. 4, OPCR).
    while ((FMC->OPCR & FMC_OPCR_OPM_FINISHED) != FMC_OPCR_OPM_FINISHED) {
    }
}

// In the 56 bytes after the keymaps (ld .tex_text0b): code beyond flash2's room.
__attribute__((section(".tex_text0b"), noinline)) static void settings_put(uint32_t word) {
    fmc_run(FMC_OCMR_CMD_PAGE_ERASE);
    FMC->WRDR = word;
    fmc_run(FMC_OCMR_CMD_WORD_PROGRAM);
}

static void settings_save(void) {
    uint32_t word = SETTINGS_KEY | sleep_choice << 8 | tp_level;
    if (word == settings_word) return;
    settings_put(word);
    settings_word = word;
}

#ifdef TEX_SELFTEST
// Stock's factory flash test (FUN_4810), run over USB by tools/tex_selftest.py (raw HID command 14 00): write a
// test value where the settings live, read it back, put the settings back. The low byte 0xA5 is no TrackPoint
// level, so if power drops mid-test the next boot takes the defaults. Stock starts it by holding Up+LAlt+Fn for 6 s
// and shows the result on Caps Lock (312 bytes here); this version is the read-back alone, 88 bytes. Off by default,
// as in the v1.1 release.
#    define SETTINGS_TEST (SETTINGS_KEY | 0xA5A5U)
static bool settings_selftest(void) {
    settings_put(SETTINGS_TEST);
    // Branch cache and pre-fetch buffer off, so the read comes from the flash array (UM v1.60, CFCR bits 12 and 4).
    uint32_t cfcr = FMC->CFCR;
    FMC->CFCR     = cfcr & ~(FMC_CFCR_CE | 1U << 4);
    bool ok       = *(volatile uint32_t *)SETTINGS_ADDR == SETTINGS_TEST;
    FMC->CFCR     = cfcr;
    settings_put(settings_word);
    return ok;
}
#endif

// Before ps2_mouse_init() sends the sensitivity.
void keyboard_pre_init_kb(void) {
    uint32_t word = settings_word = *(volatile uint32_t *)SETTINGS_ADDR;
    if ((word & 0xFFFF0000U) == SETTINGS_KEY && (uint8_t)word < 9) {
        tp_level     = word;
        sleep_choice = word >> 8;
        if (sleep_choice < 9) power_set_sleep(sleep_choice, false);
    }
    keyboard_pre_init_user();
}

void keyboard_post_init_kb(void) {
    power_init();
    keyboard_post_init_user();
}

extern int tp_buttons; // action.c: the matrix mouse buttons, merged into the PS/2 report

#ifndef TEX_NO_DIP4
// DIP switch 4 (stock FUN_5614): Fn holds the middle button, so Fn + stick scrolls and a quick Fn tap clicks
// (ps2_mouse.c's scroll button). Any key pressed while Fn is down cancels the click: the button is then held on
// past PS2_MOUSE_SCROLL_BTN_SEND, so Fn+F1 doesn't click.
// The middle button has two owners, its own key and Fn (while fn_scroll isn't 0); it is down while either holds
// it. Housekeeping calls this with KC_NO, which only runs out the wait after a release.
static uint8_t  fn_scroll; // 0 off, 1 Fn down, 2 Fn down and another key pressed, 3 released, waiting
static uint16_t fn_scroll_time;
static bool     mid_key;

static void fn_scroll_record(uint16_t keycode, bool pressed) {
    if (fn_scroll == 3 && timer_elapsed(fn_scroll_time) > PS2_MOUSE_SCROLL_BTN_SEND) fn_scroll = 0;
    if (keycode == MS_BTN3) {
        mid_key = pressed;
    } else if (IS_QK_MOMENTARY(keycode)) {
        if (pressed && (tex_dip & TEX_DIP4_FN_SCROLL)) {
            fn_scroll = 1;
        } else if (!pressed && fn_scroll == 1) {
            fn_scroll = 0; // a tap clicks, a hold that scrolled doesn't
        } else if (!pressed && fn_scroll == 2) {
            fn_scroll      = 3; // held on until the click window has passed since this release
            fn_scroll_time = timer_read();
        }
    } else if (pressed && fn_scroll == 1) {
        fn_scroll = 2;
    }
    if (mid_key || fn_scroll) {
        tp_buttons |= 1 << PS2_MOUSE_BTN_MIDDLE;
    } else {
        tp_buttons &= ~(1 << PS2_MOUSE_BTN_MIDDLE);
    }
}
#endif

#ifndef TEX_NO_MOUSEKEYS
// Mouse movement keys: mk_held has a bit per key held, up, down, left, right as bits 0-3 and up-left, up-right,
// down-left, down-right as 4-7. A direction moves while any of its three keys is held, so letting go of one key
// never cancels another. Movement goes out with the matrix mouse buttons every 16 ms and speeds up from 1 to 11
// counts while held.
#define MK_UP    (1 << 0 | 1 << 4 | 1 << 5)
#define MK_DOWN  (1 << 1 | 1 << 6 | 1 << 7)
#define MK_LEFT  (1 << 2 | 1 << 4 | 1 << 6)
#define MK_RIGHT (1 << 3 | 1 << 5 | 1 << 7)
static uint8_t  mk_held, mk_ticks;
static uint16_t mk_time;

static void mousekey_record(uint16_t keycode, bool pressed) {
    uint8_t bit = 1 << (keycode <= MS_RGHT ? keycode - MS_UP : keycode - MS_UPLEFT + 4);
    if (pressed) {
        mk_held |= bit;
    } else {
        mk_held &= ~bit;
    }
}

static void mousekey_task(void) {
    if (!mk_held) {
        mk_ticks = 0;
        return;
    }
    if (timer_elapsed(mk_time) < 16) return;
    mk_time = timer_read();
    if (mk_ticks < 40) mk_ticks++;
    int8_t         step = 1 + mk_ticks / 4;
    report_mouse_t r    = {.buttons = tp_buttons};
    if (mk_held & MK_UP) r.y -= step;
    if (mk_held & MK_DOWN) r.y += step;
    if (mk_held & MK_LEFT) r.x -= step;
    if (mk_held & MK_RIGHT) r.x += step;
    host_mouse_send(&r);
}
#endif

bool process_record_kb(uint16_t keycode, keyrecord_t *record) {
    power_input();
#ifndef TEX_NO_DIP4
    // First, so a key another handler takes (Fn+Esc, Fn+slot) still cancels Fn's click. The middle button's key
    // is handled here, not by action.c, which would let go of the button while Fn still holds it.
    fn_scroll_record(keycode, record->event.pressed);
    if (keycode == MS_BTN3) return false;
#endif
    if (!process_record_user(keycode, record)) {
        return false;
    }
    if (!ble_process_record(keycode, record)) {
        return false;
    }
#ifndef TEX_NO_MACROS
    if (keycode >= QK_MACRO_0 && keycode <= QK_MACRO_31) {
        if (record->event.pressed) macro_play(keycode - QK_MACRO_0);
        return false;
    }
#endif
#ifndef TEX_NO_MOUSEKEYS
    if ((keycode >= MS_UP && keycode <= MS_RGHT) || (keycode >= MS_UPLEFT && keycode <= MS_DOWNRIGHT)) {
        mousekey_record(keycode, record->event.pressed);
        return false;
    }
#endif
    if (keycode == BAT_REPORT) {
        if (record->event.pressed) battery_report();
        return false;
    }
    if (keycode >= TP_SEN1 && keycode <= TP_SEN9) {
        if (record->event.pressed) {
            tp_level = keycode - TP_SEN1;
            tp_send_sensitivity();
            settings_save();
            type_text("tp");
            type_number(tp_level + 1, "");
        }
        return false;
    }
    if (keycode >= SLEEP1 && keycode <= SLEEP9) {
        if (record->event.pressed) {
            sleep_choice = keycode - SLEEP1;
            settings_save();
            power_set_sleep(sleep_choice, true);
        }
        return false;
    }
    return true;
}

#ifdef TEX_DIAG
static uint32_t diag_loops;

static const pin_t diag_rows[MATRIX_ROWS] = MATRIX_ROW_PINS;
static const pin_t diag_cols[MATRIX_COLS] = MATRIX_COL_PINS;

static void diag_set_all(const pin_t *pins, uint8_t n, iomode_t mode) {
    for (uint8_t i = 0; i < n; i++) {
        palSetLineMode(pins[i], mode);
    }
}

// Scan the matrix three ways, one row mask per row each: 0 = QMK COL2ROW (row
// driven low, columns pulled up), 1 = stock as decompiled (column driven high,
// rows pulled down), 2 = ROW2COL (column driven low, rows pulled up). Leaves
// the pins as QMK's COL2ROW scan expects them between scans.
static void diag_scan(matrix_row_t out[3][MATRIX_ROWS]) {
    memset(out, 0, 3 * MATRIX_ROWS * sizeof(matrix_row_t));
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_INPUT_PULLUP);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLUP);
        palSetLineMode(diag_rows[r], PAL_MODE_OUTPUT_PUSHPULL);
        palClearLine(diag_rows[r]);
        wait_us(30);
        for (uint8_t c = 0; c < MATRIX_COLS; c++) {
            if (!palReadLine(diag_cols[c])) out[0][r] |= (matrix_row_t)1 << c;
        }
    }
    for (uint8_t mode = 1; mode <= 2; mode++) {
        diag_set_all(diag_rows, MATRIX_ROWS, mode == 1 ? PAL_MODE_INPUT_PULLDOWN : PAL_MODE_INPUT_PULLUP);
        for (uint8_t c = 0; c < MATRIX_COLS; c++) {
            diag_set_all(diag_cols, MATRIX_COLS, mode == 1 ? PAL_MODE_INPUT_PULLDOWN : PAL_MODE_INPUT_PULLUP);
            palSetLineMode(diag_cols[c], PAL_MODE_OUTPUT_PUSHPULL);
            if (mode == 1) {
                palSetLine(diag_cols[c]);
            } else {
                palClearLine(diag_cols[c]);
            }
            wait_us(30);
            for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
                if (palReadLine(diag_rows[r]) == (mode == 1)) out[mode][r] |= (matrix_row_t)1 << c;
            }
        }
    }
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLUP);
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_INPUT_PULLUP);
}

// Stock's scan step for step (FUN_4ec0 with the run-time pin config at 0x9A60):
// rows are pulled-down inputs driven low between columns, columns are push-pull
// outputs held low; per column: rows to input, column high (SRR), read rows,
// column low (RR), rows back to driven low. A key reads as its row high.
static void diag_scan_stock(matrix_row_t out[MATRIX_ROWS]) {
    memset(out, 0, MATRIX_ROWS * sizeof(matrix_row_t));
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_OUTPUT_PUSHPULL);
    for (uint8_t c = 0; c < MATRIX_COLS; c++) palClearLine(diag_cols[c]);
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLDOWN);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) palClearLine(diag_rows[r]);
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        GPIOA->DIRCR &= ~0x1FEU;
        palSetLine(diag_cols[c]);
        uint32_t rows = ~(GPIOA->DINR & 0x1FFU) >> 1; // FUN_84cc
        palClearLine(diag_cols[c]);
        GPIOA->DIRCR |= 0x1FEU;
        for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
            if (!(rows >> r & 1)) out[r] |= (matrix_row_t)1 << c;
        }
    }
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLUP);
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_INPUT_PULLUP);
}

// Any key at all, two ways: every column high into pulled-down rows (bit 0), and
// every row low against pulled-up columns (bit 1).
static uint8_t diag_any_key(void) {
    uint8_t seen = 0;
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLDOWN);
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_OUTPUT_PUSHPULL);
    for (uint8_t c = 0; c < MATRIX_COLS; c++) palSetLine(diag_cols[c]);
    wait_us(30);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        if (palReadLine(diag_rows[r])) seen |= 1;
    }
    diag_set_all(diag_cols, MATRIX_COLS, PAL_MODE_INPUT_PULLUP);
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_OUTPUT_PUSHPULL);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) palClearLine(diag_rows[r]);
    wait_us(30);
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        if (!palReadLine(diag_cols[c])) seen |= 2;
    }
    diag_set_all(diag_rows, MATRIX_ROWS, PAL_MODE_INPUT_PULLUP);
    return seen;
}

static uint8_t diag_any_seen; // OR of diag_any_key() since the last 13 04

// TrackPoint motion as QMK sends it to the host: reports, sum of |x|, sum of |y| (13 0A).
static uint32_t diag_tp[3];

// Drive each matrix pin high then low as a push-pull output with its input
// buffer on, and record which ones read back what they drive: out[0] per port
// = followed high, out[1] = followed low.
static void diag_loopback(uint16_t out[2][4]) {
    memset(out, 0, 2 * 4 * sizeof(uint16_t));
    for (uint8_t i = 0; i < MATRIX_ROWS + MATRIX_COLS; i++) {
        pin_t        pin  = i < MATRIX_ROWS ? diag_rows[i] : diag_cols[i - MATRIX_ROWS];
        ioportid_t   port = PAL_PORT(pin);
        uint16_t     bit  = 1U << PAL_PAD(pin);
        uint8_t      idx  = HT32_PAL_IDX(port);
        palSetLineMode(pin, PAL_MODE_OUTPUT_PUSHPULL);
        port->INER |= bit;
        palSetLine(pin);
        wait_us(30);
        if (port->DINR & bit) out[0][idx] |= bit;
        palClearLine(pin);
        wait_us(30);
        if (!(port->DINR & bit)) out[1][idx] |= bit;
        palSetLineMode(pin, PAL_MODE_INPUT_PULLUP);
    }
}
// Every pin's input, watched for ms milliseconds with all input buffers on (pulls
// and outputs untouched): out[0] = first reading, out[1] = pins that changed,
// out[2] low half = B1 (USART0 RX from the BLE board) edges, capped at 0xFFFF.
static void diag_watch(uint16_t out[3][4], uint8_t ms) {
    GPIO_TypeDef *const ports[4] = {(GPIO_TypeDef *)GPIOA, (GPIO_TypeDef *)GPIOB, (GPIO_TypeDef *)GPIOC, (GPIO_TypeDef *)GPIOD};
    uint32_t            iner[4];
    memset(out, 0, 3 * 4 * sizeof(uint16_t));
    for (uint8_t p = 0; p < 4; p++) {
        iner[p] = ports[p]->INER;
        ports[p]->INER = 0xFFFF;
    }
    wait_us(20);
    for (uint8_t p = 0; p < 4; p++) out[0][p] = ports[p]->DINR;
    uint16_t       b1    = out[0][1] & 2;
    uint32_t       edges = 0;
    const uint32_t start = timer_read32();
    while (timer_elapsed32(start) < ms) {
        for (uint8_t p = 0; p < 4; p++) {
            uint16_t now = ports[p]->DINR;
            out[1][p] |= now ^ out[0][p];
            if (p == 1 && (now & 2) != b1) {
                b1 = now & 2;
                edges++;
            }
        }
    }
    out[2][0] = edges > 0xFFFF ? 0xFFFF : edges;
    for (uint8_t p = 0; p < 4; p++) ports[p]->INER = iner[p];
}

// Which pins a held key joins, without assuming the matrix pins: every pin in
// diag_allow becomes a GPIO input pulled down (high = true) or up, then each in
// turn is driven to the opposite level and every pin that moves from its idle
// reading is recorded as a (driven, moved) pair, port << 4 | pad. Pins left out
// belong to the BLE board link, the TrackPoint, the SPI memory, the battery
// divider, BOOT and SWD. Returns the number of pairs; stores up to max, and the
// idle readings of the allowed pins in idle_out.
static const uint16_t diag_allow[4] = {0xCDFE, 0xEB04, 0xFEC1, 0x000D};

static uint8_t diag_pairs(bool high, uint8_t *out, uint8_t max, uint16_t idle_out[4]) {
    GPIO_TypeDef *const ports[4] = {(GPIO_TypeDef *)GPIOA, (GPIO_TypeDef *)GPIOB, (GPIO_TypeDef *)GPIOC, (GPIO_TypeDef *)GPIOD};
    uint32_t            saved[4][8];
    uint16_t            idle[4];
    uint8_t             n = 0;
    for (uint8_t p = 0; p < 4; p++) {
        GPIO_TypeDef *g = ports[p];
        uint32_t      m = diag_allow[p];
        saved[p][0] = g->DIRCR, saved[p][1] = g->INER, saved[p][2] = g->PUR, saved[p][3] = g->PDR;
        saved[p][4] = g->ODR, saved[p][5] = g->DOUTR;
        saved[p][6] = AFIO->GPxCFGR[p][0], saved[p][7] = AFIO->GPxCFGR[p][1];
        for (uint8_t b = 0; b < 16; b++) {
            if (m >> b & 1) {
                AFIO->GPxCFGR[p][b >> 3] = (AFIO->GPxCFGR[p][b >> 3] & ~(0xFU << (4 * (b & 7)))) | (AFIO_GPIO << (4 * (b & 7)));
            }
        }
        g->DIRCR &= ~m;
        g->ODR &= ~m;
        g->INER |= m;
        g->PUR = high ? g->PUR & ~m : g->PUR | m;
        g->PDR = high ? g->PDR | m : g->PDR & ~m;
    }
    wait_us(100);
    for (uint8_t p = 0; p < 4; p++) idle_out[p] = idle[p] = ports[p]->DINR & diag_allow[p];
    for (uint8_t p = 0; p < 4; p++) {
        for (uint8_t b = 0; b < 16; b++) {
            uint16_t bit = 1U << b;
            if (!(diag_allow[p] & bit)) continue;
            if (high) {
                ports[p]->SRR = bit;
            } else {
                ports[p]->RR = bit;
            }
            ports[p]->DIRCR |= bit;
            wait_us(30);
            for (uint8_t q = 0; q < 4; q++) {
                uint16_t moved = (ports[q]->DINR & diag_allow[q]) ^ idle[q];
                if (q == p) moved &= ~bit;
                for (uint8_t c = 0; c < 16; c++) {
                    if (moved >> c & 1) {
                        if (n < max) {
                            out[2 * n]     = p << 4 | b;
                            out[2 * n + 1] = q << 4 | c;
                        }
                        if (n < UINT8_MAX) n++;
                    }
                }
            }
            ports[p]->DIRCR &= ~bit;
            wait_us(30);
        }
    }
    for (uint8_t p = 0; p < 4; p++) {
        GPIO_TypeDef *g = ports[p];
        uint32_t      m = diag_allow[p];
        g->DOUTR = (g->DOUTR & ~m) | (saved[p][5] & m);
        g->ODR   = (g->ODR & ~m) | (saved[p][4] & m);
        g->PUR   = (g->PUR & ~m) | (saved[p][2] & m);
        g->PDR   = (g->PDR & ~m) | (saved[p][3] & m);
        g->INER  = (g->INER & ~m) | (saved[p][1] & m);
        g->DIRCR = (g->DIRCR & ~m) | (saved[p][0] & m);
        AFIO->GPxCFGR[p][0] = saved[p][6];
        AFIO->GPxCFGR[p][1] = saved[p][7];
    }
    return n;
}
#endif

// QMK's idle time counts the matrix only; the stick counts too.
void ps2_mouse_moved_user(report_mouse_t *mouse_report) {
    power_pointer_activity();
#ifdef TEX_DIAG
    diag_tp[0]++;
    diag_tp[1] += mouse_report->x < 0 ? -mouse_report->x : mouse_report->x;
    diag_tp[2] += mouse_report->y < 0 ? -mouse_report->y : mouse_report->y;
#endif
}

uint8_t tex_dip;

// DIP switch n closes matrix column 14, row n-1 (stock FUN_4c74 keeps the same bits; FUN_8598 decodes 1-3,
// FUN_5614 tests 4, the scroll code FUN_5cc8 tests 5, FUN_541c tests 6 as bit 5). All eight rows are read so
// Fn+B can show them; nothing in stock reads rows 6 and 7, so switches 7 and 8 may not be wired there.
static uint8_t dip_read(void) {
    uint8_t dip = 0;
    for (uint8_t row = 0; row < MATRIX_ROWS; row++) {
        if (matrix_is_on(row, PROFILE_SWITCH_COL)) dip |= 1 << row;
    }
    return dip;
}

__attribute__((weak)) void profile_switch_user(uint8_t profile) {}

void housekeeping_task_kb(void) {
    static uint8_t profile = UINT8_MAX;
    tex_dip                = dip_read();
    // Exactly one of switches 1-3 on selects profile 1-3; none or several is 0 (stock FUN_8598).
    uint8_t three = tex_dip & 7;
    uint8_t now   = three & (three - 1) ? 0 : three == 4 ? 3 : three;
    if (now != profile) {
        profile = now;
        profile_switch_user(profile);
    }
#ifndef TEX_NO_DIP4
    fn_scroll_record(KC_NO, false);
#endif
#ifndef TEX_NO_MOUSEKEYS
    mousekey_task();
#endif
    ble_housekeeping();
    tp_setup_task();
    tp_watch_task();
    power_task();
#ifdef TEX_TEST_TIMEOUT_S
    // Test build (keymap "test90"): hand back to the IAP after a fixed uptime,
    // so a build that types wrong or can't be reached still returns to 1407.
    if (timer_read32() > TEX_TEST_TIMEOUT_S * 1000UL) {
        bootloader_jump();
    }
#endif
#ifdef TEX_DIAG
    diag_loops++;
    // Caps Lock LED (C10, active low) lights while any key closes, so a key
    // test needs no host-side timing.
    static uint32_t any_timer;
    if (timer_elapsed32(any_timer) >= 20) {
        any_timer    = timer_read32();
        uint8_t seen = diag_any_key();
        diag_any_seen |= seen;
        palWriteLine(C10, seen ? PAL_LOW : PAL_HIGH);
    }
#endif
    housekeeping_task_user();
}

// Stock 0x11 handler (FUN_6528): IAP magic at the top of SRAM, USB off, ~30 ms, reset.
static void iap_reset(uint32_t magic) {
    *(volatile uint32_t *)IAP_MAGIC_ADDR = magic;
    usbDisconnectBus(&USBD1);
    wait_ms(30);
    __disable_irq();
    NVIC_SystemReset();
}

void bootloader_jump(void) {
    iap_reset(IAP_MAGIC_VALUE);
}

// Flash is mapped at 0; keep GCC from treating low constant addresses as null-page reads.
static const uint8_t *flash_ptr(uint32_t addr) {
    volatile uint32_t a = addr;
    return (const uint8_t *)a;
}

// The stock updater's commands on the vendor interface, as stock answers them
// (FUN_7dd4 / FUN_893c): a reply echoes request bytes 0-3 and carries up to
// 60 payload bytes from +4. Anything else gets the stock NAK, FF AA 00 00 then
// the request's bytes 0-3. 11 never replies: stock resets at once. Stock's
// 0x40-0x7C config commands (keymap and macro storage) are not kept.
void raw_hid_receive(uint8_t *data, uint8_t length) {
    uint8_t        reply[RAW_EPSIZE] = {0};
    const uint8_t *src               = NULL;
    uint8_t        len               = 0;

    memcpy(reply, data, 4);
    switch (data[0]) {
        case 0x11: // 00: reboot into the IAP, 01: restart the app
            if (data[1] <= 1) {
                iap_reset(data[1] == 0 ? IAP_MAGIC_VALUE : IAP_MAGIC_RUN_APP);
            }
            break;
#ifdef TEX_SELFTEST
        case 0x14: // 00: the flash self-test above; reply byte 4 is 1 for a pass, 0 for a failure
            if (data[1] == 0x00) {
                reply[4] = settings_selftest();
                len      = 1;
            }
            break;
#endif
#ifdef TEX_DIAG
        case 0x13: // test build (keymap "diag"): main-loop passes, uptime, debounced matrix, raw port inputs
            if (data[1] == 0x00) {
                uint32_t now = timer_read32();
                memcpy(reply + 4, &diag_loops, 4);
                memcpy(reply + 8, &now, 4);
                for (uint8_t row = 0; row < MATRIX_ROWS; row++) {
                    matrix_row_t bits = matrix_get_row(row);
                    memcpy(reply + 12 + 2 * row, &bits, 2);
                }
                const uint16_t ports[] = {palReadPort(GPIOA), palReadPort(GPIOB), palReadPort(GPIOC), palReadPort(GPIOD)};
                memcpy(reply + 28, ports, sizeof(ports));
                len = 32;
            } else if (data[1] == 0x01) { // three raw scans, see diag_scan()
                matrix_row_t scans[3][MATRIX_ROWS];
                diag_scan(scans);
                memcpy(reply + 4, scans, sizeof(scans));
                len = sizeof(scans);
            } else if (data[1] == 0x02 && data[2] < 4) { // GPIO and AFIO registers of port data[2]
                ioportid_t     port   = HT32_PAL_ID(data[2]);
                const uint32_t regs[] = {port->DIRCR, port->INER, port->PUR, port->PDR, port->ODR, port->DRVR,
                                         port->LOCKR, port->DINR, port->DOUTR, AFIO->GPxCFGR[data[2]][0],
                                         AFIO->GPxCFGR[data[2]][1], CKCU->AHBCCR, CKCU->APBCCR0};
                memcpy(reply + 4, regs, sizeof(regs));
                len = sizeof(regs);
            } else if (data[1] == 0x04) { // stock's scan copied, and the any-key flags since the last 13 04
                matrix_row_t scan[MATRIX_ROWS];
                diag_scan_stock(scan);
                memcpy(reply + 4, scan, sizeof(scan));
                reply[4 + sizeof(scan)] = diag_any_seen;
                diag_any_seen           = 0;
                len                     = sizeof(scan) + 1;
            } else if (data[1] == 0x05) { // pins a held key joins, see diag_pairs(); data[2] 1 = drive high
                uint16_t idle[4];
                uint8_t  n = diag_pairs(data[2] != 0, reply + 6, (RAW_EPSIZE - 6) / 2, idle);
                reply[4]   = n;
                reply[5]   = n < (RAW_EPSIZE - 6) / 2 ? n : (RAW_EPSIZE - 6) / 2;
                len        = 2 + 2 * reply[5];
            } else if (data[1] == 0x07) { // the idle readings of a 13 05 sweep; data[2] 1 = pulled down
                uint16_t idle[4];
                diag_pairs(data[2] != 0, NULL, 0, idle);
                memcpy(reply + 4, idle, sizeof(idle));
                len = sizeof(idle);
            } else if (data[1] == 0x06) { // every pin watched for data[2] ms (max 50), see diag_watch()
                uint16_t w[3][4];
                diag_watch(w, data[2] > 50 ? 50 : data[2]);
                memcpy(reply + 4, w, sizeof(w));
                len = sizeof(w);
            } else if (data[1] == 0x08) { // raw TrackPoint transfer: data[2] bytes to send from data[4], then data[3] to receive
                // reply: per sent byte its response and ps2_error, then per received byte the byte and ps2_error
                uint8_t ns = data[2] > 8 ? 8 : data[2], nr = data[3] > 8 ? 8 : data[3], *r = reply + 4;
                for (uint8_t i = 0; i < ns; i++) {
                    *r++ = ps2_host_send(data[4 + i]);
                    *r++ = ps2_error;
                }
                for (uint8_t i = 0; i < nr; i++) {
                    *r++ = ps2_host_recv_response();
                    *r++ = ps2_error;
                }
                len = 2 * (ns + nr);
            } else if (data[1] == 0x09) { // ms taken by 10000 wait_us(1) calls, and by 1000 wait_us(10)
                uint32_t t0 = timer_read32();
                for (uint16_t i = 0; i < 10000; i++) wait_us(1);
                uint32_t t1 = timer_read32();
                for (uint16_t i = 0; i < 1000; i++) wait_us(10);
                uint32_t t2 = timer_read32(), d[2] = {t1 - t0, t2 - t1};
                memcpy(reply + 4, d, sizeof(d));
                len = sizeof(d);
            } else if (data[1] == 0x0A) { // TrackPoint motion counters (diag_tp), then main-loop passes
                memcpy(reply + 4, diag_tp, sizeof(diag_tp));
                memcpy(reply + 4 + sizeof(diag_tp), &diag_loops, 4);
                len = sizeof(diag_tp) + 4;
            } else if (data[1] == 0x03) { // output loopback, see diag_loopback()
                uint16_t loop[2][4];
                diag_loopback(loop);
                memcpy(reply + 4, loop, sizeof(loop));
                len = sizeof(loop);
            }
            break;
#endif
        case 0x12: // flash reads the updater makes around a flash
            if (data[1] == 0x00) { // FWInfo
                src = flash_ptr(0x400);
                len = 0x34;
            } else if (data[1] == 0x01) { // AP-info pointer
                src = flash_ptr(0x3C00);
                len = 4;
            } else if (data[1] == 0x02) { // stock answers a single 1
                reply[4] = 1;
                len      = 1;
            } else if (data[1] >= 0x20 && data[1] <= 0x27) { // version block, 60 bytes a chunk
                src = flash_ptr(0x3000 + (data[1] - 0x20) * 60);
                len = 60;
            }
            break;
    }
    if (len == 0) {
        memmove(reply + 4, reply, 4);
        reply[0] = 0xFF;
        reply[1] = 0xAA;
        reply[2] = 0;
        reply[3] = 0;
    } else if (src != NULL) {
        memcpy(reply + 4, src, len);
    }
    raw_hid_send(reply, sizeof(reply));
}

void mcu_reset(void) {
    __disable_irq();
    NVIC_SystemReset();
}
