"""compare a3 full-T results with the pre-registered tier-A predictions; recompute tier-B counts on audit truth."""
import json, math, collections, yaml
R = '/Users/ephemeral/Desktop/qec-ai-search'
Y = yaml.safe_load(open(f'{R}/experiments/E-022-morphing-criterion.yaml'))
pred = Y['heldout_predictions_tierA']['d_circ']
T = json.load(open(f'{R}/results/E-022-morphing-criterion/table.json'))
res = collections.defaultdict(dict)
for l in open(f'{R}/results/E-022-audit/a3_log.jsonl'):
    o = json.loads(l)
    if o['T'] != 4 or o.get('full'):
        continue
    if o['key'] in pred: res[o['key']][o['basis']] = o
c = collections.Counter(); bad = []; injbad = []; bigd = collections.Counter()
for k, v in res.items():
    for b, o in v.items():
        d = o['d_circ']
        ok = d == pred[k]
        c['hit' if ok else 'miss'] += 1
        if not ok: bad.append((k, b, pred[k], d))
        if not o.get('inject', {}).get('ok'): injbad.append((k, b))
        if d and d >= 5: bigd[(d, d < T[k]['d_end'])] += 1
print('instances', sum(len(v) for v in res.values()), dict(c), 'misses', bad, 'inject_fail', injbad)
print('d>=5 instances (d, loses):', dict(bigd))
full = [k for k in pred if len(res.get(k, {})) == 2]
if len(full) == len(pred):
    B = collections.Counter(); g = collections.defaultdict(list)
    for k in pred:
        t = res[k]['Z']['d_circ']; de = T[k]['d_end']
        B['B1_ok'] += t >= math.ceil(2 * de / 3)
        if de <= 5: B['B2_n'] += 1; B['B2_ok'] += t == de
        B['B4_ok'] += res[k]['X']['d_circ'] == t
        if de >= 3: B['B5_n'] += 1; B['B5_loss'] += t < de
        B['loss_%d' % (de - t)] += 1
        nm, hom, vv = k.split('_')
        if vv in ('repo', 'paper', 'std01', 'std10'): g[(nm, hom)].append(t < de)
    for x in g.values():
        if len(x) == 4 and any(x): B['B3_n'] += 1; B['B3_ok'] += all(x)
    print(dict(B))
