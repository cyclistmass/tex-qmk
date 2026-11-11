# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Stage A recovery check for the TEX Shinobi: move between the app and the stock IAP without flashing.

usage: python -I tex_iap_probe.py list
       python -I tex_iap_probe.py info              # 12 00 to whichever mode is present (read-only)
       python -I tex_iap_probe.py enter-iap         # 11 00 to the app (04D9:0407), wait for 04D9:1407
       python -I tex_iap_probe.py leave-iap         # 11 01 to the IAP (04D9:1407), wait for 04D9:0407
       python -I tex_iap_probe.py watch [seconds]   # print every mode change, e.g. across a power cycle
       python -I tex_iap_probe.py checksum START LEN [START LEN ...]
                                                    # 1D 01 to the IAP: its checksum of flash ranges
                                                    # (START is relative to 0x3000; the app is at 0x200)
       python -I tex_iap_probe.py matrix [seconds]  # 13 00 to a diag build: print loop rate, matrix and
                                                    # port inputs whenever they change
       python -I tex_iap_probe.py regs              # 13 02/13 03 to a diag build: GPIO registers, loopback
       python -I tex_iap_probe.py pairs [seconds]   # 13 05 to a diag build: which pins a held key joins
       python -I tex_iap_probe.py pins [seconds]    # 13 06 to a diag build: every pin that changes, B1 edges
       python -I tex_iap_probe.py ps2 NRECV [BYTE ...]  # 13 08 to a diag build: raw TrackPoint transfer
       python -I tex_iap_probe.py ps2poll [seconds] # 13 08 EB polls while the stick moves; 13 09 delay timing
       python -I tex_iap_probe.py tpstats [seconds] # 13 0A to a diag build: TrackPoint motion QMK sends, per second
       python -I tex_iap_probe.py peek ADDR [ADDR ...]
                                                    # 12 01 to the v6 peek build: 60 bytes from each ADDR
       python -I tex_iap_probe.py stock-regs        # peek: GPIO A-D, AFIO and CKCU registers, as regs prints
       python -I tex_iap_probe.py stock-keys [seconds]
                                                    # peek: port inputs and stock's key bitmap while typing

The only reports this file can send are 11 00, 11 01, 12 00, 1D 01 (the updater's read-only
checksum query) and 13 00-13 0A (the diag build's state queries and raw TrackPoint transfers; 13 05 briefly drives the matrix and spare pins, 13 06 turns input buffers on while it watches) and,
to the v6 peek build, 12 01 <u32 addr> (a 60-byte memory read; use 4-aligned peripheral addresses). Erase (1D 00), set-pointer and write (1E/1F) are not in it: flashing is
tex_flash.py's job. Needs the keyboard on USB with the PC's Bluetooth off, and the hidapi package.
"""
import struct
import sys
import time

import hid

VID = 0x04D9
APP, IAP, BLE = 0x0407, 0x1407, 0x2521
NAMES = {APP: "app (04D9:0407)", IAP: "IAP (04D9:1407)", BLE: "Bluetooth (04D9:2521)"}
VENDOR_PAGE = 0xFF00
REFUSED = b"\xff\xaa"


def interfaces():
    return [d for d in hid.enumerate(VID) if d["product_id"] in NAMES]


def modes():
    return sorted({d["product_id"] for d in interfaces()})


def describe(m):
    return ", ".join(NAMES[p] for p in m) or "nothing (keyboard off, unplugged or rebooting)"


def vendor_path(pid):
    """The update interface of the given mode: usage page 0xFF00, else the mode's only interface."""
    ifs = [d for d in interfaces() if d["product_id"] == pid]
    vendor = [d for d in ifs if d["usage_page"] == VENDOR_PAGE]
    if vendor:
        return vendor[0]["path"]
    if len(ifs) == 1:
        return ifs[0]["path"]
    return None


def send(pid, payload, want_reply):
    path = vendor_path(pid)
    if path is None:
        sys.exit(f"no update interface for {NAMES[pid]}; run 'list'")
    h = hid.device()
    h.open_path(path)
    try:
        # 65 bytes on the wire: report ID 0, then the 64-byte report.
        h.write([0x00] + payload + [0x00] * (64 - len(payload)))
        return bytes(h.read(64, timeout_ms=1000)) if want_reply else None
    finally:
        h.close()


def wait_for(pid, timeout):
    start = time.monotonic()
    seen = None
    while time.monotonic() - start < timeout:
        now = modes()
        if now != seen:
            print(f"  {time.monotonic() - start:5.1f} s  {describe(now)}")
            seen = now
        if pid in now and vendor_path(pid):
            return time.monotonic() - start
        time.sleep(0.2)
    return None


def cmd_list():
    for d in interfaces():
        print(f"{NAMES[d['product_id']]:24} if={d['interface_number']:>2} usage_page={d['usage_page']:#06x} "
              f"usage={d['usage']:#04x} {d['product_string']!r}")
    print("modes present:", describe(modes()))


def cmd_info():
    m = [p for p in modes() if p in (APP, IAP)]
    if not m:
        sys.exit(f"no USB keyboard: {describe(modes())}. Turn the PC's Bluetooth off and plug the keyboard in.")
    reply = send(m[0], [0x12, 0x00], True)
    print(f"12 00 to {NAMES[m[0]]}:")
    if not reply:
        print("  no reply in 1 s")
        return
    for i in range(0, len(reply), 16):
        print(f"  {i:#04x}: " + " ".join(f"{b:02x}" for b in reply[i:i + 16]))
    if reply[:2] == b"\xff\xaa":
        print("  refused (FF AA)")


def cmd_switch(src, dst, sub):
    if src not in modes():
        sys.exit(f"needs {NAMES[src]}; present: {describe(modes())}")
    print(f"sending 11 {sub:02x} to {NAMES[src]}")
    send(src, [0x11, sub], False)
    t = wait_for(dst, 20)
    print(f"{NAMES[dst]} after {t:.1f} s" if t is not None else f"{NAMES[dst]} did not appear in 20 s")
    return 0 if t is not None else 1


def cmd_checksum(ranges):
    """The updater's verify query (0x408780): 1D 01 <u32 start> <u32 len>, answer u32 at reply byte 4."""
    if IAP not in modes():
        sys.exit(f"needs {NAMES[IAP]}; present: {describe(modes())}")
    for start, length in ranges:
        reply = send(IAP, [0x1D, 0x01] + list(struct.pack("<II", start, length)), True)
        if not reply:
            print(f"  start {start:#07x} len {length:6}: no reply in 1 s")
        elif reply[:2] == b"\xff\xaa":
            print(f"  start {start:#07x} len {length:6}: refused (FF AA)")
        else:
            print(f"  start {start:#07x} len {length:6}: {struct.unpack_from('<I', reply, 4)[0]:08x}"
                  f"  (reply {reply[:12].hex(' ')})")


def keys_of(rows):
    return " ".join(f"r{i}c{c}" for i, bits in enumerate(rows) for c in range(16) if bits >> c & 1) or "-"


def cmd_matrix(seconds):
    """Poll the diag build. 13 00: u32 loop passes, u32 uptime ms, 8 x u16 debounced matrix rows, u16 ports
    A-D. 13 01: three raw scans of 8 x u16 rows (QMK COL2ROW, stock col-high, ROW2COL). 13 04: stock's scan
    copied step for step (8 x u16), then a byte of any-key flags seen since the last 13 04."""
    path = vendor_path(APP)
    if path is None:
        sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
    h = hid.device()
    h.open_path(path)

    def query(sub):
        h.write([0x00, 0x13, sub] + [0x00] * 62)
        r = bytes(h.read(64, timeout_ms=1000))
        if not r or r[:2] == REFUSED or r[1] != sub:
            sys.exit(f"no diag reply to 13 {sub:02x} ({r[:8].hex(' ') if r else 'nothing'}); is a diag build running?")
        return r

    start, last, prev, beat = time.monotonic(), None, None, 0.0
    try:
        while time.monotonic() - start < seconds:
            r = query(0x00)
            loops, ms = struct.unpack_from("<II", r, 4)
            rows = struct.unpack_from("<8H", r, 12)
            ports = struct.unpack_from("<4H", r, 28)
            scans = [struct.unpack_from("<8H", query(0x01), 4 + 16 * i) for i in range(3)]
            now = time.monotonic() - start
            rate = f"{(loops - prev[0]) * 1000 / (ms - prev[1]):5.0f} loops/s" if prev and ms > prev[1] else ""
            r4 = query(0x04)
            exact, anykey = struct.unpack_from("<8H", r4, 4), r4[20]
            state = (rows, ports, scans, exact, anykey)
            if state != last or now - beat >= 10:
                print(f"{now:6.1f} s  up {ms / 1000:6.1f} s {rate}  A {ports[0]:04x} B {ports[1]:04x} "
                      f"C {ports[2]:04x} D {ports[3]:04x}  qmk [{keys_of(rows)}]  raw col2row [{keys_of(scans[0])}] "
                      f"stock [{keys_of(scans[1])}] row2col [{keys_of(scans[2])}] exact [{keys_of(exact)}] any {anykey}")
                last, beat = state, now
            prev = (loops, ms)
            time.sleep(0.1)
    finally:
        h.close()


def cmd_regs():
    """The diag build's 13 02 (GPIO/AFIO registers per port) and 13 03 (output loopback of the matrix pins)."""
    path = vendor_path(APP)
    if path is None:
        sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
    h = hid.device()
    h.open_path(path)
    try:
        def query(*req):
            h.write([0x00, 0x13, *req] + [0x00] * (63 - len(req)))
            r = bytes(h.read(64, timeout_ms=2000))
            if not r or r[:2] == REFUSED or r[1] != req[0]:
                sys.exit(f"no diag reply to 13 {req[0]:02x} ({r[:8].hex(' ') if r else 'nothing'})")
            return r
        names = "DIRCR INER PUR PDR ODR DRVR LOCKR DINR DOUTR CFGR0 CFGR1".split()
        for port in range(4):
            regs = struct.unpack_from("<13I", query(0x02, port), 4)
            print(f"port {'ABCD'[port]}: " + " ".join(f"{n} {v:08x}" if n.startswith("CFGR") else f"{n} {v & 0xFFFF:04x}"
                                                    for n, v in zip(names, regs)))
        print(f"CKCU AHBCCR {regs[11]:08x} APBCCR0 {regs[12]:08x}")
        loop = struct.unpack_from("<8H", query(0x03), 4)
        for port in range(4):
            print(f"loopback {'ABCD'[port]}: follows high {loop[port]:04x}, follows low {loop[4 + port]:04x}")
    finally:
        h.close()


DIAG_ALLOW = (0xCDFE, 0xEB04, 0xFEC1, 0x000D)  # shinobi.c diag_allow
ROWS = [f"A{i}" for i in range(1, 9)]
COLS = "D2 B8 B11 D0 B13 B14 A15 A14 A10 C14 C15 B15 C0 A11 C13".split()


def pin_name(v):
    name = f"{'ABCD'[v >> 4]}{v & 15}"
    tag = f"r{ROWS.index(name)}" if name in ROWS else f"c{COLS.index(name)}" if name in COLS else "?"
    return f"{name}({tag})"


def cmd_pairs(seconds):
    """13 05 to the diag build: pins pulled down (or up), each driven high (or low) in turn; every pin that moves
    is a (driven, moved) pair. A held key should show up as its column and row joined."""
    path = vendor_path(APP)
    if path is None:
        sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
    h = hid.device()
    h.open_path(path)

    def sweep(high):
        h.write([0x00, 0x13, 0x05, 1 if high else 0] + [0x00] * 61)
        r = bytes(h.read(64, timeout_ms=1000))
        if not r or r[:2] == REFUSED or r[1] != 0x05:
            sys.exit(f"no diag reply to 13 05 ({r[:8].hex(' ') if r else 'nothing'}); is the pairs build running?")
        return r[4], frozenset((r[6 + 2 * i], r[7 + 2 * i]) for i in range(r[5]))

    def idle(high):
        h.write([0x00, 0x13, 0x07, 1 if high else 0] + [0x00] * 61)
        r = bytes(h.read(64, timeout_ms=1000))
        if not r or r[:2] == REFUSED or r[1] != 0x07:
            sys.exit(f"no diag reply to 13 07 ({r[:8].hex(' ') if r else 'nothing'}); is the pairs build running?")
        return struct.unpack_from("<4H", r, 4)

    def show(total, pairs):
        return f"{total:3} " + (" ".join(f"{pin_name(a)}>{pin_name(b)}" for a, b in sorted(pairs)) or "-")

    def stuck(high, levels):
        # pulled down, a pin should idle low (pulled up, high); list the ones that do not
        bad = [pin_name(p << 4 | b) for p in range(4) for b in range(16)
               if DIAG_ALLOW[p] >> b & 1 and bool(levels[p] >> b & 1) == high]
        return " ".join(bad) or "-"

    start, last, beat = time.monotonic(), None, 0.0
    try:
        while time.monotonic() - start < seconds:
            hi, lo = sweep(True), sweep(False)
            idle_hi, idle_lo = idle(True), idle(False)
            now = time.monotonic() - start
            if (hi, lo, idle_hi, idle_lo) != last or now - beat >= 10:
                print(f"{time.strftime('%T')}  high: {show(*hi)}   low: {show(*lo)}"
                      f"   not idling low: {stuck(True, idle_hi)}   not idling high: {stuck(False, idle_lo)}", flush=True)
                last, beat = (hi, lo, idle_hi, idle_lo), now
            time.sleep(0.05)
    finally:
        h.close()


def cmd_pins(seconds):
    """13 06 to the diag build: all inputs watched 50 ms at a time with every input buffer on. Prints the pins
    that changed in each window (and the USART0 RX edges on B1) whenever that set changes, and every 10 s."""
    path = vendor_path(APP)
    if path is None:
        sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
    h = hid.device()
    h.open_path(path)
    start, last, beat = time.monotonic(), None, 0.0
    try:
        while time.monotonic() - start < seconds:
            h.write([0x00, 0x13, 0x06, 50] + [0x00] * 61)
            r = bytes(h.read(64, timeout_ms=1000))
            if not r or r[:2] == REFUSED or r[1] != 0x06:
                sys.exit(f"no diag reply to 13 06 ({r[:8].hex(' ') if r else 'nothing'}); is the pins build running?")
            first, changed, extra = (struct.unpack_from("<4H", r, 4 + 8 * i) for i in range(3))
            names = " ".join(pin_name(p << 4 | b) for p in range(4) for b in range(16) if changed[p] >> b & 1) or "-"
            state = (names, extra[0] > 0)
            now = time.monotonic() - start
            if state != last or now - beat >= 10:
                print(f"{time.strftime('%T')}  in A {first[0]:04x} B {first[1]:04x} C {first[2]:04x} D {first[3]:04x}"
                      f"  changed [{names}]  B1 edges {extra[0]}", flush=True)
                last, beat = state, now
    finally:
        h.close()


def ps2_open():
    path = vendor_path(APP)
    if path is None:
        sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
    h = hid.device()
    h.open_path(path)
    return h


def ps2_xfer(h, send, nrecv):
    """13 08: returns [(response, error)] for the sent bytes and [(byte, error)] for the received ones."""
    h.write([0x00, 0x13, 0x08, len(send), nrecv] + list(send) + [0x00] * (59 - len(send)))
    r = bytes(h.read(64, timeout_ms=3000))
    if not r or r[:2] == REFUSED or r[1] != 0x08:
        sys.exit(f"no diag reply to 13 08 ({r[:8].hex(' ') if r else 'nothing'}); is the TrackPoint diag build running?")
    pairs = [(r[4 + 2 * i], r[5 + 2 * i]) for i in range(len(send) + nrecv)]
    return pairs[:len(send)], pairs[len(send):]


def cmd_ps2(nrecv, send):
    h = ps2_open()
    try:
        sent, got = ps2_xfer(h, send, nrecv)
        print("sent " + " ".join(f"{b:02x}>{a:02x}/e{e}" for b, (a, e) in zip(send, sent))
              + "   got " + " ".join(f"{a:02x}/e{e}" for a, e in got))
    finally:
        h.close()


def cmd_ps2poll(seconds):
    """Delay timing once, the stick's status (E9) and sensitivity (E2 80 4A), then EB polls: each packet
    (buttons, x, y as signed counts) and the PS/2 error codes, with a summary every 5 s."""
    h = ps2_open()
    try:
        h.write([0x00, 0x13, 0x09] + [0x00] * 62)
        r = bytes(h.read(64, timeout_ms=5000))
        if r and r[1] == 0x09:
            a, b = struct.unpack_from("<II", r, 4)
            print(f"wait_us(1) takes {a / 10:.1f} us, wait_us(10) takes {b:.1f} us")
        print("status E9:", ps2_xfer(h, [0xE9], 3))
        print("sensitivity E2 80 4A:", ps2_xfer(h, [0xE2, 0x80, 0x4A], 1))
        start, beat = time.monotonic(), time.monotonic()
        polls = fails = moves = 0
        sx = sy = 0
        while time.monotonic() - start < seconds:
            sent, got = ps2_xfer(h, [0xEB], 3)
            polls += 1
            (ack, err), (b0, e0), (x, ex), (y, ey) = sent[0], *got
            if ack != 0xFA or err or e0 or ex or ey:
                fails += 1
                print(f"  fail: ack {ack:02x}/e{err} bytes {b0:02x}/e{e0} {x:02x}/e{ex} {y:02x}/e{ey}", flush=True)
                continue
            dx = x - 256 if b0 & 0x10 else x
            dy = y - 256 if b0 & 0x20 else y
            if dx or dy or b0 & 7:
                moves += 1
                sx += abs(dx)
                sy += abs(dy)
                print(f"  {b0:02x} {dx:+4d} {dy:+4d}" + ("" if b0 & 8 else "  (bit 3 clear: framing?)"), flush=True)
            if time.monotonic() - beat >= 5:
                print(f"{time.strftime('%T')}  {polls} polls, {fails} failed, {moves} with motion, |x| {sx} |y| {sy}",
                      flush=True)
                beat = time.monotonic()
                polls = fails = moves = sx = sy = 0
            time.sleep(0.01)
    finally:
        h.close()


def cmd_tpstats(seconds):
    """13 0A once a second: mouse reports QMK sent, their summed |x| and |y|, and main-loop passes."""
    h = ps2_open()
    try:
        start, prev = time.monotonic(), None
        while time.monotonic() - start < seconds:
            h.write([0x00, 0x13, 0x0A] + [0x00] * 62)
            r = bytes(h.read(64, timeout_ms=1000))
            if not r or r[:2] == REFUSED or r[1] != 0x0A:
                sys.exit(f"no diag reply to 13 0a ({r[:8].hex(' ') if r else 'nothing'}); is the TrackPoint diag build running?")
            now = struct.unpack_from("<4I", r, 4)
            if prev:
                d = [a - b for a, b in zip(now, prev)]
                print(f"{time.strftime('%T')}  {d[0]:4} reports/s  |x| {d[1]:5}  |y| {d[2]:5}  {d[3]:5} loops/s", flush=True)
            prev = now
            time.sleep(1)
    finally:
        h.close()


class Peek:
    """The v6 peek build: its 12 01 reads 60 bytes from the u32 at request bytes 4-7 into reply bytes 4-63
    (word reads when ADDR is 4-aligned, byte reads otherwise). An unmapped ADDR faults the firmware."""

    def __init__(self):
        path = vendor_path(APP)
        if path is None:
            sys.exit(f"needs {NAMES[APP]}; present: {describe(modes())}")
        self.h = hid.device()
        self.h.open_path(path)

    def read(self, addr):
        self.h.write([0x00, 0x12, 0x01, 0, 0] + list(struct.pack("<I", addr)) + [0x00] * 56)
        r = bytes(self.h.read(64, timeout_ms=1000))
        if len(r) < 64 or r[:2] == REFUSED:
            sys.exit(f"no peek reply for {addr:#010x} ({r[:8].hex(' ') if r else 'nothing'}); is v6 peek running?")
        return r[4:64]

    def close(self):
        self.h.close()


GPIO = [0x400B0000 + 0x2000 * n for n in range(4)]
AFIO, CKCU = 0x40022000, 0x40088000
STOCK_KEYS = 0x200002FC  # stock's key bitmap is at 0x200002FD, after 0x78 bytes of per-key history


def cmd_peek(addrs):
    p = Peek()
    try:
        for a in addrs:
            d = p.read(a)
            for i in range(0, 60, 16):
                print(f"{a + i:#010x}: " + " ".join(f"{w:08x}" for w in struct.unpack_from(f"<{min(16, 60 - i) // 4}I", d, i)))
    finally:
        p.close()


def cmd_stock_regs():
    p = Peek()
    try:
        names = "DIRCR INER PUR PDR ODR DRVR LOCKR DINR DOUTR".split()
        cfgr = struct.unpack_from("<8I", p.read(AFIO + 0x20))
        for port in range(4):
            regs = struct.unpack_from("<9I", p.read(GPIO[port]))
            print(f"port {'ABCD'[port]}: " + " ".join(f"{n} {v & 0xFFFF:04x}" for n, v in zip(names, regs))
                  + f" CFGR0 {cfgr[2 * port]:08x} CFGR1 {cfgr[2 * port + 1]:08x}")
        ck = struct.unpack_from("<15I", p.read(CKCU))
        print(f"CKCU AHBCCR {ck[9]:08x} APBCCR0 {ck[11]:08x} APBCCR1 {ck[12]:08x}")
        print(f"AFIO ESSR0 {struct.unpack_from('<I', p.read(AFIO))[0]:08x}")
    finally:
        p.close()


def cmd_stock_keys(seconds):
    """Port inputs (DINR) and the first 16 bytes of stock's key bitmap (FF = released), whenever they change."""
    p = Peek()
    start, last, beat = time.monotonic(), None, 0.0
    try:
        while time.monotonic() - start < seconds:
            dinr = [struct.unpack_from("<I", p.read(g + 0x1C))[0] & 0xFFFF for g in GPIO]
            keys = p.read(STOCK_KEYS)[1:17]
            now = time.monotonic() - start
            if (dinr, keys) != last or now - beat >= 10:
                print(f"{time.strftime('%T')}  in A {dinr[0]:04x} B {dinr[1]:04x} C {dinr[2]:04x} D {dinr[3]:04x}"
                      f"  keys {keys.hex(' ')}", flush=True)
                last, beat = (dinr, keys), now
            time.sleep(0.02)
    finally:
        p.close()


def cmd_watch(seconds):
    print(f"watching for {seconds} s; power-cycle the keyboard now")
    start, seen = time.monotonic(), None
    while time.monotonic() - start < seconds:
        now = modes()
        if now != seen:
            print(f"  {time.monotonic() - start:5.1f} s  {describe(now)}")
            seen = now
        time.sleep(0.2)


def main():
    args = sys.argv[1:] or ["list"]
    if args[0] == "list":
        cmd_list()
    elif args[0] == "info":
        cmd_info()
    elif args[0] == "enter-iap":
        return cmd_switch(APP, IAP, 0x00)
    elif args[0] == "leave-iap":
        return cmd_switch(IAP, APP, 0x01)
    elif args[0] == "ps2" and len(args) >= 2:
        cmd_ps2(int(args[1], 0), [int(a, 16) for a in args[2:]])
    elif args[0] == "tpstats":
        cmd_tpstats(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "ps2poll":
        cmd_ps2poll(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "peek" and len(args) >= 2:
        cmd_peek([int(a, 0) for a in args[1:]])
    elif args[0] == "stock-regs":
        cmd_stock_regs()
    elif args[0] == "stock-keys":
        cmd_stock_keys(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "regs":
        cmd_regs()
    elif args[0] == "pins":
        cmd_pins(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "pairs":
        cmd_pairs(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "matrix":
        cmd_matrix(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "watch":
        cmd_watch(float(args[1]) if len(args) > 1 else 60)
    elif args[0] == "checksum" and len(args) >= 3 and len(args) % 2 == 1:
        nums = [int(a, 0) for a in args[1:]]
        cmd_checksum(list(zip(nums[::2], nums[1::2])))
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
