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
| Fn+1 ... Fn+9 | TrackPoint sensitivity 1-9; the keyboard types back `tp N` |
| Fn+F1 ... Fn+F9 | sleep on battery after 1, 2, 5, 10, 15, 30, 60, 120 min or never; typed back |
| Fn+B | types the firmware version, then a status line |
| Fn+arrows | media keys: Stop, Play, Previous, Next |

The keyboard "types back" by sending keystrokes, so have a text editor or other text field in focus when you
press Fn+1...9, Fn+F1...F9 or Fn+B.

### Fn+B

Fn+B types two lines, for example:

    v1.1 default 2026-11-12-22:45:00
    bat 100% adc 3383 on usb sleep 15 min tp 3 dip 24 wake 1420 ms idle 37 s

* First line: firmware version, keymap and build time.
* Second line: battery level, the raw battery reading (`adc`), power source (`on usb` or `on bat`), sleep time
  and TrackPoint level. From v1.1 also:
  * `dip`: the numbers of the DIP switches that are on (`dip 24` is switches 2 and 4), or `dip 0` for none.
  * `wake`: after the last wake from sleep, how long the Bluetooth link took to come back, in milliseconds; 0 if
    it hasn't slept since it was powered on. It counts from the end of the keyboard's own wake-up to the module
    reporting the link connected.
  * `idle`: the last stretch of at least a second with no key and no TrackPoint movement, in seconds. Leave the
    keyboard alone, then press Fn+B: it shows how long you left it. A number that stays small means something,
    such as a drifting TrackPoint, keeps it busy (and from sleeping). The clock stops in sleep, so a stretch that
    included sleep counts only its awake part.

v1.0 types the same two lines without `dip`, `wake` and `idle`.

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
| Want the stock firmware back | Run TEX's `AP_0407_4.04.exe`, with `-force` if it says there is nothing to update. |

## Known issues

* **Battery percentage isn't calibrated.** It assumes two alkaline AA cells, so NiMH rechargeables read low. A
  voltmeter reading next to the Fn+B `adc` value, for alkaline and NiMH, would fix the scale. Please send one
  if you can.
* **USB plug and unplug restart the keyboard.** The processor sees a power-on reset each time. Settings are kept.
* **TEX's configurator and macro tool don't work.** Remap keys and add shortcuts with the
  [keymap editor](https://cyclistmass.github.io/tex-qmk/shinobi/editor/) instead, then flash the image it gives
  you. From v1.1 it also makes sequence macros (a key types a short phrase or a run of keys, 96 bytes in total)
  and mouse movement keys. ([How the editor works](editor/README.md).)
* **No VIA/Vial live remapping.** TEX's bootloader takes images up to 28,076 bytes; v1.0 is 28,072 and v1.1 28,012. The keymap
  editor changes the keymap in the image, so a change takes a flash.
* **ISO and JIS boards are untested.** The extra keys are in the keymap.
* **No Bluetooth firmware updates.** Updates go over USB through TEX's bootloader.
* **Not ported:** DIP switch 6 (file system mode), and stock's Up+LAlt+Fn hold combo. That combo is a factory
  flash self-test, not a user feature: after 6 s it writes and reads back a test value and shows pass or fail on
  the Caps Lock LED. It is written but left out of the build, because it needs 312 bytes and 64 are free.
* **DIP switches 1-5 are untested on the keyboard.** Their handling follows the stock firmware's code.
* **Flashing from stock** has not been tested yet with either install method; both were tested over earlier QMK
  builds.

Report problems on the [issue tracker](https://github.com/cyclistmass/tex-qmk/issues). Include the two Fn+B
lines.
