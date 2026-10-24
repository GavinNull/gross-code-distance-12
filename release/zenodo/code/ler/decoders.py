"""Decoders used for every circuit (sinter custom decoders): "bposd" = BP-OSD (stimbposd / ldpc; min-sum, 10000
iterations, OSD-CS order 7, the parameters of arXiv:2308.07915) and "relay5" = Relay-BP (relay-bp package)."""
IBM_BPOSD = dict(max_bp_iters=10000, bp_method="min_sum", ms_scaling_factor=0, osd_method="osd_cs", osd_order=7)
RELAY5 = dict(gamma0=0.1, pre_iter=80, num_sets=300, set_max_iter=60, gamma_dist_interval=(-0.24, 0.66),
              stop_nconv=5)


def sinter_decoders():
    from stimbposd import SinterDecoder_BPOSD
    from relay_bp.stim import SinterDecoder_RelayBP
    return {"bposd": SinterDecoder_BPOSD(**IBM_BPOSD), "relay5": SinterDecoder_RelayBP(**RELAY5)}
