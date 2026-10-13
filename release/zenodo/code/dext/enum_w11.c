/* Exact enumeration of the weight-W extended logicals containing a given column (used with W = 11).
   Input file: N R K, then N lines "h0 h1 l" (He column as two u64, Le column as u64).
   usage: enum_w11 file W j0 [split_mod split_idx]; environment EXCL = file "m c_1 ... c_m" of excluded columns
   (the columns of lower orbit classes).
   Branch rule: pick the unsatisfied row with fewest available columns, branch on its available columns in index
   order, excluding earlier siblings (each solution found exactly once).  Prune when the syndrome is zero with weight
   < W (would split a weight-W logical into two kernel vectors of weight < W, one of them a logical: excluded by
   d_ext = W) and when popcount(s) > (W-k)*maxw.  split: at depth 1 only branches with index % mod == idx.
   Output: one line per solution (sorted column indices), then "SUMMARY j0 split_idx split_mod nodes found". */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#define MAXN 384
#define NW 6
static int N, R, K, W;
static uint64_t h0[MAXN], h1[MAXN], lm[MAXN];
static int cand[128][MAXN], ncand[128];
static uint64_t ex[NW];
static int chosen[32];
static long long nodes = 0, found = 0;
static int maxw;
static int smod = 1, sidx = 0;
static inline int isex(int c) { return (ex[c >> 6] >> (c & 63)) & 1; }
#define HS 4096
static int hnext[MAXN], hhead[HS];
static inline unsigned hh(uint64_t a, uint64_t b) { return (unsigned)((a * 0x9E3779B97F4A7C15ULL) ^ (b * 0xC2B2AE3D27D4EB4FULL)) >> 20 & (HS - 1); }
static void emit(int k) {
    found++;
    int t[32];
    for (int i = 0; i < W; i++) t[i] = chosen[i];
    for (int i = 0; i < W; i++) for (int j = i + 1; j < W; j++) if (t[j] < t[i]) { int x = t[i]; t[i] = t[j]; t[j] = x; }
    for (int i = 0; i < W; i++) printf("%d%c", t[i], i == W - 1 ? '\n' : ' ');
}
static void last2(int k, uint64_t s0, uint64_t s1, uint64_t l) {
    nodes++;
    int pc = __builtin_popcountll(s0) + __builtin_popcountll(s1);
    if (pc > 2 * maxw) return;
    int best = -1, bc = 1 << 30;
    for (int r = 0; r < R; r++) {
        int bit = r < 64 ? (s0 >> r) & 1 : (s1 >> (r - 64)) & 1;
        if (!bit) continue;
        int c = 0;
        for (int i = 0; i < ncand[r]; i++) c += !isex(cand[r][i]);
        if (c < bc) { bc = c; best = r; if (c == 0) return; }
    }
    for (int i = 0; i < ncand[best]; i++) {
        int c1 = cand[best][i];
        if (isex(c1)) continue;
        uint64_t t0 = s0 ^ h0[c1], t1 = s1 ^ h1[c1];
        for (int c2 = hhead[hh(t0, t1)]; c2 >= 0; c2 = hnext[c2]) {
            if (h0[c2] != t0 || h1[c2] != t1 || c2 == c1 || isex(c2)) continue;
            if (l ^ lm[c1] ^ lm[c2]) { chosen[k] = c1; chosen[k + 1] = c2; emit(k); }
        }
    }
}
/* pair table: all unordered pairs (a<b) keyed by He sum */
#define PHS (1 << 18)
static int *pa, *pb, *pnext, phead[PHS], npairs;
static uint64_t *p0, *p1;
static inline unsigned ph(uint64_t a, uint64_t b) { return (unsigned)(((a * 0x9E3779B97F4A7C15ULL) ^ (b * 0xC2B2AE3D27D4EB4FULL)) >> 40) & (PHS - 1); }
static void build_pairs(void) {
    long M = (long)N * (N - 1) / 2;
    pa = malloc(M * sizeof(int)); pb = malloc(M * sizeof(int)); pnext = malloc(M * sizeof(int));
    p0 = malloc(M * sizeof(uint64_t)); p1 = malloc(M * sizeof(uint64_t));
    for (int i = 0; i < PHS; i++) phead[i] = -1;
    for (int a = 0; a < N; a++) for (int b = a + 1; b < N; b++) {
        uint64_t x0 = h0[a] ^ h0[b], x1 = h1[a] ^ h1[b];
        if (!x0 && !x1) continue;
        int id = npairs++;
        pa[id] = a; pb[id] = b; p0[id] = x0; p1[id] = x1;
        unsigned hb = ph(x0, x1); pnext[id] = phead[hb]; phead[hb] = id;
    }
}
static void last3(int k, uint64_t s0, uint64_t s1, uint64_t l) {
    nodes++;
    int pc = __builtin_popcountll(s0) + __builtin_popcountll(s1);
    if (pc > 3 * maxw) return;
    int best = -1, bc = 1 << 30;
    for (int r = 0; r < R; r++) {
        int bit = r < 64 ? (s0 >> r) & 1 : (s1 >> (r - 64)) & 1;
        if (!bit) continue;
        int c = 0;
        for (int i = 0; i < ncand[r]; i++) c += !isex(cand[r][i]);
        if (c < bc) { bc = c; best = r; if (c == 0) return; }
    }
    int added[MAXN], na = 0;
    for (int i = 0; i < ncand[best]; i++) {
        int c1 = cand[best][i];
        if (isex(c1)) continue;
        ex[c1 >> 6] |= 1ULL << (c1 & 63); added[na++] = c1;   /* c1 and earlier siblings excluded for the pair */
        uint64_t t0 = s0 ^ h0[c1], t1 = s1 ^ h1[c1];
        for (int id = phead[ph(t0, t1)]; id >= 0; id = pnext[id]) {
            if (p0[id] != t0 || p1[id] != t1) continue;
            int a = pa[id], b = pb[id];
            if (isex(a) || isex(b)) continue;
            if (l ^ lm[c1] ^ lm[a] ^ lm[b]) { chosen[k] = c1; chosen[k + 1] = a; chosen[k + 2] = b; emit(k); }
        }
    }
    for (int i = 0; i < na; i++) ex[added[i] >> 6] &= ~(1ULL << (added[i] & 63));
}
static void dfs(int k, uint64_t s0, uint64_t s1, uint64_t l) {
    nodes++;
    if (k == W - 3 && (s0 || s1)) { last3(k, s0, s1, l); return; }
    if (k == W - 2 && (s0 || s1)) { last2(k, s0, s1, l); return; }
    if (k == W) {
        if (!s0 && !s1 && l) emit(k);
        return;
    }
    if (!s0 && !s1) return;
    int pc = __builtin_popcountll(s0) + __builtin_popcountll(s1);
    if (pc > (W - k) * maxw) return;
    int best = -1, bc = 1 << 30;
    for (int r = 0; r < R; r++) {
        int bit = r < 64 ? (s0 >> r) & 1 : (s1 >> (r - 64)) & 1;
        if (!bit) continue;
        int c = 0;
        for (int i = 0; i < ncand[r]; i++) c += !isex(cand[r][i]);
        if (c < bc) { bc = c; best = r; if (c == 0) return; }
    }
    int added[MAXN], na = 0;
    for (int i = 0; i < ncand[best]; i++) {
        int c = cand[best][i];
        if (isex(c)) continue;
        if (k == 1 && smod > 1 && (c % smod) != sidx) { ex[c >> 6] |= 1ULL << (c & 63); added[na++] = c; continue; }
        chosen[k] = c;
        ex[c >> 6] |= 1ULL << (c & 63); added[na++] = c;
        dfs(k + 1, s0 ^ h0[c], s1 ^ h1[c], l ^ lm[c]);
    }
    for (int i = 0; i < na; i++) ex[added[i] >> 6] &= ~(1ULL << (added[i] & 63));
}
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "r");
    W = atoi(argv[2]);
    int j0 = atoi(argv[3]);
    if (argc > 5) { smod = atoi(argv[4]); sidx = atoi(argv[5]); }
    if (fscanf(f, "%d %d %d", &N, &R, &K) != 3) return 1;
    for (int c = 0; c < N; c++) {
        unsigned long long a, b, l;
        if (fscanf(f, "%llu %llu %llu", &a, &b, &l) != 3) return 1;
        h0[c] = a; h1[c] = b; lm[c] = l;
        int w = __builtin_popcountll(a) + __builtin_popcountll(b);
        if (w > maxw) maxw = w;
        for (int r = 0; r < R; r++) {
            int bit = r < 64 ? (a >> r) & 1 : (b >> (r - 64)) & 1;
            if (bit) cand[r][ncand[r]++] = c;
        }
    }
    for (int c = 0; c < HS; c++) hhead[c] = -1;
    for (int c = N - 1; c >= 0; c--) { unsigned b = hh(h0[c], h1[c]); hnext[c] = hhead[b]; hhead[b] = c; }
    /* optional: columns to exclude (lower orbit classes), from env EXCL file: count then indices */
    char *ef = getenv("EXCL");
    if (ef) { FILE *g = fopen(ef, "r"); int m, c; if (fscanf(g, "%d", &m) == 1) for (int i = 0; i < m; i++) if (fscanf(g, "%d", &c) == 1) ex[c >> 6] |= 1ULL << (c & 63); fclose(g); }
    build_pairs();
    chosen[0] = j0;
    ex[j0 >> 6] |= 1ULL << (j0 & 63);
    dfs(1, h0[j0], h1[j0], lm[j0]);
    fprintf(stderr, "DONE j0=%d split=%d/%d nodes=%lld found=%lld maxw=%d\n", j0, sidx, smod, nodes, found, maxw);
    printf("SUMMARY %d %d %d %lld %lld\n", j0, sidx, smod, nodes, found);
    return 0;
}
