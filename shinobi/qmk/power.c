// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Battery level and sleep on battery power, after stock (PORT_NOTES.md, "Power").
#include "quantum.h"
#include "shinobi.h"
#include "version.h"

// B12 WAKEUP: high on USB power (D201) or when the BLE board raises TO_MCU
// (D202; the module firmware never does). Low = running on battery.
#define WAKEUP_PIN B12

// Stock sleeps after 15 min without input on battery (1 800 000 ticks of 0.5 ms,
// config 0x20000638+8). Test keymap "sleep30" shortens it.
#ifdef TEX_SLEEP_IDLE_MS
#    define SLEEP_IDLE_MS TEX_SLEEP_IDLE_MS
#else
#    define SLEEP_IDLE_MS (15UL * 60 * 1000)
#endif

// BAT_PWR reaches A0 through R7 with R11/C8 to ground. The ADC is set up as
// stock FUN_340c does: CK_AHB/64, channel 0 alone, 16-cycle sampling,
// continuous conversion started once by software. Polled; stock takes an
// interrupt per conversion.
#define BAT_ADC_REG(off) (*(volatile uint32_t *)(0x40010000U + (off)))
#define BAT_ADC_CR BAT_ADC_REG(0x00)
#define BAT_ADC_LST0 BAT_ADC_REG(0x04)
#define BAT_ADC_STR BAT_ADC_REG(0x20)
#define BAT_ADC_DR0 BAT_ADC_REG(0x30)
#define BAT_ADC_TCR BAT_ADC_REG(0x70)
#define BAT_ADC_TSR BAT_ADC_REG(0x74)
#define BAT_ADC_CR_RUN 0x82 // as stock writes it: ADC on, continuous
#define BAT_ADC_ADCDIV_64 (6U << 16)
#define BAT_SAMPLE_MS 100

// Stock's only use of the reading: below 0x834 on battery, the LED shows a low
// battery (FUN_974c). The percentage is not stock: stock always tells the BLE
// module 100. The divider values are not known, so the scale below assumes
// two alkaline AA cells and that stock warns at 1.10 V a cell [I]; BAT_REPORT
// types the raw reading so the scale can be checked against a meter.
#define BAT_LOW 0x834
#define BAT_LOW_CLEAR (BAT_LOW + 40)
static const struct {
    uint16_t raw;
    uint8_t  percent;
} bat_curve[] = {
    // raw = 0x834 * V_cell / 1.10 V; alkaline discharge shape
    {2864, 100}, {2673, 85}, {2482, 60}, {2386, 45}, {2291, 30}, {2195, 18}, {2100, 8}, {1909, 0},
};

// Low battery on the LED (stock FUN_569c, 0.5 ms ticks): 3 blinks of 25 ms,
// then a 3 s pause.
#define LOW_BLINK_MS 25
#define LOW_PAUSE_MS 3000

// Wake sources: the matrix rows A1-A8 (EXTI lines 1-8) with every column
// driven high, and B12 (line 12). The rows are pulled down, so a key held
// across the row's diode reads high, as in stock's scan.
#define EXTI_REG(off) (*(volatile uint32_t *)(0x40024000U + (off)))
#define EXTI_WAKUPCR EXTI_REG(0x50)
#define EXTI_WAKUPPOLR EXTI_REG(0x54) // 0 = wake on high
#define EXTI_WAKUPFLG EXTI_REG(0x58)
#define EXTI_WAKUPCR_EVWUPIEN (1U << 31)
#define WAKE_LINES 0x11FEU // lines 1-8 and 12
#define EVWUP_IRQ 3        // HT32_EVWUP_IRQ_VECTOR, Vector4C

// WDTSHLT mode 2: the watchdog halts in sleep and deep sleep, so it can't
// reset the board while nothing kicks it. PR 0x35CA unlocks MR0.
#define WDT_PR_UNLOCK 0x35CA

// Fn+F1..F9 pick the sleep time in minutes (0 = never); shinobi.c saves it.
static const uint8_t sleep_minutes[] = {1, 2, 5, 10, 15, 30, 60, 120, 0};
static uint32_t      sleep_idle_ms   = SLEEP_IDLE_MS;
static bool          slept;

// A wake with no input after it goes back to sleep this soon (USB power
// leaving again, or a key released before the scan saw it).
#define WAKE_GRACE_MS 2000

static const pin_t wake_rows[MATRIX_ROWS] = MATRIX_ROW_PINS;
static const pin_t wake_cols[MATRIX_COLS] = MATRIX_COL_PINS;

// quantum/matrix.c; not in its header.
void matrix_init_pins(void);

static uint32_t bat_filtered; // raw * 16
static uint16_t bat_sampled_at;
static bool     bat_low;
static uint32_t awake_since;
static uint32_t pointer_activity;

static bool on_battery(void) {
    return !palReadLine(WAKEUP_PIN);
}

static void bat_adc_start(void) {
    CKCU->APBCCR1 |= CKCU_APBCCR1_ADCEN;
    CKCU->APBCFGR = (CKCU->APBCFGR & ~CKCU_APBCFGR_ADCDIV_MASK) | BAT_ADC_ADCDIV_64;
    palSetLineMode(A0, PAL_MODE_INPUT_ANALOG);
    BAT_ADC_CR   = 0;
    BAT_ADC_LST0 = 0;
    BAT_ADC_STR  = 16;
    BAT_ADC_TCR  = 1; // software trigger
    BAT_ADC_CR   = BAT_ADC_CR_RUN;
    BAT_ADC_TSR  = 1;
}

static void bat_adc_stop(void) {
    BAT_ADC_CR = 0;
    CKCU->APBCCR1 &= ~CKCU_APBCCR1_ADCEN;
}

uint16_t battery_raw(void) {
    return bat_filtered / 16;
}

uint8_t battery_percent(void) {
    uint16_t raw = battery_raw();
    if (raw >= bat_curve[0].raw) return 100;
    for (uint8_t i = 1; i < ARRAY_SIZE(bat_curve); i++) {
        if (raw >= bat_curve[i].raw) {
            uint16_t span = bat_curve[i - 1].raw - bat_curve[i].raw;
            uint8_t  gain = bat_curve[i - 1].percent - bat_curve[i].percent;
            return bat_curve[i].percent + (uint32_t)(raw - bat_curve[i].raw) * gain / span;
        }
    }
    return 0;
}

static void bat_task(void) {
    if (timer_elapsed(bat_sampled_at) < BAT_SAMPLE_MS) return;
    bat_sampled_at = timer_read();
    uint32_t dr    = BAT_ADC_DR0;
    if (!(dr & (1U << 31))) return; // no conversion yet
    uint16_t raw = dr & 0x0FFF;
    // About 1.6 s to settle, so a burst of keys or the radio doesn't flicker it.
    bat_filtered = bat_filtered ? bat_filtered - bat_filtered / 16 + raw : (uint32_t)raw * 16;
    bool battery = on_battery();
    if (battery && battery_raw() < BAT_LOW) {
        bat_low = true;
    } else if (!battery || battery_raw() > BAT_LOW_CLEAR) {
        bat_low = false;
    }
    ble_set_battery(battery_percent());
}

static void low_battery_led_task(void) {
    static uint16_t since;
    static uint8_t  step; // 0 = pause, 1-6 = blink half-periods
    if (!bat_low || ble_pairing()) {
        if (step) {
            step = 0;
            led_update_ports(host_keyboard_led_state());
        }
        return;
    }
    if (timer_elapsed(since) < (step ? LOW_BLINK_MS : LOW_PAUSE_MS)) return;
    since = timer_read();
    step  = step == 6 ? 0 : step + 1;
    if (step) {
        palToggleLine(C10);
    } else {
        led_update_ports(host_keyboard_led_state());
    }
}

void power_pointer_activity(void) {
    pointer_activity = timer_read32();
}

// Deep-sleep 1 until a key or B12 wakes the board (stock FUN_7760/FUN_7734,
// without its RTC tick: nothing here needs to run while asleep).
static void power_sleep(void) {
    tp_power_off();
    ble_sleep();
    bat_adc_stop();
    palSetLine(C10); // LED off (active low)

    // Columns drive high; C13, the profile switch, would hold its row high,
    // so it floats down with the rows.
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        if (c == PROFILE_SWITCH_COL) {
            palSetLineMode(wake_cols[c], PAL_MODE_INPUT_PULLDOWN);
        } else {
            palSetLineMode(wake_cols[c], PAL_MODE_OUTPUT_PUSHPULL);
            palSetLine(wake_cols[c]);
        }
    }
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        palSetLineMode(wake_rows[r], PAL_MODE_INPUT_PULLDOWN);
    }

    CKCU->APBCCR0 |= CKCU_APBCCR0_AFIOEN | CKCU_APBCCR0_EXTIEN;
    AFIO->ESSR[0] = 0;          // lines 0-7: port A
    AFIO->ESSR[1] = 1U << 16;   // line 8: port A, line 12: port B

    WDT->PR  = WDT_PR_UNLOCK;
    WDT->MR0 = (WDT->MR0 & ~WDT_MR0_WDTSHLT_MASK) | WDT_MR0_WDTSHLT_MODE2;
    WDT->PR  = 0;

    // The wake path has no deglitch filter in deep sleep (UM v1.60 ch. 11: the
    // debounce runs on PCLK, on the interrupt path only), so a short pulse on a
    // row wakes the board: row A8 did so every ~3 s, 0.5 s after each sleep
    // entry (Mauro, 2026-11-03). A key wake still holds its row high once the
    // clock is back; a pulse has ended by then, so sleep again.
    for (;;) {
        EXTI_WAKUPPOLR = 0;
        EXTI_WAKUPCR   = WAKE_LINES;
        EXTI_WAKUPFLG  = 0xFFFF;
        wait_us(1000);
        // A line already active (a key held down) wakes on its release instead,
        // as stock does.
        uint16_t held  = EXTI_WAKUPFLG & WAKE_LINES;
        EXTI_WAKUPPOLR = held;
        EXTI_WAKUPFLG  = 0xFFFF;
        EXTI_WAKUPCR   = WAKE_LINES | EXTI_WAKUPCR_EVWUPIEN;

        chSysLock(); // PRIMASK: the wake interrupt ends WFI but is never taken
        uint32_t nvic    = NVIC->ISER[0];
        uint32_t systick = SysTick->CTRL;
        NVIC->ICER[0]    = 0xFFFFFFFFU;
        SysTick->CTRL    = 0;
        SCB->ICSR        = SCB_ICSR_PENDSTCLR_Msk;
        NVIC->ICPR[0]    = 1U << EVWUP_IRQ;
        NVIC->ISER[0]    = 1U << EVWUP_IRQ;
        SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
        do {
            TEX_WDT_RELOAD();
            __DSB();
            __WFI();
        } while (!(EXTI_WAKUPFLG & WAKE_LINES));
        uint16_t woke = EXTI_WAKUPFLG & WAKE_LINES;
        SCB->SCR &= ~SCB_SCR_SLEEPDEEP_Msk;
        ht32_clock_init(); // deep sleep leaves the core on the 8 MHz HSI
        boardInit();       // HSI auto-trim for USB

        // Real: B12 (USB power) or a row still high. Not a held line going low:
        // with that also counted real, the board slept 5 times in 47 s untouched,
        // every wake on A8 and none a glitch (Mauro, 2026-11-04). Sleeping again
        // samples the held lines afresh.
        bool real = woke & ~0x1FEU;
        for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
            if ((woke & (2U << r)) && palReadLine(wake_rows[r])) real = true;
        }

        EXTI_WAKUPCR  = 0;
        EXTI_WAKUPFLG = 0xFFFF;
        NVIC->ICER[0] = 1U << EVWUP_IRQ;
        NVIC->ICPR[0] = 1U << EVWUP_IRQ;
        NVIC->ISER[0] = nvic;
        SysTick->VAL  = 0;
        SysTick->CTRL = systick;
        chSysUnlock();
        if (real) break;
    }

    matrix_init_pins();
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        palSetLineMode(wake_cols[c], PAL_MODE_INPUT_PULLUP);
    }
    bat_adc_start();
    tp_power_on();
    ble_wake();
    led_update_ports(host_keyboard_led_state());
    awake_since = timer_read32();
    slept       = true;
}

void power_init(void) {
    palSetLineMode(WAKEUP_PIN, PAL_HT32_MODE_AF(AFIO_GPIO) | PAL_HT32_MODE_INE);
    bat_adc_start();
    awake_since = timer_read32();
}

void power_task(void) {
    bat_task();
    low_battery_led_task();
    bool idle = sleep_idle_ms && on_battery() && last_input_activity_elapsed() >= sleep_idle_ms && timer_elapsed32(pointer_activity) >= sleep_idle_ms &&
                timer_elapsed32(awake_since) >= (slept ? WAKE_GRACE_MS : sleep_idle_ms);
    if (idle) power_sleep();
}

#define TYPE_SETTLE_MS 20 // per event; Fn+B types in about 4 s

// Each press and release goes out on its own (ble_flush_keys).
static void type_event(uint8_t code, bool pressed) {
    if (pressed) {
        register_code(code);
    } else {
        unregister_code(code);
    }
    ble_flush_keys(TYPE_SETTLE_MS);
}

// Types lower-case letters, digits, space, '.', '-', ':', '%' and newline: enough
// for the report below. send_string and its ASCII tables cost about 900 bytes the
// IAP's image limit doesn't have.
void type_text(const char *s) {
    for (; *s; s++) {
        char    c     = *s;
        uint8_t code  = KC_NO;
        bool    shift = false;
        if (c >= 'a' && c <= 'z') {
            code = KC_A + c - 'a';
        } else if (c >= '1' && c <= '9') {
            code = KC_1 + c - '1';
        } else if (c == '0') {
            code = KC_0;
        } else if (c == ' ') {
            code = KC_SPC;
        } else if (c == '\n') {
            code = KC_ENT;
        } else if (c == '.') {
            code = KC_DOT;
        } else if (c == '-') {
            code = KC_MINS;
        } else if (c == ':') {
            code  = KC_SCLN;
            shift = true;
        } else if (c == '%') {
            code  = KC_5;
            shift = true;
        }
        if (shift) type_event(KC_LSFT, true);
        type_event(code, true);
        type_event(code, false);
        if (shift) type_event(KC_LSFT, false);
    }
}

void type_number(uint16_t n) {
    char    buf[6];
    uint8_t i = sizeof(buf) - 1;
    buf[i]    = '\0';
    do {
        buf[--i] = '0' + n % 10;
        n /= 10;
    } while (n);
    type_text(buf + i);
}

static void type_sleep_time(void) {
    if (sleep_idle_ms % 60000) { // test keymap sleep30
        type_number(sleep_idle_ms / 1000);
        type_text(" s");
    } else if (sleep_idle_ms) {
        type_number(sleep_idle_ms / 60000);
        type_text(" min");
    } else {
        type_text("never");
    }
}

// Fn+F1..F9 type it back, as nothing else shows it; a saved choice at boot doesn't.
void power_set_sleep(uint8_t choice, bool announce) {
    sleep_idle_ms = sleep_minutes[choice] * 60000UL;
    if (!announce) return;
    type_text("sleep ");
    type_sleep_time();
}

// Fn+B: types which build is running, the battery reading, for checking the
// scale above, the sleep time and the TrackPoint level.
void battery_report(void) {
    type_text("v" TEX_FW_VERSION " " QMK_KEYMAP " " QMK_BUILDDATE "\nbat ");
    type_number(battery_percent());
    type_text("% adc ");
    type_number(battery_raw());
    type_text(on_battery() ? " on bat sleep " : " on usb sleep ");
    type_sleep_time();
    type_text(" tp ");
    type_number(tp_level + 1);
    type_text("\n");
}
