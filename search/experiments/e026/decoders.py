"""E-026 decoders for sinter: BP-OSD (IBM parameters, stimbposd) and Relay-BP (relay5 parameters, relay_bp)."""
from search.experiments.e026.common import IBM_BPOSD, RELAY5


def sinter_decoders():
    from stimbposd import SinterDecoder_BPOSD
    from relay_bp.stim import SinterDecoder_RelayBP
    return {"bposd": SinterDecoder_BPOSD(**IBM_BPOSD), "relay5": SinterDecoder_RelayBP(**RELAY5)}
