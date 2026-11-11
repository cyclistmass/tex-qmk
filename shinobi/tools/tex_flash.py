# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Flash the TEX Shinobi through its stock IAP, without the vendor updater.

usage: python -I tex_flash.py <image.bin> <key> [--wait SECONDS]
       python -I tex_flash.py <image.bin> <key> --dry-run <transcript.jsonl>

<image.bin> is the plain app image linked at 0x3200 (a QMK .bin, or a stock image); <key> is TEX's stock
updater AP_0407_4.04.exe or the keyboard's 52-byte key file (tex_key.py). The reports are the vendor
updater's, as recorded from it (PORT_NOTES.md, "Flashing"): erase `1D 00`, write pointer `1E 01`/`1E 00`, 52-byte blocks `1F`, checksum `1D 01`, the version
block at pointer 0, start `11 01`. The version block is read from the keyboard (`12 20`/`12 21`/`12 22`)
before the erase and written back unchanged; a valid copy is kept next to the <key> file as
tex_version_block.bin and used when the keyboard's is blank (after an interrupted flash).

Starts from either mode: in the app (04D9:0407) it sends `11 00` and waits for the IAP (04D9:1407). Stops
at the first report the IAP refuses or does not answer; the IAP itself is never erased, so a stopped flash
leaves the keyboard in the IAP, ready for another try. --dry-run builds the same reports and compares them
with a recorded vendor transcript (tex updater_trace.py output) without opening the keyboard.
Needs the keyboard on USB with the PC's Bluetooth off, and the hidapi package.
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_updater as bu  # noqa: E402
import tex_iap_probe as probe  # noqa: E402
import tex_key  # noqa: E402

BLOCK = 52  # the updater's block size; also the key length, so every block starts at key index 0
APP_PTR = 0x200  # write pointers are relative to 0x3000: the app at 0x3200, the version block at 0
ERASE_ARG = 0x1CE  # sent by the updater in the erase report at byte 9 (unaligned); meaning not decoded
VERSION_BLOCK = 180  # 3 x 60 bytes, the payloads of `12 20`, `12 21`, `12 22`
REFUSED = b"\xff\xaa"


def u32(v):
    return list(struct.pack("<I", v))


def word_sum(data):
    return sum(struct.unpack_from(f"<{len(data) // 4}I", data)) & 0xFFFFFFFF


def write_steps(ptr, data):
    """Set the pointer, read it back, then write data in 52-byte blocks; each reply names the next pointer."""
    steps = [("setptr", [0x1E, 0x01, 0, 0] + u32(ptr), ptr), ("getptr", [0x1E, 0x00, 0, 0] + u32(0xFFFFFFFF), ptr)]
    for off in range(0, len(data), BLOCK):
        chunk = data[off:off + BLOCK]
        steps.append(("block", [0x1F, len(chunk), 0, 0] + list(chunk), ptr + off + len(chunk)))
    return steps


def plan(enc, version_block):
    """Every report from the erase to the start, in order."""
    return ([("erase", [0x1D, 0x00] + [0] * 7 + u32(ERASE_ARG), None)]
            + write_steps(APP_PTR, enc)
            + [("checksum", [0x1D, 0x01, 0, 0] + u32(APP_PTR) + u32(len(enc)), word_sum(enc))]
            + write_steps(0, version_block)
            + [("start", [0x11, 0x01], None)])


def padded(payload):
    return bytes(payload) + bytes(64 - len(payload))


def dry_run(steps, transcript):
    """Compare our reports with the vendor's, from its first erase to its first start (info reads left out)."""
    sent = [bytes.fromhex(r["hex"]) for r in map(json.loads, open(transcript)) if r["dir"] == "write"]
    first = next(i for i, b in enumerate(sent) if b[:2] == b"\x1d\x00")
    last = next(i for i, b in enumerate(sent) if b[:2] == b"\x11\x01")
    vendor = [b for b in sent[first:last + 1] if b[0] != 0x12]
    ours = [padded(p) for _, p, _ in steps]
    for i, (a, b) in enumerate(zip(ours, vendor)):
        if a != b:
            sys.exit(f"report {i} ({steps[i][0]}) differs:\n  ours   {a.hex()}\n  vendor {b.hex()}")
    if len(ours) != len(vendor):
        sys.exit(f"{len(ours)} reports here, {len(vendor)} from the vendor")
    print(f"dry run: all {len(ours)} reports from erase to start match the vendor transcript byte for byte")


class Iap:
    def __init__(self):
        path = probe.vendor_path(probe.IAP)
        if path is None:
            sys.exit("no IAP update interface; run tex_iap_probe.py list")
        self.h = probe.hid.device()
        self.h.open_path(path)
        while self.h.read(64, timeout_ms=50):
            pass  # drop anything left from an earlier session

    def xfer(self, payload, timeout_ms=1000):
        self.h.write([0x00] + list(padded(payload)))
        reply = bytes(self.h.read(64, timeout_ms=timeout_ms))
        if not reply:
            raise IOError(f"no reply to {bytes(payload[:2]).hex(' ')} in {timeout_ms} ms")
        if reply[:2] == REFUSED:
            raise IOError(f"IAP refused {bytes(payload[:2]).hex(' ')}")
        if reply[0] != payload[0] and not (payload[0] == 0x1F and reply[0] == 0x1E):
            raise IOError(f"reply {reply[:8].hex(' ')} to {bytes(payload[:2]).hex(' ')}")
        return reply

    def close(self):
        self.h.close()


def valid_version_block(vb):
    return len(vb) == VERSION_BLOCK and vb[:2] == b"\x1a\x00" and vb[-4:-2] == b"\xa5\x5a"


def read_version_block(iap):
    return b"".join(iap.xfer([0x12, sub])[4:64] for sub in (0x20, 0x21, 0x22))


def run(iap, steps, image_len):
    image_blocks = -(-image_len // BLOCK)
    done, t0 = 0, time.monotonic()
    for kind, payload, expect in steps:
        if kind == "start":
            iap.h.write([0x00] + list(padded(payload)))
            return
        reply = iap.xfer(payload, timeout_ms=5000 if kind == "erase" else 1000)
        got = struct.unpack_from("<I", reply, 4)[0]
        if kind in ("getptr", "block") and got != expect:
            raise IOError(f"{kind}: IAP pointer {got:#x}, expected {expect:#x}")
        if kind == "checksum":
            if got != expect:
                raise IOError(f"checksum: IAP {got:08x}, image {expect:08x}")
            print(f"  checksum {got:08x} matches ({image_len} bytes written in {time.monotonic() - t0:.1f} s)")
        if kind == "block":
            done += 1
            if done <= image_blocks and done % 135 == 0:
                print(f"  {done}/{image_blocks} blocks")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    img, key = open(args[0], "rb").read(), tex_key.load(args[1])
    sp, reset = bu.check_image(img)
    _, enc = bu.device_image(img, key)
    print(f"{args[0]}: {len(img)} bytes, SP {sp:#x}, reset {reset:#x}, sha256 {bu.sha(img)[:12]}, sum {word_sum(enc):08x}")
    saved = os.path.join(os.path.dirname(os.path.abspath(args[1])), "tex_version_block.bin")

    if "--dry-run" in args:
        rows = [json.loads(r) for r in open(args[args.index("--dry-run") + 1])]
        blocks, cur = [], None
        for r in rows:
            b = bytes.fromhex(r["hex"]) if r["dir"] == "write" else b""
            if b[:2] == b"\x1e\x01":
                cur = []
                blocks.append(cur)
            elif b[:1] == b"\x1f":
                cur.append(b[4:4 + b[1]])
        vb = b"".join(blocks[1])  # the vendor's second write pass is the version block
        return dry_run(plan(enc, vb), args[args.index("--dry-run") + 1])

    wait = float(args[args.index("--wait") + 1]) if "--wait" in args else 15
    if probe.APP in probe.modes() and probe.vendor_path(probe.APP):
        print("keyboard is in the app; sending 11 00")
        probe.send(probe.APP, [0x11, 0x00], False)
        if probe.wait_for(probe.IAP, 20) is None:
            sys.exit("the IAP did not appear in 20 s")
    if probe.IAP not in probe.modes():
        sys.exit(f"no USB keyboard in the IAP or the app: {probe.describe(probe.modes())}")

    iap = Iap()
    try:
        info = iap.xfer([0x12, 0x00])
        if info[12:16] != bytes.fromhex("d9040714"):
            sys.exit(f"unexpected IAP info {info[:32].hex(' ')}")
        vb = read_version_block(iap)
        if valid_version_block(vb):
            if not os.path.exists(saved) or open(saved, "rb").read() != vb:
                with open(saved, "wb") as f:
                    f.write(vb)
                print(f"version block saved to {saved}")
        elif os.path.exists(saved) and valid_version_block(open(saved, "rb").read()):
            vb = open(saved, "rb").read()
            print(f"the keyboard's version block is blank; using {saved}")
        else:
            sys.exit("the keyboard's version block is blank and no saved copy exists; flash once with the "
                     "vendor updater")
        print("erasing and writing")
        steps = plan(enc, vb)
        run(iap, steps[:-1], len(enc))
        back = read_version_block(iap)
        if back != vb:
            raise IOError(f"version block reads back differently:\n  wrote {vb.hex()}\n  read  {back.hex()}")
        print("version block written and read back; starting the firmware (11 01)")
        run(iap, steps[-1:], len(enc))
    except IOError as e:
        sys.exit(f"stopped: {e}. The keyboard stays in the IAP; run this again or run TEX's updater.")
    finally:
        iap.close()

    print(f"watching USB for {wait:.0f} s")
    start, seen = time.monotonic(), None
    while time.monotonic() - start < wait:
        now = probe.modes()
        if now != seen:
            print(f"  {time.monotonic() - start:5.1f} s  {probe.describe(now)}")
            seen = now
        if probe.APP in now and probe.vendor_path(probe.APP):
            print("the app is up (04D9:0407)")
            return 0
        time.sleep(0.2)
    print("the app did not come up as 04D9:0407 in that time (expected for canary builds, which return to the IAP)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
