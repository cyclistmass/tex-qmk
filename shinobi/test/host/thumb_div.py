# Copyright 2026 Mauro DiBenedetto
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run divsi3.S's routines, as linked, on a small ARMv6-M (Thumb-1) interpreter, against Python's division.

usage: python3 -I thumb_div.py <elf> <symbol> [<symbol> ...]   (__aeabi_idiv, __divsi3, __aeabi_idivmod)

host_tests.c checks a C model of the arithmetic; this runs the linked bytes themselves, with libgcc's __udivsi3
and __aeabi_idiv0, from the ELF's load segments. A symbol must be a Thumb function (FUNC, odd value): a label
without the Thumb bit faults on a Cortex-M0 when reached by BX or a function pointer. Every instruction the
routines run must be one the interpreter decodes, or the run fails. Edge values (0, +-1, INT_MIN, INT_MAX ...)
and 20,000 random pairs; division by zero must return 0 (and for idivmod, the dividend as remainder), as
__udivsi3 does through __aeabi_idiv0. Needs only python3.
"""
import random
import struct
import sys
import time

M = 0xFFFFFFFF


def load(path):
    b = open(path, "rb").read()
    assert b[:4] == b"\x7fELF" and b[4] == 1 and b[5] == 1, "32-bit little-endian ELF"
    phoff, shoff = struct.unpack_from("<II", b, 28)
    phentsize, phnum, shentsize, shnum, shstrndx = struct.unpack_from("<HHHHH", b, 42)
    mem = {}
    for i in range(phnum):
        ptype, off, vaddr, _, filesz, _, _, _ = struct.unpack_from("<8I", b, phoff + i * phentsize)
        if ptype == 1:
            for j in range(filesz):
                mem[vaddr + j] = b[off + j]
    syms = {}
    secs = [struct.unpack_from("<10I", b, shoff + i * shentsize) for i in range(shnum)]
    for s in secs:
        if s[1] == 2:  # SHT_SYMTAB
            strtab = secs[s[6]]
            for k in range(s[5] // 16):
                name, value, size, info, _, _ = struct.unpack_from("<IIIBBH", b, s[4] + k * 16)
                n = b[strtab[4] + name : b.index(b"\0", strtab[4] + name)].decode()
                if n:
                    syms[n] = (value, size, info & 15)
    return mem, syms


class Fault(Exception):
    pass


def run(mem, entry, r0, r1, limit=5000):
    ram = {}
    R = [0] * 16
    R[0], R[1] = r0 & M, r1 & M
    for i in range(2, 13):
        R[i] = 0xDEAD0000 + i
    R[13], R[14] = 0x20004000, 0xFFFFFFF1  # return to a magic Thumb address
    saved = R[4:12] + [R[13]]
    if not entry & 1:
        raise Fault(f"entry {entry:#x} has no Thumb bit: a BL/BX there would switch to ARM state, which Cortex-M0 faults on")
    pc = entry & ~1
    N = Z = C = V = 0
    used = set()

    def rd8(a):
        if a in mem:
            return mem[a]
        if a in ram:
            return ram[a]
        raise Fault(f"read of unmapped {a:#x}")

    def rd32(a):
        if a & 3:
            raise Fault(f"unaligned word read {a:#x}")
        return rd8(a) | rd8(a + 1) << 8 | rd8(a + 2) << 16 | rd8(a + 3) << 24

    def wr32(a, v):
        if a & 3 or not 0x20000000 <= a < 0x20004000:
            raise Fault(f"bad write {a:#x}")
        for k in range(4):
            ram[a + k] = v >> (8 * k) & 255

    def addc(a, b, c):
        nonlocal N, Z, C, V
        r = a + b + c
        res = r & M
        N, Z, C = res >> 31, int(res == 0), int(r > M)
        V = int(((a ^ res) & (b ^ res)) >> 31 & 1)
        return res

    def nz(res):
        nonlocal N, Z
        N, Z = res >> 31 & 1, int(res == 0)
        return res

    def cond(c):
        return [Z, not Z, C, not C, N, not N, V, not V, C and not Z, not C or Z, N == V, N != V, not Z and N == V, Z or N != V][c]

    for _ in range(limit):
        if pc == 0xFFFFFFF0:
            if R[4:12] + [R[13]] != saved:
                raise Fault("callee-saved registers or SP not restored")
            return R[0], R[1], used
        h = rd8(pc) | rd8(pc + 1) << 8
        npc = pc + 2
        P = pc + 4  # PC as read by instructions
        op = None
        if h >> 11 == 0b00011:
            imm, rm, rn, rdx = h >> 6 & 7, h >> 6 & 7, h >> 3 & 7, h & 7
            b = imm if h >> 10 & 1 else R[rm]
            R[rdx] = addc(R[rn], (~b) & M, 1) if h >> 9 & 1 else addc(R[rn], b, 0)
            op = "adds/subs r"
        elif h >> 13 == 0:
            k, imm, rm, rdx = h >> 11, h >> 6 & 31, h >> 3 & 7, h & 7
            v = R[rm]
            if k == 0:
                if imm:
                    C = v >> (32 - imm) & 1
                res = v << imm & M
                op = "lsls i"
            elif k == 1:
                imm = imm or 32
                C = v >> (imm - 1) & 1
                res = v >> imm if imm < 32 else 0
                op = "lsrs i"
            else:
                imm = imm or 32
                sv = v - (1 << 32) if v >> 31 else v
                C = (sv >> (imm - 1)) & 1
                res = (sv >> min(imm, 31)) & M if imm < 32 else (M if v >> 31 else 0)
                op = "asrs i"
            R[rdx] = nz(res)
        elif h >> 13 == 1:
            k, rdx, imm = h >> 11 & 3, h >> 8 & 7, h & 255
            if k == 0:
                R[rdx] = nz(imm); op = "movs i"
            elif k == 1:
                addc(R[rdx], (~imm) & M, 1); op = "cmp i"
            elif k == 2:
                R[rdx] = addc(R[rdx], imm, 0); op = "adds i8"
            else:
                R[rdx] = addc(R[rdx], (~imm) & M, 1); op = "subs i8"
        elif h >> 10 == 0b010000:
            k, rm, rdx = h >> 6 & 15, h >> 3 & 7, h & 7
            a, b = R[rdx], R[rm]
            names = "ands eors lsls lsrs asrs adcs sbcs rors tst rsbs cmp cmn orrs muls bics mvns".split()
            op = names[k] + " r"
            if k == 0: R[rdx] = nz(a & b)
            elif k == 1: R[rdx] = nz(a ^ b)
            elif k in (2, 3, 4, 7):
                s = b & 255
                if k == 2:
                    if s: C = (a << s >> 32 & 1) if s <= 32 else 0
                    res = a << s & M if s < 32 else 0
                elif k == 3:
                    if s: C = (a >> (s - 1) & 1) if s <= 32 else 0
                    res = a >> s if s < 32 else 0
                elif k == 4:
                    sa = a - (1 << 32) if a >> 31 else a
                    if s: C = (sa >> min(s - 1, 31)) & 1
                    res = (sa >> min(s, 31)) & M
                else:
                    raise Fault("rors not implemented")
                R[rdx] = nz(res)
            elif k == 5: R[rdx] = addc(a, b, C)
            elif k == 6: R[rdx] = addc(a, (~b) & M, C)
            elif k == 8: nz(a & b)
            elif k == 9: R[rdx] = addc(0, (~b) & M, 1)
            elif k == 10: addc(a, (~b) & M, 1)
            elif k == 11: addc(a, b, 0)
            elif k == 12: R[rdx] = nz(a | b)
            elif k == 13: R[rdx] = nz(a * b & M)
            elif k == 14: R[rdx] = nz(a & ~b & M)
            else: R[rdx] = nz(~b & M)
        elif h >> 10 == 0b010001:
            k, rm, rdx = h >> 8 & 3, h >> 3 & 15, (h & 7) | (h >> 4 & 8)
            vm = P if rm == 15 else R[rm]
            if k == 3:
                if rm == 15 or not vm & 1:
                    raise Fault(f"bx/blx to {vm:#x}: not Thumb")
                if h >> 7 & 1:
                    R[14] = npc | 1; op = "blx r"
                else:
                    op = "bx"
                npc = vm & ~1
            elif k == 2:
                if rdx == 15: npc = vm & ~1
                else: R[rdx] = vm
                op = "mov hi"
            elif k == 0:
                if rdx == 15: raise Fault("add pc")
                R[rdx] = (R[rdx] + vm) & M; op = "add hi"
            else:
                addc(R[rdx], (~vm) & M, 1); op = "cmp hi"
        elif h >> 11 == 0b01001:
            R[h >> 8 & 7] = rd32((P & ~3) + (h & 255) * 4); op = "ldr lit"
        elif h >> 11 == 0b10110 and h >> 9 & 3 == 2 or h >> 12 == 0b1011 and h >> 9 & 3 == 2:
            regs = [i for i in range(8) if h >> i & 1]
            if h >> 11 & 1:  # pop
                for i in regs:
                    R[i] = rd32(R[13]); R[13] += 4
                if h >> 8 & 1:
                    v = rd32(R[13]); R[13] += 4
                    if not v & 1: raise Fault(f"pop pc {v:#x}: not Thumb")
                    npc = v & ~1
                op = "pop"
            else:
                if h >> 8 & 1: regs = regs + [14]
                R[13] -= 4 * len(regs)
                for n, i in enumerate(regs): wr32(R[13] + 4 * n, R[i])
                op = "push"
        elif h >> 8 == 0b10110000:
            R[13] = (R[13] + ((-1) ** (h >> 7 & 1)) * (h & 127) * 4) & M; op = "add/sub sp"
        elif h >> 12 == 0b1101 and h >> 8 & 15 < 14:
            if cond(h >> 8 & 15):
                off = (h & 255) - 256 if h & 128 else h & 255
                npc = P + off * 2
            op = "b<c>"
        elif h >> 11 == 0b11100:
            off = (h & 0x7FF) - 0x800 if h & 0x400 else h & 0x7FF
            npc = P + off * 2; op = "b"
        elif h >> 11 == 0b11110:
            h2 = rd8(pc + 2) | rd8(pc + 3) << 8
            if h2 >> 14 != 0b11 or not h2 >> 12 & 1:
                raise Fault(f"{pc:#x}: 32-bit {h:04x} {h2:04x} not BL")
            S = h >> 10 & 1
            J1, J2 = h2 >> 13 & 1, h2 >> 11 & 1
            I1, I2 = 1 - (J1 ^ S), 1 - (J2 ^ S)
            off = S << 24 | I1 << 23 | I2 << 22 | (h & 0x3FF) << 12 | (h2 & 0x7FF) << 1
            if S: off -= 1 << 25
            R[14] = (pc + 4) | 1
            npc = pc + 4 + off; op = "bl"
        elif h >> 8 in (0xB2, 0xBA) and (h >> 8 == 0xB2 or h >> 6 & 3 != 2):
            k, v, rdx = h >> 6 & 3, R[h >> 3 & 7], h & 7
            if h >> 8 == 0xB2:
                op = ["sxth", "sxtb", "uxth", "uxtb"][k]
                w = 16 if k in (0, 2) else 8
                v &= (1 << w) - 1
                if k < 2 and v >> (w - 1): v |= M ^ ((1 << w) - 1)
            elif k == 0:
                v = int.from_bytes(v.to_bytes(4, "little"), "big"); op = "rev"
            elif k == 1:
                v = (v >> 8 & 0x00FF00FF) | (v << 8 & 0xFF00FF00); op = "rev16"
            else:
                v = ((v & 255) << 8 | (v >> 8 & 255)); v = v | (M ^ 0xFFFF) if v >> 15 else v; op = "revsh"
            R[rdx] = v & M
        elif h == 0xBF00:
            op = "nop"
        else:
            raise Fault(f"{pc:#x}: instruction {h:04x} not decoded")
        used.add(op)
        R[15] = npc
        pc = npc
    raise Fault("no return within the instruction limit")


def s32(x):
    return x - (1 << 32) if x >> 31 else x


def main(path, names):
    t0 = time.time()
    mem, syms = load(path)
    edge = [0, 1, -1, 2, -2, 5, -5, 13, -13, 14, -14, 127, -128, 32767, -32768, 2**31 - 1, -2**31]
    random.seed(1)
    pairs = [(a, b) for a in edge for b in edge] + [
        (random.getrandbits(32) - 2**31, random.choice([random.randint(-14, 14), random.getrandbits(32) - 2**31])) for _ in range(20000)]
    fails = 0
    for name in names:
        if name not in syms:
            print(f"SKIP {name}: not in {path}"); continue
        addr, size, typ = syms[name]
        print(f"{name}: value {addr:#x} ({'odd, Thumb' if addr & 1 else 'EVEN'}), type {'FUNC' if typ == 2 else typ}")
        if typ != 2 or not addr & 1:
            fails += 1; print(f"FAIL {name} is not a Thumb function symbol")
        n, used, zero = 0, set(), []
        for a, b in pairs:
            try:
                q, r, u = run(mem, addr, a, b)
            except Fault as e:
                fails += 1; print(f"FAIL {name}({a}, {b}): {e}"); break
            used |= u
            if b == 0:
                zero.append((a, s32(q), s32(r))); continue
            if a == -2**31 and b == -1:
                want_q = -2**31  # wraps, as two's complement does; C leaves it undefined
            else:
                want_q = abs(a) // abs(b) * (1 if (a < 0) == (b < 0) else -1)
            ok = s32(q) == want_q
            if name == "__aeabi_idivmod":
                ok = ok and s32(r) == (a - want_q * b + 2**31) % 2**32 - 2**31
            if not ok:
                fails += 1
                if fails < 10: print(f"FAIL {name}({a}, {b}) = {s32(q)}, {s32(r)}; want {want_q}")
            n += 1
        print(f"  {n} divisions checked; instructions run: {', '.join(sorted(used))}")
        qs = sorted({q for _, q, _ in zero})
        rem_is_a = all(r == a for a, _, r in zero)
        print(f"  divide by zero ({len(zero)} cases) returns quotient {qs}" + (", remainder the dividend" if name == "__aeabi_idivmod" and rem_is_a else ""))
        if qs != [0] or (name == "__aeabi_idivmod" and not rem_is_a):
            fails += 1; print(f"FAIL {name}: divide by zero no longer returns 0")
    print("PASS thumb_div" if not fails else f"FAIL thumb_div: {fails}")
    print(f"TIMING label=thumb_div start={int(t0)} end={int(time.time())} seconds={time.time() - t0:.1f} result={'fail' if fails else 'ok'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
