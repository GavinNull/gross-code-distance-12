/* Exhaustive search for low-weight undetected logicals of a binary column system (SM S5, second implementation):
   column j has a syndrome s_j (NBIT bits, NW 64-bit words) and a logical part l_j (<= 64 bits).  A solution is a
   set x of distinct columns with sum s = 0 and sum l != 0.  Used by code/p11/direct.py on the full SD6 detector error
   model (column = DEM mechanism, syndrome = its detectors, logical part = its observables).

   Algorithm: symmetry root cases (orbit o: x contains rep_o and no column of an orbit < o) + depth-first
   syndrome-driven branching down to `look` remaining columns, then a meet-in-the-middle terminal: all subsets of
   size 1..look of all columns are tabulated by syndrome (sorted array, binary search), so the last `look` columns
   are never branched on.  At an inner node with syndrome s != 0 a row r of s is chosen (fewest available covering
   columns, ties: lowest row) and the branches are "first column of x in the list of available columns covering r
   is list[i]" (list[0..i-1] removed from the available set): an exact partition.  A node with s = 0 is reported if
   l != 0 and otherwise pruned (a minimal-weight solution contains no proper subset with s = 0 and l = 0, so the
   pruning loses no minimal-weight solution).  Lower bound: ceil(|s| / wmax), wmax = largest column weight.
   Every reported set is re-verified here (distinct, s = 0, l != 0).

   input (stdin): ncol nbit
                  per column: hw h_1..h_hw  lw l_1..l_lw   (row indices of s_j, bit indices of l_j)
                  norb  orbit_of[0..ncol-1]  rep[0..norb-1]
   argv:          W mode(enum|decide) look(1..3) [o_lo o_hi]
   output:        "SOL w c1 ... cw" lines on stdout; one "CASE ..." line per root case and a "DONE ..." line on stderr.
   build:         cc -O3 -DNW=4 -o mitm code/p11/mitm.c          (NW * 64 >= number of detectors)  */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#ifndef NW
#define NW 4
#endif
typedef struct { uint64_t w[NW]; } syn;
static int ncol, nbit, norb, *orb, *rep, W, decide, look;
static syn *S; static uint64_t *Lg; static int *wt;
static int **rowcols, *nrowcols; /* columns covering each row */
static char *avail;
static long long nodes = 0, nsol = 0; static int stopflag = 0;
static int cur[64], ncur = 0;

static inline int iszero(const syn *a) { for (int i = 0; i < NW; i++) if (a->w[i]) return 0; return 1; }
static inline void sxor(syn *a, const syn *b) { for (int i = 0; i < NW; i++) a->w[i] ^= b->w[i]; }
static inline int scmp(const syn *a, const syn *b) {
  for (int i = NW - 1; i >= 0; i--) { if (a->w[i] < b->w[i]) return -1; if (a->w[i] > b->w[i]) return 1; } return 0; }
static inline int pc(const syn *a) { int c = 0; for (int i = 0; i < NW; i++) c += __builtin_popcountll(a->w[i]); return c; }

typedef struct { syn k; uint16_t c[3]; } ent;
static ent *T[4]; static long nT[4];
static int cmpent(const void *x, const void *y) { return scmp(&((const ent *)x)->k, &((const ent *)y)->k); }

static void build_tables(void) {
  for (int sz = 1; sz <= look; sz++) {
    long cap = 1; for (int i = 0; i < sz; i++) cap = cap * (ncol - i) / (i + 1);
    T[sz] = malloc(sizeof(ent) * (cap + 1)); long c = 0;
    if (sz == 1) for (int a = 0; a < ncol; a++) { T[1][c].k = S[a]; T[1][c].c[0] = a; c++; }
    if (sz == 2) for (int a = 0; a < ncol; a++) for (int b = a + 1; b < ncol; b++) {
      syn k = S[a]; sxor(&k, &S[b]); T[2][c].k = k; T[2][c].c[0] = a; T[2][c].c[1] = b; c++; }
    if (sz == 3) for (int a = 0; a < ncol; a++) for (int b = a + 1; b < ncol; b++) {
      syn k2 = S[a]; sxor(&k2, &S[b]);
      for (int d = b + 1; d < ncol; d++) { syn k = k2; sxor(&k, &S[d]); T[3][c].k = k;
        T[3][c].c[0] = a; T[3][c].c[1] = b; T[3][c].c[2] = d; c++; } }
    nT[sz] = c; qsort(T[sz], c, sizeof(ent), cmpent);
    fprintf(stderr, "table %d: %ld entries\n", sz, c);
  }
}

static void report(int extra, const uint16_t *ex) {
  int set[64], n = 0; for (int i = 0; i < ncur; i++) set[n++] = cur[i]; for (int i = 0; i < extra; i++) set[n++] = ex[i];
  /* verify */
  syn s; memset(&s, 0, sizeof s); uint64_t l = 0;
  for (int i = 0; i < n; i++) { for (int j = 0; j < i; j++) if (set[i] == set[j]) { fprintf(stderr, "DUP\n"); exit(3); }
    sxor(&s, &S[set[i]]); l ^= Lg[set[i]]; }
  if (!iszero(&s) || !l) { fprintf(stderr, "BAD SOLUTION\n"); exit(4); }
  /* sort for output */
  for (int i = 1; i < n; i++) { int v = set[i], j = i - 1; while (j >= 0 && set[j] > v) { set[j + 1] = set[j]; j--; } set[j + 1] = v; }
  printf("SOL %d", n); for (int i = 0; i < n; i++) printf(" %d", set[i]); printf("\n");
  nsol++; if (decide) stopflag = 1;
}

static int wmax;
static void dfs(syn *s, uint64_t l, int k) {
  nodes++;
  if (stopflag) return;
  if (iszero(s)) { if (l && ncur > 0) report(0, NULL); return; }
  if (k == 0) return;
  int p = pc(s);
  if ((p + wmax - 1) / wmax > k) return;
  if (k <= look) {
    for (int sz = 1; sz <= k; sz++) {
      /* binary search */
      long lo = 0, hi = nT[sz];
      while (lo < hi) { long md = (lo + hi) / 2; if (scmp(&T[sz][md].k, s) < 0) lo = md + 1; else hi = md; }
      for (long i = lo; i < nT[sz] && scmp(&T[sz][i].k, s) == 0; i++) {
        int ok = 1; uint64_t ll = l;
        for (int q = 0; q < sz; q++) { if (!avail[T[sz][i].c[q]]) { ok = 0; break; } ll ^= Lg[T[sz][i].c[q]]; }
        if (ok && ll) report(sz, T[sz][i].c);
        if (stopflag) return;
      }
    }
    return;
  }
  /* choose row of s with fewest available covering columns */
  int best = -1, bc = 1 << 30;
  for (int wi = 0; wi < NW; wi++) { uint64_t x = s->w[wi]; while (x) { int b = __builtin_ctzll(x); x &= x - 1; int r = wi * 64 + b;
      int c = 0; for (int i = 0; i < nrowcols[r]; i++) c += avail[rowcols[r][i]];
      if (c < bc) { bc = c; best = r; } } }
  if (bc == 0) return;
  int list[512], nl = 0;
  for (int i = 0; i < nrowcols[best]; i++) if (avail[rowcols[best][i]]) list[nl++] = rowcols[best][i];
  for (int i = 0; i < nl && !stopflag; i++) {
    int c = list[i]; avail[c] = 0; cur[ncur++] = c;
    syn s2 = *s; sxor(&s2, &S[c]);
    dfs(&s2, l ^ Lg[c], k - 1);
    ncur--;               /* c stays unavailable for later siblings */
  }
  for (int i = 0; i < nl; i++) avail[list[i]] = 1;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: W enum|decide look [olo ohi]\n"); return 1; }
  W = atoi(argv[1]); decide = !strcmp(argv[2], "decide"); look = atoi(argv[3]);
  if (scanf("%d %d", &ncol, &nbit) != 2) return 1;
  if (nbit > 64 * NW || ncol > 65535) { fprintf(stderr, "too big\n"); return 1; }
  S = calloc(ncol, sizeof(syn)); Lg = calloc(ncol, 8); wt = calloc(ncol, sizeof(int));
  nrowcols = calloc(nbit, sizeof(int)); rowcols = calloc(nbit, sizeof(int *));
  int **tmp = calloc(ncol, sizeof(int *));
  for (int j = 0; j < ncol; j++) {
    int hw; scanf("%d", &hw); tmp[j] = malloc(sizeof(int) * (hw + 1)); tmp[j][0] = hw;
    for (int i = 0; i < hw; i++) { int r; scanf("%d", &r); tmp[j][i + 1] = r; S[j].w[r / 64] ^= 1ULL << (r % 64); nrowcols[r]++; }
    int lw; scanf("%d", &lw); for (int i = 0; i < lw; i++) { int b; scanf("%d", &b); Lg[j] ^= 1ULL << b; }
    wt[j] = pc(&S[j]);
  }
  for (int r = 0; r < nbit; r++) { rowcols[r] = malloc(sizeof(int) * (nrowcols[r] + 1)); nrowcols[r] = 0; }
  for (int j = 0; j < ncol; j++) for (int i = 0; i < tmp[j][0]; i++) { int r = tmp[j][i + 1]; rowcols[r][nrowcols[r]++] = j; }
  scanf("%d", &norb); orb = malloc(sizeof(int) * ncol); rep = malloc(sizeof(int) * norb);
  for (int j = 0; j < ncol; j++) scanf("%d", &orb[j]);
  for (int o = 0; o < norb; o++) scanf("%d", &rep[o]);
  /* sanity: distinct nonzero columns */
  for (int j = 0; j < ncol; j++) if (iszero(&S[j]) && !Lg[j]) { fprintf(stderr, "zero column %d\n", j); return 2; }
  wmax = 0; for (int j = 0; j < ncol; j++) if (wt[j] > wmax) wmax = wt[j];
  int olo = 0, ohi = norb - 1; if (argc >= 6) { olo = atoi(argv[4]); ohi = atoi(argv[5]); }
  build_tables();
  avail = calloc(ncol, 1);
  for (int o = olo; o <= ohi && !stopflag; o++) {
    long long n0 = nodes, s0 = nsol;
    for (int j = 0; j < ncol; j++) avail[j] = orb[j] >= o;
    int r = rep[o]; avail[r] = 0; ncur = 0; cur[ncur++] = r;
    syn s = S[r];
    dfs(&s, Lg[r], W - 1);
    fprintf(stderr, "CASE orbit=%d rep=%d nodes=%lld sols=%lld\n", o, r, nodes - n0, nsol - s0);
    fflush(stdout);
  }
  fprintf(stderr, "DONE W=%d mode=%s look=%d nodes=%lld sols=%lld stop=%d\n", W, argv[2], look, nodes, nsol, stopflag);
  return 0;
}
