/* SPDX-License-Identifier: BSD-2-Clause
 * EL1 identity-mapped UEFI -> Linux Image. No stack access after disabling MMU.
 * Cache set/way layout follows Arm's CCSIDR/CLIDR definitions, including CCIDX.
 */
.text
.globl enter_native
.p2align 4
enter_native:
    msr daifset, #15
    mov x19, x0                  // native Image
    mov x20, x1                  // minimal FDT
    mrs x21, csselr_el1
    dsb sy
    mrs x2, clidr_el1
    ubfx x3, x2, #24, #3        // level of coherence
    mrs x22, id_aa64mmfr2_el1
    ubfx x22, x22, #20, #4      // CCIDX
    mov x4, #0
1:
    cmp x4, x3
    b.hs 6f
    add x5, x4, x4, lsl #1
    lsr x6, x2, x5
    and x6, x6, #7
    cmp x6, #2
    b.lo 5f
    lsl x5, x4, #1
    msr csselr_el1, x5
    isb
    mrs x6, ccsidr_el1
    and x7, x6, #7
    add x7, x7, #4             // log2 cache line bytes
    cbnz x22, 2f
    ubfx x8, x6, #3, #10       // max way
    ubfx x9, x6, #13, #15      // max set
    b 3f
2:
    ubfx x8, x6, #3, #21
    ubfx x9, x6, #32, #24
3:
    clz w10, w8               // way field occupies the high bits of wN
    mov x11, x8
4:
    mov x12, x9
7:
    lsl x13, x11, x10
    lsl x14, x12, x7
    orr x13, x13, x14
    orr x13, x13, x5
    dc cisw, x13
    subs x12, x12, #1
    b.ge 7b
    subs x11, x11, #1
    b.ge 4b
    dsb sy
5:
    add x4, x4, #1
    b 1b
6:
    msr csselr_el1, x21
    dsb sy
    mrs x2, sctlr_el1
    bic x2, x2, #1
    bic x2, x2, #4
    bic x2, x2, #0x1000
    msr sctlr_el1, x2
    isb
    ic iallu
    dsb sy
    isb
    mov x0, x20
    mov x1, #0
    mov x2, #0
    mov x3, #0
    br x19
