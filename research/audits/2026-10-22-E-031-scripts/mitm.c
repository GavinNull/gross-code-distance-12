/* Auditor's own meet-in-the-middle enumerator of all extended-code logicals of weight w (<= 9) that contain a given
 * column r: x = {r} u A u B, max(A) < min(B), |A| = floor((w-1)/2), |B| = ceil((w-1)/2), H(r)+H(A)+H(B) = 0,
 * L(x) != 0.  H parts must fit in 64 bits (bb90: 45 checks; BB72: 36).
 * input (stdin): N, then N lines "hHex lHex"; argv: w r1 [r2 ...] (representatives)
 * output: one line per logical: "w: c1 c2 ..." (sorted), and a final "done" line with counts.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
typedef uint64_t u64;
static int N; static u64 H[1024], Lv[1024];
typedef struct { u64 s; uint8_t c[4]; } ent;
static int cmp(const void *a, const void *b){ u64 x = ((const ent*)a)->s, y = ((const ent*)b)->s; return x < y ? -1 : x > y; }
static ent *tab; static long ntab;
static void build(int b){
  long cap = 1; for (int i = 0; i < b; i++) cap = cap * (N - i) / (i + 1);
  tab = malloc(sizeof(ent) * (cap + 1)); ntab = 0;
  int idx[4];
  if (b == 0){ tab[0].s = 0; ntab = 1; return; }
  for (int i = 0; i < b; i++) idx[i] = i;
  while (1){
    u64 s = 0; for (int i = 0; i < b; i++){ s ^= H[idx[i]]; tab[ntab].c[i] = idx[i]; }
    tab[ntab++].s = s;
    int i = b - 1; while (i >= 0 && idx[i] == N - b + i) i--;
    if (i < 0) break;
    idx[i]++; for (int j = i + 1; j < b; j++) idx[j] = idx[j - 1] + 1;
  }
  qsort(tab, ntab, sizeof(ent), cmp);
}
int main(int argc, char **argv){
  if (scanf("%d", &N) != 1 || N > 255) return 1;
  for (int j = 0; j < N; j++) if (scanf("%llx %llx", (unsigned long long*)&H[j], (unsigned long long*)&Lv[j]) != 2) return 1;
  int w = atoi(argv[1]); int a = (w - 1) / 2, b = (w - 1) - a;
  build(b);
  long found = 0, stab = 0;
  for (int ri = 2; ri < argc; ri++){
    int r = atoi(argv[ri]);
    int idx[4]; int ok = 1;
    for (int i = 0; i < a; i++) idx[i] = i;
    if (a > N) ok = 0;
    while (ok){
      u64 s = H[r], l = Lv[r]; int bad = 0, mx = -1;
      for (int i = 0; i < a; i++){ s ^= H[idx[i]]; l ^= Lv[idx[i]]; if (idx[i] == r) bad = 1; mx = idx[i]; }
      if (!bad){
        long lo = 0, hi = ntab;            /* first entry with syndrome >= s */
        while (lo < hi){ long m = (lo + hi) / 2; if (tab[m].s < s) lo = m + 1; else hi = m; }
        for (long e = lo; e < ntab && tab[e].s == s; e++){
          if (b > 0 && tab[e].c[0] <= mx) continue;
          int hit = 0; u64 ll = l;
          for (int i = 0; i < b; i++){ if (tab[e].c[i] == r) hit = 1; ll ^= Lv[tab[e].c[i]]; }
          if (hit) continue;
          if (!ll){ stab++; continue; }
          int v[9]; int k = 0; v[k++] = r;
          for (int i = 0; i < a; i++) v[k++] = idx[i];
          for (int i = 0; i < b; i++) v[k++] = tab[e].c[i];
          for (int i = 1; i < k; i++){ int t = v[i], j = i - 1; while (j >= 0 && v[j] > t){ v[j + 1] = v[j]; j--; } v[j + 1] = t; }
          printf("%d:", w); for (int i = 0; i < k; i++) printf(" %d", v[i]); printf("\n");
          found++;
        }
      }
      if (a == 0) break;
      int i = a - 1; while (i >= 0 && idx[i] == N - a + i) i--;
      if (i < 0) break;
      idx[i]++; for (int j = i + 1; j < a; j++) idx[j] = idx[j - 1] + 1;
    }
  }
  printf("done w=%d found=%ld stabilizer_like=%ld table=%ld\n", w, found, stab, ntab);
  return 0;
}
