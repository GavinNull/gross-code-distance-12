/* Auditor's independent exact search (E-029 audit).  Written from scratch; shares no code with ccsearch.c.
 *
 * Decide / enumerate x subset of columns with D x = 0, L x != 0, |x| <= W.
 *
 * Differences from ccsearch (deliberate, so that implementation bugs would not coincide):
 *   - last TWO levels by table lookup: a hash table of all column-pair syndromes (meet in the middle for the last
 *     two columns) + single-column table; no branching at budget 2;
 *   - branching row = fewest available covering columns, ties broken by HIGHEST row index;
 *   - packing bound computed with rows scanned from the highest index down, and conflicts restricted to
 *     currently AVAILABLE columns (tighter, still valid since x \ a is a subset of the available columns);
 *   - representative / orbit order taken from the instance file as given (myexport.py puts the max-index column
 *     first and orders orbits differently from export.py);
 *   - every reported solution is re-verified inside the program (distinct, zero syndrome, nonzero observable).
 * Completeness: (a) zero syndrome & zero observable partial set -> not extendable to a minimum solution;
 * (b) a column of x \ a covers any row of s; branch over available covering columns, each excluded for later
 * siblings; (c) root case o: rep_o in x, orbits < o excluded.
 *
 * usage: auditsearch INST decide|enum W [o0 o1]
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define NWMAX 10   /* was 8 for the R<=3 runs; 10 needed for c16 R=12 (585 detectors) */
typedef uint64_t u64;
typedef struct { u64 w[NWMAX]; } syn;

static int nr, nc, nobs, norb, NW, NCW, wmax, W, mode;
static syn *S; static u64 *Lo; static int *cw;
static int **rc, *rdeg;            /* row -> columns */
static u64 *avail;                 /* NCW words */
static int **orb, *osz, *oidx;
static long long nodes, nsol;
static int path[64], stopf;

static inline int av(int c) { return (avail[c >> 6] >> (c & 63)) & 1; }
static inline void setav(int c) { avail[c >> 6] |= 1ULL << (c & 63); }
static inline void clrav(int c) { avail[c >> 6] &= ~(1ULL << (c & 63)); }
static inline int pcnt(const syn *s) { int k = 0; for (int i = 0; i < NW; i++) k += __builtin_popcountll(s->w[i]); return k; }
static inline int zero(const syn *s) { for (int i = 0; i < NW; i++) if (s->w[i]) return 0; return 1; }
static inline int same(const syn *a, const syn *b) { for (int i = 0; i < NW; i++) if (a->w[i] != b->w[i]) return 0; return 1; }
static inline u64 hsh(const syn *s) { u64 h = 0x9E3779B97F4A7C15ULL; for (int i = 0; i < NW; i++) { h ^= s->w[i] + 0x9E3779B97F4A7C15ULL + (h << 6) + (h >> 2); h *= 0xff51afd7ed558ccdULL; } return h ^ (h >> 33); }

/* single table */
static int sh_size, *sh;
/* pair table: chained */
static int ph_size, *ph_head; static int *pn_next, *pa, *pb; static long long np;

static void build_tables(void) {
  sh_size = 1; while (sh_size < 4 * nc) sh_size <<= 1;
  sh = malloc(sizeof(int) * sh_size); for (int i = 0; i < sh_size; i++) sh[i] = -1;
  for (int c = 0; c < nc; c++) {
    u64 h = hsh(&S[c]) & (sh_size - 1);
    while (sh[h] >= 0) { if (same(&S[sh[h]], &S[c])) { fprintf(stderr, "dup syndrome\n"); exit(3); } h = (h + 1) & (sh_size - 1); }
    sh[h] = c;
  }
  long long npairs = (long long)nc * (nc - 1) / 2;
  ph_size = 1; while (ph_size < 2 * npairs) ph_size <<= 1;
  ph_head = malloc(sizeof(int) * ph_size); for (int i = 0; i < ph_size; i++) ph_head[i] = -1;
  pn_next = malloc(sizeof(int) * npairs); pa = malloc(sizeof(int) * npairs); pb = malloc(sizeof(int) * npairs);
  np = 0;
  for (int a = 0; a < nc; a++) for (int b = a + 1; b < nc; b++) {
    syn t; for (int i = 0; i < NW; i++) t.w[i] = S[a].w[i] ^ S[b].w[i];
    u64 h = hsh(&t) & (ph_size - 1);
    pa[np] = a; pb[np] = b; pn_next[np] = ph_head[h]; ph_head[h] = (int)np; np++;
  }
}
static int single(const syn *s) { u64 h = hsh(s) & (sh_size - 1); while (sh[h] >= 0) { if (same(&S[sh[h]], s)) return sh[h]; h = (h + 1) & (sh_size - 1); } return -1; }

static void verify_and_report(int depth) {
  syn t; memset(&t, 0, sizeof t); u64 L = 0;
  for (int i = 0; i < depth; i++) { for (int j = 0; j < i; j++) if (path[i] == path[j]) { fprintf(stderr, "BUG repeated column\n"); exit(5); }
    for (int k = 0; k < NW; k++) t.w[k] ^= S[path[i]].w[k]; L ^= Lo[path[i]]; }
  if (!zero(&t) || !L) { fprintf(stderr, "BUG invalid solution\n"); exit(5); }
  nsol++;
  printf("SOL %d obs=%llx :", depth, (unsigned long long)L);
  for (int i = 0; i < depth; i++) printf(" %d", path[i]);
  printf("\n"); fflush(stdout);
  if (mode == 0) stopf = 1;
}

static int lbound(const syn *s) {
  int w = pcnt(s);
  int lb1 = (w + wmax - 1) / wmax;
  syn t = *s; int lb2 = 0;
  for (int i = NW - 1; i >= 0; i--) {
    while (t.w[i]) {
      int r = i * 64 + 63 - __builtin_clzll(t.w[i]);
      lb2++;
      t.w[i] &= ~(1ULL << (r & 63));
      for (int j = 0; j < rdeg[r]; j++) { int c = rc[r][j]; if (av(c)) for (int k = 0; k < NW; k++) t.w[k] &= ~S[c].w[k]; }
    }
  }
  return lb1 > lb2 ? lb1 : lb2;
}

static void dfs(const syn *s, u64 L, int depth, int k) {
  nodes++;
  if (zero(s)) { if (L) verify_and_report(depth); return; }
  if (k <= 0) return;
  int c = single(s);
  if (c >= 0 && av(c) && (L ^ Lo[c])) { path[depth] = c; verify_and_report(depth + 1); if (stopf) return; }
  if (k == 1) return;
  if (k == 2) {
    u64 h = hsh(s) & (ph_size - 1);
    for (int e = ph_head[h]; e >= 0; e = pn_next[e]) {
      int a = pa[e], b = pb[e];
      if (!av(a) || !av(b)) continue;
      if (!(L ^ Lo[a] ^ Lo[b])) continue;
      int ok = 1; for (int i = 0; i < NW; i++) if ((S[a].w[i] ^ S[b].w[i]) != s->w[i]) { ok = 0; break; }
      if (!ok) continue;
      path[depth] = a; path[depth + 1] = b; verify_and_report(depth + 2); if (stopf) return;
    }
    return;
  }
  if (lbound(s) > k) return;
  /* branching row */
  int best = -1, bc = 1 << 30;
  for (int i = NW - 1; i >= 0; i--) { u64 t = s->w[i]; while (t) { int r = i * 64 + 63 - __builtin_clzll(t); t &= ~(1ULL << (r & 63));
      int cnt = 0; for (int j = 0; j < rdeg[r]; j++) cnt += av(rc[r][j]);
      if (cnt < bc) { bc = cnt; best = r; } } }
  if (bc == 0) return;
  int lst[2048], n = 0;
  for (int j = 0; j < rdeg[best]; j++) if (av(rc[best][j])) lst[n++] = rc[best][j];
  /* NOTE: single-column completion was handled above; children with budget k-1 also cover larger remainders */
  for (int i = 0; i < n && !stopf; i++) {
    int cc = lst[i]; clrav(cc);
    syn t; for (int q = 0; q < NW; q++) t.w[q] = s->w[q] ^ S[cc].w[q];
    path[depth] = cc;
    /* a single-column remainder {cc} is also found here (child has zero syndrome); duplicates with the lookup
       above are harmless in decide mode; enum mode dedups below by requiring child to have nonzero syndrome
       when the lookup already matched */
    if (mode == 1 && zero(&t)) { continue; }   /* already reported by the single() lookup */
    dfs(&t, L ^ Lo[cc], depth + 1, k - 1);
  }
  for (int i = 0; i < n; i++) setav(lst[i]);
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage\n"); return 1; }
  FILE *f = fopen(argv[1], "r"); if (!f) return 1;
  mode = !strcmp(argv[2], "enum"); W = atoi(argv[3]);
  if (fscanf(f, "%d %d %d %d", &nr, &nc, &nobs, &norb) != 4) return 2;
  NW = (nr + 63) / 64; NCW = (nc + 63) / 64; if (NW > NWMAX || nobs > 64) return 2;
  S = calloc(nc, sizeof(syn)); Lo = calloc(nc, 8); cw = calloc(nc, sizeof(int)); rdeg = calloc(nr, sizeof(int));
  int **tmp = malloc(sizeof(int *) * nc); wmax = 0;
  for (int c = 0; c < nc; c++) { int k; if (fscanf(f, "%d", &k) != 1) return 2; tmp[c] = malloc(sizeof(int) * (k + 1)); tmp[c][0] = k;
    for (int j = 0; j < k; j++) { int r; if (fscanf(f, "%d", &r) != 1) return 2; tmp[c][j + 1] = r; S[c].w[r >> 6] ^= 1ULL << (r & 63); rdeg[r]++; }
    if (k == 0) { fprintf(stderr, "empty column\n"); return 2; }
    cw[c] = k; if (k > wmax) wmax = k;
    int m; if (fscanf(f, "%d", &m) != 1) return 2; for (int j = 0; j < m; j++) { int o; if (fscanf(f, "%d", &o) != 1) return 2; Lo[c] ^= 1ULL << o; } }
  rc = malloc(sizeof(int *) * nr); for (int r = 0; r < nr; r++) { rc[r] = malloc(sizeof(int) * (rdeg[r] + 1)); if (rdeg[r] > 2048) return 4; rdeg[r] = 0; }
  for (int c = 0; c < nc; c++) for (int j = 1; j <= tmp[c][0]; j++) { int r = tmp[c][j]; rc[r][rdeg[r]++] = c; }
  orb = malloc(sizeof(int *) * norb); osz = malloc(sizeof(int) * norb); oidx = malloc(sizeof(int) * nc); for (int c = 0; c < nc; c++) oidx[c] = -1;
  for (int o = 0; o < norb; o++) { if (fscanf(f, "%d", &osz[o]) != 1) return 2; orb[o] = malloc(sizeof(int) * osz[o]);
    for (int j = 0; j < osz[o]; j++) { if (fscanf(f, "%d", &orb[o][j]) != 1) return 2; if (oidx[orb[o][j]] >= 0) return 6; oidx[orb[o][j]] = o; } }
  for (int c = 0; c < nc; c++) if (oidx[c] < 0) return 6;
  fclose(f);
  build_tables();
  int o0 = 0, o1 = norb; if (argc > 5) { o0 = atoi(argv[4]); o1 = atoi(argv[5]); }
  avail = calloc(NCW, 8);
  printf("AUDIT %s nr=%d nc=%d norb=%d wmax=%d pairs=%lld mode=%s W=%d orbits=[%d,%d)\n", argv[1], nr, nc, norb, wmax, np, argv[2], W, o0, o1); fflush(stdout);
  for (int o = o0; o < o1 && !stopf; o++) {
    memset(avail, 0, 8 * NCW);
    for (int c = 0; c < nc; c++) if (oidx[c] >= o) setav(c);
    int rep = orb[o][0]; clrav(rep); path[0] = rep;
    long long n0 = nodes, s0 = nsol; clock_t t0 = clock();
    dfs(&S[rep], Lo[rep], 1, W - 1);
    printf("ORBIT %d rep %d nodes %lld sols %lld cpu %.1fs\n", o, rep, nodes - n0, nsol - s0, (double)(clock() - t0) / CLOCKS_PER_SEC); fflush(stdout);
  }
  printf("DONE %s W=%d nodes %lld sols %lld cpu %.1fs\n", stopf ? "FOUND" : (nsol ? "ENUMERATED" : "NONE"), W, nodes, nsol, (double)clock() / CLOCKS_PER_SEC);
  return 0;
}
