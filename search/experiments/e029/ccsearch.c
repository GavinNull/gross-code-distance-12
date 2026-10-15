/* E-029 exact minimum-weight logical search on a parity-check / DEM matrix (own code, experimenter).
 *
 * Problem: columns c = 0..nc-1, each with a row set D_c (detectors or checks) and an observable mask L_c.
 * Find x (set of columns) with XOR_c D_c = 0, XOR_c L_c != 0, |x| <= W.
 *
 * Completeness:
 *  (a) a minimum-weight solution x has no nonempty proper subset y with D y = 0 (else y or x\y is a smaller
 *      solution), so a branch whose partial set has zero syndrome and zero observable can be closed;
 *  (b) for a partial set a of x with syndrome s != 0, the rest x\a must contain a column covering any fixed row
 *      r in s; branching on all available columns of r, each excluded for its later siblings, partitions the
 *      solutions extending a;
 *  (c) symmetry: if a group G permutes the columns, preserving zero syndrome and nonzero observable, every
 *      solution can be moved by G to one containing the representative of its lowest orbit and no column of
 *      a lower orbit.  Root case o: start from {rep_o}, exclude orbits < o.  (Orbit 'reps' = first column
 *      listed per orbit.)  With no symmetry, every column is its own orbit.
 *  Pruning (all valid lower bounds on the number of further columns needed to clear s):
 *      ceil(|s| / wmax) and a greedy packing: rows of s pairwise not covered by a common column need distinct
 *      columns.
 *  Last level by syndrome lookup (exact match of the remaining syndrome against an available column).
 *
 * Modes:
 *   decide W [o0 o1]      : stop at the first solution of weight <= W (reports it), else prints NONE
 *   enum W [o0 o1]        : print every solution with weight <= W found (minimal ones; see (a)); with a known
 *                           lower bound W on the distance these are exactly the weight-W solutions in the root
 *                           cases (each solution once per root case = once per its lowest-orbit rep inclusion)
 *   estimate W N [o0 o1]  : Knuth random-probe estimate of the node count (N probes per root case)
 *
 * Input (text): nr nc nobs norb / per column: k rows... m obs... / per orbit: size cols...
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define MAXW 32 /* up to 2048 rows */
typedef uint64_t u64;

static int nr, nc, nobs, norb, NW, NCW;
static u64 *colS;   /* nc * NW */
static u64 *colL;   /* nc (nobs <= 64) */
static int *colW;   /* row weight */
static int **rowcols, *rowdeg;
static u64 *rowmask; /* nr * NCW : columns covering row */
static u64 *conf;    /* nr * NW : rows sharing a column with row r (incl. r) */
static int *orbsz, **orbcols, *orbof;
static int wmax;
static u64 *avail;   /* NCW */
static long long nodes;
static int chosen[64];
static int mode; /* 0 decide 1 enum 2 estimate */
static long long nsol;
static int W;

/* hash: syndrome -> column (assumes distinct syndromes; checked) */
static int hsize; static int *htab;
static u64 hashS(const u64 *s) { u64 h = 1469598103934665603ULL; for (int i = 0; i < NW; i++) { h ^= s[i]; h *= 1099511628211ULL; h ^= h >> 29; } return h; }
static int eqS(const u64 *a, const u64 *b) { for (int i = 0; i < NW; i++) if (a[i] != b[i]) return 0; return 1; }
static void hput(int c) { u64 h = hashS(colS + (size_t)c * NW) & (hsize - 1); while (htab[h] >= 0) { if (eqS(colS + (size_t)htab[h] * NW, colS + (size_t)c * NW)) { fprintf(stderr, "duplicate syndrome cols %d %d\n", htab[h], c); exit(3);} h = (h + 1) & (hsize - 1);} htab[h] = c; }
static int hget(const u64 *s) { u64 h = hashS(s) & (hsize - 1); while (htab[h] >= 0) { if (eqS(colS + (size_t)htab[h] * NW, s)) return htab[h]; h = (h + 1) & (hsize - 1);} return -1; }

static inline int isav(int c) { return (avail[c >> 6] >> (c & 63)) & 1; }
static inline void setav(int c, int v) { if (v) avail[c >> 6] |= 1ULL << (c & 63); else avail[c >> 6] &= ~(1ULL << (c & 63)); }
static inline int pc(const u64 *s) { int k = 0; for (int i = 0; i < NW; i++) k += __builtin_popcountll(s[i]); return k; }
static inline int iszero(const u64 *s) { for (int i = 0; i < NW; i++) if (s[i]) return 0; return 1; }

static int lowerbound(const u64 *s) {
  int w = pc(s);
  int lb1 = (w + wmax - 1) / wmax;
  u64 t[MAXW]; memcpy(t, s, NW * 8);
  int lb2 = 0;
  for (int i = 0; i < NW; i++) {
    while (t[i]) {
      int r = i * 64 + __builtin_ctzll(t[i]);
      lb2++;
      const u64 *cf = conf + (size_t)r * NW;
      for (int j = 0; j < NW; j++) t[j] &= ~cf[j];
    }
  }
  return lb1 > lb2 ? lb1 : lb2;
}

static void report(int depth, u64 L) {
  nsol++;
  printf("SOL %d obs=%llx :", depth, (unsigned long long)L);
  for (int i = 0; i < depth; i++) printf(" %d", chosen[i]);
  printf("\n"); fflush(stdout);
}

/* choose row of s with the fewest available covering columns; returns row, count in *cnt */
static int pickrow(const u64 *s, int *cnt) {
  int best = -1, bc = 1 << 30;
  for (int i = 0; i < NW; i++) {
    u64 t = s[i];
    while (t) {
      int r = i * 64 + __builtin_ctzll(t); t &= t - 1;
      const u64 *rm = rowmask + (size_t)r * NCW;
      int k = 0;
      for (int j = 0; j < NCW; j++) k += __builtin_popcountll(rm[j] & avail[j]);
      if (k < bc) { bc = k; best = r; if (k <= 1) { *cnt = k; return r; } }
    }
  }
  *cnt = bc; return best;
}

static int stopflag;

/* s = syndrome of chosen[0..depth-1], L = observable; k = remaining budget */
static void dfs(const u64 *s, u64 L, int depth, int k) {
  nodes++;
  if (iszero(s)) {
    if (L) { report(depth, L); if (mode == 0) stopflag = 1; }
    return; /* zero-syndrome, trivial: not minimal -> close (a) */
  }
  if (k == 0) return;
  if (lowerbound(s) > k) return;
  if (k == 1) {
    int c = hget(s);
    if (c >= 0 && isav(c)) {
      u64 L2 = L ^ colL[c];
      if (L2) { chosen[depth] = c; nodes++; report(depth + 1, L2); if (mode == 0) stopflag = 1; }
    }
    return;
  }
  int cnt; int r = pickrow(s, &cnt);
  if (cnt == 0) return;
  int list[4096]; int n = 0;
  for (int j = 0; j < rowdeg[r]; j++) { int c = rowcols[r][j]; if (isav(c)) list[n++] = c; }
  u64 s2[MAXW];
  for (int i = 0; i < n && !stopflag; i++) {
    int c = list[i];
    setav(c, 0);
    for (int j = 0; j < NW; j++) s2[j] = s[j] ^ colS[(size_t)c * NW + j];
    chosen[depth] = c;
    dfs(s2, L ^ colL[c], depth + 1, k - 1);
    /* c stays unavailable for later siblings (b) */
  }
  for (int i = 0; i < n; i++) setav(list[i], 1);
}

/* Knuth estimator: one random path; returns estimated node count of the subtree */
static double probe(const u64 *s0, u64 L0, int k0, int depth0) {
  u64 s[MAXW]; memcpy(s, s0, NW * 8); u64 L = L0; int k = k0; double est = 0, mult = 1;
  int removed[64][2]; int nrm = 0; int depth = depth0;
  /* we must emulate exclusion: choosing child i means siblings 0..i-1 are excluded */
  int excl[8192]; int nex = 0;
  while (1) {
    est += mult;
    if (iszero(s)) break;
    if (k == 0) break;
    if (lowerbound(s) > k) break;
    if (k == 1) { int c = hget(s); if (c >= 0 && isav(c)) est += mult; break; }
    int cnt; int r = pickrow(s, &cnt);
    if (cnt == 0) break;
    int list[4096]; int n = 0;
    for (int j = 0; j < rowdeg[r]; j++) { int c = rowcols[r][j]; if (isav(c)) list[n++] = c; }
    int i = rand() % n;
    for (int j = 0; j <= i; j++) { setav(list[j], 0); excl[nex++] = list[j]; }
    int c = list[i];
    for (int j = 0; j < NW; j++) s[j] ^= colS[(size_t)c * NW + j];
    L ^= colL[c]; k--; depth++;
    mult *= n;
  }
  for (int j = 0; j < nex; j++) setav(excl[j], 1);
  (void)removed; (void)nrm;
  return est;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: %s inst decide|enum|estimate W [N] [o0 o1]\n", argv[0]); return 1; }
  FILE *f = fopen(argv[1], "r"); if (!f) { perror("open"); return 1; }
  mode = !strcmp(argv[2], "decide") ? 0 : !strcmp(argv[2], "enum") ? 1 : 2;
  W = atoi(argv[3]);
  int ai = 4; int N = 0;
  if (mode == 2) N = atoi(argv[ai++]);
  if (fscanf(f, "%d %d %d %d", &nr, &nc, &nobs, &norb) != 4) return 2;
  NW = (nr + 63) / 64; NCW = (nc + 63) / 64;
  if (NW > MAXW || nobs > 64) { fprintf(stderr, "too large\n"); return 2; }
  colS = calloc((size_t)nc * NW, 8); colL = calloc(nc, 8); colW = calloc(nc, sizeof(int));
  rowdeg = calloc(nr, sizeof(int)); rowcols = calloc(nr, sizeof(int *));
  int **tmp = calloc(nc, sizeof(int *));
  wmax = 0;
  for (int c = 0; c < nc; c++) {
    int k; if (fscanf(f, "%d", &k) != 1) return 2;
    tmp[c] = malloc((k + 1) * sizeof(int)); tmp[c][0] = k;
    for (int j = 0; j < k; j++) { int r; if (fscanf(f, "%d", &r) != 1) return 2; tmp[c][j + 1] = r; colS[(size_t)c * NW + r / 64] ^= 1ULL << (r % 64); rowdeg[r]++; }
    colW[c] = k; if (k > wmax) wmax = k;
    int m; if (fscanf(f, "%d", &m) != 1) return 2;
    for (int j = 0; j < m; j++) { int o; if (fscanf(f, "%d", &o) != 1) return 2; colL[c] ^= 1ULL << o; }
  }
  for (int r = 0; r < nr; r++) { rowcols[r] = malloc((rowdeg[r] + 1) * sizeof(int)); rowdeg[r] = 0; }
  for (int c = 0; c < nc; c++) for (int j = 1; j <= tmp[c][0]; j++) { int r = tmp[c][j]; rowcols[r][rowdeg[r]++] = c; }
  rowmask = calloc((size_t)nr * NCW, 8); conf = calloc((size_t)nr * NW, 8);
  for (int r = 0; r < nr; r++) for (int j = 0; j < rowdeg[r]; j++) { int c = rowcols[r][j]; rowmask[(size_t)r * NCW + c / 64] |= 1ULL << (c % 64); for (int i = 0; i < NW; i++) conf[(size_t)r * NW + i] |= colS[(size_t)c * NW + i]; }
  for (int r = 0; r < nr; r++) conf[(size_t)r * NW + r / 64] |= 1ULL << (r % 64);
  orbsz = calloc(norb, sizeof(int)); orbcols = calloc(norb, sizeof(int *)); orbof = malloc(nc * sizeof(int));
  for (int c = 0; c < nc; c++) orbof[c] = -1;
  for (int o = 0; o < norb; o++) { if (fscanf(f, "%d", &orbsz[o]) != 1) return 2; orbcols[o] = malloc(orbsz[o] * sizeof(int)); for (int j = 0; j < orbsz[o]; j++) { if (fscanf(f, "%d", &orbcols[o][j]) != 1) return 2; orbof[orbcols[o][j]] = o; } }
  for (int c = 0; c < nc; c++) if (orbof[c] < 0) { fprintf(stderr, "column %d in no orbit\n", c); return 2; }
  fclose(f);
  hsize = 1; while (hsize < 4 * nc) hsize <<= 1; htab = malloc(hsize * sizeof(int)); memset(htab, -1, hsize * sizeof(int));
  int zerocols = 0;
  for (int c = 0; c < nc; c++) { if (colW[c] == 0) { zerocols++; if (colL[c]) { printf("WEIGHT1 logical column %d\n", c); } continue; } hput(c); }
  int o0 = 0, o1 = norb;
  if (argc > ai + 1) { o0 = atoi(argv[ai]); o1 = atoi(argv[ai + 1]); }
  avail = calloc(NCW, 8);
  printf("INST %s nr=%d nc=%d nobs=%d norb=%d wmax=%d zerocols=%d mode=%s W=%d orbits=[%d,%d)\n", argv[1], nr, nc, nobs, norb, wmax, zerocols, argv[2], W, o0, o1);
  fflush(stdout);
  srand(12345);
  double esttot = 0;
  for (int o = o0; o < o1 && !stopflag; o++) {
    for (int c = 0; c < nc; c++) setav(c, orbof[c] >= o && colW[c] > 0);
    int rep = orbcols[o][0];
    if (colW[rep] == 0) continue;
    setav(rep, 0);
    chosen[0] = rep;
    long long n0 = nodes, s0 = nsol; clock_t t0 = clock();
    if (mode == 2) {
      double e = 0; for (int p = 0; p < N; p++) e += probe(colS + (size_t)rep * NW, colL[rep], W - 1, 1);
      e /= N; esttot += e;
      printf("EST orbit %d size %d est_nodes %.3e (%.1fs)\n", o, orbsz[o], e, (double)(clock() - t0) / CLOCKS_PER_SEC);
    } else {
      dfs(colS + (size_t)rep * NW, colL[rep], 1, W - 1);
      printf("ORBIT %d size %d nodes %lld sols %lld cpu %.1fs\n", o, orbsz[o], nodes - n0, nsol - s0, (double)(clock() - t0) / CLOCKS_PER_SEC);
    }
    fflush(stdout);
  }
  if (mode == 2) printf("EST_TOTAL %.3e\n", esttot);
  else printf("DONE %s W=%d nodes %lld sols %lld cpu %.1fs\n", stopflag ? "FOUND" : (nsol ? "ENUMERATED" : "NONE"), W, nodes, nsol, (double)clock() / CLOCKS_PER_SEC);
  return 0;
}
