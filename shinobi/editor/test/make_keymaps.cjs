// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
// Editor-core checks that need no compiler, and the inputs for the byte-identity test.
// usage: node make_keymaps.cjs <release .bin> <out dir>
// Writes <out>/default_keymap.c (the editor's export of the unchanged keymap), <out>/custom_keymap.c,
// <out>/custom.json and <out>/custom_patched.bin (a remap on every layer plus shortcuts, patched into the release).
"use strict";
const fs = require("fs");
const path = require("path");
require("../shinobi_data.js");
const { makeCore } = require("../editor_core.js");

const [releasePath, outDir] = process.argv.slice(2);
if (!releasePath || !outDir) {
    console.error("usage: node make_keymaps.cjs <release .bin> <out dir>");
    process.exit(2);
}
const core = makeCore(globalThis.SHINOBI_DATA);
const data = core.data;
let failures = 0;
function check(cond, what) {
    console.log(`${cond ? "PASS" : "FAIL"} ${what}`);
    if (!cond) failures++;
}
function keyIndex(baseToken) {
    const i = data.default_layers._BASE.indexOf(baseToken);
    if (i < 0) throw new Error(`no ${baseToken} on the base layer`);
    return i;
}

(async () => {
    const t0 = Date.now();
    fs.mkdirSync(outDir, { recursive: true });
    const release = new Uint8Array(fs.readFileSync(releasePath));

    // Every default token resolves, and its preferred token resolves back to the same value.
    const def = core.defaultLayers();
    let roundTrip = true;
    for (const id of core.layerIds) for (const v of def[id]) if (core.resolve(core.tokenFor(v)) !== v) roundTrip = false;
    check(roundTrip, "default keymap tokens round-trip through value and back");
    check(core.catalog.every((g) => g.items.every((i) => core.resolve(core.tokenFor(i.value)) === i.value)), "catalog round-trips");

    const ok = await core.checkImage(release);
    check(ok.ok, `release image accepted (${ok.problems.join("; ") || "sha256 and default keymap match"})`);

    // Fail closed: a byte changed in code, in the keymap, a short image, and an image without the record.
    const bad = [];
    let img = new Uint8Array(release); img[0x2000] ^= 0xff; bad.push(["one code byte changed", img]);
    img = new Uint8Array(release); img[data.release.keymaps_offset + 10] ^= 0x01; bad.push(["one keymap byte changed", img]);
    bad.push(["image cut short", release.slice(0, release.length - 4)]);
    img = new Uint8Array(release); img[0x3bf8 - 0x3200 + 1] = 0; bad.push(["record at 0x3BF8 changed", img]);
    for (const [what, image] of bad) {
        const r = await core.checkImage(image);
        let threw = false;
        try { await core.patch(image, def); } catch (e) { threw = /^refused/.test(e.message); }
        check(!r.ok && threw, `refused: ${what} (${r.problems.join("; ")})`);
    }

    // Unchanged keymap: patching writes the same bytes back.
    const same = await core.patch(release, def);
    check(Buffer.compare(Buffer.from(same), Buffer.from(release)) === 0, "patching the default keymap leaves the release unchanged");
    fs.writeFileSync(path.join(outDir, "default_keymap.c"), core.keymapC(def));

    // A changed keymap: one remap on each layer, shortcuts, a layer toggle.
    const L = core.defaultLayers();
    const r = core.resolve;
    L._BASE[keyIndex("KC_CAPS")] = r("KC_LCTL");
    L._BASE[keyIndex("KC_INT1")] = r("KC_RSFT");
    L._BASE[keyIndex("KC_SCRL")] = r("LCTL(LSFT(KC_ESC))");
    L._MAC[keyIndex("KC_APP")] = r("KC_RGUI");
    L._FNCTL[keyIndex("KC_INT5")] = r("TG(_FN)");
    L._FN[keyIndex("KC_C")] = r("LCTL(KC_C)");
    L._FN[keyIndex("KC_V")] = r("LCTL(KC_V)");
    L._FN[keyIndex("KC_L")] = r("LGUI(KC_L)");
    L._FN[keyIndex("KC_H")] = r("KC_LEFT");
    L._FN[keyIndex("KC_F12")] = r("KC_CALC");
    L._FN[keyIndex("KC_PAUS")] = r("RALT(KC_PSCR)");
    const json = core.toJSON(L);
    const back = core.fromJSON(json);
    check(core.layerIds.every((id) => back[id].every((v, i) => v === L[id][i])), "keymap.json round-trips");
    const patched = await core.patch(release, L);
    const diff = [];
    for (let i = 0; i < release.length; i++) if (patched[i] !== release[i]) diff.push(i);
    const lo = data.release.keymaps_offset, hi = lo + core.encode(L).length;
    check(diff.length > 0 && diff.every((i) => i >= lo && i < hi), `patch changes ${diff.length} bytes, all inside the keymaps (0x${(lo + 0x3200).toString(16)}-0x${(hi + 0x3200 - 1).toString(16)})`);
    fs.writeFileSync(path.join(outDir, "custom_keymap.c"), core.keymapC(L));
    fs.writeFileSync(path.join(outDir, "custom.json"), json);
    fs.writeFileSync(path.join(outDir, "custom_patched.bin"), patched);
    console.log(`custom_patched.bin sha256 ${await core.sha256(patched)}`);
    const t1 = Date.now();
    console.log(`TIMING label=editor_core_checks start=${Math.floor(t0 / 1000)} end=${Math.floor(t1 / 1000)} seconds=${((t1 - t0) / 1000).toFixed(1)} result=${failures ? "fail" : "ok"}`);
    process.exit(failures ? 1 : 0);
})().catch((e) => {
    console.error(e);
    process.exit(1);
});
