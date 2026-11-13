// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Host tests of the firmware's input logic: Fn scrolling and the middle button, mouse movement keys, sequence
// macros and typed text. extract.py copies the real functions from shinobi.c and power.c into extracted.c; this
// file gives them the QMK pieces they use, as stubs that keep QMK's behaviour where it matters (register_code on a
// modifier changes the real mods), drives them with random press and release sequences, and checks each step
// against a model of what the keyboard should do. Also checks divsi3.S's arithmetic, step by step, against C's;
// div_asm.sh runs the assembly itself.
//
// Not covered here: the order of the handlers in process_record_kb (Fn+Esc and Fn+slot reaching the Fn-scroll
// bookkeeping), and the wake timer in ble.c; both need the keyboard.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// --- QMK keycodes and settings, at their values in the pinned QMK and the keyboard's headers.
enum {
    KC_NO = 0x00, KC_A = 0x04, KC_1 = 0x1E, KC_0 = 0x27, KC_ENT = 0x28, KC_SPC = 0x2C, KC_MINS = 0x2D,
    KC_SCLN = 0x33, KC_DOT = 0x37, KC_5 = 0x22, KC_ESC = 0x29,
    MS_UP = 0xCD, MS_DOWN, MS_LEFT, MS_RGHT, MS_BTN1 = 0xD1, MS_BTN2, MS_BTN3,
    KC_LEFT_CTRL = 0xE0, KC_LSFT = 0xE1, KC_RIGHT_GUI = 0xE7,
    QK_MOMENTARY = 0x5220, QK_MOMENTARY_MAX = 0x523F,
    MS_UPLEFT = 0x7E00, MS_UPRIGHT, MS_DOWNLEFT, MS_DOWNRIGHT, // shinobi.h's custom keycodes, in order
};
#define IS_QK_MOMENTARY(code) ((code) >= QK_MOMENTARY && (code) <= QK_MOMENTARY_MAX)
#define MO(layer) (QK_MOMENTARY | (layer))
#define TEX_DIP4_FN_SCROLL (1 << 3)
#define PS2_MOUSE_BTN_MIDDLE 2
#define PS2_MOUSE_SCROLL_BTN_SEND 300
#define MOD_LCTL 0x01
#define MOD_LSFT 0x02

static int failures;
#define CHECK(cond, ...)                                    \
    do {                                                    \
        if (!(cond)) {                                      \
            if (failures++ < 20) {                          \
                printf("FAIL %s:%d: ", __func__, __LINE__); \
                printf(__VA_ARGS__);                        \
                printf("\n");                               \
            }                                               \
        }                                                   \
    } while (0)

// --- Timer: 16-bit like QMK's timer_read, starting near the wrap so the tests cross it.
static uint32_t now = 65000;
static uint16_t timer_read(void) { return (uint16_t)now; }
static uint16_t timer_elapsed(uint16_t t) { return (uint16_t)(now - t); }

// --- Keyboard state: QMK's real mods and keys, and the reports sent.
static uint8_t real_mods, keys[256];
typedef struct { uint8_t mods; uint8_t key; } report_t; // key: the one key down, or 0 (tests press one at a time)
static report_t reports[4096];
static int      n_reports;

static void send_keyboard_report(void) {
    report_t r = {real_mods, 0};
    for (int k = 0; k < 256; k++) {
        if (keys[k]) r.key = (uint8_t)k;
    }
    if (n_reports < 4096) reports[n_reports++] = r;
}
static uint8_t get_mods(void) { return real_mods; }
static void    clear_mods(void) { real_mods = 0; }
static void    set_mods(uint8_t m) { real_mods = m; }
static void    register_code(uint8_t c) {
    if (c >= KC_LEFT_CTRL && c <= KC_RIGHT_GUI) {
        real_mods |= 1 << (c & 7);
    } else {
        keys[c] = 1;
    }
    send_keyboard_report();
}
static void unregister_code(uint8_t c) {
    if (c >= KC_LEFT_CTRL && c <= KC_RIGHT_GUI) {
        real_mods &= ~(1 << (c & 7));
    } else {
        keys[c] = 0;
    }
    send_keyboard_report();
}
static void ble_flush_keys(uint16_t ms) { (void)ms; }

static int     tp_buttons;
static uint8_t tex_dip;

static const uint8_t macro_table[] = {
    0xE1, 0x0B, 0x08, 0, // 0: Shift held for "h", then "e": "He"
    0xE0, 0x06, 0,       // 1: Ctrl+C
    0xE8, 0x04, 0,       // 2: 0xE8 isn't a modifier; it is tapped, then "a"
    0xE0, 0xE1, 0x1D, 0, // 3: Ctrl+Shift+Z
};
static const uint8_t *tex_macros = macro_table, *tex_macros_end = macro_table + sizeof(macro_table);

#include "extracted.c"

// --- Mouse movement keys: random presses and releases of all eight; each direction must move while any of its
// three keys is held (its own and the two diagonals that include it).
static void test_mousekeys(void) {
    static const uint16_t key[8] = {MS_UP, MS_DOWN, MS_LEFT, MS_RGHT, MS_UPLEFT, MS_UPRIGHT, MS_DOWNLEFT, MS_DOWNRIGHT};
    // per key: up, down, left, right
    static const bool dirs[8][4] = {{1, 0, 0, 0}, {0, 1, 0, 0}, {0, 0, 1, 0}, {0, 0, 0, 1},
                                    {1, 0, 1, 0}, {1, 0, 0, 1}, {0, 1, 1, 0}, {0, 1, 0, 1}};
    static const uint8_t mask[4] = {MK_UP, MK_DOWN, MK_LEFT, MK_RIGHT};
    bool held[8] = {0};
    mk_held      = 0;
    for (int step = 0; step < 20000; step++) {
        int k   = rand() % 8;
        held[k] = !held[k];
        mousekey_record(key[k], held[k]);
        for (int d = 0; d < 4; d++) {
            bool want = false;
            for (int i = 0; i < 8; i++) want |= held[i] && dirs[i][d];
            CHECK(((mk_held & mask[d]) != 0) == want, "step %d direction %d: moving %d, want %d", step, d, (mk_held & mask[d]) != 0, want);
        }
    }
    // The reported case: hold Up, press and release Up-Left: Up keeps moving, left stops.
    mk_held = 0;
    mousekey_record(MS_UP, true);
    mousekey_record(MS_UPLEFT, true);
    mousekey_record(MS_UPLEFT, false);
    CHECK((mk_held & MK_UP) && !(mk_held & MK_LEFT), "Up held, Up-Left released: mk_held %02x", mk_held);
}

// --- Fn scrolling (DIP 4) and the middle button's own key share the middle button. Model: it is down while the
// key is held, while Fn (pressed with DIP 4 on) is held, and after such an Fn hold that saw another key, until
// more than PS2_MOUSE_SCROLL_BTN_SEND ms after its release (so the hold doesn't end in a click). There are two Fn
// keys, MO(3) on Base and on the Fn/Ctrl swap layer; Fn is down while either is. Another layer's key, MO(1), is an
// ordinary key.
static void test_middle(void) {
    bool     btn3 = false, fn[2] = {0}, fn_dip = false, fn_other = false, waiting = false;
    uint32_t released = 0;
    fn_scroll = 0, fn_down = 0, mid_key = false, tp_buttons = 0;
    for (int step = 0; step < 200000; step++) {
        int r = rand() % 11;
        if (r == 0) {
            tex_dip ^= TEX_DIP4_FN_SCROLL;
            continue;
        }
        uint16_t keycode = KC_NO;
        bool     pressed = false;
        if (r <= 3) { // time passes; housekeeping calls with KC_NO
            now += rand() % 2 ? rand() % 40 : rand() % 400;
        } else if (r <= 5) {
            int  k    = rand() % 2;
            bool any  = fn[0] || fn[1];
            keycode   = MO(3), pressed = fn[k] = !fn[k];
            bool now_ = fn[0] || fn[1];
            if (!any && now_) {
                if (waiting && now - released > PS2_MOUSE_SCROLL_BTN_SEND) waiting = false;
                if (tex_dip & TEX_DIP4_FN_SCROLL) fn_dip = true, fn_other = false, waiting = false;
            } else if (any && !now_ && fn_dip) {
                fn_dip = false;
                if (fn_other) waiting = true, released = now;
            }
        } else if (r <= 7) {
            keycode = MS_BTN3, pressed = btn3 = !btn3;
        } else {
            keycode = r == 8 ? KC_A : r == 9 ? KC_ESC : MO(1), pressed = rand() % 2;
            if (pressed && fn_dip) fn_other = true;
        }
        fn_scroll_record(keycode, pressed);
        if (waiting && now - released > PS2_MOUSE_SCROLL_BTN_SEND) waiting = false;
        bool want = btn3 || fn_dip || waiting;
        bool down = tp_buttons & 1 << PS2_MOUSE_BTN_MIDDLE;
        CHECK(down == want, "step %d: middle %d, want %d (key %d, Fn %d%d, other %d, waiting %d)", step, down, want, btn3, fn[0], fn[1], fn_other, waiting);
        CHECK((tp_buttons & ~(1 << PS2_MOUSE_BTN_MIDDLE)) == 0, "step %d: other buttons changed: %x", step, tp_buttons);
    }
}

// --- Macros and typed text: each key goes out with only the modifiers the macro (or Shift for ':' and '%') asks
// for, whatever the user holds, and the held ones are back afterwards, also in the last report.
static void expect_keys(const char *what, uint8_t held, const report_t *want, int n_want) {
    int n = 0;
    for (int i = 0; i < n_reports; i++) {
        if (!reports[i].key || (i && reports[i - 1].key == reports[i].key)) continue; // presses only
        CHECK(n < n_want, "%s with mods %02x: extra key %02x", what, held, reports[i].key);
        if (n < n_want) {
            CHECK(reports[i].key == want[n].key && reports[i].mods == want[n].mods, "%s with mods %02x: key %d is %02x+%02x, want %02x+%02x", what, held, n, reports[i].mods,
                  reports[i].key, want[n].mods, want[n].key);
        }
        n++;
    }
    CHECK(n == n_want, "%s with mods %02x: %d keys, want %d", what, held, n, n_want);
    CHECK(real_mods == held, "%s with mods %02x: mods afterwards %02x", what, held, real_mods);
    CHECK(n_reports && reports[n_reports - 1].mods == held && !reports[n_reports - 1].key, "%s with mods %02x: last report %02x+%02x", what, held,
          reports[n_reports - 1].mods, reports[n_reports - 1].key);
}

static void test_typing(void) {
    static const report_t m0[] = {{MOD_LSFT, 0x0B}, {0, 0x08}}, m1[] = {{MOD_LCTL, 0x06}}, m2[] = {{0, 0xE8}, {0, 0x04}},
                          m3[] = {{MOD_LCTL | MOD_LSFT, 0x1D}}, text[] = {{0, KC_A}, {MOD_LSFT, KC_SCLN}, {MOD_LSFT, KC_5}, {0, KC_SPC}, {0, KC_1}};
    static const struct { const report_t *want; int n; } macros[] = {{m0, 2}, {m1, 1}, {m2, 2}, {m3, 1}};
    static const uint8_t held[] = {0, MOD_LSFT, MOD_LCTL, MOD_LCTL | MOD_LSFT, 0xFF};
    char what[16];
    for (unsigned h = 0; h < sizeof(held); h++) {
        for (int m = 0; m < 4; m++) {
            real_mods = held[h], n_reports = 0;
            macro_play((uint8_t)m);
            snprintf(what, sizeof(what), "macro %d", m);
            expect_keys(what, held[h], macros[m].want, macros[m].n);
        }
        real_mods = held[h], n_reports = 0;
        type_text("a:% 1");
        expect_keys("type_text", held[h], text, 5);
    }
    // No typed answer may press Enter (or keypad Enter): one typed into a chat would send it.
    for (int c = 1; c < 128; c++) {
        char s[2] = {(char)c, 0};
        n_reports = 0;
        type_text(s);
        for (int i = 0; i < n_reports; i++) CHECK(reports[i].key != KC_ENT && reports[i].key != 0x58, "type_text(%d) pressed Enter", c);
    }
}

// --- divsi3.S, instruction by instruction on 32-bit registers, against C's division (rounds toward zero).
static uint32_t asr31(uint32_t x) { return x >> 31 ? 0xFFFFFFFFu : 0; }
static int32_t  divsi3_model(int32_t a, int32_t b) {
    uint32_t r0 = (uint32_t)a, r1 = (uint32_t)b, r2, r4;
    r4 = r0, r4 ^= r1;
    r2 = asr31(r0), r0 ^= r2, r0 -= r2;
    r2 = asr31(r1), r1 ^= r2, r1 -= r2;
    r0 = r0 / r1; // __udivsi3
    r4 = asr31(r4), r0 ^= r4, r0 -= r4;
    return (int32_t)r0;
}
static void test_divsi3(void) {
    static const int32_t edge[] = {0, 1, -1, 2, -2, 5, -5, 13, -13, 14, -14, 127, -128, 32767, -32768, INT32_MAX, INT32_MIN};
    int n = sizeof(edge) / sizeof(edge[0]);
    for (int i = 0; i < n + 200000; i++) {
        int32_t a = i < n * n ? edge[i % n] : (int32_t)((uint32_t)rand() << 16 ^ (uint32_t)rand());
        int32_t b = i < n * n ? edge[i / n % n] : (int32_t)(rand() % 2 ? rand() % 29 - 14 : (uint32_t)rand() << 16 ^ (uint32_t)rand());
        if (b == 0 || (a == INT32_MIN && b == -1)) continue; // C leaves these undefined
        int32_t q = divsi3_model(a, b);
        CHECK(q == a / b, "%d / %d: %d, want %d", a, b, q, a / b);
        CHECK(a - q * b == a % b, "%d %% %d: %d, want %d", a, b, a - q * b, a % b); // __aeabi_idivmod's remainder
    }
}

int main(void) {
    srand(1);
    test_mousekeys();
    test_middle();
    test_typing();
    test_divsi3();
    if (failures) {
        printf("FAIL host tests: %d failures\n", failures);
        return 1;
    }
    printf("PASS host tests: mouse keys, Fn scroll and middle button, macros and typed text with held modifiers, divsi3\n");
    return 0;
}
