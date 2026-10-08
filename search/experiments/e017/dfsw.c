/* E-017: multi-word port of the E-013 auditor / E-014 DFS (search/experiments/e014/dfs128.c).
 * Algorithm unchanged; only the syndrome type changes from u128 to NW x uint64 (NW = 5 -> up to 320 rows),
 * and the logical mask lm is a 32-bit int (<= 32 observables).
 * Question decided: is there x with He x = 0, Le x != 0, |x| <= W ?  (case = lowest orbit used, see dfs128.c)
 *   - a minimum-weight logical is syndrome-minimal, so a syndrome-driven DFS that stops at syndrome 0 reaches it;
 *   - x* contains a column of its lowest-index orbit o; translating, x* contains rep(o) and no column of orbits < o;
 *   - branching on an odd row r with the fewest available columns: branch i takes c_i and forbids c_1..c_{i-1};
 *   - prune: depth + ceil(popcount(syn)/wmax) > W; an odd row with no available column;
 *   - with 1 column left: hash lookup of the syndrome among available columns.
 * instance format: R N NO / N lines: NW words (hex) lm orbit / NO reps
 * usage: dfsw inst.txt W case [split_mod split_idx]
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#define NW 5
#define MAXN 2048
#define MAXR (64*NW)
typedef struct { uint64_t w[NW]; } syn_t;
static inline int popc(const syn_t *a){ int s=0; for(int i=0;i<NW;i++) s+=__builtin_popcountll(a->w[i]); return s; }
static inline int iszero(const syn_t *a){ for(int i=0;i<NW;i++) if(a->w[i]) return 0; return 1; }
static inline int eq(const syn_t *a, const syn_t *b){ for(int i=0;i<NW;i++) if(a->w[i]!=b->w[i]) return 0; return 1; }
static inline void xorin(syn_t *a, const syn_t *b){ for(int i=0;i<NW;i++) a->w[i]^=b->w[i]; }
static int R, N, NO, W;
static syn_t ch[MAXN]; static int cl[MAXN], corb[MAXN], cw[MAXN];
static int reps[MAXN];
static int *rowc[MAXR]; static int rown[MAXR];
static int avail_cnt[MAXR];
static char forb[MAXN], chosen[MAXN];
static int stack_[64]; static int depth;
static long long nodes = 0, found = 0;
static int wmax = 1;
static int split_mod = 1, split_idx = 0;
#define HS (1<<16)
static int hhead[HS], hnext[MAXN];
static unsigned hidx(const syn_t *s){ uint64_t h=0x12345; for(int i=0;i<NW;i++){ h ^= s->w[i]; h *= 0x9e3779b97f4a7c15ULL; h ^= h>>29; } h *= 0xbf58476d1ce4e5b9ULL; h ^= h>>32; return (unsigned)(h & (HS-1)); }
static void mark(int c, int delta){ for(int k=0;k<NW;k++){ uint64_t h=ch[c].w[k]; while(h){ int i=__builtin_ctzll(h); h&=h-1; avail_cnt[64*k+i]+=delta; } } }
static void report(int extra1, int lm){
  found++;
  if (found <= 50){
    printf("FOUND w=%d lm=%d cols:", depth + (extra1>=0), lm);
    for (int i=0;i<depth;i++) printf(" %d", stack_[i]);
    if (extra1>=0) printf(" %d", extra1);
    printf("\n"); fflush(stdout);
  }
}
static long long stop_after = 1;
static void dfs(syn_t syn, int lm, int level){
  nodes++;
  if (found >= stop_after) return;
  if (iszero(&syn)){ if (lm) report(-1,lm); return; }
  int rem = W - depth;
  int u = popc(&syn);
  if (rem <= 0) return;
  if ((u + wmax - 1) / wmax > rem) return;
  if (rem == 1){
    for (int c = hhead[hidx(&syn)]; c >= 0; c = hnext[c])
      if (eq(&ch[c],&syn) && !forb[c] && !chosen[c] && (lm ^ cl[c])) report(c, lm^cl[c]);
    return;
  }
  int best=-1, bc=1<<30;
  for(int k=0;k<NW;k++){ uint64_t s=syn.w[k]; while(s){ int i=64*k+__builtin_ctzll(s); s&=s-1; if(avail_cnt[i]<bc){bc=avail_cnt[i]; best=i;} } }
  if (bc == 0) return;
  int tried[MAXN]; int nt=0; int bi=0;
  for (int k=0;k<rown[best];k++){
    int c = rowc[best][k];
    if (forb[c] || chosen[c]) continue;
    int my = bi++;
    if (level==0 && split_mod>1 && (my % split_mod)!=split_idx){ forb[c]=1; mark(c,-1); tried[nt++]=c; continue; }
    chosen[c]=1; mark(c,-1); stack_[depth++]=c;
    syn_t s2 = syn; xorin(&s2,&ch[c]);
    dfs(s2, lm ^ cl[c], level+1);
    depth--; chosen[c]=0;
    forb[c]=1; tried[nt++]=c;
  }
  for (int k=0;k<nt;k++){ forb[tried[k]]=0; mark(tried[k],+1); }
}
int main(int argc, char **argv){
  if (argc < 4){ fprintf(stderr,"usage: dfsw inst W case [split_mod split_idx [stop_after]]\n"); return 1; }
  FILE *f = fopen(argv[1],"r"); if(!f) return 5; W=atoi(argv[2]); int cs=atoi(argv[3]);
  if (argc>=6){ split_mod=atoi(argv[4]); split_idx=atoi(argv[5]); }
  if (argc>=7) stop_after=atoll(argv[6]);
  if (fscanf(f,"%d %d %d",&R,&N,&NO)!=3) return 2;
  if (R > MAXR || N > MAXN) { fprintf(stderr,"too big\n"); return 6; }
  for (int j=0;j<N;j++){ for(int k=0;k<NW;k++){ unsigned long long v; if(fscanf(f,"%llx",&v)!=1) return 3; ch[j].w[k]=v; }
    if (fscanf(f,"%d %d",&cl[j],&corb[j])!=2) return 3; cw[j]=popc(&ch[j]); if(cw[j]>wmax) wmax=cw[j]; }
  for (int o=0;o<NO;o++) if (fscanf(f,"%d",&reps[o])!=1) return 4;
  memset(hhead,-1,sizeof hhead);
  for (int j=N-1;j>=0;j--){ unsigned b=hidx(&ch[j]); hnext[j]=hhead[b]; hhead[b]=j; }
  for (int i=0;i<R;i++){ rowc[i]=malloc(sizeof(int)*N); rown[i]=0; }
  for (int j=0;j<N;j++) for(int k=0;k<NW;k++){ uint64_t h=ch[j].w[k]; while(h){ int i=64*k+__builtin_ctzll(h); h&=h-1; rowc[i][rown[i]++]=j; } }
  for (int i=0;i<R;i++) avail_cnt[i]=rown[i];
  clock_t t0=clock();
  for (int j=0;j<N;j++) if (corb[j]<cs){ forb[j]=1; mark(j,-1); }
  int c0=reps[cs];
  chosen[c0]=1; mark(c0,-1); stack_[depth++]=c0;
  dfs(ch[c0], cl[c0], 0);
  double sec=(double)(clock()-t0)/CLOCKS_PER_SEC;
  printf("SUMMARY W=%d case=%d split=%d/%d nodes=%lld found=%lld wmax=%d sec=%.1f\n",W,cs,split_idx,split_mod,nodes,found,wmax,sec);
  return 0;
}
