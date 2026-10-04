import numpy as np, pymatching
def make_decoder(H, L, priors, info):
    p = np.clip(np.asarray(priors, dtype=np.float64), 1e-15, 0.5)
    m = pymatching.Matching.from_check_matrix(H, weights=np.log((1 - p) / p), faults_matrix=L)
    A = np.random.default_rng(0).standard_normal((900, 900))
    def decode(syndrome):
        # heavy BLAS work that a "hide CPU" attacker hopes psutil won't charge
        C = A @ A
        _ = float(C[0, 0])
        return m.decode(syndrome)
    return decode
