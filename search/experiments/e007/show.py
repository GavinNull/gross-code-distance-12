import json, sys
for l in open(sys.argv[1]):
    r = json.loads(l); m = r["metrics"]; sp = m.get("speed") or {}; c = m.get("counts") or {}
    ctx = r.get("context", {})
    src = r.get("src", "")
    print(r["eval_index"], "valid" if r["valid"] else "INVALID", "score=%.5f" % r["score"] if r["valid"] else "", c.get("fail_any"),
          "ratio=%s" % (sp.get("ratio_to_reference") or sp.get("ratio_to_paper_params")), "t=%.0fs" % r["timing"]["eval_s"], "ref=", (m.get("reference_counts") or {}).get("fail_any"))
