# Flashing from Linux, FreeBSD and OpenBSD

`tools/tex_flash.py` is the same file on every OS. It talks to the keyboard through the Python
[`hidapi`](https://pypi.org/project/hidapi/) package (module `hid`), finds the keyboard by USB vendor ID 04D9 and
the vendor usage page 0xFF00 (never by a device path), and needs read/write access to the keyboard's HID node.
That access is the only thing that differs per OS. No setuid, no sudo while flashing: root is needed once, to
install a permission rule.

| OS | Status | Backend |
|---|---|---|
| Windows | tested (v1.0 flashed with it) | hidapi's Windows HID backend |
| Linux | **not yet tested on hardware** (the tests and the argument/locale/message code ran under WSL; WSL cannot see the keyboard) | hidapi `hidraw` |
| FreeBSD | **untested** | hidapi `libusb` (FreeBSD's own libusb) |
| OpenBSD | **untested, and probably not usable yet**, see below | hidapi `libusb` |

The keyboard shows up as `04D9:0407` (firmware) and `04D9:1407` (TEX's bootloader, "IAP"). During a flash it
re-enumerates from one to the other, so the permission rule must cover both. `tex_flash.py` does the switch
itself; you do not need to hold Esc.

Turn the computer's Bluetooth off first, as in the main README, and take the firmware and a key source
(`AP_0407_4.04.exe` from TEX's site, read as data and never run, or a 52-byte key file) from the main README.

## Linux

1. Python 3 and hidapi. Either a venv:

       python3 -m venv ~/.venvs/tex && ~/.venvs/tex/bin/pip install hidapi

   or the distribution's package (Debian/Ubuntu: `sudo apt install python3-hid`; the package name differs on other
   distributions, and the module must be called `hid`). If pip has no wheel for your platform it builds hidapi
   and needs `libudev-dev`, `libusb-1.0-0-dev` and `python3-dev` (Debian names).
2. The permission rule, once, as root:

       sudo cp tools/unix/70-tex-shinobi.rules /etc/udev/rules.d/
       sudo udevadm control --reload

   Unplug and replug the keyboard. The rule tags both USB modes with `uaccess`, so the user logged in at the
   seat gets access while logged in; nobody else does, and nothing is world-writable. Check with
   `ls -l /dev/hidraw*` (an ACL `+` on the node) or `getfacl /dev/hidrawN`.
   The rule tags every hidraw node of the keyboard, including its normal typing interface, which a program of
   yours could then read as raw keystrokes. udev cannot tell the interfaces apart by usage page. If that matters
   to you, remove the rule after flashing.
3. Run, from `tools/`:

       ~/.venvs/tex/bin/python -I tex_flash.py tex_shinobi_v1.0.bin AP_0407_4.04.exe

   `-I` is Python's isolated mode (the flasher adds its own folder to the module path).
4. If it says it cannot open the keyboard, the rule is not applied: replug the keyboard, and check that you are
   at a local seat (an ssh session has no `uaccess`; use a group rule instead, e.g. `GROUP="plugdev", MODE="0660"`
   in place of `TAG+="uaccess"`, and add yourself to that group).

## FreeBSD (untested)

hidapi on FreeBSD uses libusb, which detaches the kernel's `uhid`/`hidraw` driver from the interface while the
flasher runs and gives it back afterwards. That needs write access to the USB device nodes, not to
`/dev/uhid*`.

1. `pkg install python3 hidapi libusb`, then `pip install hidapi` (in a venv, or the py-hidapi package if your
   ports tree has one). The module must be `hid`.
2. As root, once: `pw groupadd texflash && pw groupmod texflash -m YOURNAME`, log in again.
3. `tex-shinobi.devd.conf` (here) changes the group and mode of the `uhid`/`hidraw` nodes of 04D9:0407/1407:

       cp tools/unix/tex-shinobi.devd.conf /usr/local/etc/devd/tex-shinobi.conf && service devd restart

   For the libusb backend the `/dev/usb/*` nodes need the same; devfs cannot match by vendor, so
   `devfs.rules.example` opens all of `usb/*` to the group `texflash`. That is broader than the Linux rule: use it only
   if the devd rule alone gives "cannot open", and remove it afterwards.
4. Replug the keyboard and run as on Linux. If hidapi cannot find the keyboard, run
   `usbconfig list` and `python -I tex_iap_probe.py list` and open an issue with the output.

## OpenBSD (untested; no working backend known)

hidapi's OpenBSD port uses libusb, and the port's own notes say `uhid(4)`/`uhidev(4)` must be disabled in the
kernel for libusb to reach the device. A custom kernel is not a reasonable requirement, and I did not write a
native `/dev/uhid*` backend because its ioctl layout could not be checked without an OpenBSD machine to test on.
So today: flash from Windows, Linux or FreeBSD (a live USB stick is enough); the keyboard does not care which
OS flashed it.

If you want to try a `uhid` backend yourself, the permissions it would need are these. Create a group and give it
the nodes, once, as root (the nodes are static, so this survives reboots; it is reset by a `MAKEDEV` run):

    groupadd texflash
    usermod -G texflash YOURNAME      # log in again
    chgrp texflash /dev/uhid*
    chmod 660 /dev/uhid*

Which `uhidN` is the keyboard's vendor interface changes with what else is plugged in, which is why the flasher
selects by vendor ID and usage page and not by node name (the tests cover this selection for all four path
styles).

## What is and is not verified

* Verified (Windows and Linux under WSL, no hardware): argument parsing, image checks, message table
  completeness, locale choice, device selection against a fake hidapi, the dry-run comparison.
* Not verified: any run against a real keyboard on Linux, FreeBSD or OpenBSD; that the udev/devd rules apply;
  that hidapi builds on each OS as described; the FreeBSD and OpenBSD libusb behaviour.
* The translations are **unreviewed** (see below).

## Languages

Messages are in English, Traditional Chinese (zh-TW), Japanese, German, French and Spanish. Choose with
`--lang de` (also `zh-TW`, `ja`, `fr`, `es`, `en`), or let the flasher read the locale: `LC_ALL`, `LC_MESSAGES`,
`LANG` (`LANGUAGE` as a preference list), and on Windows the user's UI language. Anything else, including
Simplified Chinese, gets English. If the terminal's encoding cannot show the language (for example Japanese
written to a cp1252 pipe), the flasher says so in English and uses English.

**The translations are unreviewed**: written without a native-speaker check. Please report or fix wording
in `tools/tex_i18n.py`, the one message table. Hex dumps, report and pointer mismatches, the image summary line
and the operating system's own error texts are not translated, so that bug reports stay comparable.
argparse's own fixed words (`usage:`, `options:`, parser errors) stay English.

## Tests

No hardware needed:

    python -I -m pytest tools/tests        # or:  python -I tools/tests/test_flasher.py
