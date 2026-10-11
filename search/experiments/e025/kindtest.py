"""E-025 structure: which logical kind forces the long windows?  Colour-symmetric family, period P, window limit on
one unit; CEGAR with only the logicals of one kind (X-type: hooks on X checks, Z readers; Z-type: hooks on Z checks,
X readers) or only those whose hook is (not) on a given unit."""
import sys, time
import search.experiments.e021.nwfull as NF
from search.experiments.e025.cegar_lib import Cegar
from search.experiments.e025.exact_cp import make_family

P = int(sys.argv[1]); unit = sys.argv[2]; win = int(sys.argv[3]); kinds = sys.argv[4]
F = make_family("1,2;0,3")
recs, _ = NF.prepare_full(F, "XZ")
keep = [r for r in recs if r["kind"] in kinds]
C = Cegar(F, P, keep, maxwin=win, winunits={(unit[0], int(unit[1:]))})
t0 = time.time()
st, t, info = C.run(1800)
print(f"P={P} window({unit}) <= {win} kinds={kinds} logicals={len(keep)}: {st} it={info['it']} {time.time()-t0:.0f}s", flush=True)
