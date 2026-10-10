"""E-022 audit: build a full-T memory instance from the E-019 auditor's circuit constructor (mycirc, from the
paper tables, detector-complete via noiseless sampling) for an E-022 key, CSS-projected or full DEM, with the
K-translation orbit split. Gate sets are matched to the experimenter's spec (circuit definition only).
usage: a1_build.py key basis T full(0/1) [window lo-hi]  -> writes instance, prints JSON"""
import sys, json, os, itertools, time
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search')
sys.path.insert(0, '/Users/ephemeral/Desktop/qec-ai-search/research/audits/2026-10-08-E-019-scripts')
import mycirc
from inst import make, noisy, dem_columns, orbits, write_instance
from search.experiments.e019 import common
from search.experiments.e022.newcodes import load_random, register
OUT = '/Users/ephemeral/Desktop/qec-ai-search/results/E-022-audit'

def match(key):
    name, hom, v = key.split('_')
    c = common.get_code(name)
    gates, meas, _, _ = common.spec(c, hom, v)
    theirs = [(tuple(frozenset(l) for l in gates[r]), frozenset(meas[r]['X']), frozenset(meas[r]['Z'])) for r in range(2)]
    for kind in ('IV', 'VIII'):
        for sa, sb in itertools.product((0, 1), (0, 1)):
            try:
                M = make(name, hom, kind, sa, sb)
            except AssertionError:
                continue
            mine = []
            for i in (1, 2):
                layers, ms = M.F(i)
                mine.append((tuple(frozenset(l) for l in layers), frozenset(ms['X']), frozenset(ms['Z'])))
            if mine == theirs:
                return M, (kind, sa, sb)
    return None, None

def build(key, basis, T, full, window=None):
    register(load_random()); mycirc.PARENT.update(common.CODES)
    M, lab = match(key)
    assert M is not None, 'no match'
    M.check_contraction()
    c, nc = noisy(M, basis, T, full, 'sd6', window)
    ndet, nobs, cols = dem_columns(nc)
    if not full:
        # CSS projection: keep same-basis detectors only (detector coords: 3rd coord 0=Z,1=X type; final=2)
        pass
    orb, norb = orbits(M, M.memory(basis, T, full_detectors=full), cols, None)
    why = None
    if orb is None:
        why = norb; norb = 0
    wtag = 'all' if window is None else f'{window[0]}-{window[1]}'
    path = f'{OUT}/inst_{key}_{basis}_T{T}_f{int(full)}_{wtag}.txt'
    nrows = write_instance(path, ndet, nobs, cols, orb, norb)
    return dict(key=key, basis=basis, T=T, full=full, label=lab, ndet=ndet, rows=nrows, nobs=nobs, cols=len(cols),
                norb=norb, orbit_fail=why, det_info=M.det_info, path=path), M, nc, cols

if __name__ == '__main__':
    key, basis, T, full = sys.argv[1], sys.argv[2], int(sys.argv[3]), bool(int(sys.argv[4]))
    win = tuple(map(int, sys.argv[5].split('-'))) if len(sys.argv) > 5 else None
    t0 = time.time()
    info, *_ = build(key, basis, T, full, win)
    info['sec'] = round(time.time() - t0, 1)
    print(json.dumps(info, default=str))
