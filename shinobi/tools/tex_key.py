# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Load the TEX Shinobi's 52-byte firmware key, from a key file or from TEX's own updater.

usage: python -I tex_key.py <AP_0407_4.04.exe> <out xor_key_52.bin>

The stock IAP undoes a 52-byte repeating XOR on every image it is sent. The key is not
stored anywhere in TEX's updater; it is recovered here from the encrypted stock image the
updater carries:
  1. Vector-table bytes 0x68..0x9B of the stock image are the same default-handler word
     (0x000032CF) thirteen times, so ciphertext XOR that word gives a first key guess.
  2. Each key byte is then refined by maximum likelihood against the byte distribution of
     Thumb code over the whole image.
The result is accepted only if its SHA-256 matches the known key's, so a wrong guess is
never used. The stock updater is the AP_0407 V1.04.04 Windows updater from TEX's site
(sha256 in build_updater.STOCK_EXE_SHA).

tex_flash.py and build_updater.py take either the key file or the updater exe wherever
they ask for the key, through load().
"""
import collections
import hashlib
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_updater as bu  # noqa: E402
from tex_i18n import t  # noqa: E402

LEN = 52
KEY_SHA = "f16ee8f89ba10701814564614693a13be0a69cd27531de6e88cf380f10922a51"
DEFAULT_HANDLER = bytes.fromhex("cf320000")  # stock's default handler, 0x32CF


def _xor(data, key):
    return bytes(b ^ key[i % LEN] for i, b in enumerate(data))


def derive(enc):
    """Best key guess for an encrypted stock image (see the module docstring)."""
    w = DEFAULT_HANDLER * (LEN // 4)
    k = bytearray(enc[0x68 + i] ^ w[i] for i in range(LEN))
    body = range(0x100, len(enc))
    for _ in range(3):
        plain = _xor(enc, k)
        ref = [collections.Counter(plain[i] for i in body if i % 2 == par) for par in (0, 1)]
        tot = [sum(r.values()) for r in ref]
        changed = False
        for j in range(LEN):
            col = [enc[i] for i in body if i % LEN == j]
            r, total = ref[j % 2], tot[j % 2]
            best = max(range(256), key=lambda c: sum(math.log((r[x ^ c] + 0.5) / (total + 128)) for x in col))
            if best != k[j]:
                k[j] = best
                changed = True
        if not changed:
            break
    return bytes(k)


def from_updater(exe):
    """The key, recovered from the bytes of TEX's stock AP_0407_4.04.exe."""
    if bu.sha(exe) != bu.STOCK_EXE_SHA:
        raise ValueError(t("key_not_stock"))
    off, size = bu.image_slot(exe)
    key = derive(bu.decode(exe[off:off + size]))
    if bu.sha(key) != KEY_SHA:
        raise ValueError(t("key_not_recovered"))
    return key


def load(path):
    """The key from a 52-byte key file or from the stock updater exe. Exits with a message on failure."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        sys.exit(t("cannot_read", path=path, err=e))
    try:
        key = data if len(data) == LEN else from_updater(data)
    except ValueError as e:
        sys.exit(t("key_load_failed", path=path, detail=e))
    if hashlib.sha256(key).hexdigest() != KEY_SHA:
        sys.exit(t("key_wrong", path=path))
    return key


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    key = load(sys.argv[1])
    with open(sys.argv[2], "wb") as f:
        f.write(key)
    print(f"key written to {sys.argv[2]} (sha256 {KEY_SHA[:12]}...)")


if __name__ == "__main__":
    main()
