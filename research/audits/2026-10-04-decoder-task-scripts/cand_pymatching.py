import numpy as np, pymatching
def make_decoder(H, L, priors, info):
    p = np.clip(np.asarray(priors, dtype=np.float64), 1e-15, 0.5)
    m = pymatching.Matching.from_check_matrix(H, weights=np.log((1 - p) / p), faults_matrix=L)
    def decode(syndrome):
        return m.decode(syndrome)
    return decode
