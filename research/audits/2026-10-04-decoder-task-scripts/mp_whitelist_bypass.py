"""mp_rule 白名单新 bypass 尝试（全部应被 validate_rules 拒绝）。PYTHONPATH=<repo> uv run python ..."""
from evaluators.decoder_mp import validate_rules, RuleError
SCHED='SCHEDULE={"first_iters":80,"leg_iters":60,"max_legs":8,"gamma0":0.125,"gamma_low":-0.24,"gamma_high":0.66,"stop_solutions":5,"reset_messages":True}\n'
V='def var_rule(prior,inc,gamma,prev):\n return prior,inc\n'
tests={
 "axis0_sum":'def check_rule(m,sgn):\n return np.sum(m,axis=0,keepdims=True)\n'+V,
 "cumsum_no_axis":'def check_rule(m,sgn):\n return np.cumsum(m)\n'+V,
 "take_along_axis0":'def check_rule(m,sgn):\n return np.take_along_axis(m,m,axis=0)\n'+V,
 "subscript":'def check_rule(m,sgn):\n x=m[0]\n return x\n'+V,
 "attr_escape":'def check_rule(m,sgn):\n return m.T\n'+V,
 "rebind_np":'def check_rule(m,sgn):\n np=1\n return m\n'+V,
 "for_loop":'def check_rule(m,sgn):\n for i in m:\n  pass\n return m\n'+V,
 "lambda":'def check_rule(m,sgn):\n f=lambda x:x\n return f(m)\n'+V,
 "str_const":'def check_rule(m,sgn):\n return np.where(m=="a",m,m)\n'+V,
 "walrus":'def check_rule(m,sgn):\n return (x:=m)\n'+V,
 "rowkth_var_k":'def check_rule(m,sgn):\n k=np.sum(m,axis=1,keepdims=True)\n return np.rowkth(m,k)\n'+V,
 "full_like_var":'def check_rule(m,sgn):\n c=np.sum(m,axis=1,keepdims=True)\n return np.full_like(m,c)\n'+V,
}
bad=0
for n,b in tests.items():
    try: validate_rules(SCHED+b,max_legs=64); print(f"[ACCEPT-BUG] {n}"); bad+=1
    except RuleError as e: print(f"[reject] {n}: {str(e)[:70]}")
print("bypasses accepted:",bad,"(expect 0)")
