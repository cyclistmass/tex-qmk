# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the keyboard's flash self-test over USB and print PASS or FAIL.

usage: python -I tex_selftest.py

Sends `14 00` to the running firmware (04D9:0407) on the update interface, the way tex_iap_probe.py sends its
queries. The firmware writes a test value to the page that holds its settings, reads it back from the flash
array (cache and pre-fetch off), and writes the settings back, as stock's factory test does (FUN_4810). The
reply's byte 4 is 1 for a pass, 0 for a failure. Only firmware built with TEX_SELFTEST answers it; the
released v1.1 doesn't have the room, and answers with the stock refusal (FF AA).

Exit status: 0 pass, 1 fail, 2 no answer, a refusal or an unexpected reply.
Needs the keyboard on USB with the PC's Bluetooth off, and the hidapi package.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REQUEST = [0x14, 0x00, 0x00, 0x00]
PASS, FAIL, ERROR = 0, 1, 2


def verdict(reply):
    """(exit status, message) for the firmware's reply to 14 00."""
    if not reply:
        return ERROR, "no answer from the keyboard"
    if reply[:2] == b"\xff\xaa":
        return ERROR, "this firmware has no self-test (build it with TEX_SELFTEST)"
    if reply[:4] != bytes(REQUEST) or len(reply) < 5 or reply[4] not in (0, 1):
        return ERROR, "unexpected reply " + reply[:8].hex(" ")
    if reply[4] == 1:
        return PASS, "PASS: the settings page took the test value and read it back; settings restored"
    return FAIL, "FAIL: the settings page read back something else than the test value"


def main(argv):
    if len(argv) > 1:
        sys.exit(__doc__)
    import tex_iap_probe as probe  # needs hidapi; imported here so verdict() can be tested without it

    if probe.APP not in probe.modes():
        print(f"the keyboard's firmware isn't on USB: found {probe.describe(probe.modes())}")
        return ERROR
    status, message = verdict(probe.send(probe.APP, REQUEST, True))
    print(message)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
