// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "quantum.h"

enum shinobi_keycodes {
    // TrackPoint sensitivity levels 1-9 (stock Fn+1..9).
    TP_SEN1 = QK_KB_0,
    TP_SEN2,
    TP_SEN3,
    TP_SEN4,
    TP_SEN5,
    TP_SEN6,
    TP_SEN7,
    TP_SEN8,
    TP_SEN9,
    // Bluetooth (ble.c): tap = host slot 1-3, hold 3 s = pair a new host there.
    BLE_SLOT1,
    BLE_SLOT2,
    BLE_SLOT3,
    BLE_PAIR, // the pair button: hold 3 s pairs slot 1
    BLE_USB,  // back to USB when it is plugged in (stock Fn+Esc)
    BAT_REPORT, // types the battery level (power.c)
    // Sleep time choices 1-9 (power.c), Fn+F1..F9.
    SLEEP1,
    SLEEP2,
    SLEEP3,
    SLEEP4,
    SLEEP5,
    SLEEP6,
    SLEEP7,
    SLEEP8,
    SLEEP9,
    // Mouse movement on the diagonals (shinobi.c); straight moves use QMK's MS_UP/MS_DOWN/MS_LEFT/MS_RGHT.
    MS_UPLEFT,
    MS_UPRIGHT,
    MS_DOWNLEFT,
    MS_DOWNRIGHT,
};

// ble.c
bool ble_process_record(uint16_t keycode, keyrecord_t *record);
void ble_housekeeping(void);
bool ble_pairing(void);
void ble_flush_keys(uint8_t settle_ms);
void ble_set_battery(uint8_t percent);
void ble_sleep(void);
void ble_wake(void);
// ms from the last wake (ble_wake) to the module's first status with the link connected; 0 before any sleep
extern uint16_t ble_wake_ms;

// power.c
void     power_init(void);
void     power_task(void);
void     power_pointer_activity(void);
void     power_input(void); // a key or a TrackPoint packet, for Fn+B's idle figure
void     power_set_sleep(uint8_t choice, bool announce);
uint16_t battery_raw(void);
uint8_t  battery_percent(void);
void     battery_report(void);
// power.c: types text and numbers through the active output, for readbacks
void     type_text(const char *s);
void     type_number(uint16_t n);
// power.c: plays sequence macro n (MC_n) from the editor's table
void     macro_play(uint8_t n);

// shinobi.c: TrackPoint power
void tp_power_off(void);
void tp_power_on(void);
void ps2_host_resume(void);

// ps2_vendor.c: no stream-mode reads while the stick is off or starting up;
// when the last stream packet started
extern bool     ps2_stream_paused;
extern uint32_t ps2_last_packet;

// Called when DIP switches 1-3 change: 0 = none or several on, 1-3 = the one that is on.
void profile_switch_user(uint8_t profile);
// DIP switches as read from matrix column 14 rows 0-7, bit n = switch n+1 on (shinobi.c).
extern uint8_t tex_dip;
#define TEX_DIP4_FN_SCROLL (1 << 3) // Fn + stick scrolls, an Fn tap is a middle click
#define TEX_DIP5_REVERSE   (1 << 4) // vertical scrolling reversed
