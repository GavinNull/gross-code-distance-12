/* Same algorithm as enum.c, syndromes up to 256 bits (for R >= 2 DEMs).  Same input/output format. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
typedef struct { uint64_t w[4]; } bs;
static int N, M, K, W;
static bs *syn; static uint32_t *lg;
static int **touch; static int *ntouch;
static char *ban; static int cur[64]; static long long nodes = 0, ntriv = 0, nlog = 0;
static int maxw;
static inline int pc(const bs *x){ return __builtin_popcountll(x->w[0])+__builtin_popcountll(x->w[1])+__builtin_popcountll(x->w[2])+__builtin_popcountll(x->w[3]); }
static inline int iszero(const bs *x){ return !(x->w[0]|x->w[1]|x->w[2]|x->w[3]); }
static inline int lowbit(const bs *x){ for(int i=0;i<4;i++) if(x->w[i]) return 64*i+__builtin_ctzll(x->w[i]); return -1; }
static void dfs(int d, bs s, uint32_t l){
  nodes++;
  if(iszero(&s)){
    if(l){ nlog++; printf("S %d %u", d, l); for(int i=0;i<d;i++) printf(" %d", cur[i]); printf("\n"); }
    else ntriv++;
    return;
  }
  int r = W - d; if(r<=0) return;
  if(pc(&s) > r*maxw) return;
  int i = lowbit(&s);
  int *T = touch[i]; int nt = ntouch[i];
  int added[1024]; int na=0;
  for(int a=0;a<nt;a++){
    int j=T[a]; if(ban[j]) continue;
    ban[j]=1; cur[d]=j;
    bs t = s; for(int q=0;q<4;q++) t.w[q]^=syn[j].w[q];
    dfs(d+1, t, l^lg[j]);
    added[na++]=j;
  }
  for(int a=0;a<na;a++) ban[added[a]]=0;
}
int main(){
  if(scanf("%d %d %d %d",&N,&M,&K,&W)!=4) return 1;
  if(M>256) return 2;
  syn=calloc(N,sizeof(bs)); lg=calloc(N,4); ban=calloc(N,1);
  ntouch=calloc(M,sizeof(int)); touch=calloc(M,sizeof(int*));
  for(int i=0;i<M;i++){ touch[i]=malloc(sizeof(int)*N); }
  maxw=0;
  for(int j=0;j<N;j++){ int s; scanf("%d",&s); if(s>maxw)maxw=s;
    for(int a=0;a<s;a++){ int i; scanf("%d",&i); syn[j].w[i/64]|=((uint64_t)1)<<(i%64); touch[i][ntouch[i]++]=j; }
    unsigned l; scanf("%u",&l); lg[j]=l; }
  int J; scanf("%d",&J);
  for(int jb=0;jb<J;jb++){
    int seed, nb; scanf("%d %d",&seed,&nb); memset(ban,0,N);
    for(int a=0;a<nb;a++){ int b; scanf("%d",&b); ban[b]=1; }
    ban[seed]=1; cur[0]=seed;
    dfs(1, syn[seed], lg[seed]);
    fprintf(stderr,"job %d seed %d nodes %lld logical %lld trivial %lld\n", jb, seed, nodes, nlog, ntriv);
    fflush(stdout);
  }
  return 0;
}
