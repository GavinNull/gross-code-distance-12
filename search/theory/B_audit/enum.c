/* Auditor's independent enumerator of light extended-code logicals (theory B audit).
 * Input (stdin):  N M K W
 *                 N lines: s i_1..i_s  l   (syndrome support of column, logical image as integer bitmask)
 *                 J      then J lines:  seed nb b_1..b_nb   (banned columns for this job)
 * For each job: all column sets S containing `seed`, avoiding banned columns, |S| <= W, H-sum 0,
 * found by DFS branching on the lowest unsatisfied check with sibling exclusion (each S exactly once per job).
 * A branch stops as soon as the syndrome is 0 (complete for |S| < d_ext + 3, see audit report).
 * Output: "S w L c_1 .. c_w" for every S with nonzero logical image; "Z w" counts trivial (zero-logical) sets only.
 * M <= 128 (two 64-bit words), K <= 32.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
typedef unsigned __int128 u128;
static int N, M, K, W;
static u128 *syn; static uint32_t *lg; static int *wt;
static int **touch; static int *ntouch;
static char *ban; static int cur[64]; static long long nodes = 0, ntriv = 0, nlog = 0;
static int maxw;
static int pc(u128 x){ return __builtin_popcountll((uint64_t)x) + __builtin_popcountll((uint64_t)(x>>64)); }
static int lowbit(u128 x){ uint64_t lo=(uint64_t)x; if(lo) return __builtin_ctzll(lo); return 64+__builtin_ctzll((uint64_t)(x>>64)); }
static void dfs(int d, u128 s, uint32_t l){
  nodes++;
  if(s==0){
    if(l){ nlog++; printf("S %d %u", d, l); for(int i=0;i<d;i++) printf(" %d", cur[i]); printf("\n"); }
    else ntriv++;
    return;
  }
  int r = W - d; if(r<=0) return;
  if(pc(s) > r*maxw) return;
  int i = lowbit(s);
  int *T = touch[i]; int nt = ntouch[i];
  int added[512]; int na=0;
  for(int a=0;a<nt;a++){
    int j=T[a]; if(ban[j]) continue;
    ban[j]=1; cur[d]=j;
    dfs(d+1, s^syn[j], l^lg[j]);
    added[na++]=j;     /* stays banned for later siblings */
  }
  for(int a=0;a<na;a++) ban[added[a]]=0;
}
int main(){
  if(scanf("%d %d %d %d",&N,&M,&K,&W)!=4) return 1;
  syn=calloc(N,sizeof(u128)); lg=calloc(N,4); wt=calloc(N,4); ban=calloc(N,1);
  int **lists=calloc(M,sizeof(int*)); ntouch=calloc(M,sizeof(int)); touch=calloc(M,sizeof(int*));
  for(int i=0;i<M;i++){ touch[i]=malloc(sizeof(int)*N); }
  maxw=0;
  for(int j=0;j<N;j++){ int s; scanf("%d",&s); wt[j]=s; if(s>maxw)maxw=s;
    for(int a=0;a<s;a++){ int i; scanf("%d",&i); syn[j]|=((u128)1)<<i; touch[i][ntouch[i]++]=j; }
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
