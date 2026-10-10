/* [E-021] copy of e014/dfs128_all.c; only change: env STOPFIRST=k exits after the k-th solution is printed. */
/* [E-014, lead] 128-bit port of the E-013 auditor's DFS: only the syndrome type changes (uint64 -> unsigned __int128),
 * the instance format gains a high word for He, and popcount/ctz/hash use both halves.  Algorithm unchanged.
 * Original header follows.
 * Auditor's exhaustive search for a logical of weight <= W in an extended code (He: r<=64 rows, Le: <=8 rows).
 * Complete for the question "is there x with He x = 0, Le x != 0, |x| <= W" under the symmetry reduction
 * described in the report:
 *   - a minimum-weight logical x* is syndrome-minimal (no proper nonempty subset with He-syndrome 0), so a
 *     syndrome-driven DFS that stops at syndrome 0 reaches it;
 *   - x* contains a column from its lowest-index orbit o; translating, x* contains rep(o) and no column of
 *     orbits < o.  Case o: start {rep(o)}, forbid orbits < o.
 *   - branching: pick an odd row r of the current syndrome; x*\S must contain a column of r; branch over the
 *     available columns c_1..c_k of r, forbidding c_1..c_{i-1} in branch i (disjoint, exhaustive split).
 *   - prune: k + ceil(popcount(syn)/wmax) > W;  an odd row with no available column.
 *   - leaves: with 1 column left, look syn up among available columns; with 2 left, branch once more then look up.
 * usage: dfs inst.txt W case [split_mod split_idx]   (split on the first branching level)
 * prints FOUND lines with column indices, and a summary.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#define MAXN 512
#define MAXR 128
typedef unsigned __int128 u128;
static inline int pc128(u128 x){ return __builtin_popcountll((uint64_t)x) + __builtin_popcountll((uint64_t)(x>>64)); }
static inline int ctz128(u128 x){ uint64_t lo=(uint64_t)x; return lo ? __builtin_ctzll(lo) : 64 + __builtin_ctzll((uint64_t)(x>>64)); }
static int R, N, NO, W;
static u128 ch[MAXN]; static int cl[MAXN], corb[MAXN], cw[MAXN];
static int reps[MAXN];
static int rowc[MAXR][MAXN], rown[MAXR];
static int avail_cnt[MAXR];
static char forb[MAXN], chosen[MAXN];
static int stack_[64]; static int depth;
static long long nodes = 0, found = 0;
static int wmax = 1;
static int split_mod = 1, split_idx = 0; static long long stopfirst = 0;
/* hash: syndrome -> columns with that He vector (several columns can share He with different Le) */
#define HS (1<<16)
static int hhead[HS], hnext[MAXN];
static unsigned hidx(u128 hh){ uint64_t h = (uint64_t)hh ^ ((uint64_t)(hh>>64) * 0x9e3779b97f4a7c15ULL); h ^= h>>29; h *= 0xbf58476d1ce4e5b9ULL; h ^= h>>32; return (unsigned)(h & (HS-1)); }

static void mark(int c, int delta){ /* delta=-1 makes c unavailable, +1 available */
  u128 h = ch[c]; while (h){ int i = ctz128(h); h &= h-1; avail_cnt[i] += delta; } }

static void report(int extra1, int extra2, int lm){
  found++;
  if (found <= 100000){
    printf("FOUND w=%d lm=%d cols:", depth + (extra1>=0) + (extra2>=0), lm);
    for (int i=0;i<depth;i++) printf(" %d", stack_[i]);
    if (extra2>=0) printf(" %d", extra2);
    if (extra1>=0) printf(" %d", extra1);
    printf("\n"); fflush(stdout);
  }
  if (stopfirst && found >= stopfirst) { printf("STOPPED nodes=%lld\n", nodes); fflush(stdout); exit(0); }
}

static void dfs(u128 syn, int lm, int level){
  nodes++;
  if (syn == 0){ if (lm) report(-1,-1,lm); return; }
  int rem = W - depth;
  int u = pc128(syn);
  if (rem <= 0) return;
  if ((u + wmax - 1) / wmax > rem) return;
  if (rem == 1){
    for (int c = hhead[hidx(syn)]; c >= 0; c = hnext[c])
      if (ch[c] == syn && !forb[c] && !chosen[c] && (lm ^ cl[c])) report(c,-1,lm^cl[c]);
    return;
  }
  /* choose odd row with fewest available columns */
  int best = -1, bc = 1<<30; u128 s = syn;
  while (s){ int i = ctz128(s); s &= s-1; if (avail_cnt[i] < bc){ bc = avail_cnt[i]; best = i; } }
  if (bc == 0) return;
  int tried[MAXN]; int nt = 0; int bi = 0;
  for (int k = 0; k < rown[best]; k++){
    int c = rowc[best][k];
    if (forb[c] || chosen[c]) continue;
    int my = bi++;
    if (level == 0 && split_mod > 1 && (my % split_mod) != split_idx){
      /* not ours: still must forbid it for the following siblings (disjoint split) */
      forb[c] = 1; mark(c,-1); tried[nt++] = c; continue; }
    chosen[c] = 1; mark(c,-1); stack_[depth++] = c;
    dfs(syn ^ ch[c], lm ^ cl[c], level+1);
    depth--; chosen[c] = 0;
    forb[c] = 1; tried[nt++] = c; /* stays unavailable */
  }
  for (int k = 0; k < nt; k++){ forb[tried[k]] = 0; mark(tried[k], +1); }
}

int main(int argc, char **argv){
  if (argc < 4){ fprintf(stderr, "usage\n"); return 1; }
  FILE *f = fopen(argv[1], "r"); if (!f){ fprintf(stderr, "cannot open %s\n", argv[1]); return 5; } W = atoi(argv[2]); int cs = atoi(argv[3]);
  if (argc >= 6){ split_mod = atoi(argv[4]); split_idx = atoi(argv[5]); }
  if (fscanf(f, "%d %d %d", &R, &N, &NO) != 3) return 2;
  for (int j=0;j<N;j++){ unsigned long long lo, hi; if (fscanf(f, "%llu %llu %d %d", &lo, &hi, &cl[j], &corb[j]) != 4) return 3; ch[j]=((u128)hi<<64)|lo; cw[j]=pc128(ch[j]); if (cw[j]>wmax) wmax=cw[j]; }
  for (int o=0;o<NO;o++) if (fscanf(f, "%d", &reps[o]) != 1) return 4;
  if (getenv("STOPFIRST")) stopfirst = atoll(getenv("STOPFIRST"));
  memset(hhead, -1, sizeof hhead);
  for (int j=N-1;j>=0;j--){ unsigned b = hidx(ch[j]); hnext[j] = hhead[b]; hhead[b] = j; }
  for (int j=0;j<N;j++){ u128 h = ch[j]; while (h){ int i=ctz128(h); h&=h-1; rowc[i][rown[i]++] = j; } }
  for (int i=0;i<R;i++) avail_cnt[i] = rown[i];
  clock_t t0 = clock();
  /* case cs: forbid orbits < cs, choose rep */
  for (int j=0;j<N;j++) if (corb[j] < cs){ forb[j]=1; mark(j,-1); }
  int c0 = reps[cs];
  chosen[c0]=1; mark(c0,-1); stack_[depth++] = c0;
  dfs(ch[c0], cl[c0], 0);
  double sec = (double)(clock()-t0)/CLOCKS_PER_SEC;
  printf("SUMMARY W=%d case=%d split=%d/%d nodes=%lld found=%lld wmax=%d sec=%.1f\n", W, cs, split_idx, split_mod, nodes, found, wmax, sec);
  return 0;
}
