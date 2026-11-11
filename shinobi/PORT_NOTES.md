# TEX Shinobi BLE5 → QMK port notes

How the port works and what it rests on. Owner-facing install notes are in [README.md](README.md).

v1.0 (2026-11-04) builds with `qmk_firmware` at [`qmk_firmware.commit`](qmk_firmware.commit), arm-none-eabi-gcc
13.2.1 and QMK CLI 1.2.0, after `tools/patch_qmk_tree.sh`. The default image is 28,072 bytes, linked at 0x3200.
Its vector table is at 0x3200, startup writes 0x3200 to VTOR before `__early_init`, the USB device is 04D9:0407,
and RAM ends at 0x20003FE0, so the IAP magic word at 0x20003FFC is never touched.

Evidence labels: **[O]** observed in the stock code or data, **[I]** inferred, otherwise unknown. All of it comes
from Ghidra and scripts over the decrypted stock app image (AP_0407 V1.04.04), plus tests on one keyboard.
Addresses like FUN_893c or 0x9DCB are in that image, base 0x3200.

## Has anyone done this?

No public QMK, Vial or other open firmware for the Shinobi turned up (GitHub, the QMK and Vial keyboard trees,
web search, 2026-10-30). Community work so far replaces TEX's online configurator for the stock `.TEX` files:
[rianmcguire/tex-shinobi-offline](https://github.com/rianmcguire/tex-shinobi-offline),
[garzoc/tex_yoda_2_configurator](https://github.com/garzoc/tex_yoda_2_configurator),
[dormema/texnologia](https://github.com/dormema/texnologia). TEX staff said on
[KeebTalk](https://www.keebtalk.com/t/tex-shinobi-7-row-mechanical-keyboard-with-trackpoint-pre-order/6479) that
they tried QMK but had problems with the TrackPoint. The closest precedent is QMK's `annepro2`: same Holtek
HT32F523x2 family, stock IAP kept, BLE module on a UART.

## Hardware map

| Item | Value | Evidence |
|---|---|---|
| MCU | Holtek HT32F52352, LQFP-64. Stock IRQs match the HT32F52342/52352 registry and the stack at 0x20003FE0 means 16 KB SRAM. TEX (2026-11-03) wrote "HT50F52352 LQFP 64PIN"; no HT50F52352 is known, so that is read as a typo for HT32F52352 | [O] IRQs/stack, TEX for package, [I] typo |
| Clock | No crystal: 8 MHz HSI → PLL ×6 = 48 MHz; 1 flash wait state; HSI auto-trim on when USB starts (`HSICR = (HSICR & ~0x30) \| 0x23`) | [O] |
| Flash map | IAP 0x0000-0x2FFF, version block 0x3000, app 0x3200 (VTOR) | [O] |
| IAP entry | 0x55AAFAF5 at 0x20003FFC, USB IRQ off, ~30 ms, reset (FUN_6528); IAP enumerates as 04D9:1407 | [O], PID seen live |
| Matrix | Rows A1-A8 (inputs), cols D2 B8 B11 D0 B13 B14 A15 A14 A10 C14 C15 B15 C0 A11 C13. Stock drives cols high and reads rows; QMK `COL2ROW` | [O] pins, [I] diode direction |
| DIP switches 1-3 | Column 14 (C13), rows 0-2; exactly one closed = profile 1-3, else 0. DIP 4-6 (Fn scroll, reverse scroll, file system) not read by QMK. Defaults: 1 Fn/Ctrl swapped, 2 Mac, 3 both | [O] FUN_8598, FUN_4948 |
| Keymap | 0x9DCB (14×8, index col×8+row); Mac swap 0x9E5A; Fn tables 0x9E62 (actions), 0x9E7C (codes) | [O] |
| Fn | Code 0xD8, placed on positions 48 and 70 by default; 70 is the TrackPoint middle button (the "weird mouse buttons" users report) | [O] positions, [I] which key |
| Codes | <0xE0 HID usages; 0xEC-0xFD = consumer bits in order (report 2: 0x183, Mail, Calc, MyComputer, Play, Stop, Prev, Next, Mute, Vol−, Vol+, AC Search/Home/Back/Fwd/Stop/Refresh/Bookmarks); 0xC8/0xCA/0xC9 = mouse left/right/middle | [O] |
| TrackPoint | PS/2 CLK B3, DATA in B4 (SPI0 slave), DATA out B5 (open drain), power C8 active low (switches `TPM_PWR` through Q2). B5 reaches `TP_DATA` through R2; stick on header J1 (1 power, 2 data, 7 GND, 8 clock), middle button via J2. Sensitivity `E2 81 4A <v>`, levels 66 73 80 8F A0 B3 C9 E1 FC. IBM TrackPoint spec v4.0: `E2 81 XX YY` writes RAM, 0x4A = sensitivity, 0x80 = 1.00× (0x00-0xFF = 0-1.99×), kept across `FF` reset and `F6`; `F0` = remote mode; POR 600 ms ±20 %; `E1` returns 01 + version byte | [O], schematic for nets, spec for semantics |
| Caps Lock LED | C10, active low | [O] |
| Other LEDs | C4 = `LOW_LED`, C5 = `PAIR_LED` (table 0x9D83). Both go to the BLE board through J3, so the LEDs sit there | [O] pins, schematic for names |
| BLE module | Nordic nRF52810-QCAA (QFN32) on a separate board on connector J3; pinout below. USART0 TX B0 → module RX, RX B1 ← module TX, 500 kbaud, DMA. Stock pulses D1 (`FROM_MCU`) in its wake routine 0x5a22; the module reset is C1, not D1 | TEX for chip, schematic for pins, [O] for USART0 use |
| Battery sense | `BAT_PWR` from the BLE board (J3.9) → R7 → A0, with R11/C8 (divider into the ADC) | schematic |
| Wake input | B12 `WAKEUP` = diode-OR of `TO_MCU` (D202) and USB power detect (D201) | schematic |
| Pair button | Matrix [5,9], stock code 0xC7 (held 3 s alone queues `E0`). J3.13 is row 5 and J3.14 `PAIR` reaches column 9 through D101, so the key is on the BLE board | schematic, [O] code, [I] button |
| SPI memory | U3, SO-8 drawn as a 25010 SPI EEPROM (part not confirmed). SCK C2, MOSI C3, MISO B6, CS B7 (`SPI_SEL`). The earlier CS A9 guess is contradicted: A9 is the BOOT pin, on R21/SEL1. Stock profiles at (profile+1)×0x1000 | schematic, [I] offsets |
| SWD | Header CN2 "Program Pin": 1 VDD33, 2 SWDIO (A13), 3 SWCLK (A12), 4 nRST, 5 GND. Stock never touches A12/A13 | schematic, [O] |

### J3, MCU ↔ BLE board (schematic)

Every signal goes through a series resistor (R42-R55); pins 15-22 are not connected. Names are from the
schematic, so `BT_RX` is the module's receive line.

| J3 | Net | MCU / other end |
|---|---|---|
| 1 | `BT_RX` | B0 (USART0 TX) |
| 2 | `BT_TX` | B1 (USART0 RX) |
| 3 | `TO_MCU` | B10, and the B12 wake line through D202 |
| 4 | `FROM_MCU` | D1 |
| 5 | `RESET_N` | C1 |
| 6 | `BT_BOOST` | Q1 → VDD33 (the BLE board powers the keyboard on battery) |
| 7 | `VDD33` | 3.3 V |
| 8 | `USB_VCC` | USB 5 V |
| 9 | `BAT_PWR` | A0 battery divider |
| 10 | `LOW_LED` | C4 |
| 11 | `PAIR_LED` | C5 |
| 12 | `VSS` | ground |
| 13 | `KB_R5` | matrix row 5 (A6) |
| 14 | `PAIR` | matrix column 9 (C14) through D101 |

Source: TEX's hot-swap schematic (OrCAD Capture, rev 1.1), which TEX shared for this port. It is TEX's
document, so it is not in this repository. Pin index = physical pin was checked three ways:
the VDD/VSS pins land on the symbol's power pins, all 15 matrix columns and 8 rows match the firmware, and so do
the TrackPoint (B3/B4/C8) and Caps Lock (C10) pins. Whether the board being ported is the hot-swap variant is
not confirmed; every pin the firmware uses matches it, except that the SPI CS guess was wrong.


### The BLE board as the host sees it (GATT, read 2026-11-03)

Read-only GATT dump of a paired keyboard (WinRT) [O]:

* Device Information: manufacturer "ChengYong Made", model "TEX-BLE", hardware "21070000", firmware "01:0",
  software "00.10". PnP ID: USB-IF vendor 04D9, product 2521, version 0. Chengyong International also wrote the
  updater (`FWUpdate`, "Chengyong International Co.,Ltd") and the app's serial starts with "CY", so one vendor
  wrote both the keyboard firmware and the module firmware.
* GAP: name "TEX-BLE-1" (the "-1" is probably the slot [I]), appearance 0x03C1 keyboard, preferred connection
  interval 7.5 ms, slave latency 79, supervision timeout 5 s.
* HID over GATT (reserved by Windows, not readable) enumerates five collections: keyboard, mouse, system control,
  consumer control and a second keyboard (NKRO [I]). Battery service, 100 % at the time.
* So the module owns its name, report map and pairing; the MCU only feeds it events, which fits the `'5'`
  key-event ring and the `'7'` mouse/consumer words of the inner frame.


## What the firmware does

* Matrix, base layer and Fn layer come straight from the stock tables. `keyboard.json` and
  `keymaps/default/keymap.c` were generated by `tools/gen_qmk.py <decrypted_base3200.bin> qmk`
  and edited by hand since. Rerunning it overwrites those edits. `LAYOUT` is in matrix order, because the
  physical key coordinates are not known.
* DIP switches 1-3 → `_FNCTL` / `_MAC` overlay layers, same defaults as stock.
* TrackPoint via QMK `ps2_mouse` in stream mode, as stock runs it, through `ps2_vendor.c` (QMK's busywait
  driver plus `pbuf_has_data()`). Remote mode does not work with this stick: it acks `EB` but never reports
  motion. `PS2_MOUSE_ROTATE 180`, because both axes came out reversed. QMK resets the stick and waits for BAT
  before configuring it, which stock skips. Middle button + stick = scroll; tapping it = middle click.
  `wait_us()` runs on the BFTM0 timer: the M0+ has no cycle counter, and QMK's fallback sleeps whole 1 ms ticks,
  which turned the PS/2 driver's 10 ms timeouts into 10-20 s stalls.
* Fn+1..9 set TrackPoint sensitivity 1-9 (stock levels). Scrolling scales with the level: one wheel notch per
  14 - level stick counts.
* A stuck TrackPoint is power-cycled (C8), as stock does, after a while without packets. Unlike stock, the stick
  stays powered during USB suspend, which avoids the stock slow-wake bug.
* Settings: the TrackPoint level and sleep time go in internal flash page 254 (0x1FC00) as one word
  `0x5E77 << 16 | sleep << 8 | tp`. They are written only when Fn+1..9 or Fn+F1..F9 changes them (page erase +
  word program through the FMC, Holtek UM v1.60 ch. 4). Page 255 holds the option bytes and is never touched.
  Erased flash fails the key, so a fresh board gets the build defaults. Every USB plug and unplug resets the MCU
  (RSTCU reports a power-on reset), so settings have to survive power cuts.
* Image budget: the IAP takes at most 28,076 bytes (the stock app's size). Several choices keep the image under
  it: LTO, no mousekey (matrix mouse buttons go through `tp_buttons`), no send_string (Fn+B has its own typer),
  one CRT0 RAM area, and the space below the record at 0x3BF8 for the vectors, unwind table, .data image and
  keymaps (see the linker script).
* Bluetooth through the BLE board (`ble.c`, `BLUETOOTH_DRIVER = custom`, see "BLE link"). QMK picks the host
  automatically: USB when enumerated, otherwise Bluetooth once the module reports a connection.
* Escape hatches in every build: HardFault and a ChibiOS halt enter the IAP instead of looping (`board.c`,
  `chconf.h`; `boards/TEX_SHINOBI/tex_hw.h` owns the IAP magic and `TEX_ENTER_IAP()`). The watchdog is reloaded
  in `__early_init` and on every kernel tick, since stock reloads it every main-loop pass. Bootmagic: hold Esc
  while plugging in.
* Updater-compatible vendor interface: raw HID on usage page 0xFF00, usage 1, 64-byte reports (the stock
  descriptor at 0x9B94). It answers the stock updater's `12 00/01/02/20-27` flash reads and `11 00/01` (IAP /
  app restart) exactly as stock does (FUN_7dd4/FUN_893c). Requests are echoed in bytes 0-3, with the payload
  from +4; anything else gets the NAK `FF AA 00 00` + request bytes 0-3, and `11` never replies. So the stock
  updater can flash QMK and flash stock back. Stock's 0x40-0x7C config commands (keymap and macro storage for
  TEX's configurator) are not implemented.

## Flashing

The stock IAP at 0x0000-0x2FFF is kept and does all erasing and writing. Neither the updater nor this
repository contains it.

* Entry: the app writes 0x55AAFAF5 to 0x20003FFC, turns the USB IRQ off, waits ~30 ms and resets (stock
  FUN_6528, `bootloader_jump()` here). The IAP enumerates as 04D9:1407. The stock updater asks the app for this
  with `11 00` on the vendor interface.
* IAP protocol (64-byte reports, recorded from the stock updater): `12 00` info (bytes 12-15 = `d9 04 07 14`),
  `12 20`/`12 21`/`12 22` read the version block, `1D 00` erase, `1E 01 <u32>` set the write pointer and
  `1E 00` read it back (pointers are relative to 0x3000: the app at 0x200, the version block at 0),
  `1F <len> <data>` write 52-byte blocks (the reply's u32 at byte 4 is the next pointer), and
  `1D 01 <start> <len>` checksum (the reply's u32 at byte 4). Then the version block is written at pointer 0,
  and `11 01` starts the app.
* The image is padded with 0xFF to 28,076 bytes and XORed with a 52-byte repeating key, which the IAP removes
  on the chip. The key is not stored in the updater; `tools/tex_key.py` recovers it from the encrypted stock
  image the updater carries and checks it against a SHA-256. The updater compares a 32-bit word sum of what it
  sent with the IAP's `1D 01` answer.
* **The record at 0x3BF8.** Stock carries a 12-byte record between two functions at flash 0x3BF8:
  `00 51 04 04 01 00 00 34 04 00 02 00`. Its first word matches bytes 0x10-0x13 of the IAP's `12 00` reply
  (version 1.04.04 [I]). Without it the IAP answers the checksum query with 0 and every flash "fails to
  checksum". The writes themselves were fine. Shown on hardware: a QMK test image with only this record patched
  in passed, and every image without it failed. The linker script splits flash so the record stays at 0x3BF8.
  Its other fields are not decoded.
* The updater stores the device-encrypted image in its own container, scrambled by a byte table and two swap
  passes (`decode`/`encode` in `tools/build_updater.py`, which mirror the updater's loader). `build_updater.py`
  replaces only the image0_A slot. The size fields and version string stay as stock, so the updater needs
  `-force`. Fed the stock image, it reproduces the stock updater byte for byte.
* `tools/tex_flash.py` speaks the same protocol directly. It reads the version block before erasing, keeps a
  copy, writes it back unchanged and reads it back. A failed step leaves the keyboard in the IAP.
* Whether the IAP erases flash page 254 (the settings) when flashing is unknown. If it does, a reflash brings
  back the defaults.

## BLE link

Decoded from the stock firmware (MCU side) and from the nRF52810 image in TEX's BLE5 updater
`521_BT_for407_0.10_20230914` (module side: container ".maaV106", header = last 0x830 bytes, the same 52-byte
XOR key). What `ble.c` relies on:

* USART0, B0 TX / B1 RX (AF6), 500 kbaud 8N1, no flow control. C1 `RESET_N`, D1 `FROM_MCU` and B10 `TO_MCU` are
  left alone: stock never drives or reads them in practice.
* Wire frame `CRC_le, ~CRC_le, (0xA800 | len)_le, inner`, CRC-16/XMODEM over the length word and the inner frame.
  Checked against the stock examples, e.g. slot 2 = `3a 63 c5 9c 04 a8 7c c0 02 00`, and by the real module
  answering.
* Inner `7C type seq n …`. MCU to module: `'1'` 32-byte config block with "TEX-BLE" (boot), `'4'` status reply,
  `'5'` up to 30 key events (`code | 0x8000` when pressed; 12-bit codes as the module maps them, FUN_0001e278:
  HID usages, 0xE0-0xE7 modifiers, 0xE9-0xEB power/sleep/wake, 0xEC-0xFD consumer keys, 0x1F0-0x1F7 mouse
  buttons 1-8; the module keeps 19 keys down, so NKRO goes through), `'6'` mouse X/Y int16 + wheel/pan int8,
  commands `0x40` wake, `C0+k` slot, `E0+k` pair. The module builds the HID reports itself.
* Stop-and-wait: the module acks with a `7C '4'` whose [2] is the seq; resend after 128 ms. Module `'4'`: [4]
  battery, [5] host LEDs (bit 1 Caps Lock), [8] link state (4 connected, 3 pairing), [9] slot. Stock answers a
  `'4'` with its own when idle; so does `ble.c`.
* The module never sends on its own; it answers frames. An MCU `'4'` echoing its last LED byte and status gets
  an answer only when they changed, so `ble.c` sends one every 250 ms when idle to see link and LED changes.
* MCU `'4'` byte [4] is the battery level the module shows the host (Battery Service 0x180F, notified on
  change). The module measures nothing itself; stock always sends 100.
* Differences from stock: mouse deltas are subtracted on ack instead of zeroed (stock loses movement); a status
  reply does not hold back the next frame for 128 ms; the real battery level is sent.


## Power

`power.c`, after stock:

* B12 `WAKEUP` (input, GPIO function) is high on USB power; low means battery.
* Battery: ADC channel 0 on A0, set up as stock FUN_340c (CK_AHB/64, 16-cycle sampling, continuous), read every
  100 ms and filtered. Below 0x834 on battery the LED does stock's low-battery pattern (3 blinks of 25 ms, 3 s
  pause), unless the module is pairing. The percentage sent to the module is not stock: the divider values
  (R7, R11) are not readable from the schematic file, so the scale assumes two alkaline AA cells and that 0x834 is
  1.10 V a cell [I]. Fn+B types the percentage and the raw reading, to check the scale against a meter.
* Sleep: on battery after 15 min without a key or TrackPoint input (stock default). USART0 stops with TX held
  high, the TrackPoint is switched off (C8 high, PS/2 lines released), the ADC stops, the columns drive high
  except C13 and the rows A1-A8 are pulled down. EXTI wake on lines 1-8 (port A) and 12 (B12); a line already
  active wakes on its release, as stock does. Deep-sleep 1 through WFI with only EVWUP enabled and PRIMASK set;
  the watchdog is set to halt in sleep. Stock sends the module nothing first, and neither does this.
* Wake: `ht32_clock_init()` (the core wakes on the 8 MHz HSI), matrix pins back, ADC, USART0 and queue `0x40`.
  The TrackPoint gets power back and, 1 s later (POR 600 ms), F5, EA, F4 and its sensitivity; until then stream
  reads pause so its BAT bytes are not read as a packet.
* Test keymap `sleep30` sleeps after 30 s.


## Can it be flashed over Bluetooth?

Stock: probably only halfway. The app accepts the vendor commands 0x11 (enter IAP) and 0x12 (info) from the BLE
module's UART link as well as USB (FUN_8000 → FUN_7dd4 → FUN_893c) [I strong]. So rebooting into the updater
wirelessly likely works. But erase and write are done by the IAP at 0x0000-0x2FFF, which is not in the update
package, and the only update path ever observed is USB (re-enumerates as 04D9:1407). Whether the IAP can take an
image through the BLE module is unknown until the SWD dump.

QMK: no. Updates go over USB through the stock IAP, or over SWD. Wireless updates would need a new bootloader.


## QMK tree patches

`tools/patch_qmk_tree.sh` changes two things in the QMK checkout:

* `RAW_EPSIZE` becomes overridable (it is a plain `#define 32` in `tmk_core/protocol/usb_descriptor.h`). The
  stock updater opens the keyboard by its 64-byte vendor reports, so `config.h` sets 64.
* ChibiOS-Contrib's `ht32f523x2.h` puts `RSTCU_BASE` at 0x40088000, but the reset unit's registers start at
  0x40088100 (HT32F52342/52352 UM v1.60, table 19; stock's peripheral-reset helper at 0x3aec agrees). Unpatched,
  `usb_lld_stop()`'s `RSTCU->AHBPRSTR = USBRST` writes 0x20 into CKCU GCCR, clearing HSIEN while the PLL runs
  from HSI. Worth fixing upstream.

## Developer test builds

Keymaps that only exist for bring-up, each a `rules.mk` flag on top of `default`:

* `canary` (`TEX_CANARY`): enters the IAP from `__early_init`, before clock setup. Proves the IAP starts the
  image. `canary_slow` spins first, to tell an IAP hand-over at 48 MHz from one at 8 MHz.
* `test90`, `test600` (`TEX_TEST_TIMEOUT_S`): full firmware that returns to the IAP after 90 s / 10 min of
  uptime, for a first flash with a guaranteed way back.
* `diag` (`TEX_DIAG`): `test600` plus read-only `13 xx` state queries on the vendor interface (matrix, ports,
  raw PS/2), read by `tools/tex_iap_probe.py`.
* `sleep30` (`TEX_SLEEP_IDLE_MS`): sleeps after 30 s on battery, until a sleep time is chosen with Fn+F1..F9.

## Open questions

* The physical key coordinates, for a proper `LAYOUT` and a configurator layout.
* Battery scale: the divider values (R7, R11) are not readable from the schematic file, so the percentage assumes
  two alkaline AA cells. It needs a meter reading against the Fn+B raw value, for alkaline and NiMH.
* The Up+LAlt+Fn hold combo in stock (0x9776, toggles a flag) is not ported.
* The record at 0x3BF8: the fields after the version word.
* Room for VIA/Vial: the 28,076-byte IAP limit leaves 4 bytes.
