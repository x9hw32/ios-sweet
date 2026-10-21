/* SPDX-License-Identifier: BSD-2-Clause
 * Position-independent Linux Image entry for Qualcomm ABL, MMU/cache off.
 */
.section .text.head, "ax"
.global _head
_head:
    b _start
    .long 0
    .quad 0
    .quad _end
    .quad 0xa
    .quad 0, 0, 0
    .ascii "ARM\x64"
    .long 0

.text
.global _start
_start:
    msr daifset, #0xf
    mov x19, x0
    mrs x20, CurrentEL
    cmp x20, #4
    b.ne .Lhalt
    mrs x20, sctlr_el1
    tst x20, #1
    b.ne .Lhalt
    tst x20, #4
    b.ne .Lhalt
    msr spsel, #1
    adrp x1, _stack_top
    add x1, x1, :lo12:_stack_top
    mov sp, x1
    adrp x1, _bss_start
    add x1, x1, :lo12:_bss_start
    adrp x2, _bss_end
    add x2, x2, :lo12:_bss_end
.Lzero:
    cmp x1, x2
    b.hs .Lready
    str xzr, [x1], #8
    b .Lzero
.Lready:
    adrp x1, vectors
    add x1, x1, :lo12:vectors
    msr vbar_el1, x1
    isb
    mov x0, x19
    bl shim_main
.Lhalt:
    wfe
    b .Lhalt

.macro vector number
    .balign 128
    mov x0, #\number
    b exception
.endm
.balign 2048
vectors:
    vector 0
    vector 1
    vector 2
    vector 3
    vector 4
    vector 5
    vector 6
    vector 7
    vector 8
    vector 9
    vector 10
    vector 11
    vector 12
    vector 13
    vector 14
    vector 15
exception:
    msr daifset, #0xf
    bl shim_exception
    b .Lhalt

.section .rodata.payload, "a"
.balign 16
.global _payload_start, _payload_end
_payload_start:
.incbin "payload.bin"
_payload_end:
