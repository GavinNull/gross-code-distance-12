/* E-019 audit: exhaustive search for a minimum-weight undetected logical in a column matroid.
 * Written fresh for this audit (does not derive from adfs.c / dfsw.c).
 *
 * Input file:  line 1: nrows ncols nobs norb
 *              next ncols lines: "<orbit> <k> r1..rk <j> o1..oj"
 *   (orbit in 0..norb-1; if norb == 0 no orbit split: one case "everything allowed", start from empty with
 *    branching on the first column choice handled by a virtual row = all columns.)
 * Usage: mdfs file W [case|-1] [all]
 *   searches for column sets of size <= W with zero syndrome and nonzero logical.
 *   With orbits: case i = sets containing the first column of orbit i (its representative) and no column of
 *   orbits < i. -1 = all cases in sequence. 'all' = count every solution found (no early stop), only meaningful
 *   without pruning differences; default stops at the first solution of the case and prints it.
 * Completeness argument: see audit report (minimal-weight logicals have no zero-syndrome proper subset;
 *   disjoint branching on an unsatisfied row; popcount/maxweight bound).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

static int R, C, NO, NORB, NW, W, ALL;
static uint64_t *colbits;     /* C x NW */
static uint64_t *collog;      /* C */
static int *colorb, *colw;
static int **rowcols, *rowdeg;
static char *forb, *used;
static uint64_t *syn;         /* stack of syndromes: (W+2) x NW */
static int stack[256];
static long long nodes, found;
static int maxw;

static int popc(const uint64_t *s) { int p = 0; for (int i = 0; i < NW; i++) p += __builtin_popcountll(s[i]); return p; }

static void report(int depth) {
    printf("FOUND w=%d cols:", depth);
    for (int i = 0; i < depth; i++) printf(" %d", stack[i]);
    printf("\n"); fflush(stdout);
}

static int dfs(int depth, uint64_t lg) {
    nodes++;
    uint64_t *s = syn + (size_t)depth * NW;
    int pc = popc(s);
    if (pc == 0) {
        if (lg) { found++; report(depth); return ALL ? 0 : 1; }
        return 0;
    }
    int rem = W - depth;
    if (rem <= 0) return 0;
    if ((pc + maxw - 1) / maxw > rem) return 0;
    /* choose unsatisfied row with fewest allowed columns */
    int best = -1, bestc = 1 << 30;
    for (int wd = 0; wd < NW; wd++) {
        uint64_t x = s[wd];
        while (x) {
            int b = __builtin_ctzll(x); x &= x - 1;
            int r = wd * 64 + b;
            int cnt = 0;
            for (int k = 0; k < rowdeg[r]; k++) { int c = rowcols[r][k]; if (!forb[c] && !used[c]) cnt++; }
            if (cnt < bestc) { bestc = cnt; best = r; if (cnt == 0) return 0; }
        }
    }
    int *list = rowcols[best];
    int nl = rowdeg[best];
    int ret = 0;
    int nf = 0;
    int fl[4096];
    for (int k = 0; k < nl; k++) {
        int c = list[k];
        if (forb[c] || used[c]) continue;
        uint64_t *t = syn + (size_t)(depth + 1) * NW;
        const uint64_t *cb = colbits + (size_t)c * NW;
        for (int i = 0; i < NW; i++) t[i] = s[i] ^ cb[i];
        used[c] = 1; stack[depth] = c;
        int r = dfs(depth + 1, lg ^ collog[c]);
        used[c] = 0;
        if (r) { ret = 1; break; }
        if (nf >= 4096) { fprintf(stderr, "deg overflow\n"); exit(9); }
        forb[c] = 1; fl[nf++] = c;
    }
    for (int i = 0; i < nf; i++) forb[fl[i]] = 0;
    return ret;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage\n"); return 1; }
    FILE *f = fopen(argv[1], "r");
    W = atoi(argv[2]);
    int onecase = argc > 3 ? atoi(argv[3]) : -1;
    ALL = argc > 4 && !strcmp(argv[4], "all");
    if (fscanf(f, "%d %d %d %d", &R, &C, &NO, &NORB) != 4) return 2;
    if (NO > 64) { fprintf(stderr, "too many observables\n"); return 3; }
    NW = (R + 63) / 64;
    colbits = calloc((size_t)C * NW, 8); collog = calloc(C, 8); colorb = calloc(C, 4); colw = calloc(C, 4);
    rowdeg = calloc(R, sizeof(int)); rowcols = calloc(R, sizeof(int *));
    int **tmp = calloc(C, sizeof(int *));
    maxw = 0;
    for (int c = 0; c < C; c++) {
        int k; if (fscanf(f, "%d %d", &colorb[c], &k) != 2) return 4;
        tmp[c] = malloc(sizeof(int) * (k + 1)); tmp[c][0] = k;
        for (int i = 0; i < k; i++) {
            int r; if (fscanf(f, "%d", &r) != 1) return 5;
            tmp[c][i + 1] = r; colbits[(size_t)c * NW + r / 64] ^= 1ULL << (r % 64); rowdeg[r]++;
        }
        int j; if (fscanf(f, "%d", &j) != 1) return 6;
        for (int i = 0; i < j; i++) { int o; if (fscanf(f, "%d", &o) != 1) return 7; collog[c] ^= 1ULL << o; }
        colw[c] = k; if (k > maxw) maxw = k;
    }
    for (int r = 0; r < R; r++) { rowcols[r] = malloc(sizeof(int) * (rowdeg[r] + 1)); rowdeg[r] = 0; }
    for (int c = 0; c < C; c++) for (int i = 1; i <= tmp[c][0]; i++) { int r = tmp[c][i]; rowcols[r][rowdeg[r]++] = c; }
    forb = calloc(C, 1); used = calloc(C, 1);
    syn = calloc((size_t)(W + 2) * NW, 8);
    for (int c = 0; c < C; c++) if (colw[c] == 0 && collog[c]) { printf("weight-1 logical column %d\n", c); }
    int ncase = NORB > 0 ? NORB : C;   /* without orbits: case i = sets whose smallest column index is i */
    clock_t t0 = clock();
    long long totfound = 0;
    for (int cs = 0; cs < ncase; cs++) {
        if (onecase >= 0 && cs != onecase) continue;
        memset(forb, 0, C); memset(used, 0, C);
        int rep = -1;
        for (int c = 0; c < C; c++) {
            if (NORB > 0) { if (colorb[c] < cs) forb[c] = 1; if (colorb[c] == cs && rep < 0) rep = c; }
            else { if (c < cs) forb[c] = 1; if (c == cs) rep = c; }
        }
        if (rep < 0) continue;
        nodes = 0; found = 0;
        for (int i = 0; i < NW; i++) syn[i] = colbits[(size_t)rep * NW + i];
        used[rep] = 1; stack[0] = rep;
        /* shift: depth counts chosen columns; we start at depth 1 with syndrome in slot 1 */
        memcpy(syn + NW, syn, NW * 8);
        int r = dfs(1, collog[rep]);
        (void)r;
        totfound += found;
        if (NORB > 0 || found) printf("CASE %d rep %d nodes %lld found %lld cpu %.1f\n", cs, rep, nodes, found,
               (double)(clock() - t0) / CLOCKS_PER_SEC);
        fflush(stdout);
    }
    printf("SUMMARY W=%d found=%lld cpu=%.1f\n", W, totfound, (double)(clock() - t0) / CLOCKS_PER_SEC);
    return 0;
}
