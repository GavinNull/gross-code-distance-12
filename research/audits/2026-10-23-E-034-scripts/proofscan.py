"""Auditor: structural scan of a pbdfs VeriPB 3.0 proof (plain text).
Reports: rule census; position of the last 'red' vs the first 'del'/'pol'/'rup'; that every deleted id was derived in
the proof (id > number of input constraints + red steps, i.e. never an input or symmetry constraint), never deleted
twice; that every hint / pol operand id is live (derived and not deleted) at the time of use; ids of 'conclusion'.
    uv run python proofscan.py OPB_NCONS PROOF
"""
import json, re, sys
ncons = int(sys.argv[1]); path = sys.argv[2]
nxt = ncons + 1
live = set(range(1, ncons + 1)); deleted = set()
census = {}; first = {}; last_red = 0; red_ids = set(); bad_use = []; bad_del = []
for ln, line in enumerate(open(path), 1):
    s = line.strip()
    if ln == 1 or not s: continue
    rule = s.split()[0]
    census[rule] = census.get(rule, 0) + 1
    first.setdefault(rule, ln)
    body = s[:-1] if s.endswith(';') else s
    if rule in ('red', 'rup', 'pol'):
        if rule == 'pol':
            ids = [int(t) for t in body.split()[1:] if re.fullmatch(r'\d+', t)]
            # pol: numbers following '*' or 'd' are multipliers/divisors, not ids
            toks = body.split()[1:]; ids = []
            for i, t in enumerate(toks):
                if re.fullmatch(r'\d+', t) and not (i + 1 < len(toks) and toks[i + 1] in ('*', 'd')):
                    ids.append(int(t))
        elif rule == 'rup' and ' : ' in body:
            ids = [int(t) for t in body.split(' : ')[1].split() if t != '~']
        else:
            ids = []
        for i in ids:
            if i not in live: bad_use.append((ln, i))
        if rule == 'red': last_red = ln; red_ids.add(nxt)
        live.add(nxt); nxt += 1
    elif rule == 'del':
        for t in body.split()[2:]:
            i = int(t)
            if i <= ncons or i in red_ids or i not in live: bad_del.append((ln, i))
            live.discard(i); deleted.add(i)
    elif rule == 'conclusion':
        concl = body
out = dict(proof=path, census=census, first_line=first, last_red_line=last_red,
           red_before_any_derivation_or_deletion=last_red < min(first.get(r, 1 << 60) for r in ('del', 'pol', 'rup')),
           deletions=len(deleted), bad_deletions=bad_del[:5], n_bad_deletions=len(bad_del),
           uses_of_dead_ids=bad_use[:5], n_uses_of_dead_ids=len(bad_use), conclusion=concl, ids_used=nxt - 1)
print(json.dumps(out))
