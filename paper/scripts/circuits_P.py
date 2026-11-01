"""Circuit data for revision P: Table I (best circuit distance per period), Table II and Table S1 (timings), and the
delta matrices used in Fig. 1 and SM S2.

Everything structural is read from the schedule specs (qec-schedule/v1 json): period, reset step, CNOT order, CNOT
steps, measurement step, membership in the class T(P) (one timing per check type, six distinct CNOT steps spanning at
most P-3 steps between reset and measurement, distinct steps modulo P on every data qubit) and delta(A_i, B_j).
Circuit distances and extended-code distances are read from the audit result files where they exist
(results/E-040-audit-circ, results/E-043-audit: direct DEM searches and list enumerations); the values for the
older circuits (u11, c11, Fig. 12) come from their audits and are listed in AUDITED below with the audit file.

Usage (repository root):
  PYTHONPATH=.:tests uv run python paper/scripts/circuits_P.py          # writes paper/figures/circuits_P.json, prints rows
  PYTHONPATH=.:tests uv run python paper/scripts/circuits_P.py --check  # also checks Tables I, II, S1 of draft.tex
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "paper" / "scripts"))
from check_tables import CODES, type_patterns  # noqa: E402

CIRCUITS = [  # name, code, spec, label in the paper
    ("ibmg", "gross", "search/experiments/e033/ibm_gross_spec.json", "IBM depth 8"),
    ("fig12", "gross", "results/E-021-gross-new-orders/fig12_spec.json", "SBB Fig. 12"),
    ("g8", "gross", "search/experiments/e040/g8_d11_spec.json", "$g_8$"),
    ("g9", "gross", "search/experiments/e043/g9_d11_spec.json", "$g_9$"),
    ("g10", "gross", "search/experiments/e040/g10_d12_spec.json", "$g_{10}$"),
    ("u11", "gross", "search/experiments/e032/u11_spec.json", "$u_{11}$"),
    ("ibm90", "bb90", "search/experiments/e030/ibm90_spec.json", "IBM depth 8"),
    ("b9", "bb90", "search/experiments/e043/b9_d9_spec.json", "$b_9$"),
    ("b10", "bb90", "search/experiments/e043/b10_d9_spec.json", "$b_{10}$"),
    ("c11", "bb90", "search/experiments/e030/c11_spec.json", "$c_{11}$"),
]

# Audited values not recoverable from the audit result files of E-040/E-043 (older audits).
AUDITED = {
    "u11": dict(dcirc=12, dext={"Z": 10, "X": 10}, audit="research/audits/2026-10-22-E-032.md; 2026-10-29-theoryB.md"),
    "c11": dict(dcirc=10, dext={"Z": 8, "X": 8}, audit="research/audits/2026-10-22-E-030.md; 2026-10-29-theoryB.md"),
    "fig12": dict(dcirc=11, dext={"Z": 11, "X": 11}, audit="research/audits/2026-10-05 (E-014); SBB Prop. 3, Cor. 1"),
    "g10": dict(dcirc=12, audit="research/audits/2026-10-30-E-040-circuits.md; 2026-11-01-E-042.md"),
    "g8": dict(dcirc=11, audit="research/audits/2026-10-30-E-040-circuits.md"),
}
# Bulk upper bounds in T(P) (research/audits/2026-10-30-E-040-impossibility.md, all five CONFIRMED); P >= 10 (gross),
# P >= 11 ([[90]]): the code distance.
BOUND = {("gross", 8): 11, ("gross", 9): 11, ("gross", 10): 12, ("gross", 11): 12,
         ("bb90", 8): 8, ("bb90", 9): 9, ("bb90", 10): 9, ("bb90", 11): 10}
D = {"gross": 12, "bb90": 10}


def in_T(spec_path, code):
    """T(P) membership read off the spec; returns (bool, reason)."""
    d = json.loads((ROOT / spec_path).read_text())
    P = d["period"]
    try:
        pats = type_patterns(str(ROOT / spec_path), code)
    except AssertionError:
        return False, "checks of one type do not share one timing"
    for t in "XZ":
        seq, prep, meas = pats[t]
        rel = [(tt - prep) % P for _, tt in seq]
        m = (meas - prep) % P
        if len(set(rel)) != 6 or min(rel) != 1 or m != max(rel) + 1 or max(rel) - min(rel) > P - 3:
            return False, f"{t} window"
    n = CODES[code]["L"] * CODES[code]["M"] * 2
    steps = [[] for _ in range(n)]
    for key in ("x_checks", "z_checks"):
        for ch in d[key]:
            for q, tt in ch["cnots"]:
                steps[q].append(tt % P)
    if any(len(s) != len(set(s)) for s in steps):
        return False, "data qubit collision"
    return True, ""


def delta_matrix(code, spec_path):
    """delta(A_i, B_j) in the Z basis via the audited bulk model (search/theory/B_audit)."""
    from search.theory.B_audit.common import Bulk, get_code, load_spec_dict
    c = CODES[code]
    L, M = c["L"], c["M"]
    idx = lambda a, b: (a % L) * M + (b % M)
    B = Bulk(load_spec_dict(spec_path), get_code(code), "Z")
    out = [[None] * 3 for _ in range(3)]
    for ch, (order, tm) in enumerate(B.wr):
        a, b = divmod(ch, M)
        xl = {idx(a + dx, b + dy): i for i, (_, (dx, dy)) in enumerate(c["A"])}
        for z, (ro, rt) in enumerate(B.rd):
            ha, hb = divmod(z, M)
            zl = {idx(ha - dx, hb - dy): j for j, (_, (dx, dy)) in enumerate(c["B"])}
            sh = set(xl) & set(zl)
            if not sh:
                continue
            q = sh.pop()
            v = B.sig(z, q, tm[q])
            i, j = xl[q], zl[q]
            assert out[i][j] in (None, v), "delta not translation invariant"
            out[i][j] = v
    return out


def audit_values(name):
    """(dcirc, dext per basis, max R of direct search, source) from the audit result files."""
    rec = dict(AUDITED.get(name, {}))
    files = {"g8": "E-040-audit-circ", "g10": "E-040-audit-circ"}
    src = files.get(name, "E-043-audit")
    dfile = ROOT / "results" / src / "direct.jsonl"
    lfile = ROOT / "results" / src / "lists.jsonl"
    found, none = {}, {}
    if dfile.exists():
        for line in dfile.open():
            r = json.loads(line)
            if r["spec"] != name:
                continue
            (found if r.get("found") else none).setdefault(r["basis"], []).append((r["R"], r["W<="]))
    if found or none:
        rmax = max(R for v in none.values() for R, _ in v) if none else 0
        lower = min(W for v in none.values() for _, W in v) + 1 if none else None
        upper = min(W for v in found.values() for _, W in v) if found else None
        rec["direct_Rmax"] = rmax
        rec["direct_lower"] = lower
        rec["direct_witness"] = upper
        rec.setdefault("audit", f"results/{src}/direct.jsonl")
        if upper is not None and lower is not None:
            assert upper == lower, (name, lower, upper)
            assert rec.get("dcirc", upper) == upper, (name, rec.get("dcirc"), upper)
            rec["dcirc"] = upper
        elif lower is not None:
            assert rec["dcirc"] >= lower, name
    if lfile.exists() and "dext" not in rec:
        dext = {}
        for line in lfile.open():
            r = json.loads(line)
            if r.get("name", r.get("spec")) == name:
                # the enumeration is complete below W, so the smallest listed weight is d_ext
                dext[r["basis"]] = r.get("d_ext", min(int(w) for w in r["by_weight"]))
        if dext:
            rec["dext"] = dext
    return rec


def main():
    out = []
    for name, code, spec, label in CIRCUITS:
        P = json.loads((ROOT / spec).read_text())["period"]
        t_ok, why = in_T(spec, code)
        row = dict(name=name, code=code, spec=spec, label=label, period=P, in_T=t_ok, not_T_reason=why)
        row.update(audit_values(name))
        if t_ok:
            pats = type_patterns(str(ROOT / spec), code)
            row["timing"] = {t: dict(reset=pats[t][1], order="".join(n for n, _ in pats[t][0]),
                                     steps=[tt for _, tt in pats[t][0]], meas=pats[t][2]) for t in "XZ"}
            row["delta"] = delta_matrix(code, spec)
            flat = [v for r in row["delta"] for v in r]
            row["delta_coboundary"] = len(set(flat)) == 1
        out.append(row)
    # Table I consistency: in each (code, P) the best attained value in T equals the bulk upper bound.
    for (code, P), b in BOUND.items():
        att = [r["dcirc"] for r in out if r["code"] == code and r["period"] == P and r["in_T"]]
        assert att and max(att) == b, (code, P, att, b)
    (ROOT / "paper" / "figures" / "circuits_P.json").write_text(json.dumps(out, indent=1))
    for r in out:
        print(f"{r['name']:6s} {r['code']:5s} P={r['period']:2d} T={r['in_T']!s:5s} dcirc={r['dcirc']:2d} "
              f"dext={r.get('dext')} delta={r.get('delta')}")
        if r["in_T"]:
            for t in "XZ":
                tm = r["timing"][t]
                print(f"    {t}: reset {tm['reset']}  {tm['order']}  {', '.join(map(str, tm['steps']))}  meas {tm['meas']}")
    if "--check" in sys.argv:
        sys.exit(check(out))


def check(out):
    tex = (ROOT / "paper" / "draft.tex").read_text()
    by = {r["name"]: r for r in out}
    bad = 0
    for lab in ("tab:timing", "tab:timingS"):
        i = tex.index("\\label{%s}" % lab)
        j = tex.index("\\end{tabular}", i)
        cur = None
        for row in tex[i:j].split("\\\\"):
            m = re.search(r"%\s*circ=(\w+)", row)
            if m:
                cur = m.group(1)
            if "&" not in row or not re.search(r"&\s*\$[XZ]\$\s*&", row):
                continue
            cells = [c.strip() for c in row.split("&")]
            t = re.search(r"\$([XZ])\$", cells[1]).group(1)
            tm = by[cur]["timing"][t]
            ok = (cells[2] == str(tm["reset"]) and cells[3].replace("$", "").replace("_", "") == tm["order"]
                  and cells[4].replace(" ", "") == ",".join(map(str, tm["steps"])) and cells[5] == str(tm["meas"]))
            print(f"{lab:12s} {cur:6s} {t} {'OK' if ok else 'MISMATCH'}")
            bad += not ok
    i = tex.index("\\label{tab:periods}")
    j = tex.index("\\end{tabular}", i)
    for row in tex[i:j].split("\\\\"):
        cells = [c.replace("\\hline", "").strip() for c in row.split("&")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        P = int(cells[0])
        for code, k in (("gross", 1), ("bb90", 3)):
            val = int(re.sub(r"[^0-9]", "", cells[k].split("(")[0]) or -1)
            ok = val == BOUND[(code, P)]
            print(f"tab:periods  P={P} {code:5s} {'OK' if ok else 'MISMATCH'} ({val})")
            bad += not ok
    # Table S3 (delta of every circuit): entries "(a,b,c;\\,d,e,f;\\,g,h,i)" in the order of the rows
    i = tex.index("\\label{tab:deltaall}")
    j = tex.index("\\end{tabular}", i)
    names = {"IBM gross": "ibmg", "IBM $\\code{90,8,10}$": "ibm90", "$g_8$": "g8", "$g_9$": "g9",
             "$g_{10}$": "g10", "$u_{11}$": "u11", "$b_9$": "b9", "$b_{10}$": "b10", "$c_{11}$": "c11"}
    for row in tex[i:j].split("\\\\"):
        cells = [c.replace("\\hline", "").strip() for c in row.split("&")]
        for k in range(0, len(cells) - 1, 2):
            key = next((v for n, v in names.items() if cells[k].startswith(n)), None)
            if key is None:
                continue
            vals = [int(x) for x in re.findall(r"-?\d+", cells[k + 1])]
            ok = vals == [v for r in by[key]["delta"] for v in r]
            print(f"tab:deltaall {key:6s} {'OK' if ok else 'MISMATCH'}")
            bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    main()
