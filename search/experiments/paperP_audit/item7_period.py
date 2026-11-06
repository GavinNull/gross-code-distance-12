"""Item 7a: period lemma check for u11 and c11 by brute-force enumeration (no difference-constraint solver).
For P = 8..13 enumerate every timing vector of T(P) with the circuit's CNOT orders (X times increasing along pi_X,
first at 0, span <= P-3; Z times increasing along pi_Z, any offset, span <= P-3; distinct mod P on both data qubits
of every X/Z overlap; determinism G_L = G_R) and keep those whose G equals the circuit's G up to a constant.
Report counts per P and the minimum over realisations of max(span_X, span_Z).
  uv run python search/experiments/paperP_audit/item7_period.py
"""
import itertools, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from item3_triples import CODES, build

LAB = ["A1", "A2", "A3", "B1", "B2", "B3"]


def spec_times(spec, code):
    HX, HZ, labX, labZ = build(CODES[code]); P = spec["period"]
    def un(ch, lab):
        p = ch["prep"] % P
        inv = {q: n for n, q in lab.items()}
        return {inv[q]: p + ((t - p) % P) for q, t in ch["cnots"]}
    return P, un(spec["x_checks"][0], labX), un(spec["z_checks"][0], labZ)


def G(tx, tz, P):
    GL = tuple(tuple((tx[f"A{i}"] - tz[f"B{j}"]) // P for j in (1, 2, 3)) for i in (1, 2, 3))
    GR = tuple(tuple((tx[f"B{j}"] - tz[f"A{i}"]) // P for j in (1, 2, 3)) for i in (1, 2, 3))
    return GL, GR


def legal(tx, tz, P):
    for i in (1, 2, 3):
        pass
    left = [tx[f"A{i}"] % P for i in (1, 2, 3)] + [tz[f"B{j}"] % P for j in (1, 2, 3)]
    right = [tx[f"B{j}"] % P for j in (1, 2, 3)] + [tz[f"A{i}"] % P for i in (1, 2, 3)]
    if len(set(left)) < 6 or len(set(right)) < 6:
        return None
    GL, GR = G(tx, tz, P)
    return GL if GL == GR else None


def norm(g):
    c = g[0][0]
    return tuple(tuple(v - c for v in r) for r in g)


def main():
    out = {}
    for name, code, path in (("u11", "gross", "search/experiments/e032/u11_spec.json"),
                             ("c11", "bb90", "search/experiments/e030/c11_spec.json")):
        spec = json.load(open(Path(__file__).resolve().parents[3] / path))
        P0, tx0, tz0 = spec_times(spec, code)
        g0 = legal(tx0, tz0, P0)
        assert g0 is not None, "spec itself not legal under my conditions"
        piX = sorted(LAB, key=tx0.get); piZ = sorted(LAB, key=tz0.get)
        res = {"orders": ["".join(piX), "".join(piZ)], "G_spec": norm(g0),
               "spans_spec": [max(tx0.values()) - min(tx0.values()), max(tz0.values()) - min(tz0.values())]}
        for P in range(8, 14):
            n = 0; minspan = None
            for xs in itertools.combinations(range(1, P - 2), 5):
                x = (0,) + xs
                tx = dict(zip(piX, x))
                for z0 in range(-P, P):
                    for zs in itertools.combinations(range(1, P - 2), 5):
                        tz = dict(zip(piZ, (z0,) + tuple(z0 + v for v in zs)))
                        g = legal(tx, tz, P)
                        if g is not None and norm(g) == norm(g0):
                            n += 1
                            sp = max(x[-1], zs[-1])
                            minspan = sp if minspan is None else min(minspan, sp)
            res[f"P{P}"] = {"realisations": n, "min_max_span": minspan}
        out[name] = res
        print(name, json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
