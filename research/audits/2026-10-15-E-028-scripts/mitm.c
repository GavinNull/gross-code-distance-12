/* Auditor MITM enumerator (different algorithm from the project's DFS).
   input (stdin): n w hbits
                  key[0..n-1] (uint64: low hbits = syndrome, higher bits = logical part)
                  r m A[0..m-1]   (case: fixed column r, allowed columns A sorted ascending, r not in A)
   output: every set {r} u S, S subset of A, |S| = w-1, syndrome(r)^syndrome(S) = 0 and logical part != 0,
           one line "SOL r s1 ... s_{w-1}" (each set exactly once: S sorted, split into first a and last b elements). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef struct { uint64_t k; uint8_t p[4]; } ent;
static int cmp(const void *x, const void *y) {
  uint64_t a = ((const ent *)x)->k, b = ((const ent *)y)->k; return a < b ? -1 : a > b;
}
static uint64_t HM;
static int n, w, m, A[512]; static uint64_t key[512];
static ent *gen(int sz, long *cnt) {
  long cap = 1; for (int i = 0; i < sz; i++) cap = cap * (m - i) / (i + 1);
  if (sz == 0) cap = 1;
  ent *e = malloc(sizeof(ent) * (cap + 1)); long c = 0; int idx[4];
  for (int i = 0; i < sz; i++) idx[i] = i;
  if (sz == 0) { e[0].k = 0; *cnt = 1; return e; }
  while (1) {
    uint64_t k = 0; for (int i = 0; i < sz; i++) { k ^= key[A[idx[i]]]; e[c].p[i] = (uint8_t)idx[i]; }
    e[c].k = k; c++;
    int i = sz - 1; while (i >= 0 && idx[i] == m - sz + i) i--;
    if (i < 0) break;
    idx[i]++; for (int j = i + 1; j < sz; j++) idx[j] = idx[j - 1] + 1;
  }
  *cnt = c; return e;
}
int main(void) {
  int hb; if (scanf("%d %d %d", &n, &w, &hb) != 3) return 1;
  HM = (hb == 64) ? ~0ULL : ((1ULL << hb) - 1);
  for (int i = 0; i < n; i++) scanf("%llu", (unsigned long long *)&key[i]);
  int r; scanf("%d %d", &r, &m); for (int i = 0; i < m; i++) scanf("%d", &A[i]);
  if (m > 255) return 2;
  int a = (w - 1) / 2, b = w - 1 - a;
  long nx, ny; ent *X = gen(a, &nx); ent *Y = gen(b, &ny);
  for (long i = 0; i < ny; i++) Y[i].k = Y[i].k;   /* full key kept; sort by H part */
  /* sort Y by H part: store H in high-order comparison by masking */
  for (long i = 0; i < ny; i++) { uint64_t L = Y[i].k & ~HM, H = Y[i].k & HM; Y[i].k = (H << (64 - hb)) | (L >> hb); }
  qsort(Y, ny, sizeof(ent), cmp);
  long sols = 0, probes = 0;
  for (long i = 0; i < nx; i++) {
    uint64_t t = (X[i].k ^ key[r]); uint64_t tH = t & HM, tL = (t & ~HM) >> hb;
    int amax = a ? X[i].p[a - 1] : -1;
    uint64_t lo = tH << (64 - hb), hi = lo | ((hb == 64) ? 0 : ((1ULL << (64 - hb)) - 1));
    long L0 = 0, R0 = ny; while (L0 < R0) { long md = (L0 + R0) / 2; if (Y[md].k < lo) L0 = md + 1; else R0 = md; }
    for (long j = L0; j < ny && Y[j].k <= hi; j++) {
      probes++;
      if (b && Y[j].p[0] <= amax) continue;
      uint64_t yL = Y[j].k & ((hb == 64) ? 0 : ((1ULL << (64 - hb)) - 1));
      if ((yL ^ tL) == 0) continue;            /* logical part zero */
      sols++;
      printf("SOL %d", r);
      for (int q = 0; q < a; q++) printf(" %d", A[X[i].p[q]]);
      for (int q = 0; q < b; q++) printf(" %d", A[Y[j].p[q]]);
      printf("\n");
    }
  }
  fprintf(stderr, "DONE w=%d r=%d m=%d nx=%ld ny=%ld probes=%ld sols=%ld\n", w, r, m, nx, ny, probes, sols);
  return 0;
}
