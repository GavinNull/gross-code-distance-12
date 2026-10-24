"""Logical-error-rate data of the paper (SM S7 and S8): circuits, noise models, decoders, analysis.

Modules: circuits (the sampled circuits, built with the template of code/gross12/schedule.py), noise (SD6 with the idle
channel rescaled, p_idle = lambda p), na_noise (the neutral-atom circuit-level model of SM S8), decoders (BP-OSD and
Relay-BP with the parameters used for every circuit).  Scripts: tables.py (every ratio of the paper recomputed from
the shipped sampling statistics, and the identity of every sampled circuit with the circuits built here, through
sinter's task hash), sample_one.py (re-samples one ratio).  Optional dependencies: requirements-ler.txt.
"""
