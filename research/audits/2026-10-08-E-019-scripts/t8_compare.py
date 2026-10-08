"""gate-by-gate comparison: my circuits (from paper Tables IV/VIII) vs search/experiments/e019/common.spec."""
import sys, itertools
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search')
from inst import make
from search.experiments.e019 import common as E
lab = {('IV', 0, 0): 'repo', ('IV', 1, 1): 'paper', ('IV', 0, 1): 'std01', ('IV', 1, 0): 'std10',
       ('VIII', 0, 0): 'swap2', ('VIII', 0, 1): 'sw01', ('VIII', 1, 0): 'sw10', ('VIII', 1, 1): 'sw11'}
ok = bad = 0
mapping = {}
for code in ('bb72', 'bb108', 'bb144', 'bb288'):
    for hom in ('x', 'y', 'xy'):
        c = E.get_code(code)
        if not E.hom_valid(c, hom):
            continue
        theirs = {}
        for v in E.VARIANTS:
            gates, meas, _a, _b = E.spec(c, hom, v)
            theirs[v] = [(tuple(frozenset(l) for l in gates[r]), frozenset(meas[r]['X']), frozenset(meas[r]['Z'])) for r in range(2)]
        for kind in ('IV', 'VIII'):
            for sa, sb in itertools.product((0, 1), (0, 1)):
                M = make(code, hom, kind, sa, sb)
                mine = []
                for i in (1, 2):
                    layers, meas = M.F(i)
                    mine.append((tuple(frozenset(l) for l in layers), frozenset(meas['X']), frozenset(meas['Z'])))
                hits = [v for v, t in theirs.items() if t == mine]
                if hits:
                    ok += 1
                else:
                    bad += 1
                mapping[f'{code} {hom} {kind}{sa}{sb}'] = hits
for k, v in mapping.items():
    print(k, '->', v)
print('matched', ok, 'unmatched', bad)
