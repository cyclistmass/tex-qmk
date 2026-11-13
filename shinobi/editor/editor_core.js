// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
// Keymap editor core for the TEX Shinobi QMK firmware. It owns every interpretation of a keymap: keycode tokens
// to values and back, the in-image keymap and macro encodings, the release-image check and patch, and
// keymap.c/json export. The page (index.html) and the tests (test/*.cjs) both use it. Data comes from
// shinobi_data.js (tools/gen_editor_data.py), read from the pinned QMK headers and each release's sources.
(function (root) {
    "use strict";

    // Fixed by ld/HT32F52352_TEX_SHINOBI.ld: stock's record at 0x3BF8 (image base 0x3200).
    const RECORD_OFFSET = 0x3bf8 - 0x3200;
    const RECORD = [0x00, 0x51, 0x04, 0x04, 0x01, 0x00, 0x00, 0x34, 0x04, 0x00, 0x02, 0x00];
    const MOD_FUNCS = ["LCTL", "LSFT", "LALT", "LGUI"]; // bit order 0x100, 0x200, 0x400, 0x800
    const RMOD_FUNCS = ["RCTL", "RSFT", "RALT", "RGUI"];
    const MOD_LABELS = ["Ctrl", "Shift", "Alt", "Win"];
    const MACRO_SLOTS = 16; // MC_0-MC_15; the firmware plays MC_n as the n-th 0-terminated sequence in the table

    // What the editor offers. Everything here must resolve against the pinned QMK and shinobi.h (checked at load).
    // A third field names the release feature a group needs. Left out on purpose: features compiled out of the
    // firmware (mouse wheel keys, buttons 4-8, send_string, tap dance, mod-tap and layer-tap).
    const CATALOG = [
        ["Letters", "KC_A KC_B KC_C KC_D KC_E KC_F KC_G KC_H KC_I KC_J KC_K KC_L KC_M KC_N KC_O KC_P KC_Q KC_R KC_S KC_T KC_U KC_V KC_W KC_X KC_Y KC_Z"],
        ["Numbers", "KC_1 KC_2 KC_3 KC_4 KC_5 KC_6 KC_7 KC_8 KC_9 KC_0"],
        ["Symbols", "KC_GRV KC_MINS KC_EQL KC_LBRC KC_RBRC KC_BSLS KC_SCLN KC_QUOT KC_COMM KC_DOT KC_SLSH KC_NUBS KC_NUHS"],
        ["Editing and navigation", "KC_ESC KC_TAB KC_ENT KC_SPC KC_BSPC KC_DEL KC_INS KC_HOME KC_END KC_PGUP KC_PGDN KC_UP KC_DOWN KC_LEFT KC_RGHT KC_CAPS KC_PSCR KC_SCRL KC_PAUS KC_APP"],
        ["Modifiers", "KC_LCTL KC_LSFT KC_LALT KC_LGUI KC_RCTL KC_RSFT KC_RALT KC_RGUI"],
        ["Function keys", "KC_F1 KC_F2 KC_F3 KC_F4 KC_F5 KC_F6 KC_F7 KC_F8 KC_F9 KC_F10 KC_F11 KC_F12 KC_F13 KC_F14 KC_F15 KC_F16 KC_F17 KC_F18 KC_F19 KC_F20 KC_F21 KC_F22 KC_F23 KC_F24"],
        ["Numpad", "KC_NUM KC_P7 KC_P8 KC_P9 KC_P4 KC_P5 KC_P6 KC_P1 KC_P2 KC_P3 KC_P0 KC_PDOT KC_PENT KC_PPLS KC_PMNS KC_PAST KC_PSLS"],
        ["Media", "KC_MPLY KC_MSTP KC_MPRV KC_MNXT KC_MUTE KC_VOLD KC_VOLU KC_BRID KC_BRIU"],
        ["Apps and browser", "KC_WBAK KC_WFWD KC_WHOM KC_WREF KC_WSTP KC_WSCH KC_MAIL KC_CALC KC_MYCM"],
        ["System", "KC_PWR KC_SLEP KC_WAKE"],
        ["International", "KC_INT1 KC_INT2 KC_INT3 KC_INT4 KC_INT5 KC_LNG1 KC_LNG2"],
        ["Mouse buttons", "MS_BTN1 MS_BTN2 MS_BTN3"],
        ["Mouse movement", "MS_UPLEFT MS_UP MS_UPRIGHT MS_LEFT MS_RGHT MS_DOWNLEFT MS_DOWN MS_DOWNRIGHT", "mouse_keys"],
        ["Macros", Array.from({ length: MACRO_SLOTS }, (_, i) => "MC_" + i).join(" "), "macros"],
        ["TrackPoint speed", "TP_SEN1 TP_SEN2 TP_SEN3 TP_SEN4 TP_SEN5 TP_SEN6 TP_SEN7 TP_SEN8 TP_SEN9"],
        ["Bluetooth and battery", "BLE_SLOT1 BLE_SLOT2 BLE_SLOT3 BLE_PAIR BLE_USB BAT_REPORT"],
        ["Sleep time", "SLEEP1 SLEEP2 SLEEP3 SLEEP4 SLEEP5 SLEEP6 SLEEP7 SLEEP8 SLEEP9"],
        ["Layers", "MO(_FN) TG(_FN) MO(_MAC) TG(_MAC) MO(_FNCTL) TG(_FNCTL)"],
        ["Nothing", "KC_NO _______"],
    ];

    const LABELS = {
        KC_GRV: "`", KC_MINS: "-", KC_EQL: "=", KC_LBRC: "[", KC_RBRC: "]", KC_BSLS: "\\", KC_SCLN: ";", KC_QUOT: "'",
        KC_COMM: ",", KC_DOT: ".", KC_SLSH: "/", KC_NUBS: "ISO \\", KC_NUHS: "ISO #", KC_ESC: "Esc", KC_TAB: "Tab",
        KC_ENT: "Enter", KC_SPC: "Space", KC_BSPC: "Bksp", KC_DEL: "Del", KC_INS: "Ins", KC_HOME: "Home", KC_END: "End",
        KC_PGUP: "PgUp", KC_PGDN: "PgDn", KC_UP: "↑", KC_DOWN: "↓", KC_LEFT: "←", KC_RGHT: "→", KC_CAPS: "Caps",
        KC_PSCR: "PrtSc", KC_SCRL: "ScrLk", KC_PAUS: "Pause", KC_APP: "Menu", KC_LCTL: "Ctrl", KC_LSFT: "Shift",
        KC_LALT: "Alt", KC_LGUI: "Win", KC_RCTL: "RCtrl", KC_RSFT: "RShift", KC_RALT: "RAlt", KC_RGUI: "RWin",
        KC_NUM: "NumLk", KC_PDOT: "P.", KC_PENT: "PEnter", KC_PPLS: "P+", KC_PMNS: "P-", KC_PAST: "P*", KC_PSLS: "P/",
        KC_MPLY: "Play", KC_MSTP: "Stop", KC_MPRV: "Prev", KC_MNXT: "Next", KC_MUTE: "Mute", KC_VOLD: "Vol-",
        KC_VOLU: "Vol+", KC_BRID: "Bri-", KC_BRIU: "Bri+", KC_WBAK: "Back", KC_WFWD: "Fwd", KC_WHOM: "WWW Home",
        KC_WREF: "Refresh", KC_WSTP: "WWW Stop", KC_WSCH: "Search", KC_MAIL: "Mail", KC_CALC: "Calc", KC_MYCM: "My PC",
        KC_PWR: "Power", KC_SLEP: "Sleep", KC_WAKE: "Wake", KC_INT1: "Ro", KC_INT2: "Kana", KC_INT3: "Yen",
        KC_INT4: "Henkan", KC_INT5: "Muhen", KC_LNG1: "Han/Eng", KC_LNG2: "Hanja", MS_BTN1: "Left click",
        MS_BTN2: "Right click", MS_BTN3: "Middle", BLE_SLOT1: "BT 1", BLE_SLOT2: "BT 2", BLE_SLOT3: "BT 3",
        BLE_PAIR: "BT pair", BLE_USB: "USB", BAT_REPORT: "Battery", KC_NO: "None", _______: "▽",
        MS_UP: "Mouse ↑", MS_DOWN: "Mouse ↓", MS_LEFT: "Mouse ←", MS_RGHT: "Mouse →", MS_UPLEFT: "Mouse ↖",
        MS_UPRIGHT: "Mouse ↗", MS_DOWNLEFT: "Mouse ↙", MS_DOWNRIGHT: "Mouse ↘",
    };
    const TITLES = {
        _______: "Transparent: the key does what the layer below says",
        KC_NO: "Does nothing",
        BLE_PAIR: "Tap: Bluetooth slot 1; hold 3 s: pair a new host there",
        BLE_USB: "Back to USB when it is plugged in",
        BAT_REPORT: "Types the battery level",
        KC_NUBS: "The extra key left of Z on ISO boards",
        KC_NUHS: "The extra key left of Enter on ISO boards",
    };
    const MOUSE_TITLE = "Moves the pointer while held, speeding up the longer it is held";

    // Sequence macros are typed text. Plain characters use a US layout; {Name} is one key by its label or QMK name
    // (Enter, Tab, F5, Del, ...), {Ctrl+Shift+Esc} holds modifiers for that key, {Ctrl} alone holds Ctrl for the next
    // key, {0x2A} is a raw HID usage, and {{ is a literal {.
    const US = {};
    "abcdefghijklmnopqrstuvwxyz".split("").forEach((c, i) => { US[c] = [0, 0x04 + i]; US[c.toUpperCase()] = [1, 0x04 + i]; });
    "1234567890".split("").forEach((c, i) => { US[c] = [0, 0x1e + i]; US["!@#$%^&*()"[i]] = [1, 0x1e + i]; });
    [[" ", null, 0x2c], ["-", "_", 0x2d], ["=", "+", 0x2e], ["[", "{", 0x2f], ["]", "}", 0x30], ["\\", "|", 0x31],
        [";", ":", 0x33], ["'", "\"", 0x34], ["`", "~", 0x35], [",", "<", 0x36], [".", ">", 0x37], ["/", "?", 0x38]]
        .forEach(([a, b, u]) => { US[a] = [0, u]; if (b) US[b] = [1, u]; });
    const US_BACK = [{}, {}]; // [shift][usage] -> character
    for (const [ch, [s, u]] of Object.entries(US)) US_BACK[s][u] = ch;
    const MACRO_MODS = ["Ctrl", "Shift", "Alt", "Win", "RCtrl", "RShift", "RAlt", "RWin"]; // HID 0xE0-0xE7

    function makeCore(data, tag) {
        const rel = tag ? data.releases.find((r) => r.tag === tag) : data.releases[data.releases.length - 1];
        if (!rel) throw new Error(`unknown release ${tag}`);
        const kc = data.keycodes;
        const custom = rel.custom_keycodes;
        const funcs = data.functions;
        const layerIds = data.layers.map((l) => l.id);
        const nkeys = data.keys.length;
        const { rows, cols } = data.matrix;
        const layerBytes = rows * cols * 2;
        const blockBytes = layerIds.length * layerBytes;

        function layerIndex(id) {
            const i = layerIds.indexOf(id);
            if (i < 0) throw new Error(`unknown layer ${id}`);
            return i;
        }

        // Token grammar: NAME | FUNC(ARG). Values follow QMK's macros at the pinned commit.
        function resolve(token) {
            const t = String(token).replace(/\s+/g, "");
            const m = /^([A-Z]+)\((.*)\)$/.exec(t);
            if (m) {
                const f = funcs[m[1]];
                if (!f) throw new Error(`unknown function ${m[1]} in ${t}`);
                if (f.arg === "layer") return f.base | (layerIndex(m[2]) & 0x1f);
                const inner = resolve(m[2]);
                if (inner > 0x1fff) throw new Error(`${t}: modifiers only wrap basic keys`);
                return f.base | inner;
            }
            if (/^0x[0-9a-fA-F]{1,4}$/.test(t)) return parseInt(t, 16);
            if (Object.prototype.hasOwnProperty.call(custom, t)) return custom[t];
            if (Object.prototype.hasOwnProperty.call(kc, t)) return kc[t];
            throw new Error(`unknown keycode ${t}`);
        }

        const groups = CATALOG.filter(([, , feature]) => !feature || rel[feature]);
        // Preferred name for each value: catalog names first, then the shortest KC_/MS_ alias.
        const names = new Map();
        for (const [, list] of CATALOG) for (const n of list.split(" ")) if (!/\(/.test(n)) { try { names.set(resolve(n), n); } catch (e) { /* not in this release */ } }
        for (const [n, v] of Object.entries(custom)) if (!names.has(v)) names.set(v, n);
        const byLen = Object.entries(kc).filter(([n]) => /^(KC|MS)_/.test(n)).sort((a, b) => a[0].length - b[0].length);
        for (const [n, v] of byLen) if (!names.has(v)) names.set(v, n);

        function tokenFor(v) {
            if (names.has(v)) return names.get(v);
            for (const f of ["MO", "TG"]) {
                const b = funcs[f].base;
                if (v >= b && v < b + 0x20 && (v & 0x1f) < layerIds.length) return `${f}(${layerIds[v & 0x1f]})`;
            }
            if (v >= 0x100 && v <= 0x1fff && names.has(v & 0xff)) {
                const right = v & 0x1000;
                let t = names.get(v & 0xff);
                for (let i = 3; i >= 0; i--) if (v & (0x100 << i)) t = `${(right ? RMOD_FUNCS : MOD_FUNCS)[i]}(${t})`;
                return t;
            }
            return "0x" + v.toString(16).toUpperCase().padStart(4, "0");
        }

        function macroIndex(v) {
            const i = v - kc.MC_0;
            return i >= 0 && i < 32 ? i : -1;
        }

        function label(v) {
            const t = tokenFor(v);
            if (LABELS[t]) return LABELS[t];
            let m;
            if (macroIndex(v) >= 0) return "Macro " + macroIndex(v);
            if ((m = /^(KC|MS)_(.+)$/.exec(t))) return m[2];
            if ((m = /^(MO|TG)\((\w+)\)$/.exec(t))) {
                const l = data.layers.find((x) => x.id === m[2]);
                return (m[1] === "MO" ? "Hold " : "Toggle ") + l.name.replace(/ \(.*\)$/, "");
            }
            if ((m = /^TP_SEN(\d)$/.exec(t))) return "TP " + m[1];
            if ((m = /^SLEEP(\d)$/.exec(t))) return "Sleep " + m[1];
            if (v >= 0x100 && v <= 0x1fff && names.has(v & 0xff)) {
                const parts = [];
                for (let i = 0; i < 4; i++) if (v & (0x100 << i)) parts.push((v & 0x1000 ? "R" : "") + MOD_LABELS[i]);
                return parts.join("+") + "+" + label(v & 0xff);
            }
            return t;
        }

        function isMouseKey(v) {
            return (v >= kc.MS_UP && v <= kc.MS_RGHT) || ["MS_UPLEFT", "MS_UPRIGHT", "MS_DOWNLEFT", "MS_DOWNRIGHT"].some((n) => custom[n] === v);
        }

        function title(v) {
            const t = tokenFor(v);
            if (TITLES[t]) return TITLES[t];
            if (macroIndex(v) >= 0) return `Types sequence macro ${macroIndex(v)} (step 3)`;
            if (isMouseKey(v)) return MOUSE_TITLE;
            return t;
        }

        // What this release's firmware can't do: keys for features it doesn't have.
        function unsupported(layers) {
            const out = [];
            for (const id of layerIds) {
                for (const v of layers[id]) {
                    if (macroIndex(v) >= 0 && !rel.macros) out.push(`${label(v)} needs firmware v1.1 or later`);
                    else if (macroIndex(v) >= MACRO_SLOTS) out.push(`${label(v)}: the editor offers macros 0-${MACRO_SLOTS - 1}`);
                    else if (v >= kc.MS_UP && v <= kc.MS_RGHT && !rel.mouse_keys) out.push(`${label(v)} needs firmware v1.1 or later`);
                }
            }
            return [...new Set(out)];
        }

        function modsOf(v) {
            return v >= 0x100 && v <= 0x1fff ? { mods: (v >> 8) & 0x0f, right: !!(v & 0x1000), base: v & 0xff } : null;
        }

        function withMods(base, mods, right) {
            if (base > 0xff) throw new Error("modifiers only wrap basic keys");
            if (!mods) return base;
            return (right ? 0x1000 : 0) | (mods << 8) | base;
        }

        function defaultLayers() {
            const out = {};
            for (const id of layerIds) out[id] = rel.default_layers[id].map(resolve);
            return out;
        }

        // Macro key names, case-insensitive: the page's labels first (Enter, Esc, Bksp), then QMK names without KC_.
        const keyNames = new Map();
        MACRO_MODS.forEach((n, i) => keyNames.set(n.toLowerCase(), 0xe0 + i));
        for (const [t, l] of Object.entries(LABELS)) {
            if (!/^KC_/.test(t) || kc[t] > 0xe7 || kc[t] < 4) continue;
            if (!keyNames.has(l.toLowerCase())) keyNames.set(l.toLowerCase(), kc[t]);
        }
        for (const [n, v] of Object.entries(kc)) {
            if (!/^KC_/.test(n) || v < 4 || v > 0xe7) continue;
            const k = n.slice(3).toLowerCase();
            if (!keyNames.has(k)) keyNames.set(k, v);
        }
        function keyName(u) { // a name for usage u that parses back to u
            if (u >= 0xe0) return MACRO_MODS[u - 0xe0];
            const t = names.get(u);
            for (const c of [t && LABELS[t], t && t.replace(/^KC_/, "")]) {
                if (c && /^[A-Za-z0-9↑↓←→]+$/.test(c) && keyNames.get(c.toLowerCase()) === u) return c;
            }
            return "0x" + u.toString(16).toUpperCase().padStart(2, "0");
        }

        function parseMacro(text) {
            const out = [];
            const s = String(text);
            for (let i = 0; i < s.length;) {
                const ch = s[i];
                if (ch === "{" && s[i + 1] === "{") { out.push(0xe1, 0x2f); i += 2; continue; }
                if (ch === "{") {
                    const end = s.indexOf("}", i);
                    if (end < 0) throw new Error(`"{" without "}" at position ${i + 1} (type {{ for a literal {)`);
                    const parts = s.slice(i + 1, end).split("+").map((p) => p.trim());
                    for (const p of parts) {
                        let u;
                        if (/^0x[0-9a-fA-F]{1,2}$/.test(p)) u = parseInt(p, 16);
                        else u = keyNames.get(p.toLowerCase());
                        if (u === undefined || u < 4 || u > 0xe7) throw new Error(`unknown key {${p}}`);
                        out.push(u);
                    }
                    i = end + 1;
                    continue;
                }
                const k = US[ch];
                if (!k) throw new Error(`can't type ${JSON.stringify(ch)} (US layout); use {Name} for other keys`);
                if (k[0]) out.push(0xe1);
                out.push(k[1]);
                i++;
            }
            return out;
        }

        function formatMacro(bytes) {
            let text = "";
            let mods = [];
            for (const u of bytes) {
                if (u >= 0xe0) { mods.push(u); continue; }
                const shift = mods.length === 1 && mods[0] === 0xe1 ? 1 : mods.length ? -1 : 0;
                const ch = shift >= 0 ? US_BACK[shift][u] : undefined;
                if (ch !== undefined) text += ch === "{" ? "{{" : ch;
                else text += "{" + mods.map(keyName).concat(keyName(u)).join("+") + "}";
                mods = [];
            }
            for (const m of mods) text += "{" + keyName(m) + "}";
            return text;
        }

        // The table: each macro's usages and a 0, in MC order; trailing empty macros take no room.
        function encodeMacros(macros) {
            const size = rel.macros ? rel.macros.size : 0;
            const list = macros || [];
            if (list.length > MACRO_SLOTS) throw new Error(`at most ${MACRO_SLOTS} macros`);
            const last = list.reduce((a, t, i) => (t ? i : a), -1);
            if (last >= 0 && !rel.macros) throw new Error(`${rel.tag} has no sequence macros; they need firmware v1.1 or later`);
            const bytes = [];
            for (let i = 0; i <= last; i++) {
                let b;
                try { b = parseMacro(list[i] || ""); } catch (e) { throw new Error(`macro ${i}: ${e.message}`); }
                bytes.push(...b, 0);
            }
            if (bytes.length > size) throw new Error(`the macros take ${bytes.length} bytes; the table holds ${size}`);
            const out = new Uint8Array(size);
            out.set(bytes);
            return { table: out, used: bytes.length };
        }

        // keymaps[layer][row][col], uint16 little-endian; positions not in LAYOUT stay KC_NO, as LAYOUT() leaves them.
        function encode(layers) {
            const buf = new Uint8Array(blockBytes);
            layerIds.forEach((id, li) => {
                const vals = layers[id];
                if (!vals || vals.length !== nkeys) throw new Error(`layer ${id} needs ${nkeys} keys`);
                vals.forEach((v, k) => {
                    if (!Number.isInteger(v) || v < 0 || v > 0xffff) throw new Error(`layer ${id} key ${k}: bad value`);
                    const [r, c] = data.keys[k].matrix;
                    const off = li * layerBytes + (r * cols + c) * 2;
                    buf[off] = v & 0xff;
                    buf[off + 1] = v >> 8;
                });
            });
            return buf;
        }

        // Fails closed: the image must be this release, with the default keymap and empty macros where expected.
        async function checkImage(image) {
            const problems = [];
            if (image.length !== rel.size) problems.push(`size is ${image.length} bytes, ${rel.file} is ${rel.size}`);
            const digest = await sha256(image);
            if (digest !== rel.sha256) problems.push(`sha256 ${digest.slice(0, 16)}… is not ${rel.file}'s ${rel.sha256.slice(0, 16)}…`);
            const want = encode(defaultLayers());
            const at = rel.keymaps_offset;
            if (image.length >= at + want.length) {
                for (let i = 0; i < want.length; i++) {
                    if (image[at + i] !== want[i]) {
                        problems.push(`keymap bytes differ from the default at offset 0x${(at + i).toString(16)}`);
                        break;
                    }
                }
            }
            if (rel.macros) {
                const { offset, size } = rel.macros;
                if (image.length < offset + size || image.subarray(offset, offset + size).some((b) => b !== 0)) {
                    problems.push(`the macro table at 0x${(offset + 0x3200).toString(16)} is not empty`);
                }
            }
            if (image.length < RECORD_OFFSET + RECORD.length || RECORD.some((b, i) => image[RECORD_OFFSET + i] !== b)) {
                problems.push("stock's record at 0x3BF8 is missing");
            }
            return { ok: problems.length === 0, problems, sha256: digest };
        }

        async function patch(image, layers, macros) {
            const check = await checkImage(image);
            if (!check.ok) throw new Error("refused: " + check.problems.join("; "));
            const bad = unsupported(layers);
            if (bad.length) throw new Error(`${rel.tag} can't do this: ${bad.join("; ")}`);
            const table = encodeMacros(macros).table;
            const out = new Uint8Array(image);
            out.set(encode(layers), rel.keymaps_offset);
            if (rel.macros) out.set(table, rel.macros.offset);
            return out;
        }

        function keymapC(layers, macros) {
            let text = rel.keymap_c_template;
            for (const id of layerIds) {
                const toks = layers[id].map(tokenFor);
                let lines = [];
                let row = -1;
                toks.forEach((t, k) => {
                    const r = data.keys[k].matrix[0];
                    if (r !== row) {
                        lines.push([]);
                        row = r;
                    }
                    lines[lines.length - 1].push(t);
                });
                const body = lines.map((l) => "        " + l.map((t) => t.padEnd(7)).join(", ").trimEnd()).join(",\n");
                const marker = `@@${id}@@`;
                if (!text.includes(marker)) throw new Error(`template has no ${marker}`);
                text = text.replace(marker, "\n" + body + "\n    ");
            }
            const { table, used } = encodeMacros(macros);
            if (used) {
                const hex = Array.from(table.subarray(0, used), (b) => "0x" + b.toString(16).toUpperCase().padStart(2, "0"));
                const rowsOut = [];
                for (let i = 0; i < hex.length; i += 12) rowsOut.push("    " + hex.slice(i, i + 12).join(", ") + ",");
                const listing = (macros || []).map((t, i) => (t ? `//   MC_${i}: ${t.replace(/[\r\n]/g, " ")}\n` : "")).join("");
                text += `\n// Sequence macros, played by MC_0-MC_${MACRO_SLOTS - 1}: HID usages, 0xE0-0xE7 held until the next key, 0 ends one.\n` +
                    `// The linker places them in the macro table (ld/HT32F52352_TEX_SHINOBI.ld) and zero-fills the rest.\n` +
                    listing +
                    `const uint8_t tex_macro_data[] __attribute__((section(".tex_macros"), used)) = {\n${rowsOut.join("\n")}\n};\n`;
            }
            return text;
        }

        function toJSON(layers, macros) {
            const out = { keyboard: "tex/shinobi", format: 1, release: rel.tag, layers: {} };
            for (const id of layerIds) out.layers[id] = layers[id].map(tokenFor);
            const list = (macros || []).slice();
            while (list.length && !list[list.length - 1]) list.pop();
            if (list.length) out.macros = list;
            return JSON.stringify(out, null, 1) + "\n";
        }

        function fromJSON(text) {
            const j = JSON.parse(text);
            if (j.keyboard !== "tex/shinobi" || j.format !== 1) throw new Error("not a TEX Shinobi keymap file");
            const layers = {};
            for (const id of layerIds) {
                const toks = j.layers && j.layers[id];
                if (!Array.isArray(toks) || toks.length !== nkeys) throw new Error(`layer ${id} needs ${nkeys} keys`);
                layers[id] = toks.map(resolve);
            }
            const macros = j.macros === undefined ? [] : j.macros;
            if (!Array.isArray(macros) || macros.some((t) => typeof t !== "string")) throw new Error("macros must be a list of strings");
            encodeMacros(macros); // throws on bad syntax, too many bytes, or a release without macros
            const bad = unsupported(layers);
            if (bad.length) throw new Error(bad.join("; "));
            return { layers, macros: Array.from({ length: MACRO_SLOTS }, (_, i) => macros[i] || "") };
        }

        const catalog = groups.map(([group, list]) => ({ group, items: list.split(" ").map((n) => ({ token: n, value: resolve(n) })) }));
        return {
            data, release: rel, layerIds, catalog, macroSlots: rel.macros ? MACRO_SLOTS : 0, resolve, tokenFor, label, title,
            modsOf, withMods, defaultLayers, macroIndex, isMouseKey, unsupported, parseMacro, formatMacro, encodeMacros,
            encode, checkImage, patch, keymapC, toJSON, fromJSON, sha256,
        };
    }

    async function sha256(bytes) {
        const h = await root.crypto.subtle.digest("SHA-256", bytes);
        return Array.from(new Uint8Array(h), (b) => b.toString(16).padStart(2, "0")).join("");
    }

    // Which release an image is, by its sha256; null if none.
    async function identify(data, image) {
        const digest = await sha256(image);
        const r = data.releases.find((x) => x.sha256 === digest);
        return r ? r.tag : null;
    }

    const api = { makeCore, identify, sha256 };
    root.ShinobiCore = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
