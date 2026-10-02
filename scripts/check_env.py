"""环境自检：只验证各工具链能跑通，不做任何研究性实验。"""
import importlib
import sys

PKGS = ["stim", "sinter", "pymatching", "ldpc", "beliefmatching", "stimbposd",
        "numpy", "scipy", "networkx", "galois", "anthropic", "gymnasium", "torch"]


def check_imports():
    for name in PKGS:
        mod = importlib.import_module(name)
        print(f"  {name:15s} {getattr(mod, '__version__', 'ok')}")


def check_stim_pymatching():
    import stim, pymatching, numpy as np
    circ = stim.Circuit.generated("surface_code:rotated_memory_z", distance=3, rounds=3,
                                  after_clifford_depolarization=1e-3)
    dem = circ.detector_error_model(decompose_errors=True)
    m = pymatching.Matching.from_detector_error_model(dem)
    det, obs = circ.compile_detector_sampler().sample(2000, separate_observables=True)
    errs = np.sum(m.decode_batch(det)[:, 0] != obs[:, 0])
    print(f"  stim+pymatching: d=3 surface code, 2000 shots, {errs} logical errors")


def check_ldpc():
    import numpy as np
    from ldpc import BpOsdDecoder
    H = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)  # 3-bit repetition code
    dec = BpOsdDecoder(H, error_rate=0.1, osd_method="osd_cs", osd_order=2)
    print(f"  ldpc BP-OSD: decode([1,0]) -> {dec.decode(np.array([1, 0], dtype=np.uint8))}")


def check_torch():
    import torch
    print(f"  torch MPS available: {torch.backends.mps.is_available()}")


if __name__ == "__main__":
    print(f"Python {sys.version.split()[0]}")
    for f in (check_imports, check_stim_pymatching, check_ldpc, check_torch):
        f()
    print("环境 OK")
