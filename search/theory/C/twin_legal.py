"""Question C: legality of a twin pair (X and Z check on the same 6 qubits) in W(P): X CNOTs at pi+s(q), Z at
pi+delta+s'(q), s,s' bijections Q->{1..6} (W8) or injections into a 7-window (W9).  Count legal (s,s') per delta."""
import itertools, sys
import numpy as np
P = int(sys.argv[1]) if len(sys.argv) > 1 else 8
L = P - 2  # window positions 1..P-2 for CNOTs (W(P): pi < tau < mu <= pi + P - 1)
perms = [p for p in itertools.permutations(range(1, L + 1), 6)]
A = np.array(perms)                       # rows: s(q) for q = 0..5
for d in range(P):
    tot = 0
    for s in A:
        x = s[None, :]
        z = d + A                         # all s'
        ok = ((x - z) % P != 0).all(1)
        diff = x - z
        for i in range(-3, 4):
            ok &= ((diff < i * P).sum(1) % 2 == 0)
        tot += ok.sum()
    print("P", P, "delta", d, "legal pairs", tot, "of", len(A) ** 2)
