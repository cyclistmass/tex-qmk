# TEX Shinobi

7-row ThinkPad-style keyboard with a PS/2 TrackPoint. Unofficial QMK port, v1.0: in daily use on one board over USB and Bluetooth.

* Keyboard maintainer: [cyclistmass](https://github.com/cyclistmass)
* Hardware: Holtek HT32F52352 Cortex-M0+ (LQFP-64), crystal-less USB, PS/2 TrackPoint, nRF52810 BLE module on connector J3
* Stock firmware analysed: AP_0407 V1.04.04

Make example for this keyboard (after setting up your build environment):

    qmk compile -kb tex/shinobi -km default

The QMK checkout needs `shinobi/tools/patch_qmk_tree.sh` once: it makes the raw HID reports 64 bytes, as the updater
expects, and fixes ChibiOS-Contrib's RSTCU base address for this chip.

Flashing: `shinobi/tools/tex_flash.py <image.bin> <AP_0407_4.04.exe>` through the stock IAP, or the stock updater
(`shinobi/tools/build_updater.py` wraps the image into a copy of it). See `README.md` and `PORT_NOTES.md` in the `shinobi` folder of the repository.

## Fn keys

* **Fn+Mute / Fn+Vol- / Fn+Vol+**: Bluetooth host 1-3; hold 3 s to pair
* **Fn+Esc**: back to USB
* **Fn+1..9**: TrackPoint sensitivity, typed back as "tp N"
* **Fn+F1..F9**: sleep on battery after 1, 2, 5, 10, 15, 30, 60, 120 min or never, typed back (default 15 min)
* **Fn+B**: types the firmware version, battery level, power source, sleep time and TrackPoint level

The sensitivity and sleep time are kept in flash, so they survive a power cut (every USB plug and unplug is one).

## Bootloader

The stock IAP at 0x0000-0x2FFF is kept. Enter it by:

* **Bootmagic**: hold Esc while plugging in the keyboard
* **Keycode**: `QK_BOOT` (not in the default keymap)
* **Stock updater**: its `11 00` command on the vendor interface (usage page 0xFF00), which this firmware answers
  like stock

Either way the keyboard re-enumerates as the stock IAP, USB 04D9:1407. A HardFault or a ChibiOS halt also
lands there, so a crash doesn't take the updater path away.

The other keymaps are developer test builds (PORT_NOTES.md, "Developer test builds"); flash `default`.
