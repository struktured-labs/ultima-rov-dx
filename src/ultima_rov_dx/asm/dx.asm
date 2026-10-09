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
HR_VBLANK       equ $FF8E   ; game: set by its VBlank interrupt, cleared at its idle waits
PARADE_LIST     equ $FF9C   ; low byte of the parade's graphic list (bank 7 $7CA6 + 5k), set by ParadeLoad (also on DMG: unused HRAM)
PARADE_ON       equ $FF9D   ; 1 = the attract-loop parade is up: OamPass colours its sprites from PARADE_TAB (CGB)
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
MAP_CACHED      equ $D716   ; ROM theme held in WRAM slot SLOT_MAP ($FF = none; set by bank-8 MapTheme)
HERO_CACHED     equ $D717   ; champion whose colours are in OBJ palette 0 ($FF = none; set by bank-8 HeroObj)
THEME_OBJ       equ $DFD0   ; 4 slots x 4 colours of OBJ palette THEME_OBJ_SLOT (per-theme override; no obj_themes are set: knights stay royal everywhere)
THEME_OBJ_SLOT  equ 5       ; royal
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
REC_TIER        equ $D7C0   ; 16: colour tier 0-2 of object record i ($D000+16i), set by the bank-2 AllocHook
MONSTER_PAL     equ 1       ; OBJ palettes 1-3: monster tiers base / stronger / strongest (TierPal adds the tier)
ENTRY_TIER      equ $DB10   ; 40: tier per OAM entry (TierEnd, from REC_TIER and [record+3]; read by TierPal)
ITEM_IDS        equ $C5B0   ; WRAM0: item id of floor-item slot k (BG tiles $40+4k-$43+4k; $FF = empty)
ITEM_CACHE      equ $D7D0   ; 15: ITEM_IDS as last coloured (low byte = low(ITEM_IDS) + $20)
PREP_DONE       equ $D7DF   ; 1 = Prep8 coloured the shadow OAM since the last DMA (the hook skips its OAM pass)
PREP_LY         equ 128     ; Prep8 runs only below this line (or past 145): done before VBlank
FLOOR_TILES     equ $40
FLOOR_SLOTS     equ 15      ; bank 0 $1450/$2721: slots $C5B0-$C5BE -> tiles $40-$7B
W2C_ORG         equ $DB40   ; WRAM2 code section wram2c (past the longest attribute program, $DB0F)
TEMPLATE_BASE   equ $55AF   ; bank 1: 9-byte object templates (alt group at $580A = template 67)
SPAWN_RET       equ $2898   ; return address of the template spawner's call $5FE6 (bank 0 $2895)
CLONE_RET       equ $5B4A   ; return address of the record cloner's call $5FE6 (bank 2 $5B47)
ALLOC_REST      equ $5FE9   ; bank 2 allocator after its first instruction (ld bc,$d000)
TIER_TAB        equ $7FBA   ; bank 2: nibble per template (monsters.tier_table), after section bank2_alloc
LUT_MENU        equ $DC00   ; 256: start menu (items overlaid from ITEM_PAL at LCD-on)
LUT_GAME        equ $DD00   ; 256 (entries $00-$3F unused: from SLOTPAL)
BG_THEMES       equ $DE00   ; 4 slots x 64: BG base colours (0 surface, 1 current dungeon, 2 entrance, 3 UI)
W2_IMAGE_LEN    equ $1000
MAX_THEMES      equ 4           ; WRAM theme slots: BG_THEMES $DE00-$DEFF; $DF00-$DFFF holds W2 code (section wram2b)
SLOT_MAP        equ 1           ; WRAM slot that caches the current dungeon's ROM theme
ROM_THEMES      equ 32          ; themes in bank 8 (THEME_BG_ROM, THEME_OBJ_ROM, RT_SLOT, MP_IDX)
MP_SETS         equ 16          ; metatile palette sets in METAPAL (themes share them via MP_IDX)
AREA_FLAG       equ $D13E       ; WRAM bank 1: second area set (Injustice, Dishonor, Pride, Abyss; bank 0 $2355)
HELPER          equ $FFF3   ; 12 bytes of HRAM: reads WRAM bank 1 for WRAM2 code (installed only while used)
CURSOR_PAL      equ 7
PORTRAIT_PAL    equ 5           ; BG palette `earth`: start-menu portrait (no item uses it, see item_palettes)
PLAYER_PAL      equ 0
OBP1_PAL        equ 7

BANK8_ORG       equ $4000
W2_IMAGE_ROM    equ $4400   ; bank 8 address of the WRAM2 image
PICTURE_LUT     equ $5600   ; bank 8: tile -> BG palette for the dungeon-entrance cutscene (256)
PICTURE_FIX     equ $5700   ; bank 8: attribute fixups (VRAM lo, hi, attr)..., hi = 0 ends (<= 256 bytes)
PICTURE_BANK    equ 7       ; ROM bank of the (only) picture LCD-on site, restored after the copy
LUT_TITLE_ROM   equ $5C00   ; bank 8: castle title LUT (256), copied at the bank-7 title LCD-on
LUT_LOGO_ROM    equ $5D00   ; bank 8: logo LUT (256)
BRAND_TILES     equ $6000   ; bank 8: logo branding tile data (palettes/branding.yaml), BRAND_TILES_LEN bytes
BRAND_CELLS     equ $6600   ; bank 8: (lo, hi, tile)*, hi = 0 ends: $9800 map cells of the branding
BRAND_TILES_LEN equ $600    ; tiles $A0-$FF (all unused by the logo), zero-padded by the builder
BRAND_VRAM      equ $8A00   ; tile $A0 with LCDC $89 (signed tile data, $80-$FF at $8800)
AREA_THEME      equ $6800   ; bank 8: ROM theme per area id [$D12F], 256 with AREA_FLAG = 0, then 256 with 1
METAPAL         equ $6A00   ; bank 8: palette per metatile graphic, 128 per set (MP_SETS)
THEME_BG_ROM    equ $7200   ; bank 8: 64 bytes of BG base colours per ROM theme
THEME_OBJ_ROM   equ $7A00   ; bank 8: 8 bytes (OBJ palette THEME_OBJ_SLOT) per ROM theme
RT_SLOT         equ $7B00   ; bank 8: WRAM slot per ROM theme (0 surface, 1 dungeon cache, 2 entrance, 3 UI)
MP_IDX          equ $7B20   ; bank 8: METAPAL set per ROM theme
SCENE_LUTS      equ $5800   ; bank 8: 256-byte LUTs of scene pictures (MAX_SCENE_LUTS, SCENES LUT index)
MAX_SCENE_LUTS  equ 4
SCENES          equ $5E00   ; bank 8: (lo, hi, ROM theme, LUT, OBJ)* of scene LCD-on return addresses, hi = 0 ends
SCENE_OBJ       equ $5F00   ; bank 8: 8 bytes per scene OBJ palette 0 (SCENES OBJ index)
BANK_SIG        equ $5FF0   ; bank 8: byte at $4001 of ROM banks 1-7 (finds the caller's bank again)
HERO_OBJ_ROM    equ $7B40   ; bank 8: 4 x 8 bytes, OBJ palette 0 (PLAYER_PAL) per champion (HERO_ID)
CARD_TINT       equ $7C00   ; bank 8: 16 x 8 bytes, title-card UI palette per dungeon ([HR_CARD] & 15; SCENES theme $FF)
CARD_UI         equ $7C80   ; bank 8: low byte of BASE_BG's UI palette (where CARD_TINT goes)
GOLD_DIGITS     equ $7D00   ; bank 8: DIGIT_LEN bytes, side-panel digits $E8-$F1 redrawn in gold (VRAM bank 1)
PARADE_PAL_ROM  equ $7E00   ; bank 8: PARADE_LEN bytes, OBJ palette per byte of the parade lists 7:$7CA6-$7CBE (builder, from OBJPAL)
PARADE_TAB      equ ENTRY_TIER  ; WRAM2: PARADE_PAL_ROM copied over ENTRY_TIER (unused off map screens, cleared at every LCD-on)
PARADE_LISTS    equ $7CA6   ; bank 7: the parade's five 4-graphic lists ($FF-terminated, 5 bytes each)
PARADE_LEN      equ 25
PARADE_RET      equ $4854   ; return address of the parade's LCD-on site 7:$4853 (rst $28)
PARADE_LOAD     equ $49EE   ; bank 7: load the graphics of list DE into tiles $80+8k (k = list index)
DIGIT_VRAM      equ $8E80   ; tile $E8 (signed tile data); LUT_GAME gives $E8-$F1 attribute bit 3
DIGIT_LEN       equ 160
HR_CARD         equ $FF8F   ; title card (bank 7 $4608): dungeon number shown on the card
TITLE_BANK      equ 7       ; ROM bank of the title and picture LCD-on sites
AREA_ID         equ $D12F   ; WRAM bank 1: current area/map id
HERO_ID         equ $D133   ; WRAM bank 1: champion 0 Mariah, 1 Iolo, 2 Dupre, 3 Shamino (also the select cursor)
HERO_BG         equ $DD00   ; WRAM2, in unused LUT_GAME $00-$1F: champion-select portrait colours (BG palettes 1-4)

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
section rst20b, $0023, $0023           ; rst $20 padding
PrepWait:                               ; 0:$175A (animated-tile copy): prep,
        call PrepTramp                  ; then the original wait for LY 145
        jr PrepWait2
section rst28, $0028, $0028            ; rst $28: LCD on (game screens)
        jp LcdOnGame
section rst28b, $002B, $002B           ; rst $28 padding
PrepWait2:
        jp $02DC                        ; wait for LY 145
section rst30, $0030, $0030            ; rst $30: LCD on (title screens)
LcdOnTitle:                             ; A = new LCDC value; LUT mode from it:
        push af                         ; $81 (castle, map $9800) -> 1
        and $09                         ; $89 (logo, map $9C00)   -> 9
        jr LcdOnCommon
HudExit:                                ; $0035: back from W2Hud (A = 1)
        ldh [rSVBK], a
        ret

; Idle-wait hook: the main loop's halt wait ($1EE7 `xor a; ldh [$FF8E],a`)
; and $02EA (wait for the VBlank flag: `ldh a,[rLCDC]; or a`, its `ret z`
; stays) call PrepTramp. Every exit clears HR_VBLANK (the halt wait needs it;
; $02EA clears it on its own) and returns A / Z of the LCDC test. The wait
; for LY 145 ($02DC) itself is not hooked: the title code calls it
; back-to-back inside line 145, where the original returns at once; any hook
; overhead misses LY 145 and waits a whole frame (title sequence ~13%
; slower). Only its call in the animated-tile copy (0:$175A, then DMA and
; the VRAM copy) goes through PrepWait. Lives in interrupt-vector filler
; the game never executes: the timer and joypad interrupts are never enabled
; (IE = $0B), and the VBlank / STAT / serial vectors are 3-byte jumps
; followed by $FF padding.
section vec_prep_lcd, $0043, $0043     ; VBlank vector padding
PrepLcd:                                ; DMG
        xor a
        ldh [HR_VBLANK], a
        jr PrepLcd2
section vec_prep_lcd2, $004B, $004B    ; STAT vector padding
PrepLcd2:                               ; the replaced test (A = LCDC, Z = off)
        ldh a, [rLCDC]
        or a
        ret
section vec_prep, $0051, $0051         ; timer vector (never enabled), after its reti
PrepTramp:
        ldh a, [HR_CGB]                 ; 1 = CGB
        add a                           ; A = 2, Z = DMG
        jr z, PrepLcd
        jr PrepTramp2
section vec_prep_b, $005B, $005B       ; serial vector padding (after jp $C550)
PrepTramp2:
        ldh [rSVBK], a                  ; 2 (main code runs with SVBK = 1)
        jp W2Prep                       ; returns through HudExit (SVBK = 1)

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
section patch_idle_vbl, $02EA, $02EA    ; wait for the VBlank flag
        call PrepTramp
section patch_anim_wait, $175A, $175A  ; animated tiles: wait LY 145, DMA, copy
        call PrepWait                   ; (was call $02DC)
section patch_idle_halt, $1EE7, $1EE7   ; main loop, before its halt wait
        call PrepTramp                  ; (was xor a; ldh [$FF8E],a)
; Attract-loop parade (bank 7 $47D6, "YOUR FRIENDS" / "YOUR FOES"): both
; calls of its graphics loader ($49EE, DE = list of 4 graphic bytes) go
; through ParadeLoad, which notes the list in HRAM (harmless on DMG).
section patch_parade_first, $1C7F7, $47F7   ; ld de,$7ca6; call $49ee (first page)
        call ParadeLoad
section patch_parade_page, $1C8D4, $48D4    ; pop de; call $49ee (next pages)
        call ParadeLoad
section bank7_parade, $1FFF8, $7FF8         ; bank 7 $FF padding after the ending text
ParadeLoad:
        ld a, e
        ldh [PARADE_LIST], a
        jp PARADE_LOAD

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
        call HeroObj                    ; champion colours in OBJ palette 0 (cached)
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
        ld a, [AREA_ID]                 ; ROM theme of the current area
        ld l, a
        ld h, high(AREA_THEME)
        ld a, [AREA_FLAG]               ; second area set: second half
        or a
        jr z, .t
        inc h
.t:
        ld a, [hl]
        push af
        add low(MP_IDX)                 ; B = metatile palette set of the theme
        ld l, a
        ld h, high(MP_IDX)
        ld a, [hl]
        ld b, a                         ; HL = METAPAL + set*128 + g
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
        call MapTheme                   ; ROM theme -> WRAM slot (dungeon colours cached in SLOT_MAP)
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
        xor a                           ; no parade yet (HRAM is random at power-on)
        ldh [PARADE_ON], a
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

; A = ROM theme of the area being loaded (bank 8 mapped, SVBK = 2).
; Returns the WRAM theme slot in A. Surface, entrance and UI themes have
; fixed slots; a dungeon theme is copied into SLOT_MAP (BG base colours and
; OBJ palette THEME_OBJ_SLOT) unless it is already there, and CUR_THEME is
; invalidated so SetTheme reloads it. Keeps C.
MapTheme:
        ld e, a
        add low(RT_SLOT)
        ld l, a
        ld h, high(RT_SLOT)
        ld a, [hl]
        cp SLOT_MAP
        ret nz
        ld hl, MAP_CACHED
        ld a, e
        cp [hl]
        ld a, SLOT_MAP
        ret z
        ld [hl], e
        ld a, $FF
        ld [CUR_THEME], a
        ld a, e                         ; HL = THEME_BG_ROM + theme*64
        rrca
        rrca
        ld b, a
        and $C0
        ld l, a
        ld a, b
        and $3F
        add high(THEME_BG_ROM)
        ld h, a
        push de
        ld de, BG_THEMES + SLOT_MAP * 64
        ld b, 64
.bg:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .bg
        pop de
        ld a, e                         ; HL = THEME_OBJ_ROM + theme*8
        add a
        add a
        add a
        add low(THEME_OBJ_ROM)
        ld l, a
        ld h, high(THEME_OBJ_ROM)
        ld de, THEME_OBJ + SLOT_MAP * 8
        ld b, 8
.obj:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .obj
        ld a, SLOT_MAP
        ret

; Every metatile slot load (area entry), SVBK = 1: OBJ palette 0 (the player,
; its attack pose and the entrance-cutscene champion) takes the colours of
; the champion in HERO_ID, resynced at the next OAM DMA. Preserves all.
HeroObj:
        push af
        push bc
        push de
        push hl
        ld a, [HERO_ID]
        and $03
        ld e, a
        ld a, 2
        ldh [rSVBK], a
        ld hl, HERO_CACHED
        ld a, e
        cp [hl]
        jr z, .done
        ld [hl], a
        add a
        add a
        add a
        add low(HERO_OBJ_ROM)
        ld l, a
        ld h, high(HERO_OBJ_ROM)
        ld de, BASE_OBJ + PLAYER_PAL * 8
        ld b, 8
.c:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .c
        ld a, [LAST_OBP0]
        cpl
        ld [LAST_OBP0], a
.done:
        ld a, 1
        ldh [rSVBK], a
        pop hl
        pop de
        pop bc
        pop af
        ret
; Logo screen (LCD_MODE 9, LCD off, bank 8 mapped): copy the branding tiles
; into VRAM and place their cells in the $9800 map; the dissolve copies them
; to $9C00 with the rest of the logo. Attributes follow from the logo LUT.
Brand:
        ld a, [LCD_MODE]
        cp 9
        ret nz
        xor a
        ldh [rVBK], a
        ld hl, BRAND_TILES
        ld de, BRAND_VRAM
        ld bc, BRAND_TILES_LEN
.t:
        ld a, [hl+]
        ld [de], a
        inc de
        dec bc
        ld a, b
        or c
        jr nz, .t
        ld hl, BRAND_CELLS
.c:
        ld e, [hl]
        inc hl
        ld a, [hl+]
        or a
        ret z
        ld d, a
        ld a, [hl+]
        ld [de], a
        jr .c

; Bank 8 mapped, SVBK = 2, HL = return address of a game LCD-on site (its
; mode byte), B = byte at $4001 of the caller's bank. A SCENES entry (lo, hi,
; ROM theme, LUT, OBJ) for that site replaces the screen's BG colours with
; the theme, the live LUT with SCENE_LUTS[LUT] ($FF: keep) and OBJ palette 0
; with SCENE_OBJ[OBJ] ($FF: keep; the champion's colours come back with the
; next area). Returns A = the caller's bank (from BANK_SIG).
SceneHook:
        push bc
        ld a, h                         ; the attract-loop parade: its sprites
        cp high(PARADE_RET)             ; take their gameplay colours
        jr nz, .np
        ld a, l
        cp low(PARADE_RET)
        call z, ParadeOn8
.np:
        ld a, [LCD_MODE]                ; map screens: gold side-panel digits in
        or a                            ; VRAM bank 1 (LCD off; nothing else
        jr nz, .nodig                   ; uses bank-1 tile data)
        push hl
        ld hl, GOLD_DIGITS
        ld de, DIGIT_VRAM
        ld b, DIGIT_LEN
        inc a
        ldh [rVBK], a
.dg:
        ld a, [hl+]
        ld [de], a
        inc de
        dec b
        jr nz, .dg
        xor a
        ldh [rVBK], a
        pop hl
.nodig:
        ld de, SCENES
.l:
        ld a, [de]
        ld c, a
        inc de
        ld a, [de]
        inc de
        or a
        jp z, .done                     ; hi = 0: end of table
        cp h
        jr nz, .next
        ld a, c
        cp l
        jr z, .hit
.next:
        inc de
        inc de
        inc de
        jr .l
.hit:
        ld a, [de]                      ; ROM theme -> BASE_BG
        inc de
        push de
        cp $FF
        jr z, .tint                     ; $FF: keep the theme, tint the card
        rrca
        rrca
        ld b, a
        and $C0
        ld l, a
        ld a, b
        and $07
        add high(THEME_BG_ROM)
        ld h, a
        ld de, BASE_BG
        ld b, 64
.bg:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .bg
.reload:
        ld a, $FE                       ; no theme: the next screen reloads its own
        ld [CUR_THEME], a
        ld a, [LAST_BGP]
        cpl
        ld [LAST_BGP], a
        pop de
        ld a, [de]                      ; LUT
        inc de
        cp $FF
        jr z, .obj
        add high(SCENE_LUTS)
        ld h, a
        ld l, 0
        push de
        ld de, LUT
.lut:
        ld a, [hl+]
        ld [de], a
        inc e
        jr nz, .lut
        pop de
.obj:
        ld a, [de]                      ; OBJ palette 0
        cp $FF
        jr z, .done
        add a
        add a
        add a
        add low(SCENE_OBJ)
        ld l, a
        ld h, high(SCENE_OBJ)
        ld de, BASE_OBJ + PLAYER_PAL * 8
        ld b, 8
.o:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .o
        ld a, $FF
        ld [HERO_CACHED], a
        ld a, [LAST_OBP0]
        cpl
        ld [LAST_OBP0], a
        jr .done
.tint:                                  ; title card: UI palette of this dungeon
        ldh a, [HR_CARD]
        and $0F
        add a
        add a
        add a
        ld l, a
        ld h, high(CARD_TINT)
        ld a, [CARD_UI]
        ld e, a
        ld d, high(BASE_BG)
        ld b, 8
.tn:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .tn
        jr .reload
.done:
        pop bc
; B = signature byte read at $4001 before bank 8 was mapped: A = that bank.
SigBank:
        ld a, [$4001]                   ; bank 8 itself (nested call from a
        cp b                            ; bank-8 routine interrupted by VBlank)
        ld a, 8
        ret z
        ld hl, BANK_SIG
        ld c, 1
.s:
        ld a, [hl+]
        cp b
        jr z, .f
        inc c
        ld a, c
        cp 8
        jr nz, .s
        ld c, TITLE_BANK                ; not found (never): the picture bank
.f:
        ld a, c
        ret

; Rebuild ENTRY_TIER from the object records (WRAM1 [record+3] = shadow-OAM
; offset of its two 8x16 entries; free records hold $FF). Entered from the
; WRAM2 routine TierFar with SVBK = 2, B = caller's $4001 signature, C = mode:
; 0 (after the DMA): entries without a record are tier 0 if visible in the
; shadow OAM now, else unknown (0, TierPal rebuilds when one shows up);
; $80 (TierPal): every entry known. Known = bit 7, tier = bits 0-1.
; Returns A = caller's bank, SVBK = 2.
TierScan8:
        bit 0, c
        jp nz, HeroMenu8
        bit 1, c
        jp nz, Prep8
        bit 2, c
        jp nz, FillAttrs8
        call TierCore
        jp SigBank
TierCore:
        push bc
        ld hl, ENTRY_TIER
        ld de, $C000
.c:
        ld a, c
        or a
        jr nz, .f
        ld a, [de]                      ; Y = 0: slot empty
        or a
        jr z, .f
        ld a, $80
.f:
        ld [hl+], a
        ld a, e
        add 4
        ld e, a
        cp $A0
        jr nz, .c
        ld hl, $D003
        ld de, REC_TIER
.r:
        ld a, 1
        ldh [rSVBK], a
        ld b, [hl]                      ; [record+3]
        inc a
        ldh [rSVBK], a
        ld a, b
        or a
        jr z, .n                        ; not drawn
        cp $A0
        jr nc, .n                       ; free ($FF)
        and $FC                         ; (not always a multiple of 4 while
        rrca                            ; the record is being set up)
        rrca
        add low(ENTRY_TIER)
        ld c, a
        ld a, [de]
        or $80
        push hl
        ld l, c
        ld h, high(ENTRY_TIER)
        ld [hl+], a
        ld [hl], a
        pop hl
.n:
        inc e
        ld a, l
        add 16
        ld l, a
        jr nc, .r
        pop bc
        ret
; C = 1 (SetThemeM): BG palette PORTRAIT_PAL = HERO_BG colours of the
; champion in INV+$33 (= WRAM1 $D133, ReadInv just ran). CUR_THEME = $FF:
; the next screen reloads its theme, so the change stays in the menu.
HeroMenu8:
        ld a, [LCD_BYTE]                ; only on the start menu's LCD-on
        cp $64
        jp nz, SigBank
        ld a, [INV+$33]
        and 3
        add a
        add a
        add a
        add low(HERO_BG)
        ld e, a
        ld d, high(HERO_BG)
        ld hl, BASE_BG + PORTRAIT_PAL * 8
        ld c, 8
.l:
        ld a, [de]
        ld [hl+], a
        inc e
        dec c
        jr nz, .l
        ld a, $FF
        ld [CUR_THEME], a
        ld a, [LAST_BGP]
        cpl
        ld [LAST_BGP], a
        jp SigBank

; SceneHook at the parade's LCD-on (SVBK = 2, TierClear just ran):
; PARADE_TAB = PARADE_PAL_ROM, PARADE_ON = 1 until the next LCD-on.
; Preserves HL.
ParadeOn8:
        push hl
        ld hl, PARADE_PAL_ROM
        ld de, PARADE_TAB
        ld b, PARADE_LEN
.c:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .c
        ld a, 1
        ldh [PARADE_ON], a
        pop hl
        ret

Bank8CodeEnd:

; bank 8 $5400-$55FF (between the WRAM2 image and PICTURE_LUT)
section bank8b, $21400, $5400
; C = 2 (W2Prep: the game's idle waits $1EE7 / $02EA, main code, outside
; VBlank, shadow OAM final for the next DMA): the sprite palette bits go into
; the shadow OAM, so the DMA itself carries them and the VBlank hook skips
; its OAM pass (the game's own VBlank VRAM work keeps its time). Map screens
; first rebuild every entry's tier from the records (no unknown entries) and
; colour dropped floor items. Skipped when it could run into VBlank (the
; hook then colours OAM as before).
Prep8:
        push bc
        xor a
        ldh [HR_VBLANK], a
        ldh a, [rLCDC]
        add a
        jr nc, .x                       ; LCD off
        ldh a, [rLY]
        cp PREP_LY
        jr c, .go
        cp 146
        jr c, .x                        ; too close to VBlank / LY 145 target
.go:
        ld hl, $C003                    ; clear the palette bits: all recomputed
        ld b, 40
.z:
        ld a, [hl]
        and $F8
        ld [hl+], a
        inc l
        inc l
        inc l
        dec b
        jr nz, .z
        ld a, [LCD_MODE]
        or a
        jr nz, .pal
        ld c, $80
        call TierCore
        call LiveFloor
.pal:
        ld hl, $C000
        call OamPass
        ld a, 1
        ld [PREP_DONE], a
.x:
        pop bc
        jp SigBank
; C = 4 (SetTheme, LCD off): recompute attributes of both BG maps from
; their tile ids.
FillAttrs8:
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
        ld a, [LCD_MODE]
        cp 3
        jr nz, .fixed
; Picture: map cells whose tile id is shared by two regions get their own
; attribute (PICTURE_FIX); SigBank maps the caller's bank 7 back.
        ld hl, PICTURE_FIX
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
        jp SigBank
Bank8bEnd:

; ======================================================== WRAM bank 2 image

section wram2, $20400, $D000

; -- after every OAM DMA (VBlank): palette sync on DMG-register change,
; then OBJ palette bits in OAM.
W2AfterDma:
        push bc
        push de
        push hl
        call W2AfterDmaBody
        ld hl, PREP_DONE
        ld a, [hl]
        ld [hl], 0
        or a
        call z, W2AfterDmaT             ; not prepped: the OAM entry tiers here
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
        cp 146                          ; a late DMA (bank 0 $1717 at LY 145:
        ret nc                          ; its tile copy follows) keeps the time
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
        call HudCellLy                  ; HudCell while still in VBlank
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
        ld a, [PREP_DONE]               ; Prep8 coloured the shadow OAM at the
        or a                            ; game's idle wait: the DMA carried it
        ret nz
        ld hl, $FE00
; HL = OAM page: $FE00 after the DMA (fallback), $C000 from Prep8 (which
; clears the palette bits first). An entry whose palette bits are already
; set came from Prep8 through the DMA and is kept.
OamPass:
        ld b, 40
.o:
        ld a, [hl+]                     ; Y
        or a
        jr z, .hide
        inc l                           ; skip X
        inc l
        ld a, [hl-]                     ; attribute; HL -> tile
        and 7
        jr nz, .kept
        ld a, [hl+]                     ; tile; HL -> attribute
        sub $80
        jr c, .player
        rrca
        rrca
        rrca
        and $0F
        ld e, a                         ; slot at or past the loaded count ($C539):
        call SlotCount                  ; not a monster. The champion's attack
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
        jp TierPal                      ; monster palette + the entry's tier
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
.kept:
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
        call BuildLutT                  ; forget OAM entry tiers, BuildLut
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
        ld c, 1                         ; start-menu portrait colours (bank 8
        call TierFar                    ; HeroMenu8 checks LCD_BYTE $64)
        ld a, [LCD_BYTE]                ; champion select: BG palettes 1-4 =
        cp $7F                          ; the four portraits (HERO_BG); the
        jr nz, .synced                  ; next screen reloads its theme
        ld hl, HERO_BG
        ld de, BASE_BG + 8
        ld b, 32
.hb:
        ld a, [hl+]
        ld [de], a
        inc e
        dec b
        jr nz, .hb
        ld a, $FF
        ld [CUR_THEME], a
.synced:
        call SceneTramp
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
        ld c, 4                         ; FillAttrs8 (bank 8; picture fixups too)
        jp TierFar

; OamPass, E = sprite slot of the entry's tile ($80+8E): A = loaded slot
; count ($C539). On the attract-loop parade (PARADE_ON) the slots hold the
; graphics of list PARADE_LIST instead: the entry gets PARADE_TAB[list
; offset + E], the gameplay OBJ palette of that graphic (monsters: base
; tier), and OamPass goes on at .apply (HL = attribute byte).
SlotCount:
        ldh a, [PARADE_ON]
        or a
        ld a, [SPRITE_COUNT]
        ret z
        pop af                          ; not back into the slot lookup
        ldh a, [PARADE_LIST]
        add e
        add (low(PARADE_TAB) - low(PARADE_LISTS)) & $FF
        ld e, a
        ld d, high(PARADE_TAB)
        ld a, [de]
        and 7
        jp OamPass.apply

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
        ret                             ; (OBJ palette 5 no longer follows the theme: royal everywhere)

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
        call Brand                      ; logo: DX plate + credit (bank 8 mapped)
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
        jp MapItemsLut                  ; side-panel A/B icons + floor items by type

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
        jr HelperOff
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
        call IconPal                    ; ItemPal, on the panel's colour 0
        ld hl, LUT+$F8
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        push hl
        ld a, [INV+$25]
        call IconPal
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

; Scene LCD-on (game sites, SVBK = 2): bank-8 SceneHook may replace the
; theme, LUT and OBJ palette 0 for the screen being switched on (SCENES
; table, keyed by the site's return address); the caller's ROM bank is
; found again from its signature byte at $4001 (BANK_SIG).
SceneTramp:
        ldh a, [HR_LCDMODE]
        or a
        ret nz                          ; title sites: no scenes
        ld hl, sp+14                    ; [ret][ret][hl][de][bc][ret][af][rst ret]
        ld a, [hl+]
        ld h, [hl]
        ld l, a
        ld a, [$4001]
        ld b, a
        ld a, 8
        ld [MBC_BANK], a
        call SceneHook                  ; A = caller's bank
        ld [MBC_BANK], a
        ret

; LCD-on, after BuildLut: SetTheme, then on the start menu ($64) the current
; champion's portrait colours in BG palette PORTRAIT_PAL (bank 8 HeroMenu8;
; BuildLut's ReadInv has refreshed INV+$33 = WRAM1 $D133).
; Side-panel refresh step (from the 4-cell loop, stack: [loop][bc]): draw
; cell A only while LY is still in VBlank, else end the batch here and
; resume from this cell next frame (VRAM writes in mode 3 are lost).
HudCellLy:
        ld e, a
        ldh a, [rLY]
        cp 144
        ld a, e
        jp nc, HudCell
        pop hl
        pop bc
        ld a, c
        ld [LIVE_R], a
        ret
; PrepTramp (idle waits, SVBK = 2): Prep8 in bank 8, then the original
; LCDC test for the caller's `ret z`; back to SVBK 1 through HudExit.
; The LY window test comes first, so a wait entered just before VBlank
; costs only a few cycles more than the original.
W2Prep:
        ldh a, [rLY]
        sub PREP_LY                     ; LY in [PREP_LY, 146): skip
        cp 146 - PREP_LY
        jr c, .skip
        push bc                         ; (TierFar keeps DE)
        push hl
        ld c, 2
        call TierFar
        pop hl
        pop bc
.skip:
        xor a
        ldh [HR_VBLANK], a
        ldh a, [rLCDC]
        or a
        ld a, 1
        jp HudExit
W2bEnd:

; ======================================================== WRAM bank 2, $DB40-$DBFF
; Monster tiers and floor-item colours (reverse_engineering/notes/monsters.md).
; $DB40 is past the longest translated attribute program (TILE_PROG reads stop
; at $DB00; the output is at most 9 bytes longer).
section wram2c, $20F40, W2C_ORG

; BuildLut, map screens: side-panel A/B icons, then every floor item.
MapItemsLut:
        call HudItemsLut
        ld hl, ITEM_CACHE               ; forget the cache: all slots recoloured
        ld a, $FE
        ld b, FLOOR_SLOTS
.i:
        ld [hl+], a
        dec b
        jr nz, .i
; LUT[$40+4k..$43+4k] = BG palette of the item in floor slot k (ITEM_IDS,
; item_palettes) for each slot whose id changed since the last call; empty
; slots keep their entry. NZ if a slot was recoloured.
FloorItems:
        ld de, ITEM_IDS
        ld c, 0
.k:
        ld a, e
        add low(ITEM_CACHE) - low(ITEM_IDS)
        ld l, a
        ld h, high(ITEM_CACHE)
        ld a, [de]
        cp [hl]
        jr z, .n
        ld [hl], a
        cp $FF
        jr z, .n
        call ItemPal                    ; A = palette (clobbers HL)
        ld b, a
        ld a, e
        sub low(ITEM_IDS)
        add a
        add a
        add FLOOR_TILES
        ld l, a
        ld h, high(LUT)
        ld a, b
        ld [hl+], a
        ld [hl+], a
        ld [hl+], a
        ld [hl], a
        inc c
.n:
        inc e
        ld a, e
        cp low(ITEM_IDS) + FLOOR_SLOTS
        jr nz, .k
        ld a, c
        or a
        ret

; Map screens, after every DMA (outside the VBlank-critical live refresh:
; no VRAM access): an item dropped with the LCD on (bank 0 $145E fills a
; free ITEM_IDS slot) gets its colour: the LUT changes and the attribute
; sweep rewrites the map from it.
LiveFloor:
        call FloorItems
        ret z
        xor a
        ld [SWEEP_LO], a
        ld a, $98
        ld [SWEEP_HI], a
        ret

; W2Pal, per OAM entry whose sprite id has OBJ palette A: monsters
; (MONSTER_PAL) get MONSTER_PAL + the entry's tier. HL = attribute byte.
TierPal:
        cp MONSTER_PAL
        jp nz, OamPass.apply
        ld a, l
        rrca
        rrca
        and $3F
        add low(ENTRY_TIER)
        ld e, a
        ld d, high(ENTRY_TIER)
        ld a, [de]
        bit 7, a
        jr nz, .k
        push hl                         ; unknown: the entry's record just got
        push bc                         ; this OAM slot (spawned, back on screen,
        ld c, $80                       ; moved): rebuild from the records now
        call TierFar
        pop bc
        pop hl
        ld a, [de]
.k:
        and 3
        add MONSTER_PAL
        jp OamPass.apply

; A = item id: A = BG palette of its side-panel A/B icon. ItemPal, unless
; that palette's colour 0 differs from the panel's (palette 0) on this
; screen (water / grass items on the overworld): then the panel palette,
; so the icon never sits on a tinted square. Clobbers DE, HL.
IconPal:
        call ItemPal
        ld e, a
        add a
        add a
        add a
        or low(BASE_BG)
        ld l, a
        ld h, high(BASE_BG)
        ld a, [hl+]
        ld d, [hl]
        ld l, low(BASE_BG)
        cp [hl]
        jr nz, .r
        inc l
        ld a, d
        cp [hl]
.r:
        ld a, e
        ret z
        xor a
        ret

; C = TierScan8 mode: run it in bank 8 and map the caller's bank back.
TierFar:
        push de
        ld a, [$4001]
        ld b, a
        ld a, 8
        ld [MBC_BANK], a
        call TierScan8
        ld [MBC_BANK], a
        pop de
        ret

; After every DMA: W2AfterDmaBody, then (map screens) rebuild ENTRY_TIER
; (TierScan8, bank 8), which W2Pal uses right after the next DMA. Runs on
; every exit of the body: its live refresh is skipped whenever W2Pal ends
; after VBlank (busy screens), the tiers must not be. An entry whose slot
; is empty now is left unknown: if a monster shows up in it next frame,
; TierPal rebuilds the table first, so no frame shows the base colour.
W2AfterDmaT:
        ld a, [LCD_MODE]
        or a
        ret nz
        call LiveFloor
        ld c, 0
        jp TierFar

; LCD-on: no stale tiers on the new screen.
BuildLutT:
        call TierClear
        jp BuildLut
TierClear:
        ld hl, ENTRY_TIER
        xor a
        ldh [PARADE_ON], a              ; every screen but the parade (SceneHook sets it again)
        ld b, 40
.c:
        ld [hl+], a
        dec b
        jr nz, .c
        ret
W2cEnd:

; ======================================================== bank 2 hooks
; bank 2 $5FE6 (object record allocator, both callers run with bank 2
; mapped): ld bc,$d000 -> jp AllocHook.
section patch_alloc, $9FE6, $5FE6
        jp AllocHook

; Free bank-2 space ($7F33-$7FFF is $FF padding in the original; $7F34 on).
; On success (Z, BC = new record) the record's colour tier goes to
; REC_TIER: from the template when the spawner called (its stack holds the
; template pointer + 1), copied from the source record when the cloner did
; (monster splitting). Returns like the original: Z and A = $FF, or NZ.
; Preserves DE and HL.
section bank2_alloc, $BF34, $7F34
AllocHook:
        call .alloc
        ret nz
        ldh a, [HR_CGB]
        or a
        jr z, .ok
        push hl
        push de
        ld a, 2                         ; REC_TIER is in WRAM bank 2 (the stack
        ldh [rSVBK], a                  ; is not in $D000-$DFFF)
        ld hl, sp+4
        ld a, [hl+]
        ld e, a
        ld a, [hl+]
        ld d, a                         ; DE = caller's return, HL = caller's stack
        ld a, e
        cp low(SPAWN_RET)
        jr nz, .clone
        ld a, d
        cp high(SPAWN_RET)
        jr nz, .done
        ld hl, sp+10                    ; caller's [bc][bc][template + 1]
        ld a, [hl+]
        ld h, [hl]
        ld l, a
        ld de, $10000 - (TEMPLATE_BASE + 1)
        add hl, de                      ; HL = 9 * U
        ld d, $FF
.div:
        inc d
        ld a, l
        sub 9
        ld l, a
        ld a, h
        sbc 0
        ld h, a
        jr nc, .div                     ; D = U
        ld a, d
        srl a
        ld e, a
        ld a, 0
        rla
        ld d, a                         ; D = U & 1, E = U / 2
        ld a, e
        add low(TIER_TAB)
        ld l, a
        ld a, high(TIER_TAB)
        adc 0
        ld h, a
        ld a, [hl]
        bit 0, d
        jr z, .lo
        swap a
.lo:
        and $0F
        jr .store
.clone:
        ld a, d
        cp high(CLONE_RET)
        jr nz, .done
        ld a, e
        cp low(CLONE_RET)
        jr nz, .done
        ld a, [hl]                      ; source record (low byte)
        swap a
        and $0F
        add low(REC_TIER)
        ld l, a
        ld h, high(REC_TIER)
        ld a, [hl]
.store:
        ld d, a
        ld a, c
        swap a
        and $0F
        add low(REC_TIER)
        ld l, a
        ld h, high(REC_TIER)
        ld [hl], d
.done:
        ld a, 1
        ldh [rSVBK], a
        pop de
        pop hl
.ok:
        ld a, $FF
        cp a
        ret
.alloc:
        ld bc, $D000
        jp ALLOC_REST
Bank2End:
