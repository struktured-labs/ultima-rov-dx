// Headless SameBoy harness: logs every VRAM / CGB-palette / OAM write with the
// core's own access-blocked flags, LY, STAT mode, speed and PC.
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "gb.h"
typedef struct GB_gameboy_internal_s GBI;
typedef struct { uint16_t pc, addr; uint8_t bank, val, ly, mode, ds, lcdc, kind, blocked; } ev_t;
#define MAXEV 200000
static uint32_t pixels[160*144];
static int vbl;
static ev_t evs[MAXEV]; static int nev;
// hist[kind][ds][ly]  kind: 0 vram 1 bgpd 2 obpd 3 oam   (LCD on only)
static uint32_t hist[4][2][154]; static uint32_t blocked[4][2]; static uint32_t total[4][2];
static int log_all;
static uint32_t rgb(GB_gameboy_t *gb, uint8_t r, uint8_t g, uint8_t b){ return (r<<16)|(g<<8)|b; }
static void vblank(GB_gameboy_t *gb, GB_vblank_type_t t){ vbl = 1; }
static void logcb(GB_gameboy_t *gb, const char *s, GB_log_attributes_t a){}
static bool wcb(GB_gameboy_t *gb, uint16_t addr, uint8_t val){
    GBI *g = (GBI *)gb; int kind = -1; bool blk = false;
    if (addr >= 0x8000 && addr < 0xA000) { kind = 0; blk = g->vram_write_blocked; }
    else if (addr == 0xFF69) { kind = 1; blk = g->cgb_palettes_blocked; }
    else if (addr == 0xFF6B) { kind = 2; blk = g->cgb_palettes_blocked; }
    else if (addr >= 0xFE00 && addr < 0xFEA0) { kind = 3; blk = g->oam_write_blocked; }
    else if (addr == 0xFF55 || addr == 0xFF4D || addr == 0xFF40) kind = 4;
    if (kind < 0) return true;
    uint8_t lcdc = g->io_registers[GB_IO_LCDC], ly = g->io_registers[GB_IO_LY];
    int ds = g->cgb_double_speed ? 1 : 0;
    if (kind < 4 && (lcdc & 0x80)) {
        total[kind][ds]++; if (ly < 154) hist[kind][ds][ly]++;
        if (blk) blocked[kind][ds]++;
    }
    if ((kind == 4 || blk || log_all || ((lcdc & 0x80) && ly < 144 && kind < 4)) && nev < MAXEV) {
        ev_t *e = &evs[nev++];
        e->pc = g->pc; e->addr = addr; e->bank = g->mbc_rom_bank; e->val = val; e->ly = ly;
        e->mode = g->io_registers[GB_IO_STAT] & 3; e->ds = ds; e->lcdc = lcdc; e->kind = kind; e->blocked = blk;
    }
    return true;
}
GB_gameboy_t *sb_open(const char *rom, const char *boot){
    GB_gameboy_t *gb = GB_alloc(); GB_init(gb, GB_MODEL_CGB_E);
    if (GB_load_boot_rom(gb, boot)) return NULL;
    GB_set_vblank_callback(gb, vblank); GB_set_pixels_output(gb, pixels);
    GB_set_rgb_encode_callback(gb, rgb); GB_set_log_callback(gb, logcb);
    GB_set_color_correction_mode(gb, GB_COLOR_CORRECTION_DISABLED);
    if (GB_load_rom(gb, rom)) return NULL;
    GB_set_write_memory_callback(gb, wcb);
    return gb;
}
void sb_frame(GB_gameboy_t *gb, int keys){
    for (int k = 0; k < 8; k++) GB_set_key_state(gb, k, (keys >> k) & 1);
    vbl = 0; int guard = 0;
    while (!vbl && guard++ < 2000000) GB_run(gb);
}
void sb_log_all(int on){ log_all = on; }
uint32_t *sb_pixels(void){ return pixels; }
uint8_t *sb_direct(GB_gameboy_t *gb, int which, size_t *size){ uint16_t bank; return GB_get_direct_access(gb, which, size, &bank); }
uint8_t sb_read(GB_gameboy_t *gb, uint16_t a){ return GB_safe_read_memory(gb, a); }
void sb_write(GB_gameboy_t *gb, uint16_t a, uint8_t v){ GB_write_memory(gb, a, v); }
int sb_svbk(GB_gameboy_t *gb){ return ((GBI*)gb)->cgb_ram_bank; }
ev_t *sb_events(int *n){ *n = nev; return evs; }
void sb_clear(void){ nev = 0; memset(hist,0,sizeof hist); memset(blocked,0,sizeof blocked); memset(total,0,sizeof total); }
uint32_t *sb_hist(void){ return &hist[0][0][0]; }
uint32_t *sb_blocked(void){ return &blocked[0][0]; }
uint32_t *sb_total(void){ return &total[0][0]; }
size_t sb_state_size(GB_gameboy_t *gb){ return GB_get_save_state_size(gb); }
void sb_save(GB_gameboy_t *gb, uint8_t *buf){ GB_save_state_to_buffer(gb, buf); }
int sb_load(GB_gameboy_t *gb, const uint8_t *buf, size_t n){ return GB_load_state_from_buffer(gb, buf, n); }
// execution probes: up to 64 addresses; each hit logs (idx, ly, mode, cycles since vblank cb, ds)
typedef struct { uint16_t idx; uint8_t ly, mode, ds; uint32_t cyc; } hit_t;
static uint16_t probe_addr[64]; static int16_t probe_bank[64]; static int nprobe;
#define MAXHIT 400000
static hit_t hits[MAXHIT]; static int nhit;
static void xcb(GB_gameboy_t *gb, uint16_t a, uint8_t op){
    GBI *g = (GBI *)gb;
    for (int i = 0; i < nprobe; i++) if (probe_addr[i] == a) {
        if (probe_bank[i] >= 0) {
            int b = a >= 0xD000 && a < 0xE000 ? g->cgb_ram_bank : (a >= 0x4000 && a < 0x8000 ? g->mbc_rom_bank : -1);
            if (b != probe_bank[i]) continue;
        }
        if (nhit < MAXHIT) { hit_t *h = &hits[nhit++]; h->idx = i; h->ly = g->io_registers[GB_IO_LY];
            h->mode = g->io_registers[GB_IO_STAT] & 3; h->ds = g->cgb_double_speed; h->cyc = g->cycles_since_vblank_callback; }
    }
}
void sb_probe(GB_gameboy_t *gb, int n, uint16_t *addr, int16_t *bank){
    nprobe = n; memcpy(probe_addr, addr, n * 2); memcpy(probe_bank, bank, n * 2); nhit = 0;
    GB_set_execution_callback(gb, n ? xcb : NULL);
}
hit_t *sb_hits(int *n){ *n = nhit; return hits; }
void sb_hits_clear(void){ nhit = 0; }
uint16_t sb_pc(GB_gameboy_t *gb){ return ((GBI*)gb)->pc; }
uint16_t sb_sp(GB_gameboy_t *gb){ return ((GBI*)gb)->sp; }
int sb_bank(GB_gameboy_t *gb){ return ((GBI*)gb)->mbc_rom_bank; }
int sb_ime(GB_gameboy_t *gb){ return ((GBI*)gb)->ime; }
