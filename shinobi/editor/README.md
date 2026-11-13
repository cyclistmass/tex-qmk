# Keymap editor

A static web page that remaps the Shinobi's keys without a compiler. It writes your keymap into a released image,
`tex_shinobi_v1.0.bin` or `tex_shinobi_v1.1.bin`, and only into the 960 keymap bytes at 0x3800 and, for v1.1, the
96-byte macro table at 0x37A0. It also exports the same keymap as `keymap.c` for people who build the firmware
themselves. Why it works this way is in [DESIGN.md](DESIGN.md).

## Using it

1. Open the page: <https://cyclistmass.github.io/tex-qmk/shinobi/editor/>, or `index.html` from a checkout,
   straight from disk or served with `python -I -m http.server 8765 --bind 127.0.0.1`.
2. Download the release image from the release page and load it with **Choose the .bin file**. The page knows each
   release by its SHA-256, checks the default keymap (and the empty macro table), and refuses any other image.
3. Choose the computer's keyboard layout, so the keys show what they type there. Pick a layer (Base, Mac, Fn-Ctrl
   swap, Fn), click a key, and pick what it should do. Tick Ctrl, Shift, Alt or Win
   for a shortcut such as Ctrl+C.
4. v1.1 only: write sequence macros in **Macros** and assign Macro 0-15 to keys; put mouse movement keys on
   keys in step 3 or with the Fn + U I O / J K L / M , preset in **Mouse keys**.
5. **Download firmware** saves `tex_shinobi_v1.x_custom.bin`. Flash it like a release:

       python -I tools/tex_flash.py tex_shinobi_v1.1_custom.bin AP_0407_4.04.exe

   or wrap it into TEX's updater with `tools/build_updater.py`.
6. **Save keymap.json** keeps your keymap and macros so you can load it again later. **Download keymap.c** gives the C source.

Known limits:

* Fn+B still reports the keymap name as `default` in a patched image, because the name is compiled into the code.
* The drawn layout is approximate and has not been checked against the board.
* Sequence macros need v1.1. They are typed for the computer's keyboard layout chosen in step 2 (US, UK, German,
  French, Spanish, Nordic or Japanese JIS, as Windows lays them out; macOS's differ), with no delays, and all of
  them share 96 bytes: each key takes 1 byte, a key with Shift or AltGr (right Alt) or a shortcut 2, Shift+AltGr 3,
  an accent from a dead key one more, and each macro up to the last one used 1 more. keymap.json records the
  layout. The layouts were written from Windows' and have not been typed on a real computer with each one.
* Fn+B and the keyboard's other typed answers always type as on a US layout.
* The page is in English, Traditional Chinese, Japanese, German, French and Spanish: it opens in the browser's
  language when it has it, else English, and the menu at the top changes it. The translations are machine-made and
  not yet reviewed, and the page says so. Macro key names such as `{Enter}` stay English in every language.

## Files

* `index.html`: the page.
* `editor_core.js`: keycodes, encoding, the image check, patching and export. The page and the tests both use it.
* `i18n.js`: the page's strings, one table per language; `test/i18n.cjs` checks every table has every string with
  the same placeholders.
* `shinobi_data.js`: generated facts (layout, keycode values, and per release the default keymap, board keycodes,
  macro table, SHA-256 and build date). Regenerate it from the pinned QMK tree and every release image, oldest
  first:

      python -I ../tools/gen_editor_data.py <qmk_firmware dir> \
          shinobi-v1.0 tex_shinobi_v1.0.bin 2026-11-04-12:22:53 \
          shinobi-v1.1 tex_shinobi_v1.1.bin 2026-11-13-08:17:00

  Each release's sources are read at its git tag; one with no tag yet is read from the working tree. The date is
  the release's build date, which Fn+B prints and which a rebuild needs to match the image. A release that isn't
  tagged yet must be published with exactly the image named here: build it with
  `test/build_wsl.sh <qmk dir> ../qmk/keymaps/default/keymap.c <date> tex_shinobi_v1.x.bin`.

## Testing

`test/byte_identity.sh <release .bin> <out dir> <qmk_firmware dir>` is the acceptance test, run from the release's
own sources. It needs node,
the QMK CLI and the ARM toolchain (in WSL on Windows). It:

* checks the editor core: keycode round trips, and that a changed code byte, a changed keymap or macro byte, a short
  image and a changed bootloader record are all refused; for v1.1, macro text round trips and limits, and for v1.0,
  that macros and mouse keys are refused;
* compiles the editor's export of the default keymap with the release's build date, which must equal the release;
* changes a key on every layer and adds shortcuts (and for v1.1 mouse keys and three macros), then checks that the
  patched release equals a compiled build of the exported `keymap.c`.

`test/ci_check.sh <qmk_firmware dir> <work dir>` is what CI runs on every push. For each release it downloads the
image and unpacks the tag's sources, or, for a release not tagged yet, builds this checkout and requires the SHA-256
in `shinobi_data.js`. It then checks that `shinobi_data.js` regenerates identically and runs `byte_identity.sh` for
each release in its own sources. Firmware changes after a release don't affect that release's check; changes before
v1.1 is tagged must come with a rebuilt image and regenerated data.

`test/qmk_fixed_date.sh` and `test/build_wsl.sh` are its helpers: QMK stamps the build date into the image, so the
test pins it.
