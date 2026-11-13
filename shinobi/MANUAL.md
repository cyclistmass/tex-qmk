# TEX Shinobi BLE5 with QMK: owner's manual

For the QMK firmware v1.0 and v1.1 from this repository. To install it, see [README.md](README.md#installing).

## At a glance

| You want to | Do this |
|---|---|
| Use it over USB | Plug in the cable. Fn+Esc switches back to USB from Bluetooth. |
| Use it over Bluetooth | Fn+Mute, Fn+Vol- or Fn+Vol+ picks host 1, 2 or 3. |
| Pair a new computer | Hold Fn+Mute (or Vol-, Vol+) for 3 s, then pick "TEX-BLE" on the computer. |
| Change TrackPoint speed | Fn+1 (slowest) ... Fn+9 (fastest). Default 3. |
| Change the sleep time on battery | Fn+F1 ... Fn+F9. Default 15 min. |
| Check battery and settings | Fn+B, in a text editor. |
| Scroll with the TrackPoint | Hold the middle button and push the stick. Tap it for a middle click. |

## Keys

The layout is the stock Shinobi layout, read from TEX's own firmware tables.

### The DIP switches

The DIP switch block on the bottom of the keyboard is read as on stock firmware (without a TEX profile file),
for switches 1 to 5. Turn on at most one of switches 1 to 3:

| Switch on | Does |
|---|---|
| 1 | Fn and left Ctrl swapped |
| 2 | Mac layout: left Alt and left Win swapped, right Alt and right Win swapped, App becomes right Alt |
| 3 | both 1 and 2 |
| none, or more than one of 1-3 | stock layout |

Switches 4 and 5 work from v1.1 (v1.0 ignores them):

* **4 on:** hold Fn and push the TrackPoint to scroll; tapping Fn on its own is a middle click. Fn together with
  another key doesn't click. The middle button scrolls with the switch on or off.
* **5 on:** vertical scrolling is reversed.
* **6 (file system mode for TEX's configurator):** not available, because the configurator doesn't work with
  this firmware.
* **7 and 8:** stock doesn't use them. Switch n is read from matrix column 14, row n-1; stock reads switch 6 there
  but never rows 6 and 7, so it is not known whether 7 and 8 are wired to them. Fn+B's `dip` shows what the
  keyboard reads (from v1.1): if 7 or 8 never shows up when on, it isn't wired there.

The DIP switches are separate from the Fn keys: Fn+F1...F9 set the sleep time whatever the switches say.

### Fn combinations

| Keys | Does |
|---|---|
| Fn+Mute / Fn+Vol- / Fn+Vol+ | Bluetooth host 1 / 2 / 3. Hold 3 s to pair a new host to that slot |
| Fn+Esc | back to USB |
| Fn+1 ... Fn+9 | TrackPoint sensitivity 1-9; types back `tp3` and so on |
| Fn+F1 ... Fn+F9 | sleep on battery after 1, 2, 5, 10, 15, 30, 60, 120 min or never; types back `zzz15m` and so on |
| Fn+B | types the firmware version, then a status line |
| Fn+arrows | media keys: Stop, Play, Previous, Next |

The keyboard "types back" by sending keystrokes, so have a text editor or other text field in focus when you
press Fn+1...9, Fn+F1...F9 or Fn+B. The answers are short; the tables below translate them. They are typed as on
a US keyboard layout: with another layout on the computer some characters come out as that layout's, for example
`y` and `z` swapped on German, or punctuation in place of digits on French.

### What the keyboard types

**Fn+1 ... Fn+9** types `tp1` ... `tp9`: the TrackPoint sensitivity now set, 1 slowest, 9 fastest, 3 by default.

**Fn+F1 ... Fn+F9** types `zzz` and the sleep time now set (`m` is minutes):

| Keys | Types | Sleeps on battery after |
|---|---|---|
| Fn+F1 | `zzz1m` | 1 minute without input |
| Fn+F2 | `zzz2m` | 2 minutes |
| Fn+F3 | `zzz5m` | 5 minutes |
| Fn+F4 | `zzz10m` | 10 minutes |
| Fn+F5 | `zzz15m` | 15 minutes (the default) |
| Fn+F6 | `zzz30m` | 30 minutes |
| Fn+F7 | `zzz60m` | an hour |
| Fn+F8 | `zzz120m` | two hours |
| Fn+F9 | `zzz never` | never |

**Fn+B** types two lines, for example:

    v1.1 default 2026-11-13-08:17:00
    bat85% adc2900 aa zzz15m tp3 dip24 idl15m34s wk1420ms

One space separates the fields; within a field the label and value run together.

| Typed | Means | Useful for |
|---|---|---|
| `v1.1 default 2026-11-13-08:17:00` | Firmware version, keymap name and build time. An image made with the keymap editor also says `default`. | Knowing which firmware is on the keyboard. Quote it in bug reports. |
| `bat85%` | Battery level, worked out from `adc` for two alkaline AA cells. | Knowing when to change the cells. NiMH rechargeables read low (see [Known issues](#known-issues)). |
| `adc2900` | The raw battery reading the level comes from. | Calibrating the battery scale: a voltmeter reading across the cells, sent with this number, fixes it. |
| `aa` / `usb` | Running on the AA cells, or on USB power. | On USB power the keyboard never sleeps. |
| `zzz15m` | Sleep time on battery, as set with Fn+F1...F9 (`zzz never` if it never sleeps). | Checking the setting, which survives battery changes and power cuts. |
| `tp3` | TrackPoint sensitivity, as set with Fn+1...9. | Checking the setting, which is saved the same way. |
| `dip24` | The DIP switches that are on: here switches 2 and 4. `dip0` means none. | Checking a switch is read after you flip it. If 7 or 8 never shows up when on, it isn't wired (see [The DIP switches](#the-dip-switches)). |
| `idl15m34s` | The last stretch of at least a second with no key and no TrackPoint movement: 15 minutes 34 seconds here, `idl37s` under a minute. Sleep doesn't count: a stretch that included sleep counts only its awake part. | Leave the keyboard alone for a while, then press Fn+B: it should show about how long you left it. If `idl` stays small and the keyboard never sleeps on battery, something keeps it busy, most likely a drifting TrackPoint. |
| `wk1420ms` | After the last wake from sleep, the milliseconds from the keyboard waking up to the Bluetooth link being back. `wk0ms` if it hasn't slept since it was powered on. | Telling where wake time goes. A large `wk` is Bluetooth reconnecting; if waking feels slow but `wk` is small, the delay is elsewhere (the keyboard's own wake-up, or the computer). |

v1.0 types `bat 85% adc 2900 on bat sleep 15 min tp 3`, and `sleep 15 min` and `tp 3` for Fn+F1...F9 and
Fn+1...9, with no `dip`, `idl` or `wk`.

## Bluetooth

The keyboard remembers three hosts, one per slot.

* **Pair:** hold Fn+Mute (slot 1), Fn+Vol- (slot 2) or Fn+Vol+ (slot 3) for 3 seconds. The pairing light blinks.
  On the computer, add a Bluetooth device and pick the keyboard: it shows as "TEX-BLE-" and a number. Pairing a slot again replaces the host it
  had.
* **Switch:** tap Fn+Mute, Fn+Vol- or Fn+Vol+. The keyboard reconnects to that slot's host.
* **Back to USB:** Fn+Esc, with the cable plugged in.

Bluetooth uses the keyboard's own Bluetooth module, which keeps its pairings across firmware changes.

## Power, battery and sleep

The keyboard runs on two AA cells, or on USB power when the cable is in.

* **Sleep:** on battery, the keyboard sleeps after the idle time set with Fn+F1...F9 (default 15 minutes). No
  key or TrackPoint use counts as idle. On USB power it never sleeps.
* **Wake:** press any key. Bluetooth reconnects within a few
  seconds.
* **Low battery:** the Caps Lock light blinks three times every 3 seconds. Replace the cells.
* **Battery level:** sent to the computer over Bluetooth and typed by Fn+B. It assumes alkaline cells; see
  [Known issues](#known-issues).
* **USB plug and unplug restart the keyboard.** This is normal on this hardware. Settings are kept.

## Settings that are saved

The TrackPoint level and the sleep time are saved in the keyboard's flash when you change them. They survive
battery changes, USB plugging and unplugging, and power cuts.

## Troubleshooting

| Problem | Try |
|---|---|
| Nothing types over Bluetooth | Press a key to wake it, wait a few seconds. Tap the slot's Fn key (Fn+Mute, Vol-, Vol+). Check the computer still lists the keyboard as paired; if not, pair the slot again. |
| It types on the wrong computer | Tap the Fn slot key for the computer you want, or Fn+Esc for USB. |
| TrackPoint doesn't move | Wait a few seconds: the keyboard restarts a stuck TrackPoint by itself. Unplugging and replugging USB restarts the whole keyboard. |
| TrackPoint too fast or slow | Fn+1 ... Fn+9. |
| Middle button scrolls when you want a click | Tap it without moving the stick. |
| Keys are swapped (Fn/Ctrl, Alt/Win) | Check DIP switches 1-3 on the bottom; turn them all off for the stock layout. |
| Battery percentage looks low | With NiMH rechargeables it reads low; see [Known issues](#known-issues). |
| Flashing can't find the keyboard | Turn the PC's Bluetooth off. Or hold Esc while plugging in the USB cable: the keyboard starts in the bootloader, ready to flash. |
| Settings (TrackPoint level, sleep time) aren't kept | With a firmware built with `TEX_SELFTEST`, run `python -I tools/tex_selftest.py` with the keyboard on USB: it tests the flash page that holds them and prints PASS or FAIL. The released v1.1 doesn't include the test, and the script says so. |
| Want the stock firmware back | Run TEX's `AP_0407_4.04.exe`, with `-force` if it says there is nothing to update. |

## Known issues

* **Battery percentage isn't calibrated.** It assumes two alkaline AA cells, so NiMH rechargeables read low. A
  voltmeter reading next to the Fn+B `adc` value, for alkaline and NiMH, would fix the scale. Please send one
  if you can.
* **USB plug and unplug restart the keyboard.** The processor sees a power-on reset each time. Settings are kept.
* **TEX's configurator and macro tool don't work.** Remap keys and add shortcuts with the
  [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/) instead, then flash the image it gives
  you. From v1.1 it also makes sequence macros (a key types a short phrase or a run of keys, 96 bytes in total)
  and mouse movement keys. Macros are typed for the keyboard layout you choose for the computer (US, UK, German,
  French, Spanish, Nordic or Japanese); Fn+B's answers stay US. ([How the editor works](editor/README.md).)
* **No VIA/Vial live remapping.** TEX's bootloader takes images up to 28,076 bytes; v1.0 is 28,072 and v1.1 27,740. The keymap
  editor changes the keymap in the image, so a change takes a flash.
* **ISO and JIS boards are untested.** The extra keys are in the keymap.
* **No Bluetooth firmware updates.** Updates go over USB through TEX's bootloader.
* **Not ported:** DIP switch 6 (file system mode), and stock's Up+LAlt+Fn hold combo. That combo is a factory
  flash self-test, not a user feature: it writes and reads back a test value where the settings live. This
  firmware has it as a USB command instead, run by `tools/tex_selftest.py`, but only in builds with
  `TEX_SELFTEST` (88 bytes); the released v1.1 leaves it out.
* **DIP switches 1-5 are untested on the keyboard.** Their handling follows the stock firmware's code.
* **Flashing from stock** has not been tested yet with either install method; both were tested over earlier QMK
  builds.

Report problems on the [issue tracker](https://github.com/cyclistmass/tex-qmk/issues). Include the two Fn+B
lines.
