"""E-006: per-w table for gross fixed-weight files (Relay5 vs MLE, four-way classification of Relay5 failures).
Classes per failing sector of a Relay5-failing sample (MLE run on all Relay5 failures):
  nonconv  : Relay5 did not converge (output does not satisfy the syndrome)
  mle_fail : Relay5 converged, MLE also fails
  tie      : Relay5 converged to a wrong-class solution with the same likelihood weight as the MLE solution (|dW|<1e-6)
  heavier  : Relay5 converged to a wrong-class solution strictly heavier than the MLE solution, MLE succeeds
f_w^mle (HT): MLE failures on Relay5-failing samples (weight 1) + subsample of the rest (weight 1/sub).
uv run python -m search.decoders.gross_fw_table [tag]"""
import glob, json, sys, collections
import numpy as np
from search.decoders.common import RESULTS
tag = sys.argv[1] if len(sys.argv) > 1 else "gross_p0.001"
agg = collections.defaultdict(lambda: collections.Counter())
for f in sorted(glob.glob(str(RESULTS / "fixedweight" / tag / "w*_b*.npz"))):
    d = dict(np.load(f)); w = int(d["w"]); sub = float(d["sub"])
    A = agg[w]; n = len(d["insub"]); A["n"] += n; A["cpu"] += float(d["cpu"])
    fr = d["Z_relay5_fail"] | d["X_relay5_fail"]
    rf = d["Z_ref_fail"] | d["X_ref_fail"]
    A["relay_fail"] += int(fr.sum())
    A["mle_fail_HT"] += float(rf[fr].sum()) + float(rf[~fr & d["ref_done"]].sum()) / max(sub, 1e-12)
    A["mle_fail_on_relay_fail"] += int((rf & fr).sum())
    A["mle_fail_in_sub"] += int((rf & ~fr & d["ref_done"]).sum()); A["sub_size"] += int((~fr & d["ref_done"]).sum())
    A["timeouts"] += int(((d["Z_ref_status"] == 2) | (d["X_ref_status"] == 2)).sum())
    if "Z_relay5_conv" in d:
        for s in "ZX":
            F = d[f"{s}_relay5_fail"]
            if not F.any():
                continue
            conv = d[f"{s}_relay5_conv"]; mf = d[f"{s}_ref_fail"]
            dW = d[f"{s}_relay5_W"] - d[f"{s}_ref_W"]
            A["sec_fail"] += int(F.sum())
            A["nonconv"] += int((F & ~conv).sum())
            A["mle_fail"] += int((F & conv & mf).sum())
            A["tie"] += int((F & conv & ~mf & (np.abs(dW) < 1e-6)).sum())
            A["heavier"] += int((F & conv & ~mf & (dW >= 1e-6)).sum())
out = {}
print("w n relay_fail f_relay mle_HT f_mle ratio | sector: fail nonconv mle_fail tie heavier | sub mle_in_sub/size timeouts cpu")
for w in sorted(agg):
    A = agg[w]; n = A["n"]
    r = A["relay_fail"] / A["mle_fail_HT"] if A["mle_fail_HT"] else None
    out[w] = dict(A); out[w]["ratio"] = r
    print(w, n, A["relay_fail"], round(A["relay_fail"] / n, 5), round(A["mle_fail_HT"], 1), round(A["mle_fail_HT"] / n, 5),
          None if r is None else round(r, 2), "|", A["sec_fail"], A["nonconv"], A["mle_fail"], A["tie"], A["heavier"], "|",
          f'{A["mle_fail_in_sub"]}/{A["sub_size"]}', A["timeouts"], round(A["cpu"]))
(RESULTS / "fixedweight" / f"{tag}_table.json").write_text(json.dumps(out, indent=1))
