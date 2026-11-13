# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Flash the TEX Shinobi through its stock IAP, without the vendor updater.

usage: python -I tex_flash.py <image.bin> <key> [--wait SECONDS] [--lang LANG]
       python -I tex_flash.py <image.bin> <key> --dry-run <transcript.jsonl>

Runs unchanged on Windows, Linux, FreeBSD and OpenBSD (Linux and the BSDs need a permission rule, see
unix/README.md). Messages are in English, Traditional Chinese, Japanese, German, French or Spanish (--lang, else
the system locale; tex_i18n.py); hex dumps and mismatch details stay English for bug reports.

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
import argparse
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_updater as bu  # noqa: E402
import tex_i18n  # noqa: E402
import tex_iap_probe as probe  # noqa: E402
import tex_key  # noqa: E402
from tex_i18n import t  # noqa: E402

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


def dry_run(steps, rows):
    """Compare our reports with the vendor's, from its first erase to its first start (info reads left out).
    rows are the transcript's records (tex updater_trace.py output, one JSON object per line)."""
    sent = [bytes.fromhex(r["hex"]) for r in rows if r["dir"] == "write"]
    first = next(i for i, b in enumerate(sent) if b[:2] == b"\x1d\x00")
    last = next(i for i, b in enumerate(sent) if b[:2] == b"\x11\x01")
    vendor = [b for b in sent[first:last + 1] if b[0] != 0x12]
    ours = [padded(p) for _, p, _ in steps]
    for i, (a, b) in enumerate(zip(ours, vendor)):
        if a != b:
            sys.exit(f"report {i} ({steps[i][0]}) differs:\n  ours   {a.hex()}\n  vendor {b.hex()}")
    if len(ours) != len(vendor):
        sys.exit(f"{len(ours)} reports here, {len(vendor)} from the vendor")
    print(t("dry_ok", n=len(ours)))


class Iap:
    def __init__(self):
        path = probe.vendor_path(probe.IAP)
        if path is None:
            sys.exit(t("no_iap_iface"))
        self.h = probe.open_device(path)
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
            print(t("checksum_ok", sum=f"{got:08x}", n=image_len, s=f"{time.monotonic() - t0:.1f}"))
        if kind == "block":
            done += 1
            if done <= image_blocks and done % 135 == 0:
                print(t("blocks", done=done, total=image_blocks))


def lang_arg(value):
    lang = tex_i18n.normalize(value)
    if lang is None:
        raise argparse.ArgumentTypeError(f"{value!r}: use one of {', '.join(tex_i18n.LANGS)}")
    return lang


def parse_args(argv):
    """Parse the command line; the language (--lang, else the locale) is chosen first so --help is in it."""
    pre = argparse.ArgumentParser(prog="tex_flash.py", add_help=False)
    pre.add_argument("--lang", type=lang_arg)
    known, _ = pre.parse_known_args(argv)
    tex_i18n.setup(known.lang)
    ap = argparse.ArgumentParser(prog="tex_flash.py", description=t("help_desc"))
    ap.add_argument("image", help=t("help_image"))
    ap.add_argument("key", help=t("help_key"))
    ap.add_argument("--wait", type=float, default=15, metavar="SECONDS", help=t("help_wait"))
    ap.add_argument("--dry-run", metavar="TRANSCRIPT", help=t("help_dry"))
    ap.add_argument("--lang", type=lang_arg, metavar="LANG", help=t("help_lang"))
    return ap.parse_args(argv)


def read_file(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        sys.exit(t("cannot_read", path=path, err=e))


def read_transcript(path):
    return [json.loads(r) for r in read_file(path).decode("utf-8").splitlines() if r.strip()]


def save_version_block(path, vb):
    try:
        with open(path, "wb") as f:
            f.write(vb)
        print(t("vb_saved", path=path))
    except OSError as e:
        print(t("vb_save_failed", path=path, err=e))


def vendor_version_block(rows):
    """The version block the vendor wrote: its second write pass in the transcript."""
    blocks, cur = [], None
    for r in rows:
        b = bytes.fromhex(r["hex"]) if r["dir"] == "write" else b""
        if b[:2] == b"\x1e\x01":
            cur = []
            blocks.append(cur)
        elif b[:1] == b"\x1f":
            cur.append(b[4:4 + b[1]])
    return b"".join(blocks[1])


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    img = read_file(args.image)
    key = tex_key.load(args.key)
    sp, reset = bu.check_image(img)
    _, enc = bu.device_image(img, key)
    print(f"{args.image}: {len(img)} bytes, SP {sp:#x}, reset {reset:#x}, sha256 {bu.sha(img)[:12]}, sum {word_sum(enc):08x}")
    saved = os.path.join(os.path.dirname(os.path.abspath(args.key)), "tex_version_block.bin")

    if args.dry_run:
        rows = read_transcript(args.dry_run)
        return dry_run(plan(enc, vendor_version_block(rows)), rows)

    wait = args.wait
    if probe.APP in probe.modes() and probe.vendor_path(probe.APP):
        print(t("in_app"))
        probe.send(probe.APP, [0x11, 0x00], False)
        if probe.wait_for(probe.IAP, 20) is None:
            sys.exit(t("iap_timeout", s=20))
    if probe.IAP not in probe.modes():
        sys.exit(t("no_keyboard", modes=probe.describe(probe.modes())))

    iap = Iap()
    try:
        info = iap.xfer([0x12, 0x00])
        if info[12:16] != bytes.fromhex("d9040714"):
            sys.exit(f"unexpected IAP info {info[:32].hex(' ')}")
        vb = read_version_block(iap)
        if valid_version_block(vb):
            if not os.path.exists(saved) or read_file(saved) != vb:
                save_version_block(saved, vb)
        elif os.path.exists(saved) and valid_version_block(read_file(saved)):
            vb = read_file(saved)
            print(t("vb_blank_saved", path=saved))
        else:
            sys.exit(t("vb_blank_none"))
        print(t("erasing"))
        steps = plan(enc, vb)
        run(iap, steps[:-1], len(enc))
        back = read_version_block(iap)
        if back != vb:
            raise IOError(f"version block reads back differently:\n  wrote {vb.hex()}\n  read  {back.hex()}")
        print(t("starting"))
        run(iap, steps[-1:], len(enc))
    except IOError as e:
        sys.exit(t("stopped", detail=e))
    finally:
        iap.close()

    print(t("watching", s=f"{wait:.0f}"))
    start, seen = time.monotonic(), None
    while time.monotonic() - start < wait:
        now = probe.modes()
        if now != seen:
            print(f"  {time.monotonic() - start:5.1f} s  {probe.describe(now)}")
            seen = now
        if probe.APP in now and probe.vendor_path(probe.APP):
            print(t("app_up"))
            return 0
        time.sleep(0.2)
    print(t("app_not_up"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
