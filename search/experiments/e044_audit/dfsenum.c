/* E-044 audit: independent exact enumeration of weight-W undetected logicals of a DEM (columns = distinct
   (detector set, observable mask) signatures).  Canonical detector-driven DFS: the set's smallest column m0 is the
   seed (columns < m0 forbidden); at every node the flipped detector with the fewest admissible columns is resolved
   by branching over the admissible columns touching it; earlier siblings are forbidden in later sibling subtrees
   (each set generated exactly once).  Last column found by exact syndrome lookup.  Sets whose syndrome vanishes
   before weight W are pruned (a minimum-weight logical contains no proper zero-syndrome subset); such events with a
   nonzero observable are reported as LOWER (would mean distance < W).
   input (stdin): M D NWORDS_NEEDED ; then M lines: ndet d1 .. dn obsmask
   output: one line per logical "SOL c1 .. cW", final "COUNT n LOWER m NODES x". usage: dfsenum W */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define MAXD 256
#define NW 4
typedef struct { uint64_t w[NW]; } bs;
static int M, D, W;
static int *ndet, **det; static uint64_t *obs; static bs *syn;
static int *ncol, **col;            /* columns per detector */
static int *forb, *inset;
static int S[64]; static long long count = 0, lower = 0, nodes = 0;
/* hash: syndrome -> list of columns with that syndrome */
#define HB (1<<20)
static int *hhead, *hnext;
static uint64_t hsh(const bs *s){ uint64_t h=1469598103934665603ULL; for(int i=0;i<NW;i++){h^=s->w[i]; h*=1099511628211ULL; h^=h>>29;} return h&(HB-1);}
static int eq(const bs*a,const bs*b){for(int i=0;i<NW;i++) if(a->w[i]!=b->w[i]) return 0; return 1;}
static int pc(const bs*a){int c=0; for(int i=0;i<NW;i++) c+=__builtin_popcountll(a->w[i]); return c;}
static int m0;
static void rec(int depth, bs cur, uint64_t ob){
  nodes++;
  int r = W - depth;
  int s = pc(&cur);
  if (s == 0) { if (ob) lower++; return; }
  if (s > 9*r) return;
  if (r == 1) {
    for (int c = hhead[hsh(&cur)]; c >= 0; c = hnext[c]) {
      if (c > m0 && !forb[c] && !inset[c] && eq(&syn[c], &cur) && (ob ^ obs[c])) {
        count++; printf("SOL"); for(int i=0;i<depth;i++) printf(" %d",S[i]); printf(" %d\n",c);
      }
    }
    return;
  }
  /* choose flipped detector with fewest admissible columns */
  int bd=-1, bn=1<<30;
  for (int i=0;i<NW;i++){ uint64_t x=cur.w[i]; while(x){ int b=__builtin_ctzll(x); x&=x-1; int d=64*i+b; int n=0;
      for(int j=0;j<ncol[d];j++){int c=col[d][j]; if(c>m0 && !forb[c] && !inset[c]) n++;}
      if(n<bn){bn=n;bd=d;} } }
  if (bn==0) return;
  int lst[512], nl=0;
  for(int j=0;j<ncol[bd];j++){int c=col[bd][j]; if(c>m0 && !forb[c] && !inset[c]) lst[nl++]=c;}
  for (int j=0;j<nl;j++){
    int c=lst[j]; bs nx; for(int i=0;i<NW;i++) nx.w[i]=cur.w[i]^syn[c].w[i];
    inset[c]=1; S[depth]=c; rec(depth+1, nx, ob^obs[c]); inset[c]=0; forb[c]++;
  }
  for (int j=0;j<nl;j++) forb[lst[j]]--;
}
int main(int argc,char**argv){
  W=atoi(argv[1]); int lo = argc>2? atoi(argv[2]):0; int hi = argc>3? atoi(argv[3]):-1;
  if(scanf("%d %d",&M,&D)!=2) return 1; if(D>64*NW){fprintf(stderr,"too many dets\n");return 1;}
  ndet=calloc(M,sizeof(int)); det=calloc(M,sizeof(int*)); obs=calloc(M,8); syn=calloc(M,sizeof(bs));
  ncol=calloc(D,sizeof(int)); col=calloc(D,sizeof(int*));
  for(int c=0;c<M;c++){ scanf("%d",&ndet[c]); det[c]=malloc(sizeof(int)*ndet[c]);
    for(int i=0;i<ndet[c];i++){scanf("%d",&det[c][i]); syn[c].w[det[c][i]/64]|=1ULL<<(det[c][i]%64); ncol[det[c][i]]++;}
    unsigned long long o; scanf("%llu",&o); obs[c]=o; }
  for(int d=0;d<D;d++){col[d]=malloc(sizeof(int)*ncol[d]); ncol[d]=0;}
  for(int c=0;c<M;c++) for(int i=0;i<ndet[c];i++){int d=det[c][i]; col[d][ncol[d]++]=c;}
  hhead=malloc(sizeof(int)*HB); memset(hhead,-1,sizeof(int)*HB); hnext=malloc(sizeof(int)*M);
  for(int c=0;c<M;c++){uint64_t h=hsh(&syn[c]); hnext[c]=hhead[h]; hhead[h]=c;}
  forb=calloc(M,sizeof(int)); inset=calloc(M,sizeof(int));
  if(hi<0) hi=M-1;
  for(m0=lo;m0<=hi;m0++){
    if(ndet[m0]==0) continue;
    inset[m0]=1; S[0]=m0; rec(1, syn[m0], obs[m0]); inset[m0]=0;
  }
  printf("COUNT %lld LOWER %lld NODES %lld\n",count,lower,nodes);
  return 0;
}
