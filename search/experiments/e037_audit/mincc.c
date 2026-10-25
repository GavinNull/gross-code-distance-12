/* E-037 audit: independent exhaustive search for undetectable logicals of weight <= W on a DEM.  auditor.

   No minimality constraints from E-037, no cardinality/blocking families, no proof logging.  The only pruning rule is
   the classical one, proved in the audit report:
     (P) a minimum-weight undetectable logical x contains no nonempty proper detector-silent subset
         (if y is one: L y != 0 makes y a lighter solution, L y == 0 makes x \ y a lighter solution).
   Search: start column s (all columns with "columns > s only" = nosym mode; or orbit representatives with "no column
   of an earlier orbit" = sym mode, justified by the translation group checked in Python), then repeatedly pick an
   odd ("unsatisfied") detector d and branch over the allowed columns touching d, forbidding earlier branches
   (each set reached on exactly one path).  A node whose set is detector-silent is a leaf: a solution if some
   observable is odd, otherwise pruned by (P).  Every x of minimum weight <= W is reached: along its path every proper
   prefix is non-silent by (P), so an odd detector exists and x \ S contains a column touching it.
   Consequently: no solution printed with W = d-1  =>  no undetectable logical of weight <= d-1;
   with W = d and none of weight < d, the printed solutions are exactly all weight-d undetectable logicals
   (each once in nosym mode; up to the group in sym mode).

   input (stdin): n ndet W mode     then n lines "k d1..dk obsmask"
                  mode 0 = nosym; mode 1 = sym, then: norb, and per orbit "rep size members..."
   output: "SOL w c1 c2 ..." per solution, final "DONE nodes=.. nsol=.. minw=.."
*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int n, ndet, W, mode;
static int *cdeg, **cdet;          /* column -> detectors */
static uint32_t *cobs;
static int *ddeg, **dcol;           /* detector -> columns */
static int *par;                    /* parity per detector */
static int *upos, *ulist, ucnt;     /* odd detectors */
static int *forb, *inS, *blocked;
static int S[64], sw;
static uint32_t obs;
static long long nodes, nsol;
static int maxdeg, minw = 1 << 30;

static void flip(int d) {
    if (par[d]) { int p = upos[d]; int last = ulist[--ucnt]; ulist[p] = last; upos[last] = p; upos[d] = -1; par[d] = 0; }
    else { upos[d] = ucnt; ulist[ucnt++] = d; par[d] = 1; }
}
static void addc(int c) { for (int i = 0; i < cdeg[c]; i++) flip(cdet[c][i]); obs ^= cobs[c]; inS[c] = 1; S[sw++] = c; }
static void remc(int c) { for (int i = 0; i < cdeg[c]; i++) flip(cdet[c][i]); obs ^= cobs[c]; inS[c] = 0; sw--; }
static inline int avail(int c) { return !forb[c] && !inS[c] && !blocked[c]; }

static void dfs(void) {
    nodes++;
    if (ucnt == 0) {
        if (obs) {
            nsol++; if (sw < minw) minw = sw;
            printf("SOL %d", sw); for (int i = 0; i < sw; i++) printf(" %d", S[i]); printf("\n");
        }
        return;
    }
    int r = W - sw;
    if (r <= 0) return;
    if (ucnt > r * maxdeg) return;
    /* pick odd detector with fewest available columns */
    int best = -1, bc = 1 << 30;
    for (int i = 0; i < ucnt; i++) {
        int d = ulist[i], cnt = 0;
        for (int j = 0; j < ddeg[d]; j++) if (avail(dcol[d][j])) cnt++;
        if (cnt < bc) { bc = cnt; best = d; if (cnt == 0) return; }
    }
    int cand[4096], nc = 0;
    for (int j = 0; j < ddeg[best]; j++) if (avail(dcol[best][j])) cand[nc++] = dcol[best][j];
    for (int i = 0; i < nc; i++) {
        int c = cand[i];
        addc(c); dfs(); remc(c);
        forb[c]++;
    }
    for (int i = 0; i < nc; i++) forb[cand[i]]--;
}

int main(void) {
    if (scanf("%d %d %d %d", &n, &ndet, &W, &mode) != 4) return 3;
    cdeg = calloc(n, sizeof(int)); cdet = calloc(n, sizeof(int *)); cobs = calloc(n, sizeof(uint32_t));
    ddeg = calloc(ndet, sizeof(int));
    for (int c = 0; c < n; c++) {
        if (scanf("%d", &cdeg[c]) != 1) return 3;
        cdet[c] = malloc(sizeof(int) * (cdeg[c] + 1));
        for (int i = 0; i < cdeg[c]; i++) { if (scanf("%d", &cdet[c][i]) != 1) return 3; ddeg[cdet[c][i]]++; }
        unsigned m; if (scanf("%u", &m) != 1) return 3; cobs[c] = m;
        if (cdeg[c] == 0) { fprintf(stderr, "column %d has no detectors\n", c); return 4; }
        if (cdeg[c] > maxdeg) maxdeg = cdeg[c];
    }
    dcol = calloc(ndet, sizeof(int *));
    int *fill = calloc(ndet, sizeof(int));
    for (int d = 0; d < ndet; d++) dcol[d] = malloc(sizeof(int) * (ddeg[d] + 1));
    for (int c = 0; c < n; c++) for (int i = 0; i < cdeg[c]; i++) { int d = cdet[c][i]; dcol[d][fill[d]++] = c; }
    par = calloc(ndet, sizeof(int)); upos = malloc(sizeof(int) * ndet); ulist = malloc(sizeof(int) * ndet);
    for (int d = 0; d < ndet; d++) upos[d] = -1;
    forb = calloc(n, sizeof(int)); inS = calloc(n, sizeof(int)); blocked = calloc(n, sizeof(int));
    if (mode == 0) {
        for (int s = 0; s < n; s++) {
            for (int c = 0; c <= s; c++) blocked[c] = 1;   /* s itself is added explicitly */
            addc(s); dfs(); remc(s);
        }
    } else {
        int norb; if (scanf("%d", &norb) != 1) return 3;
        for (int o = 0; o < norb; o++) {
            int rep, sz; if (scanf("%d %d", &rep, &sz) != 2) return 3;
            int *mem = malloc(sizeof(int) * sz);
            for (int i = 0; i < sz; i++) if (scanf("%d", &mem[i]) != 1) return 3;
            addc(rep); dfs(); remc(rep);
            for (int i = 0; i < sz; i++) blocked[mem[i]] = 1;   /* later orbits: no column of this orbit */
            free(mem);
            fprintf(stderr, "orbit %d/%d nodes=%lld nsol=%lld\n", o + 1, norb, nodes, nsol);
        }
    }
    printf("DONE nodes=%lld nsol=%lld minw=%d\n", nodes, nsol, nsol ? minw : -1);
    return 0;
}
