import stim,sinter,pymatching
print(stim.__version__, pymatching.__version__)
c=stim.Circuit.generated("surface_code:rotated_memory_z",distance=3,rounds=3,after_clifford_depolarization=0.001,before_round_data_depolarization=0.002,before_measure_flip_probability=0.003,after_reset_flip_probability=0.004)
print(c)
