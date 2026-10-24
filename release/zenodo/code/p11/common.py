"""Circuit registry, codes, extended codes, lists of extended logicals and translation groups for the period-11
circuits and their relatives (gross code: u11 and two controls; [[90,8,10]]: c11, c12, c13, c16, u16, s16).

Conventions are those of code/gross12/ext.py: the Z-basis memory sees X errors, uses H = HZ, L = LZ and the
residuals (proper suffixes) of the X-check CNOT orders; the X basis is the mirror image.  A column of the extended
code is a nonzero pair (H s, L s) for s a single data qubit or a proper suffix of a check order; equal pairs are
merged.  Column order in the data files: data qubits first, then for every check in row order its suffixes of
length 5, 4, 3, 2, 1, keeping the first occurrence of each (H s, L s).

family "gross": data/extended_code/u11_extended_code_{Z,X}_memory.json (360 columns, 5 orbits of the 72
    translations), lists data/logicals/u11_weight{10,11}_logicals_{Z,X}_memory.json (144 and 7344), d_ext = 10.
family "bb90":  data/extended_code/bb90_extended_code_{Z,X}_memory.json (225 columns, 5 orbits of the 45
    translations), lists data/logicals/bb90_weight{8,9}_logicals_{Z,X}_memory.json (585 and 16830), d_ext = 8.
Every circuit of a family has exactly the column set of its family's data file (checked by check_circuits.py and
asserted by lift.py); the column ORDER of a circuit's own construction may differ (it depends on its orders).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gross12.code import load_code as load_gross            # noqa: E402
from gross12.ext import ext_columns, hl, key_of             # noqa: E402,F401  (re-exported)
from gross12.paths import CIRCUITS, DATA, WITNESSES         # noqa: E402,F401
from gross12.schedule import load_schedule                  # noqa: E402

EXT = DATA / "extended_code"
LOGICALS = DATA / "logicals"

CIRCUITS_P11 = {
    "u11": ("gross", "u11.json"),
    "u11_control_p10": ("gross", "u11_control_p10.json"),
    "u11_control_segmented": ("gross", "u11_control_segmented.json"),
    "c11": ("bb90", "bb90_c11.json"),
    "c12": ("bb90", "bb90_c12.json"),
    "c13": ("bb90", "bb90_c13.json"),
    "c16": ("bb90", "bb90_c16.json"),
    "u16": ("bb90", "bb90_u16.json"),
    "s16": ("bb90", "bb90_s16.json"),
}
FAMILY = {
    "gross": dict(dext=10, l=12, m=6, ext="u11_extended_code_{b}_memory.json",
                  lists="u11_weight{w}_logicals_{b}_memory.json", counts={10: 144, 11: 7344}, n_group=72),
    "bb90": dict(dext=8, l=15, m=3, ext="bb90_extended_code_{b}_memory.json",
                 lists="bb90_weight{w}_logicals_{b}_memory.json", counts={8: 585, 9: 16830}, n_group=45),
}


def family_of(name: str) -> str:
    return CIRCUITS_P11[name][0]


def circuit(name: str):
    return load_schedule(CIRCUITS / CIRCUITS_P11[name][1])


def load_code(family: str):
    if family == "gross":
        return load_gross()
    from bb90 import bbcode
    return bbcode.load_code()


def translation(family: str, a: int, b: int) -> list[int]:
    """translation by x^a y^b on the data qubits (both blocks); its first half is also the map of check indices."""
    f = FAMILY[family]
    l, m = f["l"], f["m"]
    p = [((i // m + a) % l) * m + (i % m + b) % m for i in range(l * m)]
    return p + [x + l * m for x in p]


def order_group(spec, family: str) -> list[tuple[int, int]]:
    """translations that map the CNOT order of every check to the order of its image check (both check types)."""
    f = FAMILY[family]
    xo, zo = spec.orders()
    G = []
    for a in range(f["l"]):
        for b in range(f["m"]):
            pq = translation(family, a, b)
            half = f["l"] * f["m"]
            if all(tuple(pq[q] for q in ords[i]) == tuple(ords[pq[i]]) for ords in (xo, zo) for i in range(half)):
                G.append((a, b))
    return G


def load_ext(family: str, basis: str) -> dict:
    return json.load(open(EXT / FAMILY[family]["ext"].format(b=basis)))


def ext_keys_from_file(code, family: str, basis: str) -> list[bytes]:
    d = load_ext(family, basis)
    H, L = hl(code, basis)
    out = []
    for c in d["columns"]:
        h = np.zeros(H.shape[0], np.uint8); h[c["H"]] = 1
        lv = np.zeros(L.shape[0], np.uint8); lv[c["L"]] = 1
        assert key_of(code, basis, c["support"]) == h.tobytes() + lv.tobytes(), c
        out.append(h.tobytes() + lv.tobytes())
    return out


def load_list(family: str, w: int, basis: str) -> list[list[int]]:
    d = json.load(open(LOGICALS / FAMILY[family]["lists"].format(w=w, b=basis)))
    assert d["count"] == len(d["logicals"]) == FAMILY[family]["counts"][w]
    return [e["columns"] for e in d["logicals"]]


def key_matrices(keys, nH):
    Hm = np.array([np.frombuffer(k[:nH], np.uint8) for k in keys]).T
    Lm = np.array([np.frombuffer(k[nH:], np.uint8) for k in keys]).T
    return Hm, Lm
