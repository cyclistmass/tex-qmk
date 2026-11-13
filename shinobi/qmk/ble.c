// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
//
// QMK Bluetooth driver for the Shinobi's BLE board: a Chengyong nRF52810 module
// on J3, talking to the MCU over USART0 (B0 TX, B1 RX, 500 kbaud 8N1). It
// reproduces the stock AP 4.04 link layer (PORT_NOTES.md, "BLE link"):
//
//   wire:  CRC_le, ~CRC_le, (0xA800 | len)_le, inner[len]
//          CRC-16/XMODEM over the length word and the inner frame
//   inner: 7C type seq n payload
//
// One frame is in flight at a time. The module acks with a 7C '4' frame whose
// seq matches; without one, stock resends the same frame every 127.5 ms.
//
// The module builds the HID reports itself from key events, 12-bit codes
// (module firmware FUN_0001e278): HID keyboard usages, 0xE0-0xE7 for the
// modifiers, 0xE9-0xEB for power/sleep/wake, 0xEC-0xFD for the consumer keys
// and 0x1F0-0x1F7 for mouse buttons 1-8. The module never sends on its own;
// it answers frames, so the MCU polls with '4' to see link and LED changes.
#include <string.h>
#include "quantum.h"
#include "bluetooth.h"
#include "connection.h"
#include "shinobi.h"

#define BLE_SD SD0
#define BLE_RETRANSMIT_MS 128 // stock: 255 ticks of 0.5 ms
#define BLE_PAIR_HOLD_MS 3000 // stock: 6000 ticks
#define BLE_POLL_MS 250       // module notes: poll every 100-500 ms
#define BLE_HOLD_MS 5000      // keys typed while the link is down wait this long for it
#define BLE_KEY_GAP_MS 20     // between key frames; Fn+B's settle time

#define FRAME_MARK 0x7C
#define TYPE_CONFIG '1'
#define TYPE_STATUS '4'
#define TYPE_KEYS '5'
#define TYPE_MOUSE '6'

#define CMD_WAKE 0x40
#define CMD_SLOT 0xC0 // + slot 0..2
#define CMD_PAIR 0xE0 // + slot 0..2

#define LINK_PAIRING 3
#define LINK_CONNECTED 4

// Stock flags byte (S+0x17).
#define FLAG_MOUSE 0x80
#define FLAG_BATTERY 0x40
#define FLAG_REPLY 0x20
#define FLAG_STATUS 0x02
#define FLAG_LEDS 0x01

#define KEY_PRESSED 0x8000
#define KEYS_PER_FRAME 30
#define KEY_RING_SIZE 32

#define CODE_SYSTEM_FIRST 0xE9 // power, sleep, wake
#define CODE_CONSUMER_FIRST 0xEC
#define CODE_MOUSE_BUTTON1 0x1F0

// Stock '1' payload (flash 0x9A40); "TEX-BLE" is the advertised name, the
// other fields are not decoded.
static const uint8_t config_block[32] = {0x00, 0x00, 0x10, 0x00, 0xB8, 0x0B, 0x28, 0x00, 0x50, 0x46, 0xA0,
                                         0x00, 0x7F, 0xFF, 0xFF, 0xFF, 'T',  'E',  'X',  '-',  'B',  'L',
                                         'E',  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

// Consumer usages in the order of stock's bitmap (codes 0xEC..0xFD).
static const uint16_t consumer_usages[] = {
    AL_CC_CONFIG, AL_EMAIL, AL_CALCULATOR, AL_LOCAL_BROWSER, TRANSPORT_PLAY_PAUSE, TRANSPORT_STOP, TRANSPORT_PREV_TRACK,
    TRANSPORT_NEXT_TRACK, AUDIO_MUTE, AUDIO_VOL_DOWN, AUDIO_VOL_UP, AC_SEARCH, AC_HOME, AC_BACK, AC_FORWARD, AC_STOP,
    AC_REFRESH, AC_BOOKMARKS,
};

static const SerialConfig ble_serial_config = {.speed = 500000};

static uint8_t  seq;
static uint8_t  inflight;           // type awaiting an ack, 0 when idle
static uint8_t  inflight_keys;      // entries carried by the in-flight '5'
static int16_t  inflight_mouse[4];  // deltas carried by the in-flight '6'
static uint16_t sent_at;
static uint8_t  cmd_queue[8];
static uint8_t  cmd_head, cmd_count;
static uint16_t key_ring[KEY_RING_SIZE];
static uint8_t  key_tail, key_count;
static int16_t  mouse_acc[4]; // x, y, wheel, pan
static uint8_t  flags;
static uint8_t  battery = 100; // the module shows it to the host as the Battery Service level
static uint8_t  host_leds;
static uint8_t  status_spare[2]; // module '4' bytes 6..7, echoed back as stock does
static uint8_t  status_block[7]; // [0] link state, [1] slot 0..2; [6] is not the module's
static bool     status_seen;
static uint16_t link_down_at; // when keys started waiting for the link
static uint32_t woke_at;      // ble_wake()
static bool     wake_waiting; // from ble_wake() until the link is up
uint16_t        ble_wake_ms;
static uint16_t keys_acked_at;

static report_keyboard_t last_keyboard;
static report_nkro_t     last_nkro;
static uint8_t           last_mouse_buttons;
static uint8_t           last_consumer_code;
static uint8_t           last_system_code;

static uint16_t crc16_xmodem(const uint8_t *data, uint8_t len, uint16_t crc) {
    while (len--) {
        crc ^= (uint16_t)*data++ << 8;
        for (uint8_t i = 0; i < 8; i++) {
            crc = crc & 0x8000 ? crc << 1 ^ 0x1021 : crc << 1;
        }
    }
    return crc;
}

static void send_frame(const uint8_t *inner, uint8_t len) {
    uint8_t  head[6];
    uint16_t length = 0xA800 | len;
    head[4]         = length & 0xFF;
    head[5]         = length >> 8;
    uint16_t crc    = crc16_xmodem(inner, len, crc16_xmodem(head + 4, 2, 0));
    head[0]         = crc & 0xFF;
    head[1]         = crc >> 8;
    head[2]         = ~crc & 0xFF;
    head[3]         = ~crc >> 8;
    sdWrite(&BLE_SD, head, sizeof(head));
    sdWrite(&BLE_SD, inner, len);
}

static void queue_command(uint8_t cmd) {
    if (cmd_count < sizeof(cmd_queue)) {
        cmd_queue[(cmd_head + cmd_count++) % sizeof(cmd_queue)] = cmd;
    }
}

static void queue_key(uint16_t code, bool pressed) {
    // Stock drops events silently when its ring is full; so does this.
    if (code && key_count < KEY_RING_SIZE) {
        key_ring[(key_tail + key_count++) % KEY_RING_SIZE] = code | (pressed ? KEY_PRESSED : 0);
    }
}

static bool bluetooth_link_up(void) {
    return status_seen && status_block[0] == LINK_CONNECTED;
}

// Builds and sends one frame of the given type (stock FUN_7a50).
static void build(uint8_t type) {
    uint8_t frame[4 + 2 * KEYS_PER_FRAME] = {FRAME_MARK, type, seq, 0};
    uint8_t len                           = 4;

    switch (type) {
        case TYPE_CONFIG:
            memcpy(frame + 4, config_block, sizeof(config_block));
            len += sizeof(config_block);
            break;
        case TYPE_STATUS:
            frame[4] = battery;
            frame[5] = host_leds;
            memcpy(frame + 6, status_spare, sizeof(status_spare));
            memcpy(frame + 8, status_block, sizeof(status_block));
            len = 15;
            break;
        case TYPE_KEYS:
            // A press and its release in one frame reach the host as nothing
            // (taps held for the link were lost so), so a frame ends before a
            // key it already has.
            inflight_keys = 0;
            while (inflight_keys < key_count && inflight_keys < KEYS_PER_FRAME) {
                uint16_t entry = key_ring[(key_tail + inflight_keys) % KEY_RING_SIZE];
                bool     again = false;
                for (uint8_t i = 4; i < len; i += 2) {
                    if (((frame[i] | frame[i + 1] << 8) ^ entry) & ~KEY_PRESSED) continue;
                    again = true;
                }
                if (again) break;
                frame[len++] = entry & 0xFF;
                frame[len++] = entry >> 8;
                inflight_keys++;
            }
            frame[3] = inflight_keys;
            break;
        case TYPE_MOUSE:
            memcpy(inflight_mouse, mouse_acc, sizeof(inflight_mouse));
            frame[4] = inflight_mouse[0] & 0xFF;
            frame[5] = inflight_mouse[0] >> 8;
            frame[6] = inflight_mouse[1] & 0xFF;
            frame[7] = inflight_mouse[1] >> 8;
            frame[8] = (int8_t)inflight_mouse[2];
            frame[9] = (int8_t)inflight_mouse[3];
            len      = 10;
            break;
        default: // commands are header-only
            break;
    }
    send_frame(frame, len);
    sent_at = timer_read();
}

// Picks the next frame the way stock does: retransmit first, then a queued
// command, then mouse or status, then keys.
static void send_next(void) {
    if (inflight) {
        build(inflight);
        return;
    }
    // Keys typed while the link is down (waking, or USB just unplugged) wait
    // for it, as stock delivers them: the key that woke the board, then the
    // next two taps, were lost (Mauro, 2026-11-04). Pointer motion would only
    // arrive as a jump, so it is dropped.
    bool link_up = bluetooth_link_up();
    if (link_up || !key_count) link_down_at = timer_read();
    if (!link_up) {
        memset(mouse_acc, 0, sizeof(mouse_acc));
        flags &= ~FLAG_MOUSE;
        if (timer_elapsed(link_down_at) >= BLE_HOLD_MS) key_tail = key_count = 0;
    }
    uint8_t type;
    if (cmd_count) {
        type = cmd_queue[cmd_head];
    } else if (flags & FLAG_MOUSE) {
        type = TYPE_MOUSE;
    } else if (flags) {
        // A status reply needs no ack and keeps the current seq.
        flags = 0;
        build(TYPE_STATUS);
        return;
    } else if (key_count && link_up && timer_elapsed(keys_acked_at) >= BLE_KEY_GAP_MS) {
        type = TYPE_KEYS;
    } else {
        // Idle: a '4' echoing what the module last said draws an answer only
        // when the link state or the host LEDs changed.
        if (timer_elapsed(sent_at) >= BLE_POLL_MS) build(TYPE_STATUS);
        return;
    }
    seq++;
    inflight = type;
    build(type);
}

static void acked(void) {
    switch (inflight) {
        case TYPE_KEYS:
            key_tail = (key_tail + inflight_keys) % KEY_RING_SIZE;
            key_count -= inflight_keys;
            keys_acked_at = timer_read();
            break;
        case TYPE_MOUSE:
            // Stock zeroes the accumulators here and loses what came in since
            // the build; subtract what was sent instead.
            for (uint8_t i = 0; i < 4; i++) mouse_acc[i] -= inflight_mouse[i];
            if (!mouse_acc[0] && !mouse_acc[1] && !mouse_acc[2] && !mouse_acc[3]) flags &= ~FLAG_MOUSE;
            break;
        default:
            if (cmd_count && cmd_queue[cmd_head] == inflight) {
                cmd_head = (cmd_head + 1) % sizeof(cmd_queue);
                cmd_count--;
            }
            break;
    }
    inflight = 0;
}

// A 7C '4' from the module: link status, host LEDs, and the ack (stock FUN_3f8c).
static void handle_status(const uint8_t *in, uint8_t len) {
    if (len < 15) return;
    if (!inflight && !flags) {
        flags = FLAG_REPLY;
    } else {
        flags &= FLAG_MOUSE;
    }
    if (in[4] != battery) flags |= FLAG_BATTERY;
    if (in[5] != host_leds) {
        host_leds = in[5];
        flags |= FLAG_LEDS;
    }
    memcpy(status_spare, in + 6, sizeof(status_spare));
    if (!status_seen || memcmp(status_block, in + 8, sizeof(status_block))) {
        memcpy(status_block, in + 8, sizeof(status_block));
        status_seen = true;
        flags |= FLAG_STATUS;
    }
    if (wake_waiting && status_block[0] == LINK_CONNECTED) {
        uint32_t ms  = timer_elapsed32(woke_at);
        ble_wake_ms  = ms < 65535 ? ms : 65535;
        wake_waiting = false;
    }
    if (inflight && in[2] == seq) acked();
    send_next();
}

static void handle_frame(const uint8_t *in, uint8_t len) {
    // Frames not starting 7C tunnel the vendor protocol (stock passes them to
    // its USB command handlers, the IAP jump included); they are ignored here.
    if (len >= 2 && in[0] == FRAME_MARK && in[1] == TYPE_STATUS) {
        handle_status(in, len);
    }
}

// Receive: resynchronise byte by byte on the header checks, then the CRC (stock FUN_8000).
static void poll_rx(void) {
    static uint8_t buf[6 + 64];
    static uint8_t n;
    msg_t          c;
    while ((c = sdGetTimeout(&BLE_SD, TIME_IMMEDIATE)) >= 0) {
        buf[n++] = c;
        while (n >= 6) {
            uint16_t crc    = buf[0] | buf[1] << 8;
            uint16_t ncrc   = buf[2] | buf[3] << 8;
            uint16_t length = buf[4] | buf[5] << 8;
            uint8_t  len    = length & 0x7FF;
            if ((uint16_t)(crc + ncrc) != 0xFFFF || length >> 11 != 0x15 || len > 64) {
                memmove(buf, buf + 1, --n);
                continue;
            }
            if (n < 6 + len) break;
            if (crc16_xmodem(buf + 6, len, crc16_xmodem(buf + 4, 2, 0)) == crc) {
                handle_frame(buf + 6, len);
                n = 0;
            } else {
                memmove(buf, buf + 1, --n);
            }
            break;
        }
    }
}

void bluetooth_init(void) {
    palSetLineMode(B0, PAL_MODE_HT32_AF(6));
    palSetLineMode(B1, PAL_MODE_HT32_AF(6) | PAL_HT32_MODE_INE);
    sdStart(&BLE_SD, &ble_serial_config);
    // Stock cold boot: the config block, then three wake commands.
    queue_command(TYPE_CONFIG);
    queue_command(CMD_WAKE);
    queue_command(CMD_WAKE);
    queue_command(CMD_WAKE);
}

void bluetooth_task(void) {
    poll_rx();
    if (!inflight || timer_elapsed(sent_at) >= BLE_RETRANSMIT_MS) {
        send_next();
    }
}

// Typed text (Fn+B) comes far faster than a person types. Events sent back to
// back reach the host merged: Fn+B lost doubled letters and whole taps. Runs
// the link until every queued key is acked (at most 250 ms, so a lost link
// can't hang the keyboard), then settle_ms more before the next event.
void ble_flush_keys(uint8_t settle_ms) {
    uint16_t start = timer_read();
    while ((key_count || inflight) && timer_elapsed(start) < 250) {
        bluetooth_task();
    }
    start = timer_read();
    while (timer_elapsed(start) < settle_ms) {
        bluetooth_task();
    }
}

bool ble_pairing(void) {
    return status_seen && status_block[0] == LINK_PAIRING;
}

void ble_set_battery(uint8_t percent) {
    if (percent != battery) {
        battery = percent;
        flags |= FLAG_BATTERY;
    }
}

// Stock stops USART0 and leaves the module connected (FUN_7ec8); the module
// idles on its own after its inactivity timeout. TX stays high, the line's
// idle level: a low on it wakes the module.
void ble_sleep(void) {
    sdStop(&BLE_SD);
    palSetLineMode(B0, PAL_HT32_MODE_AF(AFIO_GPIO) | PAL_MODE_OUTPUT_PUSHPULL);
    palSetLine(B0);
}

void ble_wake(void) {
    palSetLineMode(B0, PAL_MODE_HT32_AF(6));
    sdStart(&BLE_SD, &ble_serial_config);
    queue_command(CMD_WAKE);
    status_seen = false; // the link may have dropped while asleep
    woke_at      = timer_read32();
    wake_waiting = true;
}

// QMK asks this only to pick the output in auto mode, where USB comes first.
// Without USB the module is the only way out, so it is chosen while its link
// comes up too, and keys wait in the ring (send_next).
bool bluetooth_is_connected(void) {
    return !ble_pairing();
}

uint8_t bluetooth_keyboard_leds(void) {
    return host_leds;
}

static bool report_has(const report_keyboard_t *report, uint8_t code) {
    for (uint8_t i = 0; i < KEYBOARD_REPORT_KEYS; i++) {
        if (report->keys[i] == code) return true;
    }
    return false;
}

// QMK hands over reports; the module wants press and release events.
void bluetooth_send_keyboard(report_keyboard_t *report) {
    uint8_t mods = report->mods ^ last_keyboard.mods;
    for (uint8_t i = 0; i < 8; i++) {
        if (mods >> i & 1) queue_key(KC_LEFT_CTRL + i, report->mods >> i & 1);
    }
    for (uint8_t i = 0; i < KEYBOARD_REPORT_KEYS; i++) {
        if (last_keyboard.keys[i] && !report_has(report, last_keyboard.keys[i])) queue_key(last_keyboard.keys[i], false);
    }
    for (uint8_t i = 0; i < KEYBOARD_REPORT_KEYS; i++) {
        if (report->keys[i] && !report_has(&last_keyboard, report->keys[i])) queue_key(report->keys[i], true);
    }
    last_keyboard = *report;
}

bool bluetooth_can_send_nkro(void) {
    return true;
}

// The module keeps up to 19 keys down (its own report is not 6KRO).
void bluetooth_send_nkro(report_nkro_t *report) {
    uint8_t mods = report->mods ^ last_nkro.mods;
    for (uint8_t i = 0; i < 8; i++) {
        if (mods >> i & 1) queue_key(KC_LEFT_CTRL + i, report->mods >> i & 1);
    }
    for (uint8_t i = 0; i < NKRO_REPORT_BITS; i++) {
        uint8_t changed = report->bits[i] ^ last_nkro.bits[i];
        for (uint8_t b = 0; b < 8; b++) {
            if (changed >> b & 1) queue_key(i * 8 + b, report->bits[i] >> b & 1);
        }
    }
    last_nkro = *report;
}

void bluetooth_send_mouse(report_mouse_t *report) {
    // QMK's button bits are HID buttons 1-8: left, right, middle, ...
    uint8_t changed = report->buttons ^ last_mouse_buttons;
    for (uint8_t i = 0; i < 8; i++) {
        if (changed >> i & 1) queue_key(CODE_MOUSE_BUTTON1 + i, report->buttons >> i & 1);
    }
    last_mouse_buttons = report->buttons;

    const int16_t delta[4] = {report->x, report->y, report->v, report->h};
    for (uint8_t i = 0; i < 4; i++) {
        mouse_acc[i] += delta[i];
        if (delta[i]) flags |= FLAG_MOUSE;
    }
}

void bluetooth_send_consumer(uint16_t usage) {
    uint8_t code = 0;
    for (uint8_t i = 0; i < ARRAY_SIZE(consumer_usages); i++) {
        if (consumer_usages[i] == usage) code = CODE_CONSUMER_FIRST + i;
    }
    if (code == last_consumer_code) return;
    queue_key(last_consumer_code, false);
    queue_key(code, true);
    last_consumer_code = code;
}

void bluetooth_send_system(uint16_t usage) {
    uint8_t code = usage >= SYSTEM_POWER_DOWN && usage <= SYSTEM_WAKE_UP ? CODE_SYSTEM_FIRST + (usage - SYSTEM_POWER_DOWN) : 0;
    if (code == last_system_code) return;
    queue_key(last_system_code, false);
    queue_key(code, true);
    last_system_code = code;
}

// Fn+Mute / Fn+Vol- / Fn+Vol+: tap selects host slot 1-3, holding 3 s pairs a
// new host on that slot. The pair button pairs slot 1, as stock does. Either
// sends keys over Bluetooth even with USB plugged in; Fn+Esc goes back to USB.
static uint8_t  slot_key;  // BLE_SLOT1..3 or BLE_PAIR held, 0 when none
static uint16_t slot_key_since;
static bool     slot_key_paired;

bool ble_process_record(uint16_t keycode, keyrecord_t *record) {
    if (keycode == BLE_USB) {
        if (record->event.pressed) connection_set_host_noeeprom(CONNECTION_HOST_AUTO);
        return false;
    }
    if (keycode < BLE_SLOT1 || keycode > BLE_PAIR) return true;
    if (record->event.pressed) {
        slot_key        = keycode;
        slot_key_since  = timer_read();
        slot_key_paired = false;
    } else if (slot_key == keycode) {
        if (!slot_key_paired && keycode != BLE_PAIR) {
            queue_command(CMD_SLOT + (keycode - BLE_SLOT1));
            connection_set_host_noeeprom(CONNECTION_HOST_BLUETOOTH);
        }
        slot_key = 0;
    }
    return false;
}

void ble_housekeeping(void) {
    if (slot_key && !slot_key_paired && timer_elapsed(slot_key_since) >= BLE_PAIR_HOLD_MS) {
        slot_key_paired = true;
        queue_command(CMD_PAIR + (slot_key == BLE_PAIR ? 0 : slot_key - BLE_SLOT1));
        connection_set_host_noeeprom(CONNECTION_HOST_BLUETOOTH);
    }

    // C10 blinks every 100 ms while the module pairs, as stock does; otherwise
    // it stays the Caps Lock indicator of whichever host is active.
    static bool     blinking;
    static uint16_t blink_at;
    bool            pairing = ble_pairing();
    if (pairing && timer_elapsed(blink_at) >= 100) {
        blink_at = timer_read();
        palToggleLine(C10);
    } else if (!pairing && blinking) {
        led_update_ports(host_keyboard_led_state());
    }
    blinking = pairing;
}
