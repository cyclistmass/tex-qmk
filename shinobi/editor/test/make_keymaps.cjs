// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
// Editor-core checks that need no compiler, and the inputs for the byte-identity test.
// usage: node make_keymaps.cjs <release .bin> <out dir>
// The release is recognised by its sha256 among those in shinobi_data.js. Writes <out>/build_date (the release's),
// <out>/default_keymap.c (the editor's export of the unchanged keymap), <out>/custom_keymap.c, <out>/custom.json and
// <out>/custom_patched.bin (a remap on every layer plus shortcuts, and from v1.1 mouse keys and macros, patched in).
"use strict";
const fs = require("fs");
const path = require("path");
require("../shinobi_data.js");
const { makeCore, identify } = require("../editor_core.js");

const [releasePath, outDir] = process.argv.slice(2);
if (!releasePath || !outDir) {
    console.error("usage: node make_keymaps.cjs <release .bin> <out dir>");
    process.exit(2);
}
let failures = 0;
function check(cond, what) {
    console.log(`${cond ? "PASS" : "FAIL"} ${what}`);
    if (!cond) failures++;
}
function throws(fn, re) {
    try { fn(); } catch (e) { return re.test(e.message) ? e.message : `wrong error: ${e.message}`; }
    return "";
}

(async () => {
    const t0 = Date.now();
    fs.mkdirSync(outDir, { recursive: true });
    const release = new Uint8Array(fs.readFileSync(releasePath));
    const tag = await identify(globalThis.SHINOBI_DATA, release);
    if (!tag) throw new Error(`${releasePath} is none of the releases in shinobi_data.js`);
    const core = makeCore(globalThis.SHINOBI_DATA, tag);
    const rel = core.release;
    console.log(`release ${tag} (${rel.file}), macros ${JSON.stringify(rel.macros)}, mouse keys ${rel.mouse_keys}`);
    fs.writeFileSync(path.join(outDir, "build_date"), rel.build_date);
    const keyIndex = (baseToken) => {
        const i = rel.default_layers._BASE.indexOf(baseToken);
        if (i < 0) throw new Error(`no ${baseToken} on the base layer`);
        return i;
    };

    // Every default token resolves, and its preferred token resolves back to the same value.
    const def = core.defaultLayers();
    let roundTrip = true;
    for (const id of core.layerIds) for (const v of def[id]) if (core.resolve(core.tokenFor(v)) !== v) roundTrip = false;
    check(roundTrip, "default keymap tokens round-trip through value and back");
    check(core.catalog.every((g) => g.items.every((i) => core.resolve(core.tokenFor(i.value)) === i.value)), "catalog round-trips");
    const groups = core.catalog.map((g) => g.group);
    check(groups.includes("Macros") === !!rel.macros && groups.includes("Mouse movement") === rel.mouse_keys,
        `catalog offers macros and mouse keys only where ${tag} has them`);

    const ok = await core.checkImage(release);
    check(ok.ok, `release image accepted (${ok.problems.join("; ") || "sha256, default keymap and empty macros match"})`);

    // Fail closed: a byte changed in code, in the keymap, in the macro table, a short image, no record.
    const bad = [];
    let img = new Uint8Array(release); img[0x2000] ^= 0xff; bad.push(["one code byte changed", img]);
    img = new Uint8Array(release); img[rel.keymaps_offset + 10] ^= 0x01; bad.push(["one keymap byte changed", img]);
    if (rel.macros) { img = new Uint8Array(release); img[rel.macros.offset + rel.macros.size - 1] = 0x04; bad.push(["one macro byte changed", img]); }
    bad.push(["image cut short", release.slice(0, release.length - 4)]);
    img = new Uint8Array(release); img[0x3bf8 - 0x3200 + 1] = 0; bad.push(["record at 0x3BF8 changed", img]);
    for (const [what, image] of bad) {
        const r = await core.checkImage(image);
        let threw = false;
        try { await core.patch(image, def, []); } catch (e) { threw = /^refused/.test(e.message); }
        check(!r.ok && threw, `refused: ${what} (${r.problems.join("; ")})`);
    }

    // Unchanged keymap: patching writes the same bytes back.
    const same = await core.patch(release, def, []);
    check(Buffer.compare(Buffer.from(same), Buffer.from(release)) === 0, "patching the default keymap leaves the release unchanged");
    fs.writeFileSync(path.join(outDir, "default_keymap.c"), core.keymapC(def, []));

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
    let macros = [];
    if (!rel.macros) {
        // A release without macros or mouse keys refuses them everywhere.
        const M = core.defaultLayers();
        M._FN[keyIndex("KC_E")] = r("MC_0");
        check(core.unsupported(M).length === 1, `${tag}: a macro key is flagged (${core.unsupported(M).join("; ")})`);
        check(!!throws(() => core.encodeMacros(["hi"]), /no sequence macros/), `${tag}: macro text refused`);
        let refused = false;
        try { await core.patch(release, M, []); } catch (e) { refused = /can't do this/.test(e.message); }
        check(refused, `${tag}: patch refuses a keymap with a macro key`);
    } else {
        // Macro text: the syntax round-trips through bytes, and bad text or too many bytes is refused.
        const texts = ["Hello, World!{Enter}", "{Ctrl+A}{Ctrl+C}", "a{{b}c~|\"_+", "{Win+R}notepad{Enter}", "{Ctrl}{Shift}{Esc}",
            "{0x68}{F13}{Del}{Menu}{Ctrl+Shift+Esc}", "{RAlt}"];
        for (const t of texts) {
            const b = core.parseMacro(t);
            const back = core.formatMacro(b);
            check(JSON.stringify(core.parseMacro(back)) === JSON.stringify(b), `macro "${t}" -> ${b.length} bytes -> "${back}" -> same bytes`);
        }
        check(JSON.stringify(core.parseMacro("He")) === JSON.stringify([0xe1, 0x0b, 0x08]), `"He" encodes as E1 0B 08 (DESIGN.md)`);
        for (const [t, re] of [["{Nope}", /unknown key/], ["a{Enter", /without/], ["é", /can't type/], ["{0x00}", /unknown key/], ["{KC_NO}", /unknown key/]]) {
            check(!!throws(() => core.parseMacro(t), re), `bad macro "${t}" refused (${throws(() => core.parseMacro(t), re)})`);
        }
        check(!!throws(() => core.encodeMacros(["x".repeat(rel.macros.size)]), /holds/), `macros over ${rel.macros.size} bytes refused`);
        const full = core.encodeMacros(["x".repeat(rel.macros.size - 1)]);
        check(full.used === rel.macros.size, `macros of exactly ${rel.macros.size} bytes fit`);

        // Mouse keys on Fn+IJKL-style keys and the arrows' diagonals, and macro keys on Fn.
        L._FN[keyIndex("KC_I")] = r("MS_UP");
        L._FN[keyIndex("KC_K")] = r("MS_DOWN");
        L._FN[keyIndex("KC_J")] = r("MS_LEFT");
        L._FN[keyIndex("KC_SCLN")] = r("MS_RGHT");
        L._FN[keyIndex("KC_U")] = r("MS_UPLEFT");
        L._FN[keyIndex("KC_O")] = r("MS_UPRIGHT");
        L._FN[keyIndex("KC_M")] = r("MS_DOWNLEFT");
        L._FN[keyIndex("KC_DOT")] = r("MS_DOWNRIGHT");
        L._FN[keyIndex("KC_1")] = r("MC_0");
        L._FN[keyIndex("KC_2")] = r("MC_1");
        L._FN[keyIndex("KC_4")] = r("MC_3");
        L._BASE[keyIndex("KC_PSCR")] = r("MC_15");
        macros = Array.from({ length: core.macroSlots }, () => "");
        macros[0] = "Hello, World!{Enter}";
        macros[1] = "{Ctrl+A}{Ctrl+C}";
        macros[3] = "{Win+R}notepad{Enter}";
    }
    const json = core.toJSON(L, macros);
    const back = core.fromJSON(json);
    check(core.layerIds.every((id) => back.layers[id].every((v, i) => v === L[id][i])) &&
        macros.every((t, i) => back.macros[i] === t), "keymap.json round-trips");
    const patched = await core.patch(release, L, macros);
    const diff = [];
    for (let i = 0; i < release.length; i++) if (patched[i] !== release[i]) diff.push(i);
    const lo = rel.keymaps_offset, hi = lo + core.encode(L).length;
    const inMacros = (i) => rel.macros && i >= rel.macros.offset && i < rel.macros.offset + rel.macros.size;
    check(diff.length > 0 && diff.every((i) => (i >= lo && i < hi) || inMacros(i)),
        `patch changes ${diff.length} bytes (${diff.filter(inMacros).length} in the macro table), all inside the keymaps and macros`);
    fs.writeFileSync(path.join(outDir, "custom_keymap.c"), core.keymapC(L, macros));
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
