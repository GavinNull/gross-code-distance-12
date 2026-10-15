"""Auditor's proof re-checks (own driver, not code/proofs/certify.py).

    python proofs.py shipped NAME            # shipped .drat.xz: sha256 (CNF, DRAT, .xz vs MANIFEST), drat-trim, cake_lpr
    python proofs.py regen NAME              # unshipped: CaDiCaL re-solve, sha256 vs record, drat-trim, cake_lpr
    python proofs.py cnf PATH.cnf NAME REC.jsonl   # lift batch CNF already on disk (batch_struct.py --keep)
    python proofs.py tamper NAME             # tamper suite on one shipped proof
drat-trim is run WITHOUT -w (warnings visible) and writes the LRAT core that cake_lpr then checks.
Work files go to $AUDIT_TMP (scratch) and are deleted.  One JSON line per call on stdout.
"""
import gzip
import hashlib
import json
import lzma
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "release/zenodo"
PROOFS = PKG / "certificates/proofs"
CAD = str(ROOT / "tools/cadical/build/cadical")
DT = str(ROOT / "tools/drat-trim/drat-trim")
CAKE = str(ROOT / "tools/cake_lpr/cake_lpr")
TMP = Path(os.environ.get("AUDIT_TMP", "/private/tmp/e027audit"))
TMP.mkdir(parents=True, exist_ok=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, log):
    t = time.time()
    with open(log, "wb") as fo:
        p = subprocess.Popen(cmd, stdout=fo, stderr=subprocess.STDOUT)
        _, status, ru = os.wait4(p.pid, 0)
    return os.waitstatus_to_exitcode(status), Path(log).read_text(errors="replace"), round(time.time() - t, 1), \
        round(ru.ru_utime + ru.ru_stime, 1)


def drat_trim(cnf, drat, tag, lrat=True):
    lr = TMP / f"{tag}.lrat"
    cmd = [DT, str(cnf), str(drat), "-t", "20000"] + (["-L", str(lr)] if lrat else [])
    code, txt, wall, cpu = run(cmd, TMP / f"{tag}.dt.log")
    lines = [l for l in txt.splitlines() if l.startswith("s ")]
    warn = sum("WARNING" in l for l in txt.splitlines())
    return dict(verdict=lines[-1] if lines else f"none(exit {code})", warnings=warn, cpu=cpu), lr


def cake(cnf, lrat, tag):
    code, txt, wall, cpu = run([CAKE, str(cnf), str(lrat)], TMP / f"{tag}.cake.log")
    lines = [l for l in txt.splitlines() if l.startswith("s ")]
    return dict(verdict=lines[-1] if lines else f"none(exit {code}): {txt.strip()[:120]}", cpu=cpu)


def records():
    return {json.loads(l)["name"]: json.loads(l) for l in open(PROOFS / "certificates_proofs.jsonl")}


def manifest():
    m = {}
    for l in open(PKG / "MANIFEST.sha256"):
        h, p = l.split(None, 1)
        m[p.strip().lstrip("./").lstrip("*")] = h
    return m


def unpack_cnf(r, tag):
    cnf = TMP / f"{tag}.cnf"
    with gzip.open(PKG / r["cnf"], "rb") as fi, open(cnf, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    return cnf


def check_pair(cnf, drat, tag, out):
    dt, lr = drat_trim(cnf, drat, tag)
    out["drat_trim"] = dt
    if dt["verdict"] == "s VERIFIED" and lr.exists():
        out["lrat_sha256_match"] = None
        out["lrat_sha"] = sha(lr)
        out["cake_lpr"] = cake(cnf, lr, tag)
    for p in (lr,):
        if p.exists():
            p.unlink()


def shipped(name):
    r = records()[name]
    tag = name
    out = dict(mode="shipped", name=name)
    xz = PROOFS / "drat" / f"{name}.drat.xz"
    mf = manifest()
    key = f"certificates/proofs/drat/{name}.drat.xz"
    out["xz_manifest_match"] = mf.get(key) == sha(xz) if key in mf else "not in manifest"
    cnf = unpack_cnf(r, tag)
    drat = TMP / f"{tag}.drat"
    with lzma.open(xz, "rb") as fi, open(drat, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    out["cnf_sha_match"] = sha(cnf) == r["cnf_sha256"]
    out["drat_sha_match"] = sha(drat) == r["drat_sha256"]
    check_pair(cnf, drat, tag, out)
    out["lrat_sha_eq_record"] = out.get("lrat_sha") == r.get("lrat_sha256")
    out.pop("lrat_sha", None); out.pop("lrat_sha256_match", None)
    cnf.unlink(); drat.unlink()
    return out


def regen_file(cnf, name, rec):
    tag = name
    out = dict(name=name, cnf_sha_match=sha(cnf) == rec["cnf_sha256"])
    drat = TMP / f"{tag}.drat"
    code, txt, wall, cpu = run([CAD, "-q", "--binary=true", str(cnf), str(drat)], TMP / f"{tag}.cad.log")
    out["cadical"] = dict(exit=code, cpu=cpu)
    if code == 20:
        out["drat_bytes"] = drat.stat().st_size
        out["drat_sha_match"] = sha(drat) == rec["drat_sha256"]
        check_pair(cnf, drat, tag, out)
        out["lrat_sha_eq_record"] = out.get("lrat_sha") == rec.get("lrat_sha256")
        out.pop("lrat_sha", None); out.pop("lrat_sha256_match", None)
    if drat.exists():
        drat.unlink()
    return out


def regen(name):
    r = records()[name]
    cnf = unpack_cnf(r, name)
    out = regen_file(cnf, name, r)
    out["mode"] = "regen"
    cnf.unlink()
    return out


def tamper(name):
    """tamper suite on a shipped proof: each variant must NOT verify (except where noted)."""
    r = records()[name]
    cnf = unpack_cnf(r, name)
    drat = TMP / f"{name}.drat"
    with lzma.open(PROOFS / "drat" / f"{name}.drat.xz", "rb") as fi, open(drat, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    res = {}
    # 0. baseline, also writes the LRAT
    dt, lr = drat_trim(cnf, drat, name + "_base")
    res["baseline"] = dt["verdict"]
    lrat_lines = lr.read_text().splitlines()
    clauses = [l for l in cnf.read_text().splitlines() if l and l[0] not in "cp"]
    header = [l for l in cnf.read_text().splitlines() if l.startswith("p ")][0]
    # core clause ids used as hints in the LRAT
    used = set()
    for l in lrat_lines:
        t = l.split()
        if len(t) > 1 and t[1] == "d":
            continue
        z = t.index("0") if "0" in t else len(t)
        hints = t[z + 1:-1] if t and t[-1] == "0" else t[z + 1:]
        used |= {abs(int(h)) for h in hints if h.lstrip("-").isdigit()}
    core = sorted(i for i in used if 1 <= i <= len(clauses))
    rng = random.Random(7)
    # 1. truncated DRAT (first 60 % of bytes)
    b = drat.read_bytes()
    t1 = TMP / f"{name}_trunc.drat"; t1.write_bytes(b[: int(len(b) * 0.6)])
    res["drat_truncated_60pct"] = drat_trim(cnf, t1, name + "_t1", lrat=False)[0]["verdict"]; t1.unlink()
    # 2. CNF with one core clause removed (header adjusted) -> the proof must fail (formula may still be UNSAT)
    k = rng.choice(core)
    c2 = TMP / f"{name}_drop.cnf"
    p = header.split()
    c2.write_text(f"p cnf {p[2]} {int(p[3]) - 1}\n" + "\n".join(c for i, c in enumerate(clauses, 1) if i != k) + "\n")
    res["cnf_core_clause_removed"] = drat_trim(c2, drat, name + "_t2", lrat=False)[0]["verdict"]
    res["cnf_core_clause_removed_cake_with_old_lrat"] = cake(c2, lr, name + "_t2c")["verdict"]
    c2.unlink()
    # 3. CNF with one core clause weakened by an extra fresh literal
    c3 = TMP / f"{name}_weak.cnf"
    nv = int(p[2]) + 1
    c3.write_text(f"p cnf {nv} {p[3]}\n" + "\n".join((c[:-1] + f"{nv} 0") if i == k else c
                                                    for i, c in enumerate(clauses, 1)) + "\n")
    res["cnf_core_clause_weakened"] = drat_trim(c3, drat, name + "_t3", lrat=False)[0]["verdict"]
    res["cnf_core_clause_weakened_cake"] = cake(c3, lr, name + "_t3c")["verdict"]
    c3.unlink()
    # 4. LRAT with one hint of a middle step altered
    steps = [i for i, l in enumerate(lrat_lines) if len(l.split()) > 1 and l.split()[1] != "d"]
    j = steps[len(steps) // 2]
    t = lrat_lines[j].split()
    z = t.index("0")
    t[z + 1] = str(int(t[z + 1]) % max(1, len(clauses)) + 1) if t[z + 1] != "0" else t[z + 1]
    l4 = TMP / f"{name}_bad.lrat"
    l4.write_text("\n".join(lrat_lines[:j] + [" ".join(t)] + lrat_lines[j + 1:]) + "\n")
    res["lrat_hint_altered_cake"] = cake(cnf, l4, name + "_t4")["verdict"]
    l4.unlink()
    # 5. LRAT whose final empty clause step is removed
    l5 = TMP / f"{name}_noempty.lrat"
    keep = [l for l in lrat_lines if not (len(l.split()) > 1 and l.split()[1] == "0")]
    l5.write_text("\n".join(keep) + "\n")
    res["lrat_without_empty_clause_cake"] = cake(cnf, l5, name + "_t5")["verdict"]
    l5.unlink()
    res["core_clauses"] = len(core)
    lr.unlink(); cnf.unlink(); drat.unlink()
    return dict(mode="tamper", name=name, results=res)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "shipped":
        o = shipped(a[1])
    elif a[0] == "regen":
        o = regen(a[1])
    elif a[0] == "tamper":
        o = tamper(a[1])
    elif a[0] == "cnf":
        rec = {json.loads(l)["name"]: json.loads(l) for l in open(a[3])}[a[2]]
        o = regen_file(Path(a[1]), a[2], rec)
        o["mode"] = "lift-batch"
    print(json.dumps(o), flush=True)
