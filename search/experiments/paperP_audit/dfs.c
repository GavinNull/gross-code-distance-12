/* Item 5: exhaustive DFS for an undetected logical of weight <= W in a DEM.
   Input (stdin): nd nm no; then per mechanism: k d_1..d_k omask; then ns start-mechanism indices.
   Branch on the lowest unsatisfied detector, sibling exclusion; root branches over the start set (symmetry);
   a nonempty undetected set with trivial observable is pruned (a minimal logical contains no such subset).
   Output: FOUND w + mechanism list, or NONE with node count. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define MAXD 4096
#define WORDS (MAXD/64)
static int nd, nm, no, W, maxdeg = 0;
static int **md, *mk; static uint64_t *mo;
static int **dm, *dk;          /* detector -> mechanisms */
static uint64_t syn[WORDS]; static int pop = 0;
static char *excl, *used; static int chosen[64]; static long long nodes = 0;
static uint64_t obs = 0; static int soldepth = 0;
static void flip(int m){ for(int i=0;i<mk[m];i++){int d=md[m][i]; uint64_t b=1ULL<<(d&63); if(syn[d>>6]&b) pop--; else pop++; syn[d>>6]^=b;} obs^=mo[m]; }
static int lowest(void){ for(int w=0;w<WORDS;w++) if(syn[w]) return w*64+__builtin_ctzll(syn[w]); return -1; }
static int dfs(int depth){
  nodes++;
  if(pop==0){ if(depth>0){ if(obs){ soldepth=depth; return 1;} return 0; } }
  if(depth==W) return 0;
  if((pop + maxdeg - 1)/maxdeg > W-depth) return 0;
  int d = lowest();
  int *list = dm[d]; int k = dk[d]; int added[512]; int na=0;
  int res=0;
  for(int i=0;i<k && !res;i++){ int m=list[i]; if(excl[m]||used[m]) continue;
    used[m]=1; chosen[depth]=m; flip(m);
    res = dfs(depth+1);
    flip(m); used[m]=0;
    if(!res){ excl[m]=1; added[na++]=m; } }
  for(int i=0;i<na;i++) excl[added[i]]=0;
  return res;
}
int main(int argc,char**argv){
  W=atoi(argv[1]);
  if(scanf("%d %d %d",&nd,&nm,&no)!=3) return 1; if(nd>MAXD){fprintf(stderr,"too many detectors\n");return 1;}
  md=malloc(nm*sizeof(int*)); mk=malloc(nm*sizeof(int)); mo=malloc(nm*sizeof(uint64_t));
  dk=calloc(nd,sizeof(int));
  for(int m=0;m<nm;m++){ scanf("%d",&mk[m]); md[m]=malloc(mk[m]*sizeof(int)); for(int i=0;i<mk[m];i++){scanf("%d",&md[m][i]); dk[md[m][i]]++;} unsigned long long o; scanf("%llu",&o); mo[m]=o; if(mk[m]>maxdeg) maxdeg=mk[m]; }
  dm=malloc(nd*sizeof(int*)); int *fill=calloc(nd,sizeof(int));
  for(int d=0;d<nd;d++) dm[d]=malloc((dk[d]+1)*sizeof(int));
  for(int m=0;m<nm;m++) for(int i=0;i<mk[m];i++){int d=md[m][i]; dm[d][fill[d]++]=m;}
  int ns; scanf("%d",&ns); int *st=malloc(ns*sizeof(int)); for(int i=0;i<ns;i++) scanf("%d",&st[i]);
  excl=calloc(nm,1); used=calloc(nm,1);
  int found=0;
  for(int i=0;i<ns && !found;i++){ int m=st[i]; used[m]=1; chosen[0]=m; flip(m);
    found=dfs(1); flip(m); used[m]=0; if(!found) excl[m]=1; }
  if(found){ printf("FOUND %d :",soldepth); for(int i=0;i<soldepth;i++) printf(" %d",chosen[i]); }
  else printf("NONE");
  printf(" nodes %lld maxdeg %d\n", nodes, maxdeg);
  if(found){ /* print solution: re-run is unnecessary; chosen[] holds it up to depth where pop==0 */ }
  return 0;
}
