/* Exhaustive search for a low-weight extended-code logical that writes a VeriPB proof (format 3.0; -2: format 2.0)
 * of unsatisfiability of the OPB instance written by code/veripb/build_opb.py.  The search is NOT trusted: only the
 * proof is (checked by VeriPB against the OPB file).
 *
 * usage: pbdfs INST [-p PROOF] [-n NODELIMIT] [-F N] [-2]
 *   -p PROOF   write the proof (otherwise count only); a .gz name writes gzip
 *   -n LIMIT   stop (exit 3) after LIMIT nodes
 *   -F N       bounded parity-clause cache (see below); -F 0 (default) keeps every clause of a case
 * build:  cc -O2 -o pbdfs code/veripb/pbdfs.c
 * exit: 0 UNSAT (proof complete), 2 SAT (solution printed), 3 node limit, 1 error
 *
 * Certificates: a node returns a constraint that propagates ~c (c = column the node added) under its parent's
 * assignment; the parent derives C(S,F) by RUP from those (hints in order) and deletes them.
 * Search (per case column c, in the order of the instance file):  S = chosen columns (x columns and q "columns"),
 * F = columns forbidden by earlier sibling branches, G = columns refuted globally (unit clauses ~x_g already in
 * the proof).  Row i is "open" if the parity of |S cap N_i| is odd and the row cannot be repaired by its own q
 * (check rows always; logical rows when q_i is chosen / forbidden).  Every solution extending (S, F, G) must
 * contain an available column of every open row.
 *   - open row with no available column            -> leaf: rup C ; [~ R(i,S)]
 *   - weight budget used up                         -> leaf: rup C ; [~ weight ge_i le_i]  (the weight constraint
 *                                                      sets every other column to 0; the binary digits of the
 *                                                      row equality then fail by propagation, the row being odd)
 *   - counting bound (packing / max coverage)       -> leaf: pol sum R + lambda*weight  (certificate)
 *   - tight counting bound (slack s): the same pol propagates to 0 every column whose use costs more than s
 *     (outside a packing of exactly rem rows; or lambda - cnt_j > s for the cover bound); those columns are
 *     excluded in the whole subtree and the pol is put first in the hints of every RUP below.
 *   - no open row: S is a solution (some q chosen or an odd logical row with free q) -> blocked set (rup) or SAT;
 *     otherwise branch on the clause sum q >= 1.
 *   - else branch on the open row with the fewest available columns: child i takes c_i and forbids c_1..c_{i-1};
 *     parent: rup C ; [~ child_1 .. child_k R(i,S)]
 * C(S,F) = (OR_{s in S} ~s) OR (OR_{f in F} f).  R(i,T) for T = S cap N_i of odd size is the parity clause
 * sum_{N_i \ T} x + 3 sum_T ~x >= 1 (same propagation as the clause), derived from the row equality
 * sum_N x - 2A = 0 (ge: >=, le: <=) by  le + 2 * ((ge + sum_T 2 ~x) / 2) :
 * (ge + sum_T 2~x)/2 :  sum_{N\T} x + sum_T ~x - A >= -(t-1)/2  (t = |T| odd, the division rounds up);
 * le : -sum_{N\T} x + sum_T ~x + 2A >= t ;  le + 2*(...) : sum_{N\T} x + 3 sum_T ~x >= 1.
 * Symmetry: before any derivation (strengthening_to_core on, so redundance goals come from the core only), case c
 * with orbit members g adds  ~x_g v x_rep v OR_{earlier orbits} x  by redundance (witness: translation sigma with
 * sigma(rep) = g).  All goals hold under the negated clause: the formula is invariant, earlier symmetry clauses map
 * to clauses containing ~x of an earlier orbit (false there) or x_g (true there).  Case c ends with the unit ~x_rep;
 * the units ~x_g follow by unit propagation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define MAXC 1024
#define MAXR 1024
#define NWM 16
typedef uint64_t u64;

static int NX, NQ, NC, R, NL, NR, W, NCONS, NW;
static int isx[MAXC], ncr[MAXC], *crow[MAXC];
static int nrc[MAXR], *rcol[MAXR];
static int ge_id[MAXR], le_id[MAXR], wid, sid;
static u64 cmask[MAXC][NWM];
static int NBAS, *bas, NEXP, *exm, *excn, **exc, *exdn, **exd; static char isbas[MAXR];
static int NB, bid0; static int *bsz, **bcol;
static int NCASE; static int *case_col, *case_nred; static int **red_col; static char ***red_wit;

static char chosen[MAXC], forb[MAXC], gfalse[MAXC];
static long long unit_id[MAXC];
static char xforb[MAXC];                 /* excluded in the current subtree by an ancestor's tight bound */
static long long xstack[64]; static int nxs = 0;          /* id of the unit ~x_j once column j is refuted globally */
static int avail[MAXR];                 /* available columns per row (not chosen/forbidden/gfalse) */
static u64 syn[NWM];
static int S[64], nS, wt;
static int Fl[4096], nF;
static long long nodes = 0, limit = -1, nprune1 = 0, nprune2 = 0, nleaf0 = 0, nleafw = 0, nblk = 0, nqbr = 0;
static FILE *pf = NULL;
static long long nextid;
static long long nrowcl = 0;
static char names[MAXC][16];

static void die(const char *m){ fprintf(stderr, "error: %s\n", m); exit(1); }

/* ---------------- proof output helpers */
static int V3 = 1;   /* VeriPB proof format 3.0 (default); -2 = format 2.0 */
#define EOL (V3 ? ";\n" : "\n")
static char *obuf; static size_t olen = 0, ocap = 0;
static void oflush(void){ if (pf && olen){ fwrite(obuf, 1, olen, pf); } olen = 0; }
static void ostr(const char *s){ if (!pf) return; size_t l = strlen(s); if (olen + l + 1 > ocap){ oflush(); if (l + 1 > ocap){ ocap = 2*(l+1); obuf = realloc(obuf, ocap);} } memcpy(obuf+olen, s, l); olen += l; if (olen > (1<<22)) oflush(); }
static void oint(long long v){ char b[32]; snprintf(b, sizeof b, "%lld", v); ostr(b); }

/* ---------------- row clause cache: key (row, sorted T) */
typedef struct { int row, nt; int t[24]; long long id; } RKey;
static RKey *ht; static size_t htcap = 0, htn = 0;
static u64 rhash(int row, int nt, const int *t){ u64 h = 1469598103934665603ULL ^ (u64)row * 0x9e3779b97f4a7c15ULL; for (int i=0;i<nt;i++){ h ^= (u64)(t[i]+1); h *= 1099511628211ULL; h ^= h >> 29; } return h; }
static void htgrow(void){
  size_t oc = htcap; RKey *o = ht; htcap = oc ? oc*2 : (1<<16); ht = calloc(htcap, sizeof(RKey)); if (!ht) die("oom");
  for (size_t i=0;i<oc;i++) if (o[i].id){ u64 h = rhash(o[i].row, o[i].nt, o[i].t) & (htcap-1); while (ht[h].id) h = (h+1)&(htcap-1); ht[h] = o[i]; }
  free(o);
}
static int cmpi(const void *a, const void *b){ return *(const int*)a - *(const int*)b; }
static int inrow(int j, int i){ return (cmask[j][i>>6] >> (i&63)) & 1; }

static long long row_clause(int i){
  int t[64], nt = 0;
  for (int k=0;k<nS;k++) if (inrow(S[k], i)) t[nt++] = S[k];
  if (nt > 24) die("T too large");
  if (!(nt & 1)) die("row clause for even row");
  qsort(t, nt, sizeof(int), cmpi);
  if (!pf) return 1;
  if ((htn+1)*2 > htcap) htgrow();
  u64 h = rhash(i, nt, t) & (htcap-1);
  while (ht[h].id){ if (ht[h].row == i && ht[h].nt == nt && !memcmp(ht[h].t, t, nt*sizeof(int))) return ht[h].id; h = (h+1)&(htcap-1); }
  /* derive  R' = le + 2 * ((ge + sum_T 2 ~x) / 2)  =  sum_{N\\T} x + 3 sum_T ~x >= 1  (propagates like the clause) */
  ostr("pol "); oint(le_id[i]); ostr(" "); oint(ge_id[i]);
  for (int a=0;a<nt;a++){ ostr(" ~"); ostr(names[t[a]]); ostr(" 2 * +"); }
  ostr(" 2 d 2 * +");
  /* drop globally refuted columns: R + (~x_g >= 1) */
  for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (gfalse[j]){ ostr(" "); oint(unit_id[j]); ostr(" +"); } }
  ostr(EOL);
  long long id = nextid++;
  ht[h].row = i; ht[h].nt = nt; memcpy(ht[h].t, t, nt*sizeof(int)); ht[h].id = id; htn++; nrowcl++;
  return id;
}

static void cache_flush(void){
  if (pf && htn){ int cnt = 0; for (size_t h=0;h<htcap;h++) if (ht[h].id){ if (cnt % 1000 == 0) ostr(cnt ? (V3 ? ";\ndel id" : "\ndel id") : "del id"); ostr(" "); oint(ht[h].id); cnt++; } ostr(EOL); }
  if (htcap) memset(ht, 0, htcap*sizeof(RKey)); htn = 0;
}

/* Bounded row-clause cache (-F N).  Without it every parity clause of a case stays alive until the end of the
   case; VeriPB keeps every live constraint in memory (about 2-4 KB each), which for u11 W = 11 reached 40-67 GB.
   With -F N, whenever the cache holds more than N clauses at the entry of a node, every cached clause that is not
   pinned is deleted from the proof (and from the cache; it is re-derived if needed again).  Pinned = the parity
   clause `base` of every active branch frame and every certificate a child returned without ownership (owned = 0,
   e.g. a parity clause returned by a leaf), i.e. exactly the ids that a pending RUP of an ancestor will still cite.
   The search itself is unchanged (the cache affects only the proof text). */
static long long cachemax = 0, ntrim = 0;
static long long *pin; static int npin = 0, pincap = 0;
static void pin_push(long long id){ if (npin == pincap){ pincap = pincap ? 2*pincap : 1024; pin = realloc(pin, pincap*sizeof(long long)); if (!pin) die("oom"); } pin[npin++] = id; }
static int is_pinned(long long id){ for (int k=0;k<npin;k++) if (pin[k] == id) return 1; return 0; }
static void cache_trim(void){
  if (!pf || !cachemax || (long long)htn <= cachemax) return;
  RKey *keep = malloc((npin+1)*sizeof(RKey)); int nk = 0, cnt = 0;
  for (size_t h=0;h<htcap;h++) if (ht[h].id){
    if (is_pinned(ht[h].id)){ if (nk > npin) die("pin overflow"); keep[nk++] = ht[h]; }
    else { if (cnt % 1000 == 0) ostr(cnt ? (V3 ? ";\ndel id" : "\ndel id") : "del id"); ostr(" "); oint(ht[h].id); cnt++; } }
  if (cnt) ostr(EOL);
  memset(ht, 0, htcap*sizeof(RKey)); htn = 0;
  for (int k=0;k<nk;k++){ u64 h = rhash(keep[k].row, keep[k].nt, keep[k].t) & (htcap-1); while (ht[h].id) h = (h+1)&(htcap-1); ht[h] = keep[k]; htn++; }
  free(keep); ntrim++;
}

static void emit_clause_rup(const long long *hints, int nh){
  ostr("rup");
  for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
  for (int k=0;k<nF;k++){ ostr(" 1 "); ostr(names[Fl[k]]); }
  ostr(" >= 1"); if (nh >= 0 || !V3) ostr(V3 ? " :" : " ;");
  if (nh >= 0){ ostr(" ~"); for (int k=0;k<nxs;k++){ ostr(" "); oint(xstack[k]); } for (int k=0;k<nh;k++){ ostr(" "); oint(hints[k]); } }
  ostr(EOL);
}

/* ---------------- state updates */
static void setcol_unavail(int j, int d){ for (int k=0;k<ncr[j];k++) avail[crow[j][k]] += d; }
static void choose(int j){ chosen[j] = 1; setcol_unavail(j, -1); S[nS++] = j; if (isx[j]) wt++; for (int w=0;w<NW;w++) syn[w] ^= cmask[j][w]; }
static void unchoose(int j){ chosen[j] = 0; setcol_unavail(j, +1); nS--; if (isx[j]) wt--; for (int w=0;w<NW;w++) syn[w] ^= cmask[j][w]; }
static int qcol(int i){ return NX + (i - R); }   /* q column of logical row i (i >= R) */
static int qfree(int i){ int q = qcol(i); return !chosen[q] && !forb[q] && !gfalse[q]; }
static int isavail(int j){ return !chosen[j] && !forb[j] && !gfalse[j] && !xforb[j]; }

static int open_rows(int *O){
  int no = 0;
  for (int w=0;w<NW;w++){ u64 s = syn[w]; while (s){ int b = __builtin_ctzll(s); s &= s-1; int i = (w<<6)+b; if (i < R || !qfree(i)) O[no++] = i; } }
  return no;
}

static long long node(void);
static int owned;                         /* set by node(): parent must delete the returned certificate */
static int leafrup = 1;
static int tight = 1; static long long ntight = 0;
static int enumerate = 0; static long long nsol = 0;
static long long wcur;                    /* weight constraint of the current case (refuted columns weakened away) */

/* Certificates.  node() returns the id of a constraint that, under the PARENT's assignment (parent S true,
   parent F and earlier siblings false), propagates ~c for the column c the node added (or conflicts).  The parent
   then derives its clause C(S,F) by RUP with hints  ~ cert_1 .. cert_k base  (base = parity clause of the branched
   row, or the input clause sum q >= 1). */
typedef struct { long long rid, pid; } LC;
static LC *lcache; static int nlc;         /* rem = 0 leaves of the current parent: R id -> pol (R + weight) id */

static char excl[MAXC];                   /* columns excluded at the current node by a tight counting bound */
static long long branch_x(int row, long long xcert);
static long long branch(int row){ return branch_x(row, 0); }
static long long branch_x(int row, long long xcert){
  int cand[MAXC], nc = 0;
  if (row >= 0){ for (int k=0;k<nrc[row];k++){ int j = rcol[row][k]; if (isavail(j) && !(xcert && excl[j])) cand[nc++] = j; } }
  else { for (int i=R;i<NR;i++){ int q = qcol(i); if (isbas[i - R] && isavail(q)) cand[nc++] = q; } }
  int xl[MAXC], nxl = 0;
  if (xcert){ for (int j=0;j<NX;j++) if (excl[j]){ excl[j] = 0; xforb[j] = 1; setcol_unavail(j, -1); xl[nxl++] = j; }
    xstack[nxs++] = xcert; }
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
    if (id < 0){ free(ch); free(own); free(mylc); npin = pin0; return id; }
    ch[a] = id; own[a] = owned;
    if (!owned) pin_push(id);
    forb[j] = 1; setcol_unavail(j, -1); Fl[nF++] = j;
  }
  for (int a=f0;a<nF;a++){ forb[Fl[a]] = 0; setcol_unavail(Fl[a], +1); }
  nF = f0;
  if (xcert){ nxs--; for (int a=0;a<nxl;a++){ xforb[xl[a]] = 0; setcol_unavail(xl[a], +1); } }
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
  free(ch); free(own); free(mylc); free(h);
  npin = pin0;
  lcache = NULL; nlc = 0;
  owned = 1;
  return id;
}

static long long node(void){
  nodes++;
  cache_trim();
  if (limit > 0 && nodes > limit) return -3;
  int O[MAXR]; int no = open_rows(O);
  int rem = W - wt;
  if (no == 0){
    int sol = 0;
    for (int k=0;k<nS;k++) if (!isx[S[k]]) sol = 1;
    for (int i=R;i<NR && !sol;i++) if (((syn[i>>6]>>(i&63))&1) && qfree(i)) sol = 1;
    if (sol){
      for (int b=0;b<NB;b++){ int all = 1; for (int a=0;a<bsz[b] && all;a++) if (!chosen[bcol[b][a]]) all = 0;
        if (all){ nblk++; owned = 0; return bid0 + b; } }
      printf("SAT columns:"); for (int k=0;k<nS;k++) if (isx[S[k]]) printf(" %d", S[k]); printf("\n");
      if (enumerate){ nsol++; owned = 0; return 1; }     /* count-only enumeration: record and go on */
      return -2;
    }
    nqbr++;
    return branch(-1);
  }
  int best = -1, bc = 1<<30;
  for (int a=0;a<no;a++) if (avail[O[a]] < bc){ bc = avail[O[a]]; best = O[a]; }
  if (bc == 0){ nleaf0++; owned = 0; return row_clause(best); }
  if (rem <= 0){
    nleafw++;
    /* prefer an open row that does not contain the last added column: same parity clause for all such siblings */
    int last = S[nS-1], pick = -1;
    for (int a=0;a<no;a++) if (!inrow(last, O[a]) && (pick < 0 || O[a] < pick)) pick = O[a];
    if (pick < 0) pick = best;
    if (leafrup){
      /* weight exhausted: the full weight constraint propagates every other column (refuted ones included) to 0;
         the row equality of the odd row then fails by propagation on its binary digits (no parity clause needed) */
      ostr("rup"); for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
      for (int k=0;k<nF;k++) if (!isx[Fl[k]]){ ostr(" 1 "); ostr(names[Fl[k]]); }
      ostr(V3 ? " >= 1 : ~ " : " >= 1 ; ~ "); oint(wid); ostr(" "); oint(ge_id[pick]); ostr(" "); oint(le_id[pick]); ostr(EOL);
      owned = 1; return nextid++; }
    long long r = row_clause(pick);
    if (0){
      /* weight exhausted: the weight constraint propagates every other column to 0, so the clause needs no F part */
      ostr("rup"); for (int k=0;k<nS;k++){ ostr(" 1 ~"); ostr(names[S[k]]); }
      for (int k=0;k<nF;k++) if (!isx[Fl[k]]){ ostr(" 1 "); ostr(names[Fl[k]]); }   /* forbidden q's are not weight-bounded */
      ostr(V3 ? " >= 1 : ~ " : " >= 1 ; ~ "); oint(wcur); ostr(" "); oint(r); ostr(EOL);
      owned = 1; return nextid++; }
    if (lcache) for (int a=0;a<nlc;a++) if (lcache[a].rid == r){ owned = 1; return lcache[a].pid; }
    ostr("pol "); oint(r); ostr(" "); oint(wcur); ostr(" +"); ostr(EOL);
    long long p = nextid++;
    if (lcache){ lcache[nlc].rid = r; lcache[nlc].pid = p; nlc++; }
    owned = 1; return p;
  }
  /* counting bounds */
  {
    static int cnt[MAXC]; int lam = 0;
    u64 om[NWM]; memset(om, 0, sizeof om); for (int a=0;a<no;a++) om[O[a]>>6] |= 1ULL << (O[a]&63);
    for (int j=0;j<NX;j++){ if (!isavail(j)) { cnt[j] = 0; continue; }
      int c = 0; for (int w=0;w<NW;w++) c += __builtin_popcountll(cmask[j][w] & om[w]);
      cnt[j] = c; if (c > lam) lam = c; }
    int use[MAXR], nu = 0, lamu = 0;
    {
      /* greedy packing first (fewest rows in the derivation): rows whose available columns are pairwise disjoint;
         stop as soon as rem + 1 rows are packed */
      static char cov[MAXC]; memset(cov, 0, NX);
      int ord[MAXR]; for (int a=0;a<no;a++) ord[a] = O[a];
      for (int a=1;a<no;a++){ int v = ord[a], b = a-1; while (b>=0 && avail[ord[b]] > avail[v]){ ord[b+1] = ord[b]; b--; } ord[b+1] = v; }
      for (int a=0;a<no && nu <= rem;a++){ int i = ord[a], ok = 1;
        for (int k=0;k<nrc[i] && ok;k++){ int j = rcol[i][k]; if (isx[j] && isavail(j) && cov[j]) ok = 0; }
        if (ok){ use[nu++] = i; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isx[j] && isavail(j)) cov[j] = 1; } } }
      if (nu > rem){ nprune2++; lamu = 1; } else nu = 0;
    }
    if (!nu && no > lam * rem){ nprune1++; for (int a=0;a<no;a++) use[nu++] = O[a]; lamu = lam; }
    if (nu){
      long long rid[MAXR]; for (int a=0;a<nu;a++) rid[a] = row_clause(use[a]);
      ostr("pol "); oint(rid[0]); for (int a=1;a<nu;a++){ ostr(" "); oint(rid[a]); ostr(" +"); }
      ostr(" "); oint(wcur); if (lamu > 1){ ostr(" "); oint(lamu); ostr(" *"); } ostr(" +"); ostr(EOL);
      owned = 1; return nextid++;
    }
    /* tight bounds: (a) packing of exactly rem rows -> every available column outside their union is excluded;
       (b) cover with |O| = lam*rem -> every column with cnt < lam is excluded.  The excluding constraint
       (same pol as a prune, slack 0) propagates those columns to 0 in the parent's RUP. */
    if (tight){
      static char ua[MAXC], ub[MAXC]; int npa = 0, npb = 0;
      int pk[MAXR], np = 0;
      {
        static char cov[MAXC]; memset(cov, 0, NX);
        int ord[MAXR]; for (int a=0;a<no;a++) ord[a] = O[a];
        for (int a=1;a<no;a++){ int v = ord[a], b = a-1; while (b>=0 && avail[ord[b]] > avail[v]){ ord[b+1] = ord[b]; b--; } ord[b+1] = v; }
        for (int a=0;a<no && np < rem;a++){ int i = ord[a], ok = 1;
          for (int k=0;k<nrc[i] && ok;k++){ int j = rcol[i][k]; if (isx[j] && isavail(j) && cov[j]) ok = 0; }
          if (ok){ pk[np++] = i; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isx[j] && isavail(j)) cov[j] = 1; } } }
        if (np == rem) for (int j=0;j<NX;j++){ ua[j] = isavail(j) && !cov[j]; npa += ua[j]; }
      }
      { int sl = lam * rem - no;   /* cover bound slack: columns with lam - cnt > slack are excluded */
        if (sl >= 0) for (int j=0;j<NX;j++){ ub[j] = isavail(j) && lam - cnt[j] > sl; npb += ub[j]; } }
      int mode = 0;
      if (np == rem && npa >= npb && npa > 0) mode = 1; else if (npb > 0) mode = 2;
      if (mode){
        char *u = mode == 1 ? ua : ub;
        /* branching row: fewest surviving candidates */
        int br = -1, bs = 1<<30;
        for (int a=0;a<no;a++){ int i = O[a], sv = 0; for (int k=0;k<nrc[i];k++){ int j = rcol[i][k]; if (isavail(j) && !(isx[j] && u[j])) sv++; }
          if (sv < bs){ bs = sv; br = i; } }
        if (bs < avail[best]){
          ntight++;
          long long xc;
          if (mode == 1){ long long rid[MAXR]; for (int a=0;a<np;a++) rid[a] = row_clause(pk[a]);
            ostr("pol "); oint(rid[0]); for (int a=1;a<np;a++){ ostr(" "); oint(rid[a]); ostr(" +"); } ostr(" "); oint(wcur); ostr(" +"); ostr(EOL); }
          else { long long rid[MAXR]; for (int a=0;a<no;a++) rid[a] = row_clause(O[a]);
            ostr("pol "); oint(rid[0]); for (int a=1;a<no;a++){ ostr(" "); oint(rid[a]); ostr(" +"); } ostr(" "); oint(wcur);
            if (lam > 1){ ostr(" "); oint(lam); ostr(" *"); } ostr(" +"); ostr(EOL); }
          xc = nextid++;
          for (int j=0;j<NX;j++) excl[j] = u[j];
          return branch_x(br, xc);
        }
      }
    }
  }
  return branch(best);
}

/* ---------------- input */
static int rd(FILE *f){ int v; if (fscanf(f, "%d", &v) != 1) die("parse"); return v; }

int main(int argc, char **argv){
  if (argc < 2) die("usage: pbdfs INST [-p PROOF] [-n LIMIT]");
  const char *proof = NULL;
  for (int a=2;a<argc;a++){
    if (!strcmp(argv[a], "-p")) proof = argv[++a];
    else if (!strcmp(argv[a], "-n")) limit = atoll(argv[++a]);
    else if (!strcmp(argv[a], "-e")) enumerate = 1;   /* list all solutions (no proof) */
    else if (!strcmp(argv[a], "-P")) leafrup = 0;
    else if (!strcmp(argv[a], "-2")) V3 = 0;
    else if (!strcmp(argv[a], "-F")) cachemax = atoll(argv[++a]);   /* bounded row-clause cache */
    else if (!strcmp(argv[a], "-T")) tight = 0;    /* no tight-bound exclusions */   /* rem = 0 leaves as pol (R + weight) instead of rup */
  }
  FILE *f = fopen(argv[1], "r"); if (!f) die("open inst");
  NX = rd(f); NQ = rd(f); R = rd(f); W = rd(f); NCONS = rd(f);
  NL = NQ; NC = NX + NQ; NR = R + NL; NW = (NR + 63) / 64;
  if (NC > MAXC || NR > MAXR || NW > NWM) die("too large");
  for (int j=0;j<NC;j++){ isx[j] = rd(f); ncr[j] = rd(f); crow[j] = malloc(sizeof(int)*ncr[j]);
    for (int k=0;k<ncr[j];k++){ int i = rd(f); crow[j][k] = i; cmask[j][i>>6] |= 1ULL << (i&63); nrc[i]++; } }
  for (int i=0;i<NR;i++){ rcol[i] = malloc(sizeof(int)*nrc[i]); nrc[i] = 0; }
  for (int j=0;j<NC;j++) for (int k=0;k<ncr[j];k++){ int i = crow[j][k]; rcol[i][nrc[i]++] = j; }
  for (int i=0;i<NR;i++){ ge_id[i] = rd(f); le_id[i] = rd(f); avail[i] = nrc[i]; }
  wid = rd(f); sid = rd(f);
  NBAS = rd(f); bas = malloc(sizeof(int)*(NBAS+1)); for (int a=0;a<NBAS;a++){ bas[a] = rd(f); isbas[bas[a]] = 1; }
  NEXP = rd(f); exm = malloc(sizeof(int)*(NEXP+1)); excn = malloc(sizeof(int)*(NEXP+1)); exdn = malloc(sizeof(int)*(NEXP+1));
  exc = malloc(sizeof(int*)*(NEXP+1)); exd = malloc(sizeof(int*)*(NEXP+1));
  for (int e=0;e<NEXP;e++){ exm[e] = rd(f); excn[e] = rd(f); exc[e] = malloc(sizeof(int)*(excn[e]+1)); for (int a=0;a<excn[e];a++) exc[e][a] = rd(f);
    exdn[e] = rd(f); exd[e] = malloc(sizeof(int)*(exdn[e]+1)); for (int a=0;a<exdn[e];a++) exd[e][a] = rd(f); }
  NB = rd(f); bid0 = rd(f);
  bsz = malloc(sizeof(int)*(NB+1)); bcol = malloc(sizeof(int*)*(NB+1));
  for (int b=0;b<NB;b++){ bsz[b] = rd(f); bcol[b] = malloc(sizeof(int)*bsz[b]); for (int a=0;a<bsz[b];a++) bcol[b][a] = rd(f);
    if (bsz[b] > W) die("blocked sets must have size <= W"); }
  NCASE = rd(f);
  case_col = malloc(sizeof(int)*NCASE); case_nred = malloc(sizeof(int)*NCASE);
  red_col = malloc(sizeof(int*)*NCASE); red_wit = malloc(sizeof(char**)*NCASE);
  size_t lcap = 1<<20; char *line = malloc(lcap);
  for (int c=0;c<NCASE;c++){
    case_col[c] = rd(f); case_nred[c] = rd(f);
    red_col[c] = malloc(sizeof(int)*(case_nred[c]+1)); red_wit[c] = malloc(sizeof(char*)*(case_nred[c]+1));
    for (int r=0;r<case_nred[c];r++){
      red_col[c][r] = rd(f);
      if (!fgets(line, lcap, f)) die("witness");
      size_t l = strlen(line); while (l && (line[l-1]=='\n' || line[l-1]==' ')) line[--l] = 0;
      red_wit[c][r] = strdup(line[0]==' ' ? line+1 : line);
    }
  }
  fclose(f);
  for (int j=0;j<NC;j++){ if (j < NX) snprintf(names[j], 16, "x%d", j+1); else snprintf(names[j], 16, "q%d", j-NX+1); }
  int gz = 0;
  if (enumerate && proof) die("-e is count-only");
  if (proof){
    size_t pl = strlen(proof);
    if (pl > 3 && !strcmp(proof + pl - 3, ".gz")){ char cmd[4096]; snprintf(cmd, sizeof cmd, "gzip -1 -n > '%s'", proof); pf = popen(cmd, "w"); gz = 1; }
    else pf = fopen(proof, "w");
    if (!pf) die("open proof"); ocap = 1<<23; obuf = malloc(ocap); }
  nextid = NCONS + 1;
  ostr(V3 ? "pseudo-Boolean proof version 3.0\n" : "pseudo-Boolean proof version 2.0\n");
  ostr("f "); oint(NCONS); ostr(EOL);
  /* symmetry breaking, before any derivation: for case c (orbit rep), every orbit member g gets
     ~x_g v x_rep v OR_{earlier cases' orbits} x  by redundance with the translation sigma, sigma(rep) = g */
  int *earlier = malloc(sizeof(int)*(NX+1)); int ne = 0;
  if (pf){
    int any = 0; for (int c=0;c<NCASE;c++) if (case_nred[c]) any = 1;
    if (any) ostr(V3 ? "strengthening_to_core on;\n" : "strengthening_to_core on\n");
    for (int c=0;c<NCASE;c++){
      for (int r=0;r<case_nred[c];r++){
        ostr("red 1 ~"); ostr(names[red_col[c][r]]); ostr(" 1 "); ostr(names[case_col[c]]);
        for (int e=0;e<ne;e++){ ostr(" 1 "); ostr(names[earlier[e]]); }
        ostr(V3 ? " >= 1 : " : " >= 1 ; "); ostr(red_wit[c][r]); ostr(EOL); nextid++;
      }
      earlier[ne++] = case_col[c]; for (int r=0;r<case_nred[c];r++) earlier[ne++] = red_col[c][r];
    }
  }
  /* logical rows outside the basis: from  E_m - sum_{c_m} E_l - sum_{d_m} E_r  (all x coefficients even)
     derive  3 ~q_m + 3 sum_{c_m} q_l >= 1  as  le' + 2*((ge' + 2 ~q_m + sum 2 q_l)/2); then sum_{basis} q >= 1 by RUP */
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
    ostr("rup"); for (int a=0;a<NBAS;a++){ ostr(" 1 "); ostr(names[qcol(R+bas[a])]); } ostr(V3 ? " >= 1;\n" : " >= 1 ;\n");
    sid = nextid++;
  }
  clock_t t0 = clock();
  int rc = 0;
  for (int c=0;c<NCASE;c++){
    int col = case_col[c];
    if (gfalse[col]) continue;
    long long n0 = nodes;
    cache_flush();
    /* weight constraint with the refuted columns weakened away (they are false anyway) */
    if (pf){ int any = 0; ostr("pol "); oint(wid); for (int j=0;j<NX;j++) if (gfalse[j]){ ostr(" "); ostr(names[j]); ostr(" +"); any = 1; }
      ostr(EOL); wcur = nextid++; if (!any){} }
    else wcur = wid;
    choose(col);
    lcache = NULL; nlc = 0;
    long long cert = node();
    unchoose(col);
    long long id = cert;
    if (cert > 0){ ostr("rup 1 ~"); ostr(names[col]); ostr(V3 ? " >= 1 : ~ " : " >= 1 ; ~ "); oint(cert); ostr(EOL); id = nextid++;
      if (pf && owned){ ostr("del id "); oint(cert); ostr(EOL); } }
    if (id == -2){ rc = 2; printf("case %d (column %d): SAT\n", c, col); break; }
    if (id == -3){ rc = 3; printf("case %d: node limit\n", c); break; }
    gfalse[col] = 1; setcol_unavail(col, -1); unit_id[col] = id;
    for (int r=0;r<case_nred[c];r++){
      int g = red_col[c][r];
      /* unit ~x_g: propagation from the symmetry-breaking clause (all earlier orbits and x_rep are false) */
      ostr("rup 1 ~"); ostr(names[g]); ostr(V3 ? " >= 1;\n" : " >= 1 ;\n"); unit_id[g] = nextid++;
      if (!gfalse[g]){ gfalse[g] = 1; setcol_unavail(g, -1); }
    }
    printf("case %d col %d nodes %lld (total %lld) rowclauses %lld cpu %.1fs\n", c, col, nodes - n0, nodes, nrowcl,
           (double)(clock()-t0)/CLOCKS_PER_SEC);
    fflush(stdout);
  }
  if (rc == 0){
    /* all x columns are refuted; parity clauses ~q_l v (some column of row l) give q = 0; sum q >= 1 fails */
    for (int j=0;j<NX;j++) if (!gfalse[j]) die("column not refuted");
    cache_flush();
    for (int i=R;i<NR;i++) if (isbas[i - R]){ int q = qcol(i); choose(q); row_clause(i); unchoose(q); }
    ostr(V3 ? "rup >= 1;\n" : "rup >= 1 ;\n");
    long long cid = nextid++;
    ostr(V3 ? "output NONE;\nconclusion UNSAT : " : "output NONE\nconclusion UNSAT : "); oint(cid); ostr(V3 ? ";\nend pseudo-Boolean proof;\n" : "\nend pseudo-Boolean proof\n");
  }
  oflush(); if (pf){ if (gz){ if (pclose(pf) != 0) die("gzip failed"); } else fclose(pf); }
  if (cachemax) printf("cache trims %lld (cachemax %lld)\n", ntrim, cachemax);
  printf("RESULT %s W=%d nodes=%lld prune_cover=%lld prune_pack=%lld leaf_empty=%lld leaf_weight=%lld blocked=%lld qbranch=%lld tight=%lld rowclauses=%lld proof_lines~%lld cpu=%.1fs\n",
         rc==0?(nsol?"ENUMERATED":"UNSAT"):rc==2?"SAT":"LIMIT", W, nodes, nprune1, nprune2, nleaf0, nleafw, nblk, nqbr, ntight, nrowcl, nextid - NCONS - 1,
         (double)(clock()-t0)/CLOCKS_PER_SEC);
  return rc;
}
