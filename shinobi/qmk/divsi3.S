// Copyright 2026 Mauro DiBenedetto
// SPDX-License-Identifier: GPL-2.0-or-later
//
// Signed 32-bit division, replacing libgcc's: its Thumb-1 __divsi3 is 460 bytes, too many for the IAP's
// image limit. This one divides the magnitudes with __udivsi3, which every build links anyway, and gives the
// quotient the sign of a ^ b, so it rounds toward zero as C requires; INT_MIN works, its magnitude being
// 0x80000000 unsigned. Division by zero reaches __udivsi3, which handles it as libgcc's own __divsi3 does
// (__aeabi_idiv0). The only caller today is ps2_mouse.c's scroll scaling.
//
// Assembly, not C: under LTO a C function of this name clashes with libgcc's at link time. libgcc keeps
// __divsi3, __aeabi_idiv and __aeabi_idivmod in one object, so all three are defined here to keep it out:
// libc_nano's fvwrite.o refers to __aeabi_idivmod before the linker drops unused sections. Each function has
// its own section, so an unused one is dropped too.

    .syntax unified
    .thumb
    .section .text.__divsi3, "ax", %progbits
    .global __divsi3
    .global __aeabi_idiv
    .thumb_func
    .type   __divsi3, %function
__divsi3:
__aeabi_idiv:
    push    {r4, lr}
    movs    r4, r0
    eors    r4, r1          // bit 31: the quotient's sign
    asrs    r2, r0, #31
    eors    r0, r2
    subs    r0, r0, r2      // |a|
    asrs    r2, r1, #31
    eors    r1, r2
    subs    r1, r1, r2      // |b|
    bl      __udivsi3
    asrs    r4, r4, #31
    eors    r0, r4
    subs    r0, r0, r4      // negated when the signs differ
    pop     {r4, pc}
    .size   __divsi3, . - __divsi3

// Quotient in r0, remainder a - q * b in r1 (the remainder takes the dividend's sign, as C's % does).
    .section .text.__aeabi_idivmod, "ax", %progbits
    .global __aeabi_idivmod
    .thumb_func
    .type   __aeabi_idivmod, %function
__aeabi_idivmod:
    push    {r0, r1, r4, lr}
    bl      __divsi3
    pop     {r1, r2}        // a, b
    muls    r2, r0
    subs    r1, r1, r2
    pop     {r4, pc}
    .size   __aeabi_idivmod, . - __aeabi_idivmod
