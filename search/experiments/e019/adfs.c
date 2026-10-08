/* adfs.c -- auditor's own exact search (written without reading dfs128.c / dfsw.c).
 *
 * Problem: columns c with H_c in GF(2)^R (R <= 64*NW) and L_c in GF(2)^12. Decide whether some set S with
 * |S| <= W has sum H = 0 and sum L != 0.
 *
 * Symmetry: columns carry an orbit label 0..NORB-1 under a group G of column permutations that preserves
 * {S : H(S)=0, L(S)!=0}. Case i: S contains rep_i (= lowest-index column of orbit i) and no column of an
 * orbit < i. Every solution is G-equivalent to a solution of exactly one case (its minimal orbit).
 *
 * Search: S grows from {rep}; at each node pick the syndrome row with the fewest still-allowed covering
 * columns; branch over those columns in order, forbidding earlier siblings (standard disjoint branching:
 * any completion must contain a column covering that row; the first such one in the list identifies the
 * branch). A node with zero syndrome is a leaf (a minimum-weight logical has no proper zero-syndrome subset,
 * so if L = 0 there it can be pruned; if L != 0 it is a solution). Pruning: popcount(s) > rem * wmax.
 * Last level (rem == 1): hash lookup of the exact syndrome.
 *
 * usage: adfs inst W case [split nsplit] [all]
 *   all: do not stop at the first solution; print every FOUND set.
 *   any: accept every nonempty zero-syndrome set (minimum weight of a nonzero codeword of ker H).
 *   first: branch on the lowest-index syndrome row instead of the row with fewest allowed columns.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

#define NW 3
#define MAXC 2048
#define MAXR (64 * NW)

typedef struct { uint64_t w[NW]; } syn_t;

static int R, C, NORB, W;
static syn_t H[MAXC];
static uint32_t Lm[MAXC];
static int orb[MAXC];
static int *rowcols[MAXR];
static int rowdeg[MAXR];
static int forb[MAXC];
static int avail[MAXR];
static int colrows[MAXC][MAXR];
static int colw[MAXC];
static int wmax;
static long long nodes = 0, found = 0;
static int stack_[64];
static int SPLIT = 0, NSPLIT = 1, ALL = 0, FIRSTROW = 0, ANY = 0;

/* hash of syndromes -> column list */
#define HS (1 << 14)
static int hhead[HS], hnext[MAXC];

static inline int iszero(const syn_t *s) { for (int k = 0; k < NW; k++) if (s->w[k]) return 0; return 1; }
static inline int popc(const syn_t *s) { int p = 0; for (int k = 0; k < NW; k++) p += __builtin_popcountll(s->w[k]); return p; }
static inline int eq(const syn_t *a, const syn_t *b) { for (int k = 0; k < NW; k++) if (a->w[k] != b->w[k]) return 0; return 1; }
static inline uint32_t hsh(const syn_t *s) {
    uint64_t h = 0x9E3779B97F4A7C15ULL;
    for (int k = 0; k < NW; k++) { h ^= s->w[k]; h *= 0xBF58476D1CE4E5B9ULL; h ^= h >> 31; }
    return (uint32_t)(h & (HS - 1));
}

static void forbid(int c) { if (forb[c]++ == 0) for (int i = 0; i < colw[c]; i++) avail[colrows[c][i]]--; }
static void allow(int c) { if (--forb[c] == 0) for (int i = 0; i < colw[c]; i++) avail[colrows[c][i]]++; }

static void report(int depth, int last) {
    found++;
    printf("FOUND w=%d cols:", depth + (last >= 0));
    for (int i = 0; i < depth; i++) printf(" %d", stack_[i]);
    if (last >= 0) printf(" %d", last);
    printf("\n");
    fflush(stdout);
}

static int dfs(syn_t s, int depth, uint32_t lm) {
    nodes++;
    if (iszero(&s)) {
        if (lm || ANY) { report(depth, -1); return !ALL; }
        return 0;
    }
    int rem = W - depth;
    if (rem <= 0) return 0;
    if (popc(&s) > rem * wmax) return 0;
    if (rem == 1) {
        for (int c = hhead[hsh(&s)]; c >= 0; c = hnext[c])
            if (!forb[c] && eq(&H[c], &s) && ((lm ^ Lm[c]) || ANY)) { report(depth, c); if (!ALL) return 1; }
        return 0;
    }
    int best = -1, bestv = 1 << 30;
    for (int k = 0; k < NW; k++) {
        uint64_t x = s.w[k];
        while (x) {
            int b = __builtin_ctzll(x); x &= x - 1;
            int r = 64 * k + b;
            if (avail[r] < bestv) { bestv = avail[r]; best = r; }
            if (FIRSTROW) break;
        }
        if (FIRSTROW && best >= 0) break;
    }
    if (bestv == 0) return 0;
    int list[MAXC], n = 0;
    for (int i = 0; i < rowdeg[best]; i++) { int c = rowcols[best][i]; if (!forb[c]) list[n++] = c; }
    int ret = 0;
    int i;
    for (i = 0; i < n; i++) {
        int c = list[i];
        forbid(c);
        if (depth == 1 && NSPLIT > 1 && (i % NSPLIT) != SPLIT) continue;
        syn_t s2; for (int k = 0; k < NW; k++) s2.w[k] = s.w[k] ^ H[c].w[k];
        stack_[depth] = c;
        if (dfs(s2, depth + 1, lm ^ Lm[c])) { ret = 1; i++; break; }
    }
    for (int j = 0; j < i && j < n; j++) allow(list[j]);
    return ret;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: adfs inst W case [split nsplit] [all]\n"); return 2; }
    FILE *fp = fopen(argv[1], "r");
    if (!fp) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    W = atoi(argv[2]);
    int cs = atoi(argv[3]);
    if (argc >= 6 && argv[4][0] >= '0' && argv[4][0] <= '9') { SPLIT = atoi(argv[4]); NSPLIT = atoi(argv[5]); }
    for (int a = 4; a < argc; a++) { if (!strcmp(argv[a], "all")) ALL = 1; if (!strcmp(argv[a], "first")) FIRSTROW = 1; if (!strcmp(argv[a], "any")) ANY = 1; }
    if (fscanf(fp, "%d %d %d", &R, &C, &NORB) != 3 || R > MAXR || C > MAXC) { fprintf(stderr, "bad header\n"); return 2; }
    for (int r = 0; r < R; r++) { rowcols[r] = malloc(sizeof(int) * C); rowdeg[r] = 0; }
    for (int c = 0; c < C; c++) {
        unsigned long lmv; int k;
        if (fscanf(fp, "%d %lu %d", &orb[c], &lmv, &k) != 3) { fprintf(stderr, "bad col %d\n", c); return 2; }
        Lm[c] = (uint32_t)lmv; colw[c] = k;
        memset(&H[c], 0, sizeof(syn_t));
        for (int i = 0; i < k; i++) {
            int r; if (fscanf(fp, "%d", &r) != 1 || r < 0 || r >= R) { fprintf(stderr, "bad row\n"); return 2; }
            colrows[c][i] = r; H[c].w[r / 64] ^= 1ULL << (r % 64);
            rowcols[r][rowdeg[r]++] = c;
        }
    }
    fclose(fp);
    for (int i = 0; i < HS; i++) hhead[i] = -1;
    for (int c = C - 1; c >= 0; c--) { uint32_t h = hsh(&H[c]); hnext[c] = hhead[h]; hhead[h] = c; }
    for (int r = 0; r < R; r++) avail[r] = rowdeg[r];
    memset(forb, 0, sizeof(forb));
    int rep = -1;
    for (int c = 0; c < C; c++) if (orb[c] == cs) { rep = c; break; }
    if (rep < 0) { fprintf(stderr, "no rep\n"); return 2; }
    for (int c = 0; c < C; c++) if (orb[c] < cs) forbid(c);
    wmax = 0;
    for (int c = 0; c < C; c++) if (!forb[c] && colw[c] > wmax) wmax = colw[c];
    forbid(rep);
    stack_[0] = rep;
    clock_t t0 = clock();
    if (W >= 1) dfs(H[rep], 1, Lm[rep]);
    printf("SUMMARY inst=%s W=%d case=%d split=%d/%d nodes=%lld found=%lld wmax=%d sec=%.1f\n", argv[1], W, cs, SPLIT,
           NSPLIT, nodes, found, wmax, (double)(clock() - t0) / CLOCKS_PER_SEC);
    return 0;
}
