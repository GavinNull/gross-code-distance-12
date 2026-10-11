"""E-024a: translate a core (rec indices of a source family's prepare_full list) into the rec indices of a target
family (e.g. per-check free): all G24-translates of the core logicals (by their extended-code column sets).

    PYTHONPATH=.:tests uv run python -m search.experiments.e024a.core_lift core.json "1,2;0,3" "" out.json [split_units]
"""
import json
import sys

import search.experiments.e021.nwfull as NF
from search.experiments.e021.extgen import ext_general
from search.experiments.e021.mono import fig12_labels
from search.experiments.e021.nwsat import Family, parse_sub


def fam(sub, split=""):
    gens = parse_sub(sub) if sub else [(0, 0)]
    if split:
        from search.experiments.e024a.mixed import MixedFamily
        return MixedFamily(gens, {(x[0], int(x[1:])) for x in split.split(",")})
    return Family(gens)


def main():
    core = json.load(open(sys.argv[1]))["core"]
    src, dst, out = sys.argv[2], sys.argv[3], sys.argv[4]
    split = sys.argv[5] if len(sys.argv) > 5 else ""
    Fs, Fd = fam(src), fam(dst, split)
    rs, _ = NF.prepare_full(Fs, "XZ")
    rd, _ = NF.prepare_full(Fd, "XZ")
    f12 = fig12_labels()
    orbit = set()
    for kind in "XZ":
        E = ext_general(kind, f12[kind])
        for k in core:
            r = rs[k]
            if r["kind"] != kind:
                continue
            for P in E["perms"]:
                orbit.add((kind, tuple(sorted(int(P[j]) for j in r["S"]))))
    sel = [i for i, r in enumerate(rd) if (r["kind"], tuple(sorted(r["S"]))) in orbit]
    print(f"core {len(core)} reps -> {len(orbit)} logicals in G24 orbits -> {len(sel)} modelled recs in target family")
    json.dump(sel, open(out, "w"))


if __name__ == "__main__":
    main()
