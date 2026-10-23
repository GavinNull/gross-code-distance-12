"""Auditor: map a pbdfs VeriPB 3.0 proof text to 2.0 syntax line by line (own mapping), print sha256 of the result.
    uv run python v3to2.py PROOF_V3 [PROOF_V2]   -> prints sha256 of the mapped text (and of PROOF_V2, and whether equal)
Rules: header version 3.0 -> 2.0; every line must end with ';' (checked) which is removed; 'rup' lines: ' : ' -> ' ; '
(hinted) or, without hints, ' ;' appended (2.0 pbdfs always prints the separator); 'red' lines: ' : ' -> ' ; '."""
import hashlib, sys
h = hashlib.sha256(); n = 0
with open(sys.argv[1], 'rb') as f:
    first = f.readline()
    assert first == b'pseudo-Boolean proof version 3.0\n'
    h.update(b'pseudo-Boolean proof version 2.0\n')
    for line in f:
        n += 1
        assert line.endswith(b';\n'), line[:80]
        s = line[:-2]
        if s.startswith(b'rup') or s.startswith(b'red'):
            if b' : ' in s:
                assert s.count(b' : ') == 1
                s = s.replace(b' : ', b' ; ')
            else:
                s = s + b' ;'
        h.update(s + b'\n')
out = {'lines': n, 'mapped_sha256': h.hexdigest()}
if len(sys.argv) > 2:
    g = hashlib.sha256()
    with open(sys.argv[2], 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): g.update(b)
    out['v2_sha256'] = g.hexdigest(); out['equal'] = out['v2_sha256'] == out['mapped_sha256']
print(out)
