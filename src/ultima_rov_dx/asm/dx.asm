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
rSCX    equ $43
rWX     equ $4B
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
SPRITE_COUNT    equ $C539   ; sprite slots in use (bank 0 $291B loader)
TILE_PROG       equ $D800   ; WRAM bank 1: generated tile program
MBC_BANK        equ $2100

; ---------------------------------------------------------------- ours
HR_DISPATCH     equ $FF98   ; bank-8 far-call index
HR_LCDMODE      equ $FF99   ; 0 = game site (mode byte decides map/text), 1 = castle title, 9 = logo
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
CUR_THEME       equ $D704   ; area theme currently loaded into BASE_BG
ENTRANCE_THEME  equ $D705   ; theme of dungeon title cards + entrance cutscene (set by builder)
LCD_BYTE        equ $D706   ; mode byte of the last game LCD-on site
MAP_THEME       equ $D707   ; area theme of the play field (set by Slot, restored at map LCD-on)
UI_THEME        equ $D710   ; theme of text screens, dialogs and the start menu (set by builder)
LIVE_K          equ $D711   ; frame counter: start-menu slot pair refreshed this frame
LIVE_R          equ $D712   ; next side-panel cell (0-35) refreshed after the OAM DMA
SHIP_PAL        equ $D713   ; OBJ palette of the ship sprite while sailing (set by builder)
SWEEP_LO        equ $D714   ; map attribute sweep: next $98xx/$9Bxx cell, SWEEP_HI = 0 idle
SWEEP_HI        equ $D715
FIRE_OBJ        equ $DFF0   ; 4 colours of the wand's fireball (OBJ palette 7 on map screens, via OBP0)
FIRE_TILES      equ $38     ; wand projectile tiles $38-$47 (items $06-$08, either button)
FIRE_PAL        equ 7
SWEEP_CELLS     equ 16      ; cells per frame (replaces the 4-cell side-panel refresh)
STAND_G         equ $FF96   ; graphic under the player ($2B = ship, bank 0 $2331)
SHIP_G          equ $2B
MENU_OBJ        equ $D718   ; 4 colours of the start-menu cursor (OBJ palette 7 in menu mode)
HR_BACKUP       equ $D720   ; 12: HRAM bytes under HELPER while it is installed
TEXT_RANGES     equ $D72C   ; 20: text screens, then champion select: count, (first, last, palette)*
TEXT_RANGES_LEN equ 20
ITEM_PAL        equ $D740   ; 64: BG palette per item id (inventory / side-panel icons)
INV             equ $D780   ; 64: copy of WRAM1 $D100-$D13F (inventory $D100-$D11F, B $D125, A $D126, armour $D134)
FLAT_BG         equ $D708   ; 4 colours used when a DMG palette maps every shade alike (blank/fade)
SLOTG           equ $D7E0   ; 16: graphic index g of metatile slot s (debug/inspection)
SLOTPAL         equ $D7F0   ; 16: palette of metatile slot s
ATTR_PROG       equ $D800   ; translated attribute program
LUT_MENU        equ $DC00   ; 256: start menu (items overlaid from ITEM_PAL at LCD-on)
LUT_GAME        equ $DD00   ; 256 (entries $00-$3F unused: from SLOTPAL)
BG_THEMES       equ $DE00   ; 8 x 64: BG base colours per theme
W2_IMAGE_LEN    equ $1000
MAX_THEMES      equ 4           ; BG_THEMES $DE00-$DEFF; $DF00-$DFFF holds W2 code (section wram2b)
HELPER          equ $FFF3   ; 12 bytes of HRAM: reads WRAM bank 1 for WRAM2 code (installed only while used)
CURSOR_PAL      equ 7
PLAYER_PAL      equ 0
OBP1_PAL        equ 7

BANK8_ORG       equ $4000
W2_IMAGE_ROM    equ $4400   ; bank 8 address of the WRAM2 image
AREA_THEME      equ $5400   ; bank 8: theme index per area id [$D12F] (256)
PICTURE_LUT     equ $5600   ; bank 8: tile -> BG palette for the dungeon-entrance cutscene (256)
PICTURE_FIX     equ $5700   ; bank 8: attribute fixups (VRAM lo, hi, attr)..., hi = 0 ends (<= 256 bytes)
PICTURE_BANK    equ 7       ; ROM bank of the (only) picture LCD-on site, restored after the copy
METAPAL         equ $5800   ; bank 8: palette per metatile graphic, 128 per theme (8 themes)
LUT_TITLE_ROM   equ $5C00   ; bank 8: castle title LUT (256), copied at the bank-7 title LCD-on
LUT_LOGO_ROM    equ $5D00   ; bank 8: logo LUT (256)
TITLE_BANK      equ 7       ; ROM bank of the title and picture LCD-on sites
AREA_ID         equ $D12F   ; WRAM bank 1: current area/map id

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
HudExit:                                ; $0035: back from W2Hud (A = 1)
        ldh [rSVBK], a
        ret

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
        ldh a, [rSVBK]
        push af
        ld a, 2
        ldh [rSVBK], a
        call W2AfterDma                 ; (saves BC, DE, HL itself)
        pop af
        ldh [rSVBK], a
        ret

LcdOnGame:                              ; rst $28: A = new LCDC value
        push af
        xor a
LcdOnCommon:
        ldh [HR_LCDMODE], a
        ldh a, [HR_CGB]
        or a
        jr z, .dmg
        ld a, 2
        ldh [rSVBK], a
        call W2LcdOn                    ; (saves BC, DE, HL itself)
        ld a, 1
        ldh [rSVBK], a
.dmg:
        pop af
        ldh [rLCDC], a
        ret

MetaHook:                               ; $066B: A = tile, HL = map address
        call .orig
        push af
        ldh a, [HR_CGB]
        or a
        jr z, .skip
        ld a, 2
        ldh [rSVBK], a
        call W2MetaW                    ; (saves BC, DE, HL itself)
        ld a, 1
        ldh [rSVBK], a
.skip:
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

HudTramp:                               ; tail of $04C1 (A/B item icons copied)
        ld a, 1                         ; original: select bank 1, ret
        ld [MBC_BANK], a
        ldh a, [HR_CGB]
        or a
        ret z
        ld hl, $D125
        ld e, [hl]                      ; E = B item, D = A item
        inc l
        ld d, [hl]
        inc a
        ldh [rSVBK], a
        jp W2Hud                        ; returns through HudExit

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
section patch_hud_icons, $04E6, $04E6   ; $04E6: call $01A9; ld a,1; ld [$2100],a; ret
        call COPY64
        jp HudTramp
        nop
        nop
        nop
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
        ldh [HR_SLOTG], a
        ld a, [AREA_ID]                 ; theme of the current area
        ld l, a
        ld h, high(AREA_THEME)
        ld a, [hl]
        push af
        ld b, a                         ; HL = METAPAL + theme*128 + g
        rrca
        and $80
        ld c, a
        ld a, b
        srl a
        add high(METAPAL)
        ld h, a
        ldh a, [HR_SLOTG]
        or c
        ld l, a
        ld c, [hl]                      ; C = palette
        ld a, 2
        ldh [rSVBK], a
        pop af
        ld [MAP_THEME], a
        call SetTheme                   ; (WRAM2) new area theme -> BASE_BG
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
        ldh a, [rLCDC]                  ; LCD on: cells already on the map keep
        bit 7, a                        ; the old palette -> sweep them
        jr z, .done
        xor a
        ld [SWEEP_LO], a
        ld a, $98
        ld [SWEEP_HI], a
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
        push bc
        push de
        push hl
        call W2AfterDmaBody
        pop hl
        pop de
        pop bc
        ret
W2AfterDmaBody:
        call W2Pal
        ld a, [LCD_MODE]                ; live refresh of attributes that the
        or a                            ; game changes with the LCD on: side
        jr z, .live                     ; panel (hearts/stars/equipped items)
        cp 4                            ; and start-menu item slots
        jr z, .live
        cp 5
        ret nz
.live:
        ldh a, [rLCDC]
        bit 7, a
        ret z
        ldh a, [rLY]
        cp 144
        ret c                           ; not in VBlank: try next frame
        di
        call HelperOn
        ld hl, $D125
        call HELPER
        ld [INV+$25], a
        call HELPER
        ld [INV+$26], a
        ld a, [LIVE_K]
        inc a
        ld [LIVE_K], a
        and $0F
        add a
        ld c, a                         ; menu: slots c, c+1
        ld l, a
        ld h, $D1
        call HELPER
        ld e, a
        call HELPER
        ld d, a
        push de
        call HelperOff
        pop de
        ei
        ld a, [LCD_MODE]
        cp 4
        jr nz, .hud
        ld h, high(INV)
        ld a, c
        add low(INV)
        ld l, a
        ld [hl], e
        inc l
        ld [hl], d
        ld a, c
        call SlotLut
        ld a, c
        call SlotCells
        inc c
        ld a, c
        call SlotLut
        ld a, c
        call SlotCells
.hud:
        call HudItemsLut
        ld a, [SWEEP_HI]                ; map attribute sweep pending (slots
        or a                            ; reloaded with the LCD on): it takes
        jp nz, Sweep                    ; the side-panel refresh's VBlank time
; 4 side-panel cells per frame (36 cells: rows 0-17, 2 columns)
        ld a, [LIVE_R]
        ld c, a
        ld b, 4
.n:
        push bc
        ld a, c
        call HudCell
        pop bc
        inc c
        ld a, c
        cp 36
        jr c, .k
        ld c, 0
.k:
        dec b
        jr nz, .n
        ld a, c
        ld [LIVE_R], a
        ret

; palette sync on DMG-register change, then OBJ palette bits in OAM.
W2Pal:
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
        ld e, a                         ; slot at or past the loaded count ($C539):
        ld a, [SPRITE_COUNT]            ; not a monster. The champion's attack
        cp e                            ; pose uses tiles $E0-$EF (slots 12-13),
        jr c, .unl                      ; the sailing ship $B8-$BF (slot 7)
        jr z, .unl
        ld a, e
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
.unl:
        call UnloadedPal
        jr .apply
.player:
        dec l
        ld a, [hl]                      ; E = tile
        inc l
        ld e, a
        ld a, [LCD_MODE]
        cp 4
        jr z, .menu
        or a
        jr nz, .pl
        ld a, e                         ; map: the wand's fireball
        sub FIRE_TILES
        cp 16
        jr nc, .pl
        ld a, FIRE_PAL
        jr .apply
.menu:
        ld a, e                         ; start menu: cursor (tiles 0-3) gets
        cp 4                            ; its own palette
        jr nc, .pl
        ld a, CURSOR_PAL
        jr .apply
.pl:
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
        ld a, [LCD_MODE]                ; start menu: palette 7 = cursor colours,
        cp 4                            ; map: fireball colours, both mapped
        jr z, .menu                     ; through OBP0
        or a
        jr nz, SyncGroup
        ld hl, FIRE_OBJ
        jr .o0
.menu:
        ld hl, MENU_OBJ
.o0:
        ld a, [LAST_OBP0]
        ld d, a
; HL = base colours (4 per palette, index = DMG shade), B = count,
; D = DMG palette register value, C = data port. Advances HL.
SyncGroup:
        ld a, d                         ; all four shades alike (blank/fade)?
        rrca
        rrca
        cp d
        jr z, .flat
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
.flat:                                  ; every colour of B palettes = FLAT_BG[shade]
        push hl
        ld a, d
        and $03
        add a
        add low(FLAT_BG)
        ld l, a
        ld h, high(FLAT_BG)
        ld a, [hl+]
        ld e, a
        ld d, [hl]
        pop hl
.fp:
        push bc
        ld b, 4
.fc:
        ld a, e
        ldh [c], a
        ld a, d
        ldh [c], a
        dec b
        jr nz, .fc
        pop bc
        ld a, l
        add 8
        ld l, a
        dec b
        jr nz, .fp
        ret

; -- LCD about to be switched on (HR_LCDMODE: 0 game, 1 title).
; Game sites are patched `rst $28` + one mode byte that is also a harmless
; opcode: $00 (nop) = map screen, $40 (ld b,b) = text screen, $49 (ld c,c) =
; dungeon title card (text + entrance theme), $52 (ld d,d) = entrance
; cutscene picture (PICTURE_LUT + entrance theme, bank-7 site only),
; $5B (ld e,e) = blank screen (text + surface theme). Stack here:
; [ret][hl][de][bc][af][rst return -> mode byte].
; LCD_MODE: 0 map, 1 castle title, 2 text, 3 picture, 9 logo.
W2LcdOn:
        push bc
        push de
        push hl
        call W2LcdOnBody
        pop hl
        pop de
        pop bc
        ret
W2LcdOnBody:
        ldh a, [rLCDC]
        bit 7, a
        ret nz                          ; already on: nothing safe to do
        xor a
        ld [LCD_BYTE], a
        ldh a, [HR_LCDMODE]
        or a
        jr nz, .have
        ld hl, sp+12                    ; [ret][hl][de][bc][ret][af][rst ret]
        ld a, [hl+]
        ld h, [hl]
        ld l, a
        ld a, [hl]                      ; mode byte (caller's ROM bank is mapped)
        ld [LCD_BYTE], a
        or a
        jr z, .have
        ld b, 3                         ; picture
        cp $52
        jr z, .b
        inc b                           ; 4 start menu
        cp $64
        jr z, .b
        inc b                           ; 5 dialog
        cp $6D
        jr z, .b
        ld b, 2                         ; text screen
.b:
        ld a, b
.have:
        ld [LCD_MODE], a
        call BuildLut
        ld a, [LCD_MODE]                ; theme for the new screen
        or a
        jr z, .map                      ; map: the area theme
        cp 1
        jr z, .t0                       ; title screens: surface theme
        cp 9
        jr z, .t0
        cp 3
        jr z, .ent
        cp 2
        jr nz, .ui                      ; menu, dialog: UI theme
        ld a, [LCD_BYTE]
        cp $49
        jr z, .ent
        cp $5B
        jr z, .t0
.ui:
        ld a, [UI_THEME]
        jr .set
.map:
        ld a, [MAP_THEME]
        jr .set
.t0:
        xor a
        jr .set
.ent:
        ld a, [ENTRANCE_THEME]
.set:
        call SetTheme
        ldh a, [rBGP]
        call SyncBG
        call SyncOBJ
        ld a, [LCD_BYTE]                ; blank screen: UI colour 0 -> flat white,
        cp $5B                          ; matching the LCD-off frames around it
        jr nz, .attrs
        ld a, $80
        ldh [rBCPS], a
        ld a, [FLAT_BG]
        ldh [rBCPD], a
        ld a, [FLAT_BG+1]
        ldh [rBCPD], a
.attrs:
        call FillAttrs
        ld a, [LCD_MODE]
        cp 3
        ret nz
; Picture: map cells whose tile id is shared by two regions get their own
; attribute (list in bank 8), then the caller's bank 7 is mapped back.
        ld a, 8
        ld [MBC_BANK], a
        ld hl, PICTURE_FIX
        ld a, 1
        ldh [rVBK], a
.fix:
        ld e, [hl]
        inc hl
        ld a, [hl+]
        or a
        jr z, .fixed
        ld d, a
        ld a, [hl+]
        ld [de], a
        jr .fix
.fixed:
        xor a
        ldh [rVBK], a
        ld a, TITLE_BANK
        ld [MBC_BANK], a
        ret
; Recompute attributes of both BG maps from their tile ids (LCD off).
FillAttrs:
        xor a                           ; full recompute: no sweep needed
        ld [SWEEP_HI], a
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

; A = area theme. Loads its BG base colours and forces a CRAM resync at
; the next OAM DMA (VBlank) if it differs from the current one. SVBK = 2.
SetTheme:
        ld hl, CUR_THEME
        cp [hl]
        ret z
        ld [hl], a
        rrca                            ; DE = BG_THEMES + theme*64
        rrca
        ld b, a
        and $C0
        ld e, a
        ld a, b
        and $07
        add high(BG_THEMES)
        ld d, a
        ld hl, BASE_BG
        ld b, 64
.c:
        ld a, [de]
        ld [hl+], a
        inc e
        dec b
        jr nz, .c
        ld a, [LAST_BGP]
        cpl
        ld [LAST_BGP], a
        ret

; Rebuild the live LUT for LCD_MODE.
BuildLut:
        ld a, [LCD_MODE]
        or a
        jp z, .game
        dec a
        jr z, .castle
        dec a
        jr z, .text
        dec a
        jr z, .pic
        dec a
        jr z, .menu
        dec a
        jr z, .dialog
        ld hl, LUT_LOGO_ROM             ; 9: logo
        jr .rom
.castle:
        ld hl, LUT_TITLE_ROM
        jr .rom
.pic:                                   ; entrance cutscene
        ld hl, PICTURE_LUT
.rom:                                   ; LUT from bank 8; bank-7 sites only
        ld a, 8
        ld [MBC_BANK], a
        ld de, LUT
.t:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .t
        ld a, TITLE_BANK
        ld [MBC_BANK], a
        ret
.menu:                                  ; start menu: base LUT + item icons
        ld hl, LUT_MENU
        ld de, LUT
.m:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .m
        call ReadInv
        call HudItemsLut
        ld c, 0
.ms:
        ld a, c
        call SlotLut
        inc c
        ld a, c
        cp 32
        jr nz, .ms
        ld a, [INV+$34]                 ; armour icon, tiles $BC-$BF
        call ItemPal
        ld hl, LUT+$BC
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl], a
        ret
.dialog:                                ; dialog: UI palette + side panel
        call .text
        ld hl, LUT_MENU+$E4
        ld de, LUT+$E4
.d:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .d
        call ReadInv
        jp HudItemsLut
.text:                                  ; text screens: UI palette, then box frames and
        ld a, [LUT_GAME + $FF]          ; portraits from TEXT_RANGES (champion select:
        ld hl, LUT                      ; its own ranges on top)
.x:
        ld [hl], a
        inc l
        jr nz, .x
        ld hl, TEXT_RANGES
        call TileRanges
        ld a, [LCD_BYTE]
        cp $7F
        ret nz
        jp TileRanges
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
        call ReadInv
        jp HudItemsLut

; HL = count, (first, last, palette)*: LUT[first..last] = palette. Advances HL.
TileRanges:
        ld a, [hl+]
        or a
        ret z
        ld b, a
.r:
        ld a, [hl+]
        ld e, a
        ld a, [hl+]
        ld c, a
        ld a, [hl+]
        push hl
        ld h, high(LUT)
        ld l, e
.f:
        ld [hl], a
        ld d, a
        ld a, l                         ; A = this tile (flags from cp, not inc)
        inc l
        cp c
        ld a, d
        jr nz, .f
        pop hl
        dec b
        jr nz, .r
        ret

; ---- inventory helpers. WRAM2 code cannot see WRAM bank 1 ($D1xx), so a
; 12-byte reader is placed in HRAM while needed (the bytes under it are
; saved and put back).
HelperOn:
        ld hl, HELPER
        ld de, HR_BACKUP
        ld bc, HelperCode
.l:
        ld a, [hl]
        ld [de], a
        ld a, [bc]
        ld [hl+], a
        inc de
        inc bc
        ld a, l
        cp $FF
        jr nz, .l
        ret
HelperOff:
        ld hl, HELPER
        ld de, HR_BACKUP
.l:
        ld a, [de]
        ld [hl+], a
        inc de
        ld a, l
        cp $FF
        jr nz, .l
        ret
HelperCode:                             ; A = B = [HL+] of WRAM bank 1
        ld a, 1
        ldh [rSVBK], a
        ld a, [hl+]
        ld b, a
        ld a, 2
        ldh [rSVBK], a
        ld a, b
        ret
; INV = WRAM1 $D100-$D13F (LCD off: no VBlank interrupt can nest).
ReadInv:
        call HelperOn
        ld hl, $D100
        ld de, INV
.r:
        call HELPER
        ld [de], a
        inc e
        ld a, l
        cp $40
        jr nz, .r
        jp HelperOff
; A = item id -> A = BG palette. Clobbers HL.
ItemPal:
        cp $FF
        jr z, .none
        and $3F
        add low(ITEM_PAL)
        ld l, a
        ld h, high(ITEM_PAL)
        ld a, [hl]
        ret
.none:
        ld a, [LUT_GAME + $FF]
        ret
; LUT[$F8-$FB] = palette of the A item, LUT[$FC-$FF] = B item.
HudItemsLut:
        ld a, [INV+$26]
        call ItemPal
        ld hl, LUT+$F8
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        push hl
        ld a, [INV+$25]
        call ItemPal
        pop hl
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl], a
        ret
; A = inventory slot c (0-31): LUT[4*(c+3)..+3] = palette of INV[c]. Keeps C.
SlotLut:
        ld b, a
        add low(INV)
        ld l, a
        ld h, high(INV)
        ld a, [hl]
        call ItemPal
        ld e, a
        ld a, b
        add 3
        add a
        add a
        ld l, a
        ld h, high(LUT)
        ld a, e
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl], a
        ret
; A = slot c: rewrite the attributes of its 2x2 cells at $9C25 + (c&7)*2
; + (c&$18)*8 (bank 0 $1027-$108C layout). Keeps C.
SlotCells:
        ld b, a
        and $07
        add a
        add $25
        ld l, a
        ld a, b
        and $18
        add a
        add a
        add a
        add l
        ld l, a
        ld h, $9C
        call Cell
        inc hl
        call Cell
        ld a, l
        add 31
        ld l, a
        ld a, h
        adc 0
        ld h, a
        call Cell
        inc hl
; HL = map cell: attribute = LUT[tile]. Keeps HL; clobbers A, DE.
Cell:
        xor a
        ldh [rVBK], a
        ld e, [hl]
        ld d, high(LUT)
        ld a, [de]
        ld d, a
        ld a, 1
        ldh [rVBK], a
        ld [hl], d
        xor a
        ldh [rVBK], a
        ret
; A = side-panel cell r (0-35: row r/2, column r&1). The panel is the
; window (LCDC bit 5, WX < 160) at its column 0, else BG columns
; SCX/8+18.. (start menu, dialogs).
HudCell:
        ld b, a
        ldh a, [rLCDC]
        ld d, a
        and $20
        jr z, .bg
        ldh a, [rWX]
        cp 160
        jr nc, .bg
        ld e, 0
        ld a, d
        and $40
        jr .map
.bg:
        ldh a, [rSCX]
        rrca
        rrca
        rrca
        and $1F
        add 18
        ld e, a
        ld a, d
        and $08
.map:
        ld h, $98
        jr z, .h
        ld h, $9C
.h:
        ld a, b
        and 1
        add e
        and $1F
        ld e, a
        ld a, b
        srl a
        ld c, a
        and $07
        swap a
        add a
        or e
        ld l, a
        ld a, c
        rrca
        rrca
        rrca
        and $03
        add h
        ld h, a
        jr Cell

; -- $04C1 copied the A/B item icons (bank 0 HudTramp; D = A item, E = B
; item). Right after the copy we are in VBlank or the LCD is off: recolour
; the icon cells now. In the start menu (no OAM DMA while idle) also the
; slot under the cursor, whose item was just swapped. Exits via HudExit.
W2Hud:
        push bc
        ld a, e
        ld [INV+$25], a
        ld a, d
        ld [INV+$26], a
        ldh a, [rLCDC]
        bit 7, a
        jr z, .ok
        ldh a, [rLY]
        cp 144
        jr c, .out
.ok:
        ld a, [LCD_MODE]
        or a
        jr z, .go
        cp 5
        jr z, .go
        cp 4
        jr nz, .out
        call HelperOn                   ; menu: no DMA from the VBlank ISR
        ldh a, [$FF8F]                  ; cursor slot (bank 0 $10AB)
        and $1F
        ld c, a
        ld l, a
        ld h, $D1
        call HELPER
        push af
        call HelperOff
        pop af
        ld b, a
        ld h, high(INV)
        ld a, c
        add low(INV)
        ld l, a
        ld [hl], b
        ld a, c
        call SlotLut
        ld a, c
        call SlotCells
.go:
        call HudItemsLut
        ld c, 2                         ; side-panel rows 1-5 (A and B icons)
.h:
        ld a, c
        push bc
        call HudCell
        pop bc
        inc c
        ld a, c
        cp 12
        jr nz, .h
.out:
        pop bc
        ld a, 1
        jp HudExit

W2CodeEnd:

; ======================================================== WRAM bank 2, $DF00-$DFFF
section wram2b, $21300, $DF00

; A = OBJ palette of a sprite tile in a slot the loader has not filled
; ($C539 count): the champion (attack pose), or the ship while sailing.
UnloadedPal:
        ldh a, [STAND_G]
        cp SHIP_G
        ld a, PLAYER_PAL
        ret nz
        ld a, [SHIP_PAL]
        ret

; Map attributes after metatile slots were reloaded with the LCD on (ship
; voyage into a new area, bank 8 Slot): the whole $9800 area map still
; carries the old slots' palettes. Rewrites SWEEP_CELLS cells per frame from
; the LUT while in VBlank (A = SWEEP_HI on entry). About one second per sweep.
Sweep:
        ld h, a
        ld a, [SWEEP_LO]
        ld l, a
        ld d, high(LUT)
        ld c, SWEEP_CELLS
.c:
        ldh a, [rLY]                    ; VBlank over: stop, resume next frame
        cp 144
        jr c, .save
        xor a
        ldh [rVBK], a
        ld e, [hl]
        ld a, [de]
        ld b, a
        ld a, 1
        ldh [rVBK], a
        ld [hl], b
        inc hl
        ld a, h
        cp $9C
        jr z, .done
        dec c
        jr nz, .c
.save:
        xor a
        ldh [rVBK], a
        ld a, l
        ld [SWEEP_LO], a
        ld a, h
        ld [SWEEP_HI], a
        ret
.done:
        xor a
        ldh [rVBK], a
        ld [SWEEP_HI], a
        ret

W2MetaW:
        push hl
        push bc
        push de
        call W2Meta
        pop de
        pop bc
        pop hl
        ret
; -- single metatile written by $066B. HL = map address + $21,
; stack: [ret][de][bc][hl][ret][af: A = tile + 4].
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
        ld hl, sp+11
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
W2bEnd:
