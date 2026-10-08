/* Audit E-020: exhaustive backtracking (no SAT) over per-check starts s_c in Z_8, 144 checks.
   Constraint: for each data qubit q, the 6 times s_c + k_c(q) mod 8 are pairwise distinct.
   Propagation: forward checking on domains (bitmask of 8) + per-data-qubit pigeonhole (unassigned checks <=
   number of free times reachable), MRV variable choice. Optional: fix check FIXC to value FIXV (argv).
   Prints every solution and node count.  Usage: p8search inst.txt [fixc fixv] */
#include <stdio.h>
#include <stdlib.h>
#define NC 144
#define NQ 144
int kq[NC][6], kk[NC][6];
int qc[NQ][6], qk[NQ][6], nqc[NQ];
int val[NC];
unsigned char dom[NC];
long long nodes = 0, nsol = 0;
static int popc(unsigned x){return __builtin_popcount(x);}
static unsigned rot(unsigned m, int k){k&=7; return ((m<<k)|(m>>(8-k)))&0xff;}
int consistent_q(int q){
  /* times used by assigned checks; free times; unassigned checks must fit (pigeonhole), and each
     unassigned check must have some free time (FC guarantees) */
  unsigned used=0, reach=0; int un=0;
  for(int j=0;j<6;j++){int c=qc[q][j];
    if(val[c]>=0) used|=1u<<((val[c]+qk[q][j])&7);
    else {un++; reach|=rot(dom[c],qk[q][j]);}}
  reach&=~used;
  return popc(reach)>=un;
}
void search(int depth){
  nodes++;
  int best=-1,bs=99;
  for(int c=0;c<NC;c++) if(val[c]<0){int s=popc(dom[c]); if(s<bs){bs=s;best=c;}}
  if(best<0){nsol++; printf("SOL"); for(int c=0;c<NC;c++) printf(" %d",val[c]); printf("\n"); fflush(stdout); return;}
  if(bs==0) return;
  int c=best;
  for(int v=0;v<8;v++) if(dom[c]>>v&1){
    unsigned char save[NC]; for(int i=0;i<NC;i++) save[i]=dom[i];
    val[c]=v; dom[c]=1u<<v; int ok=1;
    for(int j=0;j<6&&ok;j++){int q=kq[c][j]; if(q<0) continue; int t=(v+kk[c][j])&7;
      for(int i=0;i<6;i++){int d=qc[q][i]; if(d==c) continue;
        int bad=(t-qk[q][i])&7;
        if(val[d]>=0){ if(((val[d]+qk[q][i])&7)==t){ok=0;break;} }
        else { dom[d]&=~(1u<<bad); if(!dom[d]){ok=0;break;} }
      }}
    if(ok){ /* pigeonhole on all data qubits touched by c's neighbours (cheap: all) */
      for(int q=0;q<NQ&&ok;q++) if(nqc[q]==6 && !consistent_q(q)) ok=0; }
    if(ok) search(depth+1);
    val[c]=-1; for(int i=0;i<NC;i++) dom[i]=save[i];
  }
}
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"r");
  for(int c=0;c<NC;c++){int ci,p; if(fscanf(f,"%d %d",&ci,&p)!=2) return 1;
    for(int j=0;j<6;j++){ if(fscanf(f,"%d %d",&kq[c][j],&kk[c][j])!=2) return 1;
      int q=kq[c][j]; qc[q][nqc[q]]=c; qk[q][nqc[q]]=kk[c][j]; nqc[q]++; }}
  for(int q=0;q<NQ;q++) if(nqc[q]!=6){fprintf(stderr,"q%d deg %d\n",q,nqc[q]);return 1;}
  /* optional env SKIP="q1,q2,...": drop the all-different constraint of these data qubits (control experiments) */
  char*sk=getenv("SKIP"); if(sk){ char*e=sk; while(*e){ int q=strtol(e,&e,10); if(*e==',') e++;
      /* replace qubit q's checks by private dummy entries: detach by giving each a unique far offset class */
      for(int j=0;j<6;j++){int c=qc[q][j]; for(int i=0;i<6;i++) if(kq[c][i]==q) kq[c][i]=-1;} nqc[q]=0; } }
  for(int c=0;c<NC;c++){val[c]=-1;dom[c]=0xff;}
  if(argc>3){int fc=atoi(argv[2]),fv=atoi(argv[3]); dom[fc]=1u<<fv;}
  search(0);
  printf("DONE solutions=%lld nodes=%lld\n",nsol,nodes);
  return 0;
}
