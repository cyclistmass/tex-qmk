# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Wrap a QMK image for the TEX Shinobi into a copy of the stock updater.

usage: python -I build_updater.py <stock AP_0407_4.04.exe> <qmk.bin> <out dir>

The updater carries the app image at the tail of the exe, scrambled (decode and
encode below mirror the updater's own loader) and XORed with the keyboard's
52-byte key (recovered from the same exe by tex_key.py), which the IAP undoes on the chip. The updater compares a 32-bit
word sum of the image it sends with the IAP's `1D 01` checksum; the IAP answers
0 unless the image keeps stock's record at 0x3BF8, so images without it are
refused here (see PORT_NOTES.md, "Flashing"). The QMK image is padded with 0xFF to
the stock image's size so no size field in the container header changes, and
the version block is left as stock, so the updater needs -force (the version
string is unchanged). Nothing here talks to the keyboard; tex_flash.py flashes
without the updater.
"""
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tex_i18n import t  # noqa: E402

HDR = 0xB24
STOCK_EXE_SHA = "f14658e73b1956641b72b80eca8f873bf95db21968baf1fb79ff7cc9e39621a7"
STOCK_IMAGE_SHA = "395008231fd9851f3456095d89a3c3c3579200d94b4c25c5244e1d18689482ce"
APP_BASE = 0x3200
RAM_BASE, RAM_END = 0x20000000, 0x20004000
SLOT = 28076  # the stock image's size, which the IAP takes
# Stock's record at flash 0x3BF8 (see ld/HT32F52352_TEX_SHINOBI.ld): without it the IAP answers the
# checksum query with 0 and every flash fails.
RECORD_AT, RECORD = 0x3BF8 - APP_BASE, bytes.fromhex("005104040100003404000200")

T = [((((v - 7) & 0xFF) << 4) + (v >> 4)) & 0xFF for v in range(256)]
INV = [0] * 256
for v, tv in enumerate(T):
    INV[tv] = v


def swaps(n):
    s5 = [(5 * k, 5 * k + 4) for k in range((n - 6) // 5 + 1)] if n - 5 > 0 else []
    s2 = [(2 * k, 2 * k + 1) for k in range((n - 2) // 2 + 1)] if n - 1 > 0 else []
    return s5, s2


def decode(buf):
    b = bytearray(buf)
    s5, s2 = swaps(len(b))
    for i, j in s5:
        b[i], b[j] = b[j], b[i]
    for i, j in s2:
        b[i], b[j] = b[j], b[i]
    return bytes(T[v] for v in b)


def encode(buf):
    b = bytearray(INV[v] for v in buf)
    s5, s2 = swaps(len(b))
    for i, j in reversed(s2):
        b[i], b[j] = b[j], b[i]
    for i, j in reversed(s5):
        b[i], b[j] = b[j], b[i]
    return bytes(b)


def image_slot(exe):
    """Offset and size of image0_A inside the exe, from the decoded container header."""
    hdr = decode(exe[-HDR:])
    pos = HDR
    for idx in range(8, -1, -1):
        size_a, size_b = struct.unpack_from("<II", hdr, 0x848 + idx * 0x50)
        for tag, size in (("B", size_b), ("A", size_a)):
            if size:
                pos += size
                if (idx, tag) == (0, "A"):
                    return len(exe) - pos, size
    sys.exit("image0_A slot not found")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check_image(img, size=SLOT):
    """Exit unless img fits the slot, starts with a plausible vector table at APP_BASE and keeps the record."""
    if not 0 < len(img) <= size:
        sys.exit(t("image_size", n=len(img), max=size))
    sp, reset = struct.unpack_from("<II", img, 0)
    if not (RAM_BASE < sp <= RAM_END and sp % 4 == 0):
        sys.exit(t("image_sp", sp=f"{sp:#x}"))
    if not (reset & 1 and APP_BASE <= reset < APP_BASE + len(img)):
        sys.exit(t("image_reset", reset=f"{reset:#x}", base=f"{APP_BASE:#x}"))
    if img[RECORD_AT:RECORD_AT + len(RECORD)] != RECORD:
        sys.exit(t("image_record", at=f"{APP_BASE + RECORD_AT:#x}"))
    return sp, reset


def device_image(img, key, size=SLOT):
    """The image as the IAP takes it: padded with 0xFF to the slot, XORed with the 52-byte key."""
    padded = img + b"\xff" * (size - len(img))
    return padded, bytes(b ^ key[i % 52] for i, b in enumerate(padded))


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tex_key  # imports this module, so not at the top
    exe_path, bin_path, out_dir = sys.argv[1:4]
    exe = open(exe_path, "rb").read()
    if sha(exe) != STOCK_EXE_SHA:
        sys.exit("not the stock AP_0407_4.04.exe")
    key = tex_key.load(exe_path)
    off, size = image_slot(exe)
    stock = decode(exe[off:off + size])
    if sha(stock) != STOCK_IMAGE_SHA or encode(stock) != exe[off:off + size]:
        sys.exit("stock image slot does not round-trip")

    img = open(bin_path, "rb").read()
    sp, reset = check_image(img, size)
    padded, enc = device_image(img, key, size)
    out = bytearray(exe)
    out[off:off + size] = encode(enc)
    if decode(bytes(out[off:off + size])) != enc or out[:off] != exe[:off] or out[off + size:] != exe[off + size:]:
        sys.exit("output does not round-trip")

    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(bin_path))[0]
    paths = {
        "updater": os.path.join(out_dir, f"{stem}_updater.exe"),
        "device-encrypted image": os.path.join(out_dir, f"{stem}_device-encrypted.bin"),
        "padded image": os.path.join(out_dir, f"{stem}_padded_base3200.bin"),
    }
    for what, data in (("updater", out), ("device-encrypted image", enc), ("padded image", padded)):
        with open(paths[what], "wb") as f:
            f.write(data)
        print(f"{what}: {paths[what]}  {len(data)} bytes  sha256 {sha(data)}")
    print(f"image0_A slot at exe offset {off:#x}, {size} bytes; QMK image {len(img)} bytes, "
          f"SP {sp:#x}, reset {reset:#x}. Run the updater with -force.")


if __name__ == "__main__":
    main()
