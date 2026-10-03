"""Own builder for depth-8 uniform BB schedules (every check of a type: same prep slot and term order;
CNOTs in the 6 slots between prep and measurement)."""
import numpy as np
from baselines.schedule import Schedule, Layer


def uniform_schedule(code, PX, sX, PZ, sZ, name="uniform"):
    n2 = code.n2
    X = list(range(n2)); Ld = list(range(n2, 2 * n2)); Rd = list(range(2 * n2, 3 * n2)); Z = list(range(3 * n2, 4 * n2))
    data = Ld + Rd
    layers = [Layer() for _ in range(8)]
    layers[PX % 8].prep_x += X; layers[(PX + 7) % 8].meas_x += X
    layers[PZ % 8].prep_z += Z; layers[(PZ + 7) % 8].meas_z += Z
    from audext import check_order_from_terms
    for i in range(n2):
        ox = check_order_from_terms(code, "X", i, sX)
        oz = check_order_from_terms(code, "Z", i, sZ)
        for s in range(6):
            layers[(PX + 1 + s) % 8].cnots.append((X[i], data[ox[s]]))
            layers[(PZ + 1 + s) % 8].cnots.append((data[oz[s]], Z[i]))
    for Lr in layers:
        Lr.cnots.sort()
    sc = Schedule(name=name, num_qubits=4 * n2, data=data, x_checks=X, z_checks=Z, layers=layers)
    sc.validate(code.HX, code.HZ)
    return sc


LRC = dict(PX=0, sX=[0, 1, 2, 3, 4, 5], PZ=4, sZ=[3, 4, 5, 0, 1, 2])   # X: A then B ; Z: B (L data) then A (R data)
