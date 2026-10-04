"""参考解码器（H-005）：全部写成与候选**同一形式**的程序源码，在同一个沙箱会话里运行、用同一套计时。

  relay_bp   主参考，决定速度预算。官方包 relay-bp==0.2.2（arXiv:2506.01779）：RelayDecoderF64 + ObservableDecoderRunner。
  bposd      次要参考，E-002 / IBM 设置（ldpc BpOsdDecoder：min-sum 10000 次、ms_scaling_factor=0（自适应）、OSD-CS 7）。
  bplsd      次要参考，ldpc BpLsdDecoder（同样的 BP 参数，LSD-CS 7）。
  pymatching 自检任务（表面码）的参考：pymatching.Matching.from_check_matrix(H, weights, faults_matrix=L)。

参数以 JSON 字面量写进源码（`program_for(name, params)`），所以参考程序本身也有确定的源码哈希。
"""
from __future__ import annotations

import json

__all__ = ["REFERENCE_NAMES", "program_for", "RELAY_TEMPLATE", "BPOSD_TEMPLATE", "BPLSD_TEMPLATE",
           "PYMATCHING_TEMPLATE"]

RELAY_TEMPLATE = '''\
import numpy as np
import relay_bp

PARAMS = __PARAMS__


def make_decoder(H, L, priors, info):
    p = PARAMS
    dec = relay_bp.RelayDecoderF64(
        H.tocsr(), error_priors=np.asarray(priors, dtype=np.float64), alpha=p["alpha"], gamma0=p["gamma0"],
        pre_iter=p["pre_iter"], num_sets=p["num_sets"], set_max_iter=p["set_max_iter"],
        gamma_dist_interval=tuple(p["gamma_dist_interval"]), stop_nconv=p["stop_nconv"], seed=p["seed"])
    runner = relay_bp.ObservableDecoderRunner(dec, L.tocsc(), include_decode_result=False)

    def decode(syndrome):
        return runner.decode_observables(syndrome)

    return decode
'''

BPOSD_TEMPLATE = '''\
import numpy as np
from ldpc import BpOsdDecoder

PARAMS = __PARAMS__


def make_decoder(H, L, priors, info):
    dec = BpOsdDecoder(pcm=H, error_channel=[float(x) for x in priors], **PARAMS)
    Lr = L.tocsr()
    k = Lr.shape[0]

    def decode(syndrome):
        if not syndrome.any():
            return np.zeros(k, dtype=np.uint8)
        e = dec.decode(syndrome)
        return (Lr @ e) % 2

    return decode
'''

BPLSD_TEMPLATE = '''\
import numpy as np
from ldpc import BpLsdDecoder

PARAMS = __PARAMS__


def make_decoder(H, L, priors, info):
    dec = BpLsdDecoder(pcm=H, error_channel=[float(x) for x in priors], **PARAMS)
    Lr = L.tocsr()
    k = Lr.shape[0]

    def decode(syndrome):
        if not syndrome.any():
            return np.zeros(k, dtype=np.uint8)
        e = dec.decode(syndrome)
        return (Lr @ e) % 2

    return decode
'''

PYMATCHING_TEMPLATE = '''\
import numpy as np
import pymatching

PARAMS = __PARAMS__


def make_decoder(H, L, priors, info):
    p = np.clip(np.asarray(priors, dtype=np.float64), 1e-15, 0.5)
    m = pymatching.Matching.from_check_matrix(H, weights=np.log((1 - p) / p), faults_matrix=L)

    def decode(syndrome):
        return m.decode(syndrome)

    return decode
'''

_TEMPLATES = {"relay_bp": RELAY_TEMPLATE, "bposd": BPOSD_TEMPLATE, "bplsd": BPLSD_TEMPLATE,
              "pymatching": PYMATCHING_TEMPLATE}
REFERENCE_NAMES = tuple(_TEMPLATES) + ("mp_relay",)


def program_for(name: str, params: dict) -> str:
    """参考解码器的完整程序源码（与候选同一接口）。mp_relay 见 decoder_mp.reference_rules。"""
    if name == "mp_relay":
        from evaluators.decoder_mp import relay_rule_program
        return relay_rule_program(params)
    if name not in _TEMPLATES:
        raise ValueError(f"unknown reference decoder {name!r}")
    lit = repr(json.loads(json.dumps(params, sort_keys=True)))
    return _TEMPLATES[name].replace("__PARAMS__", lit)
