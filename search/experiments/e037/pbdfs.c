/* E-037: proof-logging DFS for "no undetectable logical of weight <= W" directly on a DEM.
 * Derived from e034/pbdfs.c (E-031 algorithm, VeriPB 3.0 syntax).  The proof rules are the same as in E-031/E-034
 * (see the header of e034/pbdfs.c); what changed is only what is needed for DEM-sized instances (10^4 columns):
 *   - sizes are dynamic (no MAXC / MAXR);
 *   - per-node work is local: available-column counts of rows are computed on demand for the open rows only, and
 *     the counting bounds look only at columns of open rows;
 *   - the tight-bound exclusion (every available x column outside an allowed set is excluded in the subtree) is
 *     represented by a whitelist (allowed set) instead of marking each excluded column; it excludes exactly the
 *     same columns as E-031 (columns that touch no open row are always excluded there: cnt = 0, outside packing);
 *   - the symmetry witnesses are generated from the group permutations in the instance file (one line per group
 *     element instead of one string per orbit member).
 * The search is NOT trusted: only VeriPB's verdict on the proof is.
 *
 * usage: pbdfs INST [-p PROOF] [-n NODELIMIT] [-e] [-F N] [-T]
 * exit: 0 UNSAT (proof complete), 2 SAT (solution printed), 3 node limit, 1 error
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

typedef uint64_t u64;

static int NX, NQ, NC, R, NL, NR, W, NCONS, NW;
static int *isx, *ncr, **crow;
static int *nrc, **rcol;
static long long *ge_id, *le_id, wid, sid;
static u64 *cmask;                        /* NC x NW */
#define CM(j) (cmask + (size_t)(j) * NW)
static int NBAS, *bas, NEXP, *exm, *excn, **exc, *exdn, **exd; static char *isbas;
static int NB; static long long bid0; static int *bsz, **bcol;
static int KC, KL, NG; static int **gx, **gq, **gr;
static int NCASE; static int *case_col, *case_nred; static int **red_col, **red_g;

static char *chosen, *forb, *gfalse;
static long long *unit_id;
static int *wl; static int nwl = 0;      /* whitelist counters: x column j available only if wl[j] == nwl */
static long long xstack[256]; static int nxs = 0;
static u64 *syn;
static int S[128], nS, wt;
static int *Fl, nF;
static long long nqnodes = 0, nleafq = 0, nwrap = 0;
static int NK; static long long kid0; static int *kb, *ks, **kc, *kcnt; static int **colK, *ncolK;
static int *kexc; static long long *Kact; static int nKact = 0;
static long long nodes = 0, limit = -1, nprune1 = 0, nprune2 = 0, nleaf0 = 0, nleafw = 0, nblk = 0, nqbr = 0;
static FILE *pf = NULL;
static long long nextid;
static long long nrowcl = 0;
static char (*names)[16];
static int *stampc, stampv = 1, *cnt;    /* per-column scratch with stamps */

static FILE *recf = NULL; static long long ntriv = 0; static int qbranch_ok = 0;
static long long *bh; static size_t bhcap = 0;
static u64 shash(const int *t, int n){ u64 h = 1469598103934665603ULL; for (int i=0;i<n;i++){ h ^= (u64)(t[i]+1); h *= 1099511628211ULL; h ^= h >> 31; } return h; }
static long long blk_lookup(void);
static void die(const char *m){ fprintf(stderr, "error: %s\n", m); exit(1); }
static void *xm(size_t n){ void *p = calloc(1, n ? n : 1); if (!p) die("oom"); return p; }

/* ---------------- proof output */
#define EOL ";\n"
static char *obuf; static size_t olen = 0, ocap = 0;
static void oflush(void){ if (pf && olen){ fwrite(obuf, 1, olen, pf); } olen = 0; }
static void ostr(const char *s){ if (!pf) return; size_t l = strlen(s); if (olen + l + 1 > ocap){ oflush(); if (l + 1 > ocap){ ocap = 2*(l+1); obuf = realloc(obuf, ocap);} } memcpy(obuf+olen, s, l); olen += l; if (olen > (1<<22)) oflush(); }
static void oint(long long v){ char b[32]; snprintf(b, sizeof b, "%lld", v); ostr(b); }

/* ---------------- row clause cache */
typedef struct { int row, nt; int t[24]; long long id; } RKey;
static RKey *ht; static size_t htcap = 0, htn = 0;
static u64 rhash(int row, int nt, const int *t){ u64 h = 1469598103934665603ULL ^ (u64)row * 0x9e3779b97f4a7c15ULL; for (int i=0;i<nt;i++){ h ^= (u64)(t[i]+1); h *= 1099511628211ULL; h ^= h >> 29; } return h; }
static void htgrow(void){
  size_t oc = htcap; RKey *o = ht; htcap = oc ? oc*2 : (1<<16); ht = calloc(htcap, sizeof(RKey)); if (!ht) die("oom");
  for (size_t i=0;i<oc;i++) if (o[i].id){ u64 h = rhash(o[i].row, o[i].nt, o[i].t) & (htcap-1); while (ht[h].id) h = (h+1)&(htcap-1); ht[h] = o[i]; }
  free(o);
}
static int cmpi(const void *a, const void *b){ return *(const int*)a - *(const int*)b; }
static int inrow(int j, int i){ return (CM(j)[i>>6] >> (i&63)) & 1; }

static long long row_clause(int i){
  int t[128], nt = 0;
  for (int k=0;k<nS;k++) if (inrow(S[k], i)) t[nt++] = S[k];
  if (nt > 24) die("T too large");
  if (!(nt & 1)) die("row clause for even row");
  qsort(t, nt, sizeof(int), cmpi);
  if (!pf) return 1;
  if ((htn+1)*2 > htcap) htgrow();
  u64 h = rhash(i, nt, t) & (htcap-1);
  while (ht[h].id){ if (ht[h].row == i && ht[h].nt == nt && !memcmp(ht[h].t, t, nt*sizeof(int))) return ht[h].id; h = (h+1)&(htcap-1); }
  ostr("pol "); oint(le_id[i]); ostr(" "); oint(ge_id[i]);
  for (int a=0;a<nt;a++){ ostr(" ~"); ostr(names[t[a]]); ostr(" 2 * +"); }
  ostr(" 2 d 2 * +");
  for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (gfalse[j]){ ostr(" "); oint(unit_id[j]); ostr(" +"); } }
  ostr(EOL);
  long long id = nextid++;
  ht[h].row = i; ht[h].nt = nt; memcpy(ht[h].t, t, nt*sizeof(int)); ht[h].id = id; htn++; nrowcl++;
  return id;
}
static void cache_flush(void){
  if (pf && htn){ int c = 0; for (size_t h=0;h<htcap;h++) if (ht[h].id){ if (c % 1000 == 0) ostr(c ? ";\ndel id" : "del id"); ostr(" "); oint(ht[h].id); c++; } ostr(EOL); }
  if (htcap) memset(ht, 0, htcap*sizeof(RKey)); htn = 0;
}
static long long cachemax = 0, ntrim = 0;
static long long *pin; static int npin = 0, pincap = 0;
static void pin_push(long long id){ if (npin == pincap){ pincap = pincap ? 2*pincap : 1024; pin = realloc(pin, pincap*sizeof(long long)); if (!pin) die("oom"); } pin[npin++] = id; }
static int is_pinned(long long id){ for (int k=0;k<npin;k++) if (pin[k] == id) return 1; return 0; }
static void cache_trim(void){
  if (!pf || !cachemax || (long long)htn <= cachemax) return;
  RKey *keep = malloc((npin+1)*sizeof(RKey)); int nk = 0, c = 0;
  for (size_t h=0;h<htcap;h++) if (ht[h].id){
    if (is_pinned(ht[h].id)){ if (nk > npin) die("pin overflow"); keep[nk++] = ht[h]; }
    else { if (c % 1000 == 0) ostr(c ? ";\ndel id" : "del id"); ostr(" "); oint(ht[h].id); c++; } }
  if (c) ostr(EOL);
  memset(ht, 0, htcap*sizeof(RKey)); htn = 0;
  for (int k=0;k<nk;k++){ u64 h = rhash(keep[k].row, keep[k].nt, keep[k].t) & (htcap-1); while (ht[h].id) h = (h+1)&(htcap-1); ht[h] = keep[k]; htn++; }
  free(keep); ntrim++;
}

static void emit_clause_rup(const long long *hints, int nh){
  ostr("rup");
  for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
  for (int k=0;k<nF;k++){ ostr(" 1 "); ostr(names[Fl[k]]); }
  ostr(" >= 1"); if (nh >= 0) ostr(" :");
  if (nh >= 0){ ostr(" ~"); for (int k=0;k<nKact;k++){ ostr(" "); oint(Kact[k]); } for (int k=0;k<nxs;k++){ ostr(" "); oint(xstack[k]); } for (int k=0;k<nh;k++){ ostr(" "); oint(hints[k]); } }
  ostr(EOL);
}

/* ---------------- state */
/* E-037 cardinality constraints  sum_{j in T} x_j <= bound  for small trivial sets T (bound = floor(|T|/2)); a
   constraint with `bound` chosen members excludes its other members (kexc[j] > 0).  Kact = such tight constraints. */
static int kadd[128];
static int kchoose(int j){
  int added = 0;
  if (j >= NX) return 0;
  for (int a=0;a<ncolK[j];a++){ int k = colK[j][a]; kcnt[k]++;
    if (kcnt[k] > kb[k]) die("cardinality constraint exceeded");
    if (kcnt[k] == kb[k]){ for (int b=0;b<ks[k];b++){ int m = kc[k][b]; if (!chosen[m]) kexc[m]++; } Kact[nKact++] = kid0 + k; added++; } }
  return added;
}
static void kunchoose(int j){
  if (j >= NX) return;
  for (int a=ncolK[j]-1;a>=0;a--){ int k = colK[j][a];
    if (kcnt[k] == kb[k]){ for (int b=0;b<ks[k];b++){ int m = kc[k][b]; if (!chosen[m]) kexc[m]--; } nKact--; if (Kact[nKact] != kid0 + k) die("Kact order"); }
    kcnt[k]--; }
}
static void choose(int j){ chosen[j] = 1; S[nS++] = j; if (isx[j]) wt++; u64 *c = CM(j); for (int w=0;w<NW;w++) syn[w] ^= c[w]; kadd[nS-1] = kchoose(j); }
static void unchoose(int j){ kunchoose(j); chosen[j] = 0; nS--; if (isx[j]) wt--; u64 *c = CM(j); for (int w=0;w<NW;w++) syn[w] ^= c[w]; }
static int qcol(int i){ return NX + (i - R); }
static int isavail(int j){ return !chosen[j] && !forb[j] && !gfalse[j] && (j >= NX || (wl[j] == nwl && !kexc[j])); }
static int qfree(int i){ return isavail(qcol(i)); }
static int avail_row(int i){ int c = 0; for (int k=0;k<nrc[i];k++) if (isavail(rcol[i][k])) c++; return c; }

static int open_rows(int *O){
  int no = 0;
  for (int w=0;w<NW;w++){ u64 s = syn[w]; while (s){ int b = __builtin_ctzll(s); s &= s-1; int i = (w<<6)+b; if (i < R || !qfree(i)) O[no++] = i; } }
  return no;
}

/* a leaf certificate (raw constraint) must propagate ~c under the parent's assignment; if choosing c made new
   cardinality constraints tight, the exclusions they cause are not visible there, so the leaf is turned into its
   clause C(S,F) by RUP with the active cardinality constraints as hints */
static int owned;
static long long wrapK(long long id, int own){
  if (!pf || nS == 0 || kadd[nS-1] == 0){ owned = own; return id; }
  long long h[1] = { id };
  emit_clause_rup(h, 1); long long nid = nextid++; nwrap++;
  if (own){ ostr("del id "); oint(id); ostr(EOL); }
  owned = 1; return nid;
}
static long long blk_lookup(void){
  if (!NB) return -1;
  int t[128], n = 0; for (int k=0;k<nS;k++) t[n++] = S[k];
  qsort(t, n, sizeof(int), cmpi);
  /* any blocked subset of S (S has at most W columns): exact set first, then proper subsets */
  int u[128];
  for (long long mask = (1LL<<n)-1; mask > 0; mask--){
    int m = 0; for (int i=0;i<n;i++) if ((mask>>i)&1) u[m++] = t[i];
    if (m < 3) continue;
    u64 h = shash(u, m) & (bhcap-1);
    while (bh[h] >= 0){ int b = (int)bh[h]; if (bsz[b] == m && !memcmp(bcol[b], u, m*sizeof(int))) return b; h = (h+1)&(bhcap-1); }
    if (mask == (1LL<<n)-1) mask = (1LL<<n)-1;   /* exact first is mask = all; continue with subsets */
  }
  return -1;
}
static long long node(void);
static int tight = 1; static long long ntight = 0;
static int enumerate = 0; static long long nsol = 0;
static long long wcur;
typedef struct { long long rid, pid; } LC;
static LC *lcache; static int nlc;

/* branch on row (row < 0: on the basis q's).  allow != NULL: push this whitelist of x columns (tight bound) with
   certificate xcert for the subtree. */
static long long branch_x(int row, long long xcert, const int *allow, int nallow){
  if (xcert){ for (int a=0;a<nallow;a++) wl[allow[a]]++; nwl++; xstack[nxs++] = xcert; if (nxs >= 256) die("xstack"); }
  int nc = 0; int *cand;
  if (row >= 0){ cand = malloc(sizeof(int)*(nrc[row]+1)); for (int k=0;k<nrc[row];k++){ int j = rcol[row][k]; if (isavail(j)) cand[nc++] = j; } }
  else { cand = malloc(sizeof(int)*(NL+1)); for (int i=R;i<NR;i++){ int q = qcol(i); if (isbas[i - R] && isavail(q)) cand[nc++] = q; } }
  long long base = row >= 0 ? row_clause(row) : sid;
  int pin0 = npin; if (row >= 0) pin_push(base);
  long long *ch = malloc(sizeof(long long) * (nc + 2)); char *own = malloc(nc + 1);
  LC *mylc = malloc(sizeof(LC) * (nc + 1)); int mynlc = 0;
  int f0 = nF;
  for (int a=0;a<nc;a++){
    int j = cand[a];
    choose(j);
    lcache = mylc; nlc = mynlc;
    long long id = node();
    if (lcache == mylc) mynlc = nlc;
    unchoose(j);
    if (id < 0){ free(ch); free(own); free(mylc); free(cand); npin = pin0;
      for (int b=f0;b<nF;b++) forb[Fl[b]] = 0; nF = f0;
      if (xcert){ nxs--; nwl--; for (int b=0;b<nallow;b++) wl[allow[b]]--; }
      return id; }
    ch[a] = id; own[a] = owned;
    if (!owned) pin_push(id);
    forb[j] = 1; Fl[nF++] = j;
  }
  for (int a=f0;a<nF;a++) forb[Fl[a]] = 0;
  nF = f0;
  if (xcert){ nxs--; nwl--; for (int a=0;a<nallow;a++) wl[allow[a]]--; }
  int nh = 0; long long *h = malloc(sizeof(long long) * (nc + 3));
  if (xcert) h[nh++] = xcert;
  for (int a=0;a<nc;a++){ int dup = 0; for (int b=0;b<nh;b++) if (h[b] == ch[a]) dup = 1; if (!dup) h[nh++] = ch[a]; }
  h[nh++] = base;
  emit_clause_rup(h, nh);
  long long id = nextid++;
  if (pf){ int any = 0;
    for (int a=0;a<nc;a++) if (own[a]){ int dup = 0; for (int b=0;b<a;b++) if (own[b] && ch[b]==ch[a]) dup = 1;
      if (!dup){ if (!any){ ostr("del id"); any = 1; } ostr(" "); oint(ch[a]); } }
    if (xcert){ if (!any){ ostr("del id"); any = 1; } ostr(" "); oint(xcert); }
    if (any) ostr(EOL); }
  free(ch); free(own); free(mylc); free(h); free(cand);
  npin = pin0;
  lcache = NULL; nlc = 0;
  owned = 1;
  return id;
}

static long long node(void){
  nodes++;
  cache_trim();
  if (limit > 0 && nodes > limit) return -3;
  int O[NR + 1]; int no = open_rows(O);
  int rem = W - wt;
  if (no == 0){
    int sol = 0;
    for (int k=0;k<nS;k++) if (!isx[S[k]]) sol = 1;
    for (int i=R;i<NR && !sol;i++) if (((syn[i>>6]>>(i&63))&1) && qfree(i)) sol = 1;
    if (sol){
      printf("SAT columns:"); for (int k=0;k<nS;k++) if (isx[S[k]]) printf(" %d", S[k]); printf("\n");
      if (enumerate){ nsol++; owned = 0; return 1; }
      return -2;
    }
    /* E-037: S is detector-silent and logically trivial.  A minimum-weight solution contains no such proper
       subset, so the formula carries the clause ~(AND S) for every trivial set the search meets (justified outside
       the proof; recorded in a first count-only pass with -R, closed under the group by dem_inst.py). */
    if (rem > 0){ long long b = blk_lookup();
      if (b >= 0){ nblk++; owned = 0; return bid0 + b; }
      if (recf){ ntriv++; fprintf(recf, "%d", nS); for (int k=0;k<nS;k++) fprintf(recf, " %d", S[k]); fprintf(recf, "\n"); owned = 0; return 1; }
      if (!qbranch_ok) die("trivial set not in the blocked list (run the -R pass first)"); }
    /* rem = 0: the weight constraint sets every other column to 0, every basis logical row then has an even fixed
       x-sum, its equality propagates q = 0, and sum_basis q >= 1 fails (one RUP; -Q keeps the E-031 q-branch) */
    if (!qbranch_ok){
      nleafq++;
      ostr("rup"); for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
      for (int k=0;k<nF;k++) if (!isx[Fl[k]]){ ostr(" 1 "); ostr(names[Fl[k]]); }
      ostr(" >= 1 : ~ "); oint(wid);
      for (int a=0;a<NBAS;a++){ int i = R + bas[a]; ostr(" "); oint(ge_id[i]); ostr(" "); oint(le_id[i]); }
      ostr(" "); oint(sid); ostr(EOL);
      owned = 1; return nextid++;
    }
    nqbr++;
    { long long n0 = nodes; long long r = branch_x(-1, 0, NULL, 0); nqnodes += nodes - n0; return r; }
  }
  int av[NR + 1];
  int best = -1, bc = 1<<30;
  for (int a=0;a<no;a++){ av[a] = avail_row(O[a]); if (av[a] < bc){ bc = av[a]; best = O[a]; } }
  if (bc == 0){ nleaf0++; return wrapK(row_clause(best), 0); }
  if (rem <= 0){
    nleafw++;
    int last = S[nS-1], pick = -1;
    for (int a=0;a<no;a++) if (!inrow(last, O[a]) && (pick < 0 || O[a] < pick)) pick = O[a];
    if (pick < 0) pick = best;
    ostr("rup"); for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
    for (int k=0;k<nF;k++) if (!isx[Fl[k]]){ ostr(" 1 "); ostr(names[Fl[k]]); }
    ostr(" >= 1 : ~ "); oint(wid); ostr(" "); oint(ge_id[pick]); ostr(" "); oint(le_id[pick]); ostr(EOL);
    owned = 1; return nextid++;
  }
  /* counting bounds over the available x columns of open rows */
  int lam = 0;
  int ntc = 0; int *tc = malloc(sizeof(int) * 1);   /* touching available x columns */
  {
    stampv++; if (stampv == 0x7fffffff){ memset(stampc, 0, sizeof(int)*NC); stampv = 1; }
    int cap = 64; tc = realloc(tc, sizeof(int)*cap);
    for (int a=0;a<no;a++){ int i = O[a];
      for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (!isx[j] || !isavail(j)) continue;
        if (stampc[j] != stampv){ stampc[j] = stampv; cnt[j] = 0; if (ntc == cap){ cap *= 2; tc = realloc(tc, sizeof(int)*cap); } tc[ntc++] = j; }
        cnt[j]++; } }
    for (int a=0;a<ntc;a++) if (cnt[tc[a]] > lam) lam = cnt[tc[a]];
  }
  /* order open rows by available count (stable insertion sort, as E-031) */
  int ord[NR + 1]; int oav[NR + 1];
  for (int a=0;a<no;a++){ ord[a] = O[a]; oav[a] = av[a]; }
  for (int a=1;a<no;a++){ int v = ord[a], va = oav[a], b = a-1; while (b>=0 && oav[b] > va){ ord[b+1] = ord[b]; oav[b+1] = oav[b]; b--; } ord[b+1] = v; oav[b+1] = va; }
  int use[NR + 1], nu = 0, lamu = 0;
  {
    int sv = ++stampv;
    for (int a=0;a<no && nu <= rem;a++){ int i = ord[a], ok = 1;
      for (int k=0;k<nrc[i] && ok;k++){ int j = rcol[i][k]; if (isx[j] && isavail(j) && stampc[j] == -sv) ok = 0; }
      if (ok){ use[nu++] = i; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isx[j] && isavail(j)) stampc[j] = -sv; } } }
    if (nu > rem){ nprune2++; lamu = 1; } else nu = 0;
    /* restore the stamps of touching columns (cnt was keyed on stampv) */
    stampv++;
    for (int a=0;a<ntc;a++) stampc[tc[a]] = stampv;   /* cnt[] stays valid for tc */
  }
  if (!nu && no > lam * rem){ nprune1++; for (int a=0;a<no;a++) use[nu++] = O[a]; lamu = lam; }
  if (nu){
    long long *rid = malloc(sizeof(long long)*(nu+1)); for (int a=0;a<nu;a++) rid[a] = row_clause(use[a]);
    ostr("pol "); oint(rid[0]); for (int a=1;a<nu;a++){ ostr(" "); oint(rid[a]); ostr(" +"); }
    ostr(" "); oint(wcur); if (lamu > 1){ ostr(" "); oint(lamu); ostr(" *"); } ostr(" +"); ostr(EOL);
    free(rid); free(tc);
    return wrapK(nextid++, 1);
  }
  if (tight){
    /* (a) packing of exactly rem rows: allowed = available x columns in the union of the packed rows;
       (b) cover with slack sl = lam*rem - |O| >= 0: allowed = touching columns with lam - cnt <= sl.
       Everything else (including every column touching no open row) is excluded in the subtree. */
    int pk[NR + 1], np = 0;
    int *Aa = malloc(sizeof(int)*(ntc+1)), na = 0, *Ab = malloc(sizeof(int)*(ntc+1)), nb = 0;
    {
      int sv = ++stampv;
      for (int a=0;a<no && np < rem;a++){ int i = ord[a], ok = 1;
        for (int k=0;k<nrc[i] && ok;k++){ int j = rcol[i][k]; if (isx[j] && isavail(j) && stampc[j] == -sv) ok = 0; }
        if (ok){ pk[np++] = i; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isx[j] && isavail(j) && stampc[j] != -sv){ stampc[j] = -sv; Aa[na++] = j; } } } }
      stampv++;
      for (int a=0;a<ntc;a++) stampc[tc[a]] = stampv;
    }
    int sl = lam * rem - no;
    int okb = sl >= 0 && lam > sl;           /* otherwise nothing is excluded by (b) */
    if (okb) for (int a=0;a<ntc;a++){ int j = tc[a]; if (lam - cnt[j] <= sl) Ab[nb++] = j; }
    /* E-031 chooses (a) if it excludes at least as many columns as (b); both exclude all non-touching columns, so
       compare the allowed sets: |excluded_a| >= |excluded_b|  <=>  na <= nb.  (b) is usable only if okb. */
    int mode = 0;
    if (np == rem && (!okb || na <= nb)) mode = 1; else if (okb) mode = 2;
    if (mode == 1 && na == ntc && 0) mode = 0;
    if (mode){
      int *A = mode == 1 ? Aa : Ab; int nA = mode == 1 ? na : nb;
      /* membership stamp for A */
      int sv = ++stampv; for (int a=0;a<nA;a++) stampc[A[a]] = -sv;
      int br = -1, bs = 1<<30;
      for (int a=0;a<no;a++){ int i = O[a], s2 = 0; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isavail(j) && (!isx[j] || stampc[j] == -sv)) s2++; }
        if (s2 < bs){ bs = s2; br = i; } }
      stampv++; for (int a=0;a<ntc;a++) stampc[tc[a]] = stampv;
      if (bs < bc){
        ntight++;
        long long xc;
        if (mode == 1){ long long *rid = malloc(sizeof(long long)*(np+1)); for (int a=0;a<np;a++) rid[a] = row_clause(pk[a]);
          ostr("pol "); oint(rid[0]); for (int a=1;a<np;a++){ ostr(" "); oint(rid[a]); ostr(" +"); } ostr(" "); oint(wcur); ostr(" +"); ostr(EOL); free(rid); }
        else { long long *rid = malloc(sizeof(long long)*(no+1)); for (int a=0;a<no;a++) rid[a] = row_clause(O[a]);
          ostr("pol "); oint(rid[0]); for (int a=1;a<no;a++){ ostr(" "); oint(rid[a]); ostr(" +"); } ostr(" "); oint(wcur);
          if (lam > 1){ ostr(" "); oint(lam); ostr(" *"); } ostr(" +"); ostr(EOL); free(rid); }
        xc = nextid++;
        free(tc);
        long long r = branch_x(br, xc, A, nA);
        free(Aa); free(Ab);
        return r;
      }
    }
    free(Aa); free(Ab);
  }
  free(tc);
  return branch_x(best, 0, NULL, 0);
}

/* ---------------- input */
static long long rdl(FILE *f){ long long v; if (fscanf(f, "%lld", &v) != 1) die("parse"); return v; }
static int rd(FILE *f){ return (int)rdl(f); }

static void emit_witness(int g){
  int *P = gx[g], *lp = gq[g], *rp = gr[g]; char b[96];
  for (int j=0;j<NX;j++) if (P[j] != j){ snprintf(b, sizeof b, " x%d -> x%d", j+1, P[j]+1); ostr(b); }
  for (int i=0;i<NL;i++) if (lp[i] != i){ snprintf(b, sizeof b, " q%d -> q%d", i+1, lp[i]+1); ostr(b); }
  for (int i=0;i<R;i++) if (rp[i] != i) for (int k=0;k<KC;k++){ snprintf(b, sizeof b, " a%d_%d -> a%d_%d", i+1, k, rp[i]+1, k); ostr(b); }
  for (int i=0;i<NL;i++) if (lp[i] != i) for (int k=0;k<KL;k++){ snprintf(b, sizeof b, " b%d_%d -> b%d_%d", i+1, k, lp[i]+1, k); ostr(b); }
}

int main(int argc, char **argv){
  if (argc < 2) die("usage: pbdfs INST [-p PROOF] [-n LIMIT] [-e] [-F N] [-T]");
  const char *proof = NULL;
  for (int a=2;a<argc;a++){
    if (!strcmp(argv[a], "-p")) proof = argv[++a];
    else if (!strcmp(argv[a], "-n")) limit = atoll(argv[++a]);
    else if (!strcmp(argv[a], "-e")) enumerate = 1;
    else if (!strcmp(argv[a], "-F")) cachemax = atoll(argv[++a]);
    else if (!strcmp(argv[a], "-T")) tight = 0;
    else if (!strcmp(argv[a], "-R")){ recf = fopen(argv[++a], "w"); if (!recf) die("open -R"); }
    else if (!strcmp(argv[a], "-Q")) qbranch_ok = 1;    /* E-034 behaviour: branch on q at trivial sets */
    else die("unknown option");
  }
  FILE *f = fopen(argv[1], "r"); if (!f) die("open inst");
  NX = rd(f); NQ = rd(f); R = rd(f); W = rd(f); NCONS = rd(f);
  NL = NQ; NC = NX + NQ; NR = R + NL; NW = (NR + 63) / 64;
  isx = xm(sizeof(int)*NC); ncr = xm(sizeof(int)*NC); crow = xm(sizeof(int*)*NC); cmask = xm(sizeof(u64)*(size_t)NC*NW);
  nrc = xm(sizeof(int)*NR); rcol = xm(sizeof(int*)*NR); ge_id = xm(sizeof(long long)*NR); le_id = xm(sizeof(long long)*NR);
  isbas = xm(NL + 1);
  for (int j=0;j<NC;j++){ isx[j] = rd(f); ncr[j] = rd(f); crow[j] = xm(sizeof(int)*(ncr[j]+1));
    for (int k=0;k<ncr[j];k++){ int i = rd(f); if (i < 0 || i >= NR) die("row index"); crow[j][k] = i; CM(j)[i>>6] |= 1ULL << (i&63); nrc[i]++; } }
  for (int i=0;i<NR;i++){ rcol[i] = xm(sizeof(int)*(nrc[i]+1)); nrc[i] = 0; }
  for (int j=0;j<NC;j++) for (int k=0;k<ncr[j];k++){ int i = crow[j][k]; rcol[i][nrc[i]++] = j; }
  for (int i=0;i<NR;i++){ ge_id[i] = rdl(f); le_id[i] = rdl(f); }
  wid = rdl(f); sid = rdl(f);
  NBAS = rd(f); bas = xm(sizeof(int)*(NBAS+1)); for (int a=0;a<NBAS;a++){ bas[a] = rd(f); isbas[bas[a]] = 1; }
  NEXP = rd(f); exm = xm(sizeof(int)*(NEXP+1)); excn = xm(sizeof(int)*(NEXP+1)); exdn = xm(sizeof(int)*(NEXP+1));
  exc = xm(sizeof(int*)*(NEXP+1)); exd = xm(sizeof(int*)*(NEXP+1));
  for (int e=0;e<NEXP;e++){ exm[e] = rd(f); excn[e] = rd(f); exc[e] = xm(sizeof(int)*(excn[e]+1)); for (int a=0;a<excn[e];a++) exc[e][a] = rd(f);
    exdn[e] = rd(f); exd[e] = xm(sizeof(int)*(exdn[e]+1)); for (int a=0;a<exdn[e];a++) exd[e][a] = rd(f); }
  NB = rd(f); bid0 = rdl(f);
  bsz = xm(sizeof(int)*(NB+1)); bcol = xm(sizeof(int*)*(NB+1));
  for (int b=0;b<NB;b++){ bsz[b] = rd(f); bcol[b] = xm(sizeof(int)*(bsz[b]+1)); for (int a=0;a<bsz[b];a++) bcol[b][a] = rd(f);
    qsort(bcol[b], bsz[b], sizeof(int), cmpi); }
  bhcap = 16; while (bhcap < 4*(size_t)NB + 16) bhcap <<= 1; bh = xm(sizeof(long long)*bhcap); for (size_t h=0;h<bhcap;h++) bh[h] = -1;
  for (int b=0;b<NB;b++){ u64 h = shash(bcol[b], bsz[b]) & (bhcap-1); while (bh[h] >= 0) h = (h+1)&(bhcap-1); bh[h] = b; }
  NK = rd(f); kid0 = rdl(f);
  kb = xm(sizeof(int)*(NK+1)); ks = xm(sizeof(int)*(NK+1)); kc = xm(sizeof(int*)*(NK+1)); kcnt = xm(sizeof(int)*(NK+1));
  ncolK = xm(sizeof(int)*NC); colK = xm(sizeof(int*)*NC);
  for (int k=0;k<NK;k++){ kb[k] = rd(f); ks[k] = rd(f); kc[k] = xm(sizeof(int)*ks[k]); for (int a=0;a<ks[k];a++){ kc[k][a] = rd(f); ncolK[kc[k][a]]++; } }
  for (int j=0;j<NC;j++){ colK[j] = xm(sizeof(int)*(ncolK[j]+1)); ncolK[j] = 0; }
  for (int k=0;k<NK;k++) for (int a=0;a<ks[k];a++){ int j = kc[k][a]; colK[j][ncolK[j]++] = k; }
  Kact = xm(sizeof(long long)*(NK+1)); kexc = xm(sizeof(int)*NC);
  KC = rd(f); KL = rd(f); NG = rd(f);
  gx = xm(sizeof(int*)*NG); gq = xm(sizeof(int*)*NG); gr = xm(sizeof(int*)*NG);
  for (int g=0;g<NG;g++){ gx[g] = xm(sizeof(int)*NX); gq[g] = xm(sizeof(int)*(NL+1)); gr[g] = xm(sizeof(int)*R);
    for (int j=0;j<NX;j++) gx[g][j] = rd(f); for (int i=0;i<NL;i++) gq[g][i] = rd(f); for (int i=0;i<R;i++) gr[g][i] = rd(f); }
  NCASE = rd(f);
  case_col = xm(sizeof(int)*NCASE); case_nred = xm(sizeof(int)*NCASE); red_col = xm(sizeof(int*)*NCASE); red_g = xm(sizeof(int*)*NCASE);
  for (int c=0;c<NCASE;c++){
    case_col[c] = rd(f); case_nred[c] = rd(f);
    red_col[c] = xm(sizeof(int)*(case_nred[c]+1)); red_g[c] = xm(sizeof(int)*(case_nred[c]+1));
    for (int r=0;r<case_nred[c];r++){ red_col[c][r] = rd(f); red_g[c][r] = rd(f);
      if (gx[red_g[c][r]][case_col[c]] != red_col[c][r]) die("group element does not map rep to member"); }
  }
  fclose(f);
  chosen = xm(NC); forb = xm(NC); gfalse = xm(NC); unit_id = xm(sizeof(long long)*NC); wl = xm(sizeof(int)*NC);
  syn = xm(sizeof(u64)*NW); Fl = xm(sizeof(int)*(NC+1)); stampc = xm(sizeof(int)*NC); cnt = xm(sizeof(int)*NC);
  names = xm(sizeof(*names)*NC);
  for (int j=0;j<NC;j++){ if (j < NX) snprintf(names[j], 16, "x%d", j+1); else snprintf(names[j], 16, "q%d", j-NX+1); }
  int gz = 0;
  if (enumerate && proof) die("-e is count-only");
  if (recf && proof) die("-R is count-only");
  if (proof){
    size_t pl = strlen(proof);
    if (pl > 3 && !strcmp(proof + pl - 3, ".gz")){ char cmd[4096]; snprintf(cmd, sizeof cmd, "gzip -1 -n > '%s'", proof); pf = popen(cmd, "w"); gz = 1; }
    else pf = fopen(proof, "w");
    if (!pf) die("open proof"); ocap = 1<<23; obuf = malloc(ocap); }
  nextid = NCONS + 1;
  ostr("pseudo-Boolean proof version 3.0\n");
  ostr("f "); oint(NCONS); ostr(EOL);
  int *earlier = xm(sizeof(int)*(NX+1)); int ne = 0;
  if (pf){
    int any = 0; for (int c=0;c<NCASE;c++) if (case_nred[c]) any = 1;
    if (any) ostr("strengthening_to_core on;\n");
    for (int c=0;c<NCASE;c++){
      for (int r=0;r<case_nred[c];r++){
        ostr("red 1 ~"); ostr(names[red_col[c][r]]); ostr(" 1 "); ostr(names[case_col[c]]);
        for (int e=0;e<ne;e++){ ostr(" 1 "); ostr(names[earlier[e]]); }
        ostr(" >= 1 :"); emit_witness(red_g[c][r]); ostr(EOL); nextid++;
      }
      earlier[ne++] = case_col[c]; for (int r=0;r<case_nred[c];r++) earlier[ne++] = red_col[c][r];
    }
  }
  if (NEXP){
    for (int e=0;e<NEXP;e++){
      int m = R + exm[e];
      ostr("pol "); oint(ge_id[m]); for (int a=0;a<excn[e];a++){ ostr(" "); oint(le_id[R+exc[e][a]]); ostr(" +"); }
      for (int a=0;a<exdn[e];a++){ ostr(" "); oint(le_id[exd[e][a]]); ostr(" +"); } ostr(EOL);
      long long g2 = nextid++;
      ostr("pol "); oint(le_id[m]); for (int a=0;a<excn[e];a++){ ostr(" "); oint(ge_id[R+exc[e][a]]); ostr(" +"); }
      for (int a=0;a<exdn[e];a++){ ostr(" "); oint(ge_id[exd[e][a]]); ostr(" +"); } ostr(EOL);
      long long l2 = nextid++;
      ostr("pol "); oint(l2); ostr(" "); oint(g2); ostr(" ~"); ostr(names[qcol(m)]); ostr(" 2 * +");
      for (int a=0;a<excn[e];a++){ ostr(" "); ostr(names[qcol(R+exc[e][a])]); ostr(" 2 * +"); }
      ostr(" 2 d 2 * +"); ostr(EOL); nextid++;
      ostr("del id "); oint(g2); ostr(" "); oint(l2); ostr(EOL);
    }
    ostr("rup"); for (int a=0;a<NBAS;a++){ ostr(" 1 "); ostr(names[qcol(R+bas[a])]); } ostr(" >= 1;\n");
    sid = nextid++;
  }
  clock_t t0 = clock();
  int rc = 0;
  for (int c=0;c<NCASE;c++){
    int col = case_col[c];
    if (gfalse[col]) continue;
    long long n0 = nodes;
    cache_flush();
    if (pf){ ostr("pol "); oint(wid); for (int j=0;j<NX;j++) if (gfalse[j]){ ostr(" "); ostr(names[j]); ostr(" +"); } ostr(EOL); wcur = nextid++; }
    else wcur = wid;
    choose(col);
    lcache = NULL; nlc = 0;
    long long cert = node();
    unchoose(col);
    long long id = cert;
    if (cert > 0){ ostr("rup 1 ~"); ostr(names[col]); ostr(" >= 1 : ~ "); oint(cert); ostr(EOL); id = nextid++;
      if (pf && owned){ ostr("del id "); oint(cert); ostr(EOL); } }
    if (id == -2){ rc = 2; printf("case %d (column %d): SAT\n", c, col); break; }
    if (id == -3){ rc = 3; printf("case %d: node limit\n", c); break; }
    gfalse[col] = 1; unit_id[col] = id;
    for (int r=0;r<case_nred[c];r++){
      int g = red_col[c][r];
      ostr("rup 1 ~"); ostr(names[g]); ostr(" >= 1;\n"); unit_id[g] = nextid++;
      gfalse[g] = 1;
    }
    printf("case %d col %d nodes %lld (total %lld) rowclauses %lld cpu %.1fs\n", c, col, nodes - n0, nodes, nrowcl,
           (double)(clock()-t0)/CLOCKS_PER_SEC);
    fflush(stdout);
  }
  if (rc == 0){
    for (int j=0;j<NX;j++) if (!gfalse[j]) die("column not refuted");
    cache_flush();
    for (int i=R;i<NR;i++) if (isbas[i - R]){ int q = qcol(i); choose(q); row_clause(i); unchoose(q); }
    ostr("rup >= 1;\n");
    long long cid = nextid++;
    ostr("output NONE;\nconclusion UNSAT : "); oint(cid); ostr(";\nend pseudo-Boolean proof;\n");
  }
  if (recf) fclose(recf);
  oflush(); if (pf){ if (gz){ if (pclose(pf) != 0) die("gzip failed"); } else fclose(pf); }
  if (cachemax) printf("cache trims %lld (cachemax %lld)\n", ntrim, cachemax);
  printf("RESULT %s W=%d nodes=%lld prune_cover=%lld prune_pack=%lld leaf_empty=%lld leaf_weight=%lld blocked=%lld qbranch=%lld tight=%lld rowclauses=%lld proof_lines~%lld nsol=%lld qnodes=%lld trivial_recorded=%lld leaf_trivial0=%lld wrapK=%lld cpu=%.1fs\n",
         rc==0?(nsol?"ENUMERATED":"UNSAT"):rc==2?"SAT":"LIMIT", W, nodes, nprune1, nprune2, nleaf0, nleafw, nblk, nqbr, ntight, nrowcl, nextid - NCONS - 1, nsol, nqnodes, ntriv, nleafq, nwrap,
         (double)(clock()-t0)/CLOCKS_PER_SEC);
  return rc;
}
