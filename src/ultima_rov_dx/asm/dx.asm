; Ultima: Runes of Virtue DX -- CGB colorization runtime.
;
; Assembled by ultima_rov_dx.sm83asm (see build_dx.py). All addresses of
; original-game code referenced here are documented in
; reverse_engineering/notes/ and game_layout.py.
;
; Design summary (details: reverse_engineering/notes/colorization_design.md)
;   * Boot (CGB only): switch to double speed, copy the WRAM-bank-2 runtime
;     image from ROM bank 8 to $D000-$DDFF (SVBK=2).
;   * BG attributes: every write path to the $9800/$9C00 maps is mirrored:
;       - bank1 tile-program generator/executor ($4A61/$4B45): the program
;         in WRAM $D800 is translated into an attribute program that runs
;         right after it with VBK=1 (hook at bank1:$4B3C).
;       - single metatile writer $066B (hook).
;       - every LCD-on site (rst $28 / rst $30): full attribute recompute
;         of both maps while the LCD is still off.
;     Attribute of a tile = LUT[tile id]. LUT[$00-$3F] follows the HRAM
;     metatile slot system (slot s = tiles s*4..s*4+3, hook at bank1:$4F6C).
;   * OBJ: the HRAM OAM-DMA routine ($FF80, called from ~10 sites) now
;     jumps to DmaHook; after the DMA, OAM attribute bits 0-2 are set from
;     the sprite slot's graphic id ($C580 list) or the player palette.
;   * DMG palette registers (fades/blanking): when BGP/OBP0/OBP1 change the
;     CGB palettes are rebuilt by mapping each DMG shade to the base color.

; ---------------------------------------------------------------- hardware
rKEY1   equ $4D
rVBK    equ $4F
rSVBK   equ $70
rBCPS   equ $68
rBCPD   equ $69
rOCPS   equ $6A
rOCPD   equ $6B
rLCDC   equ $40
rLY     equ $44
rBGP    equ $47
rOBP0   equ $48
rOBP1   equ $49
rP1     equ $00
rIE     equ $FF

; ---------------------------------------------------------------- game
GAME_INIT       equ $1AE2   ; original target of jp at $0150 / rst $00
OAM_DMA_HRAM    equ $FF80
HRAM_DMA_CORE   equ $FF83   ; our relocated DMA start+wait (A = source page)
EXEC_RETURN     equ $4B8F   ; bank1: tile program returns here (restores SP)
META_CONT       equ $066E   ; body of the metatile writer after 3 bytes
COPY64          equ $01A9   ; wait vblank + copy 64 bytes DE->HL
SPRITE_IDS      equ $C580   ; 16 sprite-slot graphic ids ($FF = continuation)
TILE_PROG       equ $D800   ; WRAM bank 1: generated tile program
MBC_BANK        equ $2100

; ---------------------------------------------------------------- ours
HR_DISPATCH     equ $FF98   ; bank-8 far-call index
HR_LCDMODE      equ $FF99   ; 0 = game LUT, 1 = castle title LUT, 9 = logo LUT
HR_SLOTG        equ $FF9A   ; scratch: graphic index in Slot
HR_CGB          equ $FF9B   ; 1 = CGB (set by Boot on every power-up; KEY1 is not
                            ;     a reliable DMG test on all emulators)

W2_BASE         equ $D000
OBJPAL          equ $D500   ; 128: palette per sprite graphic id (id & $7F)
BASE_BG         equ $D580   ; 8 x 4 BGR555 colours (DMG shade 0..3)
BASE_OBJ        equ $D5C0
LUT             equ $D600   ; 256: BG attribute per tile id (live)
LAST_BGP        equ $D700
LAST_OBP0       equ $D701
LAST_OBP1       equ $D702
LCD_MODE        equ $D703
SLOTG           equ $D7E0   ; 16: graphic index g of metatile slot s (debug/inspection)
SLOTPAL         equ $D7F0   ; 16: palette of metatile slot s
ATTR_PROG       equ $D800   ; translated attribute program
LUT_TITLE       equ $DC00   ; 256
LUT_GAME        equ $DD00   ; 256 (entries $00-$3F unused: from SLOTPAL)
LUT_LOGO        equ $DE00   ; 256
W2_IMAGE_LEN    equ $0F00
PLAYER_PAL      equ 0
OBP1_PAL        equ 7

BANK8_ORG       equ $4000
W2_IMAGE_ROM    equ $4400   ; bank 8 address of the WRAM2 image
METAPAL         equ $5800   ; bank 8: palette per metatile graphic (128)

; ======================================================== bank 0 free space
section bank0_a, $0003, $0003          ; $0003-$001F (29 bytes)
Far8Term:                               ; bank1:$4B3C -> writes terminator
        push af
        xor a
        jr Far8
Far8SlotInner:
        push af
        ld a, 1
Far8:                                   ; A = routine index, caller AF on stack
        ldh [HR_DISPATCH], a
        ld a, 8
        ld [MBC_BANK], a
        pop af
        call BANK8_ORG
        push af
        ld a, 1                         ; both callers live in bank 1
        ld [MBC_BANK], a
        pop af
        ret

section rst20, $0020, $0020            ; rst $20: logo dissolve copy (bank7:$4BD1)
        jp DissolveCopy
section rst28, $0028, $0028            ; rst $28: LCD on (game screens)
        jp LcdOnGame
section rst30, $0030, $0030            ; rst $30: LCD on (title screens)
LcdOnTitle:                             ; A = new LCDC value; LUT mode from it:
        push af                         ; $81 (castle, map $9800) -> 1
        and $09                         ; $89 (logo, map $9C00)   -> 9
        jr LcdOnCommon

section bank0_c, $0061, $0061           ; $0061-$00FF (159 bytes)
AttrRun:                                ; end of tile program (SP = VRAM, DI)
        ld a, 1
        ldh [rVBK], a
        inc a
        ldh [rSVBK], a
        jp ATTR_PROG

DmaHook:                                ; HRAM $FF80 now jumps here (all DMA sites)
        di                              ; original: di; DMA; wait; ei; ret
        ld a, $C0
        call HRAM_DMA_CORE
        ei
        ldh a, [HR_CGB]
        or a
        ret z                           ; DMG: done
        push bc
        push de
        push hl
        ldh a, [rSVBK]
        push af
        ld a, 2
        ldh [rSVBK], a
        call W2AfterDma
        pop af
        ldh [rSVBK], a
        pop hl
        pop de
        pop bc
        ret

LcdOnGame:                              ; rst $28: A = new LCDC value
        push af
        xor a
LcdOnCommon:
        ldh [HR_LCDMODE], a
        ldh a, [HR_CGB]
        or a
        jr z, .dmg
        push bc
        push de
        push hl
        ld a, 2
        ldh [rSVBK], a
        call W2LcdOn
        ld a, 1
        ldh [rSVBK], a
        pop hl
        pop de
        pop bc
.dmg:
        pop af
        ldh [rLCDC], a
        ret

MetaHook:                               ; $066B: A = tile, HL = map address
        call .orig
        push af
        push hl
        ldh a, [HR_CGB]
        or a
        jr z, .skip
        push bc
        push de
        ld a, 2
        ldh [rSVBK], a
        call W2Meta
        ld a, 1
        ldh [rSVBK], a
        pop de
        pop bc
.skip:
        pop hl
        pop af
        ret
.orig:
        ld [hl+], a
        add $02
        jp META_CONT

Far8Slot:                               ; bank1:$4F6C replaces call $01A9
        call Far8SlotInner
        jp COPY64

DissolveCopy:                           ; bank7:$4BD1 `ld a,[hl]; ld [de],a`
        ld a, [hl]                      ; copies map $98xx -> $9Cxx (LCD on,
        ld [de], a                      ; in VBlank); mirror the attribute
        ldh a, [HR_CGB]
        or a
        ret z
        ld a, 1                         ; (KEY1 reads $80/$FE: never assume)
        ldh [rVBK], a
        ld a, [hl]
        ld [de], a
        xor a
        ldh [rVBK], a
        ret

AttrDone:                               ; end of translated attribute program
        xor a
        ldh [rVBK], a
        inc a
        ldh [rSVBK], a
        jp EXEC_RETURN

Boot:                                   ; $0150: A = $11 on CGB
        cp $11
        jr nz, .dmg
        ld a, 8                         ; GAME_INIT selects its own banks
        ld [MBC_BANK], a
        jp Bank8Boot
.dmg:
        xor a
        ldh [HR_CGB], a
        jp GAME_INIT
Bank0End:

; ======================================================== patches in game code
section patch_boot, $0150, $0150
        jp Boot
section patch_hram_dma, $F35C, $735C    ; bank3:$735C, copied to $FF80 at init
        jp DmaHook                      ; $FF80
        ldh [$46], a                    ; $FF83 = HRAM_DMA_CORE (A = $C0)
        ld a, $28
.w:     dec a
        jr nz, .w
        ret
        nop
section patch_meta, $066B, $066B
        jp MetaHook
section patch_term, $4B3C, $4B3C        ; bank1:$4B3C (9 bytes)
        call Far8Term
        jr $4B45
        nop
        nop
        nop
        nop
section patch_slot, $4F6C, $4F6C        ; bank1:$4F6C
        call Far8Slot
section patch_dissolve, $1CBD1, $4BD1   ; bank7:$4BD1
        rst $20
        nop

; ======================================================== bank 8 (ROM)
section bank8, $20000, $4000
Dispatch:
        ldh a, [HR_DISPATCH]
        or a
        jp z, Term
        jp Slot

; -- write the tile-program terminator and build the attribute program.
; In: HL = tile program write pointer, BC/DE = fill registers (live).
; Preserves BC, DE.
Term:
        ldh a, [HR_CGB]
        or a
        jr nz, .cgb
        ld a, $C3                       ; DMG: original terminator jp $4B8F
        ld [hl+], a
        ld a, low(EXEC_RETURN)
        ld [hl+], a
        ld [hl], high(EXEC_RETURN)
        ret
.cgb:
        ld a, $C3
        ld [hl+], a
        ld a, low(AttrRun)
        ld [hl+], a
        ld [hl], high(AttrRun)
        push bc
        push de
        ld a, 2
        ldh [rSVBK], a
        ld h, high(LUT)
        ld l, c
        ld a, [hl]
        ld [ATTR_PROG+1], a
        ld l, b
        ld a, [hl]
        ld [ATTR_PROG+2], a
        ld l, e
        ld a, [hl]
        ld [ATTR_PROG+4], a
        ld l, d
        ld a, [hl]
        ld [ATTR_PROG+5], a
        ld a, $01
        ld [ATTR_PROG], a
        ld a, $11
        ld [ATTR_PROG+3], a
        ld de, ATTR_PROG+6
        ld hl, TILE_PROG
.loop:
        ld a, h                         ; safety: never read past $DB00
        cp $DB
        jr nc, .end
        ld a, 1
        ldh [rSVBK], a
        ld a, [hl+]
        cp $C5
        jr z, .one
        cp $D5
        jr z, .one
        cp $31
        jr z, .sp
        cp $01
        jr z, .bc
.end:                                   ; terminator (or unknown opcode)
        ld a, 2
        ldh [rSVBK], a
        ld a, $C3
        ld [de], a
        inc de
        ld a, low(AttrDone)
        ld [de], a
        inc de
        ld a, high(AttrDone)
        ld [de], a
        ld a, 1
        ldh [rSVBK], a
        pop de
        pop bc
        ret
.one:
        ld b, a
        ld a, 2
        ldh [rSVBK], a
        ld a, b
        ld [de], a
        inc de
        jr .loop
.sp:
        ld a, [hl+]
        ld c, a
        ld a, [hl+]
        ld b, a
        ld a, 2
        ldh [rSVBK], a
        ld a, $31
        ld [de], a
        inc de
        ld a, c
        ld [de], a
        inc de
        ld a, b
        ld [de], a
        inc de
        jr .loop
.bc:
        ld a, [hl+]
        ld c, a
        ld a, [hl+]
        ld b, a
        ld a, 2
        ldh [rSVBK], a
        ld a, $01
        ld [de], a
        inc de
        push hl
        ld h, high(LUT)
        ld l, c
        ld a, [hl]
        ld [de], a
        inc de
        ld l, b
        ld a, [hl]
        ld [de], a
        inc de
        pop hl
        jr .loop

; -- metatile slot loaded: DE = graphic source (bank 1), HL = $9000+s*64.
; Records the palette of the graphic for slot s. Preserves BC, DE, HL.
Slot:
        ldh a, [HR_CGB]
        or a
        ret z
        push bc
        push de
        push hl
        ld a, e                         ; DE -= $689B
        sub $9B
        ld e, a
        ld a, d
        sbc $68
        ld d, a
        ld a, e                         ; g = DE >> 6
        rlca
        rlca
        and $03
        ld e, a
        ld a, d
        add a
        add a
        or e
        and $7F
        ld c, a
        ldh [HR_SLOTG], a
        ld b, 0
        ld hl, METAPAL
        add hl, bc
        ld c, [hl]                      ; C = palette
        pop hl
        push hl
        ld a, l                         ; s = (HL - $9000) >> 6
        rlca
        rlca
        and $03
        ld e, a
        ld a, h
        sub $90
        add a
        add a
        or e
        and $0F
        ld e, a
        ld a, 2
        ldh [rSVBK], a
        ld a, e
        or low(SLOTPAL)
        ld l, a
        ld h, high(SLOTPAL)
        ld [hl], c
        ld a, l                         ; debug: SLOTG[s] = graphic index
        sub $10
        ld l, a
        ldh a, [HR_SLOTG]
        ld [hl], a
        ld a, [LCD_MODE]
        or a
        jr nz, .done
        ld a, e
        add a
        add a
        ld l, a
        ld h, high(LUT)
        ld a, c
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl], a
.done:
        ld a, 1
        ldh [rSVBK], a
        pop hl
        pop de
        pop bc
        ret

; -- CGB boot: double speed + WRAM2 runtime image. Entered (jp) with ROM bank 8.
Bank8Boot:
        di
        ld hl, W2_BASE                  ; confirm working WRAM banking (the
        ld a, 2                         ; runtime lives in WRAM bank 2): write
        ldh [rSVBK], a                  ; $A5 in bank 2, $5A in bank 1, read
        ld [hl], $A5                    ; bank 2 back. Some emulators report
        dec a                           ; A=$11 or echo VBK in DMG mode.
        ldh [rSVBK], a
        ld [hl], $5A
        inc a
        ldh [rSVBK], a
        ld a, [hl]
        cp $A5
        jr nz, .notcgb1
        ld a, 1
        ldh [rSVBK], a
        jr .wait
.notcgb1:
        ld a, 1
        ldh [rSVBK], a
.notcgb:
        xor a
        ldh [HR_CGB], a
        jp GAME_INIT
.wait:                                  ; LCD off (boot ROM leaves it on)
        ldh a, [rLCDC]
        bit 7, a
        jr z, .off
        ldh a, [rLY]
        cp 145
        jr nz, .wait
        xor a
        ldh [rLCDC], a
.off:
        ld a, 1
        ldh [HR_CGB], a
        xor a
        ldh [rIE], a
        ld a, $30
        ldh [rP1], a
        ld a, 1
        ldh [rKEY1], a
        stop
        ld a, 2
        ldh [rSVBK], a
        ld hl, W2_IMAGE_ROM
        ld de, W2_BASE
        ld bc, W2_IMAGE_LEN
.copy:
        ld a, [hl+]
        ld [de], a
        inc de
        dec bc
        ld a, b
        or c
        jr nz, .copy
        ld a, 1
        ldh [rSVBK], a
        jp GAME_INIT
Bank8CodeEnd:

; ======================================================== WRAM bank 2 image
section wram2, $20400, $D000

; -- after every OAM DMA (VBlank): palette sync on DMG-register change,
; then OBJ palette bits in OAM.
W2AfterDma:
        ldh a, [rBGP]
        ld hl, LAST_BGP
        cp [hl]
        call nz, SyncBG
        ldh a, [rOBP0]
        ld hl, LAST_OBP0
        cp [hl]
        jr nz, .obj
        ldh a, [rOBP1]
        inc hl
        cp [hl]
        jr z, .oam
.obj:
        call SyncOBJ
.oam:
        ld hl, $FE00
        ld b, 40
.o:
        ld a, [hl+]                     ; Y
        or a
        jr z, .hide
        inc l                           ; skip X
        ld a, [hl+]                     ; tile; HL -> attribute
        sub $80
        jr c, .player
        rrca
        rrca
        rrca
        and $0F
        or low(SPRITE_IDS)
        ld e, a
        ld d, high(SPRITE_IDS)
.back:
        ld a, [de]
        cp $FF
        jr nz, .got
        dec e
        bit 7, e
        jr nz, .back
        xor a
.got:
        and $7F
        ld e, a
        ld d, high(OBJPAL)
        ld a, [de]
        jr .apply
.player:
        ld a, PLAYER_PAL
.apply:
        ld c, a
        ld a, [hl]
        bit 4, a
        jr z, .p0
        ld c, OBP1_PAL
.p0:
        and $F0
        or c
        ld [hl+], a
        dec b
        jr nz, .o
        ret
.hide:
        inc l
        inc l
        inc l
        dec b
        jr nz, .o
        ret

; A = BGP. Rebuild the 8 BG palettes.
SyncBG:
        ld [LAST_BGP], a
        ld d, a
        ld a, $80
        ldh [rBCPS], a
        ld hl, BASE_BG
        ld b, 8
        ld c, rBCPD
        jp SyncGroup

; Rebuild OBJ palettes 0-6 from OBP0 and 7 from OBP1.
SyncOBJ:
        ldh a, [rOBP1]
        ld [LAST_OBP1], a
        ldh a, [rOBP0]
        ld [LAST_OBP0], a
        ld d, a
        ld a, $80
        ldh [rOCPS], a
        ld hl, BASE_OBJ
        ld b, 7
        ld c, rOCPD
        call SyncGroup
        ld a, [LAST_OBP1]
        ld d, a
        ld b, 1
; HL = base colours (4 per palette, index = DMG shade), B = count,
; D = DMG palette register value, C = data port. Advances HL.
SyncGroup:
.pal:
        ld e, d
        push bc
        ld b, 4
.col:
        ld a, e
        and $03
        add a
        push hl
        add l
        ld l, a
        ld a, [hl+]
        ldh [c], a
        ld a, [hl]
        ldh [c], a
        pop hl
        srl e
        srl e
        dec b
        jr nz, .col
        pop bc
        ld a, l
        add 8
        ld l, a
        dec b
        jr nz, .pal
        ret

; -- LCD about to be switched on (HR_LCDMODE: 0 game, 1 title).
W2LcdOn:
        ldh a, [rLCDC]
        bit 7, a
        ret nz                          ; already on: nothing safe to do
        ldh a, [HR_LCDMODE]
        ld hl, LCD_MODE
        cp [hl]
        ld [hl], a
        call nz, BuildLut
        ldh a, [rBGP]
        call SyncBG
        call SyncOBJ
; Recompute attributes of both BG maps from their tile ids (LCD off).
FillAttrs:
        ld hl, $9800
        ld d, high(LUT)
.loop:
        xor a
        ldh [rVBK], a
        ld e, [hl]
        inc a
        ldh [rVBK], a
        ld a, [de]
        ld [hl+], a
        ld a, h
        cp $A0
        jr nz, .loop
        xor a
        ldh [rVBK], a
        ret

; Rebuild the live LUT for LCD_MODE.
BuildLut:
        ld a, [LCD_MODE]
        or a
        jr z, .game
        ld hl, LUT_TITLE
        dec a
        jr z, .t0
        ld hl, LUT_LOGO
.t0:
        ld de, LUT
.t:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .t
        ret
.game:
        ld hl, LUT_GAME + $40
        ld de, LUT + $40
.g:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .g
        ld hl, SLOTPAL
        ld de, LUT
.s:
        ld a, [hl+]
        ld [de], a
        inc e
        ld [de], a
        inc e
        ld [de], a
        inc e
        ld [de], a
        inc e
        ld a, e
        cp $40
        jr nz, .s
        ret

; -- single metatile written by $066B. HL = map address + $21,
; stack: [ret][de][bc][hl][af: A = tile + 4].
W2Meta:
        ld a, l
        sub $21
        ld e, a
        ld a, h
        sbc 0
        ld d, a                         ; DE = map address
        cp $98
        ret c
        cp $A0
        ret nc
        ld hl, sp+9
        ld a, [hl]
        sub 4
        ld c, a                         ; C = tile
        ld h, high(LUT)
        ld a, 1
        ldh [rVBK], a
        ld l, c
        ld a, [hl]
        ld [de], a
        inc de
        inc c
        inc c
        ld l, c
        ld a, [hl]
        ld [de], a
        ld a, e
        add $1F
        ld e, a
        ld a, d
        adc 0
        ld d, a
        dec c
        ld l, c
        ld a, [hl]
        ld [de], a
        inc de
        inc c
        inc c
        ld l, c
        ld a, [hl]
        ld [de], a
        xor a
        ldh [rVBK], a
        ret
W2CodeEnd:
