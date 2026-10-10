/* E-022 audit: independent lower-bound checker (different algorithm from mdfs).
 * Exhaustively enumerates every CONNECTED column set (columns adjacent iff they share a detector) of size <= W
 * that contains the representative (first column) of orbit o and only columns of orbits >= o, for every o
 * (ESU enumeration: each connected set exactly once, no syndrome-based pruning), and reports sets with zero
 * syndrome and nonzero logical. Completeness: a minimum-weight undetected logical has no zero-syndrome proper
 * subset, hence is connected; K-translations permute columns within orbits, so some image contains the rep of
 * its smallest orbit.  Input: mdfs instance format.  usage: cenum file W */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
static int R, C, NO, NORB, NW, W;
static uint64_t *cb, *cl; static int *corb, **adj, *deg;
static long long nsets, nfound;
static int cur[64]; static uint64_t syn[64][16];
static char *inset, *inext;
static void rec(int depth, int *ext, int next, int root, int minorb, uint64_t lg) {
    /* current set cur[0..depth-1], syndrome syn[depth-1] */
    nsets++;
    int z = 1; for (int i = 0; i < NW; i++) if (syn[depth-1][i]) { z = 0; break; }
    if (z && lg) { nfound++; if (nfound <= 3) { printf("FOUND w=%d cols:", depth); for (int i = 0; i < depth; i++) printf(" %d", cur[i]); printf("\n"); } }
    if (depth == W) return;
    /* ESU: while ext nonempty pick w, remove; new ext' = ext ∪ {u in N_excl(w, current set) : u > root, orb ok} */
    int *mine = malloc(sizeof(int) * (next + 4096)); int nm = 0;
    for (int k = next - 1; k >= 0; k--) {
        int w = ext[k];
        int n2 = 0;
        for (int i = 0; i < k; i++) mine[n2++] = ext[i];
        /* exclusive neighbours of w: not in set, not adjacent to set, not in ext (marked by inext) */
        int added0 = n2;
        for (int a = 0; a < deg[w]; a++) {
            int u = adj[w][a];
            if (u == root || inset[u] || inext[u] || corb[u] < minorb) continue;
            if (corb[u] == minorb && u < root) continue;
            /* exclusive: u not adjacent to any current set member */
            int bad = 0;
            for (int s = 0; s < depth && !bad; s++) { int x = cur[s]; for (int i = 0; i < NW; i++) if (cb[(size_t)u*NW+i] & cb[(size_t)x*NW+i]) { bad = 1; break; } }
            if (bad) continue;
            int dup = 0; for (int i = added0; i < n2; i++) if (mine[i] == u) { dup = 1; break; }
            if (!dup) mine[n2++] = u;
        }
        for (int i = added0; i < n2; i++) inext[mine[i]] = 1;
        cur[depth] = w; inset[w] = 1;
        for (int i = 0; i < NW; i++) syn[depth][i] = syn[depth-1][i] ^ cb[(size_t)w*NW+i];
        int *cp = malloc(sizeof(int) * (n2 + 1)); memcpy(cp, mine, sizeof(int) * n2);
        rec(depth + 1, cp, n2, root, minorb, lg ^ cl[w]);
        free(cp);
        inset[w] = 0;
        for (int i = added0; i < n2; i++) inext[mine[i]] = 0;
    }
    free(mine); (void)nm;
}
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "r"); W = atoi(argv[2]);
    if (fscanf(f, "%d %d %d %d", &R, &C, &NO, &NORB) != 4) return 2;
    NW = (R + 63) / 64; if (NW > 16) return 3;
    cb = calloc((size_t)C * NW, 8); cl = calloc(C, 8); corb = calloc(C, 4);
    int **cr = calloc(C, sizeof(int*)); int *ck = calloc(C, 4);
    int **rc = calloc(R, sizeof(int*)); int *rd = calloc(R, 4);
    for (int c = 0; c < C; c++) {
        int k; if (fscanf(f, "%d %d", &corb[c], &k) != 2) return 4;
        if (NORB == 0) corb[c] = 0;
        cr[c] = malloc(4 * (k + 1)); ck[c] = k;
        for (int i = 0; i < k; i++) { int r; if (fscanf(f, "%d", &r) != 1) return 5; cr[c][i] = r; cb[(size_t)c*NW + r/64] ^= 1ULL << (r%64); rd[r]++; }
        int j; if (fscanf(f, "%d", &j) != 1) return 6;
        for (int i = 0; i < j; i++) { int o; if (fscanf(f, "%d", &o) != 1) return 7; cl[c] ^= 1ULL << o; }
    }
    for (int r = 0; r < R; r++) { rc[r] = malloc(4 * (rd[r] + 1)); rd[r] = 0; }
    for (int c = 0; c < C; c++) for (int i = 0; i < ck[c]; i++) { int r = cr[c][i]; rc[r][rd[r]++] = c; }
    adj = calloc(C, sizeof(int*)); deg = calloc(C, 4);
    char *mark = calloc(C, 1);
    for (int c = 0; c < C; c++) {
        int n = 0; int *tmp = malloc(4 * C);
        for (int i = 0; i < ck[c]; i++) { int r = cr[c][i]; for (int a = 0; a < rd[r]; a++) { int u = rc[r][a]; if (u != c && !mark[u]) { mark[u] = 1; tmp[n++] = u; } } }
        for (int i = 0; i < n; i++) mark[tmp[i]] = 0;
        adj[c] = tmp; deg[c] = n;
    }
    for (int c = 0; c < C; c++) if (ck[c] == 0 && cl[c]) printf("FOUND w=1 (empty column) %d\n", c);
    inset = calloc(C, 1); inext = calloc(C, 1);
    int norb = NORB > 0 ? NORB : 1;
    for (int o = 0; o < norb; o++) {
        /* roots: with orbits, root = first column of orbit o; without orbits every column is a root (min index) */
        for (int root = 0; root < C; root++) {
            if (NORB > 0) { int first = -1; for (int c = 0; c < C; c++) if (corb[c] == o) { first = c; break; } if (root != first) continue; }
            int minorb = NORB > 0 ? o : 0;
            /* without orbits: only columns > root allowed (minorb 0, all corb 0 -> 'u < root' excluded) */
            cur[0] = root; inset[root] = 1;
            for (int i = 0; i < NW; i++) syn[0][i] = cb[(size_t)root*NW+i];
            int *ext = malloc(4 * (deg[root] + 1)); int ne = 0;
            for (int a = 0; a < deg[root]; a++) { int u = adj[root][a]; if (corb[u] < minorb) continue; if (corb[u] == minorb && u < root) continue; ext[ne++] = u; }
            for (int i = 0; i < ne; i++) inext[ext[i]] = 1;
            rec(1, ext, ne, root, minorb, cl[root]);
            for (int i = 0; i < ne; i++) inext[ext[i]] = 0;
            inset[root] = 0; free(ext);
        }
    }
    printf("SUMMARY W=%d connected_sets=%lld found=%lld\n", W, nsets, nfound);
    return 0;
}
