"""Question C: legality CNF of W(P)/Mg(P) + static witness clauses, each pattern clause tagged with the set of checks
it involves (spreaders of H slots, M-slot readers, every reader on a slot qubit).  Dropping any set of tagged clauses
gives a sound relaxation (definitions of auxiliary LT/AND/XOR literals are kept in the base).
usage: uv run python -m search.theory.C.build W 8 HH,HHM,DDH out.pkl"""
import pickle, sys, time
from search.experiments.e038.cegar import PatternEncoder
from search.experiments.e039.scegar import make_enc
from search.experiments.e039.static import multisets, patterns_of
from search.theory.C.involved import involved

cls, P, types, out = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(","), sys.argv[4]
t0 = time.time()
E = make_enc(cls, P); PE = PatternEncoder(E)
kidx = {k: i for i, k in enumerate(E.ks)}
tagged = []          # (tag frozenset of check indices, type, clause)
for b in ("Z", "X"):
    for t in types:
        for m in multisets("bb18", b, {t}):
            tag = frozenset(kidx[k] for k in involved(b, m))
            for pat in patterns_of(b, m):
                for c in PE.clauses(pat):
                    tagged.append((tag, t, c))
pil = {i: {v: E.pi[k].eq(v) for v in range(E.pi[k].lo, E.pi[k].hi + 1)} for i, k in enumerate(E.ks)}
pickle.dump({"cls": cls, "P": P, "ks": E.ks, "base": E.cl, "nv": E.nv, "tagged": tagged, "pi_eq": pil}, open(out, "wb"))
print("nv", E.nv, "base", len(E.cl), "tagged", len(tagged), round(time.time() - t0, 1), "s")
