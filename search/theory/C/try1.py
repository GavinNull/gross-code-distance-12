import sys, time
from search.theory.C.project import load, project
t0=time.time(); D = load("results/theory-C/W8.pkl"); print("load", round(time.time()-t0,1))
for S in ([0,1,5,6,7],[0,7,8,11,12],[0,2,3,6,7]):
    o, done, dt = project(D, S, legal_only=True, tmax=60); print(S, "legal", len(o), done, round(dt,1))
    o, done, dt = project(D, S, tmax=120); print(S, "relax", len(o), done, round(dt,1))
