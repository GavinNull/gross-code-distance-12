"""Auditor: truncation / mismatch tests for VeriPB 3 on a passing pbdfs 3.0 proof.
    uv run python trunc.py VERIPB OPB PROOF OTHER_OPB OUT.jsonl
Every variant is fed to VeriPB through a pipe (/dev/stdin), like the streamed certificates.  A variant 'passes' only
if VeriPB prints the exact line 's VERIFIED UNSATISFIABLE'."""
import json, subprocess, sys, os
vp, opb, proof, other, out = sys.argv[1:]
data = open(proof, 'rb').read()
lines = data.split(b'\n')
idx_out = data.rfind(b'\noutput NONE;') + 1
idx_conc = data.rfind(b'\nconclusion UNSAT') + 1
idx_end = data.rfind(b'\nend pseudo-Boolean proof;') + 1
var = {
    'original': (opb, data),
    'cut_10pct_midline': (opb, data[:len(data) // 10]),
    'cut_50pct_at_line_boundary': (opb, data[:data.find(b'\n', len(data) // 2) + 1]),
    'cut_99pct_at_line_boundary': (opb, data[:data.find(b'\n', len(data) * 99 // 100) + 1]),
    'cut_before_output_line': (opb, data[:idx_out]),
    'cut_before_conclusion_line': (opb, data[:idx_conc]),
    'cut_before_end_line': (opb, data[:idx_end]),
    'cut_last_byte': (opb, data[:-1]),
    'cut_inside_conclusion_line': (opb, data[:idx_conc + 20]),
    'drop_final_rup_contradiction': (opb, data[:data.rfind(b'\nrup >= 1;') + 1] + data[idx_out:].replace(b'conclusion UNSAT : ', b'conclusion UNSAT : ')),
    'other_instance_opb': (other, data),
    'empty_stream': (opb, b''),
    'header_only': (opb, lines[0] + b'\n'),
}
with open(out, 'a') as fo:
    for k, (o, d) in var.items():
        p = subprocess.run([vp, o, '/dev/stdin'], input=d, capture_output=True)
        txt = (p.stdout + p.stderr).decode(errors='replace')
        rec = dict(variant=k, opb=os.path.basename(o), bytes=len(d), rc=p.returncode,
                   verified_unsat=any(l.strip() == 's VERIFIED UNSATISFIABLE' for l in txt.splitlines()),
                   msg=[l for l in txt.splitlines() if l.strip()][-3:])
        print(json.dumps(rec)); fo.write(json.dumps(rec) + '\n')
