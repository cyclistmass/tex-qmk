// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
//
// PS/2 host for the TrackPoint: QMK's busywait driver plus pbuf_has_data(), so the
// stick runs in stream mode as stock runs it (init F5, E2 81 4A <v>, F4). In remote
// mode the stick acks EB polls but reports no motion (3861 polls while it moved,
// none with motion). QMK's interrupt driver needs PAL line events, which the HT32
// port lacks; stock receives with SPI0 as a slave clocked by the stick.
#include "timer.h"
#define ps2_host_send busywait_host_send
#define ps2_host_recv_response busywait_host_recv_response
#include "ps2_busywait.c"
#undef ps2_host_send
#undef ps2_host_recv_response

uint8_t ps2_host_send(uint8_t data);
uint8_t ps2_host_recv_response(void);

// ps2_host_init() without its 2.5 s wait, which froze the keyboard on every
// wake and lost the waking key: tp_power_on() times the stick's power-on reset.
void ps2_host_resume(void) {
    clock_init();
    data_init();
    inhibit();
}

// A packet's first byte, caught by pbuf_has_data(), until ps2_host_recv_response() takes it.
static int16_t pending = -1;

bool     ps2_stream_paused;
uint32_t ps2_last_packet;

uint8_t ps2_host_send(uint8_t data) {
    pending = -1; // the stick drops its stream output when the host sends
    return busywait_host_send(data);
}

uint8_t ps2_host_recv_response(void) {
    if (pending >= 0) {
        uint8_t data = pending;
        pending      = -1;
        ps2_error    = PS2_ERR_NONE;
        return data;
    }
    return busywait_host_recv_response();
}

// Once per main-loop pass in stream mode. The lines stay inhibited between passes, so
// the stick holds its packet; ps2_host_recv() releases them and waits about 0.6 ms
// for a start bit. A packet's first byte always has bit 3 set: anything else is the
// tail of a packet broken by an error, dropped so x and y do not land in the buttons.
bool pbuf_has_data(void) {
    if (ps2_stream_paused) return false;
    if (pending < 0) {
        uint8_t data = ps2_host_recv();
        if (ps2_error == PS2_ERR_NONE && (data & 0x08)) {
            pending         = data;
            ps2_last_packet = timer_read32();
        }
    }
    return pending >= 0;
}
