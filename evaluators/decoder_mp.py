"""mp_rule 解码器任务：候选只提供消息传递的**局部**更新规则，评估器的引擎执行迭代并强制迭代上限（H-005）。

候选源码只能包含（AST 白名单，`validate_rules`）：

    import numpy as np                       # 可选
    SCHEDULE = {"first_iters": 80, "leg_iters": 60, "max_legs": 8, "gamma0": 0.125,
                "gamma_low": -0.24, "gamma_high": 0.66, "stop_solutions": 5, "reset_messages": True}

    def check_rule(m, sgn):
        # m:   (C, D) 每个校验收到的“变量→校验”消息（LLR，按行对齐；不足 D 的位置填 +1e30，可安全参与 min / 符号）
        # sgn: (C, 1) 校验的 syndrome 符号（+1 = 没触发，-1 = 触发）
        return out                           # (C, D) “校验→变量”消息（填充位置的值被忽略）

    def var_rule(prior, inc, gamma, prev):
        # prior: (V, 1) 先验 LLR log((1-p)/p)；inc: (V, D') 收到的“校验→变量”消息（填充位置为 0）
        # gamma: (V, 1) 本段的记忆强度；prev: (V, 1) 上一次迭代的边际（段首 = 上一段最后的边际，第 0 段 = prior）
        return marg, out                     # marg (V, 1) 边际 LLR（<0 判为 1），out (V, D') “变量→校验”消息

规则函数体只允许：给局部名字赋值、return；表达式只允许数字常量、参数 / 局部名字、+ - * / ** 与比较、以及
`np.<白名单函数>(...)`：逐元素函数（abs、sign、minimum、maximum、where(c,a,b)、exp、log、log1p、expm1、tanh、arctanh、
sqrt、square、clip(x,lo,hi)、logaddexp、floor、ceil、zeros_like、ones_like、full_like(x, 常量)）与**按行**归约
（sum / min / max / prod / mean 必须写 axis=1, keepdims=True；sort / cumsum / cumprod 必须写 axis=1；
argmin / argmax 必须写 axis=1, keepdims=True；take_along_axis(x, idx, axis=1)；rowkth(x, k) = 每行第 k 小（k 为
整数常量），形状 (行, 1)）。没有下标、属性（除 np.X）、循环、函数定义、lambda、字符串、import 其他模块。
所以每个输出行只依赖同一行的输入（局部性由构造保证），规则也碰不到全局状态、文件或其他 shot。

引擎（评估器代码，在沙箱里运行）：对每个 shot 按段执行。第 0 段 γ=gamma0（所有变量相同）、first_iters 次迭代；之后每段
γ_j ~ U[gamma_low, gamma_high]（每个变量独立，引擎的 RNG，种子由 shot 的 syndrome 派生）、leg_iters 次迭代；每次迭代
check_rule → var_rule → 硬判决，满足 Hx = s 即得到一个解并结束本段；找到 stop_solutions 个解、或段数达到 max_legs、或
**总迭代次数达到任务的 max_total_iters** 时停止，返回权重（Σ 先验 LLR）最小的解；一个解都没有时返回最后一次硬判决。
迭代上限由引擎强制，候选无法改变。参考 = 同一引擎跑 Relay-BP 规则（`relay_rule_program`）。
"""
from __future__ import annotations

import ast
import json

__all__ = ["RuleError", "validate_rules", "wrap_rules", "relay_rule_program", "ELEMENTWISE", "ROWWISE"]

ELEMENTWISE = {"abs", "sign", "minimum", "maximum", "where", "exp", "log", "log1p", "expm1", "tanh", "arctanh",
               "sqrt", "square", "clip", "logaddexp", "floor", "ceil", "zeros_like", "ones_like", "full_like"}
REDUCE_KEEP = {"sum", "min", "max", "prod", "mean", "argmin", "argmax"}      # axis=1, keepdims=True
ROW_SAME = {"sort", "cumsum", "cumprod"}                                      # axis=1
ROWWISE = REDUCE_KEEP | ROW_SAME | {"take_along_axis", "rowkth"}
_ARITY = {"where": 3, "clip": 3, "full_like": 2, "minimum": 2, "maximum": 2, "logaddexp": 2, "take_along_axis": 2,
          "rowkth": 2}
SCHEDULE_KEYS = {"first_iters": int, "leg_iters": int, "max_legs": int, "gamma0": float, "gamma_low": float,
                 "gamma_high": float, "stop_solutions": int, "reset_messages": bool}
_FUNCS = {"check_rule": ["m", "sgn"], "var_rule": ["prior", "inc", "gamma", "prev"]}


class RuleError(ValueError):
    pass


def _num(node) -> bool:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float, bool):
        return True
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and _num(node.operand)


def _const_value(node):
    if isinstance(node, ast.Constant):
        return node.value
    v = _const_value(node.operand)
    return -v if isinstance(node.op, ast.USub) else v


def _check_expr(node, names: set, where: str) -> None:
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float, bool):
            raise RuleError(f"{where}: only numeric constants are allowed (got {node.value!r})")
        return
    if isinstance(node, ast.Name):
        if not isinstance(node.ctx, ast.Load) or node.id not in names:
            raise RuleError(f"{where}: name {node.id!r} is not a parameter or an assigned local")
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise RuleError(f"{where}: operator {type(node.op).__name__} is not allowed")
        _check_expr(node.left, names, where)
        _check_expr(node.right, names, where)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.USub, ast.UAdd)):
            raise RuleError(f"{where}: unary {type(node.op).__name__} is not allowed")
        _check_expr(node.operand, names, where)
        return
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or not isinstance(node.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)):
            raise RuleError(f"{where}: only single comparisons (<, <=, >, >=, ==, !=) are allowed")
        _check_expr(node.left, names, where)
        _check_expr(node.comparators[0], names, where)
        return
    if isinstance(node, ast.Call):
        f = node.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "np"):
            raise RuleError(f"{where}: only np.<function>(...) calls are allowed")
        fn = f.attr
        if fn not in ELEMENTWISE and fn not in ROWWISE:
            raise RuleError(f"{where}: np.{fn} is not in the whitelist")
        for a in node.args:
            if isinstance(a, ast.Starred):
                raise RuleError(f"{where}: *args are not allowed")
            _check_expr(a, names, where)
        kw = {k.arg: k.value for k in node.keywords}
        if None in kw:
            raise RuleError(f"{where}: **kwargs are not allowed")
        if fn in _ARITY and len(node.args) != _ARITY[fn]:
            raise RuleError(f"{where}: np.{fn} takes exactly {_ARITY[fn]} positional arguments")
        if fn in ELEMENTWISE:
            if kw:
                raise RuleError(f"{where}: np.{fn} takes no keyword arguments")
            if fn not in _ARITY and len(node.args) != 1:
                raise RuleError(f"{where}: np.{fn} takes exactly 1 positional argument")
            if fn == "full_like" and not _num(node.args[1]):
                raise RuleError(f"{where}: np.full_like(x, c) needs a numeric constant c")
            return
        if fn == "rowkth":
            if kw or not (isinstance(node.args[1], ast.Constant) and type(node.args[1].value) is int):
                raise RuleError(f"{where}: np.rowkth(x, k) needs an integer constant k and no keywords")
            return
        want = {"axis"} | ({"keepdims"} if fn in REDUCE_KEEP else set())
        if set(kw) != want:
            raise RuleError(f"{where}: np.{fn} must be called with exactly the keywords {sorted(want)} "
                            f"(axis=1{', keepdims=True' if fn in REDUCE_KEEP else ''})")
        if not (isinstance(kw["axis"], ast.Constant) and kw["axis"].value == 1 and type(kw["axis"].value) is int):
            raise RuleError(f"{where}: np.{fn} must use axis=1 (row-wise)")
        if "keepdims" in kw and not (isinstance(kw["keepdims"], ast.Constant) and kw["keepdims"].value is True):
            raise RuleError(f"{where}: np.{fn} must use keepdims=True")
        if fn != "take_along_axis" and len(node.args) != 1:
            raise RuleError(f"{where}: np.{fn} takes exactly 1 positional argument")
        return
    raise RuleError(f"{where}: {type(node).__name__} is not allowed in rules")


def _check_function(fd: ast.FunctionDef) -> None:
    want = _FUNCS[fd.name]
    a = fd.args
    if (a.posonlyargs or a.vararg or a.kwonlyargs or a.kwarg or a.defaults or a.kw_defaults
            or [x.arg for x in a.args] != want or fd.decorator_list or fd.returns
            or any(x.annotation for x in a.args)):
        raise RuleError(f"{fd.name} must be defined exactly as def {fd.name}({', '.join(want)}): (no defaults, "
                        f"annotations or decorators)")
    names = set(want)
    returned = False
    for i, st in enumerate(fd.body):
        where = f"{fd.name} line {getattr(st, 'lineno', '?')}"
        if returned:
            raise RuleError(f"{where}: statements after return")
        if i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        if isinstance(st, ast.Assign):
            if len(st.targets) != 1:
                raise RuleError(f"{where}: chained assignment is not allowed")
            _check_expr(st.value, names, where)
            t = st.targets[0]
            tg = t.elts if isinstance(t, ast.Tuple) else [t]
            if isinstance(t, ast.Tuple) and not isinstance(st.value, ast.Tuple):
                raise RuleError(f"{where}: tuple assignment needs a tuple on the right")
            if isinstance(t, ast.Tuple):
                if len(t.elts) != len(st.value.elts):
                    raise RuleError(f"{where}: tuple sizes differ")
                for e in st.value.elts:
                    _check_expr(e, names, where)
            for x in tg:
                if not isinstance(x, ast.Name):
                    raise RuleError(f"{where}: can only assign to plain local names")
                if x.id in ("np",):
                    raise RuleError(f"{where}: cannot rebind np")
                names.add(x.id)
            continue
        if isinstance(st, ast.AugAssign):
            if not isinstance(st.target, ast.Name) or st.target.id not in names or \
                    not isinstance(st.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                raise RuleError(f"{where}: augmented assignment only to existing locals with + - * /")
            _check_expr(st.value, names, where)
            continue
        if isinstance(st, ast.Return):
            if st.value is None:
                raise RuleError(f"{where}: return a value")
            vals = st.value.elts if isinstance(st.value, ast.Tuple) else [st.value]
            if len(vals) != (2 if fd.name == "var_rule" else 1):
                raise RuleError(f"{where}: {fd.name} must return "
                                f"{'(marg, out)' if fd.name == 'var_rule' else 'out'}")
            for v in vals:
                _check_expr(v, names, where)
            returned = True
            continue
        raise RuleError(f"{where}: {type(st).__name__} statements are not allowed")
    if not returned:
        raise RuleError(f"{fd.name} has no return statement")


def validate_rules(src: str, *, max_legs: int = 64) -> dict:
    """校验规则源码；返回规范化的 SCHEDULE。不合法抛 RuleError（信息可直接给 LLM）。"""
    if not isinstance(src, str) or len(src) > 50_000:
        raise RuleError("rules must be a string of at most 50000 characters")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise RuleError(f"syntax error: {e}") from e
    sched = None
    seen = set()
    for i, st in enumerate(tree.body):
        if i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        if isinstance(st, ast.Import):
            if [(a.name, a.asname) for a in st.names] != [("numpy", "np")]:
                raise RuleError("the only allowed import is `import numpy as np`")
            continue
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                and st.targets[0].id == "SCHEDULE":
            if sched is not None:
                raise RuleError("SCHEDULE defined twice")
            if not isinstance(st.value, ast.Dict):
                raise RuleError("SCHEDULE must be a dict literal")
            sched = {}
            for k, v in zip(st.value.keys, st.value.values):
                if not (isinstance(k, ast.Constant) and k.value in SCHEDULE_KEYS):
                    raise RuleError(f"SCHEDULE keys must be among {sorted(SCHEDULE_KEYS)}")
                if not _num(v):
                    raise RuleError(f"SCHEDULE[{k.value!r}] must be a numeric / boolean constant")
                sched[k.value] = _const_value(v)
            continue
        if isinstance(st, ast.FunctionDef) and st.name in _FUNCS:
            if st.name in seen:
                raise RuleError(f"{st.name} defined twice")
            seen.add(st.name)
            _check_function(st)
            continue
        raise RuleError(f"line {getattr(st, 'lineno', '?')}: only `import numpy as np`, SCHEDULE = {{...}} and the "
                        f"functions check_rule / var_rule are allowed at module level")
    if seen != set(_FUNCS):
        raise RuleError(f"define both check_rule(m, sgn) and var_rule(prior, inc, gamma, prev); missing "
                        f"{sorted(set(_FUNCS) - seen)}")
    if sched is None:
        raise RuleError("define SCHEDULE = {...}")
    out = {}
    for k, typ in SCHEDULE_KEYS.items():
        if k not in sched:
            raise RuleError(f"SCHEDULE is missing {k!r}")
        v = sched[k]
        if typ is bool:
            if type(v) is not bool:
                raise RuleError(f"SCHEDULE[{k!r}] must be True or False")
        elif typ is int:
            if type(v) is not int:
                raise RuleError(f"SCHEDULE[{k!r}] must be an integer")
        else:
            if type(v) not in (int, float):
                raise RuleError(f"SCHEDULE[{k!r}] must be a number")
            v = float(v)
        out[k] = v
    if not (1 <= out["first_iters"] <= 10_000 and 1 <= out["leg_iters"] <= 10_000):
        raise RuleError("first_iters and leg_iters must be in 1..10000")
    if not 1 <= out["max_legs"] <= max_legs:
        raise RuleError(f"max_legs must be in 1..{max_legs}")
    if not 1 <= out["stop_solutions"] <= 64:
        raise RuleError("stop_solutions must be in 1..64")
    for k in ("gamma0", "gamma_low", "gamma_high"):
        if not -4.0 <= out[k] <= 4.0:
            raise RuleError(f"{k} must be in [-4, 4]")
    if out["gamma_low"] > out["gamma_high"]:
        raise RuleError("gamma_low must be <= gamma_high")
    return out


# ---------------------------------------------------------------------------
# 引擎（作为程序源码在沙箱里运行）
# ---------------------------------------------------------------------------

ENGINE_TEMPLATE = r'''
import numpy as _np
import zlib as _zlib

RULES_SRC = __RULES__
SCHEDULE = __SCHEDULE__
MAX_TOTAL_ITERS = __MAXIT__
_BIG = 1e30


class _NP:
    """规则能看到的 np：只有白名单函数；按行函数强制 axis=1。"""
    abs = staticmethod(_np.abs); sign = staticmethod(_np.sign); minimum = staticmethod(_np.minimum)
    maximum = staticmethod(_np.maximum); where = staticmethod(_np.where); exp = staticmethod(_np.exp)
    log = staticmethod(_np.log); log1p = staticmethod(_np.log1p); expm1 = staticmethod(_np.expm1)
    tanh = staticmethod(_np.tanh); arctanh = staticmethod(_np.arctanh); sqrt = staticmethod(_np.sqrt)
    square = staticmethod(_np.square); clip = staticmethod(_np.clip); logaddexp = staticmethod(_np.logaddexp)
    floor = staticmethod(_np.floor); ceil = staticmethod(_np.ceil); zeros_like = staticmethod(_np.zeros_like)
    ones_like = staticmethod(_np.ones_like); full_like = staticmethod(_np.full_like)
    sum = staticmethod(lambda x, axis, keepdims: _np.sum(x, axis=1, keepdims=True))
    min = staticmethod(lambda x, axis, keepdims: _np.min(x, axis=1, keepdims=True))
    max = staticmethod(lambda x, axis, keepdims: _np.max(x, axis=1, keepdims=True))
    prod = staticmethod(lambda x, axis, keepdims: _np.prod(x, axis=1, keepdims=True))
    mean = staticmethod(lambda x, axis, keepdims: _np.mean(x, axis=1, keepdims=True))
    argmin = staticmethod(lambda x, axis, keepdims: _np.argmin(x, axis=1, keepdims=True))
    argmax = staticmethod(lambda x, axis, keepdims: _np.argmax(x, axis=1, keepdims=True))
    sort = staticmethod(lambda x, axis: _np.sort(x, axis=1))
    cumsum = staticmethod(lambda x, axis: _np.cumsum(x, axis=1))
    cumprod = staticmethod(lambda x, axis: _np.cumprod(x, axis=1))
    take_along_axis = staticmethod(lambda x, i, axis: _np.take_along_axis(x, i, axis=1))

    @staticmethod
    def rowkth(x, k):
        k = int(k)
        return _np.partition(x, k, axis=1)[:, k:k + 1]


def _load_rules():
    ns = {"np": _NP, "__builtins__": {}}
    # 规则源码已由评估器做过 AST 白名单校验；import numpy as np 在这里被替换为受限的 _NP
    body = "\n".join(l for l in RULES_SRC.splitlines() if l.strip() != "import numpy as np")
    exec(compile(body, "<rules>", "exec"), ns)
    return ns["check_rule"], ns["var_rule"]


def _pad(lists, fill):
    D = max(1, max((len(x) for x in lists), default=1))
    out = _np.full((len(lists), D), fill, dtype=_np.int64)
    for i, x in enumerate(lists):
        out[i, :len(x)] = x
    return out


def make_decoder(H, L, priors, info):
    check_rule, var_rule = _load_rules()
    H = H.tocsc()
    C, V = H.shape
    E = H.nnz
    var_of_edge = _np.repeat(_np.arange(V), _np.diff(H.indptr))
    chk_of_edge = H.indices.astype(_np.int64)
    chk_edges = [[] for _ in range(C)]
    for e in range(E):
        chk_edges[chk_of_edge[e]].append(e)
    var_edges = [list(range(H.indptr[v], H.indptr[v + 1])) for v in range(V)]
    CI = _pad(chk_edges, E)          # 填充位置指向哨兵 E
    VI = _pad(var_edges, E)
    cmask = CI < E
    vmask = VI < E
    p = _np.clip(_np.asarray(priors, dtype=_np.float64), 1e-15, 1 - 1e-15)
    prior = _np.log((1 - p) / p).reshape(V, 1)
    Hr = H.tocsr()
    Lr = L.tocsr()
    k = Lr.shape[0]
    S = SCHEDULE

    def run(syn):
        s = _np.asarray(syn, dtype=_np.uint8)
        sgn = (1.0 - 2.0 * s.astype(_np.float64)).reshape(C, 1)
        rng = _np.random.default_rng([0x5EED, _zlib.crc32(s.tobytes())])
        prev = prior.copy()
        best, best_w, nsol, total, last = None, None, 0, 0, None
        vc = _np.empty(E + 1)
        cv = _np.empty(E + 1)
        leg = 0
        while leg < S["max_legs"] and total < MAX_TOTAL_ITERS and nsol < S["stop_solutions"]:
            gamma = (_np.full((V, 1), S["gamma0"]) if leg == 0
                     else rng.uniform(S["gamma_low"], S["gamma_high"], size=(V, 1)))
            iters = S["first_iters"] if leg == 0 else S["leg_iters"]
            if leg == 0 or S["reset_messages"]:
                vc[:E] = prior[var_of_edge, 0]
            vc[E] = _BIG
            for _ in range(iters):
                if total >= MAX_TOTAL_ITERS:
                    break
                total += 1
                m = vc[CI]
                out = _np.asarray(check_rule(m, sgn), dtype=_np.float64)
                if out.shape != m.shape:
                    raise ValueError(f"check_rule returned shape {out.shape}, expected {m.shape}")
                cv[CI[cmask]] = out[cmask]
                cv[E] = 0.0
                inc = cv[VI]
                marg, vout = var_rule(prior, inc, gamma, prev)
                marg = _np.asarray(marg, dtype=_np.float64)
                vout = _np.asarray(vout, dtype=_np.float64)
                if marg.shape != (V, 1) or vout.shape != inc.shape:
                    raise ValueError(f"var_rule returned shapes {marg.shape}, {vout.shape}; expected {(V, 1)}, {inc.shape}")
                vc[VI[vmask]] = vout[vmask]
                vc[E] = _BIG
                prev = marg
                x = (marg[:, 0] < 0).astype(_np.uint8)
                last = x
                if _np.array_equal((Hr @ x) % 2, s):
                    w = float(prior[x.astype(bool), 0].sum())
                    nsol += 1
                    if best is None or w < best_w:
                        best, best_w = x, w
                    break
            leg += 1
        x = best if best is not None else (last if last is not None else _np.zeros(V, dtype=_np.uint8))
        return (Lr @ x) % 2

    def decode(syndrome):
        if not syndrome.any():
            return _np.zeros(k, dtype=_np.uint8)
        return run(syndrome)

    return decode
'''


def wrap_rules(rules_src: str, task) -> str:
    """规则源码 → 完整解码程序（引擎 + 规则）。规则先过 AST 白名单。"""
    mp = task.decoder["mp"]
    sched = validate_rules(rules_src, max_legs=int(mp.get("max_legs", 64)))
    return (ENGINE_TEMPLATE.replace("__RULES__", repr(rules_src))
            .replace("__SCHEDULE__", repr(sched)).replace("__MAXIT__", str(int(mp["max_total_iters"]))))


RELAY_RULES = '''\
import numpy as np

SCHEDULE = {"first_iters": __PRE__, "leg_iters": __LEG__, "max_legs": __LEGS__, "gamma0": __G0__,
            "gamma_low": __GL__, "gamma_high": __GH__, "stop_solutions": __S__, "reset_messages": True}


def check_rule(m, sgn):
    """min-sum, no scaling (Relay-BP, arXiv:2506.01779)."""
    a = np.abs(m)
    s = np.where(m < 0, -1.0, 1.0)
    tot = np.prod(s, axis=1, keepdims=True) * sgn
    min1 = np.rowkth(a, 0)
    min2 = np.rowkth(a, 1)
    return tot * s * np.where(a == min1, min2, min1)


def var_rule(prior, inc, gamma, prev):
    """disordered memory: Lambda = (1 - gamma) * prior + gamma * previous marginal."""
    lam = (1 - gamma) * prior + gamma * prev
    marg = lam + np.sum(inc, axis=1, keepdims=True)
    return marg, marg - inc
'''


def relay_rule_program(params: dict, max_legs: int = 64) -> str:
    """Relay-BP 写成规则（mp_rule 任务的参考）。段数上限由任务的 max_total_iters 实际决定。"""
    lo, hi = params["gamma_dist_interval"]
    return (RELAY_RULES.replace("__PRE__", str(int(params["pre_iter"])))
            .replace("__LEG__", str(int(params["set_max_iter"])))
            .replace("__LEGS__", str(int(params.get("max_legs", max_legs))))
            .replace("__G0__", repr(float(params["gamma0"]))).replace("__GL__", repr(float(lo)))
            .replace("__GH__", repr(float(hi))).replace("__S__", str(int(params["stop_nconv"]))))


def _schedule_json(s: dict) -> str:
    return json.dumps(s, sort_keys=True)
